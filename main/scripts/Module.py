#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
from queue import Queue
from pathlib import Path
from threading import Lock
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Tuple, Optional, Any, Dict
import os

# 导入新创建的模块
from color_gradient import ColorGradient
from position_animator import PositionAnimator
from names_list_parser import NamesListParser
from precomputed_values import PrecomputedValues
from scaled_config import ScaledConfig

# 导入工具函数
from unicode_utils import (
    load_unicode_blocks, find_block_name, find_block_index,
    load_unicode_names, load_combining_marks, build_block_index_mapping,
    get_utf8_encoding, get_utf16le_encoding, get_utf16be_encoding
)

from image_utils import (
    fast_blend_colors, normalize_color, get_random_color, parse_color_list,
    precompute_blend_colors, calculate_lines_needed, render_info_text_simple,
    render_vertical_progress_bar, render_progress_bar, render_spinner_string_at_bottom,
    check_bounds_with_padding, truncate_text_to_width
)

from font_utils import preload_middle_fonts, get_font_display_name

from file_utils import (
    write_batch, optimized_writer_thread_fn,
    create_filename_mapping, parse_content_position
)

from chapter_generator import ChapterGenerator, create_chapters_from_blocks


@dataclass
class Config:
    """从 JSON 文件加载配置，提供默认值作为后备"""
    def __init__(self, config_path: Optional[Path] = None):
        self._data = self._default_config()
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                self._data.update(user_data)
        self._post_init()

    def _default_config(self) -> Dict:
        return {
            "unicode_file": "Unicode.txt",
            "font_files": ["font.ttf"],
            "ctrl_font_file": "Ctrl-Ctrl.ttf",
            "bottom_font_file": "PressStartHan2P.ttf",
            "music_file": "DUTM.m4a",
            "blocks_file": "UnicodeBlocks.txt",
            "output_dir": "png",
            "middle_font_size": 512,
            "bottom_font_size": 16,
            "text_position": [0, 0],
            "middle_font_color": [20, 20, 20, 175],
            "image_size": [1920, 1080],
            "background_color": [0, 0, 0, 255],
            "color_cycle": [
                "#ABDF56FF", "#6DE74EFF", "#68F59FFF", "#00BE9DFF", "#00CB81FF",
                "#A8FD9AFF", "#99FEA9FF", "#98FCCAFF", "#98FEEBFF", "#97ECFDFF",
                "#33E2FDFF", "#34B5DFFF", "#0095E0FF", "#CD9BFFFF", "#AB9BFFFF",
                "#EE9AFFEF", "#FF9AF0FF", "#FE9ACCFF", "#FF9AAAFF", "#FCAB9AFF",
                "#FBC99AFF", "#FDEE99FF", "#EEFE99FF", "#CFFF9BFF"
            ],
            "png_compress_level": 2,
            "png_optimize": False,
            "dynamic_bg": False,
            "random_color": False,
            "rainbow_gradient": False,
            "gradient_colors": "",
            "gradient_cycle": 100,
            "smooth_gradient": True,
            "flash_color": "",
            "animate_elements": [],
            "animation_type": "smooth",
            "animation_amplitude": 50,
            "animation_speed": 1.0,
            "movement_speed": 0.1,
            "content_position": "center",
            "offset_x": 0,
            "offset_y": 0,
            "shuffle_content": False,
            "show_names_info": False,
            "show_encoding": False,
            "show_block_position": False,
            "show_global_position": False,
            "show_block_progress_bar": False,
            "show_global_progress_bar": False,
            "show_side_spinner": False,
            "spinner_strings": "-,\\,|,/",
            "spinner_step_interval": 1,
            "scale": 1.0,
            "workers": 4,
            "disable_comb_overlay": False,
            "frame_rate": 30.0,
            "video_name": "output",
            "add_music": False,
            "generate_chapters": True,
            "chapter_template": "{block_name}"
        }

    def _post_init(self):
        # 转换路径
        for key in ["unicode_file", "ctrl_font_file", "bottom_font_file", "music_file", "blocks_file", "output_dir"]:
            if key in self._data:
                self._data[key] = Path(self._data[key])
        # 转换颜色循环为 RGBA 元组，使用 _hex_to_rgba_fast
        self._data["color_cycle_rgba"] = [self._hex_to_rgba_fast(c) for c in self._data.get("color_cycle", [])]
        # 确保其他类型正确
        if isinstance(self._data.get("text_position"), list):
            self._data["text_position"] = tuple(self._data["text_position"])
        if isinstance(self._data.get("middle_font_color"), list):
            self._data["middle_font_color"] = tuple(self._data["middle_font_color"])
        if isinstance(self._data.get("image_size"), list):
            self._data["image_size"] = tuple(self._data["image_size"])
        if isinstance(self._data.get("background_color"), list):
            self._data["background_color"] = tuple(self._data["background_color"])

    @staticmethod
    def _hex_to_rgba(s: str) -> Tuple[int, int, int, int]:
        s = s.lstrip('#')
        if len(s) == 6:
            s += 'FF'
        if len(s) != 8:
            raise ValueError(f"Invalid hex color: {s}")
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))

    # 别名，保持与原有代码兼容（原有 Config 类中有 _hex_to_rgba_fast）
    _hex_to_rgba_fast = _hex_to_rgba

    def __getattr__(self, name):
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def update(self, args: Dict):
        """用命令行参数更新配置"""
        for key, value in args.items():
            if value is not None and key in self._data:
                self._data[key] = value
        self._post_init()


@dataclass
class UnicodeEntry:
    font_path: str
    code_str: str
    description: str

    def get_font_paths(self) -> List[str]:
        if ':' in self.font_path:
            return self.font_path.split(':')
        elif '|' in self.font_path:
            return self.font_path.split('|')
        else:
            return [self.font_path]

    def has_multiple_fonts(self) -> bool:
        return ':' in self.font_path or '|' in self.font_path



class ColorManager:
    """
    根据 description 的哈希值循环分配背景色，保持相同 description 使用相同颜色。
    支持预定义映射和直接颜色值。
    """

    def __init__(self, color_cycle: list[tuple[int, int, int, int]], state_file: Path):
        self._cycle = color_cycle
        self._mapping: dict[str, int | str] = {}
        self._counter = 0
        self._lock = Lock()
        self.state_file = state_file

        self._color_cache: dict[str, tuple[int, int, int, int]] = {}
        self._key_cache: dict[str, str] = {}

        self._dirty = False
        self._save_batch_size = 100
        self._changes_count = 0

        self.load_state()

    def load_state(self):
        if self.state_file.exists():
            try:
                if self.state_file.stat().st_size == 0:
                    logging.warning(f"颜色状态文件 {self.state_file} 为空，使用默认设置")
                    return

                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self._mapping = state.get("mapping", {})
                    self._counter = state.get("counter", 0)
                    logging.info(f"成功加载颜色状态，包含 {len(self._mapping)} 个映射")
            except json.JSONDecodeError as e:
                logging.error(f"颜色状态文件格式错误：{e}，使用默认设置")
                backup_file = self.state_file.with_suffix('.json.backup')
                self.state_file.rename(backup_file)
                logging.info(f"已将损坏的文件备份为 {backup_file}")
            except Exception as e:
                logging.error(f"加载颜色状态文件时出错：{e}，使用默认设置")

    def save_state(self, force=False):
        if not force and not self._dirty:
            return

        try:
            temp_file = self.state_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "mapping": self._mapping,
                    "counter": self._counter
                }, f, indent=2, ensure_ascii=False)

            if os.name == 'nt':  # Windows
                if self.state_file.exists():
                    self.state_file.unlink()
            temp_file.replace(self.state_file)
            self._dirty = False

        except Exception as e:
            logging.error(f"保存颜色状态文件时出错：{e}")
            temp_file = self.state_file.with_suffix('.json.tmp')
            if temp_file.exists():
                temp_file.unlink()

    @lru_cache(maxsize=512)
    def _hex_to_rgba_cached(self, hex_color: str) -> tuple[int, int, int, int]:
        """将十六进制颜色转换为 RGBA 元组"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:  # #RGB
            hex_color = ''.join([c * 2 for c in hex_color]) + 'FF'
        elif len(hex_color) == 6:  # #RRGGBB
            hex_color = hex_color + 'FF'
        elif len(hex_color) != 8:  # #RRGGBBAA
            raise ValueError(f"Invalid hex color format: {hex_color}")

        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
            int(hex_color[6:8], 16)
        )

    def get_key_from_description(self, description: str) -> str:
        """从描述中提取关键部分,忽略详细信息"""
        if description in self._key_cache:
            return self._key_cache[description]

        if '|' in description:
            key = description.split('|')[0].strip()
        else:
            key = description

        if len(self._key_cache) < 10000:
            self._key_cache[description] = key
        return key

    def get_color(self, description: str) -> tuple[int, int, int, int]:
        key = self.get_key_from_description(description)

        if key in self._mapping:
            value = self._mapping[key]

            cache_key = f"{key}_{value}"
            if cache_key in self._color_cache:
                return self._color_cache[cache_key]

            if isinstance(value, str):
                color = self._hex_to_rgba_cached(value)
            else:
                color = self._cycle[value % len(self._cycle)]

            if len(self._color_cache) < 5000:
                self._color_cache[cache_key] = color
            return color

        with self._lock:
            if key not in self._mapping:
                self._mapping[key] = self._counter
                self._counter = (self._counter + 1) % len(self._cycle)
                self._dirty = True
                self._changes_count += 1

                if self._changes_count >= self._save_batch_size:
                    self.save_state()
                    self._changes_count = 0

            value = self._mapping[key]

            if isinstance(value, str):
                color = self._hex_to_rgba_cached(value)
            else:
                color = self._cycle[value % len(self._cycle)]

            cache_key = f"{key}_{value}"
            if len(self._color_cache) < 5000:
                self._color_cache[cache_key] = color
            return color

    def set_custom_color(self, description: str, color: str):
        """为特定描述设置自定义颜色"""
        key = self.get_key_from_description(description)
        with self._lock:
            self._mapping[key] = color
            self._dirty = True
            self._changes_count += 1

            cache_keys_to_remove = [k for k in self._color_cache.keys() if k.startswith(f"{key}_")]
            for k in cache_keys_to_remove:
                del self._color_cache[k]

            if self._changes_count >= self._save_batch_size:
                self.save_state()
                self._changes_count = 0

    def build_initial_mapping(self, entries: list):
        """根据 Unicode 条目构建初始映射"""
        seen = set()
        unique_descriptions = []

        sorted_entries = sorted(entries, key=lambda x: int(x.code_str[2:], 16))

        for entry in sorted_entries:
            key = self.get_key_from_description(entry.description)
            if key not in seen:
                unique_descriptions.append(key)
                seen.add(key)

        with self._lock:
            for desc in unique_descriptions:
                if desc not in self._mapping:
                    self._mapping[desc] = self._counter
                    self._counter = (self._counter + 1) % len(self._cycle)

            self._dirty = True
            self.save_state(force=True)

        logging.info(f"构建了 {len(unique_descriptions)} 个描述的颜色映射")

    def finalize(self):
        """完成处理时调用，确保所有更改都已保存"""
        if self._dirty:
            self.save_state(force=True)


def load_unicode_entries(path: Path) -> list[UnicodeEntry]:
    entries: list[UnicodeEntry] = []

    content = path.read_text(encoding='utf-8')
    lines = content.splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(';', 2)
        if len(parts) == 2:
            parts.append('')
        elif len(parts) != 3:
            raise ValueError(f"行格式错误（期望 2 或 3 段，用 ; 分隔）: {line!r}")

        font_path = parts[0].strip().strip('"')
        code_str = parts[1].strip().strip('"')
        desc = parts[2].strip().strip('"')

        entries.append(UnicodeEntry(font_path, code_str, desc))

    return entries

def setup_logging():
    if not logging.getLogger().handlers:
        logging.basicConfig(
            format='[%(asctime)s] - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S',
            level=logging.INFO
        )


def writer_thread_fn(q: Queue, batch_size: int = 10):
    """单线程顺序写入磁盘，减少 HDD 随机寻道。"""
    batch = []

    while True:
        item = q.get()
        if item is None:
            if batch:
                _write_batch(batch)
            q.task_done()
            break

        batch.append(item)
        if len(batch) >= batch_size:
            _write_batch(batch)
            batch.clear()

        q.task_done()


def _write_batch(batch: list):
    """批量写入文件"""
    for data, out_path in batch:
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            logging.error(f"写入文件失败 {out_path}: {e}")


@lru_cache(maxsize=1024)
def blend_colors(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    """缓存版颜色混合函数"""
    inv_alpha = 1.0 - alpha
    return (
        int(fg[0] * alpha + bg[0] * inv_alpha),
        int(fg[1] * alpha + bg[1] * inv_alpha),
        int(fg[2] * alpha + bg[2] * inv_alpha)
    )


def load_config(config_path: Path = Path("config.json")) -> Config:
    """便捷加载配置函数"""
    return Config(config_path)