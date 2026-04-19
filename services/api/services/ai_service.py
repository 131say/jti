"""Генерация Blueprint из текста через Gemini."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import ValidationError

from core.mate_solver import MateResolutionError
from core.resolver import BlueprintResolutionError, finalize_resolved_blueprint
from models import ResolvedBlueprintPayload
from models_raw import RawBlueprintPayload

# Максимум попыток исправления после первой генерации (всего до 1 + N вызовов Gemini).
MAX_REPAIR_ATTEMPTS = 2

# --- Публичные исключения ---


class AiServiceError(Exception):
    """Ошибка LLM-слоя: ключ API, ответ модели, разбор JSON, валидация Blueprint."""


class AiMissingApiKeyError(AiServiceError):
    """Нет GEMINI_API_KEY / GOOGLE_API_KEY."""


class AiModelError(AiServiceError):
    """Сбой вызова Gemini или пустой ответ."""


class AiJsonExtractionError(AiServiceError):
    """Не удалось извлечь JSON из ответа модели."""


class AiBlueprintValidationError(AiServiceError):
    """JSON не прошёл валидацию RawBlueprintPayload / резолвера."""


SYSTEM_PROMPT = """You are a mechanical CAD engineer assistant for AI-Forge.
Your task: produce exactly ONE JSON object that conforms to Blueprint schema version 1.0 through 3.5.

Hard rules:
- Root keys: required metadata, global_settings, geometry, simulation. Optional global_variables (Blueprint v2.0 parametric constants). Optional assembly_mates (Blueprint v3.0+). No other extra keys.
- metadata.schema_version: "1.0" … "3.5" (use "3.5" when you use constraint mates concentric/coincident/distance; use "3.2" when you include bearings or gears without v3.5 mates; use "3.0" when you only use snap_to_operation mates; "2.1" when you include fasteners without mates; "2.0" when you use global_variables and $expressions; "1.4" for revolved_profile without globals; "1.3" for extruded_profile; "1.2" for hole patterns; "1.1" for material presets on parts).
- metadata.project_id: short snake_case id derived from the user request.
- global_settings.units: prefer "mm" unless the user specifies otherwise. up_axis: "Z" unless specified.
- geometry.parts: at least one part. Supported base_shape values for generation: "cylinder", "box", "extruded_profile", "revolved_profile", "fastener", "bearing", "gear". Do NOT use "sphere" or "custom_profile" for this pipeline.
- Shafts: use "cylinder" for simple smooth shafts; use "revolved_profile" for stepped shafts (profiles in XZ, revolve around Y). For bearing fits, prefer assembly_mates: housing seats the bearing OD via a hole operation; the shaft seats in the bearing bore the same way as a fastener snaps to a hole.
- Each part MUST have: part_id (unique string), base_shape, parameters, operations (array, may be empty []).
- cylinder parameters: radius, height (positive numbers).
- box parameters: length, width, height (positive numbers).
- extruded_profile (schema 1.3): non-standard plate/bracket shapes in XY. parameters.points = array of [x,y] vertices in order along a closed polygon (last point may equal first; server normalizes). parameters.height = extrusion along +Z (mm). Straight segments only; no sketch holes (use hole operations after extrusion). For bolt circles or grids of holes, use linear_pattern / circular_pattern (v1.2) in operations.
- revolved_profile (schema 1.4): bodies of revolution (shafts, pulleys). parameters.points = closed polygon in the XZ sketch plane: [x, z] where x is radial distance from the revolution axis (world Y) and MUST be >= 0 for every vertex (right half-plane only; do not cross the axis). parameters.angle = revolve angle in degrees, strictly (0, 360] (use 360 for full solids). One outer loop only; no holes in the sketch. Axis contact policy: the contour may touch x=0 only as one continuous edge on the axis or at isolated vertices; do NOT create multiple separate on-axis edge runs (non-manifold risk).
- Fasteners (schema 2.1): base_shape "fastener". parameters: type "bolt_hex" | "nut_hex" | "washer"; size "M6"|"M8"|"M10"|"M12"; for bolt_hex set length (mm) = shaft length under head (no modeled threads). fit: "clearance" | "tight" (reserved, default clearance). operations: [] for fasteners. Optional position [x,y,z] and rotation [rx,ry,rz] in degrees (world frame, same convention as cq.Rot) to place the part in the assembly.
- Bearings (schema 3.2): base_shape "bearing". parameters: series — catalog string, e.g. "608", "608zz", "6000zz", "6201" (see worker catalog). operations: []. BOM treats bearings as purchased; geometry is a simplified ring (no balls). Same +Z insertion convention as fasteners for mates.
- Gears (schema 3.2): base_shape "gear". parameters: module (mm), teeth (integer >= 4), thickness (mm), bore_diameter (mm), high_lod optional boolean default false. Preview (high_lod false): lightweight polygon on outer diameter for fast visualization. high_lod true: procedural trapezoid-tooth spur gear for prototyping and 3D print / Python export — good approximation, not mathematically perfect involute (not for heavy CNC). Expect longer build time and larger STEP/STL when high_lod is true.
- Gear reducers (two+ meshing spur gears, same module): Put shaft/hole spacing on a single source of truth in global_variables. Define e.g. `center_distance` = half-sum of pitch diameters plus backlash so the resolver computes it: `center_distance = (module * teeth1 + module * teeth2) / 2 + (0.05 * module)` (module must be identical for both gears). Use string expressions with `$center_distance` (and `$module`, `$teeth1`, `$teeth2` if helpful) for positions of parallel shaft holes in the housing — distance between gear rotation axes must equal `center_distance` exactly. With schema 3.5 you may instead drive spacing via assembly_mates type "distance" and value "$center_distance" after concentric mates to the holes. Do not hand-type unrelated decimals for meshing pairs.
- Assembly mates (schema 3.0+, strongly recommended instead of hand-matched coords): optional root array "assembly_mates".
  - Legacy snap (v3.0): type "snap_to_operation"; source_part; target_part; target_operation_index (hole index); reverse_direction optional. Aligns source +Z to hole axis and snaps origin to hole center (full pose).
  - Constraint assembly (v3.5): combine logical mates on the same source_part; resolver order per source is strict: (1) concentric or snap_to_operation for axis — type "concentric": same fields as snap but only sets rotation + shared axis (does NOT fix depth along the axis); (2) "coincident": source_part, target_part, offset (mm, default 0), flip (bool, 180° flip about an axis perpendicular to the mate axis) — MVP: moves source origin along the axis toward target part origin; (3) "distance": source_part, target_part, value (number or $global after resolve) — sets distance between part origins along the axis from step (1) if present, else along the line between centers. Use concentric + coincident instead of snap when you want explicit steps; use concentric + distance for gear/shaft center distance driven by global_variables (e.g. $center_distance). Omit position/rotation on source parts when mates define them (mates override explicit pose with a server warning).
- Clearance / DFM (critical): Nominal metric fastener shank diameter equals the M size in mm (e.g. M8 → ~8 mm). Through-holes in manufactured parts that must clear the bolt shank MUST be oversized: at least +0.4 mm, preferably +0.5 mm (e.g. M8 bolt → hole diameter ≥ 8.5 mm). Undersized holes will fail interference checks.
- Hole operations (optional): type must be "hole", diameter > 0, depth is either the string "through_all" OR a positive number (blind hole), position [x,y,z], direction [x,y,z] (any non-zero vector; will be normalized server-side).
- Fillet (optional): type "fillet", radius > 0, selector string (default "ALL" for all edges). Use CadQuery-style edge selectors to limit edges, e.g. "ALL", "|Z" (edges parallel to Z), ">Z", "<X". If the radius is too large for the geometry, the server may skip the fillet and record a warning.
- Chamfer (optional): type "chamfer", length > 0, selector like fillet. Same safety: oversized chamfer may be skipped with a warning.
- Hole patterns (schema 1.2, recommended for repeated holes): ONLY the child operation may be type "hole"; fillet/chamfer inside patterns are NOT supported.
  - linear_pattern: type "linear_pattern", count_x >= 1, count_y >= 1, spacing_x, spacing_y (mm), operation: { type "hole", diameter, depth, position [x,y,z] (base point for first copy), direction }. Copies form a grid in XY from that base position.
  - circular_pattern (bolt circle): type "circular_pattern", center [x,y,z] (required), radius > 0, count >= 1, angle in degrees (e.g. 360 for full circle), operation: { type "hole", diameter, depth, direction }. The inner hole "position" is ignored; holes are placed on circle in XY around center.
- Part material presets (optional, schema 1.1): on each part you may set "material" to one of: steel, aluminum_6061, abs_plastic, rubber. This drives density, friction, and STEP body color; optional "visual": { "color": "#RRGGBB", "roughness": 0..1 } overrides appearance. When using presets, keep simulation.nodes mat_id consistent with the part (same physics intent).
- simulation.materials: at least one material with mat_id, density (kg/m^3), friction (>= 0).
- simulation.nodes: one entry per geometry part with matching part_id and mat_id referencing a material.
- simulation.joints: array (may be empty []). If the assembly has connected parts, use joint types: hinge, slider, ball, or fixed. Include parent_part, child_part, joint_id, anchor_point [x,y,z], axis [x,y,z]. Optional limits: [min, max] for hinge/slider.
- global_variables (schema 2.0, optional): object map of variable_name (identifier) to JSON number only. Values MUST be plain numbers — no $ references between variables (no dependency graph). Example: "global_variables": { "shaft_diameter": 15.0, "clearance": 0.2 }.
- Parametric numeric fields (schema 2.0): anywhere in geometry/simulation you need a number, you MAY use a string expression referencing variables with a leading $, using only + - * / and parentheses. Examples: "$shaft_diameter", "($shaft_diameter / 2) + $clearance". Do NOT use functions (sin, max), attribute access, or conditionals. Unknown $name is an error.

- Assembly documentation (post-build): The Forge worker generates a PDF assembly guide (step order derived from assembly_mates, plus BOM table). When the user asks how to assemble the model or in what order to install parts, tell them to use the "Инструкции" (Assembly Guide) tab after a successful build or download docs/assembly_instructions.pdf from the project ZIP — do not invent steps that are not in the Blueprint.

Output requirements:
- Respond with JSON only (no markdown fences, no commentary) when possible.
- Use JSON numbers for numeric fields when not using v2.0 expressions; with v2.0, use numbers for global_variables values and either numbers or allowed string expressions for linked dimensions as above. String fields that are not numeric (e.g. part_id, depth "through_all", selectors) must stay as plain strings without $ unless they intentionally encode a formula (rare).
"""

EDIT_SYSTEM_PROMPT = """You are editing an existing AI-Forge Blueprint v1.0/v1.1/v1.2/v1.3/v1.4/v2.0/v2.1/v3.0/v3.2/v3.5 (mechanical CAD).

The blueprint you receive is a Raw Blueprint: geometry may use string expressions with $variable references and global_variables (schema 2.0). Preserve formulas and global_variables structure when possible.

Engineering diagnostics (optional): If the user message includes a JSON block "Latest engineering diagnostics", it comes from the Forge worker (heuristic DFM checks: interference, gear_mesh module/center distance, thin features, overhangs, fillet/chamfer proportion). Use it to explain issues or suggest targeted edits when the user asks (e.g. align `global_variables.center_distance` with `(module*(teeth1+teeth2))/2 + 0.05*module`, adjust clearance if parts interfere, reduce fillet radius). Do not claim you re-ran the CAD kernel; these are automated heuristics, not manufacturing sign-off. Do not try to "auto-fix everything" unless the user explicitly asks for a fix.

You receive:
1) The user's natural-language change request.
2) The current valid blueprint as JSON (below in the user message).

Your task:
- Return exactly ONE complete JSON object that still conforms to Blueprint schema v1.0 through v3.5.
- Apply ONLY the changes implied by the user request; keep everything else identical unless consistency requires a small adjustment.
- Preserve part_id values, joint topology, and material references unless the user explicitly asks to rename or restructure.
- Use base_shape "cylinder", "box", "extruded_profile", "revolved_profile", "fastener", "bearing", or "gear" when needed (same pipeline as zero-shot). For gears, set high_lod true only when the user needs export/print-ready tooth detail (procedural spur approximation); default false for quick previews. For two meshing spur gears use one module and drive shaft spacing from global_variables: `center_distance = (module * teeth1 + module * teeth2) / 2 + (0.05 * module)` with $ references. Prefer schema 3.5 assembly_mates: concentric each gear to its housing hole, then distance between gears with value "$center_distance" (resolver applies spacing along the shared axis after concentric). For fasteners keep clearance holes in mating parts ≥ M + 0.5 mm when possible. Stepped shafts: prefer "revolved_profile". Bearings: use assembly_mates (snap or concentric+coincident) to the housing hole.
- Same rules as creation for holes, fillets, chamfers, hole patterns (v1.2 linear_pattern / circular_pattern), simulation.materials, simulation.nodes, simulation.joints.
- If the user asks how to assemble or install parts in the real world, refer them to the generated PDF (Assembly Guide tab / docs/assembly_instructions.pdf in the ZIP) after a successful Forge build — it reflects assembly_mates and BOM.

Global variables (priority): If the user asks to change a dimension or tolerance that is already driven by global_variables, or that clearly should be a single source of truth (e.g. shaft diameter, wall thickness, clearance), update the value in global_variables and keep geometry referencing it via $name expressions. Do NOT duplicate the same numeric value in many part parameters when one global_variable can own it. If global_variables does not yet exist but parametric editing would help, you may introduce schema_version "2.0" and global_variables with numeric literals, then reference them with $ in geometry.

Output: JSON only when possible; use numbers for numeric fields where not using v2.0 expressions; keep Raw blueprint semantics (strings with $ where appropriate).
"""


def extract_json_from_text(text: str) -> dict[str, Any]:
    """Вырезает первый JSON-object из текста (поддерживает блок ```json ... ```)."""
    raw = text.strip()
    block = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if block:
        raw = block.group(1).strip()
    start = raw.find("{")
    if start < 0:
        raise AiJsonExtractionError("В ответе модели нет символа '{' — ожидался JSON-объект.")
    depth = 0
    for i in range(start, len(raw)):
        c = raw[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError as e:
                    raise AiJsonExtractionError(f"Некорректный JSON: {e}") from e
    raise AiJsonExtractionError("Незавершённый JSON-объект в ответе модели.")


def _get_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key or not str(key).strip():
        raise AiMissingApiKeyError(
            "Не задан GEMINI_API_KEY (или GOOGLE_API_KEY) в окружении API."
        )
    return str(key).strip()


def _model_name() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _response_text_to_dict(text_out: str) -> dict[str, Any]:
    try:
        data = json.loads(text_out.strip())
    except json.JSONDecodeError:
        data = extract_json_from_text(text_out)
    if not isinstance(data, dict):
        raise AiJsonExtractionError("Корень JSON должен быть объектом.")
    return data


def _generate_json_from_gemini(
    model: Any,
    gen_cfg: Any,
    user_message: str,
) -> dict[str, Any]:
    try:
        response = model.generate_content(
            user_message.strip(),
            generation_config=gen_cfg,
        )
    except Exception as e:
        raise AiModelError(f"Ошибка вызова Gemini: {e}") from e

    text_out = ""
    if response.text:
        text_out = response.text
    elif response.candidates:
        parts = response.candidates[0].content.parts
        text_out = "".join(getattr(p, "text", "") or "" for p in parts)

    if not text_out.strip():
        raise AiModelError("Пустой ответ от Gemini.")
    return _response_text_to_dict(text_out)


def _repair_prompt(invalid_data: dict[str, Any], err: ValidationError) -> str:
    return (
        "The previous JSON failed Pydantic validation for Blueprint (v1.x through v3.5). "
        "Output ONE corrected JSON object only (same schema as before).\n\n"
        "Validation errors:\n"
        + json.dumps(err.errors(), indent=2, default=str)
        + "\n\nInvalid JSON was:\n"
        + json.dumps(invalid_data, indent=2, default=str)
    )


def generate_blueprint_from_prompt(
    user_text: str,
    current_blueprint: RawBlueprintPayload | None = None,
    diagnostics_context: dict[str, Any] | None = None,
) -> RawBlueprintPayload:
    """
    Вызывает Gemini, извлекает JSON, валидирует как RawBlueprintPayload (формулы сохраняются).
    Без ``current_blueprint`` — zero-shot; с ним — итеративное редактирование (полный JSON в контексте).
    При ошибке валидации — до MAX_REPAIR_ATTEMPTS повторных запросов с контекстом ошибки.
    """
    _get_api_key()

    try:
        import google.generativeai as genai
    except ImportError as e:
        raise AiServiceError(
            "Пакет google-generativeai не установлен. Выполните: pip install google-generativeai"
        ) from e

    genai.configure(api_key=_get_api_key())
    if current_blueprint is None:
        system_instruction = SYSTEM_PROMPT
        user_message = user_text.strip()
    else:
        system_instruction = EDIT_SYSTEM_PROMPT
        user_message = (
            "User request:\n"
            + user_text.strip()
            + "\n\nCurrent blueprint JSON:\n"
            + json.dumps(current_blueprint.model_dump(mode="json"), indent=2, ensure_ascii=False)
        )
        if diagnostics_context:
            user_message += (
                "\n\nLatest engineering diagnostics (worker heuristics; optional context):\n"
                + json.dumps(diagnostics_context, indent=2, ensure_ascii=False)
            )

    model = genai.GenerativeModel(
        _model_name(),
        system_instruction=system_instruction,
    )

    gen_cfg = genai.GenerationConfig(
        temperature=0.15,
        response_mime_type="application/json",
    )

    data = _generate_json_from_gemini(model, gen_cfg, user_message)

    last_err: ValidationError | None = None
    for repair_attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        try:
            raw = RawBlueprintPayload.model_validate(data)
        except ValidationError as e:
            last_err = e
            if repair_attempt >= MAX_REPAIR_ATTEMPTS:
                break
            data = _generate_json_from_gemini(
                model,
                gen_cfg,
                _repair_prompt(data, e),
            )
            continue
        try:
            fin, _ = finalize_resolved_blueprint(
                raw.model_dump(mode="json"), mate_warnings=None
            )
            ResolvedBlueprintPayload.model_validate(fin)
        except BlueprintResolutionError as e:
            raise AiBlueprintValidationError(str(e)) from e
        except MateResolutionError as e:
            raise AiBlueprintValidationError(str(e)) from e
        except ValidationError as e:
            last_err = e
            if repair_attempt >= MAX_REPAIR_ATTEMPTS:
                break
            data = _generate_json_from_gemini(
                model,
                gen_cfg,
                _repair_prompt(data, e),
            )
            continue
        return raw

    assert last_err is not None
    raise AiBlueprintValidationError(
        "После автоматического исправления JSON всё ещё не соответствует Blueprint. "
        f"Уточните запрос. Детали: {last_err}"
    ) from last_err
