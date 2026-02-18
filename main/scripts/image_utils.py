#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import logging
from io import BytesIO
from typing import Tuple, List, Sequence, Optional
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def fast_blend_colors(fg: Sequence[int], bg: Sequence[int], alpha: float) -> tuple[int, int, int]:
    """计算前景色与背景色的叠加结果"""
    inv_alpha = 1.0 - alpha
    return (
        int(fg[0] * alpha + bg[0] * inv_alpha),
        int(fg[1] * alpha + bg[1] * inv_alpha),
        int(fg[2] * alpha + bg[2] * inv_alpha)
    )


def normalize_color(color) -> tuple[int, int, int, int]:
    """标准化颜色格式，确保返回 RGBA 元组"""
    if isinstance(color, int):
        c = int(color)
        return (c, c, c, 255)
    elif isinstance(color, (list, tuple)):
        if len(color) == 3:
            return (int(color[0]), int(color[1]), int(color[2]), 255)
        elif len(color) == 4:
            return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))
        else:
            raise ValueError(f"无效的颜色格式: {color}")
    else:
        raise ValueError(f"不支持的颜色类型: {type(color)}")


def get_random_color() -> tuple[int, int, int, int]:
    """生成随机颜色"""
    return (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        255
    )


def parse_color_list(color_str: str) -> List[Tuple[int, int, int, int]]:
    """解析颜色字符串为颜色列表"""
    colors = []
    if not color_str:
        return colors

    for color_part in color_str.split(';'):
        parts = color_part.split(',')
        if len(parts) >= 3:
            r = int(parts[0].strip())
            g = int(parts[1].strip())
            b = int(parts[2].strip())
            a = int(parts[3].strip()) if len(parts) >= 4 else 255
            colors.append((r, g, b, a))

    return colors


def precompute_blend_colors(cfg, bg_colors: list) -> tuple[dict, dict]:
    """预计算所有可能的混合颜色"""
    alpha = cfg.middle_font_color[3] / 255
    fg = tuple(int(c) for c in cfg.middle_font_color[:3])
    overlay_alpha = alpha * 0.5

    blend_cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    overlay_cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}

    for bg_color in bg_colors:
        normalized_bg = normalize_color(bg_color)
        key = (int(normalized_bg[0]), int(normalized_bg[1]), int(normalized_bg[2]))

        blend_cache[key] = fast_blend_colors(fg, key, alpha)
        overlay_cache[key] = fast_blend_colors(fg, key, overlay_alpha)

    return blend_cache, overlay_cache


def calculate_lines_needed(text: str, max_width: int, font: ImageFont.FreeTypeFont) -> int:
    """计算文本需要多少行才能适应指定宽度"""
    temp_img = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)

    words = text.split()
    current_line_width = 0
    lines = 1

    for word in words:
        bbox = temp_draw.textbbox((0, 0), word + ' ', font=font)
        word_width = bbox[2] - bbox[0]

        if current_line_width + word_width > max_width:
            lines += 1
            current_line_width = word_width
        else:
            current_line_width += word_width

    return lines


def render_info_text_simple(
        draw: ImageDraw.Draw,
        text: str,
        start_x: int,
        start_y: int,
        max_width: int,
        line_height: int,
        base_font: ImageFont.FreeTypeFont,
        fg_color: Tuple[int, int, int]
) -> int:
    """简单渲染多行文本，自动换行"""
    x = start_x
    y = start_y

    words = text.split()
    for word in words:
        word_with_space = word + ' '
        bbox = draw.textbbox((0, 0), word_with_space, font=base_font)
        word_width = bbox[2] - bbox[0]

        if x + word_width > start_x + max_width:
            x = start_x
            y += line_height

        draw.text((x, y), word_with_space, font=base_font, fill=fg_color)
        x += word_width

    return y


def render_vertical_progress_bar(
        draw: ImageDraw.Draw,
        x: int,
        y_start: int,
        y_end: int,
        width: int,
        progress: float,
        fg_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int],
        is_left: bool = True
) -> None:
    """渲染竖进度条"""
    height = y_end - y_start
    if width <= 0 or height <= 0:
        return

    try:
        # 绘制背景边框
        draw.rectangle([x, y_start, x + width, y_end], outline=fg_color, width=1)

        # 绘制进度
        if progress > 0:
            fill_height = int(height * progress)
            if fill_height > 0:
                fill_y2 = y_end
                fill_y1 = y_end - fill_height

                # 确保填充矩形有效
                if fill_y1 < y_end:
                    # 填充内部区域，留出边框宽度
                    if fill_height > 2:
                        draw.rectangle([x + 1, fill_y1, x + width - 1, fill_y2 - 1], fill=fg_color)
    except Exception as e:
        logging.debug(f"竖进度条渲染错误: {e}")


def render_progress_bar(
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        width: int,
        height: int,
        progress: float,
        fg_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int]
) -> None:
    """渲染水平进度条（保留原函数）"""
    if width <= 0 or height <= 0:
        return

    try:
        draw.rectangle([x, y, x + width, y + height], outline=fg_color, width=1)

        if progress > 0:
            fill_width = int(width * progress)
            if fill_width > 0:
                fill_x2 = x + fill_width
                if fill_x2 > x:
                    if fill_width > 2:
                        draw.rectangle([x + 1, y + 1, fill_x2 - 1, y + height - 1], fill=fg_color)
    except Exception as e:
        logging.debug(f"进度条渲染错误: {e}")


def render_spinner_string_at_bottom(
        draw: ImageDraw.Draw,
        spinner_strings: List[str],
        step: int,
        start_x: int,
        end_x: int,
        y: int,
        font: ImageFont.FreeTypeFont,
        color: Tuple[int, int, int]
) -> None:
    """
    在底部正中渲染转圈圈字符串（在多个完整字符串之间切换）

    Args:
        draw: ImageDraw对象
        spinner_strings: 转圈字符串列表，每个元素是一个完整的字符串
        step: 当前步数，决定显示哪个字符串
        start_x: 区域起始X坐标
        end_x: 区域结束X坐标
        y: Y坐标
        font: 字体
        color: 颜色
    """
    if not spinner_strings:
        return

    # 获取当前要显示的字符串
    current_string = spinner_strings[step % len(spinner_strings)]

    # 计算字符串的宽度
    bbox = draw.textbbox((0, 0), current_string, font=font)
    string_width = bbox[2] - bbox[0]
    string_height = bbox[3] - bbox[1]

    # 计算起始X坐标使字符串居中
    region_width = end_x - start_x
    string_x = start_x + (region_width - string_width) // 2

    # 确保不超出区域
    if string_x < start_x:
        string_x = start_x

    # 计算Y坐标使字符串垂直居中
    string_y = y - string_height // 2

    # 绘制字符串
    draw.text((string_x, string_y), current_string, font=font, fill=color)


def check_bounds_with_padding(x: int, y: int, width: int, height: int,
                              padding: int, canvas_width: int, canvas_height: int) -> Tuple[int, int]:
    """检查并调整坐标，确保元素在画布内（考虑边距）"""
    if width <= 0 or height <= 0:
        return x, y

    if x + width > canvas_width - padding:
        x = canvas_width - padding - width
    if x < padding:
        x = padding
    if y + height > canvas_height - padding:
        y = canvas_height - padding - height
    if y < padding:
        y = padding

    return x, y


def truncate_text_to_width(draw: ImageDraw.Draw, text: str, max_width: int,
                           font: ImageFont.FreeTypeFont) -> str:
    """截断文本以适应指定宽度"""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    if text_width <= max_width:
        return text

    # 尝试截断
    text_body = text
    while True:
        if len(text_body) <= 4:
            text_body = text_body[:4]
            return text_body
        keep = max(1, len(text_body) - 6)
        candidate = '...' + text_body[-keep:]
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            return candidate
        text_body = text_body[1:]