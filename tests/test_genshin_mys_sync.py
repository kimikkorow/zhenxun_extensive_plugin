from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "genshin_role_info" / "mys_sync.py"
COMMAND_PATH = Path(__file__).parents[1] / "genshin_role_info" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("genshin_role_info_mys_sync", MODULE_PATH)
assert SPEC and SPEC.loader
mys_sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mys_sync)


def test_mys_command_runs_existing_artifact_postprocessor() -> None:
    tree = ast.parse(COMMAND_PATH.read_text(encoding="utf-8"))
    handler = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_update_panel_from_mys"
    )
    postprocess_call = next(
        (
            node
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "check_artifact"
        ),
        None,
    )

    assert postprocess_call is not None
    assert ast.unparse(postprocess_call.args[1]) == "player_info"
    assert ast.unparse(postprocess_call.args[4]) == "True"
    draw_call = next(
        (
            node
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "draw_role_pic"
        ),
        None,
    )
    assert draw_call is not None
    assert postprocess_call.lineno < draw_call.lineno


def _detail_data() -> dict:
    return {
        "property_map": {
            "2": {"name": "生命值"},
            "20": {"name": "暴击率"},
        },
        "list": [
            {
                "base": {
                    "id": 10000046,
                    "name": "胡桃",
                    "element": "Pyro",
                    "level": 90,
                    "actived_constellation_num": 1,
                },
                "selected_properties": [
                    {
                        "property_type": 2000,
                        "base": "15552",
                        "add": "20000",
                        "final": "35552",
                    },
                    {
                        "property_type": 2001,
                        "base": "715",
                        "add": "500",
                        "final": "1215",
                    },
                    {
                        "property_type": 2002,
                        "base": "876",
                        "add": "120",
                        "final": "996",
                    },
                    {
                        "property_type": 22,
                        "base": "50.0%",
                        "add": "150.0%",
                        "final": "200.0%",
                    },
                    {
                        "property_type": 23,
                        "base": "100.0%",
                        "add": "20.0%",
                        "final": "120.0%",
                    },
                    {"property_type": 28, "base": "0", "add": "100", "final": "100"},
                ],
                "extra_properties": [
                    {
                        "property_type": 20,
                        "base": "5.0%",
                        "add": "65.0%",
                        "final": "70.0%",
                    },
                ],
                "element_properties": [
                    {
                        "property_type": 40,
                        "base": "0.0%",
                        "add": "46.6%",
                        "final": "46.6%",
                    },
                ],
                "skills": [
                    {
                        "skill_id": 10017,
                        "skill_type": 1,
                        "level": 10,
                        "icon": "https://act-upload.mihoyo.com/Skill_A_03.png",
                    },
                    {
                        "skill_id": 10462,
                        "skill_type": 1,
                        "level": 10,
                        "icon": (
                            "https://act-upload.mihoyo.com/Skill_S_Hutao_01.png"
                        ),
                    },
                    {
                        "skill_id": 10463,
                        "skill_type": 1,
                        "level": 9,
                        "icon": (
                            "https://act-upload.mihoyo.com/Skill_E_Hutao_01.png"
                        ),
                    },
                    {
                        "skill_id": 10464,
                        "skill_type": 2,
                        "level": 1,
                        "icon": "Skill_P_Hutao_01",
                    },
                ],
                "constellations": [
                    {
                        "icon": (
                            "https://act-upload.mihoyo.com/"
                            "UI_Talent_S_Hutao_01.png"
                        ),
                        "is_actived": True,
                    },
                    {"icon": "UI_Talent_S_Hutao_02", "is_actived": False},
                ],
                "weapon": {
                    "name": "护摩之杖",
                    "icon": (
                        "https://act-upload.mihoyo.com/game_record/"
                        "UI_EquipIcon_Pole_Homa.png"
                    ),
                    "level": 90,
                    "rarity": 5,
                    "promote_level": 6,
                    "affix_level": 1,
                    "main_property": {"property_type": 4, "final": "608"},
                    "sub_property": {"property_type": 22, "final": "66.2%"},
                },
                "relics": [
                    {
                        "name": "魔女的炎之花",
                        "icon": (
                            "https://act-upload.mihoyo.com/"
                            "UI_RelicIcon_15006_4.png"
                        ),
                        "pos_name": "生之花",
                        "rarity": 5,
                        "level": 20,
                        "set": {"name": "炽烈的炎之魔女"},
                        "main_property": {"property_type": 2, "value": "4780"},
                        "sub_property_list": [
                            {
                                "property_type": 20,
                                "value": "10.5%",
                                "times": 2,
                            },
                        ],
                    }
                ],
            }
        ],
    }


def test_convert_character_detail_matches_panel_schema() -> None:
    role = mys_sync.convert_character(
        _detail_data()["list"][0], _detail_data()["property_map"]
    )

    assert role["名称"] == "胡桃"
    assert role["元素"] == "火"
    assert role["等级"] == 90
    assert role["属性"] == {
        "基础生命": 15552,
        "额外生命": 20000,
        "基础攻击": 715,
        "额外攻击": 500,
        "基础防御": 876,
        "额外防御": 120,
        "暴击率": 0.7,
        "暴击伤害": 2.0,
        "元素精通": 100,
        "元素充能效率": 1.2,
        "治疗加成": 0,
        "受治疗加成": 0,
        "伤害加成": [0, 0.466, 0, 0, 0, 0, 0, 0],
    }
    assert [item["等级"] for item in role["天赋"]] == [10, 10, 9]
    assert [item["图标链接"] for item in role["天赋"]] == [
        "https://act-upload.mihoyo.com/Skill_A_03.png",
        "https://act-upload.mihoyo.com/Skill_S_Hutao_01.png",
        "https://act-upload.mihoyo.com/Skill_E_Hutao_01.png",
    ]
    assert role["命座"] == ["UI_Talent_S_Hutao_01"]
    assert role["命座图标链接"] == [
        "https://act-upload.mihoyo.com/UI_Talent_S_Hutao_01.png"
    ]
    assert role["武器"]["基础攻击"] == 608
    assert role["武器"]["图标"] == "UI_EquipIcon_Pole_Homa"
    assert role["武器"]["图标链接"] == (
        "https://act-upload.mihoyo.com/game_record/UI_EquipIcon_Pole_Homa.png"
    )
    assert role["武器"]["副属性"] == {"属性名": "暴击伤害", "属性值": 66.2}
    assert role["圣遗物"][0]["图标链接"] == (
        "https://act-upload.mihoyo.com/UI_RelicIcon_15006_4.png"
    )
    assert role["圣遗物"][0]["主属性"] == {"属性名": "生命值", "属性值": 4780}
    assert role["圣遗物"][0]["词条"] == [
        {"属性名": "暴击率", "属性值": 10.5, "强化次数": 2}
    ]


@pytest.mark.parametrize("times", [0, 5])
def test_convert_artifact_preserves_miao_upgrade_count_boundaries(times: int) -> None:
    substat = mys_sync._convert_artifact_substat(
        {"property_type": 20, "value": "10.5%", "times": times},
        {},
    )

    assert substat["强化次数"] == times


def test_convert_mona_skips_alternate_sprint_talent() -> None:
    data = {
        "base": {
            "id": 10000041,
            "name": "莫娜",
            "element": "Hydro",
            "level": 90,
            "actived_constellation_num": 6,
        },
        "skills": [
            {
                "skill_id": 10411,
                "skill_type": 1,
                "level": 1,
                "icon": "https://act-upload.mihoyo.com/Skill_A_Catalyst_MD.png",
            },
            {
                "skill_id": 10412,
                "skill_type": 1,
                "level": 4,
                "icon": "https://act-upload.mihoyo.com/Skill_S_Mona_01.png",
            },
            {
                "skill_id": 10413,
                "skill_type": 1,
                "level": 1,
                "icon": "https://act-upload.mihoyo.com/Skill_S_Mona_02.png",
            },
            {
                "skill_id": 10415,
                "skill_type": 1,
                "level": 13,
                "icon": "https://act-upload.mihoyo.com/Skill_E_Mona_01.png",
            },
        ],
    }

    role = mys_sync.convert_character(data, {})

    assert [item["等级"] for item in role["天赋"]] == [1, 4, 13]
    assert [item["图标"] for item in role["天赋"]] == [
        "Skill_A_Catalyst_MD",
        "Skill_S_Mona_01",
        "Skill_E_Mona_01",
    ]


def test_convert_ayaka_selects_talents_by_id() -> None:
    data = {
        "base": {
            "id": 10000002,
            "name": "神里绫华",
            "element": "Cryo",
            "level": 90,
            "actived_constellation_num": 1,
        },
        "skills": [
            {"skill_id": 10024, "skill_type": 1, "level": 10, "icon": "a.png"},
            {"skill_id": 10018, "skill_type": 1, "level": 10, "icon": "e.png"},
            {"skill_id": 10019, "skill_type": 1, "level": 10, "icon": "q.png"},
            {
                "skill_id": 10013,
                "skill_type": 1,
                "level": 1,
                "icon": "alternate_sprint.png",
            },
        ],
    }

    role = mys_sync.convert_character(data, {})

    assert [item["等级"] for item in role["天赋"]] == [10, 10, 10]
    assert [item["图标"] for item in role["天赋"]] == [
        "Skill_A_01",
        "Skill_S_Ayaka_01",
        "Skill_E_Ayaka",
    ]


def test_cache_write_overwrites_binding_and_preserves_inventory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(mys_sync, "PLAYER_INFO_DIR", tmp_path)
    mys_sync._write_json(tmp_path / "qq2uid.json", {"10001": 987654321})
    mys_sync._write_json(
        tmp_path / "123456789.json",
        {
            "角色": {"旧角色": {}},
            "圣遗物列表": [[{"名称": "已导入圣遗物"}], [], [], [], []],
            "圣遗物榜单": [{"评分": 50}],
        },
    )

    mys_sync.overwrite_uid_binding(10001, "123456789")
    count = mys_sync.save_character_cache(
        "123456789",
        {"nickname": "旅行者", "level": 60},
        _detail_data(),
    )

    binding = mys_sync._read_json(tmp_path / "qq2uid.json")
    cache = mys_sync._read_json(tmp_path / "123456789.json")
    assert binding["10001"] == 123456789
    assert count == 1
    assert list(cache["角色"]) == ["胡桃"]
    assert cache["圣遗物榜单"] == []
    assert cache["圣遗物列表"][0] == [{"名称": "已导入圣遗物"}]


def test_bind_single_uid_only_overwrites_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, str]] = []
    monkeypatch.setattr(
        mys_sync,
        "overwrite_uid_binding",
        lambda qq_id, uid: calls.append((qq_id, uid)),
    )

    result = mys_sync.bind_single_genshin_uid(
        10001,
        {
            "game_roles": {
                "genshin": [
                    {"game_uid": "123456789", "region": "cn_gf01"}
                ]
            }
        },
    )

    assert result.status == "bound"
    assert result.uid == "123456789"
    assert result.role_count == 0
    assert calls == [(10001, "123456789")]


@pytest.mark.parametrize("roles", [[], [{"game_uid": "1"}, {"game_uid": "2"}]])
def test_bind_non_single_uid_keeps_existing_binding(
    monkeypatch: pytest.MonkeyPatch,
    roles: list[dict],
) -> None:
    monkeypatch.setattr(
        mys_sync,
        "overwrite_uid_binding",
        lambda *_: pytest.fail("不应覆盖绑定"),
    )

    result = mys_sync.bind_single_genshin_uid(
        10001,
        {"game_roles": {"genshin": roles}},
    )

    assert result.status == "skipped"
    assert result.role_count == 0


@pytest.mark.asyncio
async def test_single_uid_overwrites_binding_and_updates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []

    class FakeAPI:
        async def get_genshin_character_details(self, credentials, **kwargs):
            calls.append(("request", credentials, kwargs))
            return _detail_data()

    monkeypatch.setattr(
        mys_sync,
        "overwrite_uid_binding",
        lambda qq_id, uid: calls.append(("bind", qq_id, uid)),
    )
    monkeypatch.setattr(
        mys_sync,
        "save_character_cache",
        lambda uid, role, data: (
            calls.append(("save", uid, role["nickname"], len(data["list"]))) or 1
        ),
    )
    user = {
        "account_id": "account",
        "cookie_token": "cookie",
        "ltoken": "ltoken",
        "stoken": "stoken",
        "mid": "mid",
        "game_roles": {
            "genshin": [
                {
                    "game_uid": "123456789",
                    "region": "cn_gf01",
                    "nickname": "旅行者",
                    "level": 60,
                }
            ]
        },
    }

    async def notify_captcha(link: str) -> None:
        return None

    result = await mys_sync.sync_single_genshin_uid(
        10001,
        user,
        FakeAPI(),
        notify_captcha,
    )

    assert result.status == "synced"
    assert result.uid == "123456789"
    assert result.role_count == 1
    assert calls[0] == ("bind", 10001, "123456789")
    assert calls[1][0] == "request"
    assert calls[1][2]["captcha_notifier"] is notify_captcha
    assert calls[2] == ("save", "123456789", "旅行者", 1)


@pytest.mark.asyncio
async def test_api_failure_keeps_overwritten_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple] = []

    class FakeAPI:
        async def get_genshin_character_details(self, credentials, **kwargs):
            raise RuntimeError("米游社触发人机验证")

    monkeypatch.setattr(
        mys_sync, "overwrite_uid_binding", lambda qq_id, uid: calls.append((qq_id, uid))
    )
    user = {"game_roles": {"genshin": [{"game_uid": "123456789", "region": "cn_gf01"}]}}

    result = await mys_sync.sync_single_genshin_uid(10001, user, FakeAPI())

    assert calls == [(10001, "123456789")]
    assert result.status == "failed"
    assert result.uid == "123456789"
    assert result.error == "米游社触发人机验证"


@pytest.mark.asyncio
@pytest.mark.parametrize("roles", [[], [{"game_uid": "1"}, {"game_uid": "2"}]])
async def test_non_single_uid_keeps_existing_binding(
    monkeypatch: pytest.MonkeyPatch,
    roles: list[dict],
) -> None:
    monkeypatch.setattr(
        mys_sync,
        "overwrite_uid_binding",
        lambda *_: pytest.fail("不应覆盖绑定"),
    )

    result = await mys_sync.sync_single_genshin_uid(
        10001,
        {"game_roles": {"genshin": roles}},
        object(),
    )

    assert result.status == "skipped"
    assert result.role_count == 0
