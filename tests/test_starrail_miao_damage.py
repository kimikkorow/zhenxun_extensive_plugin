from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import types

import pytest


PLUGIN_PATH = Path(__file__).parents[1] / "starrail_role_info"
MIAO_ROOT = Path("/Users/crazy/PycharmProjects/miao-plugin")
EXPECTED_REVISION = "afff386eb6b31bc70a98144c3bbfa884eaf5e621"
NODE = shutil.which("node")


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def damage_modules():
    for name, path in (
        ("starrail_role_info", PLUGIN_PATH),
        ("starrail_role_info.data_source", PLUGIN_PATH / "data_source"),
    ):
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    runtime = _load_module(
        "starrail_role_info.data_source.sr_miao_runtime",
        PLUGIN_PATH / "data_source" / "sr_miao_runtime.py",
    )
    damage = _load_module(
        "starrail_role_info.data_source.sr_damage",
        PLUGIN_PATH / "data_source" / "sr_damage.py",
    )
    return damage, runtime


def _functions(value):
    if isinstance(value, dict):
        if "__function__" in value:
            yield value["__function__"]
        for child in value.values():
            yield from _functions(child)
    elif isinstance(value, list):
        for child in value:
            yield from _functions(child)


def _representative_profiles() -> dict:
    payload = json.loads(
        (PLUGIN_PATH / "user_data/player_info/100013250.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["角色"]


def _cached_profile(uid: str, name: str) -> dict:
    payload = json.loads(
        (PLUGIN_PATH / f"user_data/player_info/{uid}.json").read_text(
            encoding="utf-8"
        )
    )
    return payload["角色"][name]


def test_snapshot_revision_coverage_and_all_functions_compile(damage_modules) -> None:
    _, runtime = damage_modules
    snapshot = runtime.load_rule_snapshot()
    functions = list(_functions(snapshot))

    assert snapshot["revision"] == EXPECTED_REVISION
    assert len(snapshot["characters"]) == 102
    assert all(entry.get("module") for entry in snapshot["characters"].values())
    assert len(functions) == 993
    for source in functions:
        assert callable(runtime.compile_js_function(source))


def test_sr_formula_boundaries(damage_modules) -> None:
    damage, _ = damage_modules
    defense = damage.defense_multiplier(80, 103)
    assert defense == pytest.approx(1000 / (1000 + 1230))
    assert damage.defense_multiplier(80, 103, 1, 1) == 1
    assert damage.resistance_multiplier(0.1, 0) == pytest.approx(0.9)
    assert damage.resistance_multiplier(0.1, 0.3) == pytest.approx(1.1)

    zero_crit = damage.SRAttrs(level=80, crit_rate=0, crit_dmg=2)
    full_crit = damage.SRAttrs(level=80, crit_rate=1, crit_dmg=2)
    assert damage.calculate_damage(1000, attrs=zero_crit) == ("403", "403")
    assert damage.calculate_damage(1000, attrs=full_crit) == ("1210", "1210")

    breaker = damage.SRAttrs(level=80, break_effect=1.5)
    normal_break = float(
        damage.calculate_break_damage(attrs=breaker, element="火")[0]
    )
    super_break = float(
        damage.calculate_break_damage(
            attrs=breaker,
            element="火",
            kind="superBreak",
            toughness=2,
        )[0]
    )
    assert normal_break > 0
    assert super_break == pytest.approx(normal_break, abs=1)


def test_promotion_restores_main_trace_buffs_and_renderer_notes(damage_modules) -> None:
    damage, runtime = damage_modules
    profile = dict(_representative_profiles()["黄泉"])
    without_traces = dict(profile)
    without_traces["晋升"] = 0
    with_traces = dict(profile)
    with_traces["晋升"] = 6

    no_trace_result = runtime.calculate_rule_snapshot("黄泉", without_traces)
    traced_result = runtime.calculate_rule_snapshot("黄泉", with_traces)
    assert not any("行迹-奈落" in item for item in no_trace_result["buffs"])
    assert any("行迹-奈落" in item for item in traced_result["buffs"])
    assert any("行迹-雷心" in item for item in traced_result["buffs"])

    rendered = damage.get_role_dmg(with_traces)
    assert rendered is not None
    assert rendered["额外说明"] == tuple(traced_result["buffs"])
    assert any("行于流逝的岸" in item for item in rendered["额外说明"])
    assert any("死水深潜的先驱" in item for item in rendered["额外说明"])


def test_cerydra_text_results_and_talent_table_alias(damage_modules) -> None:
    damage, runtime = damage_modules
    profile = _cached_profile("101245175", "刻律德菈")

    result = runtime.calculate_rule_snapshot("刻律德菈", profile)
    assert result["damage"]["【声明】"] == ["本计算中,刻律德菈无【军功】buff"]
    assert getattr(result["damage"]["【声明】"], "is_text", False)
    assert result["damage"]["【军功】角色攻击力提升"] == ["636点"]
    assert getattr(result["damage"]["【军功】角色攻击力提升"], "is_text", False)

    rendered = damage.get_role_dmg(profile)
    assert rendered is not None
    assert getattr(rendered["【声明】"], "is_text", False)
    assert rendered["【军功】角色攻击力提升"] == ["636点"]


def test_saber_talent_table_alias_applies_damage_buff(damage_modules) -> None:
    _, runtime = damage_modules
    profile = _cached_profile("100051625", "Saber")
    character = runtime.load_rule_snapshot()["characters"]["Saber"]["data"]
    context = runtime._build_context("Saber", profile, character)

    assert context.talent("t", "伤害提高") == pytest.approx(0.6)


def test_attr_percentages_are_visible_but_excluded_from_direct_damage(damage_modules) -> None:
    _, runtime = damage_modules
    profile = _cached_profile("100064476", "不死途")
    character = runtime.load_rule_snapshot()["characters"]["不死途"]["data"]
    context = runtime._build_context("不死途", profile, character)
    before = runtime._MiaoCalculator(context).calculate(multiplier=0.5, talents="a")

    runtime._apply_data(context, "cdmgPct", 48)
    cdmg = runtime._AttrView(context).cdmg
    after = runtime._MiaoCalculator(context).calculate(multiplier=0.5, talents="a")

    assert cdmg.base == pytest.approx(context.attr.static_cdmg)
    assert cdmg.plus == pytest.approx(context.attr.cdmg - context.attr.static_cdmg)
    assert cdmg.pct == pytest.approx(48)
    assert float(cdmg) == pytest.approx(
        cdmg.base + cdmg.plus + cdmg.base * cdmg.pct / 100
    )
    assert after.avg == pytest.approx(before.avg)
    assert after.crit == pytest.approx(before.crit)

    base_heal = runtime._MiaoCalculator(context).heal(1000).avg
    base_shield = runtime._MiaoCalculator(context).shield(1000).avg
    runtime._apply_data(context, "healPct", 50)
    runtime._apply_data(context, "shieldPct", 50)
    assert runtime._AttrView(context).heal.pct == pytest.approx(50)
    assert float(runtime._AttrView(context).shield) > context.attr.shield
    assert runtime._MiaoCalculator(context).heal(1000).avg == pytest.approx(base_heal)
    assert runtime._MiaoCalculator(context).shield(1000).avg == pytest.approx(base_shield)


def test_elation_skill_uses_basic_attack_level(damage_modules) -> None:
    _, runtime = damage_modules
    profile = _cached_profile("100030174", "火花")
    character = runtime.load_rule_snapshot()["characters"]["火花"]["data"]
    context = runtime._build_context("火花", profile, character)

    assert context.talent_levels["a"] == 6
    assert context.talent_levels["xe"] == 6


@pytest.mark.skipif(
    NODE is None or not MIAO_ROOT.exists(),
    reason="独立 Miao JavaScript oracle 不可用",
)
@pytest.mark.parametrize("name", ["黄泉", "流萤", "遐蝶"])
def test_python_snapshot_matches_original_javascript(name, damage_modules) -> None:
    _, runtime = damage_modules
    profile = _representative_profiles()[name]
    python_result = runtime.calculate_rule_snapshot(name, profile)
    process = subprocess.run(
        [str(NODE), str(PLUGIN_PATH / "tools/sr_miao_runner.mjs")],
        input=json.dumps({"name": name, "profile": profile}, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env={"MIAO_PLUGIN_ROOT": str(MIAO_ROOT)},
    )
    javascript_result = json.loads(process.stdout)

    assert python_result["damage"] == javascript_result["damage"]
    assert python_result["buffs"] == javascript_result["buffs"]


@pytest.mark.skipif(
    NODE is None or not MIAO_ROOT.exists(),
    reason="独立 Miao JavaScript oracle 不可用",
)
@pytest.mark.parametrize(
    ("uid", "name"),
    [
        ("100030174", "火花"),
        ("100162877", "爻光"),
        ("100317452", "绯英"),
        ("100064476", "不死途"),
        ("100375281", "大黑塔"),
        ("166308298", "绯英"),
    ],
)
def test_cached_damage_matches_original_javascript(
    uid, name, damage_modules
) -> None:
    _, runtime = damage_modules
    profile = _cached_profile(uid, name)
    python_result = runtime.calculate_rule_snapshot(name, profile)
    process = subprocess.run(
        [str(NODE), str(PLUGIN_PATH / "tools/sr_miao_runner.mjs")],
        input=json.dumps({"name": name, "profile": profile}, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
        env={"MIAO_PLUGIN_ROOT": str(MIAO_ROOT)},
    )
    javascript_result = json.loads(process.stdout)

    assert python_result["damage"] == javascript_result["damage"]
    assert python_result["buffs"] == javascript_result["buffs"]
