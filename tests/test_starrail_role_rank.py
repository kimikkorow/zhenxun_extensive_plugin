import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

from PIL import Image, ImageFont


MODULE_PATH = (
    Path(__file__).parents[1]
    / "starrail_role_info"
    / "utils"
    / "rank_utils.py"
)
SPEC = importlib.util.spec_from_file_location("starrail_rank_utils", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def role_data(score: float, *, rank: int = 3) -> dict:
    return {
        "评分": score,
        "星魂": [{} for _ in range(rank)],
        "光锥": {"星级": 5, "图标": "23001"},
        "属性": {
            "基础生命值": 10_000,
            "额外生命值": 20_000,
            "基础攻击力": 700,
            "额外攻击力": 1_300,
            "基础速度": 100,
            "额外速度": 25,
            "基础暴击率": 0.05,
            "暴击率": 0.70,
            "基础暴击伤害": 0.50,
            "暴击伤害": 1.60,
        },
    }


def write_role(tmp_path: Path, uid: str, data: dict) -> None:
    (tmp_path / f"{uid}.json").write_text(
        json.dumps({"角色": {"希儿": data}}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_collect_score_rank_filters_sorts_limit_and_adapts_starrail_fields(
    tmp_path: Path,
) -> None:
    write_role(tmp_path, "100000001", role_data(320, rank=6))
    write_role(tmp_path, "100000002", role_data(320, rank=2))
    write_role(tmp_path, "100000003", role_data(300))
    invalid_properties = role_data(999)
    invalid_properties["属性"] = {"基础生命值": 1}
    write_role(tmp_path, "100000004", invalid_properties)
    invalid_score = role_data(999)
    invalid_score["评分"] = "not-a-number"
    write_role(tmp_path, "100000005", invalid_score)
    (tmp_path / "100000006.json").write_text("{broken", encoding="utf-8")

    members = [
        {"user_id": 20, "card": "二十"},
        {"user_id": 10, "card": "", "nickname": "十"},
        {"user_id": 30, "nickname": "三十"},
        {"user_id": 40, "nickname": "属性异常"},
        {"user_id": 50, "nickname": "评分异常"},
        {"user_id": 60, "nickname": "JSON异常"},
        {"user_id": 70, "nickname": "未绑定"},
    ]
    uid_map = {
        "10": "100000001",
        "20": "100000002",
        "30": "100000003",
        "40": "100000004",
        "50": "100000005",
        "60": "100000006",
    }

    entries = MODULE.collect_role_rank_entries(
        members,
        uid_map,
        tmp_path,
        "希儿",
        "评分",
        limit=2,
    )

    assert [entry["qq"] for entry in entries] == [10, 20]
    assert [entry["nickname"] for entry in entries] == ["十", "二十"]
    assert [entry["value"] for entry in entries] == [320.0, 320.0]
    assert entries[0]["rank"] == 6
    assert entries[0]["weapon"] == {"星级": 5, "图标": "23001"}
    assert entries[0]["rows"] == [
        ("生命值", "30,000"),
        ("攻击力", "2,000"),
        ("速度", "125"),
        ("暴击率", "75.0%"),
        ("暴击伤害", "210.0%"),
    ]


def test_collect_score_rank_is_limited_to_sixteen(tmp_path: Path) -> None:
    members = []
    uid_map = {}
    for index in range(20):
        qq = 10_000 + index
        uid = str(2_000_000 + index)
        write_role(tmp_path, uid, role_data(100 + index))
        members.append({"user_id": qq, "nickname": str(qq)})
        uid_map[str(qq)] = uid

    entries = MODULE.collect_role_rank_entries(
        members,
        uid_map,
        tmp_path,
        "希儿",
        limit=16,
    )

    assert len(entries) == 16
    assert entries[0]["qq"] == 10_019
    assert entries[-1]["qq"] == 10_004


def test_select_damage_metric_uses_one_based_rows_and_excludes_notes() -> None:
    damage = {
        "普攻": ("12,345", "20,000"),
        "战技": ("54321",),
        "额外说明": ("行迹已生效", "光锥已生效"),
    }

    assert MODULE.select_damage_metric(damage, 1) == ("普攻", 12345.0, 20000.0)
    assert MODULE.select_damage_metric(damage, 2) == ("战技", 54321.0, None)
    assert MODULE.select_damage_metric(damage, 3) is None
    assert MODULE.select_damage_metric(damage, 0) is None


def test_collect_damage_rank_uses_requested_expected_damage(tmp_path: Path) -> None:
    first = role_data(100)
    first["测试伤害"] = 80_000
    second = role_data(999)
    second["测试伤害"] = 120_000
    write_role(tmp_path, "100000001", first)
    write_role(tmp_path, "100000002", second)

    def damage_calculator(role: dict):
        value = role["测试伤害"]
        return {
            "第一项": (str(value * 10), str(value * 20)),
            "第二项": (str(value), str(value * 2)),
            "额外说明": ("测试 Buff",),
        }

    entries = MODULE.collect_role_rank_entries(
        [
            {"user_id": 1, "nickname": "甲"},
            {"user_id": 2, "nickname": "乙"},
        ],
        {"1": "100000001", "2": "100000002"},
        tmp_path,
        "希儿",
        "伤害",
        damage_calculator=damage_calculator,
        damage_index=2,
    )

    assert [entry["qq"] for entry in entries] == [2, 1]
    assert [entry["value"] for entry in entries] == [120_000, 80_000]
    assert {entry["damage_title"] for entry in entries} == {"第二项"}


def test_role_rank_card_renders_sixteen_starrail_entries(
    monkeypatch, tmp_path: Path
) -> None:
    plugin_path = Path(__file__).parents[1] / "starrail_role_info"
    package_names = (
        "starrail_rank_preview",
        "starrail_rank_preview.data_source",
        "starrail_rank_preview.utils",
    )
    packages = {}
    for package_name in package_names:
        package = types.ModuleType(package_name)
        package.__path__ = []
        packages[package_name] = package
        monkeypatch.setitem(sys.modules, package_name, package)

    card_utils = types.ModuleType("starrail_rank_preview.utils.card_utils")
    card_utils.bg_path = str(plugin_path / "res" / "background")
    card_utils.other_path = str(plugin_path / "res" / "other")
    card_utils.weapon_path = str(tmp_path / "weapon")
    card_utils.json_path = str(plugin_path / "res" / "json_data")
    card_utils.role_data = {"1102": {"name": "希儿", "element": "Quantum"}}
    font_path = plugin_path / "res" / "fonts"
    card_utils.get_font = lambda size, name="hywh.ttf": ImageFont.truetype(
        str(font_path / name), size
    )
    monkeypatch.setitem(sys.modules, card_utils.__name__, card_utils)
    monkeypatch.setattr(
        packages["starrail_rank_preview.utils"],
        "card_utils",
        card_utils,
        raising=False,
    )

    image_utils = types.ModuleType("starrail_rank_preview.utils.image_utils")

    def load_image(path, size=None, crop=None, mode=None):
        image = Image.open(path).copy()
        if crop:
            image = image.crop(crop)
        if size:
            image = image.resize(size)
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
    get_img_calls = []

    async def get_img(**kwargs):
        get_img_calls.append(kwargs)
        return Image.new("RGBA", kwargs["size"], (220, 120, 80, 220))

    image_utils.get_img = get_img
    monkeypatch.setitem(sys.modules, image_utils.__name__, image_utils)
    monkeypatch.setattr(
        packages["starrail_rank_preview.utils"],
        "image_utils",
        image_utils,
        raising=False,
    )

    rank_utils = types.ModuleType("starrail_rank_preview.utils.rank_utils")
    rank_utils.RankEntry = dict
    monkeypatch.setitem(sys.modules, rank_utils.__name__, rank_utils)

    artifact_card = types.ModuleType(
        "starrail_rank_preview.data_source.draw_artifact_card"
    )

    async def draw_avatar(entry, mask):
        return Image.new("RGBA", mask.size, (70 + entry["QQ"] % 120, 90, 130, 120))

    artifact_card.draw_qq_logo_mask = draw_avatar
    monkeypatch.setitem(sys.modules, artifact_card.__name__, artifact_card)
    monkeypatch.setattr(
        packages["starrail_rank_preview.data_source"],
        "draw_artifact_card",
        artifact_card,
        raising=False,
    )

    role_card = types.ModuleType("starrail_rank_preview.data_source.draw_role_card")
    role_card.weapon_url = "https://example.invalid/light_cone/{}.png"
    monkeypatch.setitem(sys.modules, role_card.__name__, role_card)
    monkeypatch.setattr(
        packages["starrail_rank_preview.data_source"],
        "draw_role_card",
        role_card,
        raising=False,
    )

    render_path = plugin_path / "data_source" / "draw_role_rank_card.py"
    render_spec = importlib.util.spec_from_file_location(
        "starrail_rank_preview.data_source.draw_role_rank_card", render_path
    )
    assert render_spec and render_spec.loader
    render_module = importlib.util.module_from_spec(render_spec)
    render_spec.loader.exec_module(render_module)

    entries = [
        {
            "qq": 10_000 + index,
            "nickname": f"测试星铁昵称很长{index + 1}",
            "rank": index % 7,
            "value": 300 - index * 3.5,
            "weapon": {"星级": 5, "图标": "23001"},
            "rows": [
                ("生命值", "30,000"),
                ("攻击力", "2,000"),
                ("速度", "125"),
                ("暴击率", "75.0%"),
                ("暴击伤害", "210.0%"),
            ],
        }
        for index in range(16)
    ]
    image = asyncio.run(
        render_module.draw_role_rank_card(
            "希儿评分排行", "希儿", 123456789, entries, "1.3.8"
        )
    )

    assert image.size == (1408, 1991)
    assert image.getbbox() == (0, 0, 1408, 1991)
    assert len(image.getcolors(maxcolors=image.width * image.height) or []) > 1000
    assert get_img_calls[0]["url"] == role_card.weapon_url.format("23001")
    assert str(get_img_calls[0]["save_path"]).endswith("weapon/23001.png")
