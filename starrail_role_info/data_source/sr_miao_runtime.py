from __future__ import annotations

import math
import json
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .sr_miao_models import (
    DamageAttributes,
    DamageContext,
    DamageResult,
    DamageValues,
)


def format_miao_number(value: float) -> str:
    """Match Miao's Format.comma(value, 1) used in Buff descriptions."""
    rounded = Decimal(str(float(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.1f}"


class _JSUndefined:
    """Small JS-undefined substitute used for optional Miao params."""

    def __bool__(self) -> bool:
        return False

    def __float__(self) -> float:
        return 0.0

    def __int__(self) -> int:
        return 0

    def __eq__(self, other: Any) -> bool:
        # Strict equality with false/zero must remain false.
        return isinstance(other, _JSUndefined)

    def __lt__(self, other: Any) -> bool:
        return 0 < other

    def __le__(self, other: Any) -> bool:
        return 0 <= other

    def __gt__(self, other: Any) -> bool:
        return 0 > other

    def __ge__(self, other: Any) -> bool:
        return 0 >= other

    def __add__(self, other: Any) -> Any:
        return other

    def __radd__(self, other: Any) -> Any:
        return other

    def __sub__(self, other: Any) -> Any:
        return -other

    def __rsub__(self, other: Any) -> Any:
        return other

    def __mul__(self, other: Any) -> Any:
        return 0

    def __rmul__(self, other: Any) -> Any:
        return 0

    def __truediv__(self, other: Any) -> float:
        return 0.0

    def __rtruediv__(self, other: Any) -> float:
        return math.inf if other else 0.0

    def __pow__(self, other: Any) -> float:
        return math.nan

    def __rpow__(self, other: Any) -> float:
        return math.nan


_JS_UNDEFINED = _JSUndefined()


class _NumericView(float):
    def __new__(
        cls,
        value: float,
        base: float = 0,
        plus: float = 0,
        pct: float = 0,
        inc: float = 0,
    ):
        instance = super().__new__(cls, value)
        instance.base = base
        instance.plus = plus
        instance.pct = pct
        instance.inc = inc
        return instance


class _AttrView:
    def __init__(self, context: DamageContext):
        self._context = context

    def __getattr__(self, name: str) -> Any:
        attr = self._context.attr
        if name == "hp":
            return _NumericView(
                attr.hp,
                attr.base_hp,
                attr.hp - attr.base_hp * (1 + attr.hp_pct / 100),
                attr.hp_pct,
            )
        if name == "atk":
            return _NumericView(
                attr.atk,
                attr.base_atk,
                attr.atk - attr.base_atk * (1 + attr.atk_pct / 100),
                attr.atk_pct,
            )
        if name in {"def", "defense"}:
            return _NumericView(
                attr.defense,
                attr.base_defense,
                attr.defense - attr.base_defense * (1 + attr.defense_pct / 100),
                attr.defense_pct,
            )
        if name == "shield":
            return _NumericView(
                attr.direct_value("shield"),
                base=100,
                plus=attr.direct_plus("shield"),
                pct=attr.direct_pct("shield"),
                inc=attr.shield_inc,
            )
        if name == "heal":
            return _NumericView(
                attr.direct_value("heal"),
                base=attr.direct_base("heal"),
                plus=attr.direct_plus("heal"),
                pct=attr.direct_pct("heal"),
                inc=attr.heal_inc,
            )
        if name == "recharge":
            return _NumericView(
                attr.recharge,
                base=100,
                plus=attr.recharge - 100,
            )
        if name == "speed":
            return _NumericView(
                attr.speed,
                attr.base_speed,
                attr.speed - attr.base_speed * (1 + attr.speed_pct / 100),
                attr.speed_pct,
            )
        if name in {
            "mastery",
            "cpct",
            "cdmg",
            "dmg",
            "phy",
            "enemydmg",
            "coloringDmg",
            "stance",
            "joy",
            "effPct",
            "effDef",
        }:
            attr_name = {
                "coloringDmg": "coloring_dmg",
                "enemydmg": "enemy_damage",
                "effPct": "eff_pct",
                "effDef": "eff_def",
            }.get(name, name)
            inc = attr.mastery_inc if name == "mastery" else 0
            base = attr.direct_base(attr_name)
            return _NumericView(
                attr.direct_value(attr_name),
                base=base,
                plus=attr.direct_plus(attr_name),
                pct=attr.direct_pct(attr_name),
                inc=inc,
            )
        if name in {
            "a",
            "a2",
            "a3",
            "e",
            "e2",
            "xe",
            "q",
            "q2",
            "q3",
            "t",
            "t2",
            "me",
            "me2",
            "mt",
            "mt1",
            "mt2",
            "dot",
            "break",
            "elation",
        }:
            return _TalentBonusView(attr.talent(name))
        if name == "enemy":
            return _EnemyAttrView(attr)
        if name == "superBreak":
            return _SuperBreakView(attr)
        if name == "sp":
            return _NumericView(getattr(attr, "sp", 0), base=getattr(attr, "sp", 0))
        if name in {
            "kx",
            "fykx",
            "fyplus",
            "fypct",
            "fybase",
            "fyinc",
            "multi",
            "elevated",
            "merrymakes",
            "punchline",
            "superBreakIgnore",
        }:
            attr_name = {
                "fykx": "reaction_resistance_reduction",
                "fyplus": "reaction_plus",
                "fypct": "reaction_base_pct",
                "fybase": "reaction_base_plus",
                "fyinc": "reaction_inc",
                "kx": "resistance_pen",
                "superBreakIgnore": "super_break_ignore",
            }.get(name, name)
            return _NumericView(getattr(attr, attr_name, 0), plus=getattr(attr, attr_name, 0))
        if name == "weapon":
            return _WeaponView(self._context)
        if name == "staticAttr":
            return _StaticAttrView(self._context)
        if name == "element":
            return self._context.element
        if name == "characterName":
            return self._context.name
        raise AttributeError(name)


class _TalentBonusView:
    def __init__(self, bonus: Any):
        self._bonus = bonus

    def __getattr__(self, name: str) -> Any:
        field_name = {
            "enemydmg": "enemy_damage",
            "enemyDmg": "enemy_damage",
            "def": "enemy_def",
            "ignore": "enemy_ignore",
        }.get(name, name)
        return getattr(self._bonus, field_name, 0)


class _EnemyAttrView:
    def __init__(self, attr: Any):
        self._attr = attr

    @property
    def def_(self) -> _NumericView:
        return _NumericView(self._attr.enemy_def, plus=self._attr.enemy_def)

    @property
    def ignore(self) -> _NumericView:
        return _NumericView(self._attr.enemy_ignore, plus=self._attr.enemy_ignore)

    @property
    def phy(self) -> _NumericView:
        return _NumericView(0)

    def __getattr__(self, name: str) -> Any:
        if name == "def":
            return self.def_
        return getattr(self, name)


class _SuperBreakView:
    def __init__(self, attr: Any):
        self._attr = attr

    @property
    def ignore(self) -> _NumericView:
        return _NumericView(self._attr.super_break_ignore, plus=self._attr.super_break_ignore)


class _StaticAttrView:
    """Expose the profile-only AttrItem fields used by SR calc rules."""

    def __init__(self, context: DamageContext):
        self._context = context

    def __getattr__(self, name: str) -> Any:
        attr = self._context.attr
        if name == "dmg":
            return _NumericView(attr.static_dmg, plus=attr.static_dmg)
        if name == "phy":
            return _NumericView(attr.static_phy, plus=attr.static_phy)
        if name == "coloringDmg":
            return _NumericView(attr.static_coloring_dmg, plus=attr.static_coloring_dmg)
        if name == "speed":
            return _NumericView(attr.static_speed, plus=attr.static_speed)
        if name == "stance":
            return _NumericView(attr.static_stance, plus=attr.static_stance)
        raise AttributeError(name)


class _TalentView:
    def __init__(self, context: DamageContext):
        self._context = context

    def __getattr__(self, kind: str) -> _TalentKindView:
        return _TalentKindView(self._context, kind)


class _TalentKindView:
    def __init__(self, context: DamageContext, kind: str):
        self._context = context
        self._kind = kind

    def __getitem__(self, name: str) -> Any:
        try:
            return self._context.talent(self._kind, str(name))
        except (KeyError, IndexError):
            return _JS_UNDEFINED


class _ParamsView:
    def __init__(self, context: DamageContext):
        self._context = context

    def __getattr__(self, name: str) -> Any:
        # JavaScript's `undefined` is falsey and coerces to zero in the
        # arithmetic/comparison expressions used by Miao's params checks.
        return self._context.params.get(name, _JS_UNDEFINED)

    def __getitem__(self, name: str) -> Any:
        return self._context.params.get(name, _JS_UNDEFINED)


class _DataView:
    """Dataset facade used by rules whose first callback argument is ``ds``."""

    def __init__(self, context: DamageContext):
        self._context = context

    def __getattr__(self, name: str) -> Any:
        if name == "attr":
            return _AttrView(self._context)
        if name == "talent":
            return _TalentView(self._context)
        if name == "params":
            return _ParamsView(self._context)
        if name == "trees":
            return _TreeView(self._context)
        if name == "weapon":
            return _WeaponView(self._context)
        if name == "calc":
            return _calc_value
        if name == "profile":
            return self._context.state.get("profile", {})
        if hasattr(self._context, name):
            return getattr(self._context, name)
        raise AttributeError(name)


class _TreeView:
    def __init__(self, context: DamageContext):
        self._context = context

    def __getitem__(self, name: str) -> Any:
        return bool(self._context.state.get("trees", {}).get(str(name), False))


class _TablesView:
    def __init__(self, context: DamageContext):
        self._context = context

    def __getitem__(self, name: int | str) -> Any:
        tables = self._context.state.get("tables", {})
        return tables.get(str(name), tables.get(name, _JS_UNDEFINED))


class _Logger:
    def info(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    debug = info
    warning = info
    warn = info
    error = info


_LOGGER = _Logger()


def _get_bounce_count(data: _DataView) -> int:
    context = data._context
    teammate_count = min(max(_finite_number(context.params.get("teammateCount")), 0), 3)
    return int(
        teammate_count
        + (12 if context.cons >= 1 and context.params.get("trueSelfTriggered") else 0)
    )


def _add_field_dmg(
    basic_damage: DamageResult | dict[str, Any],
    data: _DataView,
) -> dict[str, float]:
    context = data._context
    rate = _finite_number(context.talent("e", "额外真实伤害比例"))
    if context.cons >= 2:
        count = min(max(_finite_number(context.params.get("e2BuffCount")), 0), 4)
        rate += count * 0.06
    average = _finite_number(_member(basic_damage, "avg"))
    direct = _finite_number(_member(basic_damage, "dmg"))
    return {"avg": average * (1 + rate), "dmg": direct * (1 + rate)}


def _get_enhanced_basic(data: _DataView, methods: "DamageMethods") -> DamageResult:
    context = data._context
    multiplier = context.talent("a2", "单体伤害") + context.talent("a2", "全体伤害")
    return methods.basic(context.attr.hp * multiplier, "a")


def _get_true_self_dmg(data: _DataView, methods: "DamageMethods") -> DamageResult:
    context = data._context
    teammate_count = min(max(_finite_number(context.params.get("teammateCount")), 0), 3)
    bounce_count = teammate_count + (
        12 if context.cons >= 1 and context.params.get("trueSelfTriggered") else 0
    )
    e4_stacks = (
        min(max(_finite_number(context.params.get("e4Stacks")), 0), 24)
        if context.cons >= 4
        else 0
    )
    bounce_pct = context.talent("me2", "「真我」之诗•随机单体伤害") + e4_stacks * 0.06
    multiplier = context.talent("me", "技能伤害") + bounce_count * bounce_pct
    return methods.basic(context.attr.hp * multiplier, "me")


class _WeaponView:
    def __init__(self, context: DamageContext):
        self._context = context

    @property
    def name(self) -> str:
        return str(self._context.weapon.get("名称", ""))

    @property
    def affix(self) -> int:
        return int(self._context.weapon.get("精炼等级", 1))

    @property
    def type(self) -> str:
        return str(self._context.weapon.get("类型", self._context.weapon.get("武器类型", "")))


def _calc_value(value: Any) -> float:
    return float(value or 0)


def _step(start: float, increment: float | None = None) -> list[float]:
    increment = start / 4 if increment is None or increment == 0 else increment
    return [start + increment * index for index in range(6)]


def _js_floor(value: Any, *_ignored: Any) -> int:
    # JavaScript ignores extra arguments passed to Math.floor.
    return math.floor(value)


def _js_ceil(value: Any, *_ignored: Any) -> int:
    return math.ceil(value)


def _js_trunc(value: Any, *_ignored: Any) -> int:
    return math.trunc(value)


def _js_abs(value: Any, *_ignored: Any) -> float:
    return abs(value)


def _js_min(*values: Any) -> Any:
    return values[0] if len(values) == 1 else min(values)


def _js_max(*values: Any) -> Any:
    return values[0] if len(values) == 1 else max(values)


def _includes(values: Any, value: Any) -> bool:
    try:
        return value in values
    except TypeError:
        return False


def _js_entries(value: Any) -> list[tuple[Any, Any]]:
    if isinstance(value, dict):
        return list(value.items())
    return list(enumerate(value)) if isinstance(value, (list, tuple)) else []


def _js_keys(value: Any) -> list[Any]:
    return list(value.keys()) if isinstance(value, dict) else []


def _js_values(value: Any) -> list[Any]:
    return list(value.values()) if isinstance(value, dict) else []


def _js_iter(value: Any) -> Any:
    if isinstance(value, _JSUndefined) or value is None:
        return ()
    return value


def _js_number(value: Any, fallback: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if math.isfinite(number) else fallback


def _js_string(value: Any) -> str:
    return _js_to_string(value)


def _js_template(*values: Any) -> str:
    return "".join(_js_to_string(value) for value in values)


def _format_percent(value: float) -> str:
    rounded = Decimal(str(float(value) * 100)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )
    return f"{rounded:.1f}%"


def _format_comma(value: Any, digits: int = 0) -> str:
    digits = int(digits)
    quantum = Decimal(1).scaleb(-digits)
    number = Decimal(str(float(value))).quantize(quantum, rounding=ROUND_HALF_UP)
    rendered = f"{number:,.{digits}f}"
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _js_to_string(value: Any) -> str:
    if isinstance(value, _JSUndefined):
        return "undefined"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer():
            return str(int(value))
    return str(value)


def _js_add(left: Any, right: Any) -> Any:
    """Implement JavaScript's string-coercing `+` for translated expressions."""
    if isinstance(left, str) or isinstance(right, str):
        return _js_to_string(left) + _js_to_string(right)
    return left + right


def _js_nullish(value: Any) -> bool:
    return value is None or isinstance(value, _JSUndefined)


def _convert_string_concat(source: str) -> str:
    """Wrap JavaScript `number + 'text'` expressions in `_js_add`."""
    while True:
        plus = None
        quote = None
        escaped = False
        index = 0
        while index < len(source) - 1:
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in "'\"`":
                quote = char
                index += 1
                continue
            if char == "+":
                cursor = index + 1
                while cursor < len(source) and source[cursor].isspace():
                    cursor += 1
                if cursor < len(source) and source[cursor] in "'\"":
                    plus = index
                    break
            index += 1
        if plus is None:
            return source

        cursor = plus - 1
        while cursor >= 0 and source[cursor].isspace():
            cursor -= 1
        depth = {"(": 0, "[": 0, "{": 0}
        start = cursor + 1
        while cursor >= 0:
            char = source[cursor]
            if char in ")]}":
                depth[{')': '(', ']': '[', '}': '{'}[char]] += 1
            elif char in "([{":
                if depth[char]:
                    depth[char] -= 1
                else:
                    start = cursor + 1
                    break
            elif not any(depth.values()) and char in ",:;=":
                start = cursor + 1
                break
            cursor -= 1
        else:
            start = 0
        while start < plus and source[start].isspace():
            start += 1

        quote_start = plus + 1
        while quote_start < len(source) and source[quote_start].isspace():
            quote_start += 1
        string_end = quote_start + 1
        escaped = False
        while string_end < len(source):
            if escaped:
                escaped = False
            elif source[string_end] == "\\":
                escaped = True
            elif source[string_end] == source[quote_start]:
                break
            string_end += 1
        left = source[start:plus].rstrip()
        literal = source[quote_start : min(string_end + 1, len(source))]
        source = source[:start] + f"_js_add({left}, {literal})" + source[string_end + 1 :]


def _member(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name)


def _collapse_whitespace(source: str) -> str:
    result: list[str] = []
    quote: str | None = None
    escaped = False
    pending_space = False
    for char in source:
        if quote:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"`":
            if pending_space and result and result[-1] != " ":
                result.append(" ")
            pending_space = False
            quote = char
            result.append(char)
        elif char.isspace():
            pending_space = True
        else:
            if pending_space and result and result[-1] != " ":
                result.append(" ")
            pending_space = False
            result.append(char)
    return "".join(result).strip()


def _strip_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(?m)\s*//.*$", "", source).strip()


def _find_matching(source: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    quote: str | None = None
    escaped = False
    index = start
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise SyntaxError(f"unclosed {opening} in JavaScript rule")


def _split_top_level(source: str, separator: str = ",") -> list[str]:
    result: list[str] = []
    start = 0
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if stack:
                stack.pop()
        elif char == separator and not stack:
            result.append(source[start:index].strip())
            start = index + 1
        index += 1
    result.append(source[start:].strip())
    return [item for item in result if item]


def _convert_template(source: str) -> str:
    def replace(match: re.Match[str]) -> str:
        value = match.group(1)
        pieces: list[str] = []
        cursor = 0
        for expression in re.finditer(r"\$\{(.*?)\}", value):
            pieces.append(repr(value[cursor : expression.start()]))
            pieces.append(f"({_translate_expression(expression.group(1))})")
            cursor = expression.end()
        pieces.append(repr(value[cursor:]))
        if len(pieces) == 1:
            return repr(value)
        return f"_js_template({', '.join(pieces)})"

    return re.sub(r"`([^`]*)`", replace, source)


def _ternary_bounds(source: str, question: int) -> tuple[int, int, int] | None:
    depth = {"(": 0, "[": 0, "{": 0}
    quote: str | None = None
    escaped = False
    index = 0
    question_depth: tuple[int, int, int] | None = None
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
        elif char in "([{":
            depth[char] += 1
        elif char == ")":
            depth["("] -= 1
        elif char == "]":
            depth["["] -= 1
        elif char == "}":
            depth["{"] -= 1
        if index == question:
            question_depth = (depth["("], depth["["], depth["{"])
            break
        index += 1
    if question_depth is None:
        return None

    nesting = 0
    scan_depth = list(question_depth)
    colon = None
    index = question + 1
    while index < len(source):
        char = source[index]
        if char in "'\"`":
            quote = char
            end = index + 1
            escaped = False
            while end < len(source):
                if escaped:
                    escaped = False
                elif source[end] == "\\":
                    escaped = True
                elif source[end] == quote:
                    break
                end += 1
            index = end + 1
            continue
        if char == "(":
            scan_depth[0] += 1
        elif char == ")":
            scan_depth[0] -= 1
        elif char == "[":
            scan_depth[1] += 1
        elif char == "]":
            scan_depth[1] -= 1
        elif char == "{":
            scan_depth[2] += 1
        elif char == "}":
            scan_depth[2] -= 1
        if char == "?":
            nesting += 1
        elif char == ":" and nesting == 0 and tuple(scan_depth) == question_depth:
            colon = index
            break
        elif char == ":" and nesting > 0:
            nesting -= 1
        index += 1
    if colon is None:
        return None

    # Find the expression start at the same bracket depth.
    start = question - 1
    local_depth = {"(": question_depth[0], "[": question_depth[1], "{": question_depth[2]}
    while start >= 0:
        char = source[start]
        if char == ")":
            local_depth["("] += 1
        elif char == "(":
            if local_depth["("] > question_depth[0]:
                local_depth["("] -= 1
            else:
                break
        elif char == "]":
            local_depth["["] += 1
        elif char == "[":
            if local_depth["["] > question_depth[1]:
                local_depth["["] -= 1
            else:
                break
        elif char == "}":
            local_depth["{"] += 1
        elif char == "{":
            if local_depth["{"] > question_depth[2]:
                local_depth["{"] -= 1
            else:
                break
        elif local_depth == {
            "(": question_depth[0],
            "[": question_depth[1],
            "{": question_depth[2],
        } and (
            char == ","
            or char == ":"
            or (
                char == "="
                and (start == 0 or source[start - 1] not in "=!<>")
                and (start + 1 >= len(source) or source[start + 1] not in "=")
            )
        ):
            break
        start -= 1
    condition_start = start + 1
    while condition_start < question and source[condition_start].isspace():
        condition_start += 1

    # The false branch ends at the enclosing expression delimiter.
    end = colon + 1
    scan_depth = list(question_depth)
    quote = None
    while end < len(source):
        char = source[end]
        if quote:
            if char == quote and source[end - 1] != "\\":
                quote = None
        elif char in "'\"`":
            quote = char
        elif char == "(":
            scan_depth[0] += 1
        elif char == ")":
            if tuple(scan_depth) == question_depth:
                break
            scan_depth[0] -= 1
        elif char == "[":
            scan_depth[1] += 1
        elif char == "]":
            if tuple(scan_depth) == question_depth:
                break
            scan_depth[1] -= 1
        elif char == "{":
            scan_depth[2] += 1
        elif char == "}":
            if tuple(scan_depth) == question_depth:
                break
            scan_depth[2] -= 1
        elif char == "," and tuple(scan_depth) == question_depth:
            break
        end += 1
    return condition_start, colon, end


def _convert_ternary(source: str) -> str:
    while True:
        question = None
        quote: str | None = None
        escaped = False
        for index, char in enumerate(source):
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                continue
            if char in "'\"`":
                quote = char
            elif char == "?":
                question = index
                break
        if question is None:
            return source
        bounds = _ternary_bounds(source, question)
        if bounds is None:
            return source
        start, colon, end = bounds
        condition = _convert_ternary(source[start:question].strip())
        truthy = _convert_ternary(source[question + 1 : colon].strip())
        falsy = _convert_ternary(source[colon + 1 : end].strip())
        replacement = f"({truthy} if {condition} else {falsy})"
        source = source[:start] + replacement + source[end:]


def _translate_expression(source: str) -> str:
    source = _strip_comments(source.strip().rstrip(";"))
    source = _collapse_whitespace(source)
    source = _convert_string_concat(source)
    source = _convert_template(source)
    source = _convert_ternary(source)
    source = re.sub(r"\battr\.def\b", "attr.defense", source)
    source = re.sub(r"\bMath\.min\b", "_js_min", source)
    source = re.sub(r"\bMath\.max\b", "_js_max", source)
    source = re.sub(r"\bMath\.pow\b", "pow", source)
    source = re.sub(r"\bMath\.round\b", "round", source)
    source = re.sub(r"\bMath\.floor\b", "_js_floor", source)
    source = re.sub(r"\bMath\.ceil\b", "_js_ceil", source)
    source = re.sub(r"\bMath\.trunc\b", "_js_trunc", source)
    source = re.sub(r"\bMath\.abs\b", "_js_abs", source)
    source = re.sub(r"\bNumber\b", "_js_number", source)
    source = re.sub(r"\bString\b", "_js_string", source)
    source = re.sub(r"\bObject\.entries\b", "_js_entries", source)
    source = re.sub(r"\bObject\.keys\b", "_js_keys", source)
    source = re.sub(r"\bObject\.values\b", "_js_values", source)
    source = re.sub(
        r"((?:\[[^\]]*\]|'[^']*'|\"[^\"]*\"))\.includes\(([^()]*)\)",
        r"_includes(\1, \2)",
        source,
    )
    source = re.sub(r"\bFormat\.(?:percent|pct)\b", "_format_percent", source)
    source = re.sub(r"\bFormat\.comma\b", "_format_comma", source)
    source = re.sub(
        r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*!=\s*null\b",
        r"not _js_nullish(\1)",
        source,
    )
    source = re.sub(
        r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*==\s*null\b",
        r"_js_nullish(\1)",
        source,
    )
    source = source.replace("!==", "!=").replace("===", "==")
    source = source.replace("??", " or ")
    source = source.replace("&&", " and ").replace("||", " or ")
    source = re.sub(r"!(?!=)", " not ", source)
    source = re.sub(r"\btrue\b", "True", source)
    source = re.sub(r"\bfalse\b", "False", source)
    source = re.sub(r"\bundefined\b", "_JS_UNDEFINED", source)
    source = re.sub(r"\bnull\b", "None", source)
    source = re.sub(r"\.length\b", ".__len__()", source)
    # A few Miao modules keep an intermediate result in a file-scoped
    # variable.  The Python compiler executes each arrow function separately,
    # so persist that state on the damage context instead.
    source = re.sub(r"(?<![\w.])tmpDmg(?!\w)", 'state["tmpDmg"]', source)
    # JavaScript object literals and DamageResult values both expose these
    # fields through dot access.  Python dictionaries need an explicit lookup.
    source = re.sub(
        r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\.(dmg|avg)\b(?!\s*[+\-*/]?=)",
        lambda match: f'_member({match.group(1)}, "{match.group(2)}")',
        source,
    )
    source = re.sub(
        r"(?<=[{,])\s*([A-Za-z_$][\w$]*)\s*:",
        lambda match: f'"{match.group(1)}":',
        source,
    )
    source = re.sub(
        r"\{\s*([A-Za-z_$][\w$]*)\s*\}",
        lambda match: f'{{"{match.group(1)}": {match.group(1)}}}',
        source,
    )
    # Object shorthand is common in dynamic damage argument objects, often
    # mixed with explicitly named fields: ``{ dynamicDmg, dynamicCdmg: x }``.
    source = re.sub(
        r"(?<=[{,])\s*((?!(?:True|False|None|_JS_UNDEFINED)\b)[A-Za-z_$][\w$]*)\s*(?=[,}])",
        lambda match: f'"{match.group(1)}": {match.group(1)}',
        source,
    )
    source = re.sub(r"\b([A-Za-z_$][\w$]*)\+\+", r"\1 += 1", source)
    source = re.sub(r"\b([A-Za-z_$][\w$]*)--", r"\1 -= 1", source)
    for keyword in (
        "break",
        "continue",
        "class",
        "def",
        "from",
        "global",
        "import",
        "in",
        "is",
        "lambda",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    ):
        source = re.sub(rf"\bparams\.{keyword}\b", f'params["{keyword}"]', source)
    return source


def _read_statement(source: str, start: int) -> tuple[str, int]:
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    index = start
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"`":
            quote = char
        elif char in "([{":
            stack.append(char)
        elif char in ")]}":
            if stack:
                stack.pop()
            elif char == "}":
                return source[start:index].strip(), index
        elif not stack and char == ";":
            return source[start:index].strip(), index + 1
        elif not stack and char == "\n":
            statement = source[start:index].strip()
            if statement:
                return statement, index + 1
        index += 1
    return source[start:].strip(), len(source)


def _skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def _keyword_at(source: str, index: int, keyword: str) -> bool:
    end = index + len(keyword)
    return source.startswith(keyword, index) and (
        end >= len(source) or not (source[end].isalnum() or source[end] in "_$")
    )


def _parse_control_body(source: str, index: int) -> tuple[list[tuple[str, Any]], int]:
    index = _skip_space(source, index)
    if index < len(source) and source[index] == "{":
        end = _find_matching(source, index, "{", "}")
        return _parse_statements(source[index + 1 : end]), end + 1
    statement, end = _read_statement(source, index)
    return ([(("statement", statement))] if statement else []), end


def _parse_if(source: str, index: int) -> tuple[tuple[str, Any], int]:
    opening = source.find("(", index)
    if opening < 0:
        raise SyntaxError("missing if condition")
    closing = _find_matching(source, opening, "(", ")")
    nested, end = _parse_control_body(source, closing + 1)
    end = _skip_space(source, end)
    alternate: list[tuple[str, Any]] = []
    if _keyword_at(source, end, "else"):
        alternate_start = _skip_space(source, end + len("else"))
        if _keyword_at(source, alternate_start, "if"):
            nested_if, end = _parse_if(source, alternate_start)
            alternate = [nested_if]
        else:
            alternate, end = _parse_control_body(source, alternate_start)
    return ("if", (_translate_expression(source[opening + 1 : closing]), nested, alternate)), end


def _parse_for(source: str, index: int) -> tuple[tuple[str, Any], int]:
    opening = source.find("(", index)
    if opening < 0:
        raise SyntaxError("missing for header")
    closing = _find_matching(source, opening, "(", ")")
    header = source[opening + 1 : closing].strip()
    body, end = _parse_control_body(source, closing + 1)
    of_parts = re.match(
        r"^(?:const|let|var)\s+(\[[^]]+\]|[A-Za-z_$][\w$]*)\s+of\s+(.+)$",
        header,
        flags=re.S,
    )
    if of_parts:
        variable, expression = of_parts.groups()
        return ("for_of", (variable.strip(), _translate_expression(expression), body)), end
    parts = _split_top_level(header, ";")
    if len(parts) != 3:
        raise SyntaxError(f"unsupported for loop: {header}")
    return (
        "for_c",
        (
            _translate_statement(parts[0]),
            _translate_expression(parts[1]),
            _translate_statement(parts[2]),
            body,
        ),
    ), end


def _parse_statements(source: str) -> list[tuple[str, Any]]:
    statements: list[tuple[str, Any]] = []
    index = 0
    while index < len(source):
        index = _skip_space(source, index)
        if index >= len(source):
            break
        if _keyword_at(source, index, "if"):
            statement, index = _parse_if(source, index)
            statements.append(statement)
            continue
        if _keyword_at(source, index, "for"):
            statement, index = _parse_for(source, index)
            statements.append(statement)
            continue
        if _keyword_at(source, index, "else"):
            raise SyntaxError("unmatched else statement")
        statement, index = _read_statement(source, index)
        if statement:
            statements.append(("statement", statement))
    return statements


def _translate_statement(statement: str) -> str:
    statement = statement.strip().rstrip(";")
    statement = re.sub(r"^(const|let|var)\s+", "", statement)
    return _translate_expression(statement)


def _emit_statements(statements: list[tuple[str, Any]], indent: int = 1) -> list[str]:
    lines: list[str] = []
    prefix = "    " * indent
    for kind, value in statements:
        if kind == "if":
            condition, nested, alternate = value
            lines.append(f"{prefix}if {condition}:")
            nested_lines = _emit_statements(nested, indent + 1)
            lines.extend(nested_lines or [f"{prefix}    pass"])
            if alternate:
                lines.append(f"{prefix}else:")
                alternate_lines = _emit_statements(alternate, indent + 1)
                lines.extend(alternate_lines or [f"{prefix}    pass"])
            continue
        if kind == "for_of":
            variable, expression, nested = value
            if variable.startswith("["):
                names = [item.strip() for item in variable[1:-1].split(",")]
                lines.append(f"{prefix}for _loop_item in _js_iter({expression}):")
                lines.append(f"{prefix}    {', '.join(names)} = _loop_item")
            else:
                lines.append(f"{prefix}for {variable} in _js_iter({expression}):")
            nested_lines = _emit_statements(nested, indent + 1)
            lines.extend(nested_lines or [f"{prefix}    pass"])
            continue
        if kind == "for_c":
            initialization, condition, increment, nested = value
            lines.append(f"{prefix}{initialization}")
            lines.append(f"{prefix}while {condition}:")
            nested_lines = _emit_statements(nested, indent + 1)
            lines.extend(nested_lines or [f"{prefix}    pass"])
            lines.append(f"{prefix}    {increment}")
            continue
        statement = value.strip()
        destructured = re.match(
            r"^(?:const|let|var)\s*\{\s*([^}]+)\s*\}\s*=\s*(.*)$",
            statement,
            flags=re.S,
        )
        if destructured:
            names, expression = destructured.groups()
            temporary = f"_destructured_{len(lines)}"
            lines.append(f"{prefix}{temporary} = {_translate_expression(expression)}")
            for item in _split_top_level(names):
                parts = [part.strip() for part in item.split(":", 1)]
                name = parts[0]
                source_name = parts[-1]
                lines.append(f'{prefix}{name} = _member({temporary}, "{source_name}")')
            continue
        # JavaScript allows comma expressions for simple accumulator updates.
        pieces = _split_top_level(statement)
        for piece in pieces:
            if piece.startswith("return"):
                expression = piece[len("return") :].strip()
                lines.append(f"{prefix}return {_translate_expression(expression)}")
            else:
                lines.append(f"{prefix}{_translate_statement(piece)}")
    return lines


def _compile_special_function(source: str) -> Callable[..., Any] | None:
    if "lodash.forEach('一二三'.split('')," in source:

        def calculate(context: DamageContext, methods: DamageMethods):
            result = {"dmg": 0, "avg": 0}
            for number in "一二三":
                damage = methods(
                    context.talent("a", f"{number}段伤害"),
                    "a",
                )
                result["dmg"] += damage.dmg
                result["avg"] += damage.avg
            if context.cons > 0:
                damage = methods.basic(methods.context.attr.hp * 0.3)
                result["dmg"] += damage.dmg
                result["avg"] += damage.avg
            return result

        return calculate

    if "let buffCount = 12" in source and "光降之剑" in source:

        def create_eula_detail(context: DamageContext, methods=None):
            buff_count = 12
            if context.weapon.get("名称") == "松籁响起之时":
                buff_count = 13
                if int(context.weapon.get("精炼等级", 1)) >= 4:
                    buff_count = 14
            if context.cons == 6:
                buff_count += 11

            def calculate(detail_context: DamageContext, detail_methods: DamageMethods):
                return detail_methods(
                    detail_context.talent("q", "光降之剑基础伤害")
                    + detail_context.talent("q", "每层能量伤害") * buff_count,
                    "q",
                    "phy",
                )

            return {
                "title": f"光降之剑{buff_count}层伤害",
                "params": {"gj": True},
                "dmg": calculate,
            }

        return create_eula_detail

    if "title: `${cons === 6 ? '半血' : ''}Q每跳治疗`" in source:

        def create_diona_detail(context: DamageContext, methods=None):
            def calculate(detail_context: DamageContext, detail_methods: DamageMethods):
                return detail_methods.heal(
                    detail_context.talent("q", "持续治疗量2")[0]
                    * detail_context.attr.hp
                    / 100
                    + detail_context.talent("q", "持续治疗量2")[1]
                )

            return {
                "title": f"{'半血' if context.cons == 6 else ''}Q每跳治疗",
                "dmg": calculate,
            }

        return create_diona_detail

    if "let count = cons === 6 ? 4 : 3" in source:

        def create_chongyun_detail(context: DamageContext, methods=None):
            count = 4 if context.cons == 6 else 3

            def calculate(detail_context: DamageContext, detail_methods: DamageMethods):
                return detail_methods(
                    detail_context.talent("q", "技能伤害") * count,
                    "q",
                )

            return {
                "title": f"Q {count}柄灵刃总伤害",
                "dmg": calculate,
            }

        return create_chongyun_detail
    return None


def compile_js_function(source: str) -> Callable[..., Any]:
    source = _strip_comments(source.strip())
    special = _compile_special_function(source)
    if special:
        return special
    arrow = source.find("=>")
    if arrow < 0:
        raise SyntaxError(f"invalid Miao function: {source}")
    body = source[arrow + 2 :].strip()
    if body.startswith("{"):
        body_end = _find_matching(body, 0, "{", "}")
        body = body[1:body_end]
        lines = _emit_statements(_parse_statements(body))
    else:
        lines = [f"    return {_translate_expression(body)}"]
    if not any(line.strip().startswith("return ") for line in lines):
        lines.append("    return None")

    function_source = "def _generated(context, methods=None):\n"
    function_source += "    attr = _AttrView(context)\n"
    function_source += "    ds = _DataView(context)\n"
    function_source += "    data = ds\n"
    function_source += "    talent = _TalentView(context)\n"
    function_source += "    params = _ParamsView(context)\n"
    function_source += "    weapon = _WeaponView(context)\n"
    function_source += "    cons = context.cons\n"
    function_source += "    level = context.level\n"
    function_source += "    refine = max(0, int(context.weapon.get('精炼等级', 1)) - 1)\n"
    function_source += "    element = context.element\n"
    function_source += "    characterName = context.name\n"
    function_source += "    weaponTypeName = context.weapon.get('类型', context.weapon.get('武器类型', ''))\n"
    function_source += "    currentTalent = context.state.get('currentTalent', '')\n"
    function_source += "    mastery = context.state.get('mastery', '')\n"
    function_source += "    calc = _calc_value\n"
    function_source += "    step = _step\n"
    function_source += "    dmg = methods\n"
    function_source += "    basic = methods.basic if methods else None\n"
    function_source += "    dynamic = methods.dynamic if methods else None\n"
    function_source += "    reaction = methods.reaction if methods else None\n"
    function_source += "    heal = methods.heal if methods else None\n"
    function_source += "    shield = methods.shield if methods else None\n"
    function_source += "    swirl = methods.swirl if methods else None\n"
    function_source += "    trees = _TreeView(context)\n"
    function_source += "    tables = _TablesView(context)\n"
    function_source += "    state = context.state\n"
    function_source += "    charId = context.state.get('charId', 0)\n"
    function_source += "    logger = _LOGGER\n"
    function_source += "    addFieldDmg = _add_field_dmg\n"
    function_source += "    getEnhancedBasic = _get_enhanced_basic\n"
    function_source += "    getTrueSelfDmg = _get_true_self_dmg\n"
    function_source += "    getBounceCount = _get_bounce_count\n"
    function_source += "    game = 'gs'\n"
    function_source += "    _ = None\n"
    function_source += "\n".join(lines) + "\n"
    namespace = {
        "_AttrView": _AttrView,
        "_DataView": _DataView,
        "_TalentView": _TalentView,
        "_ParamsView": _ParamsView,
        "_WeaponView": _WeaponView,
        "_TreeView": _TreeView,
        "_TablesView": _TablesView,
        "_calc_value": _calc_value,
        "_step": _step,
        "_js_floor": _js_floor,
        "_js_ceil": _js_ceil,
        "_js_trunc": _js_trunc,
        "_js_abs": _js_abs,
        "_js_number": _js_number,
        "_js_string": _js_string,
        "_js_template": _js_template,
        "_js_entries": _js_entries,
        "_js_keys": _js_keys,
        "_js_values": _js_values,
        "_js_iter": _js_iter,
        "_js_min": _js_min,
        "_js_max": _js_max,
        "_includes": _includes,
        "_member": _member,
        "_format_percent": _format_percent,
        "_format_comma": _format_comma,
        "_js_add": _js_add,
        "_js_nullish": _js_nullish,
        "_JS_UNDEFINED": _JS_UNDEFINED,
        "_LOGGER": _LOGGER,
        "_add_field_dmg": _add_field_dmg,
        "_get_enhanced_basic": _get_enhanced_basic,
        "_get_true_self_dmg": _get_true_self_dmg,
        "_get_bounce_count": _get_bounce_count,
        "math": math,
        "min": min,
        "max": max,
        "pow": pow,
        "round": round,
    }
    try:
        exec(function_source, namespace)
    except SyntaxError as error:
        raise SyntaxError(f"failed to translate Miao function {source}: {error}") from error
    return namespace["_generated"]


@dataclass
class DamageMethods:
    context: DamageContext
    calculator: Any

    def __call__(
        self,
        multiplier: float = 0,
        talent: str | bool = False,
        element: str | bool = False,
        basic_num: float = 0,
        mode: str = "talent",
        dynamic_data: dict[str, Any] | bool = False,
    ) -> DamageResult:
        data = dynamic_data if isinstance(dynamic_data, dict) else {}
        tokens = element.split(",") if isinstance(element, str) else []
        physical = "phy" in tokens
        coloring = "coloringDmg" in tokens
        scene = "scene" in tokens
        reaction = next(
            (
                token
                for token in tokens
                if token not in {"", "phy", "scene", "coloringDmg"}
            ),
            None,
        )
        if mode == "basic":
            return self.calculator.calculate(
                talents=str(talent or ""),
                reaction=reaction,
                base=float(basic_num),
                physical=physical,
                dynamic_dmg=float(data.get("dynamicDmg", 0)),
                dynamic_phy=float(data.get("dynamicPhy", 0)),
                dynamic_cpct=float(data.get("dynamicCpct", 0)),
                dynamic_cdmg=float(data.get("dynamicCdmg", 0)),
                dynamic_enemy_damage=float(data.get("dynamicEnemydmg", 0)),
                coloring=coloring,
                scene=scene,
            )
        return self.calculator.calculate(
            multiplier=float(multiplier),
            talents=str(talent or ""),
            reaction=reaction,
            physical=physical,
            dynamic_dmg=float(data.get("dynamicDmg", 0)),
            dynamic_phy=float(data.get("dynamicPhy", 0)),
            dynamic_cpct=float(data.get("dynamicCpct", 0)),
            dynamic_cdmg=float(data.get("dynamicCdmg", 0)),
            dynamic_enemy_damage=float(data.get("dynamicEnemydmg", 0)),
            coloring=coloring,
            scene=scene,
        )

    def basic(
        self,
        value: float = 0,
        talent: str | bool = False,
        element: str | bool = False,
        dynamic_data: dict[str, Any] | bool = False,
    ) -> DamageResult:
        return self(value, talent, element, value, "basic", dynamic_data)

    def dynamic(
        self,
        multiplier: float = 0,
        talent: str | bool = False,
        dynamic_data: dict[str, Any] | bool = False,
        element: str | bool = False,
    ) -> DamageResult:
        return self(multiplier, talent, element, 0, "talent", dynamic_data)

    def reaction(self, element: str = "", talent: str = "fy") -> DamageResult:
        if element in {"shock", "burn", "windShear", "bleed"}:
            talent = "dot"
        elif element in {
            "superBreak",
            "lightningBreak",
            "fireBreak",
            "windBreak",
            "physicalBreak",
            "quantumBreak",
            "imaginaryBreak",
            "iceBreak",
        }:
            talent = "break"
        return self(0, talent, element, 0, "basic", False)

    def heal(self, value: float) -> DamageResult:
        return self.calculator.heal(float(value))

    def shield(self, value: float) -> DamageResult:
        return self.calculator.shield(float(value))

    def swirl(self) -> DamageResult:
        return self.reaction("swirl")


_BREAK_BASE = {
    1: 54.0,
    2: 58.0,
    3: 62.0,
    4: 67.53,
    5: 70.51,
    6: 73.52,
    7: 76.57,
    8: 79.64,
    9: 82.74,
    10: 85.87,
    11: 91.49,
    12: 97.07,
    13: 102.59,
    14: 108.06,
    15: 113.47,
    16: 118.84,
    17: 124.15,
    18: 129.41,
    19: 134.62,
    20: 139.77,
    21: 149.33,
    22: 158.80,
    23: 168.18,
    24: 177.46,
    25: 186.65,
    26: 195.75,
    27: 204.75,
    28: 213.66,
    29: 222.48,
    30: 231.20,
    31: 246.43,
    32: 261.18,
    33: 275.47,
    34: 289.32,
    35: 302.73,
    36: 315.71,
    37: 328.29,
    38: 340.47,
    39: 352.26,
    40: 363.67,
    41: 408.12,
    42: 451.79,
    43: 494.68,
    44: 536.82,
    45: 578.22,
    46: 618.92,
    47: 658.91,
    48: 698.23,
    49: 736.89,
    50: 774.90,
    51: 871.06,
    52: 964.87,
    53: 1056.42,
    54: 1145.79,
    55: 1233.06,
    56: 1318.30,
    57: 1401.58,
    58: 1482.96,
    59: 1562.52,
    60: 1640.31,
    61: 1752.32,
    62: 1861.90,
    63: 1969.12,
    64: 2074.07,
    65: 2176.80,
    66: 2277.39,
    67: 2375.91,
    68: 2472.42,
    69: 2566.97,
    70: 2659.64,
    71: 2780.30,
    72: 2898.60,
    73: 3014.60,
    74: 3128.37,
    75: 3239.98,
    76: 3349.47,
    77: 3456.92,
    78: 3562.38,
    79: 3665.91,
    80: 3767.55,
}
_BREAK_COEFFICIENT = {
    "lightningBreak": 1.0,
    "fireBreak": 2.0,
    "windBreak": 1.5,
    "physicalBreak": 2.0,
    "quantumBreak": 0.5,
    "imaginaryBreak": 0.5,
    "iceBreak": 1.0,
    "superBreak": 1.0,
}
_DOT_COEFFICIENT = {"shock": 2.0, "burn": 1.0, "windShear": 1.0, "bleed": 1.0}


class _MiaoCalculator:
    def __init__(self, context: DamageContext):
        self.context = context

    def _defense(self, enemy_def: float, enemy_ignore: float) -> float:
        level = max(1, int(self.context.level))
        enemy_level = max(1, int(self.context.state.get("enemyLevel", 103)))
        down = max(0.0, min(1.0, (enemy_def + enemy_ignore) / 100))
        player = 200 + level * 10
        enemy = 200 + enemy_level * 10
        return player / (player + enemy * (1 - down))

    def calculate(
        self,
        multiplier: float = 0,
        talents: str = "",
        reaction: str | None = None,
        base: float = 0,
        physical: bool = False,
        dynamic_dmg: float = 0,
        dynamic_phy: float = 0,
        dynamic_cpct: float = 0,
        dynamic_cdmg: float = 0,
        dynamic_enemy_damage: float = 0,
        coloring: bool = False,
        scene: bool = False,
    ) -> DamageResult:
        attr = self.context.attr
        talent_groups = str(talents or "").split(",") if talents else []
        multi = attr.multi / 100
        direct_damage = attr.direct_base("phy" if physical else "dmg") + attr.direct_plus(
            "phy" if physical else "dmg"
        )
        direct_enemy_damage = attr.direct_base("enemy_damage") + attr.direct_plus(
            "enemy_damage"
        )
        direct_cpct = attr.direct_base("cpct") + attr.direct_plus("cpct")
        direct_cdmg = attr.direct_base("cdmg") + attr.direct_plus("cdmg")
        damage_num = 1 + direct_damage / 100
        damage_num += (dynamic_phy if physical else dynamic_dmg) / 100
        enemy_damage = 1 + (direct_enemy_damage + dynamic_enemy_damage) / 100
        cpct = (direct_cpct + dynamic_cpct) / 100
        cdmg = (direct_cdmg + dynamic_cdmg) / 100
        enemy_def = attr.enemy_def
        enemy_ignore = attr.enemy_ignore
        plus = 0.0
        talent_pct = 0.0
        for key in talent_groups:
            if not key:
                continue
            bonus = attr.talent(key)
            damage_num += bonus.dmg / 100
            enemy_damage += bonus.enemy_damage / 100
            cpct += bonus.cpct / 100
            cdmg += bonus.cdmg / 100
            enemy_def += bonus.enemy_def
            enemy_ignore += bonus.enemy_ignore
            multi += bonus.multi / 100
            plus += bonus.plus
            talent_pct += bonus.pct / 100
        if reaction == "superBreak":
            enemy_ignore += attr.super_break_ignore
        defense = self._defense(enemy_def, enemy_ignore)
        resistance = 1 + attr.resistance_pen / 100
        reduce = 0.9
        cpct = max(0.0, min(1.0, cpct))
        if cpct == 0:
            cdmg = 0
        if reaction == "elation":
            elation_base = _finite_number(
                self.context.state.get("elationBase", {}).get(str(self.context.level))
            )
            pct = multiplier + talent_pct + multi
            merrymakes = 1 + attr.merrymakes / 100
            joy = 1 + (
                attr.direct_base("joy") + attr.direct_plus("joy")
            ) / 100
            punchline = 1 + attr.punchline * 5 / (attr.punchline + 240)
            common = (
                elation_base
                * pct
                * merrymakes
                * joy
                * punchline
                * defense
                * resistance
                * reduce
                * enemy_damage
            )
            return DamageResult(
                avg=common * (1 + cpct * cdmg),
                crit=common * (1 + cdmg),
            )
        amount = (
            base * (1 + multi) + plus
            if base
            else float(attr.atk) * (multiplier + talent_pct) * (1 + multi) + plus
        )
        if reaction in _BREAK_COEFFICIENT or reaction in _DOT_COEFFICIENT or reaction == "entanglement":
            level = max(1, min(80, int(self.context.level)))
            coefficient = _BREAK_COEFFICIENT.get(reaction, _DOT_COEFFICIENT.get(reaction, 1.0))
            if reaction == "entanglement":
                coefficient = 0.6
            value = (
                _BREAK_BASE[level]
                * coefficient
                * (1 + attr.direct_value("stance") / 100)
                * enemy_damage
                * defense
                * resistance
                * reduce
            )
            return DamageResult(avg=value)
        common = amount * damage_num * enemy_damage * defense * resistance * reduce
        if reaction == "skillDot":
            return DamageResult(avg=common)
        return DamageResult(avg=common * (1 + cpct * cdmg), crit=common * (1 + cdmg))

    def heal(self, value: float) -> DamageResult:
        attr = self.context.attr
        direct_heal = attr.direct_base("heal") + attr.direct_plus("heal")
        return DamageResult(
            avg=float(value) * (1 + direct_heal / 100 + attr.heal_inc / 100)
        )

    def shield(self, value: float) -> DamageResult:
        attr = self.context.attr
        direct_shield = attr.direct_base("shield") + attr.direct_plus("shield")
        return DamageResult(
            avg=float(value) * direct_shield / 100 * attr.shield_inc / 100
        )


def _finite_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _profile_number(properties: dict[str, Any], *names: str, default: float = 0.0) -> float:
    for name in names:
        if name in properties:
            return _finite_number(properties[name], default)
    return default


def _ratio_points(value: Any) -> float:
    number = _finite_number(value)
    return number * 100 if abs(number) <= 3 else number


def _talent_levels(profile: dict[str, Any]) -> dict[str, int]:
    levels = {
        "a": 1,
        "a2": 1,
        "e": 1,
        "e2": 1,
        "q": 1,
        "t": 1,
        "me": 1,
        "me2": 1,
        "mt": 1,
        "mt2": 1,
    }
    rows = profile.get("行迹", profile.get("talents", []))
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("名称", row.get("name", "")))
            level = max(1, int(_finite_number(row.get("等级", row.get("level", 1)), 1)))
            key = "a" if "普攻" in title else "e" if "战技" in title else "q" if "终结" in title else "t"
            levels[key] = level
    direct = profile.get("talent", {})
    if isinstance(direct, dict):
        for key, value in direct.items():
            raw = value.get("level") if isinstance(value, dict) else value
            levels[str(key)] = max(1, int(_finite_number(raw, 1)))
    return levels


def _talent_data(character: dict[str, Any], levels: dict[str, int]) -> dict[str, dict[str, list[Any]]]:
    result: dict[str, dict[str, list[Any]]] = {}
    source = character.get("talent", {})
    if not isinstance(source, dict):
        return result
    for key, block in source.items():
        if not isinstance(block, dict) or not isinstance(block.get("tables"), dict):
            continue
        result[str(key)] = {}
        for table in block["tables"].values():
            if not isinstance(table, dict) or not isinstance(table.get("values"), list):
                continue
            values = table["values"]
            result[str(key)][str(table.get("name", ""))] = values
            # DamageContext.talent selects the requested level from the full
            # table.  Keep the selected level on the context below.
    return result


def _role_trees(profile: dict[str, Any], character: dict[str, Any]) -> dict[str, bool]:
    raw = profile.get("行迹节点", profile.get("trees", profile.get("行迹树", [])))
    trees: dict[str, bool] = {}
    if isinstance(raw, dict):
        trees.update({str(key): bool(value) for key, value in raw.items() if value})
    elif isinstance(raw, list):
        trees.update({str(value): True for value in raw})

    promotion = int(_finite_number(profile.get("晋升", profile.get("promotion", 0))))
    unlocked_by_promotion = {1: 2, 2: 4, 3: 6}
    tree_data = character.get("treeData", {})
    if isinstance(tree_data, dict):
        for node in tree_data.values():
            if not isinstance(node, dict) or node.get("type") != "skill":
                continue
            idx = int(_finite_number(node.get("idx")))
            required = unlocked_by_promotion.get(idx)
            if required is not None and promotion >= required:
                trees[f"10{idx}"] = True
    return trees


def _role_sets(profile: dict[str, Any]) -> dict[str, int]:
    relics = profile.get("遗器", profile.get("relics", profile.get("artis", [])))
    sets: dict[str, int] = {}
    if isinstance(relics, list):
        for relic in relics:
            if not isinstance(relic, dict):
                continue
            key = str(
                relic.get(
                    "所属套装",
                    relic.get("setId", relic.get("set_id", relic.get("name", relic.get("名称", "")))),
                )
            )
            if key:
                sets[key] = sets.get(key, 0) + 1
    elif isinstance(relics, dict):
        for key, value in relics.items():
            if isinstance(value, (int, float)):
                count = value
            elif isinstance(value, list):
                count = len(value)
            elif isinstance(value, dict):
                count = value.get("count", value.get("数量", 0))
            else:
                count = 0
            if _finite_number(count) > 0:
                sets[str(key)] = int(_finite_number(count))
    return sets


def _build_context(name: str, profile: dict[str, Any], character: dict[str, Any], enemy_level: int = 103) -> DamageContext:
    properties = profile.get("属性", profile.get("attr", {}))
    if not isinstance(properties, dict):
        raise ValueError("缺少属性对象")
    base_atk = _profile_number(properties, "基础攻击力", "baseAtk", "atkBase")
    base_hp = _profile_number(properties, "基础生命值", "baseHp", "hpBase")
    base_defense = _profile_number(properties, "基础防御力", "baseDef", "defBase")
    base_speed = _profile_number(properties, "基础速度", "baseSpeed", "speedBase")
    atk = _profile_number(properties, "atk", default=base_atk + _profile_number(properties, "额外攻击力"))
    hp = _profile_number(properties, "hp", default=base_hp + _profile_number(properties, "额外生命值"))
    defense = _profile_number(properties, "def", default=base_defense + _profile_number(properties, "额外防御力"))
    speed = _profile_number(properties, "speed", default=base_speed + _profile_number(properties, "额外速度"))
    cpct_base = _profile_number(properties, "cpctBase", default=_finite_number(properties.get("基础暴击率")) * 100)
    cdmg_base = _profile_number(properties, "cdmgBase", default=_finite_number(properties.get("基础暴击伤害")) * 100)
    cpct = _profile_number(properties, "cpct", default=cpct_base + _finite_number(properties.get("暴击率")) * 100)
    cdmg = _profile_number(properties, "cdmg", default=cdmg_base + _finite_number(properties.get("暴击伤害")) * 100)
    damage = _profile_number(properties, "dmg", default=_finite_number(properties.get("伤害加成")) * 100)
    stance = _profile_number(properties, "stance", default=_finite_number(properties.get("击破特攻")) * 100)
    effect_hit = _profile_number(properties, "effPct", default=_finite_number(properties.get("效果命中")) * 100)
    effect_res = _profile_number(properties, "effDef", default=_finite_number(properties.get("效果抵抗")) * 100)
    recharge = _profile_number(properties, "recharge", default=_finite_number(properties.get("能量恢复效率")) * 100)
    heal = _profile_number(properties, "heal", default=_finite_number(properties.get("治疗加成")) * 100)
    joy = _profile_number(properties, "joy", default=_finite_number(properties.get("欢愉度")) * 100)
    attr = DamageAttributes(
        base_hp=base_hp,
        base_atk=base_atk,
        base_defense=base_defense,
        hp=hp,
        atk=atk,
        defense=defense,
        mastery=0,
        recharge=recharge,
        cpct=cpct,
        cdmg=cdmg,
        dmg=damage,
        phy=_profile_number(properties, "phy"),
        heal=heal,
        speed=speed,
        base_speed=base_speed,
        stance=stance,
        eff_pct=effect_hit,
        eff_def=effect_res,
        joy=joy,
        static_dmg=damage,
        static_speed=speed,
        static_stance=stance,
        static_cpct=cpct_base,
        static_cdmg=cdmg_base,
        static_heal=heal,
        static_eff_pct=effect_hit,
        static_eff_def=effect_res,
        static_joy=joy,
    )
    attr.static_phy = attr.phy
    attr.static_coloring_dmg = attr.coloring_dmg
    # Miao exposes these fields on the AttrItem object but they are not part
    # of the compact dataclass because their names are revision-specific.
    attr.sp = _finite_number(character.get("sp", 0))
    attr.kx = 0.0
    attr.fykx = 0.0
    attr.fyplus = 0.0
    attr.fypct = 0.0
    attr.fybase = 0.0
    attr.fyinc = 0.0
    attr.merrymakes = 0.0
    attr.punchline = 0.0
    attr.static_attr = {
        "atk": base_atk,
        "hp": base_hp,
        "def": base_defense,
        "speed": base_speed,
        "dmg": damage,
    }
    weapon = profile.get("光锥", profile.get("weapon", {}))
    if not isinstance(weapon, dict):
        weapon = {}
    weapon = dict(weapon)
    weapon.setdefault("名称", weapon.get("name", ""))
    weapon.setdefault("类型", weapon.get("type", ""))
    weapon.setdefault("精炼等级", weapon.get("affix", weapon.get("refine", 1)))
    levels = _talent_levels(profile)
    if "xe" in character.get("talent", {}):
        levels["xe"] = levels.get("a", 1)
    for key in list(character.get("talent", {})):
        match = re.match(r"^(a|e|q|t|xe|me|mt)[123]$", str(key))
        if match:
            levels[str(key)] = levels.get(match.group(1), levels.get("a", 1))
    raw_cons = profile.get("命座", profile.get("cons"))
    if isinstance(raw_cons, list):
        cons = len(raw_cons)
    else:
        cons = int(_finite_number(raw_cons, len(profile.get("星魂", [])) if isinstance(profile.get("星魂", []), list) else 0))
    context = DamageContext(
        name=name,
        element=str(character.get("elem", profile.get("元素", profile.get("element", "")))),
        level=max(1, min(80, int(_finite_number(profile.get("等级", profile.get("level", 80)), 80)))),
        cons=cons,
        talent_levels=levels,
        weapon=weapon,
        artifacts=profile.get("遗器", profile.get("relics", [])) if isinstance(profile.get("遗器", profile.get("relics", [])), list) else [],
        attr=attr,
        params={},
        state={
            "trees": _role_trees(profile, character),
            "profile": profile,
            "enemyLevel": int(_finite_number(profile.get("敌人等级", enemy_level), enemy_level)),
            "charId": int(_finite_number(profile.get("角色ID", character.get("id", 0)))),
        },
        talent_data=_talent_data(character, levels),
    )
    for key in ("伤害参数", "计算参数", "params", "参数"):
        value = profile.get(key)
        if isinstance(value, dict):
            context.params.update(value)
    return context


def _apply_data(context: DamageContext, key: str, value: Any) -> None:
    if isinstance(value, _JSUndefined) or value is None:
        return
    number = _finite_number(value)
    attr = context.attr
    match = re.match(
        r"^(a|a2|a3|e|e2|xe|q|q2|q3|t|t2|me|mt|mt2|dot|break|elation)(Def|Ignore|Dmg|Enemydmg|Plus|Pct|Cpct|Cdmg|Multi|Elevated|Merrymakes)$",
        key,
    )
    if match:
        target = attr.talent(match.group(1))
        field_name = {
            "Enemydmg": "enemy_damage",
            "Def": "enemy_def",
            "Ignore": "enemy_ignore",
            "Cpct": "cpct",
            "Cdmg": "cdmg",
            "Multi": "multi",
            "Elevated": "elevated",
            "Merrymakes": "merrymakes",
        }.get(match.group(2), match.group(2).lower())
        setattr(target, field_name, getattr(target, field_name, 0) + number)
        return
    match = re.match(
        r"^(mastery|cpct|cdmg|heal|recharge|dmg|enemydmg|phy|coloringDmg|shield|speed|stance|joy|effPct|effDef)(Plus|Pct|Inc)?$",
        key,
    )
    if match:
        target_name, suffix = match.groups()
        field_name = {
            "enemydmg": "enemy_damage",
            "coloringDmg": "coloring_dmg",
            "effPct": "eff_pct",
            "effDef": "eff_def",
        }.get(target_name, target_name)
        if target_name in {"speed", "stance", "cpct", "cdmg", "dmg", "heal", "recharge", "mastery", "phy", "coloringDmg", "joy", "effPct", "effDef", "enemydmg", "shield"}:
            if suffix == "Pct" and target_name == "speed":
                attr.speed_pct += number
                attr.speed += attr.base_speed * number / 100
            elif suffix == "Pct":
                pct_name = {
                    "coloringDmg": "coloring_dmg",
                    "effPct": "eff_pct",
                    "effDef": "eff_def",
                    "enemydmg": "enemy_damage",
                }.get(target_name, target_name)
                setattr(
                    attr,
                    f"{pct_name}_pct",
                    getattr(attr, f"{pct_name}_pct", 0) + number,
                )
            elif suffix == "Inc":
                setattr(attr, f"{field_name}_inc", getattr(attr, f"{field_name}_inc", 0) + number)
            else:
                setattr(attr, field_name, getattr(attr, field_name, 0) + number)
        return
    match = re.match(r"^(hp|def|atk)(Base|Plus|Pct|Inc)?$", key)
    if match:
        target_name, suffix = match.groups()
        if target_name == "def":
            target_name = "defense"
        if suffix == "Pct":
            getattr(attr, f"add_{target_name}_pct")(number)
        elif suffix == "Base":
            setattr(attr, f"base_{target_name}", getattr(attr, f"base_{target_name}", 0) + number)
        elif suffix == "Inc":
            setattr(attr, f"{target_name}_inc", getattr(attr, f"{target_name}_inc", 0) + number)
        else:
            setattr(attr, target_name, getattr(attr, target_name) + number)
        return
    if key == "enemyDef":
        attr.enemy_def += number
    elif key in {"ignore", "enemyIgnore"}:
        attr.enemy_ignore += number
    elif key in {"kx", "fykx", "multi", "fyplus", "fypct", "fybase", "fyinc", "merrymakes", "punchline"}:
        field_name = "resistance_pen" if key == "kx" else key
        setattr(attr, field_name, getattr(attr, field_name, 0) + number)
    elif key == "superBreakIgnore":
        attr.super_break_ignore += number


def _resolve_callback(value: Any, context: DamageContext, methods: Any = None) -> Any:
    if isinstance(value, dict) and "__function__" in value:
        value = compile_js_function(str(value["__function__"]))
    if callable(value):
        return value(context, methods)
    return value


def _resolve_snapshot_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_resolve_snapshot_value(item) for item in value]
    if isinstance(value, dict):
        if value.get("__undefined__"):
            return _JS_UNDEFINED
        if "__function__" in value:
            return compile_js_function(str(value["__function__"]))
        return {key: _resolve_snapshot_value(item) for key, item in value.items()}
    return value


@lru_cache(maxsize=1)
def load_rule_snapshot() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "res" / "miao_rules" / "rules.json"
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict) or not isinstance(value.get("characters"), dict):
        raise ValueError("invalid Star Rail Miao rule snapshot")
    tables_path = path.with_name("weapon_tables.json")
    with tables_path.open(encoding="utf-8") as stream:
        weapon_tables = json.load(stream)
    if (
        not isinstance(weapon_tables, dict)
        or weapon_tables.get("revision") != value.get("revision")
        or not isinstance(weapon_tables.get("weapons"), dict)
    ):
        raise ValueError("invalid Star Rail Miao weapon table snapshot")
    value["weaponTables"] = weapon_tables["weapons"]
    calc_tables_path = path.with_name("calc_tables.json")
    with calc_tables_path.open(encoding="utf-8") as stream:
        calc_tables = json.load(stream)
    if (
        not isinstance(calc_tables, dict)
        or calc_tables.get("revision") != value.get("revision")
        or not isinstance(calc_tables.get("elationBase"), dict)
    ):
        raise ValueError("invalid Star Rail Miao calculator table snapshot")
    value["elationBase"] = calc_tables["elationBase"]
    return value


def _format_rule_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    number = _finite_number(value, math.nan)
    if math.isfinite(number):
        return str(math.floor(number))
    return _js_to_string(value)


def _append_rule_buffs(context: DamageContext, buffs: list[Any]) -> list[str]:
    messages: list[str] = []
    for raw in buffs:
        buff = _resolve_snapshot_value(raw)
        if not isinstance(buff, dict) or buff.get("isStatic"):
            continue
        check = buff.get("check")
        if check is not None and not bool(_resolve_callback(check, context)):
            continue
        if buff.get("cons") is not None and context.cons < _finite_number(buff.get("cons")):
            continue
        if buff.get("maxCons") is not None and context.cons > _finite_number(buff.get("maxCons")):
            continue
        tree = buff.get("tree")
        if tree is not None:
            trees = context.state.get("trees", {})
            if not trees.get(str(tree), False) and not trees.get(f"10{tree}", False):
                continue
        title = _resolve_callback(buff.get("title", ""), context)
        title = _js_to_string(title) if not isinstance(title, str) else title
        data = buff.get("data", {})
        if isinstance(data, dict):
            resolved_data: list[tuple[str, Any]] = []
            for key, raw_value in data.items():
                value = _resolve_callback(raw_value, context)
                if isinstance(value, _JSUndefined) or value is None:
                    continue
                resolved_data.append((str(key), value))
            for key, value in resolved_data:
                title = title.replace(f"[{key}]", _format_comma(value, 1))
                _apply_data(context, key, value)
        if title:
            messages.append(title)
    context.notes.extend(item for item in messages if item not in context.notes)
    return messages


def calculate_rule_snapshot(name: str, profile: dict[str, Any], enemy_level: int = 103) -> dict[str, Any]:
    snapshot = load_rule_snapshot()
    character_entry = snapshot.get("characters", {}).get(name)
    if not isinstance(character_entry, dict):
        return {"ok": False, "status": "no_rule", "name": name, "revision": snapshot.get("revision", "")}
    character = character_entry.get("data")
    module = _resolve_snapshot_value(character_entry.get("module", {}))
    if not isinstance(character, dict) or not isinstance(module, dict):
        return {"ok": False, "status": "corrupt_rule", "name": name, "revision": snapshot.get("revision", "")}
    context = _build_context(name, profile, character, enemy_level)
    context.state["elationBase"] = snapshot.get("elationBase", {})
    weapon_name = str(context.weapon.get("名称", ""))
    weapon = snapshot.get("weapons", {}).get(weapon_name)
    all_buffs = list(module.get("buffs", [])) if isinstance(module.get("buffs"), list) else []
    if isinstance(weapon, dict):
        refine = max(1, min(5, int(_finite_number(context.weapon.get("精炼等级"), 1))))
        raw_tables = snapshot.get("weaponTables", {}).get(weapon_name, {})
        if isinstance(raw_tables, dict):
            context.state["tables"] = {
                str(key): values[refine - 1]
                for key, values in raw_tables.items()
                if isinstance(values, list) and len(values) >= refine
            }
        all_buffs.extend(weapon.get("buffs", {}).get(str(refine), []))
    sets = _role_sets(profile)
    artifact_ids = snapshot.get("artifactIds", {})
    artifacts = snapshot.get("artifacts", {})
    for raw_id, count in sets.items():
        artifact_name = artifact_ids.get(str(raw_id), raw_id)
        artifact = artifacts.get(artifact_name, {})
        for amount in (2, 4) if count >= 4 else (2,) if count >= 2 else ():
            all_buffs.extend(artifact.get(str(amount), []))
    all_buffs = sorted(
        all_buffs,
        key=lambda item: _finite_number(item.get("sort"), 1) if isinstance(item, dict) else 1,
    )
    default_params = module.get("defParams", {})
    if callable(default_params):
        default_params = _resolve_callback(default_params, context)
    if not isinstance(default_params, dict):
        default_params = {}
    result: dict[str, list[str]] = {}
    messages: list[list[str]] = []
    details = module.get("details", [])
    if not isinstance(details, list):
        details = []
    for raw_detail in details:
        detail = _resolve_snapshot_value(raw_detail)
        if callable(detail):
            detail = _resolve_callback(detail, context)
        if not isinstance(detail, dict) or detail.get("isStatic"):
            continue
        if detail.get("cons") is not None and context.cons < _finite_number(detail.get("cons")):
            continue
        params = dict(default_params)
        detail_params = detail.get("params", {})
        if callable(detail_params):
            detail_params = _resolve_callback(detail_params, context)
        if isinstance(detail_params, dict):
            params.update(detail_params)
        detail_context = context.clone(params)
        calculated_messages = _append_rule_buffs(detail_context, all_buffs)
        check = detail.get("check")
        if check is not None and not bool(_resolve_callback(check, detail_context)):
            continue
        damage_callback = detail.get("dmg")
        if damage_callback is None:
            continue
        methods = DamageMethods(detail_context, _MiaoCalculator(detail_context))
        raw_result = _resolve_callback(damage_callback, detail_context, methods)
        if not isinstance(raw_result, (dict, DamageResult)):
            continue
        avg = raw_result.get("avg") if isinstance(raw_result, dict) else raw_result.avg
        direct = raw_result.get("dmg") if isinstance(raw_result, dict) else raw_result.dmg if raw_result.crit is not None else None
        if avg is None and direct is None:
            continue
        is_text = (
            isinstance(raw_result, dict) and raw_result.get("type") == "text"
        ) or (isinstance(raw_result, DamageResult) and raw_result.text is not None)
        value = _format_rule_value(avg if avg is not None else direct)
        values = DamageValues([value], is_text=True) if is_text else [value]
        if direct is not None:
            values.append(_format_rule_value(direct))
        title = _resolve_callback(detail.get("title", ""), detail_context)
        title = _js_to_string(title) if not isinstance(title, str) else title
        if not title:
            title = f"伤害{len(result) + 1}"
        result[title] = values
        messages.append(calculated_messages)
    if not result:
        return {
            "ok": False,
            "status": "calc_failed",
            "name": name,
            "revision": snapshot.get("revision", ""),
            "error": "无可输出伤害项目",
        }
    def_idx = module.get("defDmgIdx", -1)
    def_idx = int(_finite_number(def_idx, -1))
    selected = messages[def_idx] if 0 <= def_idx < len(messages) else messages[0] if messages else []
    return {
        "ok": True,
        "status": "success",
        "name": name,
        "revision": snapshot.get("revision", ""),
        "damage": result,
        "buffs": selected,
        "detailCount": len(result),
        "defDmgIdx": def_idx,
        "source": f"snapshot:character/{name}/calc.js",
    }


def invoke_rule(function: Callable[..., Any], context: DamageContext, methods=None):
    return function(context, methods)


def resolve_value(value: Any) -> Any:
    if isinstance(value, list):
        return [resolve_value(item) for item in value]
    if isinstance(value, dict):
        if "__expression__" in value:
            expression = _translate_expression(value["__expression__"])
            return eval(
                expression,
                {
                    "math": math,
                    "min": min,
                    "max": max,
                    "pow": pow,
                    "round": round,
                },
            )
        if "__function__" in value:
            return compile_js_function(value["__function__"])
        return {key: resolve_value(item) for key, item in value.items()}
    return value


def invoke_compiled(function: Callable[..., Any], context: DamageContext, methods=None):
    return function(context, methods)
