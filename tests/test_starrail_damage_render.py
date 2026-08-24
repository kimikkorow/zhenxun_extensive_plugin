from __future__ import annotations

import importlib.util
from pathlib import Path

from PIL import Image, ImageDraw


PLUGIN_PATH = Path(__file__).parents[1] / "starrail_role_info"
RENDER_PATH = PLUGIN_PATH / "data_source" / "damage_render.py"


def _load_render_module():
    spec = importlib.util.spec_from_file_location(
        "starrail_damage_render_test",
        RENDER_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_damage_label_width_matches_genshin_dynamic_bounds() -> None:
    render = _load_render_module()
    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    assert render._damage_label_width(measure, [("普攻", ("1", "2"))]) == 250
    assert (
        render._damage_label_width(
            measure,
            [("终结技强化龙灵追击(同袍攻击:3000)(峥嵘)", ("1", "2"))],
        )
        == 360
    )


def test_damage_table_uses_genshin_columns_and_buff_section(monkeypatch) -> None:
    render = _load_render_module()
    centered: list[tuple[str, int, int, object]] = []
    original_center_text = render._center_text

    def record_center_text(draw, text, left, right, top, fill, font):
        centered.append((str(text), int(left), int(right), fill))
        original_center_text(draw, text, left, right, top, fill, font)

    monkeypatch.setattr(render, "_center_text", record_center_text)
    damage = {
        "终结技伤害": ("12345", "23456"),
        "战技治疗量": ("3456",),
        "额外说明": (
            "行迹-奈落：普攻、战技和终结技造成的伤害提高60%",
            "光锥：造成的伤害提高24%",
        ),
    }
    image = render.draw_dmg_pic(damage)

    measure = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    label_width = render._damage_label_width(
        measure,
        [("终结技伤害", ("12345", "23456")), ("战技治疗量", ("3456",))],
    )
    value_split = int(label_width + (render.IMAGE_WIDTH - label_width) / 2)

    assert ("暴击伤害", label_width, value_split, "white") in centered
    assert ("期望伤害", value_split, render.IMAGE_WIDTH, "white") in centered
    assert ("23456", label_width, value_split, "white") in centered
    assert ("12345", value_split, render.IMAGE_WIDTH, "white") in centered
    assert ("3456", label_width, render.IMAGE_WIDTH, "white") in centered
    assert image.size == (948, 360)

    colors = {
        color
        for _, color in image.getcolors(maxcolors=image.width * image.height) or []
    }
    assert (*render.BUFF_ACCENT_COLOR, 255) in colors
    assert (*render.BUFF_HINT_COLOR, 255) in colors


def test_buff_source_and_effect_split_on_chinese_or_ascii_colon() -> None:
    render = _load_render_module()

    assert render._split_buff("行迹：伤害提高") == ("行迹", "伤害提高")
    assert render._split_buff("Light Cone: Damage increased") == (
        "Light Cone",
        "Damage increased",
    )
    assert render._split_buff("无说明") == ("无说明", "")
