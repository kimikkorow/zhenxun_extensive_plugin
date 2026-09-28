from __future__ import annotations

import json
import importlib
import sys
import types
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "genshin_role_info"
sys.path.insert(0, str(PLUGIN_ROOT))

REVISION = "fb22b8491ea7172d404583b1da5b7fca14b3d266"


def read_json(name: str) -> dict:
    return json.loads(
        (PLUGIN_ROOT / "res" / "json_data" / name).read_text(encoding="utf-8")
    )


def load_artifact_utils():
    package = types.ModuleType("_test_genshin_role_info")
    package.__path__ = [str(PLUGIN_ROOT)]
    utils_package = types.ModuleType("_test_genshin_role_info.utils")
    utils_package.__path__ = [str(PLUGIN_ROOT / "utils")]
    sys.modules.setdefault("_test_genshin_role_info", package)
    sys.modules.setdefault("_test_genshin_role_info.utils", utils_package)
    return importlib.import_module("_test_genshin_role_info.utils.artifact_utils")


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
    assert len(rules["rules"]["梦见月瑞希"]["details"]) == 11
    assert rules["rules"]["梦见月瑞希"]["defDmgIdx"] == 2
    assert rules["rules"]["梦见月瑞希"]["details"][2]["title"] == (
        "【辉映·星扩散】E额外持续星扩散伤害"
    )
    assert "奥黛塔" in talents["characters"]
    assert "旅行者/cryo" in talents["characters"]
    assert len(rules["rules"]["沃雅妮莎"]["details"]) == 6
    assert rules["rules"]["沃雅妮莎"]["details"][3]["title"] == (
        "1命提供攻击力提升"
    )
    assert rules["rules"]["沃雅妮莎"]["defDmgIdx"] == 2
    assert len(rules["rules"]["薇斯纳"]["details"]) == 9
    assert next(
        buff for buff in rules["rules"]["薇斯纳"]["buffs"] if buff.get("cons") == 2
    )["data"]["atkPct"] == 40
    assert {"沃雅妮莎", "薇斯纳"} <= talents["characters"].keys()


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
        "漩流颂歌",
        "新枝",
        "银釭",
        "蝶变",
        "柔风游弦",
    }

    assert expected_weapons <= equipment["weapons"].keys()
    assert equipment["artifacts"]["炉火融炼之心"]["4"]["data"] == {
        "atkPct": 12,
        "stellarConduct": 50,
    }
    assert "data" not in equipment["weapons"]["星锋剑"]
    assert equipment["weapons"]["星锋剑"]["refine"]["atkPct"] == [
        16,
        20,
        24,
        28,
        32,
        36,
    ]
    assert equipment["artifacts"]["翠绿之影"]["4"]["data"]["stellarSwirl"] == 20
    assert equipment["artifacts"]["翠绿之影"]["4"]["data"]["stellarVortex"] == 20
    assert equipment["artifacts"]["血红之证"]["4"]["data"] == {
        "cpct": 16,
        "stellarSwirl": 40,
        "stellarVortex": 40,
    }
    assert equipment["weapons"]["寸心余响"][1]["refine"]["stellarSwirl"] == [
        16,
        20,
        24,
        28,
        32,
        36,
    ]
    assert equipment["weapons"]["引火之源"][1]["refine"]["stellarVortex"] == [
        16,
        20,
        24,
        28,
        32,
        36,
    ]
    assert equipment["weapons"]["漩流颂歌"]["refine"]["heal"] == [
        4, 5, 6, 7, 8, 9
    ]
    assert equipment["weapons"]["漩流颂歌"]["refine"]["hpPct"] == [
        21, 26.25, 31.5, 36.75, 42, 47.25
    ]
    assert equipment["weapons"]["柔风游弦"]["refine"]["stellarConduct"] == [
        24, 30, 36, 42, 48, 54
    ]
    assert equipment["weapons"]["新枝"][0]["refine"]["atkPct"] == [
        4, 5, 6, 7, 8, 9
    ]
    assert equipment["weapons"]["新枝"][0]["check"]["__function__"] == (
        "({ element }) => !['冰', '雷', '风'].includes(element)"
    )
    assert equipment["weapons"]["新枝"][1]["refine"]["stellarSwirl"] == [
        8, 10, 12, 14, 16, 18
    ]
    assert equipment["weapons"]["新枝"][1]["refine"]["atkPct"] == [
        6, 7.5, 9, 10.5, 12, 13.5
    ]
    assert equipment["weapons"]["银釭"]["refine"]["mastery"] == [
        104, 130, 156, 182, 208, 234
    ]
    assert equipment["weapons"]["蝶变"]["refine"]["cdmg"] == [
        56, 72, 88, 104, 120, 136
    ]
    assert equipment["weapons"]["蝶变"]["refine"]["stellarVortex"] == [
        36, 45, 54, 63, 72, 81
    ]


def test_miao_rules_compile_and_latest_score_data() -> None:
    from data_source.damage.rules import RULES

    assert {
        "七七",
        "赛诺",
        "莱欧斯利",
        "旅行者/cryo",
        "奥黛塔",
        "阿罗夏",
        "沃雅妮莎",
        "薇斯纳",
    } <= RULES.keys()
    assert len(RULES["赛诺"].details) == 10
    assert len(RULES["莱欧斯利"].details) == 8
    assert len(RULES["奥黛塔"].details) == 8
    assert len(RULES["七七"].details) == 4
    assert len(RULES["旅行者/cryo"].details) == 5
    assert len(RULES["阿罗夏"].details) == 4
    assert len(RULES["梦见月瑞希"].details) == 11
    assert len(RULES["沃雅妮莎"].details) == 6
    assert len(RULES["薇斯纳"].details) == 9

    score = read_json("score.json")
    assert score["桑多涅"]["mastery"] == 60
    assert score["桑多涅"]["recharge"] == 50
    assert score["桑多涅"]["atk"] == 85
    assert score["梦见月瑞希"]["dmg"] == 0
    assert score["梦见月瑞希"]["recharge"] == 75
    assert score["行秋"]["recharge"] == 100
    assert score["神里绫华"]["recharge"] == 55
    assert score["香菱"]["recharge"] == 100
    assert score["芙宁娜"]["recharge"] == 100

    role_info = read_json("role_info.json")
    assert {"小天鹅", "星星使者", "莱莱可", "跳舞小妹"} <= set(
        role_info["奥黛塔"]["别名"]
    )
    assert "猎人" in role_info["阿罗夏"]["别名"]


def test_latest_reaction_coefficients_and_custom_params() -> None:
    from data_source.damage.reactions import reaction_config

    assert reaction_config("lunarBloom", "草") == ("lunar", 1.0)
    assert reaction_config("lunarCharged", "雷") == ("lunar", 7.2)
    assert reaction_config("lunarCharged", "雷", "") == ("lunar", 3.0)
    assert reaction_config("stellarConduct", "冰", "") == ("stellar", 2.0)
    assert reaction_config(
        "stellarConduct",
        "冰",
        "",
        {"stellarConductCount": 1},
    ) == ("stellar", 1.45)
    assert reaction_config("stellarSwirl", "风") == ("stellar", 3.0)
    assert reaction_config("stellarSwirl", "风", "") == ("stellar", 1.0)
    assert reaction_config("stellarSwirl", "冰") == ("stellar", 3.0)
    assert reaction_config("stellarVortex", "冰") == ("stellar", 12.0)
    assert reaction_config(
        "stellarVortex", "冰", "fy", {"stellarVortexCount": 2}
    ) == ("stellar", 8.0)


def test_mizuki_latest_damage_rules_execute() -> None:
    from data_source.damage.engine import get_role_dmg

    data = {
        "名称": "梦见月瑞希",
        "元素": "风",
        "等级": 90,
        "命座": [],
        "天赋": [{"等级": 10}, {"等级": 10}, {"等级": 10}],
        "武器": {"名称": "", "精炼等级": 1, "类型": "法器"},
        "圣遗物": [],
        "属性": {
            "基础生命": 10000,
            "额外生命": 0,
            "基础攻击": 300,
            "额外攻击": 700,
            "基础防御": 600,
            "额外防御": 0,
            "伤害加成": [0] * 8,
            "元素精通": 800,
            "元素充能效率": 1.2,
            "暴击率": 0.5,
            "暴击伤害": 1.0,
            "治疗加成": 0,
        },
    }

    result = get_role_dmg(data)

    assert result is not None
    assert {
        "天赋「廓然梦生」E持续攻击伤害",
        "【辉映·星扩散】E额外持续星扩散伤害",
        "反应星扩散单层伤害",
    } <= result.keys()

    data["命座"] = ["一命", "二命"]
    result = get_role_dmg(data)
    assert result is not None
    assert any(
        note.startswith("2命效果：处于梦浮状态下时")
        for note in result.get("额外说明", ())
    )


def test_sandrone_high_constellation_score_rule() -> None:
    get_effective = load_artifact_utils().get_effective

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


def test_mizuki_latest_dynamic_score_rule() -> None:
    get_effective = load_artifact_utils().get_effective
    artifact = {
        "所属套装": "",
        "图标": "",
        "主属性": {"属性名": "生命值", "属性值": 0},
        "词条": [],
        "等级": 0,
    }
    data = {
        "名称": "梦见月瑞希",
        "元素": "风",
        "圣遗物": [artifact.copy() for _ in range(5)],
        "属性": {
            "暴击率": 0.4,
            "暴击伤害": 1.2,
            "元素精通": 800,
        },
        "武器": {"名称": "", "精炼等级": 1},
        "命座": [],
    }

    stellar, stellar_name = get_effective(data)
    data["命座"] = ["一命", "二命", "三命", "四命"]
    high_cons, high_cons_name = get_effective(data)

    assert stellar["暴击率"] == 100
    assert stellar["暴击伤害"] == 100
    assert stellar["元素充能效率"] == 50
    assert stellar_name == "梦见月瑞希-星扩散"
    assert high_cons["元素充能效率"] == 30
    assert high_cons_name == "梦见月瑞希-星扩散|高命"

    data["命座"] = []
    data["属性"]["暴击率"] = 0
    data["属性"]["暴击伤害"] = 0
    for artifact in data["圣遗物"][:3]:
        artifact["所属套装"] = "血红之证"
    three_piece, three_piece_name = get_effective(data)
    data["圣遗物"][3]["所属套装"] = "血红之证"
    four_piece, four_piece_name = get_effective(data)
    assert three_piece["元素充能效率"] == 75
    assert three_piece_name == "梦见月瑞希"
    assert four_piece["元素充能效率"] == 50
    assert four_piece_name == "梦见月瑞希-星扩散"


def test_latest_character_artifact_score_rules() -> None:
    get_effective = load_artifact_utils().get_effective

    def make_data(
        name: str,
        *,
        mastery: float = 0,
        cpct: float = 0,
        cdmg: float = 0.5,
        cons: list[str] | None = None,
        weapon: str = "",
        weapon_refine: int = 1,
        main_affix: str = "生命值",
    ) -> dict:
        artifact = {
            "所属套装": "",
            "图标": "",
            "主属性": {"属性名": main_affix, "属性值": 0},
            "词条": [],
            "等级": 0,
        }
        return {
            "名称": name,
            "元素": "火",
            "圣遗物": [artifact.copy() for _ in range(5)],
            "属性": {
                "暴击率": cpct,
                "暴击伤害": cdmg,
                "元素精通": mastery,
                "元素充能效率": 1.0,
            },
            "武器": {"名称": weapon, "精炼等级": weapon_refine},
            "命座": cons or [],
        }

    klee, klee_name = get_effective(make_data("可莉"))
    assert klee["百分比攻击力"] == 85
    assert "元素精通" not in klee
    assert klee["元素充能效率"] == 30
    assert klee_name == "可莉-纯火"

    yoimiya, yoimiya_name = get_effective(make_data("宵宫"))
    assert yoimiya["百分比攻击力"] == 85
    assert "元素精通" not in yoimiya
    assert yoimiya_name == "宵宫-纯火"

    mastery_yoimiya, mastery_name = get_effective(
        make_data("宵宫", mastery=300, main_affix="元素精通")
    )
    assert mastery_yoimiya["元素精通"] == 75
    assert mastery_name == "宵宫"

    raiden, raiden_name = get_effective(
        make_data("雷电将军", mastery=501, cdmg=0)
    )
    assert {
        "百分比攻击力": 50,
        "暴击率": 50,
        "暴击伤害": 50,
        "元素精通": 100,
        "元素伤害加成": 50,
        "元素充能效率": 50,
    } == raiden
    assert raiden_name == "雷电将军-精通"

    hutao, hutao_name = get_effective(
        make_data("胡桃", cpct=0.1, cdmg=2.9)
    )
    assert hutao["百分比生命值"] == 80
    assert hutao["元素精通"] == 75
    assert hutao_name == "胡桃"

    furina_c1, furina_c1_name = get_effective(
        make_data("芙宁娜", cons=["一命"])
    )
    furina_c4, furina_c4_name = get_effective(
        make_data("芙宁娜", cons=["一命", "二命", "三命", "四命"])
    )
    assert furina_c1["元素充能效率"] == 100
    assert furina_c1_name == "芙宁娜"
    assert furina_c4["元素充能效率"] == 75
    assert furina_c4_name == "芙宁娜-高命"


def test_custom_score_keeps_generic_equipment_adjustments() -> None:
    get_effective = load_artifact_utils().get_effective
    artifact = {
        "所属套装": "",
        "图标": "",
        "主属性": {"属性名": "生命值", "属性值": 0},
        "词条": [],
        "等级": 0,
    }
    data = {
        "名称": "钟离",
        "元素": "岩",
        "圣遗物": [artifact.copy() for _ in range(5)],
        "属性": {
            "暴击率": 0.5,
            "暴击伤害": 1.5,
            "元素精通": 0,
        },
        "武器": {"名称": "护摩之杖", "精炼等级": 1},
        "命座": [],
    }

    weight, name = get_effective(data)

    assert weight["百分比生命值"] == 90
    assert name.endswith("武神护摩")


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

    for refine, expected in [(1, 36), (5, 72)]:
        weapon_context = context.clone()
        weapon_context.attr.atk_pct = 0
        weapon_context.weapon = {"名称": "熔猎异端之刃", "精炼等级": refine}
        apply_common_buffs(weapon_context)
        assert weapon_context.attr.atk_pct == expected


def test_furina_plunge_and_new_character_data() -> None:
    from data_source.damage.engine import get_role_dmg

    rules = read_json("miao_damage_rules.json")
    detail = rules["rules"]["芙宁娜"]["details"][-1]
    assert detail["title"] == "六命芒刀下落伤害·蒸发"
    assert detail["cons"] == 6
    data = {
        "名称": "芙宁娜", "元素": "水", "等级": 90,
        "命座": list(range(6)),
        "天赋": [{"等级": 10}, {"等级": 10}, {"等级": 10}],
        "武器": {"名称": "", "精炼等级": 1, "类型": "单手剑"},
        "圣遗物": [],
        "属性": {
            "基础生命": 15000, "额外生命": 25000,
            "基础攻击": 300, "额外攻击": 700,
            "基础防御": 600, "额外防御": 0,
            "伤害加成": [0] * 8, "元素精通": 100,
            "元素充能效率": 1.5, "暴击率": 0.5,
            "暴击伤害": 1.0, "治疗加成": 0,
        },
    }
    result = get_role_dmg(data)
    assert detail["title"] in result
    data["命座"] = list(range(5))
    assert detail["title"] not in get_role_dmg(data)
    roles = read_json("role_info.json")
    talents = read_json("miao_damage_talents.json")
    score = read_json("score.json")
    for name in ["沃雅妮莎", "薇斯纳"]:
        assert roles[name]["命座转换"] == [1, 2]
        assert set(talents["characters"][name]) >= {"a", "e", "q"}
    assert score["沃雅妮莎"] == {
        "hp": 100,
        "atk": 0,
        "def": 0,
        "cpct": 0,
        "cdmg": 0,
        "mastery": 0,
        "dmg": 0,
        "phy": 0,
        "recharge": 0,
        "heal": 75,
    }
    assert score["薇斯纳"]["mastery"] == 100


def test_miao_71_character_damage_rules_execute() -> None:
    from data_source.damage.engine import get_role_dmg

    base = {
        "等级": 90,
        "命座": [],
        "天赋": [{"等级": 10}, {"等级": 10}, {"等级": 10}],
        "圣遗物": [],
        "属性": {
            "基础生命": 15000,
            "额外生命": 10000,
            "基础攻击": 300,
            "额外攻击": 1000,
            "基础防御": 700,
            "额外防御": 0,
            "伤害加成": [0] * 8,
            "元素精通": 300,
            "元素充能效率": 1.5,
            "暴击率": 0.5,
            "暴击伤害": 1.0,
            "治疗加成": 0,
        },
    }
    vodyanitsa = {
        **base,
        "名称": "沃雅妮莎",
        "元素": "水",
        "武器": {"名称": "漩流颂歌", "精炼等级": 1, "类型": "法器"},
    }
    vesna = {
        **base,
        "名称": "薇斯纳",
        "元素": "风",
        "武器": {"名称": "新枝", "精炼等级": 1, "类型": "单手剑"},
    }

    vodyanitsa_result = get_role_dmg(vodyanitsa)
    vesna_result = get_role_dmg(vesna)

    assert "E唤春角笛后台伤害" in vodyanitsa_result
    assert "E每跳治疗量" in vodyanitsa_result
    assert "1命提供攻击力提升" not in vodyanitsa_result
    vodyanitsa["命座"] = ["一命"]
    vodyanitsa_c1_result = get_role_dmg(vodyanitsa)
    assert "1命提供攻击力提升" in vodyanitsa_c1_result
    assert "E后普攻首段伤害" in vesna_result
    assert "翔风剑一阶伤害" in vesna_result


def test_miao_71_weapon_buffs_apply() -> None:
    from data_source.damage.buffs import apply_common_buffs
    from data_source.damage.models import DamageAttributes, DamageContext

    def make_context(name: str, element: str = "风") -> DamageContext:
        return DamageContext(
            name="薇斯纳",
            element=element,
            level=90,
            cons=0,
            talent_levels={"a": 10, "e": 10, "q": 10},
            weapon={"名称": name, "精炼等级": 1},
            artifacts=[],
            attr=DamageAttributes(
                base_hp=15000,
                base_atk=300,
                base_defense=700,
                hp=25000,
                atk=1300,
                defense=700,
                mastery=0,
                recharge=150,
                cpct=50,
                cdmg=50,
                dmg=0,
                phy=0,
                heal=0,
            ),
        )

    new_branch = make_context("新枝")
    apply_common_buffs(new_branch)
    assert new_branch.attr.atk_pct == 6
    assert new_branch.attr.mastery == 0
    assert new_branch.attr.reaction_bonus["stellarSwirl"] == 8

    for element in ("水", "火", "岩", "草"):
        normal_branch = make_context("新枝", element=element)
        apply_common_buffs(normal_branch)
        assert normal_branch.attr.atk_pct == 4
        assert normal_branch.attr.mastery == 20
        for reaction in ("stellarConduct", "stellarSwirl", "stellarVortex"):
            assert normal_branch.attr.reaction_bonus.get(reaction, 0) == 0

    silver_lantern = make_context("银釭")
    apply_common_buffs(silver_lantern)
    assert silver_lantern.attr.mastery == 104

    butterfly = make_context("蝶变")
    apply_common_buffs(butterfly)
    assert butterfly.attr.cdmg == 106
    assert butterfly.attr.reaction_bonus["stellarVortex"] == 36

    flowing_song = make_context("漩流颂歌", element="水")
    apply_common_buffs(flowing_song)
    assert flowing_song.attr.heal == 4

    softwind_bow = make_context("柔风游弦")
    apply_common_buffs(softwind_bow)
    assert softwind_bow.attr.reaction_bonus["stellarConduct"] == 24
