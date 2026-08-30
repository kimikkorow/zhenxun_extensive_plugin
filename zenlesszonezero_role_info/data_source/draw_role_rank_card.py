from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from ..utils.card_utils import bg_path, get_font, other_path, weapon_path
from ..utils.image_utils import draw_center_text, draw_right_text, get_img, load_image
from ..utils.rank_utils import RankEntry
from .draw_artifact_card import draw_qq_logo_mask
from .draw_role_card import resource_url


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred: int,
    minimum: int = 18,
    font_name: str = "hywh.ttf",
):
    max_width = max(1, max_width)
    for size in range(preferred, minimum - 1, -2):
        font = get_font(size, font_name)
        if draw.textlength(text, font=font) <= max_width:
            return font
    return get_font(minimum, font_name)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred: int,
    minimum: int = 18,
    font_name: str = "hywh.ttf",
) -> tuple[str, object]:
    font = _fit_font(
        draw,
        text,
        max_width,
        preferred,
        minimum=minimum,
        font_name=font_name,
    )
    if draw.textlength(text, font=font) <= max_width:
        return text, font

    suffix = "..."
    while text and draw.textlength(text + suffix, font=font) > max_width:
        text = text[:-1]
    return text + suffix, font


def _background_path(element: object) -> Path:
    element_text = str(element or "")
    element_background = Path(bg_path) / f"背景_{element_text}.png"
    if element_background.is_file():
        return element_background
    return Path(bg_path) / "bg.png"


def _weapon_star_index(value: object) -> int:
    try:
        star = int(value)
    except (TypeError, ValueError, OverflowError):
        star = 0
    return min(max(star, 0) + 1, 5)


async def draw_role_rank_card(
    title: str,
    role_name: str,
    group_id: int,
    entries: list[RankEntry],
    plugin_version: str,
    metric: str = "评分",
) -> Image.Image:
    if metric != "评分":
        raise ValueError(f"不支持的排行类型: {metric}，绝区零排行仅支持评分")
    del role_name
    entries = entries[:16]
    boundary = (70, 130)
    interval_y = 15
    mask_bottom = load_image(path=f"{other_path}/底遮罩.png", crop=(707, 936, 1024, 1370))
    mask_w, mask_h = mask_bottom.size
    rows = max(1, (len(entries) + 3) // 4)
    width = boundary[0] * 2 + mask_w * 4
    height = boundary[1] * 2 + mask_h * rows + interval_y * (rows - 1) - 50
    element = entries[0].get("element", "") if entries else ""
    background = load_image(
        _background_path(element),
        size=(width, height),
        mode="RGBA",
    )
    draw = ImageDraw.Draw(background)
    weapon_backgrounds: dict[int, Image.Image] = {}
    weapon_icons: dict[str, Image.Image] = {}
    level_mask = load_image(path=f"{other_path}/等级遮罩.png")

    for index, entry in enumerate(entries):
        x = boundary[0] + mask_w * (index % 4)
        y = boundary[1] + (mask_h + interval_y) * (index // 4)
        background.alpha_composite(mask_bottom, (x, y))
        try:
            avatar = await draw_qq_logo_mask({"QQ": entry["qq"]}, mask_bottom)
            background.alpha_composite(avatar, (x, y))
        except Exception:
            pass

        rank_text = f"#{index + 1}"
        draw_right_text(
            draw,
            rank_text,
            x + mask_w - 18,
            y + 18,
            "#ffde6b",
            get_font(28, "number.ttf"),
        )
        nickname, nickname_font = _fit_text(
            draw,
            str(entry.get("nickname", entry.get("qq", ""))),
            mask_w - 105,
            38,
            minimum=16,
        )
        draw.text((x + 24, y + 16), nickname, fill="white", font=nickname_font)

        score_label = "评分"
        score_font = get_font(28)
        draw.text((x + 24, y + 63), score_label, fill="#ffde6b", font=score_font)
        try:
            score_text = f"{float(entry.get('value', 0)):,.1f}"
        except (TypeError, ValueError):
            score_text = "0.0"
        score_x = x + 36 + draw.textlength(score_label, font=score_font)
        draw.text(
            (score_x, y + 63),
            score_text,
            fill="#ffde6b",
            font=_fit_font(
                draw,
                score_text,
                x + 194 - score_x,
                30,
                minimum=14,
                font_name="number.ttf",
            ),
        )

        weapon = entry.get("weapon")
        if not isinstance(weapon, dict):
            weapon = {}
        star_index = _weapon_star_index(weapon.get("星级"))
        if star_index not in weapon_backgrounds:
            try:
                weapon_backgrounds[star_index] = load_image(
                    f"{other_path}/star{star_index}.png",
                    size=(100, 100),
                )
            except (OSError, ValueError):
                pass
        if star_background := weapon_backgrounds.get(star_index):
            background.alpha_composite(star_background, (x + 200, y + 67))

        icon = str(weapon.get("图标", "") or "")
        if icon:
            icon_cache_name = Path(icon).name or "weapon"
            if icon_cache_name not in weapon_icons:
                try:
                    weapon_icons[icon_cache_name] = await get_img(
                        url=resource_url.format("ui/zzz/" + icon + ".png"),
                        size=(100, 100),
                        save_path=f"{weapon_path}/{icon_cache_name}.png",
                        mode="RGBA",
                    )
                except Exception:
                    pass
            if weapon_icon := weapon_icons.get(icon_cache_name):
                background.alpha_composite(weapon_icon, (x + 200, y + 67))

        background.alpha_composite(level_mask.resize((98, 30)), (x + 24, y + 112))
        constellation = entry.get("影画", entry.get("rank", 0))
        try:
            constellation = max(0, int(constellation))
        except (TypeError, ValueError, OverflowError):
            constellation = 0
        constellation_text = f"影画{constellation}"
        draw_center_text(
            draw,
            constellation_text,
            x + 24,
            x + 122,
            y + 113,
            "black",
            _fit_font(draw, constellation_text, 94, 23, minimum=12),
        )

        for row_index, (label, row_value) in enumerate(entry.get("rows", [])):
            row_y = y + 183 + row_index * 52
            label = str(label)
            row_value = str(row_value)
            draw.text(
                (x + 24, row_y),
                label,
                fill="#dfdfdf",
                font=_fit_font(draw, label, 125, 25, minimum=15),
            )
            draw_right_text(
                draw,
                row_value,
                x + mask_w - 24,
                row_y,
                "white",
                _fit_font(draw, row_value, 155, 25, minimum=14, font_name="number.ttf"),
            )

    title, title_font = _fit_text(
        draw,
        str(title),
        width - 100,
        96,
        minimum=42,
        font_name="优设标题黑.ttf",
    )
    draw_center_text(draw, title, 0, width, 5, "white", title_font)
    footer, footer_font = _fit_text(
        draw,
        f"group:{group_id} | v{plugin_version}",
        width - 100,
        46,
        minimum=24,
        font_name="优设标题黑.ttf",
    )
    draw_center_text(draw, footer, 0, width, height - 70, "white", footer_font)
    return background.convert("RGB")
