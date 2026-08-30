import ast
import math
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "genshin_role_info"
    / "utils"
    / "artifact_utils.py"
)


def test_miao_score_supports_no_effective_main_affix() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_miao_score"
    )
    namespace = {}
    exec(compile(ast.Module([function], type_ignores=[]), MODULE_PATH, "exec"), namespace)

    _, _, max_mark = namespace["get_miao_score"](
        {"元素充能效率": 100},
        {"攻击力": 300, "防御力": 200, "生命值": 3000},
    )

    assert max_mark["2"]["main"] == 100
    assert max_mark["3"]["main"] == 0
    assert max_mark["4"]["main"] == 0
    assert max_mark["3"]["total"] > 0


def _load_genshin_roll_helpers():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    names = {
        "grow_max_value",
        "grow_min_value",
        "upgrade_count_marks",
    }
    nodes = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in names
                for target in node.targets
            )
        )
        or (
            isinstance(node, ast.FunctionDef)
            and node.name
            in {"get_artifact_upgrade_counts", "get_upgrade_count_mark"}
        )
    ]
    namespace = {"math": math}
    exec(compile(ast.Module(nodes, type_ignores=[]), MODULE_PATH, "exec"), namespace)
    return namespace


def test_genshin_upgrade_count_prefers_exact_miao_value() -> None:
    namespace = _load_genshin_roll_helpers()
    artifact = {
        "等级": 20,
        "词条": [
            {"属性名": "暴击率", "属性值": 11.7, "强化次数": 2},
            {"属性名": "暴击伤害", "属性值": 31.1, "强化次数": "4"},
        ],
    }

    assert namespace["get_artifact_upgrade_counts"](artifact, True) == [2, 4]
    assert namespace["get_upgrade_count_mark"](2) == "²"
    assert namespace["get_upgrade_count_mark"](6) == ""


def test_genshin_upgrade_count_keeps_legacy_value_inference() -> None:
    namespace = _load_genshin_roll_helpers()
    artifact = {
        "等级": 20,
        "词条": [{"属性名": "暴击率", "属性值": 7.8}],
    }

    assert namespace["get_artifact_upgrade_counts"](artifact) == [1]


def _load_starrail_roll_helpers():
    module_path = (
        Path(__file__).parents[1]
        / "starrail_role_info"
        / "utils"
        / "artifact_utils.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"get_upgrade_count_mark", "get_relic_upgrade_count"}
    ]
    namespace = {
        "upgrade_count_marks": {1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵"},
        "relic": {"test": {"sub_affix_id": "5"}},
        "relic_sub_value": {
            "5": {
                "affixes": {
                    "8": {
                        "property": "CriticalChanceBase",
                        "base": 0.02592,
                        "step": 0.00324,
                        "step_num": 2,
                    }
                }
            }
        },
        "trans_data": {"property": {"CriticalChanceBase": "暴击率"}},
        "sub_grow_max_value": {"暴击率": 0.0324},
    }
    exec(compile(ast.Module(functions, type_ignores=[]), module_path, "exec"), namespace)
    return namespace


def test_starrail_upgrade_count_excludes_initial_roll() -> None:
    namespace = _load_starrail_roll_helpers()

    count = namespace["get_relic_upgrade_count"](
        {"ID": "test"},
        {"属性名": "暴击率", "属性值": 0.1, "强化次数": "6"},
    )

    assert count == 5
    assert namespace["get_upgrade_count_mark"](5) == "⁵"
    assert namespace["get_upgrade_count_mark"](6) == ""


def test_starrail_upgrade_count_infers_old_cache_by_relic_growth() -> None:
    namespace = _load_starrail_roll_helpers()

    count = namespace["get_relic_upgrade_count"](
        {"ID": "test"},
        {"属性名": "暴击率", "属性值": 0.08424},
    )

    assert count == 2
