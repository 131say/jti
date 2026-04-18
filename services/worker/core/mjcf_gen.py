"""Blueprint JSON → MJCF (MuJoCo XML) для симуляции сборок."""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from worker.core.exceptions import BlueprintGenerationError
from worker.core.materials import resolve_part_material
from worker.generator import build_part_solid

_MUJO_JOINT = {"hinge": "hinge", "slider": "slide", "ball": "ball"}


def _length_scale_m(units: str) -> float:
    u = (units or "mm").lower()
    if u == "mm":
        return 1e-3
    if u == "m":
        return 1.0
    if u == "in":
        return 0.0254
    raise BlueprintGenerationError(f"Неизвестные global_settings.units: {units!r}")


def _norm_axis(axis: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = float(axis[0]), float(axis[1]), float(axis[2])
    n = math.sqrt(x * x + y * y + z * z)
    if n <= 1e-12:
        raise BlueprintGenerationError("joint.axis не может быть нулевым вектором")
    return (x / n, y / n, z / n)


def _part_mass_kg(
    part: dict[str, Any],
    density_by_mat: dict[str, float],
) -> float:
    sim = part.get("_sim_node")
    if sim and sim.get("mass_override") is not None:
        return float(sim["mass_override"])
    rm = resolve_part_material(part)
    if rm is not None:
        rho = rm.density_kg_m3
    else:
        mat_id = sim["mat_id"] if sim else None
        if not mat_id:
            raise BlueprintGenerationError(
                f"Нет simulation.nodes для part_id={part.get('part_id')!r}"
            )
        rho = density_by_mat.get(mat_id)
        if rho is None:
            raise BlueprintGenerationError(f"Неизвестный mat_id={mat_id!r}")
    solid = build_part_solid(part)
    vol_mm3 = float(solid.Volume())
    vol_m3 = vol_mm3 * 1e-9
    return float(rho) * vol_m3


def _part_friction(
    part: dict[str, Any],
    friction_by_mat: dict[str, float],
) -> float:
    """Трение для geom: пресет на детали или simulation.materials по mat_id."""
    rm = resolve_part_material(part)
    if rm is not None:
        return float(rm.friction)
    sim = part.get("_sim_node")
    if not sim:
        raise BlueprintGenerationError(
            f"Нет simulation.nodes для part_id={part.get('part_id')!r}"
        )
    mid = str(sim["mat_id"])
    mu = friction_by_mat.get(mid)
    if mu is None:
        raise BlueprintGenerationError(f"Неизвестный mat_id для friction: {mid!r}")
    return float(mu)


def _diag_inertia_kg_m2(part: dict[str, Any], mass_kg: float, scale_m_per_unit: float) -> tuple[float, float, float]:
    """Грубая оценка главных моментов инерции (примитив в тех же единицах, что и CAD)."""
    p = part["parameters"]
    kind = part["base_shape"]
    if kind == "box":
        L = float(p["length"]) * scale_m_per_unit
        W = float(p["width"]) * scale_m_per_unit
        H = float(p["height"]) * scale_m_per_unit
        ixx = mass_kg / 12.0 * (W * W + H * H)
        iyy = mass_kg / 12.0 * (L * L + H * H)
        izz = mass_kg / 12.0 * (L * L + W * W)
        return (ixx, iyy, izz)
    if kind == "cylinder":
        r = float(p["radius"]) * scale_m_per_unit
        h = float(p["height"]) * scale_m_per_unit
        izz = 0.5 * mass_kg * r * r
        ixx = 0.25 * mass_kg * r * r + mass_kg * h * h / 12.0
        return (ixx, ixx, izz)
    if kind == "fastener":
        return (mass_kg * 1e-4, mass_kg * 1e-4, mass_kg * 1e-4)
    if kind == "bearing":
        return (mass_kg * 1e-4, mass_kg * 1e-4, mass_kg * 1e-4)
    if kind == "gear":
        return (mass_kg * 1e-4, mass_kg * 1e-4, mass_kg * 1e-4)
    return (mass_kg * 1e-4, mass_kg * 1e-4, mass_kg * 1e-4)


def _prepare_parts(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    parts = list((blueprint.get("geometry") or {}).get("parts") or [])
    if not parts:
        raise BlueprintGenerationError("geometry.parts пуст")

    sim = blueprint.get("simulation") or {}
    nodes = sim.get("nodes") or []
    by_pid: dict[str, dict[str, Any]] = {n["part_id"]: n for n in nodes}

    out: list[dict[str, Any]] = []
    for p in parts:
        pid = p.get("part_id")
        if not pid:
            raise BlueprintGenerationError("part_id обязателен")
        row = dict(p)
        row["_sim_node"] = by_pid.get(pid)
        out.append(row)
    return out


def _joint_children(joints: list[dict[str, Any]]) -> set[str]:
    return {str(j["child_part"]) for j in joints}


def _joints_by_parent(joints: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    m: dict[str, list[dict[str, Any]]] = {}
    for j in joints:
        p = str(j["parent_part"])
        m.setdefault(p, []).append(j)
    return m


def _mjcf_joint_type(blueprint_type: str) -> str:
    if blueprint_type == "fixed":
        raise BlueprintGenerationError("joint type 'fixed' пока не поддержан в MJCF v1")
    t = _MUJO_JOINT.get(blueprint_type)
    if not t:
        raise BlueprintGenerationError(f"Неизвестный joint.type: {blueprint_type!r}")
    return t


def _add_inertial_and_geom(
    body: ET.Element,
    mesh_name: str,
    mass_kg: float,
    inertia: tuple[float, float, float],
    friction: float,
) -> None:
    iel = ET.SubElement(body, "inertial")
    iel.set("pos", "0 0 0")
    iel.set("mass", f"{mass_kg:.12g}")
    iel.set(
        "diaginertia",
        f"{inertia[0]:.12g} {inertia[1]:.12g} {inertia[2]:.12g}",
    )
    gel = ET.SubElement(body, "geom")
    gel.set("type", "mesh")
    gel.set("mesh", mesh_name)
    gel.set("contype", "1")
    gel.set("conaffinity", "1")
    # sliding, torsional, rolling (типовые вторичные коэффициенты)
    gel.set("friction", f"{friction:.12g} 0.005 0.0001")


def _append_body_tree(
    parent_el: ET.Element,
    part_id: str,
    parts_by_id: dict[str, dict[str, Any]],
    joints_by_parent: dict[str, list[dict[str, Any]]],
    mesh_names: dict[str, str],
    masses: dict[str, float],
    inertias: dict[str, tuple[float, float, float]],
    frictions: dict[str, float],
    joint_entry: dict[str, Any] | None,
    scale: float,
) -> None:
    part = parts_by_id[part_id]
    mesh_n = mesh_names[part_id]
    m = masses[part_id]
    inertia = inertias[part_id]
    fr = frictions[part_id]

    body = ET.SubElement(parent_el, "body")
    body.set("name", part_id)

    if joint_entry is not None:
        jt = _mjcf_joint_type(str(joint_entry["type"]))
        jel = ET.SubElement(body, "joint")
        jel.set("name", str(joint_entry["joint_id"]))
        jel.set("type", jt)
        ax = _norm_axis(
            (
                float(joint_entry["axis"][0]),
                float(joint_entry["axis"][1]),
                float(joint_entry["axis"][2]),
            )
        )
        jel.set("axis", f"{ax[0]:.12g} {ax[1]:.12g} {ax[2]:.12g}")
        ap = joint_entry["anchor_point"]
        px = float(ap[0]) * scale
        py = float(ap[1]) * scale
        pz = float(ap[2]) * scale
        jel.set("pos", f"{px:.12g} {py:.12g} {pz:.12g}")
        lim = joint_entry.get("limits")
        if lim is not None and jt in ("hinge", "slide"):
            jel.set("range", f"{float(lim[0]):.12g} {float(lim[1]):.12g}")

    _add_inertial_and_geom(body, mesh_n, m, inertia, fr)

    for ch in joints_by_parent.get(part_id, []):
        cid = str(ch["child_part"])
        _append_body_tree(
            body,
            cid,
            parts_by_id,
            joints_by_parent,
            mesh_names,
            masses,
            inertias,
            frictions,
            ch,
            scale,
        )


def build_mjcf_xml(blueprint: dict[str, Any]) -> str:
    """Строит XML MJCF: asset mesh на деталь, worldbody — дерево по joints, корни — siblings."""
    parts = _prepare_parts(blueprint)
    units = (blueprint.get("global_settings") or {}).get("units", "mm")
    scale = _length_scale_m(str(units))

    sim = blueprint.get("simulation") or {}
    materials = sim.get("materials") or []
    density_by_mat = {str(m["mat_id"]): float(m["density"]) for m in materials}
    friction_by_mat = {str(m["mat_id"]): float(m["friction"]) for m in materials}

    joints_raw = list(sim.get("joints") or [])
    joints_by_parent = _joints_by_parent(joints_raw)
    child_ids = _joint_children(joints_raw)

    parts_by_id = {str(p["part_id"]): p for p in parts}
    all_ids = set(parts_by_id.keys())
    for j in joints_raw:
        if str(j["parent_part"]) not in all_ids or str(j["child_part"]) not in all_ids:
            raise BlueprintGenerationError(
                f"joint ссылается на неизвестный part: {j!r}"
            )

    mesh_names = {str(p["part_id"]): f"{p['part_id']}_mesh" for p in parts}

    masses: dict[str, float] = {}
    inertias: dict[str, tuple[float, float, float]] = {}
    frictions: dict[str, float] = {}
    for p in parts:
        pid = str(p["part_id"])
        mk = _part_mass_kg(p, density_by_mat)
        masses[pid] = mk
        inertias[pid] = _diag_inertia_kg_m2(p, mk, scale)
        frictions[pid] = _part_friction(p, friction_by_mat)

    root = ET.Element("mujoco", model="AI_Forge_Sim")
    ET.SubElement(root, "compiler", angle="radian", meshdir="mesh", autolimits="true")
    opt = ET.SubElement(root, "option")
    opt.set("timestep", "0.002")
    opt.set("gravity", "0 0 -9.81")

    asset_el = ET.SubElement(root, "asset")
    for pid in sorted(all_ids):
        m_el = ET.SubElement(asset_el, "mesh")
        m_el.set("name", mesh_names[pid])
        m_el.set("file", f"{pid}.stl")
        m_el.set("scale", f"{scale:.12g} {scale:.12g} {scale:.12g}")

    wb = ET.SubElement(root, "worldbody")
    ET.SubElement(wb, "light", diffuse="1 1 1", pos="0 0 3", dir="0 0 -1")
    ET.SubElement(wb, "geom", name="floor", type="plane", size="5 5 0.1", pos="0 0 0")

    roots = [pid for pid in sorted(all_ids) if pid not in child_ids]
    if not roots:
        raise BlueprintGenerationError("Нет корневой детали (цикл в joints?)")

    for rid in roots:
        _append_body_tree(
            wb,
            rid,
            parts_by_id,
            joints_by_parent,
            mesh_names,
            masses,
            inertias,
            frictions,
            None,
            scale,
        )

    # Одиночные детали без родителя в joints, но не единственный корень: уже покрыто.
    # Несколько корней без связи: каждый уже добавлен как отдельное поддерево.
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def write_mjcf_file(blueprint: dict[str, Any], path: str | Path) -> None:
    """Записывает MJCF в файл (path — pathlib.Path или str)."""
    Path(path).write_text(build_mjcf_xml(blueprint), encoding="utf-8")
