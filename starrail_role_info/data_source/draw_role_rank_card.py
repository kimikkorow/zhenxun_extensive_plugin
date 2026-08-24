from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from PIL import Image, ImageDraw

from ..utils import card_utils
from ..utils.card_utils import bg_path, get_font, json_path, other_path, weapon_path
from ..utils.image_utils import draw_center_text, draw_right_text, get_img, load_image
from ..utils.rank_utils import RankEntry
from .draw_artifact_card import draw_qq_logo_mask
from .draw_role_card import weapon_url


def _fit_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    preferred: int,
    minimum: int = 16,
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
    minimum: int = 16,
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
    return (text + suffix if text else suffix), font


def _role_element(role_name: str) -> str:
    character_data = getattr(card_utils, "role_data", {})
    if isinstance(character_data, Mapping):
        for metadata in character_data.values():
            if not isinstance(metadata, Mapping):
                continue
            if metadata.get("name") == role_name and isinstance(
                metadata.get("element"), str
            ):
                return metadata["element"]

    try:
        data = json.loads(
            Path(f"{json_path}/characters.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, TypeError, ValueError):
        data = {}
    if isinstance(data, Mapping):
        for metadata in data.values():
            if not isinstance(metadata, Mapping):
                continue
            if metadata.get("name") == role_name and isinstance(
                metadata.get("element"), str
            ):
                return metadata["element"]
    raise ValueError(f"未找到角色{role_name}的星铁元素元数据")


def _weapon_star(value: object) -> int:
    try:
        star = int(value)
    except (TypeError, ValueError):
        return 1
    return star if 1 <= star <= 5 else 1


async def draw_role_rank_card(
    title: str,
    role_name: str,
    group_id: int,
    entries: list[RankEntry],
    plugin_version: str,
    metric: str = "评分",
) -> Image.Image:
    if metric not in {"评分", "伤害"}:
        raise ValueError(f"星铁排行不支持{metric}排行")
    entries = entries[:16]
    boundary = (70, 130)
    interval_y = 15
    mask_bottom = load_image(
        path=f"{other_path}/底遮罩.png",
        crop=(707, 936, 1024, 1370),
        mode="RGBA",
    )
    mask_w, mask_h = mask_bottom.size
    rows = max(1, (len(entries) + 3) // 4)
    width = boundary[0] * 2 + mask_w * 4
    height = boundary[1] * 2 + mask_h * rows + interval_y * (rows - 1) - 50
    background = load_image(
        f"{bg_path}/背景_{_role_element(role_name)}.png",
        size=(width, height),
        mode="RGBA",
    )
    draw = ImageDraw.Draw(background)
    weapon_backgrounds: dict[int, Image.Image] = {}
    weapon_icons: dict[str, Image.Image] = {}

    for index, entry in enumerate(entries):
        x = boundary[0] + mask_w * (index % 4)
        y = boundary[1] + (mask_h + interval_y) * (index // 4)
        background.alpha_composite(mask_bottom, (x, y))
        try:
            avatar = await draw_qq_logo_mask({"QQ": entry["qq"]}, mask_bottom)
            background.alpha_composite(avatar, (x, y))
        except Exception:
            pass

        draw_right_text(
            draw,
            f"#{index + 1}",
            x + mask_w - 18,
            y + 18,
            "#ffde6b",
            get_font(28, "number.ttf"),
        )
        nickname, nickname_font = _fit_text(
            draw,
            str(entry.get("nickname", entry["qq"])),
            mask_w - 105,
            38,
        )
        draw.text((x + 24, y + 16), nickname, fill="white", font=nickname_font)

        metric_font = get_font(28)
        draw.text((x + 24, y + 63), metric, fill="#ffde6b", font=metric_font)
        value_text = (
            f"{float(entry['value']):,.1f}"
            if metric == "评分"
            else f"{float(entry['value']):,.0f}"
        )
        value_x = x + 24 + int(draw.textlength(metric, font=metric_font)) + 8
        value_font = _fit_font(
            draw,
            value_text,
            x + 194 - value_x,
            30,
            minimum=12,
            font_name="number.ttf",
        )
        draw.text((value_x, y + 63), value_text, fill="#ffde6b", font=value_font)

        weapon = entry.get("weapon", {})
        if isinstance(weapon, Mapping) and weapon:
            star = _weapon_star(weapon.get("星级", 1))
            if star not in weapon_backgrounds:
                weapon_backgrounds[star] = load_image(
                    f"{other_path}/star{star}.png",
                    size=(100, 100),
                    mode="RGBA",
                )
            background.alpha_composite(
                weapon_backgrounds[star],
                (x + 200, y + 67),
            )
            icon_name = weapon.get("图标", "")
            if isinstance(icon_name, str) and icon_name:
                if icon_name not in weapon_icons:
                    try:
                        weapon_icons[icon_name] = await get_img(
                            url=weapon_url.format(icon_name),
                            size=(100, 100),
                            save_path=f"{weapon_path}/{icon_name}.png",
                            mode="RGBA",
                        )
                    except Exception:
                        pass
                if icon := weapon_icons.get(icon_name):
                    background.alpha_composite(icon, (x + 200, y + 67))
        level_mask = load_image(
            path=f"{other_path}/等级遮罩.png",
            size=(98, 30),
            mode="RGBA",
        )
        background.alpha_composite(level_mask, (x + 24, y + 112))
        draw_center_text(
            draw,
            f"星魂{entry.get('rank', 0)}",
            x + 24,
            x + 122,
            y + 113,
            "black",
            _fit_font(draw, f"星魂{entry.get('rank', 0)}", 98, 27, minimum=14),
        )

        for row_index, (label, row_value) in enumerate(entry.get("rows", ())):
            row_y = y + 183 + row_index * 52
            label = str(label)
            row_value = str(row_value)
            draw.text(
                (x + 24, row_y),
                label,
                fill="#dfdfdf",
                font=_fit_font(draw, label, 130, 25),
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
        title,
        width - 100,
        96,
        minimum=36,
        font_name="优设标题黑.ttf",
    )
    draw_center_text(draw, title, 0, width, 5, "white", title_font)
    if metric == "伤害":
        damage_titles = list(
            dict.fromkeys(
                str(entry["damage_title"])
                for entry in entries
                if entry.get("damage_title")
            )
        )
        footer = f"group:{group_id} | {'/'.join(damage_titles) or '未知项目'} | v{plugin_version}"
    else:
        footer = f"group:{group_id} | v{plugin_version}"
    footer, footer_font = _fit_text(
        draw,
        footer,
        width - 100,
        46,
        minimum=24,
        font_name="优设标题黑.ttf",
    )
    draw_center_text(draw, footer, 0, width, height - 70, "white", footer_font)
    return background.convert("RGB")
