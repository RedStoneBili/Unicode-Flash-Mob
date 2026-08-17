#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import random
import logging
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from control_map import get_char, CTRLS
from Module import (
    UnicodeEntry, ColorManager, ColorGradient, PositionAnimator,
    NamesListParser, PrecomputedValues, ScaledConfig,
    load_unicode_blocks, find_block_name, find_block_index,
    load_unicode_names, load_combining_marks, build_block_index_mapping,
    get_utf8_encoding, get_utf16le_encoding, get_utf16be_encoding,
    fast_blend_colors, normalize_color, get_random_color, parse_color_list,
    precompute_blend_colors, calculate_lines_needed,
    render_info_text_simple, render_vertical_progress_bar,
    render_spinner_string_at_bottom, check_bounds_with_padding,
    truncate_text_to_width, preload_middle_fonts, get_font_display_name
)

def render_frame(
    entry: UnicodeEntry,
    cfg,
    color_mgr: Optional[ColorManager],
    bottom_font: ImageFont.FreeTypeFont,
    ctrl_font: ImageFont.FreeTypeFont,
    middle_font_cache: dict,
    metrics_cache: dict,
    text_cache: dict,
    precomputed: PrecomputedValues,
    blend_cache: dict,
    overlay_cache: dict,
    overlay_enabled: bool,
    combining_cps: set,
    overlay_bbox_cache: dict,
    blocks: list,
    unicode_names: dict,
    names_list_parser: NamesListParser,
    random_color: bool,
    gradient_manager: Optional[ColorGradient],
    gradient_index: int,
    gradient_total: int,
    flash_color: Optional[Tuple[int, int, int, int]],
    position_animator: Optional[PositionAnimator],
    animated_elements: List[str],
    content_position_random: bool,
    content_position_fixed: Optional[Tuple[int, int]],
    show_names_info: bool,
    use_smooth_gradient: bool,
    show_encoding: bool,
    show_block_position: bool,
    show_global_position: bool,
    show_block_progress_bar: bool,
    show_global_progress_bar: bool,
    show_side_spinner: bool,
    spinner_step: int,
    spinner_strings: List[str],
    global_index: int,
    total_entries: int,
    total_in_block: int,
    index_in_block: int,
    scale_factor: float,
    style: str,
    font_paths: List[str],
    font_index: int,
    total_fonts: int,
    font_name: str
) -> bytes:
    try:
        cp = int(entry.code_str.strip()[2:], 16)
    except:
        raise ValueError(f"Invalid code_str: {entry.code_str!r}")

    char = get_char(cp)
    is_control = (cp in CTRLS)

    # 注意：这里不再对 font_paths 做任何修改，直接使用传入的列表
    # 对于 obo 模式，font_paths 已经是单元素列表

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

    is_multi_font = (len(font_paths) > 1) and (style == 'compare')

    if is_multi_font:
        # 并排显示所有字体
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
        # 单字体或 obo 模式（传入了单元素列表）
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
        # 单字体或 obo，显示当前字体名
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
    img.save(buf, format='PNG',
             compress_level=cfg.png_compress_level,
             optimize=cfg.png_optimize)
    data = buf.getvalue()
    buf.close()
    img.close()
    return data