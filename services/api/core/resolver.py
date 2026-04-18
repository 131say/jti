"""
Разрешение global_variables и строковых выражений в сыром JSON Blueprint (до Pydantic).

Только безопасный разбор ast + ручной обход дерева; eval() не используется.
"""

from __future__ import annotations

import ast
import copy
import re
from typing import Any

# Имена переменных в выражениях: $shaft_diameter
_DOLLAR_VAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
# Строка без $, похожая на число (LLM иногда отдаёт "100" вместо 100)
_NUMERIC_LITERAL = re.compile(
    r"^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$"
)


class BlueprintResolutionError(ValueError):
    """Ошибка разрешения $-выражений или блока global_variables."""


def _is_plain_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _parse_global_variables(raw: dict[str, Any]) -> dict[str, float]:
    """MVP: значения global_variables — только числа, без ссылок друг на друга."""
    gv_raw = raw.get("global_variables")
    if gv_raw is None:
        return {}
    if not isinstance(gv_raw, dict):
        raise BlueprintResolutionError("global_variables должен быть объектом JSON")
    out: dict[str, float] = {}
    for key, val in gv_raw.items():
        if not isinstance(key, str) or not key:
            raise BlueprintResolutionError(
                "Ключи global_variables должны быть непустыми строками"
            )
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise BlueprintResolutionError(
                f"Недопустимое имя переменной в global_variables: {key!r}"
            )
        if isinstance(val, str) and "$" in val:
            raise BlueprintResolutionError(
                f"global_variables.{key}: в MVP значения не могут содержать выражения ($)"
            )
        if not _is_plain_number(val):
            raise BlueprintResolutionError(
                f"global_variables.{key} должен быть числом (int/float), без bool и строк"
            )
        out[key] = float(val)
    return out


def _substitute_dollar_vars(expr: str, gv: dict[str, float]) -> tuple[str, dict[str, float]]:
    """
    Заменяет $name на уникальные идентификаторы __GV0, __GV1, … для парсинга как Python expr.
    Возвращает выражение и окружение {__GVn: float}.
    """
    env: dict[str, float] = {}
    token_by_name: dict[str, str] = {}
    counter = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal counter
        name = m.group(1)
        if name not in gv:
            raise BlueprintResolutionError(f"Unknown variable ${name}")
        if name not in token_by_name:
            tok = f"__GV{counter}"
            counter += 1
            token_by_name[name] = tok
            env[tok] = float(gv[name])
        return token_by_name[name]

    new_expr = _DOLLAR_VAR.sub(repl, expr)
    if "$" in new_expr:
        raise BlueprintResolutionError(
            "Недопустимый символ $ в выражении (проверьте синтаксис переменных)"
        )
    return new_expr, env


def _eval_ast_expr(node: ast.expr, env: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if _is_plain_number(node.value):
            return float(node.value)
        raise BlueprintResolutionError("В выражении допустимы только числовые константы")

    if isinstance(node, ast.Name):
        if node.id not in env:
            raise BlueprintResolutionError(f"Неизвестный идентификатор в выражении: {node.id!r}")
        return float(env[node.id])

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval_ast_expr(node.operand, env)
        return v if isinstance(node.op, ast.UAdd) else -v

    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval_ast_expr(node.left, env)
        right = _eval_ast_expr(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if right == 0.0:
            raise BlueprintResolutionError("Division by zero")
        return left / right

    raise BlueprintResolutionError("Invalid syntax (разрешены только +, -, *, /, скобки и $переменные)")


def _evaluate_expression_string(expr: str, gv: dict[str, float]) -> float:
    s = expr.strip()
    if not s:
        raise BlueprintResolutionError("Пустое выражение")
    py_expr, env = _substitute_dollar_vars(s, gv)
    try:
        tree = ast.parse(py_expr, mode="eval")
    except SyntaxError as e:
        raise BlueprintResolutionError(f"Invalid syntax: {e}") from e
    if not isinstance(tree, ast.Expression):
        raise BlueprintResolutionError("Invalid syntax")
    return _eval_ast_expr(tree.body, env)


def _maybe_coerce_numeric_string(s: str) -> Any:
    t = s.strip()
    if _NUMERIC_LITERAL.match(t):
        try:
            return float(t)
        except ValueError:
            return s
    return s


def _transform(obj: Any, gv: dict[str, float], *, in_metadata: bool = False) -> Any:
    if isinstance(obj, dict):
        out_d: dict[str, Any] = {}
        for k, v in obj.items():
            if k == "global_variables":
                out_d[k] = copy.deepcopy(v)
            else:
                next_meta = in_metadata or k == "metadata"
                out_d[k] = _transform(v, gv, in_metadata=next_meta)
        return out_d
    if isinstance(obj, list):
        return [_transform(x, gv, in_metadata=in_metadata) for x in obj]
    if isinstance(obj, str):
        if "$" in obj:
            return _evaluate_expression_string(obj, gv)
        # metadata.schema_version и др. строки не трогаем (иначе "1.3" → float)
        if in_metadata:
            return obj
        return _maybe_coerce_numeric_string(obj)
    return obj


def resolve_blueprint_variables(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Копирует корневой dict, проверяет global_variables (только числа), рекурсивно
    заменяет строки с ``$`` на числа. Корень должен быть dict.
    """
    if not isinstance(raw, dict):
        raise BlueprintResolutionError("Корень Blueprint должен быть JSON-объектом")
    out = copy.deepcopy(raw)
    gv = _parse_global_variables(out)
    return _transform(out, gv)
