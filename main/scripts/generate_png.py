#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import logging
import argparse
import random
import colorsys
import math
import re
import struct
from pathlib import Path
from threading import Thread
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import Sequence, List, Tuple, Optional, Dict, Set

sys.path.insert(0, os.path.dirname(__file__))

from control_map import get_char, CTRLS
from Module import (
    Config, UnicodeEntry, ColorManager, load_unicode_entries, setup_logging,
    ColorGradient, PositionAnimator, NamesListParser, PrecomputedValues, ScaledConfig,
    load_unicode_blocks, find_block_name, find_block_index, load_unicode_names,
    load_combining_marks, build_block_index_mapping, get_utf8_encoding,
    get_utf16le_encoding, get_utf16be_encoding, fast_blend_colors, normalize_color,
    get_random_color, parse_color_list, precompute_blend_colors, calculate_lines_needed,
    render_info_text_simple, render_vertical_progress_bar, render_spinner_string_at_bottom,
    check_bounds_with_padding, truncate_text_to_width, preload_middle_fonts,
    get_font_display_name, write_batch, optimized_writer_thread_fn,
    create_filename_mapping, parse_content_position
)

from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

Image.MAX_IMAGE_PIXELS = None


def generate_image_bytes(
        entry: UnicodeEntry,
        cfg: Config,
        color_mgr: ColorManager | None,
        bottom_font: ImageFont.FreeTypeFont,
        ctrl_font: ImageFont.FreeTypeFont,
        middle_font_cache: dict[Path, ImageFont.FreeTypeFont | None],
        metrics_cache: dict[Path, tuple[int, int]],
        text_cache: dict[str, tuple[int, int]],
        precomputed: PrecomputedValues,
        blend_cache: dict[tuple, tuple[int, int, int]],
        overlay_cache: dict[tuple, tuple[int, int, int]],
        overlay_enabled: bool,
        combining_cps: set[int],
        overlay_bbox_cache: dict[str, tuple[int, int]],
        blocks: list[tuple[int, int, str]],
        unicode_names: dict[int, str],
        names_list_parser: NamesListParser,
        random_color: bool = False,
        filename_mapping: dict[str, str] = None,
        gradient_manager: Optional[ColorGradient] = None,
        gradient_index: int = 0,
        gradient_total: int = 1,
        flash_color: Optional[Tuple[int, int, int, int]] = None,
        position_animator: Optional[PositionAnimator] = None,
        animated_elements: List[str] = None,
        content_position_random: bool = False,
        content_position_fixed: Optional[Tuple[int, int]] = None,
        show_names_info: bool = False,
        use_smooth_gradient: bool = True,
        show_encoding: bool = False,
        show_block_position: bool = False,
        show_global_position: bool = False,
        show_block_progress_bar: bool = False,
        show_global_progress_bar: bool = False,
        show_side_spinner: bool = False,
        spinner_step: int = 0,
        spinner_strings: List[str] = None,
        global_index: int = 0,
        total_entries: int = 0,
        total_in_block: int = 0,
        index_in_block: int = 0,
        scale_factor: float = 1.0,
        style: str = 'compare',
        font_paths: List[str] = None,
        font_index: int = 0,
        total_fonts: int = 1,
        font_name: str = '',
) -> tuple[bytes, Path, str | None]:
    try:
        cp = int(entry.code_str.strip()[2:], 16)
    except:
        raise ValueError(f"无效的 code_str: {entry.code_str!r}")

    char = get_char(cp)
    is_control = (cp in CTRLS)

    if font_paths is None:
        font_paths = [entry.font_path]
    is_multi_font = (len(font_paths) > 1) and (style == 'compare')

    if flash_color:
        bg_color = flash_color
    elif gradient_manager:
        if use_smooth_gradient:
            bg_color = gradient_manager.get_smooth_gradient_color(gradient_index)
        else:
            bg_color = gradient_manager.get_gradient_color(gradient_index)
    elif random_color:
        bg_color = get_random_color()
    elif color_mgr is not None:
        bg_color_raw = color_mgr.get_color(entry.description)
        bg_color = normalize_color(bg_color_raw)
    else:
        bg_color = normalize_color(cfg.background_color)

    img = Image.new('RGBA', cfg.image_size, bg_color)
    draw = ImageDraw.Draw(img)

    bg_key = tuple(bg_color[:3])
    if bg_key in blend_cache:
        blended = blend_cache[bg_key]
    else:
        blended = fast_blend_colors(precomputed.fg_color, bg_key, precomputed.alpha)
        if not random_color and not gradient_manager and not flash_color:
            blend_cache[bg_key] = blended

    if is_multi_font:
        num_fonts = len(font_paths)
        precomputed.multi_font_total_width = num_fonts * precomputed.multi_font_slot_width + (num_fonts - 1) * precomputed.multi_font_spacing
        total_width = precomputed.multi_font_total_width
        start_x = (precomputed.W - total_width) // 2
        current_x = start_x

        for i, font_path_str in enumerate(font_paths):
            font_path = None
            font = None
            font_key = None

            direct_path = Path(font_path_str)
            if direct_path.exists():
                font_path = direct_path
            else:
                for p in cfg.font_files:
                    if p.name == font_path_str or str(p) == font_path_str:
                        font_path = p
                        break
                if font_path is None:
                    cwd_path = Path.cwd() / font_path_str
                    if cwd_path.exists():
                        font_path = cwd_path
                if font_path is None:
                    script_dir = Path(__file__).parent
                    script_path = script_dir / font_path_str
                    if script_path.exists():
                        font_path = script_path
                if font_path is None:
                    main_dir = Path.cwd() / 'main'
                    main_path = main_dir / font_path_str
                    if main_path.exists():
                        font_path = main_path

            if font_path and font_path in middle_font_cache:
                font = middle_font_cache[font_path]
                font_key = font_path
            elif font_path:
                try:
                    font = ImageFont.truetype(str(font_path), cfg.middle_font_size)
                    middle_font_cache[font_path] = font
                    font_key = font_path
                except Exception as e:
                    logging.warning(f"加载字体失败 {font_path}: {e}")
                    font = None

            if not font:
                for p in cfg.font_files:
                    f = middle_font_cache.get(p)
                    if f:
                        font = f
                        font_key = p
                        break

            if not font:
                font = ImageFont.load_default()
                font_key = 'default'

            if is_control:
                font = ctrl_font
                font_key = 'ctrl'

            if font_key in metrics_cache:
                ascent, descent = metrics_cache[font_key]
            else:
                ascent, descent = font.getmetrics()
                if font_key != 'default':
                    metrics_cache[font_key] = (ascent, descent)

            baseline_y = int(precomputed.center_y + (ascent - descent) / 2) + precomputed.baseline_offset

            final_text_x_offset = precomputed.text_x_offset
            final_baseline_offset = precomputed.baseline_offset

            if content_position_random:
                final_text_x_offset = random.randint(-200, 200)
                final_baseline_offset = random.randint(-100, 100)
            elif content_position_fixed:
                final_text_x_offset, final_baseline_offset = content_position_fixed

            anim_x, anim_y = 0, 0
            if position_animator and animated_elements and 'content' in animated_elements:
                anim_x, anim_y = position_animator.get_position_offset(
                    gradient_index + i * 10, 0, 0, 'content'
                )
                final_text_x_offset += anim_x
                final_baseline_offset += anim_y

            baseline_y = int(precomputed.center_y + (ascent - descent) / 2) + final_baseline_offset

            if hasattr(font, 'path'):
                cache_key = f"{char}_{font.path}_{font.size}"
            else:
                cache_key = f"{char}_{font_key}_{cfg.middle_font_size}"

            if cache_key in text_cache:
                w, h = text_cache[cache_key]
            else:
                bbox = draw.textbbox((0, 0), char, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                w = max(1, w)
                h = max(1, h)
                text_cache[cache_key] = (int(w), int(h))

            x = current_x + (precomputed.multi_font_slot_width - w) // 2
            y = baseline_y - ascent

            x, y = check_bounds_with_padding(x, y, w, h, precomputed.padding, precomputed.W, precomputed.H)

            if overlay_enabled and cp in combining_cps:
                overlay_char = '\u25CC'
                overlay_cache_key = f"{overlay_char}_{font_key}_{cfg.middle_font_size}"
                if overlay_cache_key in overlay_bbox_cache:
                    ow, oh = overlay_bbox_cache[overlay_cache_key]
                else:
                    obbox = draw.textbbox((0, 0), overlay_char, font=ctrl_font)
                    ow = obbox[2] - obbox[0]
                    oh = obbox[3] - obbox[1]
                    ow = max(1, ow)
                    oh = max(1, oh)
                    overlay_bbox_cache[overlay_cache_key] = (int(ow), int(oh))

                if bg_key in overlay_cache:
                    overlay_color = overlay_cache[bg_key]
                else:
                    overlay_color = fast_blend_colors(precomputed.fg_color, bg_color, precomputed.overlay_alpha)
                    if not random_color and not gradient_manager and not flash_color:
                        overlay_cache[bg_key] = overlay_color

                ox = current_x + (precomputed.multi_font_slot_width - ow) // 2
                oy = baseline_y - ascent
                ox, oy = check_bounds_with_padding(ox, oy, ow, oh, precomputed.padding, precomputed.W, precomputed.H)
                draw.text((ox, oy), overlay_char, font=ctrl_font, fill=overlay_color)

            draw.text((x, y), char, font=font, fill=blended)

            current_x += precomputed.multi_font_slot_width + precomputed.multi_font_spacing

        main_char_right_edge = start_x + total_width
    else:
        font_path_str = font_paths[0] if font_paths else str(cfg.font_files[0])
        font_path = Path(font_path_str)
        middle_font = middle_font_cache.get(font_path)
        font_path_key = font_path
        if not middle_font:
            try:
                middle_font = ImageFont.truetype(str(font_path), cfg.middle_font_size)
                middle_font_cache[font_path] = middle_font
                metrics_cache[font_path] = middle_font.getmetrics()
            except Exception as e:
                logging.debug(f"直接加载字体失败 {font_path}: {e}")
                middle_font = None
        if not middle_font:
            for p in cfg.font_files:
                f = middle_font_cache.get(p)
                if f:
                    middle_font = f
                    font_path_key = p
                    break

        if not middle_font:
            char = "无法加载字体：" + char
            middle_font = ImageFont.load_default()
            font_path_key = 'default'

        if is_control:
            middle_font = ctrl_font
            font_path_key = 'ctrl'

        if font_path_key in metrics_cache:
            ascent, descent = metrics_cache[font_path_key]
        else:
            ascent, descent = middle_font.getmetrics()
            if font_path_key != 'default':
                metrics_cache[font_path_key] = (ascent, descent)

        baseline_y = int(precomputed.center_y + (ascent - descent) / 2) + precomputed.baseline_offset

        final_text_x_offset = precomputed.text_x_offset
        final_baseline_offset = precomputed.baseline_offset

        if content_position_random:
            final_text_x_offset = random.randint(-200, 200)
            final_baseline_offset = random.randint(-100, 100)
        elif content_position_fixed:
            final_text_x_offset, final_baseline_offset = content_position_fixed

        anim_x, anim_y = 0, 0
        if position_animator and animated_elements and 'content' in animated_elements:
            anim_x, anim_y = position_animator.get_position_offset(
                gradient_index, 0, 0, 'content'
            )
            final_text_x_offset += anim_x
            final_baseline_offset += anim_y

        baseline_y = int(precomputed.center_y + (ascent - descent) / 2) + final_baseline_offset

        if hasattr(middle_font, 'path'):
            cache_key = f"{char}_{middle_font.path}_{middle_font.size}"
        else:
            cache_key = f"{char}_{font_path_key}_{cfg.middle_font_size}"

        if cache_key in text_cache:
            w, h = text_cache[cache_key]
        else:
            bbox = draw.textbbox((0, 0), char, font=middle_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            w = max(1, w)
            h = max(1, h)
            text_cache[cache_key] = (int(w), int(h))

        x = (precomputed.W - w) // 2 + final_text_x_offset
        y = baseline_y - ascent

        x, y = check_bounds_with_padding(x, y, w, h, precomputed.padding, precomputed.W, precomputed.H)

        main_char_right_edge = x + w

        if overlay_enabled and cp in combining_cps:
            overlay_char = '\u25CC'
            overlay_cache_key = f"{overlay_char}_{font_path_key}_{cfg.middle_font_size}"
            if overlay_cache_key in overlay_bbox_cache:
                ow, oh = overlay_bbox_cache[overlay_cache_key]
            else:
                obbox = draw.textbbox((0, 0), overlay_char, font=ctrl_font)
                ow = obbox[2] - obbox[0]
                oh = obbox[3] - obbox[1]
                ow = max(1, ow)
                oh = max(1, oh)
                overlay_bbox_cache[overlay_cache_key] = (int(ow), int(oh))

            if bg_key in overlay_cache:
                overlay_color = overlay_cache[bg_key]
            else:
                overlay_color = fast_blend_colors(precomputed.fg_color, bg_color, precomputed.overlay_alpha)
                if not random_color and not gradient_manager and not flash_color:
                    overlay_cache[bg_key] = overlay_color

            ox = (precomputed.W - ow) // 2 + final_text_x_offset
            oy = baseline_y - ascent
            ox, oy = check_bounds_with_padding(ox, oy, ow, oh, precomputed.padding, precomputed.W, precomputed.H)
            draw.text((ox, oy), overlay_char, font=ctrl_font, fill=overlay_color)

        draw.text((x, y), char, font=middle_font, fill=blended)

    code_text = entry.code_str
    top_left_x, top_left_y = precomputed.top_left

    code_bbox = draw.textbbox((0, 0), code_text, font=bottom_font)
    code_w = code_bbox[2] - code_bbox[0]
    code_h = code_bbox[3] - code_bbox[1]
    code_w = max(1, code_w)
    code_h = max(1, code_h)

    if position_animator and animated_elements and 'code' in animated_elements:
        top_left_x, top_left_y = position_animator.get_position_offset(
            gradient_index, top_left_x, top_left_y, 'code'
        )

    top_left_x, top_left_y = check_bounds_with_padding(
        top_left_x, top_left_y, code_w, code_h,
        precomputed.padding, precomputed.W, precomputed.H
    )

    draw.text((top_left_x, top_left_y), code_text, font=bottom_font, fill=blended)

    if show_global_position and total_entries > 0:
        global_position_text = f"{global_index + 1}/{total_entries}"
        global_position_y = top_left_y + code_h + precomputed.line_spacing

        if position_animator and animated_elements and 'code' in animated_elements:
            global_position_y += position_animator.get_position_offset(gradient_index, 0, 0, 'code')[1]

        if global_position_y + code_h < precomputed.H - precomputed.padding:
            draw.text((top_left_x, global_position_y), global_position_text, font=bottom_font, fill=blended)

    name_text = ''
    if unicode_names and cp in unicode_names:
        name_text = unicode_names[cp]
    else:
        name_text = (entry.description.split('|', 1)[0].strip() if entry.description else '')

    if name_text:
        name_bbox = draw.textbbox((0, 0), name_text, font=bottom_font)
        name_w = name_bbox[2] - name_bbox[0]
        name_h = name_bbox[3] - name_bbox[1]
        name_w = max(1, name_w)
        name_h = max(1, name_h)
        name_x = precomputed.top_right_x - name_w
        name_y = precomputed.top_y

        if position_animator and animated_elements and 'name' in animated_elements:
            name_x, name_y = position_animator.get_position_offset(
                gradient_index, name_x, name_y, 'name'
            )

        name_x, name_y = check_bounds_with_padding(
            name_x, name_y, name_w, name_h,
            precomputed.padding, precomputed.W, precomputed.H
        )

        draw.text((name_x, name_y), name_text, font=bottom_font, fill=blended)

        if show_block_position and total_in_block > 0 and index_in_block > 0:
            block_position_text = f"{index_in_block}/{total_in_block}"
            block_pos_bbox = draw.textbbox((0, 0), block_position_text, font=bottom_font)
            block_pos_w = block_pos_bbox[2] - block_pos_bbox[0]
            block_pos_h = block_pos_bbox[3] - block_pos_bbox[1]

            block_pos_x = precomputed.top_right_x - block_pos_w
            block_pos_y = name_y + name_h + precomputed.line_spacing

            if position_animator and animated_elements and 'name' in animated_elements:
                block_pos_y += position_animator.get_position_offset(gradient_index, 0, 0, 'name')[1]

            if block_pos_y + block_pos_h < precomputed.H - precomputed.padding and block_pos_x >= precomputed.padding:
                draw.text((block_pos_x, block_pos_y), block_position_text, font=bottom_font, fill=blended)

    if show_encoding:
        utf8_text = f"UTF-8: {get_utf8_encoding(cp)}"
        utf16le_text = f"UTF-16LE: {get_utf16le_encoding(cp)}"
        utf16be_text = f"UTF-16BE: {get_utf16be_encoding(cp)}"

        encoding_y = precomputed.encoding_y

        utf8_bbox = draw.textbbox((0, 0), utf8_text, font=bottom_font)
        utf16le_bbox = draw.textbbox((0, 0), utf16le_text, font=bottom_font)
        utf16be_bbox = draw.textbbox((0, 0), utf16be_text, font=bottom_font)

        max_width = max(
            utf8_bbox[2] - utf8_bbox[0],
            utf16le_bbox[2] - utf16le_bbox[0],
            utf16be_bbox[2] - utf16be_bbox[0]
        )

        encoding_x = (precomputed.W - max_width) // 2
        total_height = precomputed.encoding_line_height * 3

        if encoding_y + total_height < precomputed.center_y - precomputed.middle_font_size:
            draw.text((encoding_x, encoding_y), utf8_text, font=bottom_font, fill=blended)
            draw.text((encoding_x, encoding_y + precomputed.encoding_line_height), utf16le_text, font=bottom_font, fill=blended)
            draw.text((encoding_x, encoding_y + precomputed.encoding_line_height * 2), utf16be_text, font=bottom_font, fill=blended)

    if is_multi_font:
        font_display_names = [Path(p).name for p in font_paths]
        font_line_count = len(font_display_names)
    else:
        if is_control:
            font_path_key = 'ctrl'
        else:
            font_path_key = Path(font_path_str)
        font_display_names = [get_font_display_name(font_path_key, cfg)]
        font_line_count = 1

    base_font_y = precomputed.font_name_y
    line_height = precomputed.bottom_font_size + precomputed.line_spacing

    for i, display_name in enumerate(font_display_names):
        max_w = precomputed.W // 3
        fname = truncate_text_to_width(draw, display_name, max_w, bottom_font)
        font_name_x = precomputed.padding
        current_font_y = base_font_y - i * line_height

        if position_animator and animated_elements and 'font' in animated_elements:
            anim_offset = position_animator.get_position_offset(
                gradient_index + i * 5, 0, 0, 'font'
            )
            font_name_x += anim_offset[0]
            current_font_y += anim_offset[1]

        if current_font_y >= precomputed.padding:
            draw.text((font_name_x, current_font_y), fname, font=bottom_font, fill=blended)

    top_font_y = base_font_y - (font_line_count - 1) * line_height
    block_name_y = top_font_y - precomputed.bottom_font_size - precomputed.line_spacing
    block_name_x = precomputed.block_name_pos[0]

    block_name = find_block_name(cp, blocks) if blocks else 'No_Block'
    block_bbox = draw.textbbox((0, 0), block_name, font=bottom_font)
    block_w = block_bbox[2] - block_bbox[0]
    block_h = block_bbox[3] - block_bbox[1]
    block_w = max(1, block_w)
    block_h = max(1, block_h)

    if position_animator and animated_elements and 'block' in animated_elements:
        block_name_x, block_name_y = position_animator.get_position_offset(
            gradient_index, block_name_x, block_name_y, 'block'
        )

    block_name_x, block_name_y = check_bounds_with_padding(
        block_name_x, block_name_y, block_w, block_h,
        precomputed.padding, precomputed.W, precomputed.H
    )
    draw.text((block_name_x, block_name_y), block_name, font=bottom_font, fill=blended)

    dynamic_progress_end_y = block_name_y - precomputed.line_spacing
    if dynamic_progress_end_y > precomputed.progress_start_y:
        progress_end_y = dynamic_progress_end_y
    else:
        progress_end_y = precomputed.progress_start_y + 10
    progress_actual_height = progress_end_y - precomputed.progress_start_y

    info_start_x = precomputed.W - precomputed.info_max_width - precomputed.padding
    info_height = 0

    if show_names_info:
        info_lines = names_list_parser.get_info_for_code(entry.code_str)
        if info_lines and len(info_lines) > 1:
            if info_start_x < main_char_right_edge + precomputed.element_spacing:
                info_start_x = main_char_right_edge + precomputed.element_spacing

            lines_to_show = []
            total_lines_needed = 0

            for i, line in enumerate(info_lines[1:], 1):
                line = line.strip()
                if not line:
                    continue
                while line.startswith('\t') or line.startswith(' '):
                    line = line[1:]
                if not line:
                    continue
                lines_needed = calculate_lines_needed(line, precomputed.info_max_width, bottom_font)
                total_lines_needed += lines_needed
                lines_to_show.append((line, lines_needed))

            if lines_to_show:
                total_display_height = total_lines_needed * precomputed.info_line_height
                info_height = total_display_height

                start_y = precomputed.info_bottom_y - total_display_height

                if start_y < precomputed.padding:
                    start_y = precomputed.padding
                    max_height = precomputed.info_bottom_y - precomputed.padding
                    max_lines = int(max_height / precomputed.info_line_height)
                    if max_lines > 0:
                        lines_to_show = lines_to_show[:max_lines]
                        total_display_height = sum(l[1] for l in lines_to_show) * precomputed.info_line_height
                        start_y = precomputed.info_bottom_y - total_display_height

                info_start_x = max(precomputed.padding, min(info_start_x, precomputed.W - precomputed.padding - precomputed.info_max_width))

                current_y = start_y
                for line_text, lines_needed in lines_to_show:
                    end_y = render_info_text_simple(
                        draw=draw,
                        text=line_text,
                        start_x=info_start_x,
                        start_y=current_y,
                        max_width=precomputed.info_max_width,
                        line_height=precomputed.info_line_height,
                        base_font=bottom_font,
                        fg_color=blended
                    )
                    current_y = end_y + precomputed.info_line_height

    if show_block_progress_bar or show_global_progress_bar:
        block_progress_val = index_in_block / total_in_block if total_in_block > 0 else 0
        global_progress_val = (global_index + 1) / total_entries if total_entries > 0 else 0

        if show_block_progress_bar and total_in_block > 0 and index_in_block > 0:
            render_vertical_progress_bar(
                draw=draw,
                x=precomputed.left_progress_x,
                y_start=precomputed.progress_start_y,
                y_end=progress_end_y,
                width=precomputed.progress_bar_width,
                progress=block_progress_val,
                fg_color=blended,
                bg_color=bg_color[:3],
                is_left=True
            )

            percent_text = f"{block_progress_val * 100:.1f}%"
            percent_x = precomputed.left_progress_x + precomputed.progress_bar_width + precomputed.percent_spacing
            percent_bbox = draw.textbbox((0, 0), percent_text, font=bottom_font)
            percent_height = percent_bbox[3] - percent_bbox[1]

            progress_y = progress_end_y - int(block_progress_val * progress_actual_height)
            percent_y = progress_y - percent_height // 2
            percent_y = max(precomputed.progress_start_y, min(percent_y, progress_end_y - percent_height))

            draw.text((percent_x, percent_y), percent_text, font=bottom_font, fill=blended)

        if show_global_progress_bar and total_entries > 0:
            render_vertical_progress_bar(
                draw=draw,
                x=precomputed.right_progress_x,
                y_start=precomputed.progress_start_y,
                y_end=progress_end_y,
                width=precomputed.progress_bar_width,
                progress=global_progress_val,
                fg_color=blended,
                bg_color=bg_color[:3],
                is_left=False
            )

            percent_text = f"{global_progress_val * 100:.1f}%"
            percent_bbox = draw.textbbox((0, 0), percent_text, font=bottom_font)
            percent_width = percent_bbox[2] - percent_bbox[0]
            percent_height = percent_bbox[3] - percent_bbox[1]

            percent_x = precomputed.right_progress_x - percent_width - precomputed.percent_spacing
            progress_y = progress_end_y - int(global_progress_val * progress_actual_height)
            percent_y = progress_y - percent_height // 2
            percent_y = max(precomputed.progress_start_y, min(percent_y, progress_end_y - percent_height))

            if percent_x >= precomputed.padding:
                draw.text((percent_x, percent_y), percent_text, font=bottom_font, fill=blended)

    if show_side_spinner and spinner_strings:
        spinner_y = top_font_y - precomputed.line_spacing * 2
        render_spinner_string_at_bottom(
            draw=draw,
            spinner_strings=spinner_strings,
            step=spinner_step,
            start_x=precomputed.spinner_start_x,
            end_x=precomputed.spinner_end_x,
            y=spinner_y,
            font=bottom_font,
            color=blended
        )

    buf = BytesIO()
    buf.truncate(50000)
    buf.seek(0)

    img.save(buf, format='PNG',
             compress_level=cfg.png_compress_level,
             optimize=cfg.png_optimize,
             pnginfo=None)
    data = buf.getvalue()

    img.close()
    buf.close()

    if filename_mapping and entry.code_str in filename_mapping:
        base_filename = filename_mapping[entry.code_str]
    else:
        base_filename = entry.code_str

    if style == 'obo' and font_name:
        output_filename = f"image_{base_filename}-{font_name}"
    else:
        output_filename = f"image_{base_filename}"

    out_path = cfg.output_dir / f"{output_filename}.png"
    return data, out_path, None


def parse_args():
    parser = argparse.ArgumentParser(description='Unicode 字符图片生成器')
    parser.add_argument(
        '--dynamic-bg',
        action='store_true',
        help='启用动态背景颜色，默认使用固定背景色'
    )
    parser.add_argument(
        '--random-color',
        action='store_true',
        help='使生成的图片每一张颜色完全随机'
    )
    parser.add_argument(
        '--rainbow-gradient',
        action='store_true',
        help='启用彩虹渐变背景（按文件名顺序平滑渐变）'
    )
    parser.add_argument(
        '--gradient-colors',
        type=str,
        default='',
        help='自定义渐变关键颜色，格式：R,G,B,A;R,G,B,A;...'
    )
    parser.add_argument(
        '--gradient-cycle',
        type=int,
        default=100,
        help='彩虹渐变一轮回需要的图片张数，默认100张'
    )
    parser.add_argument(
        '--smooth-gradient',
        action='store_true',
        default=True,
        help='使用平滑渐变（默认启用），禁用则使用关键颜色插值'
    )
    parser.add_argument(
        '--flash-color',
        type=str,
        default='',
        help='爆闪自定义闪出颜色，格式：R,G,B,A 例如：255,255,255,255（不传则随机）'
    )
    parser.add_argument(
        '--animate-elements',
        type=str,
        default='',
        help='需要动画飘动的信息元素，逗号分隔，可选：code,name,block,font,content'
    )
    parser.add_argument(
        '--animation-type',
        choices=['smooth', 'random_smooth'],
        default='smooth',
        help='动画类型：smooth(平滑正弦), random_smooth(随机平滑)'
    )
    parser.add_argument(
        '--animation-amplitude',
        type=int,
        default=50,
        help='动画飘动幅度（像素）'
    )
    parser.add_argument(
        '--animation-speed',
        type=float,
        default=1.0,
        help='动画颜色变化速度系数（值越大颜色变化越快）'
    )
    parser.add_argument(
        '--movement-speed',
        type=float,
        default=0.1,
        help='飘动动画速度（值越大飘动越快），默认0.1'
    )
    parser.add_argument(
        '--content-position',
        type=str,
        default='',
        help='内容位置：fixed,x,y 或 random 例如：fixed,100,-50 或 random'
    )
    parser.add_argument(
        '--shuffle-content',
        action='store_true',
        help='内容按原顺序生成，但文件名在列表内随机分配'
    )
    parser.add_argument(
        '--show-names-info',
        action='store_true',
        help='在右下角显示NamesList.txt中的信息'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=8,
        help='并发线程数，默认为 8'
    )
    parser.add_argument(
        '--png-quality',
        choices=['fast', 'balanced', 'best'],
        default='balanced',
        help='PNG 压缩质量：fast(速度优先), balanced(平衡), best(质量优先)'
    )
    parser.add_argument(
        '--force',
        '-f',
        action='store_true',
        help='忽略已存在的 PNG，强制重新生成并覆盖'
    )
    parser.add_argument(
        '--disable-comb-overlay',
        action='store_true',
        help='禁用组合类标记(Mn/Mc/Me)的◌覆盖提示'
    )
    parser.add_argument(
        '--show-encoding',
        action='store_true',
        help='在正上方四行垂直居中显示字符的UTF-8、UTF-16LE、UTF-16BE编码（不显示UTF-32）'
    )
    parser.add_argument(
        '--show-block-position',
        action='store_true',
        help='在右上角字符名称下一行显示 [区块内第几个]/[区块总字符数]'
    )
    parser.add_argument(
        '--show-global-position',
        action='store_true',
        help='在左上角字符码位下一行显示 [全局第几个]/[总字符数]'
    )
    parser.add_argument(
        '--show-block-progress-bar',
        action='store_true',
        help='在底部中间显示区块进度条及百分比'
    )
    parser.add_argument(
        '--show-global-progress-bar',
        action='store_true',
        help='在底部中间显示全局进度条及百分比'
    )
    parser.add_argument(
        '--show-side-spinner',
        action='store_true',
        help='在左右两边正中间添加转圈圈式加载条'
    )
    parser.add_argument(
        '--spinner-strings',
        type=str,
        default='-,\\,|,/',
        help='转圈圈使用的字符串列表，用逗号分隔，例如 "-,\\,|,/" 或 "◐,◓,◑,◒" 或 "⣾,⣽,⣻,⢿,⡿,⣟,⣯,⣷"'
    )
    parser.add_argument(
        '--spinner-step-interval',
        type=int,
        default=1,
        help='每隔几张图片切换一次转圈圈字符串，默认1'
    )
    parser.add_argument(
        '--scale',
        type=float,
        default=1.0,
        help='分辨率及所有字号、边距的等比缩放因子，例如 0.5 缩小一半，2.0 放大一倍'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed()
    setup_logging()

    spinner_strings = [s.strip() for s in args.spinner_strings.split(',')]
    logging.info(f"转圈字符串列表: {spinner_strings}")

    base_cfg = Config()
    scale_factor = args.scale
    if scale_factor <= 0:
        logging.error("缩放因子必须大于0，使用默认值1.0")
        scale_factor = 1.0

    cfg = ScaledConfig(base_cfg, scale_factor)
    cfg.output_dir.mkdir(exist_ok=True)

    if args.png_quality == 'fast':
        cfg.png_compress_level, cfg.png_optimize = 1, False
    elif args.png_quality == 'balanced':
        cfg.png_compress_level, cfg.png_optimize = 2, False
    else:
        cfg.png_compress_level, cfg.png_optimize = 6, True

    existing_files = {p.stem for p in cfg.output_dir.glob('*.png') if p.stat().st_size >= 1000}

    entries = load_unicode_entries(cfg.unicode_file)
    total_entries = len(entries)

    filename_mapping = None
    if args.shuffle_content:
        logging.info("应用文件名随机化：内容按原顺序生成，但文件名随机分配")
        filename_mapping = create_filename_mapping(entries)

    # 解析每个条目的字体列表，并判断模式
    to_process = []
    for e in entries:
        if ':' in e.font_path:
            all_font_paths = e.font_path.split(':')
            style = 'obo'
        elif '|' in e.font_path:
            all_font_paths = e.font_path.split('|')
            style = 'compare'
        else:
            all_font_paths = [e.font_path]
            style = 'single'

        all_exist = True
        if style == 'obo':
            base = filename_mapping.get(e.code_str, e.code_str) if filename_mapping else e.code_str
            for font_file in [Path(p).name for p in all_font_paths]:
                fname = f"image_{base}-{font_file}"
                if fname not in existing_files:
                    all_exist = False
                    break
        else:
            base = filename_mapping.get(e.code_str, e.code_str) if filename_mapping else e.code_str
            fname = f"image_{base}"
            if fname not in existing_files:
                all_exist = False

        if args.force or not all_exist:
            to_process.append((e, all_font_paths, style))

    if not to_process:
        logging.info("所有图片已存在，无需生成")
        return

    unicode_data_path = Path.cwd() / 'UnicodeData.txt'
    if unicode_data_path.exists():
        combining_cps = load_combining_marks(unicode_data_path)
        logging.info(f"加载 {len(combining_cps)} 个组合标记")
        unicode_names = load_unicode_names(unicode_data_path)
    else:
        combining_cps = set()
        unicode_names = {}
        logging.warning("UnicodeData.txt 未找到，组合 overlay 无效")

    overlay_enabled = not args.disable_comb_overlay

    blocks_path = Path.cwd() / 'UnicodeBlocks.txt'
    if blocks_path.exists():
        blocks = load_unicode_blocks(blocks_path)
        logging.info(f"加载 {len(blocks)} 个 Unicode blocks")
        block_index_mapping = build_block_index_mapping(blocks, entries)
    else:
        blocks = []
        block_index_mapping = {}
        logging.warning("UnicodeBlocks.txt 未找到，区块名称显示为 No_Block")

    names_list_path = Path.cwd() / 'NamesList.txt'
    names_list_parser = NamesListParser(names_list_path)

    gradient_manager = None
    if args.rainbow_gradient:
        if args.gradient_colors:
            key_colors = parse_color_list(args.gradient_colors)
            if key_colors:
                gradient_manager = ColorGradient(key_colors, args.gradient_cycle)
                logging.info(f"使用自定义渐变颜色: {len(key_colors)} 个关键色，{args.gradient_cycle}张一轮回")
            else:
                gradient_manager = ColorGradient(cycle_length=args.gradient_cycle)
                logging.info(f"使用默认彩虹渐变，{args.gradient_cycle}张一轮回")
        else:
            gradient_manager = ColorGradient(cycle_length=args.gradient_cycle)
            logging.info(f"使用默认彩虹渐变，{args.gradient_cycle}张一轮回")

        if args.smooth_gradient:
            logging.info("使用平滑渐变（HSV色彩空间）")
        else:
            logging.info("使用关键颜色插值渐变")

    flash_color = None
    if args.flash_color:
        colors = parse_color_list(args.flash_color)
        if colors:
            flash_color = colors[0]
            logging.info(f"使用闪出颜色: R={flash_color[0]}, G={flash_color[1]}, B={flash_color[2]}, A={flash_color[3]}")
        else:
            flash_color = get_random_color()
            logging.info("使用随机闪出颜色")
    elif args.flash_color == '' and (args.random_color or args.dynamic_bg or args.rainbow_gradient):
        pass
    else:
        flash_color = get_random_color()
        logging.info("使用随机闪出颜色")

    animated_elements = []
    if args.animate_elements:
        animated_elements = [elem.strip() for elem in args.animate_elements.split(',')]
        valid_elements = ['code', 'name', 'block', 'font', 'content']
        animated_elements = [elem for elem in animated_elements if elem in valid_elements]
        if animated_elements:
            logging.info(f"启用元素动画: {', '.join(animated_elements)}")

    total_images_needed = 0
    for _, all_font_paths, style in to_process:
        if style == 'obo':
            total_images_needed += len(all_font_paths)
        else:
            total_images_needed += 1

    position_animator = None
    if animated_elements:
        position_animator = PositionAnimator(
            total_images=total_images_needed,
            animation_type=args.animation_type,
            amplitude=int(args.animation_amplitude * scale_factor),
            speed=args.animation_speed,
            movement_speed=args.movement_speed
        )
        logging.info(f"动画设置: 类型={args.animation_type}, 幅度={int(args.animation_amplitude * scale_factor)}, 飘动速度={args.movement_speed}")
        logging.info(f"颜色变化速度系数: {args.animation_speed}")

    content_position_type, content_position_value = parse_content_position(args.content_position)
    content_position_random = (content_position_type == 'random')
    content_position_fixed = content_position_value if content_position_type == 'fixed' else None

    if content_position_fixed:
        content_position_fixed = (
            int(content_position_fixed[0] * scale_factor),
            int(content_position_fixed[1] * scale_factor)
        )

    if content_position_random:
        logging.info("内容位置: 完全随机")
    elif content_position_fixed:
        logging.info(f"内容位置: 固定位置 ({content_position_fixed[0]}, {content_position_fixed[1]})")

    precomputed = PrecomputedValues(cfg, scale_factor)

    color_mgr = None
    if args.random_color and not gradient_manager and not flash_color:
        logging.info("启用完全随机颜色模式")
        blend_cache = {}
        overlay_cache = {}
    elif args.dynamic_bg and not gradient_manager and not flash_color:
        logging.info("启用动态背景模式")
        color_mgr = ColorManager(cfg.color_cycle, Path('color_state.json'))
        if not color_mgr.state_file.exists() or not color_mgr._mapping:
            color_mgr.build_initial_mapping(entries)

        unique_colors = []
        if hasattr(color_mgr, '_mapping') and color_mgr._mapping:
            unique_colors.extend(color_mgr._mapping.values())
        if hasattr(color_mgr, 'color_cycle') and color_mgr.color_cycle:
            unique_colors.extend(color_mgr.color_cycle)
        unique_colors.append(cfg.background_color)

        seen = set()
        normalized_colors = []
        for color in unique_colors:
            normalized = normalize_color(color)
            color_key = tuple(normalized)
            if color_key not in seen:
                seen.add(color_key)
                normalized_colors.append(normalized)

        blend_cache, overlay_cache = precompute_blend_colors(cfg, normalized_colors)
    else:
        if not gradient_manager and not flash_color:
            logging.info(f"固定背景: {cfg.background_color}")
        blend_cache, overlay_cache = precompute_blend_colors(cfg, [cfg.background_color])

    logging.info(f"需要生成 {total_images_needed} 张图片 (workers={args.workers}, png-quality={args.png_quality}, scale={scale_factor:.2f})")

    bottom_font = ImageFont.truetype(str(cfg.bottom_font_file), cfg.bottom_font_size)
    try:
        ctrl_font = ImageFont.truetype(str(cfg.ctrl_font_file), cfg.middle_font_size)
    except OSError:
        logging.error(f"加载 Ctrl 字体失败: {cfg.ctrl_font_file}")
        ctrl_font = ImageFont.load_default()

    # 收集所有用到的字体路径用于预加载
    all_font_paths_set = set()
    for _, font_paths, _ in to_process:
        all_font_paths_set.update(font_paths)
    middle_font_cache, metrics_cache = preload_middle_fonts(
        [UnicodeEntry(p, "", "") for p in all_font_paths_set], cfg
    )

    text_cache: dict[str, tuple[int, int]] = {}
    overlay_bbox_cache: dict[str, tuple[int, int]] = {}

    q: Queue = Queue(maxsize=200)
    writer = Thread(target=optimized_writer_thread_fn, args=(q,), daemon=True)
    writer.start()

    start = time.time()
    match_results = []

    sorted_to_process = sorted(to_process, key=lambda x: int(x[0].code_str[2:], 16))

    with ThreadPoolExecutor(max_workers=args.workers) as pool, \
            tqdm(total=total_images_needed, desc="生成图片", unit="项") as bar:

        global_image_index = 0

        for entry, all_font_paths, style in sorted_to_process:
            index_in_block, total_in_block = block_index_mapping.get(entry.code_str, (0, 0))

            if style == 'obo':
                total_fonts = len(all_font_paths)
                for idx, font_path_str in enumerate(all_font_paths):
                    font_file = Path(font_path_str).name
                    bar.set_description(f"生成图片: {entry.code_str} ({font_file})")

                    future = pool.submit(
                        generate_image_bytes,
                        entry, cfg, color_mgr,
                        bottom_font, ctrl_font,
                        middle_font_cache, metrics_cache,
                        text_cache,
                        precomputed,
                        blend_cache, overlay_cache,
                        overlay_enabled, combining_cps,
                        overlay_bbox_cache, blocks,
                        unicode_names,
                        names_list_parser,
                        args.random_color and not gradient_manager and not flash_color,
                        filename_mapping,
                        gradient_manager,
                        global_image_index,
                        total_images_needed,
                        flash_color,
                        position_animator,
                        animated_elements,
                        content_position_random,
                        content_position_fixed,
                        args.show_names_info,
                        args.smooth_gradient,
                        args.show_encoding,
                        args.show_block_position,
                        args.show_global_position,
                        args.show_block_progress_bar,
                        args.show_global_progress_bar,
                        args.show_side_spinner,
                        (global_image_index // args.spinner_step_interval) % len(spinner_strings),
                        spinner_strings,
                        global_image_index,
                        total_images_needed,
                        total_in_block,
                        index_in_block,
                        scale_factor,
                        'obo',
                        [font_path_str],
                        0,
                        total_fonts,
                        font_file,
                    )
                    try:
                        data, path, matched_key = future.result()
                        q.put((data, path))
                        match_results.append((entry.code_str, matched_key))
                    except Exception as e:
                        logging.error(f"生成失败: {e}")
                    finally:
                        bar.update(1)
                        global_image_index += 1
            else:
                bar.set_description(f"生成图片: {entry.code_str}")
                future = pool.submit(
                    generate_image_bytes,
                    entry, cfg, color_mgr,
                    bottom_font, ctrl_font,
                    middle_font_cache, metrics_cache,
                    text_cache,
                    precomputed,
                    blend_cache, overlay_cache,
                    overlay_enabled, combining_cps,
                    overlay_bbox_cache, blocks,
                    unicode_names,
                    names_list_parser,
                    args.random_color and not gradient_manager and not flash_color,
                    filename_mapping,
                    gradient_manager,
                    global_image_index,
                    total_images_needed,
                    flash_color,
                    position_animator,
                    animated_elements,
                    content_position_random,
                    content_position_fixed,
                    args.show_names_info,
                    args.smooth_gradient,
                    args.show_encoding,
                    args.show_block_position,
                    args.show_global_position,
                    args.show_block_progress_bar,
                    args.show_global_progress_bar,
                    args.show_side_spinner,
                    (global_image_index // args.spinner_step_interval) % len(spinner_strings),
                    spinner_strings,
                    global_image_index,
                    total_images_needed,
                    total_in_block,
                    index_in_block,
                    scale_factor,
                    'compare',
                    all_font_paths,
                    0,
                    1,
                    '',
                )
                try:
                    data, path, matched_key = future.result()
                    q.put((data, path))
                    match_results.append((entry.code_str, matched_key))
                except Exception as e:
                    logging.error(f"生成失败: {e}")
                finally:
                    bar.update(1)
                    global_image_index += 1

    q.join()
    q.put(None)
    writer.join()

    elapsed = time.time() - start
    fps = total_images_needed / elapsed if elapsed > 0 else float('inf')
    logging.info(f"完成，用时 {elapsed:.2f}s，{fps:.2f} 张/秒。")

    if args.shuffle_content and filename_mapping:
        logging.info(f"文件名已随机化")


if __name__ == '__main__':
    main()