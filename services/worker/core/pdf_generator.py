"""
Сборочная PDF-инструкция (Drafting v2 MVP): граф из assembly_mates, топосорт, ReportLab + плейсхолдеры изображений.
"""

from __future__ import annotations

import heapq
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from worker.core.exceptions import BlueprintGenerationError


@dataclass(frozen=True)
class AssemblyStep:
    step_no: int
    source_part: str
    target_part: str | None
    target_operation_index: int | None
    detail_en: str


def _part_ids_in_order(blueprint: dict[str, Any]) -> list[str]:
    parts = (blueprint.get("geometry") or {}).get("parts") or []
    out: list[str] = []
    for p in parts:
        if isinstance(p, dict) and p.get("part_id"):
            out.append(str(p["part_id"]))
    return out


def build_mate_edges(
    blueprint: dict[str, Any],
) -> tuple[list[tuple[str, str]], list[str]]:
    """
    Рёбра (target_part -> source_part): target должен быть в сборке раньше source.
    Возвращает (edges, warnings).
    """
    w: list[str] = []
    mates_raw = blueprint.get("assembly_mates")
    if not mates_raw:
        return [], w
    part_ids = set(_part_ids_in_order(blueprint))
    edges: list[tuple[str, str]] = []
    for i, m in enumerate(mates_raw):
        if not isinstance(m, dict):
            w.append(f"assembly_mates[{i}]: неверный элемент")
            continue
        if m.get("type") not in (
            "snap_to_operation",
            "concentric",
            "coincident",
            "distance",
        ):
            continue
        src = str(m.get("source_part") or "").strip()
        tgt = str(m.get("target_part") or "").strip()
        if not src or not tgt:
            w.append(f"assembly_mates[{i}]: нет source_part/target_part")
            continue
        if src not in part_ids or tgt not in part_ids:
            w.append(
                f"assembly_mates[{i}]: неизвестный part_id ({src!r} / {tgt!r})"
            )
            continue
        edges.append((tgt, src))
    return edges, w


def topological_sort_parts(
    parts_order: list[str],
    edges: list[tuple[str, str]],
) -> tuple[list[str], bool]:
    """
    Топологическая сортировка (Kahn + min-heap по исходному порядку деталей).
    При цикле — добиваем оставшиеся детали в порядке parts_order.
    """
    nodes = list(parts_order)
    indeg: dict[str, int] = {p: 0 for p in nodes}
    adj: dict[str, list[str]] = defaultdict(list)
    for tgt, src in edges:
        if tgt in indeg and src in indeg:
            adj[tgt].append(src)
            indeg[src] += 1

    rank = {p: i for i, p in enumerate(parts_order)}

    heap: list[tuple[int, str]] = [
        (rank[p], p) for p in nodes if indeg[p] == 0
    ]
    heapq.heapify(heap)
    result: list[str] = []
    while heap:
        _, u = heapq.heappop(heap)
        result.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, (rank[v], v))

    cycle = len(result) < len(nodes)
    if cycle:
        seen = set(result)
        for p in parts_order:
            if p not in seen:
                result.append(p)
    return result, cycle


def build_assembly_steps(
    blueprint: dict[str, Any],
    warnings: list[str] | None = None,
) -> tuple[list[AssemblyStep], list[str]]:
    """
    Порядок шагов по топосорту из графа mates; для каждой детали после первой —
    описание установки по mate (если есть).
    """
    w = warnings if warnings is not None else []
    parts_order = _part_ids_in_order(blueprint)
    if not parts_order:
        return [], w
    if len(parts_order) == 1:
        return [], w

    edges, ew = build_mate_edges(blueprint)
    w.extend(ew)
    ordered, cyc = topological_sort_parts(parts_order, edges)
    if cyc:
        w.append(
            "assembly PDF: обнаружен цикл в графе assembly_mates — порядок шагов может быть некорректен"
        )

    mates_raw = blueprint.get("assembly_mates") or []
    mates_by_source: dict[str, dict[str, Any]] = {}
    for m in mates_raw:
        if not isinstance(m, dict):
            continue
        t = m.get("type")
        if t not in ("snap_to_operation", "concentric"):
            continue
        sid = str(m.get("source_part") or "").strip()
        if sid and sid not in mates_by_source:
            mates_by_source[sid] = m

    steps: list[AssemblyStep] = []
    step_no = 0
    for i, pid in enumerate(ordered):
        if i == 0:
            continue
        step_no += 1
        m = mates_by_source.get(pid)
        if m is not None:
            tgt = str(m.get("target_part") or "")
            toi = m.get("target_operation_index")
            toi_i = int(toi) if isinstance(toi, (int, float)) else None
            mt = m.get("type")
            if mt == "concentric":
                detail = (
                    f"Install {pid} concentric to {tgt} (hole index {toi_i}). "
                    f"Local +Z aligns with the hole axis; add coincident/distance if needed."
                )
            else:
                detail = (
                    f"Install {pid} onto {tgt} (hole operation index {toi_i}). "
                    f"Local +Z aligns with the hole axis."
                )
            steps.append(
                AssemblyStep(
                    step_no=step_no,
                    source_part=pid,
                    target_part=tgt,
                    target_operation_index=toi_i,
                    detail_en=detail,
                )
            )
        else:
            detail = (
                f"Add part {pid} to the assembly (no snap/concentric mate for this part)."
            )
            steps.append(
                AssemblyStep(
                    step_no=step_no,
                    source_part=pid,
                    target_part=None,
                    target_operation_index=None,
                    detail_en=detail,
                )
            )
    return steps, w


def _placeholder_png_bytes(lines: list[str], *, w: int = 520, h: int = 200) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise BlueprintGenerationError(
            "pdf_generator: требуется Pillow (pip install Pillow)"
        ) from e

    img = Image.new("RGB", (w, h), color=(235, 235, 238))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    y = 12
    for line in lines[:8]:
        t = line[:100]
        if font:
            draw.text((12, y), t, fill=(35, 35, 40), font=font)
        else:
            draw.text((12, y), t, fill=(35, 35, 40))
        y += 22
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_assembly_instructions_pdf(
    output_path: Path,
    blueprint: dict[str, Any],
    bom: dict[str, Any],
    *,
    step_warnings: list[str] | None = None,
) -> None:
    """
    Генерирует PDF: обложка, BOM, шаги сборки (EN), плейсхолдеры изображений.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:
        raise BlueprintGenerationError(
            "pdf_generator: требуется reportlab (pip install reportlab)"
        ) from e

    sw = step_warnings if step_warnings is not None else []
    meta = blueprint.get("metadata") or {}
    project_name = str(meta.get("project_id") or "project")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    mates_raw = blueprint.get("assembly_mates")
    has_mates = bool(mates_raw) and isinstance(mates_raw, list) and len(mates_raw) > 0

    steps: list[AssemblyStep] = []
    graph_warnings: list[str] = []
    if has_mates:
        steps, graph_warnings = build_assembly_steps(blueprint, warnings=[])
    sw.extend(graph_warnings)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
    )
    body = ParagraphStyle(
        "body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    story: list[Any] = []

    # --- Cover ---
    story.append(Paragraph("AI-Forge Assembly Instructions", title_style))
    story.append(
        Paragraph(f"<b>Project:</b> {escape(project_name)}", body)
    )
    story.append(Paragraph(f"<b>Date:</b> {escape(ts)}", body))
    story.append(Spacer(1, 8 * mm))
    cover_img = Image(io.BytesIO(_placeholder_png_bytes(["Assembly overview (preview)", "3D render placeholder — MVP"])), width=140 * mm, height=55 * mm)
    story.append(cover_img)
    story.append(PageBreak())

    # --- BOM ---
    story.append(Paragraph("Bill of Materials", styles["Heading2"]))
    story.append(Spacer(1, 4 * mm))

    bom_parts = (bom or {}).get("parts") or []
    table_data: list[list[str]] = [
        ["Part ID", "Material", "Mass (g)", "Cost (USD)", "Type"],
    ]
    for row in bom_parts:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("part_id") or "")
        mat = str(row.get("material") or "—")
        mass = f"{float(row.get('mass_g') or 0):.4g}"
        cost = f"{float(row.get('cost_usd') or 0):.4g}"
        it = str(row.get("item_type") or "manufactured")
        table_data.append([pid, mat, mass, cost, it])

    tw = doc.width
    tbl = Table(table_data, colWidths=[tw * 0.22, tw * 0.22, tw * 0.16, tw * 0.16, tw * 0.14])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8ec")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 8 * mm))
    total_m = float((bom or {}).get("total_mass_g") or 0)
    total_c = float((bom or {}).get("total_cost_usd") or 0)
    story.append(
        Paragraph(
            f"<b>Total mass:</b> {total_m:.4g} g &nbsp; <b>Total cost (estimate):</b> {total_c:.4g} USD",
            body,
        )
    )
    story.append(PageBreak())

    # --- Steps ---
    if len(_part_ids_in_order(blueprint)) <= 1:
        story.append(Paragraph("Single-part project", styles["Heading2"]))
        story.append(
            Paragraph(
                "No assembly steps. Use the BOM and 3D preview for manufacturing.",
                body,
            )
        )
    elif not has_mates:
        story.append(Paragraph("Assembly steps", styles["Heading2"]))
        story.append(
            Paragraph(
                "This assembly has no <i>assembly_mates</i> dependencies. "
                "See the full model overview and BOM. Use the Exploded View in AI-Forge for orientation.",
                body,
            )
        )
    elif not steps:
        story.append(Paragraph("Assembly steps", styles["Heading2"]))
        story.append(
            Paragraph(
                "Could not derive ordered steps from mates. Refer to BOM and 3D viewer.",
                body,
            )
        )
    else:
        story.append(Paragraph("Assembly steps", styles["Heading2"]))
        story.append(Spacer(1, 3 * mm))
        for st in steps:
            story.append(
                Paragraph(
                    f"<b>Step {st.step_no}:</b> {escape(st.detail_en)}",
                    body,
                )
            )
            img = Image(
                io.BytesIO(
                    _placeholder_png_bytes(
                        [
                            f"Step {st.step_no}",
                            f"Part: {st.source_part}",
                            f"Exploded / stage view (placeholder)",
                        ]
                    )
                ),
                width=120 * mm,
                height=45 * mm,
            )
            story.append(img)
            story.append(Spacer(1, 6 * mm))

    if sw:
        story.append(PageBreak())
        story.append(Paragraph("Generation notes", styles["Heading2"]))
        for line in sw[:40]:
            story.append(Paragraph(escape(line), body))

    doc.build(story)
