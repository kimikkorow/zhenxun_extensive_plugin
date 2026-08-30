import asyncio
import importlib.util
import sys
import types
from pathlib import Path

from PIL import Image, ImageFont


def _load_update_card(monkeypatch, tmp_path: Path):
    plugin_path = Path(__file__).parents[1] / "starrail_role_info"
    package_names = (
        "zhenxun",
        "zhenxun.plugins",
        "zhenxun.services",
        "zhenxun.plugins.starrail_update_preview",
        "zhenxun.plugins.starrail_update_preview.data_source",
        "zhenxun.plugins.starrail_update_preview.utils",
        "zhenxun.plugins.plugin_utils",
    )
    packages = {}
    for package_name in package_names:
        package = types.ModuleType(package_name)
        package.__path__ = []
        packages[package_name] = package
        monkeypatch.setitem(sys.modules, package_name, package)

    log_module = types.ModuleType("zhenxun.services.log")
    warnings = []

    class Logger:
        def warning(self, message):
            warnings.append(message)

    log_module.logger = Logger()
    monkeypatch.setitem(sys.modules, "zhenxun.services.log", log_module)

    download_utils = types.ModuleType("zhenxun.plugins.plugin_utils.download_utils")

    class DownloadError(RuntimeError):
        pass

    download_utils.DownloadError = DownloadError
    monkeypatch.setitem(sys.modules, download_utils.__name__, download_utils)

    card_utils = types.ModuleType(
        "zhenxun.plugins.starrail_update_preview.utils.card_utils"
    )
    card_utils.avatar_path = str(tmp_path / "avatar")
    card_utils.bg_path = str(plugin_path / "res" / "background")
    card_utils.other_path = str(plugin_path / "res" / "other")
    card_utils.weapon_path = str(tmp_path / "weapon")
    font_path = plugin_path / "res" / "fonts"
    card_utils.get_font = lambda size, name="hywh.ttf": ImageFont.truetype(
        str(font_path / name), size
    )
    monkeypatch.setitem(sys.modules, card_utils.__name__, card_utils)

    image_utils = types.ModuleType(
        "zhenxun.plugins.starrail_update_preview.utils.image_utils"
    )

    def load_image(path, size=None, crop=None, mode=None):
        image = Image.open(path).copy()
        if size:
            image = image.resize(size)
        if crop:
            image = image.crop(crop)
        return image.convert(mode) if mode else image

    def draw_center_text(draw, text, left, right, top, fill, font):
        width = draw.textlength(text, font=font)
        draw.text((left + (right - left - width) / 2, top), text, fill=fill, font=font)

    image_utils.load_image = load_image
    image_utils.draw_center_text = draw_center_text
    image_utils.image_build = lambda img, **kwargs: img
    calls = []

    async def get_img(**kwargs):
        calls.append(kwargs)
        if kwargs["url"].endswith("/1512.png"):
            raise DownloadError("角色头像不存在")
        return Image.new("RGBA", (200, 200), (220, 120, 80, 220))

    image_utils.get_img = get_img
    monkeypatch.setitem(sys.modules, image_utils.__name__, image_utils)

    role_card = types.ModuleType(
        "zhenxun.plugins.starrail_update_preview.data_source.draw_role_card"
    )
    role_card.weapon_url = "https://example.invalid/light_cone/{}.png"
    monkeypatch.setitem(sys.modules, role_card.__name__, role_card)

    render_path = plugin_path / "data_source" / "draw_update_card.py"
    spec = importlib.util.spec_from_file_location(
        "zhenxun.plugins.starrail_update_preview.data_source.draw_update_card",
        render_path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, calls, warnings


def test_missing_starrail_avatar_does_not_abort_update_card(monkeypatch, tmp_path: Path):
    module, calls, warnings = _load_update_card(monkeypatch, tmp_path)

    class PlayerInfo:
        roles = {
            "知更鸟•晴歌": {
                "角色ID": "1512",
                "等级": 80,
                "元素": "Wind",
                "命途": "Memory",
                "星魂": [],
                "光锥": {"星级": ""},
                "评分": 191.8,
                "更新时间": "2026-08-28 05:10:35",
            },
            "流萤": {
                "角色ID": "1310",
                "等级": 80,
                "元素": "Fire",
                "命途": "Warrior",
                "星魂": [],
                "光锥": {"星级": ""},
                "评分": 200,
                "更新时间": "2026-08-28 05:10:35",
            },
        }

        def get_player_info(self):
            return {"昵称": "测试"}

        def get_roles_info(self, role):
            return self.roles[role]

    image = asyncio.run(
        module.draw_role_pic("164955675", PlayerInfo.roles, PlayerInfo())
    )

    assert image.size == (1608, 760)
    assert image.getbbox()
    avatar_urls = [call["url"] for call in calls]
    assert "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/character/1512.png" in avatar_urls
    assert "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/character/1309.png" not in avatar_urls
    assert any("role_id=1512" in warning for warning in warnings)
