import ast
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
