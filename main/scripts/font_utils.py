#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from typing import Dict, Tuple

from PIL import ImageFont


def preload_middle_fonts(entries, cfg) -> tuple[dict, dict]:
    """预加载字体和度量信息"""
    paths = {entry.font_path for entry in entries}
    paths.update(cfg.font_files)

    font_cache: dict[Path, ImageFont.FreeTypeFont | None] = {}
    metrics_cache: dict[Path, tuple[int, int]] = {}

    for p in paths:
        try:
            font = ImageFont.truetype(str(p), cfg.middle_font_size)
            font_cache[p] = font
            metrics_cache[p] = font.getmetrics()
        except Exception as e:
            logging.warning(f"预加载字体失败 `{p}`: {e}")
            font_cache[p] = None

    return font_cache, metrics_cache


def get_font_display_name(font_path_key, cfg) -> str:
    """获取字体的显示名称"""
    try:
        if font_path_key == 'ctrl':
            return Path(cfg.ctrl_font_file).name
        elif font_path_key == 'default':
            return 'default'
        else:
            return Path(str(font_path_key)).name
    except Exception:
        return str(font_path_key)