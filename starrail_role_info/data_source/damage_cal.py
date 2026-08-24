"""Compatibility exports for the Star Rail damage renderer.

Historically this module contained copied Genshin formulas.  Star Rail uses
its own defense, resistance, break, and independent multiplier semantics;
the implementation now lives in :mod:`sr_damage`.
"""

from .sr_damage import (
    BREAK_BASE,
    MIAO_REVISION,
    SRAttrs,
    calculate_break_damage,
    calculate_damage,
    defense_coefficient,
    defense_multiplier,
    get_role_dmg,
    normalize_role_name,
    resistance_coefficient,
    resistance_multiplier,
    rule_metadata,
)

__all__ = [
    "BREAK_BASE",
    "MIAO_REVISION",
    "SRAttrs",
    "calculate_break_damage",
    "calculate_damage",
    "defense_coefficient",
    "defense_multiplier",
    "get_role_dmg",
    "normalize_role_name",
    "resistance_coefficient",
    "resistance_multiplier",
    "rule_metadata",
]
