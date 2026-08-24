import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

from PIL import Image, ImageFont


MODULE_PATH = (
    Path(__file__).parents[1]
    / "genshin_role_info"
    / "utils"
    / "rank_utils.py"
)
SPEC = importlib.util.spec_from_file_location("genshin_rank_utils", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def role_data(score: float) -> dict:
    return {
        "评分": score,
        "命座": ["一", "二"],
        "武器": {
            "星级": 5,
            "图标": "UI_EquipIcon_Pole_Homa",
            "图标链接": "https://example.invalid/homa.png",
        },
        "属性": {
            "基础生命": 15_000,
            "额外生命": 20_000,
            "基础攻击": 700,
            "额外攻击": 1_300,
            "暴击率": 0.75,
            "暴击伤害": 2.1,
            "元素精通": 187,
            "元素充能效率": 1.321,
        },
    }


def test_select_damage_metric_uses_requested_one_based_row() -> None:
    damage = {
        "重击蒸发": ("123456", "250000"),
        "治疗量": ("999999",),
        "血梅香": ("45678", "90000"),
        "额外说明": ("半血以下",),
    }

    assert MODULE.select_damage_metric(damage, 2) == ("治疗量", 999999.0, None)
    assert MODULE.select_damage_metric(damage, 3) == ("血梅香", 45678.0, 90000.0)
    assert MODULE.select_damage_metric(damage, 4) is None


def test_collect_score_rank_filters_sorts_and_limits(tmp_path: Path) -> None:
    for uid, score in (("100000001", 220), ("100000002", 260), ("100000003", 240)):
        (tmp_path / f"{uid}.json").write_text(
            json.dumps({"角色": {"胡桃": role_data(score)}}), encoding="utf-8"
        )
    members = [
        {"user_id": 1, "card": "甲"},
        {"user_id": 2, "nickname": "乙"},
        {"user_id": 3, "nickname": "丙"},
        {"user_id": 4, "nickname": "未绑定"},
    ]
    uid_map = {
        "1": "100000001",
        "2": "100000002",
        "3": "100000003",
    }

    entries = MODULE.collect_role_rank_entries(
        members, uid_map, tmp_path, "胡桃", "评分", limit=2
    )

    assert [entry["nickname"] for entry in entries] == ["乙", "丙"]
    assert [entry["value"] for entry in entries] == [260.0, 240.0]
    assert entries[0]["rank"] == 2
    assert entries[0]["weapon"] == {
        "星级": 5,
        "图标": "UI_EquipIcon_Pole_Homa",
        "图标链接": "https://example.invalid/homa.png",
    }
    assert entries[0]["rows"] == [
        ("生命值", "35,000"),
        ("暴击率", "75.0%"),
        ("暴击伤害", "210.0%"),
        ("元素精通", "187"),
        ("元素充能效率", "132.1%"),
    ]


def test_collect_damage_rank_uses_requested_row(tmp_path: Path) -> None:
    data = role_data(220)
    data["测试伤害"] = 80_000
    (tmp_path / "100000001.json").write_text(
        json.dumps({"角色": {"胡桃": data}}), encoding="utf-8"
    )

    def damage_calculator(role: dict):
        value = role["测试伤害"]
        return {
            "第一项": (str(value * 10), str(value * 20)),
            "第二项": (str(value), str(value * 2)),
        }

    entries = MODULE.collect_role_rank_entries(
        [{"user_id": 1, "nickname": "测试"}],
        {"1": "100000001"},
        tmp_path,
        "胡桃",
        "伤害",
        damage_calculator=damage_calculator,
        damage_index=2,
    )

    assert len(entries) == 1
    assert entries[0]["value"] == 80_000
    assert entries[0]["damage_title"] == "第二项"


def test_role_rank_card_renders_four_by_four_layout(
    monkeypatch, tmp_path: Path
) -> None:
    plugin_path = Path(__file__).parents[1] / "genshin_role_info"
    package_names = (
        "rank_preview",
        "rank_preview.data_source",
        "rank_preview.utils",
    )
    for package_name in package_names:
        package = types.ModuleType(package_name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, package_name, package)

    card_utils = types.ModuleType("rank_preview.utils.card_utils")
    card_utils.bg_path = str(plugin_path / "res" / "background")
    card_utils.other_path = str(plugin_path / "res" / "other")
    card_utils.weapon_path = str(plugin_path / "user_data" / "res" / "weapon")
    font_path = plugin_path / "res" / "fonts"
    card_utils.get_font = lambda size, name="hywh.ttf": ImageFont.truetype(
        str(font_path / name), size
    )
    monkeypatch.setitem(sys.modules, card_utils.__name__, card_utils)

    image_utils = types.ModuleType("rank_preview.utils.image_utils")

    def load_image(path, size=None, crop=None, mode=None):
        image = Image.open(path)
        if size:
            image = image.resize(size)
        if crop:
            image = image.crop(crop)
        return image.convert(mode) if mode else image

    def draw_center_text(draw, text, left, right, top, fill, font):
        width = draw.textlength(text, font=font)
        draw.text((left + (right - left - width) / 2, top), text, fill=fill, font=font)

    def draw_right_text(draw, text, right, top, fill, font):
        draw.text(
            (right - draw.textlength(text, font=font), top),
            text,
            fill=fill,
            font=font,
        )

    image_utils.load_image = load_image
    image_utils.draw_center_text = draw_center_text
    image_utils.draw_right_text = draw_right_text

    async def get_img(**kwargs):
        return Image.new("RGBA", kwargs["size"], (220, 120, 80, 220))

    image_utils.get_img = get_img
    monkeypatch.setitem(sys.modules, image_utils.__name__, image_utils)

    rank_utils = types.ModuleType("rank_preview.utils.rank_utils")
    rank_utils.RankEntry = dict
    monkeypatch.setitem(sys.modules, rank_utils.__name__, rank_utils)

    artifact_card = types.ModuleType("rank_preview.data_source.draw_artifact_card")
    artifact_card.artifact_url = "https://example.invalid/{}.png"
    artifact_card.get_icon_url = lambda icon, source, fallback: source or fallback.format(icon)
    artifact_card.role_info_json = {"胡桃": {"元素": "火", "英文名": "Hutao"}}

    async def draw_avatar(entry, mask):
        color = (70 + entry["QQ"] % 120, 90, 130, 120)
        return Image.new("RGBA", mask.size, color)

    artifact_card.draw_qq_logo_mask = draw_avatar
    monkeypatch.setitem(sys.modules, artifact_card.__name__, artifact_card)

    render_path = plugin_path / "data_source" / "draw_role_rank_card.py"
    spec = importlib.util.spec_from_file_location(
        "rank_preview.data_source.draw_role_rank_card", render_path
    )
    assert spec and spec.loader
    render_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render_module)

    entries = [
        {
            "qq": 10000 + index,
            "nickname": (
                f"630抽61处双黄仍然歪了的超长群名片{index + 1}"
                if index >= 12
                else f"测试昵称很长{index + 1}"
            ),
            "rank": index % 7,
            "value": 300 - index * 3.5,
            "weapon": {
                "星级": 5,
                "图标": f"weapon-{index % 3}",
                "图标链接": "",
            },
            "rows": [
                ("生命值", "35,000"),
                ("暴击率", "75.0%"),
                ("暴击伤害", "210.0%"),
                ("元素精通", "187"),
                ("元素充能效率", "132.1%"),
            ],
            "damage_title": "重击蒸发",
        }
        for index in range(16)
    ]
    image = asyncio.run(
        render_module.draw_role_rank_card(
            "胡桃评分排行", "胡桃", 123456789, entries, "4.3.1", "评分"
        )
    )
    preview_path = tmp_path / "genshin-role-rank-preview.png"
    image.save(preview_path)

    assert image.size == (1408, 1991)
    assert image.getbbox() == (0, 0, 1408, 1991)
    assert len(image.getcolors(maxcolors=image.width * image.height) or []) > 1000

    damage_image = asyncio.run(
        render_module.draw_role_rank_card(
            "胡桃伤害排行5",
            "胡桃",
            123456789,
            entries,
            "4.3.1",
            "伤害",
        )
    )
    damage_image.save(tmp_path / "genshin-role-damage-rank-preview.png")
    assert damage_image.size == (1408, 1991)
