"""Star Rail damage calculations backed by the Miao-Plugin SR rules.

The panel cache predates Miao's ``ProfileDmg`` model and stores a flattened
Chinese representation of a profile.  The pinned rule snapshot and its
Python runtime live inside this plugin, so production calculation does not
need the Miao application, Node, or a mutable external checkout.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
import re
from functools import lru_cache
from typing import Any, Iterable, Mapping

from .sr_miao_runtime import calculate_rule_snapshot, load_rule_snapshot


MIAO_REVISION = "afff386eb6b31bc70a98144c3bbfa884eaf5e621"

# Values copied from models/dmg/DmgCalcMeta.js at MIAO_REVISION.  Keeping the
# table here makes the runtime independent of node_modules while preserving
# the same level break bases used by DmgCalc.
BREAK_BASE = {
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

# DmgCalcMeta has no entries above level 80 for break damage.  Clamping is
# what the game profile calculator does for playable characters.
BREAK_COEFFICIENT = {
    "物理": 2.0,
    "火": 2.0,
    "冰": 1.0,
    "雷": 1.0,
    "风": 1.5,
    "量子": 0.5,
    "虚数": 0.5,
}
DOT_COEFFICIENT = {
    "雷": 2.0,
    "火": 1.0,
    "风": 1.0,
    "物理": 1.0,
}

_ELEMENT_TO_DAMAGE = {
    "Physical": "物理",
    "Fire": "火",
    "Ice": "冰",
    "Lightning": "雷",
    "Wind": "风",
    "Quantum": "量子",
    "Imaginary": "虚数",
    "物理": "物理",
    "火": "火",
    "冰": "冰",
    "雷": "雷",
    "风": "风",
    "量子": "量子",
    "虚数": "虚数",
}

_ALIASES = {
    "阮梅": "阮•梅",
    "阮·梅": "阮•梅",
    "阮•梅": "阮•梅",
    "丹恒饮月": "丹恒•饮月",
    "丹恒·饮月": "丹恒•饮月",
    "丹恒•饮月": "丹恒•饮月",
    "丹恒腾荒": "丹恒•腾荒",
    "丹恒·腾荒": "丹恒•腾荒",
    "丹恒•腾荒": "丹恒•腾荒",
    "三月七存护": "三月七",
    "三月七•存护": "三月七",
    "三月七·存护": "三月七",
    "三月七巡猎": "三月七·巡猎",
    "三月七•巡猎": "三月七·巡猎",
    "三月七·巡猎": "三月七·巡猎",
    "开拓者": "物主",
    "开拓者物理": "物主",
    "物理主": "物主",
    "物主": "物主",
    "火主": "火主",
    "开拓者火": "火主",
    "冰主": "冰主",
    "开拓者冰": "冰主",
    "雷主": "雷主",
    "开拓者雷": "雷主",
    "虚数主": "虚数主",
    "开拓者虚数": "虚数主",
    "记忆主": "记忆主",
    "开拓者记忆": "记忆主",
}

_MIAO_ALIASES = {
    "物主": ("穹·毁灭", "星·毁灭", "穹·同谐", "星·同谐"),
    "火主": ("穹·存护", "星·存护"),
    "冰主": ("穹·记忆", "星·记忆"),
    "雷主": ("穹·欢愉", "星·欢愉"),
    "虚数主": ("穹·虚无", "星·虚无"),
    "记忆主": ("穹·记忆", "星·记忆"),
}


def _finite(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _ratio(value: object, default: float = 0.0) -> float:
    """Read either the cache's ratio form or Miao's percent form."""
    number = _finite(value, default)
    if abs(number) > 3:
        return number / 100
    return number


def _level(value: object, default: int = 80) -> int:
    number = int(_finite(value, default))
    return max(1, min(80, number))


def _canonical_name(name: object, role: Mapping[str, object] | None = None) -> str:
    raw = str(name or "").strip()
    compact = re.sub(r"[\s·•.。]", "", raw)
    if raw in _ALIASES:
        return _ALIASES[raw]
    if compact in _ALIASES:
        return _ALIASES[compact]
    role_id = str((role or {}).get("角色ID", ""))
    if raw in {"{NICKNAME}", "{开拓者}", "开拓者"}:
        if role_id.startswith("8003") or role_id.startswith("8004"):
            return "火主"
        if role_id.startswith("8007") or role_id.startswith("8008"):
            return "冰主"
        if role_id.startswith("8009"):
            return "雷主"
        if role_id.startswith("8005") or role_id.startswith("8006"):
            return "虚数主"
        return "物主"
    if role_id.startswith("1224") or "巡猎" in raw:
        if compact.startswith("三月七"):
            return "三月七·巡猎"
    if compact.startswith("三月七"):
        return "三月七"
    return raw


def normalize_role_name(name: object, role: Mapping[str, object] | None = None) -> str:
    """Public alias normalizer used by the cache audit and ranking adapter."""
    return _canonical_name(name, role)


@lru_cache(maxsize=256)
def rule_metadata(name: str) -> dict[str, Any] | None:
    """Return auditable metadata from the packaged rule snapshot."""
    try:
        snapshot = load_rule_snapshot()
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    entry = snapshot.get("characters", {}).get(name)
    if not isinstance(entry, Mapping):
        return None
    module = entry.get("module")
    if not isinstance(module, Mapping):
        return None
    def_idx = module.get("defDmgIdx")
    try:
        def_idx = int(def_idx)
    except (TypeError, ValueError):
        def_idx = -1
    details = []
    for detail in module.get("details", ()) if isinstance(module.get("details"), list) else ():
        if isinstance(detail, Mapping) and isinstance(detail.get("title"), str):
            details.append(detail["title"])
    buffs = []
    for buff in module.get("buffs", ()) if isinstance(module.get("buffs"), list) else ():
        if isinstance(buff, Mapping) and isinstance(buff.get("title"), str):
            buffs.append(buff["title"])
    return {
        "source": f"snapshot:character/{name}/calc.js",
        "revision": snapshot.get("revision", MIAO_REVISION),
        "details": details,
        "buffs": buffs,
        "defDmgIdx": def_idx,
        "defDmgKey": module.get("defDmgKey", ""),
        "mainAttr": module.get("mainAttr", "atk,cpct,cdmg"),
    }


@dataclass
class SRAttrs:
    level: int
    enemy_level: int = 103
    atk: float = 0.0
    hp: float = 0.0
    defense: float = 0.0
    speed: float = 0.0
    crit_rate: float = 0.0
    crit_dmg: float = 0.0
    damage_bonus: float = 0.0
    break_effect: float = 0.0
    effect_hit: float = 0.0
    effect_res: float = 0.0
    energy: float = 0.0
    resistance_pen: float = 0.0
    enemy_damage: float = 0.0
    def_down: float = 0.0
    def_ignore: float = 0.0
    skill_damage: dict[str, float] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def skill_bonus(self, skill: str) -> float:
        return self.skill_damage.get(skill, 0.0) + self.skill_damage.get("all", 0.0)


def _property(props: Mapping[str, object], base: str) -> float:
    extra_name = f"额外{base[2:]}" if base.startswith("基础") else f"额外{base}"
    return _finite(props.get(base), 0.0) + _finite(props.get(extra_name), 0.0)


def _build_attrs(role: Mapping[str, object], *, enemy_level: int = 103) -> SRAttrs:
    props = role.get("属性")
    if not isinstance(props, Mapping):
        raise ValueError("缺少属性")
    level = _level(role.get("等级"))
    attrs = SRAttrs(
        level=level,
        enemy_level=max(1, int(_finite(role.get("敌人等级"), enemy_level))),
        atk=_property(props, "基础攻击力"),
        hp=_property(props, "基础生命值"),
        defense=_property(props, "基础防御力"),
        speed=_property(props, "基础速度"),
        crit_rate=_ratio(props.get("基础暴击率")) + _ratio(props.get("暴击率")),
        crit_dmg=_ratio(props.get("基础暴击伤害")) + _ratio(props.get("暴击伤害")),
        damage_bonus=_ratio(props.get("伤害加成")),
        break_effect=_ratio(props.get("击破特攻")),
        effect_hit=_ratio(props.get("效果命中")),
        effect_res=_ratio(props.get("效果抵抗")),
        energy=_ratio(props.get("能量恢复效率")),
    )
    attrs.crit_rate = max(0.0, min(1.0, attrs.crit_rate))
    attrs.crit_dmg = max(0.0, attrs.crit_dmg)
    attrs.params = _context_params(role)
    return attrs


def _context_params(role: Mapping[str, object]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for key in ("伤害参数", "计算参数", "params", "参数"):
        value = role.get(key)
        if isinstance(value, Mapping):
            params.update(value)
    # These fields are optional extensions used by the audit fixtures.  The
    # production cache does not contain them, so absence remains explicit.
    nodes = []
    for key in ("行迹节点", "行迹树", "traces", "trees"):
        value = role.get(key)
        if isinstance(value, Mapping):
            nodes.extend(str(k) for k, enabled in value.items() if enabled)
        elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            nodes.extend(str(item) for item in value)
    params["trees"] = set(nodes)
    return params


def _has_tree(attrs: SRAttrs, tree: str) -> bool:
    return tree in attrs.params.get("trees", set()) or f"10{tree}" in attrs.params.get("trees", set())


def defense_multiplier(
    level: int = 80,
    enemy_level: int = 103,
    def_down: float = 0.0,
    def_ignore: float = 0.0,
) -> float:
    """Miao SR defense zone: (200 + 10L) / (... + ...)."""
    level = max(1, int(level))
    enemy_level = max(1, int(enemy_level))
    down = max(0.0, min(1.0, _ratio(def_down) + _ratio(def_ignore)))
    player = 200 + level * 10
    enemy = 200 + enemy_level * 10
    return player / (player + enemy * (1 - down))


def resistance_multiplier(resistance: float = 0.1, penetration: float = 0.0) -> float:
    """SR resistance zone, including the half-value negative resistance rule."""
    effective = _ratio(resistance) - _ratio(penetration)
    if effective >= 0:
        return max(0.0, 1 - effective)
    return 1 - effective / 2


def _fmt(value: float) -> str:
    if not math.isfinite(value):
        raise ValueError("伤害结果不是有限数")
    return str(max(0, int(value)))


def _damage_pair(
    base: float,
    attrs: SRAttrs,
    *,
    skill: str = "all",
    bonus: float = 0.0,
    enemy_damage: float = 0.0,
    resistance: float = 0.0,
    penetration: float = 0.0,
    def_down: float = 0.0,
    def_ignore: float = 0.0,
    reduction: float = 0.9,
    allow_crit: bool = True,
) -> tuple[str, ...]:
    if base < 0:
        base = 0
    skill_bonus = attrs.skill_bonus(skill)
    dmg_zone = 1 + attrs.damage_bonus + bonus + skill_bonus
    enemy_zone = 1 + attrs.enemy_damage + enemy_damage
    defense = defense_multiplier(attrs.level, attrs.enemy_level, def_down, def_ignore)
    resistance_zone = resistance_multiplier(resistance, attrs.resistance_pen + penetration)
    common = base * dmg_zone * enemy_zone * defense * resistance_zone * reduction
    if not allow_crit:
        return (_fmt(common),)
    rate = max(0.0, min(1.0, attrs.crit_rate))
    crit_dmg = attrs.crit_dmg if rate > 0 else 0.0
    average = common * (1 + rate * crit_dmg)
    critical = common * (1 + crit_dmg)
    return (_fmt(average), _fmt(critical))


def calculate_damage(
    amount: float,
    *,
    attrs: SRAttrs,
    skill: str = "all",
    **kwargs: object,
) -> tuple[str, ...]:
    """Calculate ordinary SR damage from a pre-multiplied skill amount."""
    return _damage_pair(amount, attrs, skill=skill, **kwargs)


def calculate_break_damage(
    *,
    attrs: SRAttrs,
    element: str,
    kind: str = "break",
    toughness: float = 1.0,
    layers: float = 1.0,
    resistance: float = 0.0,
    penetration: float = 0.0,
    def_down: float = 0.0,
    def_ignore: float = 0.0,
    enemy_damage: float = 0.0,
    reduction: float = 0.9,
) -> tuple[str, ...]:
    """Calculate break, break-DOT, entanglement, or super-break damage."""
    level = max(1, min(80, attrs.level))
    element = _ELEMENT_TO_DAMAGE.get(element, element)
    if kind in {"dot", "break_dot"}:
        coefficient = DOT_COEFFICIENT.get(element, 1.0)
    elif kind in {"superBreak", "super_break"}:
        coefficient = 1.0
    elif kind in {"entanglement", "纠缠"}:
        coefficient = 0.6
    else:
        coefficient = BREAK_COEFFICIENT.get(element, 1.0)
    base = BREAK_BASE[level] * coefficient * max(0.0, toughness) * max(0.0, layers)
    if kind in {"superBreak", "super_break"}:
        # DmgCalc's break() path uses stance as the break-effect multiplier.
        break_zone = 1 + attrs.break_effect
    else:
        break_zone = 1 + attrs.break_effect
    result = _damage_pair(
        base * break_zone,
        attrs,
        skill="break" if kind != "dot" else "dot",
        enemy_damage=enemy_damage,
        resistance=resistance,
        penetration=penetration,
        def_down=def_down,
        def_ignore=def_ignore,
        reduction=reduction,
        allow_crit=False,
    )
    return result


# Names retained for callers/tests that used the old helper vocabulary.
def defense_coefficient(level: int = 80, enemy_level: int = 103, reduction_rate: float = 0, ignore: float = 0) -> float:
    return defense_multiplier(level, enemy_level, reduction_rate, ignore)


def resistance_coefficient(base_resistance: float = 0.1, penetration: float = 0) -> float:
    return resistance_multiplier(base_resistance, penetration)



def _role_properties(role: Mapping[str, object]) -> Mapping[str, object] | None:
    properties = role.get("属性")
    if properties is None:
        properties = role.get("attr")
    return properties if isinstance(properties, Mapping) else None


def _runner_failure_status(status: object) -> str:
    if status == "no_rule":
        return "no_rule"
    if status == "corrupt_cache":
        return "corrupt_cache"
    return "rule_failed"


def get_role_dmg_status(data: Mapping[str, object]) -> dict[str, Any]:
    """Run the pinned Miao SR rule and return an auditable result envelope.

    Status values are deliberately machine-readable: ``success``,
    ``rule_failed``, ``no_rule``, ``name_normalization_failed``, and
    ``corrupt_cache``.  The cache and Miao checkout are read-only inputs.
    """
    if not isinstance(data, Mapping):
        return {"status": "corrupt_cache", "error": "角色缓存不是对象"}
    try:
        role = deepcopy(dict(data))
    except (TypeError, ValueError):
        return {"status": "corrupt_cache", "error": "角色缓存无法复制"}

    raw_name = role.get("名称", role.get("name", ""))
    if not isinstance(raw_name, str) or not raw_name.strip():
        return {"status": "name_normalization_failed", "error": "角色名称为空"}
    name = _canonical_name(raw_name, role)
    if not name:
        return {"status": "name_normalization_failed", "error": "角色名称无法规范化"}

    properties = _role_properties(role)
    if properties is None:
        return {"status": "corrupt_cache", "name": name, "error": "缺少属性对象"}
    required = ("基础攻击力", "基础生命值", "基础防御力", "基础速度")
    if not all(key in properties for key in required):
        return {"status": "corrupt_cache", "name": name, "error": "属性字段不完整"}

    try:
        snapshot = load_rule_snapshot()
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return {"status": "rule_failed", "name": name, "revision": MIAO_REVISION, "error": f"规则快照不可用: {exc}"}
    rules = snapshot.get("characters", {})
    rule_name = next(
        (candidate for candidate in (name, *_MIAO_ALIASES.get(name, ())) if candidate in rules),
        None,
    )
    if rule_name is None:
        return {
            "status": "no_rule",
            "name": name,
            "revision": snapshot.get("revision", MIAO_REVISION),
            "error": "快照中不存在角色规则",
        }
    try:
        result = calculate_rule_snapshot(
            rule_name,
            role,
            enemy_level=int(_finite(role.get("敌人等级"), 103)),
        )
    except (
        ArithmeticError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        AttributeError,
        NameError,
    ) as exc:
        return {
            "status": "rule_failed",
            "name": rule_name,
            "revision": snapshot.get("revision", MIAO_REVISION),
            "error": f"Python 规则执行失败: {type(exc).__name__}: {exc}",
        }
    if not isinstance(result, Mapping) or not result.get("ok"):
        return {
            "status": _runner_failure_status(result.get("status") if isinstance(result, Mapping) else None),
            "name": rule_name,
            "revision": result.get("revision", snapshot.get("revision", MIAO_REVISION)) if isinstance(result, Mapping) else snapshot.get("revision", MIAO_REVISION),
            "error": result.get("error", "规则未产生伤害项目") if isinstance(result, Mapping) else "规则返回类型错误",
        }

    raw_damage = result.get("damage")
    if not isinstance(raw_damage, Mapping) or not raw_damage:
        return {"status": "rule_failed", "name": rule_name, "revision": snapshot.get("revision", MIAO_REVISION), "error": "规则伤害结果为空"}
    damage: dict[str, tuple[str, ...]] = {}
    for title, values in raw_damage.items():
        if not isinstance(title, str) or not title.strip() or not isinstance(values, list):
            return {"status": "rule_failed", "name": rule_name, "revision": snapshot.get("revision", MIAO_REVISION), "error": "规则伤害结果结构错误"}
        if not all(isinstance(value, str) and value for value in values):
            return {"status": "rule_failed", "name": rule_name, "revision": snapshot.get("revision", MIAO_REVISION), "error": "规则伤害结果包含非法数值"}
        damage[title] = tuple(values)
    return {
        "status": "success",
        "name": rule_name,
        "revision": result.get("revision", snapshot.get("revision", MIAO_REVISION)),
        "damage": damage,
        "buffs": tuple(value for value in result.get("buffs", []) if isinstance(value, str)),
        "detailCount": result.get("detailCount", len(damage)),
        "source": result.get("source", f"snapshot:character/{rule_name}/calc.js"),
    }


def get_role_dmg(data: Mapping[str, object]) -> dict[str, tuple[str, ...]] | None:
    """Return calculated damage for the panel renderer, or ``None`` on failure."""
    result = get_role_dmg_status(data)
    if result.get("status") != "success":
        return None
    damage = result.get("damage")
    if not isinstance(damage, dict):
        return None
    buffs = result.get("buffs")
    if isinstance(buffs, tuple) and buffs:
        damage = dict(damage)
        damage["额外说明"] = buffs
    return damage


__all__ = [
    "BREAK_BASE",
    "MIAO_REVISION",
    "SRAttrs",
    "calculate_break_damage",
    "calculate_damage",
    "defense_coefficient",
    "defense_multiplier",
    "get_role_dmg",
    "get_role_dmg_status",
    "normalize_role_name",
    "resistance_coefficient",
    "resistance_multiplier",
    "rule_metadata",
]
