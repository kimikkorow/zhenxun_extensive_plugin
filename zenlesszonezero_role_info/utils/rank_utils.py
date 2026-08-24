from __future__ import annotations

from collections.abc import Iterable, Mapping
import json
import math
from pathlib import Path
from typing import Any


RankEntry = dict[str, Any]


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _nonnegative_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        try:
            number_float = float(str(value).strip())
        except (TypeError, ValueError, OverflowError):
            return default
        if not math.isfinite(number_float):
            return default
        number = int(number_float)
    return max(0, number)


def _total_stat(
    properties: Mapping[str, object],
    stat: str,
) -> float | None:
    base = _number(properties.get(f"基础{stat}"))
    if base is None:
        return None
    extra_value = properties.get(f"额外{stat}", 0)
    extra = _number(extra_value)
    if extra is None:
        return None
    return base + extra


def _integer_text(value: float) -> str:
    return f"{int(value):,}"


def _property_rows(properties: Mapping[str, object]) -> list[tuple[str, str]] | None:
    health = _total_stat(properties, "生命值")
    attack = _total_stat(properties, "攻击力")
    crit_rate = _total_stat(properties, "暴击率")
    crit_damage = _total_stat(properties, "暴击伤害")
    anomaly_mastery = _total_stat(properties, "异常精通")
    if any(
        value is None
        for value in (health, attack, crit_rate, crit_damage, anomaly_mastery)
    ):
        return None
    return [
        ("生命值", _integer_text(health)),
        ("攻击力", _integer_text(attack)),
        ("暴击率", f"{crit_rate / 100:.1f}%"),
        ("暴击伤害", f"{crit_damage / 100:.1f}%"),
        ("异常精通", _integer_text(anomaly_mastery)),
    ]


def build_rank_entry(
    qq: int,
    nickname: str,
    role_data: Mapping[str, object],
    metric: str = "评分",
) -> RankEntry | None:
    if metric != "评分":
        return None
    properties = role_data.get("属性")
    if not isinstance(properties, Mapping):
        return None

    score = _number(role_data.get("评分"))
    if score is None:
        return None
    rows = _property_rows(properties)
    if rows is None:
        return None

    constellation = _nonnegative_int(role_data.get("影画"))
    weapon_value = role_data.get("武器")
    weapon: dict[str, Any] = {}
    if isinstance(weapon_value, Mapping):
        weapon = {
            "星级": _nonnegative_int(weapon_value.get("星级")),
            "图标": str(weapon_value.get("图标", "") or ""),
        }

    element = role_data.get("元素", "")
    return {
        "qq": qq,
        "nickname": nickname,
        "rank": constellation,
        "影画": constellation,
        "value": score,
        "rows": rows,
        "weapon": weapon,
        "element": str(element or ""),
    }


def _member_qq(member: Mapping[str, object]) -> int | None:
    value = member.get("user_id")
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _nickname(member: Mapping[str, object], qq: int) -> str:
    card = member.get("card")
    if card:
        return str(card)
    nickname = member.get("nickname")
    if nickname:
        return str(nickname)
    return str(qq)


def collect_role_rank_entries(
    members: Iterable[Mapping[str, object]],
    uid_map: Mapping[str, object],
    player_info_dir: str | Path,
    role_name: str,
    metric: str = "评分",
    limit: int = 16,
) -> list[RankEntry]:
    entries: list[RankEntry] = []
    if metric != "评分":
        return entries
    player_info_dir = Path(player_info_dir)
    try:
        requested_limit = max(0, int(limit))
    except (TypeError, ValueError, OverflowError):
        requested_limit = 16
    requested_limit = min(requested_limit, 16)

    if not isinstance(uid_map, Mapping):
        return entries

    for member in members:
        if not isinstance(member, Mapping):
            continue
        qq = _member_qq(member)
        if qq is None:
            continue
        uid = uid_map.get(str(qq))
        if uid is None or uid == "":
            continue
        uid_text = str(uid).strip()
        if not uid_text or Path(uid_text).name != uid_text:
            continue
        try:
            payload = json.loads(
                (player_info_dir / f"{uid_text}.json").read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        roles = payload.get("角色")
        if not isinstance(roles, Mapping):
            continue
        role_data = roles.get(role_name)
        if not isinstance(role_data, Mapping):
            continue
        try:
            entry = build_rank_entry(qq, _nickname(member, qq), role_data, metric)
        except (TypeError, ValueError, OverflowError):
            continue
        if entry is not None:
            entries.append(entry)

    entries.sort(key=lambda item: (-float(item["value"]), int(item["qq"])))
    return entries[:requested_limit]
