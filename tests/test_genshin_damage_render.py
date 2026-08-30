from __future__ import annotations

import importlib.util
from pathlib import Path


PLUGIN_PATH = Path(__file__).parents[1] / "genshin_role_info"
RENDER_PATH = PLUGIN_PATH / "data_source" / "damage" / "render.py"


def _load_render_module():
    spec = importlib.util.spec_from_file_location(
        "genshin_damage_render_test",
        RENDER_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_text_damage_rows_use_character_font(monkeypatch) -> None:
    render = _load_render_module()
    centered: list[tuple[str, str]] = []
    original_center_text = render._center_text

    def record_center_text(draw, text, left, right, top, fill, font):
        centered.append((str(text), str(getattr(font, "path", ""))))
        original_center_text(draw, text, left, right, top, fill, font)

    monkeypatch.setattr(render, "_center_text", record_center_text)
    render.draw_dmg_pic(
        {
            "E攻击力提升": ("11.7%",),
            "点按E伤害": ("60", "89"),
        }
    )

    text_font = next(path for text, path in centered if text == "11.7%")
    assert text_font.endswith("hywh.ttf")
    assert render._is_text_value(("11.7%",))
    assert not render._is_text_value(("60",))
