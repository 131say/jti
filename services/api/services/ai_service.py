"""Генерация Blueprint из текста через Gemini."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import ValidationError

from core.resolver import BlueprintResolutionError, resolve_blueprint_variables
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
Your task: produce exactly ONE JSON object that conforms to Blueprint schema version 1.0 through 2.0.

Hard rules:
- Root keys: required metadata, global_settings, geometry, simulation. Optional global_variables (Blueprint v2.0 parametric constants). No other extra keys.
- metadata.schema_version: "1.0" … "2.0" (use "2.0" when you use global_variables and $expressions; "1.4" for revolved_profile without globals; "1.3" for extruded_profile; "1.2" for hole patterns; "1.1" for material presets on parts).
- metadata.project_id: short snake_case id derived from the user request.
- global_settings.units: prefer "mm" unless the user specifies otherwise. up_axis: "Z" unless specified.
- geometry.parts: at least one part. Supported base_shape values for generation: "cylinder", "box", "extruded_profile", "revolved_profile". Do NOT use "sphere" or "custom_profile" for this pipeline.
- Each part MUST have: part_id (unique string), base_shape, parameters, operations (array, may be empty []).
- cylinder parameters: radius, height (positive numbers).
- box parameters: length, width, height (positive numbers).
- extruded_profile (schema 1.3): non-standard plate/bracket shapes in XY. parameters.points = array of [x,y] vertices in order along a closed polygon (last point may equal first; server normalizes). parameters.height = extrusion along +Z (mm). Straight segments only; no sketch holes (use hole operations after extrusion). For bolt circles or grids of holes, use linear_pattern / circular_pattern (v1.2) in operations.
- revolved_profile (schema 1.4): bodies of revolution (shafts, pulleys). parameters.points = closed polygon in the XZ sketch plane: [x, z] where x is radial distance from the revolution axis (world Y) and MUST be >= 0 for every vertex (right half-plane only; do not cross the axis). parameters.angle = revolve angle in degrees, strictly (0, 360] (use 360 for full solids). One outer loop only; no holes in the sketch. Axis contact policy: the contour may touch x=0 only as one continuous edge on the axis or at isolated vertices; do NOT create multiple separate on-axis edge runs (non-manifold risk).
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

Output requirements:
- Respond with JSON only (no markdown fences, no commentary) when possible.
- Use JSON numbers for numeric fields when not using v2.0 expressions; with v2.0, use numbers for global_variables values and either numbers or allowed string expressions for linked dimensions as above. String fields that are not numeric (e.g. part_id, depth "through_all", selectors) must stay as plain strings without $ unless they intentionally encode a formula (rare).
"""

EDIT_SYSTEM_PROMPT = """You are editing an existing AI-Forge Blueprint v1.0/v1.1/v1.2/v1.3/v1.4/v2.0 (mechanical CAD).

The blueprint you receive is a Raw Blueprint: geometry may use string expressions with $variable references and global_variables (schema 2.0). Preserve formulas and global_variables structure when possible.

Engineering diagnostics (optional): If the user message includes a JSON block "Latest engineering diagnostics", it comes from the Forge worker (heuristic DFM checks: interference, thin features, overhangs, fillet/chamfer proportion). Use it to explain issues or suggest targeted edits when the user asks (e.g. adjust global_variables clearance if parts interfere, reduce fillet radius, tweak dimensions). Do not claim you re-ran the CAD kernel; these are automated heuristics, not manufacturing sign-off. Do not try to "auto-fix everything" unless the user explicitly asks for a fix.

You receive:
1) The user's natural-language change request.
2) The current valid blueprint as JSON (below in the user message).

Your task:
- Return exactly ONE complete JSON object that still conforms to Blueprint schema v1.0 through v2.0.
- Apply ONLY the changes implied by the user request; keep everything else identical unless consistency requires a small adjustment.
- Preserve part_id values, joint topology, and material references unless the user explicitly asks to rename or restructure.
- Use base_shape "cylinder", "box", "extruded_profile", or "revolved_profile" when needed (same pipeline as zero-shot).
- Same rules as creation for holes, fillets, chamfers, hole patterns (v1.2 linear_pattern / circular_pattern), simulation.materials, simulation.nodes, simulation.joints.

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
        "The previous JSON failed Pydantic validation for Blueprint (v1.x or v2.0). "
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
            resolve_blueprint_variables(raw.model_dump(mode="json"))
        except BlueprintResolutionError as e:
            raise AiBlueprintValidationError(str(e)) from e
        return raw

    assert last_err is not None
    raise AiBlueprintValidationError(
        "После автоматического исправления JSON всё ещё не соответствует Blueprint. "
        f"Уточните запрос. Детали: {last_err}"
    ) from last_err
