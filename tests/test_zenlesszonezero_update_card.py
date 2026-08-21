import ast
from pathlib import Path


MODULE_PATH = (
    Path(__file__).parents[1]
    / "zenlesszonezero_role_info"
    / "data_source"
    / "draw_update_card.py"
)


def _load_avatar_url_resolver():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_get_role_avatar_url"
    )
    namespace = {
        "resource_url": "https://enka.network/{}",
        "role_avatar_url": {"已有角色": "https://example.com/avatar.png"},
    }
    exec(compile(ast.Module([function], type_ignores=[]), MODULE_PATH, "exec"), namespace)
    return namespace["_get_role_avatar_url"]


def test_role_avatar_url_uses_enka_resource_when_mapping_is_missing() -> None:
    get_role_avatar_url = _load_avatar_url_resolver()

    assert get_role_avatar_url("已有角色", {"立绘": "/ui/zzz/known.png"}) == (
        "https://example.com/avatar.png"
    )
    assert get_role_avatar_url("希格莉德", {"立绘": "/ui/zzz/IconRole66.png"}) == (
        "https://enka.network/ui/zzz/IconRole66.png"
    )
