import ast
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "genshin_role_info"
    / "data_source"
    / "draw_update_card.py"
)
ROLE_CARD_PATH = MODULE_PATH.with_name("draw_role_card.py")


def test_role_sort_supports_empty_and_numeric_scores() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    draw_role_pic = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "draw_role_pic"
    )
    sort_call = next(
        node
        for node in ast.walk(draw_role_pic)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "sorted"
    )
    key_expression = next(
        keyword.value for keyword in sort_call.keywords if keyword.arg == "key"
    )

    class PlayerInfo:
        roles = {
            "有评分": {
                "评分": 200,
                "等级": 90,
                "命座": [],
                "武器": {"精炼等级": 1},
                "元素": "火",
            },
            "无评分": {
                "评分": "",
                "等级": 90,
                "命座": [],
                "武器": {"精炼等级": 1},
                "元素": "火",
            },
        }

        def get_roles_info(self, role: str) -> dict:
            return self.roles[role]

    key = eval(
        compile(ast.Expression(key_expression), MODULE_PATH, "eval"),
        {"player_info": PlayerInfo()},
    )

    assert sorted(["无评分", "有评分"], key=key, reverse=True) == [
        "有评分",
        "无评分",
    ]


def test_icon_url_prefers_mys_source_and_supports_enka_cache() -> None:
    tree = ast.parse(ROLE_CARD_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "get_icon_url"
    )
    namespace = {}
    exec(compile(ast.Module([function], type_ignores=[]), ROLE_CARD_PATH, "exec"), namespace)
    get_icon_url = namespace["get_icon_url"]

    assert get_icon_url(
        "hash",
        "https://upload.mihoyo.com/hash.png",
        "https://enka.network/ui/{}.png",
    ) == "https://upload.mihoyo.com/hash.png"
    assert get_icon_url(
        "UI_EquipIcon_Pole_Homa", "", "https://enka.network/ui/{}.png"
    ) == "https://enka.network/ui/UI_EquipIcon_Pole_Homa.png"
