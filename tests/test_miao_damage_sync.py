from __future__ import annotations

import json
import importlib
import sys
import types
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "genshin_role_info"
sys.path.insert(0, str(PLUGIN_ROOT))

REVISION = "7875d0b22543e6d16deded823ad02a2e21b73973"


def read_json(name: str) -> dict:
    return json.loads(
        (PLUGIN_ROOT / "res" / "json_data" / name).read_text(encoding="utf-8")
    )


def test_miao_source_revision_and_character_rules() -> None:
    rules = read_json("miao_damage_rules.json")
    talents = read_json("miao_damage_talents.json")

    assert rules["source"]["revision"] == REVISION
    assert talents["source"]["revision"] == REVISION
    assert rules["rules"]["赛诺"]["defDmgKey"] == "qStellarConduct"
    assert rules["rules"]["莱欧斯利"]["defDmgIdx"] == 7
    assert len(rules["rules"]["奥黛塔"]["details"]) == 8
    assert len(rules["rules"]["七七"]["details"]) == 4
    assert rules["rules"]["七七"]["details"][2]["title"] == (
        "【辉映·星超导】Q星超导伤害"
    )
    assert rules["rules"]["旅行者/cryo"]["defDmgIdx"] == 2
    assert len(rules["rules"]["旅行者/cryo"]["details"]) == 5
    assert rules["rules"]["阿罗夏"]["details"][0]["title"] == "点按E伤害"
    assert len(rules["rules"]["阿罗夏"]["details"]) == 4
    assert "奥黛塔" in talents["characters"]
    assert "旅行者/cryo" in talents["characters"]


def test_miao_latest_equipment_rules() -> None:
    equipment = read_json("miao_damage_equipment.json")
    expected_weapons = {
        "悬黎千钧",
        "霜雪誓约",
        "群王局戏",
        "寸心余响",
        "金律铸影",
        "救赎之斩",
        "寒息",
        "戍望谣歌",
        "熔猎异端之刃",
        "引火之源",
        "白湖冬羽",
        "星锋剑",
    }

    assert expected_weapons <= equipment["weapons"].keys()
    assert equipment["artifacts"]["炉火融炼之心"]["4"]["data"] == {
        "atkPct": 12,
        "stellarConduct": 50,
    }


def test_miao_rules_compile_and_latest_score_data() -> None:
    from data_source.damage.rules import RULES

    assert {
        "七七",
        "赛诺",
        "莱欧斯利",
        "旅行者/cryo",
        "奥黛塔",
        "阿罗夏",
    } <= RULES.keys()
    assert len(RULES["赛诺"].details) == 10
    assert len(RULES["莱欧斯利"].details) == 8
    assert len(RULES["奥黛塔"].details) == 8
    assert len(RULES["七七"].details) == 4
    assert len(RULES["旅行者/cryo"].details) == 5
    assert len(RULES["阿罗夏"].details) == 4

    score = read_json("score.json")
    assert score["桑多涅"]["mastery"] == 60
    assert score["桑多涅"]["recharge"] == 50
    assert score["桑多涅"]["atk"] == 85

    role_info = read_json("role_info.json")
    assert {"小天鹅", "星星使者", "莱莱可", "跳舞小妹"} <= set(
        role_info["奥黛塔"]["别名"]
    )
    assert "猎人" in role_info["阿罗夏"]["别名"]


def test_sandrone_high_constellation_score_rule() -> None:
    package = types.ModuleType("_test_genshin_role_info")
    package.__path__ = [str(PLUGIN_ROOT)]
    utils_package = types.ModuleType("_test_genshin_role_info.utils")
    utils_package.__path__ = [str(PLUGIN_ROOT / "utils")]
    sys.modules.setdefault("_test_genshin_role_info", package)
    sys.modules.setdefault("_test_genshin_role_info.utils", utils_package)
    get_effective = importlib.import_module(
        "_test_genshin_role_info.utils.artifact_utils"
    ).get_effective

    artifact = {
        "所属套装": "",
        "图标": "",
        "主属性": {"属性名": "生命值", "属性值": 0},
        "词条": [],
        "等级": 0,
    }
    data = {
        "名称": "桑多涅",
        "元素": "冰",
        "圣遗物": [artifact.copy() for _ in range(5)],
        "属性": {
            "暴击率": 0.05,
            "暴击伤害": 0.5,
            "元素精通": 0,
        },
        "武器": {"名称": "", "精炼等级": 1},
        "命座": [],
    }

    low_cons, low_name = get_effective(data)
    data["命座"] = ["一命", "二命"]
    high_cons, high_name = get_effective(data)

    assert low_cons["百分比攻击力"] == 85
    assert low_name == "桑多涅"
    assert high_cons["百分比攻击力"] == 100
    assert high_name == "桑多涅-高命"


def test_alyosha_helper_and_traveler_weapon_functions_evaluate() -> None:
    from data_source.damage.buffs import apply_common_buffs
    from data_source.damage.miao_runtime import compile_js_function
    from data_source.damage.models import DamageAttributes, DamageContext

    rules = read_json("miao_damage_rules.json")
    equipment = read_json("miao_damage_equipment.json")
    context = DamageContext(
        name="空",
        element="冰",
        level=90,
        cons=6,
        talent_levels={"a": 1, "e": 1, "q": 1},
        weapon={"名称": "星锋剑", "精炼等级": 1},
        artifacts=[],
        attr=DamageAttributes(
            base_hp=10000,
            base_atk=300,
            base_defense=700,
            hp=10000,
            atk=1000,
            defense=700,
            mastery=0,
            recharge=100,
            cpct=5,
            cdmg=50,
            dmg=0,
            phy=0,
            heal=0,
        ),
        talent_data={
            "a": {},
            "e": {"猎者之准攻击力提升": [10]},
            "q": {},
        },
    )
    alyosha_source = rules["rules"]["阿罗夏"]["buffs"][0]["data"][
        "atkPct"
    ]["__function__"]
    weapon_source = equipment["weapons"]["星锋剑"]["check"]["__function__"]
    r5_context = context.clone()
    r5_context.weapon = {"名称": "星锋剑", "精炼等级": 5}

    assert compile_js_function(alyosha_source)(context, None) == 20
    assert compile_js_function(weapon_source)(context, None) is True
    apply_common_buffs(context)
    apply_common_buffs(r5_context)
    assert (context.attr.atk_pct, context.attr.cdmg) == (16, 92)
    assert (r5_context.attr.atk_pct, r5_context.attr.cdmg) == (32, 92)
