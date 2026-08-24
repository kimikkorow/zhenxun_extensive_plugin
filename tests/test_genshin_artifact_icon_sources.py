import ast
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).parents[1]
    / "genshin_role_info"
    / "utils"
    / "card_utils.py"
)
ROLE_CARD_PATH = MODULE_PATH.parents[1] / "data_source" / "draw_role_card.py"


def _load_backfill():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "backfill_artifact_icon_sources"
    )
    namespace = {}
    exec(compile(ast.Module([function], type_ignores=[]), MODULE_PATH, "exec"), namespace)
    return namespace["backfill_artifact_icon_sources"]


def _load_icon_url():
    tree = ast.parse(ROLE_CARD_PATH.read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "MissingIconSourceError"
        )
        or (isinstance(node, ast.FunctionDef) and node.name == "get_icon_url")
    ]
    namespace = {}
    exec(
        compile(ast.Module(nodes, type_ignores=[]), ROLE_CARD_PATH, "exec"),
        namespace,
    )
    return namespace["get_icon_url"], namespace["MissingIconSourceError"]


def test_backfills_legacy_mys_artifact_icon_source() -> None:
    source = "https://act-webstatic.mihoyo.com/item/hash.png"
    data = {
        "角色": {
            "恰斯卡": {
                "圣遗物": [
                    {"图标": "hash", "图标链接": source},
                    {"图标": "UI_RelicIcon_15021_4"},
                ]
            }
        },
        "圣遗物列表": [
            [{"图标": "hash"}, {"图标": "UI_RelicIcon_15021_4"}],
            [],
            [],
            [],
            [],
        ],
    }

    updated = _load_backfill()(data, {})

    assert updated == 1
    assert data["圣遗物列表"][0][0]["图标链接"] == source
    assert "图标链接" not in data["圣遗物列表"][0][1]


def test_preserves_existing_artifact_icon_source() -> None:
    data = {
        "角色": {
            "恰斯卡": {
                "圣遗物": [
                    {"图标": "hash", "图标链接": "https://new.example/hash.png"}
                ]
            }
        },
        "圣遗物列表": [
            [{"图标": "hash", "图标链接": "https://old.example/hash.png"}],
            [],
            [],
            [],
            [],
        ],
    }

    updated = _load_backfill()(data, {})

    assert updated == 0
    assert (
        data["圣遗物列表"][0][0]["图标链接"]
        == "https://old.example/hash.png"
    )


def test_uses_canonical_enka_icon_for_unmapped_mys_hash() -> None:
    data = {
        "角色": {},
        "圣遗物列表": [
            [{"名称": "宗室银瓮", "图标": "mihoyo_hash"}],
            [],
            [],
            [],
            [],
        ],
    }

    updated = _load_backfill()(data, {"宗室银瓮": "UI_RelicIcon_15007_4"})

    assert updated == 1
    assert data["圣遗物列表"][0][0]["图标链接"] == (
        "https://enka.network/ui/UI_RelicIcon_15007_4.png"
    )


def test_accepts_non_ui_enka_skill_icon() -> None:
    get_icon_url, _ = _load_icon_url()

    assert get_icon_url(
        "Skill_A_04", "", "https://enka.network/ui/{}.png"
    ) == "https://enka.network/ui/Skill_A_04.png"


def test_rejects_mys_hash_without_an_original_source() -> None:
    get_icon_url, error = _load_icon_url()

    with pytest.raises(error):
        get_icon_url(
            "4bde30654f95c0666d3318326260ad45",
            "",
            "https://enka.network/ui/{}.png",
        )
