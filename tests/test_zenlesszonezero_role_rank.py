import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

from PIL import Image, ImageFont
import pytest


PLUGIN_PATH = Path(__file__).parents[1] / "zenlesszonezero_role_info"
RANK_UTILS_PATH = PLUGIN_PATH / "utils" / "rank_utils.py"
SPEC = importlib.util.spec_from_file_location("zzz_rank_utils", RANK_UTILS_PATH)
assert SPEC and SPEC.loader
RANK_UTILS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RANK_UTILS)


def role_data(score: float, *, constellation: object = 2, star: object = 0) -> dict:
    return {
        "评分": score,
        "元素": "Fire",
        "影画": constellation,
        "武器": {"名称": "测试音擎", "图标": "Weapon_S_Test", "星级": star},
        "属性": {
            "基础生命值": 10_000,
            "额外生命值": 2_500,
            "基础攻击力": 1_000,
            "额外攻击力": 400,
            "基础暴击率": 500,
            "额外暴击率": 2_400,
            "基础暴击伤害": 5_000,
            "额外暴击伤害": 4_800,
            "基础异常精通": 100,
            "额外异常精通": 20,
        },
    }


def test_collect_filters_sorts_limits_and_formats_zzz_stats(tmp_path: Path) -> None:
    scores = [
        (100, 60.0),
        (2, 80.0),
        (11, 80.0),
        (3, 75.0),
    ]
    uid_map = {}
    members = []
    for index, (qq, score) in enumerate(scores):
        uid = f"100{index}"
        uid_map[str(qq)] = uid
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"角色": {"安比": role_data(score)}}), encoding="utf-8"
        )
        members.append(
            {"user_id": qq, "card": "" if index else "群名片", "nickname": f"昵称{qq}"}
        )

    uid_map[4] = "missing"
    members.extend(
        [
            {"user_id": 4, "nickname": "缺缓存"},
            {"user_id": 5, "nickname": "未绑定"},
            {"user_id": 6, "nickname": "坏 JSON"},
        ]
    )
    (tmp_path / "missing.json").write_text("{", encoding="utf-8")

    entries = RANK_UTILS.collect_role_rank_entries(
        members,
        uid_map,
        tmp_path,
        "安比",
        limit=16,
    )

    assert [entry["qq"] for entry in entries] == [2, 11, 3, 100]
    assert entries[0]["nickname"] == "昵称2"
    assert entries[0]["rows"] == [
        ("生命值", "12,500"),
        ("攻击力", "1,400"),
        ("暴击率", "29.0%"),
        ("暴击伤害", "98.0%"),
        ("异常精通", "120"),
    ]


def test_collect_rejects_bad_fields_and_enforces_sixteen_limit(tmp_path: Path) -> None:
    members = []
    uid_map = {}
    for index in range(18):
        qq = 10_000 - index
        uid = str(20_000 + index)
        uid_map[str(qq)] = uid
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"角色": {"安比": role_data(100 + index)}}), encoding="utf-8"
        )
        members.append({"user_id": qq, "nickname": str(qq)})

    uid_map[1] = "bad-fields"
    (tmp_path / "bad-fields.json").write_text(
        json.dumps({"角色": {"安比": {"评分": 999, "属性": []}}}), encoding="utf-8"
    )
    members.append({"user_id": 1, "nickname": "坏属性"})

    entries = RANK_UTILS.collect_role_rank_entries(
        members,
        uid_map,
        tmp_path,
        "安比",
        limit=99,
    )

    assert len(entries) == 16
    assert all(entry["nickname"] != "坏属性" for entry in entries)
    assert entries[0]["value"] == 117.0


def test_build_entry_maps_zzz_constellation_and_weapon_fields() -> None:
    entry = RANK_UTILS.build_rank_entry(
        123,
        "测试",
        role_data(256.1, constellation="-3", star=0),
    )

    assert entry is not None
    assert entry["rank"] == 0
    assert entry["影画"] == 0
    assert entry["weapon"] == {
        "图标": "Weapon_S_Test",
        "星级": 0,
    }
    assert entry["value"] == 256.1


def test_role_rank_card_renders_sixteen_entries_and_uses_zzz_weapon_url(
    monkeypatch, tmp_path: Path
) -> None:
    package_names = (
        "zzz_rank_preview",
        "zzz_rank_preview.data_source",
        "zzz_rank_preview.utils",
    )
    for package_name in package_names:
        package = types.ModuleType(package_name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, package_name, package)

    card_utils = types.ModuleType("zzz_rank_preview.utils.card_utils")
    card_utils.bg_path = str(PLUGIN_PATH / "res" / "background")
    card_utils.other_path = str(PLUGIN_PATH / "res" / "other")
    card_utils.weapon_path = str(tmp_path / "weapon")
    font_path = PLUGIN_PATH / "res" / "fonts"
    card_utils.get_font = lambda size, name="hywh.ttf": ImageFont.truetype(
        str(font_path / name), size
    )
    monkeypatch.setitem(sys.modules, card_utils.__name__, card_utils)

    image_utils = types.ModuleType("zzz_rank_preview.utils.image_utils")

    def load_image(path, size=None, crop=None, mode=None):
        image = Image.open(path)
        if size:
            image = image.resize(size)
        if crop:
            image = image.crop(crop)
        return image.convert(mode) if mode else image

    image_utils.load_image = load_image
    image_utils.draw_center_text = lambda draw, text, left, right, top, fill, font: draw.text(
        (left + (right - left - draw.textlength(text, font=font)) / 2, top),
        text,
        fill=fill,
        font=font,
    )
    image_utils.draw_right_text = lambda draw, text, right, top, fill, font: draw.text(
        (right - draw.textlength(text, font=font), top), text, fill=fill, font=font
    )
    requested_urls = []

    async def get_img(**kwargs):
        requested_urls.append(kwargs["url"])
        return Image.new("RGBA", kwargs["size"], (220, 120, 80, 220))

    image_utils.get_img = get_img
    monkeypatch.setitem(sys.modules, image_utils.__name__, image_utils)

    rank_utils = types.ModuleType("zzz_rank_preview.utils.rank_utils")
    rank_utils.RankEntry = dict
    monkeypatch.setitem(sys.modules, rank_utils.__name__, rank_utils)

    artifact_card = types.ModuleType("zzz_rank_preview.data_source.draw_artifact_card")

    async def draw_avatar(entry, mask):
        return Image.new("RGBA", mask.size, (70 + entry["QQ"] % 100, 90, 130, 130))

    artifact_card.draw_qq_logo_mask = draw_avatar
    monkeypatch.setitem(sys.modules, artifact_card.__name__, artifact_card)

    role_card = types.ModuleType("zzz_rank_preview.data_source.draw_role_card")
    role_card.resource_url = "https://enka.network/{}"
    monkeypatch.setitem(sys.modules, role_card.__name__, role_card)

    render_path = PLUGIN_PATH / "data_source" / "draw_role_rank_card.py"
    render_spec = importlib.util.spec_from_file_location(
        "zzz_rank_preview.data_source.draw_role_rank_card", render_path
    )
    assert render_spec and render_spec.loader
    render_module = importlib.util.module_from_spec(render_spec)
    render_spec.loader.exec_module(render_module)

    entries = [
        {
            "qq": 10_000 + index,
            "nickname": f"超长群名片{index}" if index > 10 else f"昵称{index}",
            "rank": index % 7,
            "影画": index % 7,
            "value": 300 - index * 3.5,
            "element": "Fire",
            "weapon": {"星级": 0, "图标": "Weapon_S_Test"},
            "rows": [
                ("生命值", "12,500"),
                ("攻击力", "1,400"),
                ("暴击率", "29.0%"),
                ("暴击伤害", "98.0%"),
                ("异常精通", "120"),
            ],
        }
        for index in range(16)
    ]
    image = asyncio.run(
        render_module.draw_role_rank_card(
            "安比评分排行", "安比", 123456789, entries, "0.2.5"
        )
    )

    image.save(tmp_path / "zzz-role-rank-preview.png")
    assert image.size == (1408, 1991)
    assert image.getbbox() == (0, 0, 1408, 1991)
    assert len(image.getcolors(maxcolors=image.width * image.height) or []) > 1000
    assert requested_urls == [
        "https://enka.network/ui/zzz/Weapon_S_Test.png"
    ] * 1
    with pytest.raises(ValueError, match="不支持的排行类型"):
        asyncio.run(
            render_module.draw_role_rank_card(
                "安比伤害排行", "安比", 123456789, entries, "0.2.5", "伤害"
            )
        )
