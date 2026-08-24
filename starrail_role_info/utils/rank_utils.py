from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import json
import math
from pathlib import Path
from typing import Any


RankEntry = dict[str, Any]
DamageCalculator = Callable[[Mapping[str, object]], Mapping[str, tuple[str, ...]] | None]

_PROPERTY_KEYS = (
    "基础生命值",
    "额外生命值",
    "基础攻击力",
    "额外攻击力",
    "基础速度",
    "额外速度",
    "基础暴击率",
    "暴击率",
    "基础暴击伤害",
    "暴击伤害",
)


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").rstrip("%"))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _valid_properties(properties: object) -> tuple[dict[str, float], bool]:
    if not isinstance(properties, Mapping):
        return {}, False
    values: dict[str, float] = {}
    for key in _PROPERTY_KEYS:
        value = _number(properties.get(key))
        if value is None:
            return {}, False
        values[key] = value
    return values, True


def _flat_text(value: float) -> str:
    return f"{int(value):,}"


def _percent_text(value: float) -> str:
    value = math.floor(value * 1000) / 10
    return f"{value:.1f}%"


def select_damage_metric(
    damage: Mapping[str, tuple[str, ...]] | None,
    damage_index: int,
) -> tuple[str, float, float | None] | None:
    """Select a one-based damage row, excluding renderer-only notes."""
    rows = [item for item in (damage or {}).items() if item[0] != "额外说明"]
    if damage_index < 1 or damage_index > len(rows):
        return None
    title, values = rows[damage_index - 1]
    if not values or (expected := _number(values[0])) is None:
        return None
    critical = _number(values[1]) if len(values) > 1 else None
    return title, expected, critical


def build_rank_entry(
    qq: int,
    nickname: str,
    role_data: Mapping[str, object],
    metric: str = "评分",
    damage: Mapping[str, tuple[str, ...]] | None = None,
    damage_index: int | None = None,
) -> RankEntry | None:
    """Convert one cached Star Rail role into the renderer's rank shape."""
    properties, valid = _valid_properties(role_data.get("属性"))
    if not valid:
        return None
    if metric == "评分":
        value = _number(role_data.get("评分"))
        damage_title = None
    elif metric == "伤害" and damage_index is not None:
        selected = select_damage_metric(damage, damage_index)
        if selected is None:
            return None
        damage_title, value, _ = selected
    else:
        return None
    if value is None:
        return None

    rows = [
        (
            "生命值",
            _flat_text(properties["基础生命值"] + properties["额外生命值"]),
        ),
        (
            "攻击力",
            _flat_text(properties["基础攻击力"] + properties["额外攻击力"]),
        ),
        (
            "速度",
            _flat_text(properties["基础速度"] + properties["额外速度"]),
        ),
        (
            "暴击率",
            _percent_text(properties["基础暴击率"] + properties["暴击率"]),
        ),
        (
            "暴击伤害",
            _percent_text(
                properties["基础暴击伤害"] + properties["暴击伤害"]
            ),
        ),
    ]

    constellations = role_data.get("星魂")
    rank = len(constellations) if isinstance(constellations, list) else 0
    light_cone = role_data.get("光锥")
    weapon: dict[str, object] = {}
    if isinstance(light_cone, Mapping):
        weapon = {
            "星级": light_cone.get("星级", 1),
            "图标": (
                light_cone.get("图标", "")
                if isinstance(light_cone.get("图标", ""), str)
                else ""
            ),
        }

    return {
        "qq": qq,
        "nickname": nickname,
        "rank": rank,
        "value": value,
        "rows": rows,
        "weapon": weapon,
        "damage_title": damage_title,
    }


def _member_nickname(member: Mapping[str, object], qq: int) -> str:
    for key in ("card", "nickname"):
        value = member.get(key)
        if value is not None and str(value):
            return str(value)
    return str(qq)


def collect_role_rank_entries(
    members: Iterable[Mapping[str, object]],
    uid_map: Mapping[str, object],
    player_info_dir: str | Path,
    role_name: str,
    metric: str = "评分",
    damage_calculator: DamageCalculator | None = None,
    damage_index: int | None = None,
    limit: int = 16,
) -> list[RankEntry]:
    """Collect, validate, and stably sort one role's group ranking."""
    if (
        metric not in {"评分", "伤害"}
        or (metric == "伤害" and (damage_calculator is None or damage_index is None))
        or not isinstance(uid_map, Mapping)
        or not isinstance(members, Iterable)
    ):
        return []
    try:
        limit = max(0, int(limit))
    except (TypeError, ValueError):
        limit = 16

    entries: list[RankEntry] = []
    player_info_dir = Path(player_info_dir)
    for member in members:
        if not isinstance(member, Mapping):
            continue
        qq_value = member.get("user_id")
        if isinstance(qq_value, bool):
            continue
        try:
            qq = int(str(qq_value))
        except (TypeError, ValueError):
            continue
        uid = uid_map.get(str(qq))
        if uid is None or str(uid).strip() == "":
            continue
        try:
            payload = json.loads(
                (player_info_dir / f"{str(uid).strip()}.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, UnicodeError, TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        roles = payload.get("角色")
        role_data = roles.get(role_name) if isinstance(roles, Mapping) else None
        if not isinstance(role_data, Mapping):
            continue
        try:
            damage = damage_calculator(role_data) if metric == "伤害" and damage_calculator else None
            entry = build_rank_entry(
                qq,
                _member_nickname(member, qq),
                role_data,
                metric,
                damage,
                damage_index,
            )
        except (TypeError, ValueError, OverflowError):
            continue
        if entry is not None:
            entries.append(entry)

    entries.sort(key=lambda item: (-float(item["value"]), int(item["qq"])))
    return entries[:limit]
