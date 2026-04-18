"""
Детерминированная генерация самодостаточного CadQuery-скрипта из Blueprint (MVP).

Не импортирует код воркера; только строковая сборка.
"""

from __future__ import annotations

import math
import re
from typing import Any

from worker.core.geometry import (
    expand_circular_pattern_to_hole_dicts,
    expand_linear_pattern_to_hole_dicts,
)
from worker.core.exceptions import BlueprintGenerationError
from worker.core.materials import resolve_part_material
from worker.core.profile_preflight import (
    validate_extruded_profile_points,
    validate_revolved_profile_points,
)

# Вставляется в eject build_model.py (без импорта пакета worker).
_EJECTED_FASTENER_HELPERS = '''
def _fastener_row(size: str) -> tuple[float, ...]:
    """shaft_d, head_af, head_h, nut_af, nut_h, hole_clr, washer_od, washer_t"""
    t = {
        "M6": (6.0, 10.0, 4.0, 10.0, 5.0, 6.4, 12.5, 1.6),
        "M8": (8.0, 13.0, 5.3, 13.0, 6.5, 8.5, 17.0, 1.6),
        "M10": (10.0, 16.0, 6.4, 16.0, 8.0, 10.5, 21.0, 2.0),
        "M12": (12.0, 18.0, 7.5, 18.0, 10.0, 12.5, 24.0, 2.5),
    }
    if size not in t:
        raise ValueError(f"unknown fastener size {size!r}")
    return t[size]


def _hex_r_vertex(af: float) -> float:
    return float(af) / math.sqrt(3.0)


def make_bolt_hex(size: str, length: float) -> cq.Shape:
    shaft_d, head_af, head_h, _, _, _, _, _ = _fastener_row(size)
    r = _hex_r_vertex(head_af)
    head = cq.Workplane("XY").polygon(6, r).extrude(head_h)
    bolt = head.faces(">Z").workplane().circle(shaft_d / 2.0).extrude(length)
    return bolt.val()


def make_nut_hex(size: str) -> cq.Shape:
    _, _, _, nut_af, nut_h, hole_clr, _, _ = _fastener_row(size)
    r = _hex_r_vertex(nut_af)
    body = cq.Workplane("XY").polygon(6, r).extrude(nut_h)
    return body.faces("<Z").workplane().circle(hole_clr / 2.0).cutThruAll().val()


def make_washer_flat(size: str) -> cq.Shape:
    _, _, _, _, _, hole_clr, washer_od, washer_t = _fastener_row(size)
    ro = washer_od / 2.0
    rid = hole_clr / 2.0
    w = (
        cq.Workplane("XY")
        .circle(ro)
        .extrude(washer_t)
        .faces("<Z")
        .workplane()
        .circle(rid)
        .cutThruAll()
    )
    return w.val()
'''


def _sanitize_var_name(part_id: str) -> str:
    """part_id -> валидный идентификатор Python для переменной."""
    s = str(part_id).strip().replace("-", "_").replace(" ", "_")
    if not s:
        s = "part"
    s = re.sub(r"[^0-9a-zA-Z_]", "_", s)
    if not s:
        s = "part"
    if s[0].isdigit() or not (s[0].isalpha() or s[0] == "_"):
        s = "part_" + s
    if s in {"def", "class", "if", "else", "for", "return", "import", "from", "None", "True", "False"}:
        s = s + "_"
    return s


def _py_num(x: Any) -> str:
    v = float(x)
    if math.isfinite(v) and v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return repr(v)


def _py_str(s: str) -> str:
    return repr(str(s))


def _normalize_edge_selector_py(selector: str) -> str | None:
    s = (selector or "").strip()
    if not s or s.upper() == "ALL":
        return None
    if s in ("X", "Y", "Z"):
        return f"|{s}"
    return s


def _emit_hole_block(
    var: str,
    op: dict[str, Any],
    *,
    indent: str,
) -> list[str]:
    lines: list[str] = []
    pos = op["position"]
    direction = op["direction"]
    diameter = float(op["diameter"])
    depth = op["depth"]
    lines.append(f"{indent}# Operation: hole")
    lines.append(f"{indent}_d = {_py_num(diameter)}")
    lines.append(
        f"{indent}_pos = ({_py_num(pos[0])}, {_py_num(pos[1])}, {_py_num(pos[2])})"
    )
    lines.append(
        f"{indent}_dir = ({_py_num(direction[0])}, {_py_num(direction[1])}, {_py_num(direction[2])})"
    )
    lines.append(f"{indent}_nx, _ny, _nz = float(_dir[0]), float(_dir[1]), float(_dir[2])")
    lines.append(f"{indent}_ln = math.sqrt(_nx * _nx + _ny * _ny + _nz * _nz)")
    lines.append(f"{indent}if _ln < 1e-9:")
    lines.append(f"{indent}    raise ValueError('hole direction must be non-zero')")
    lines.append(f"{indent}_ndir = (_nx / _ln, _ny / _ln, _nz / _ln)")
    lines.append(f"{indent}_radius = _d / 2.0")
    lines.append(f"{indent}_plane = Plane(_pos, None, _ndir)")
    lines.append(
        f"{indent}_cut_wp = cq.Workplane(_plane).add({var}).circle(_radius)"
    )
    if depth == "through_all":
        lines.append(f"{indent}{var} = _cut_wp.cutThruAll().val()")
    elif isinstance(depth, (int, float)) or (
        isinstance(depth, str) and depth.replace(".", "", 1).replace("-", "", 1).isdigit()
    ):
        d = float(depth)
        lines.append(f"{indent}_depth = {_py_num(d)}")
        lines.append(f"{indent}if _depth <= 0:")
        lines.append(f"{indent}    raise ValueError('hole depth must be > 0')")
        lines.append(f"{indent}{var} = _cut_wp.cutBlind(_depth).val()")
    else:
        lines.append(
            f"{indent}# WARNING: unsupported hole depth {depth!r} — hole omitted"
        )
    return lines


def _emit_fillet_block(var: str, op: dict[str, Any], *, indent: str) -> list[str]:
    radius = float(op["radius"])
    selector = str(op.get("selector") or "ALL")
    sel_py = _normalize_edge_selector_py(selector)
    lines = [f"{indent}# Operation: fillet", f"{indent}_r = {_py_num(radius)}"]
    lines.append(f"{indent}_cut_wp = cq.Workplane().add({var})")
    if sel_py is None:
        lines.append(f"{indent}{var} = _cut_wp.edges().fillet(_r).val()")
    else:
        lines.append(f"{indent}{var} = _cut_wp.edges({_py_str(sel_py)}).fillet(_r).val()")
    return lines


def _emit_chamfer_block(var: str, op: dict[str, Any], *, indent: str) -> list[str]:
    length = float(op["length"])
    selector = str(op.get("selector") or "ALL")
    sel_py = _normalize_edge_selector_py(selector)
    lines = [f"{indent}# Operation: chamfer", f"{indent}_cl = {_py_num(length)}"]
    lines.append(f"{indent}_cut_wp = cq.Workplane().add({var})")
    if sel_py is None:
        lines.append(f"{indent}{var} = _cut_wp.edges().chamfer(_cl).val()")
    else:
        lines.append(
            f"{indent}{var} = _cut_wp.edges({_py_str(sel_py)}).chamfer(_cl).val()"
        )
    return lines


def _emit_part_body(
    part: dict[str, Any],
    var: str,
    *,
    indent: str,
) -> tuple[list[str], bool]:
    """Возвращает (строки, ok) — ok=False если деталь пропущена."""
    lines: list[str] = []
    pid = part.get("part_id", "?")
    kind = part.get("base_shape")
    lines.append(f"{indent}# Part: {pid}")
    lines.append(f"{indent}# Base shape: {kind}")

    if kind == "fastener":
        p = part.get("parameters") or {}
        ft = p.get("type")
        size_lit = _py_str(str(p.get("size") or ""))
        if ft == "bolt_hex":
            length = float(p["length"])
            lines.append(
                f"{indent}{var} = make_bolt_hex({size_lit}, {_py_num(length)})"
            )
            return lines, True
        if ft == "nut_hex":
            lines.append(f"{indent}{var} = make_nut_hex({size_lit})")
            return lines, True
        if ft == "washer":
            lines.append(f"{indent}{var} = make_washer_flat({size_lit})")
            return lines, True
        lines.append(
            f"{indent}# WARNING: unknown fastener type {ft!r} — part omitted"
        )
        lines.append(f"{indent}{var} = None")
        return lines, False

    if kind == "cylinder":
        p = part.get("parameters") or {}
        r, h = float(p["radius"]), float(p["height"])
        lines.append(
            f"{indent}{var} = cq.Workplane(\"XY\").circle({_py_num(r)}).extrude({_py_num(h)}).val()"
        )
        return lines, True

    if kind == "box":
        p = part.get("parameters") or {}
        length, width, height = (
            float(p["length"]),
            float(p["width"]),
            float(p["height"]),
        )
        lines.append(
            f"{indent}{var} = cq.Workplane(\"XY\").box({_py_num(length)}, {_py_num(width)}, {_py_num(height)}).val()"
        )
        return lines, True

    if kind == "extruded_profile":
        p = part.get("parameters") or {}
        h = float(p["height"])
        pts_raw = p.get("points")
        if pts_raw is None:
            raise BlueprintGenerationError("extruded_profile: отсутствует parameters.points")
        cleaned = validate_extruded_profile_points(pts_raw)
        pts_lit = ", ".join(f"({_py_num(x)}, {_py_num(y)})" for x, y in cleaned)
        lines.append(f"{indent}_pts = [{pts_lit}]")
        lines.append(
            f"{indent}{var} = cq.Workplane(\"XY\").polyline(_pts).close().extrude({_py_num(h)}).val()"
        )
        return lines, True

    if kind == "revolved_profile":
        p = part.get("parameters") or {}
        ang = float(p["angle"])
        pts_raw = p.get("points")
        if pts_raw is None:
            raise BlueprintGenerationError(
                "revolved_profile: отсутствует parameters.points"
            )
        cleaned, an = validate_revolved_profile_points(pts_raw, ang)
        pts_lit = ", ".join(f"({_py_num(x)}, {_py_num(y)})" for x, y in cleaned)
        lines.append(f"{indent}_pts = [{pts_lit}]")
        lines.append(
            f"{indent}{var} = cq.Workplane(\"XZ\").polyline(_pts).close().revolve("
            f"{_py_num(an)}, (0, 0, 0), (0, 1, 0)).val()"
        )
        return lines, True

    lines.append(
        f"{indent}# WARNING: unsupported base_shape {kind!r} — part omitted (no solid)"
    )
    lines.append(f"{indent}{var} = None")
    return lines, False


def _emit_operations(
    var: str,
    part: dict[str, Any],
    *,
    indent: str,
) -> list[str]:
    lines: list[str] = []
    if part.get("base_shape") == "fastener":
        return lines
    for op in part.get("operations") or []:
        if not isinstance(op, dict):
            lines.append(f"{indent}# WARNING: invalid operation entry — skipped")
            continue
        t = op.get("type")
        if t == "hole":
            lines.extend(_emit_hole_block(var, op, indent=indent))
        elif t == "fillet":
            lines.extend(_emit_fillet_block(var, op, indent=indent))
        elif t == "chamfer":
            lines.extend(_emit_chamfer_block(var, op, indent=indent))
        elif t == "linear_pattern":
            lines.append(f"{indent}# Pattern: linear_pattern")
            try:
                holes = expand_linear_pattern_to_hole_dicts(op)
            except Exception as e:
                lines.append(
                    f"{indent}# WARNING: linear_pattern skipped ({e!s})"
                )
                continue
            for hi, h in enumerate(holes):
                lines.append(
                    f"{indent}# linear_pattern copy {hi + 1}/{len(holes)}"
                )
                lines.extend(_emit_hole_block(var, h, indent=indent))
        elif t == "circular_pattern":
            lines.append(f"{indent}# Pattern: circular_pattern")
            try:
                holes = expand_circular_pattern_to_hole_dicts(op)
            except Exception as e:
                lines.append(
                    f"{indent}# WARNING: circular_pattern skipped ({e!s})"
                )
                continue
            for hi, h in enumerate(holes):
                lines.append(
                    f"{indent}# circular_pattern copy {hi + 1}/{len(holes)}"
                )
                lines.extend(_emit_hole_block(var, h, indent=indent))
        else:
            lines.append(
                f"{indent}# WARNING: unsupported operation {t!r} was omitted"
            )
    return lines


def _emit_part_assy_loc(loc_var: str, part: dict[str, Any], indent: str) -> list[str]:
    pos = part.get("position")
    rot = part.get("rotation")
    if pos is None and rot is None:
        return [f"{indent}{loc_var} = cq.Location()"]
    px = float((pos or [0, 0, 0])[0])
    py = float((pos or [0, 0, 0])[1])
    pz = float((pos or [0, 0, 0])[2])
    rx = float((rot or [0, 0, 0])[0])
    ry = float((rot or [0, 0, 0])[1])
    rz = float((rot or [0, 0, 0])[2])
    return [
        f"{indent}{loc_var} = cq.Location(cq.Vector({_py_num(px)}, {_py_num(py)}, {_py_num(pz)}))"
        f" * cq.Location(cq.Rot({_py_num(rx)}, {_py_num(ry)}, {_py_num(rz)}))"
    ]


def generate_python_script(payload: dict[str, Any]) -> str:
    """Полный текст ``build_model.py``."""
    parts = (payload.get("geometry") or {}).get("parts") or []

    lines: list[str] = []
    lines.append('"""')
    lines.append("Auto-generated by AI-Forge (Blueprint -> CadQuery).")
    lines.append("Requires: cadquery")
    lines.append('"""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("import math")
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("import cadquery as cq")
    lines.append("from cadquery import Color")
    lines.append("from cadquery.occ_impl.geom import Plane")
    lines.append("")
    lines.append(_EJECTED_FASTENER_HELPERS.strip())
    lines.append("")
    lines.append("")
    lines.append("def build_assembly() -> cq.Assembly:")
    lines.append('    """Собирает модель по Blueprint (эквивалент пайплайна AI-Forge)."""')
    lines.append('    assembly = cq.Assembly(None, name="AI_Forge_Project")')

    ind = "    "
    used_vars: set[str] = set()

    def _unique_var(base: str) -> str:
        b = base or "part"
        v = b
        n = 2
        while v in used_vars:
            v = f"{b}_{n}"
            n += 1
        used_vars.add(v)
        return v

    for part in parts:
        if not isinstance(part, dict):
            lines.append(f'{ind}# WARNING: invalid part entry — skipped')
            continue
        pid = str(part.get("part_id") or "part")
        var = _unique_var(_sanitize_var_name(pid))
        body_lines, ok = _emit_part_body(part, var, indent=ind)
        lines.extend(body_lines)
        lines.extend(_emit_operations(var, part, indent=ind))

        loc_var = f"_loc_{var}"
        lines.extend(_emit_part_assy_loc(loc_var, part, ind))

        resolved = None
        try:
            resolved = resolve_part_material(part)
        except ValueError:
            resolved = None

        add_lines: list[str] = []
        if ok and resolved is not None:
            add_lines.append(
                f"{ind}assembly.add({var}, name={_py_str(pid)}, "
                f"color=Color({resolved.color_r}, {resolved.color_g}, {resolved.color_b}), "
                f"loc={loc_var})"
            )
        elif ok:
            add_lines.append(
                f"{ind}assembly.add({var}, name={_py_str(pid)}, loc={loc_var})"
            )
        else:
            add_lines.append(
                f"{ind}# WARNING: part {pid!r} was not added (no solid)"
            )

        lines.extend(add_lines)

    lines.append(f"{ind}return assembly")
    lines.append("")
    lines.append("")
    lines.append('if __name__ == "__main__":')
    lines.append("    _assy = build_assembly()")
    lines.append("    _out = Path(__file__).resolve().parent / \"ejected_export.step\"")
    lines.append('    _assy.export(str(_out), exportType="STEP")')
    lines.append('    print(f"Exported: {_out}")')

    return "\n".join(lines) + "\n"
