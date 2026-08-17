#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import subprocess
import platform
import logging
import argparse
import random
import time
from pathlib import Path
from queue import Queue
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

from Module import (
    Config, UnicodeEntry, ColorManager, load_unicode_entries,
    load_unicode_blocks, load_unicode_names, load_combining_marks,
    build_block_index_mapping, NamesListParser, PrecomputedValues,
    ScaledConfig, ColorGradient, PositionAnimator, setup_logging,
    preload_middle_fonts, get_font_display_name, load_config,
    precompute_blend_colors, parse_color_list, get_random_color
)
from render import render_frame
from control_map import CTRLS, get_char
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm


def find_ffmpeg():
    ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    for path in os.environ.get("PATH", "").split(os.pathsep):
        ffmpeg_path = os.path.join(path, ffmpeg_exe)
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    local_path = Path.cwd() / "ffmpeg" / "bin" / ffmpeg_exe
    if local_path.exists():
        return str(local_path)
    raise FileNotFoundError("ffmpeg not found in PATH or ./ffmpeg/bin/")


def add_music_to_video(video_file: Path, music_file: Path, output_file: Path, ffmpeg_path: str) -> bool:
    if not music_file.exists():
        logging.warning(f"音乐文件不存在: {music_file}")
        return False
    cmd = [
        ffmpeg_path, '-y',
        '-i', str(video_file),
        '-stream_loop', '-1',
        '-i', str(music_file),
        '-shortest',
        '-c:v', 'copy',
        '-c:a', 'aac',
        str(output_file)
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"添加音乐失败: {e.stderr}")
        return False


def generate_chapter_file(entries, blocks, frame_rate, output_path, template="{block_name}"):
    from chapter_generator import ChapterGenerator
    gen = ChapterGenerator(min_seconds=0)
    chapters = gen.generate_chapters_by_blocks(blocks, entries, frame_rate, template)
    if chapters:
        gen.save_chapter_file(chapters, output_path)
        return True
    return False


def parse_args():
    parser = argparse.ArgumentParser(description="Unicode Flash Mob 视频生成器")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="配置文件路径")
    parser.add_argument("--unicode-file", type=Path)
    parser.add_argument("--font-files", nargs="+")
    parser.add_argument("--ctrl-font", type=Path)
    parser.add_argument("--bottom-font", type=Path)
    parser.add_argument("--music-file", type=Path)
    parser.add_argument("--blocks-file", type=Path)
    parser.add_argument("--middle-font-size", type=int)
    parser.add_argument("--bottom-font-size", type=int)
    parser.add_argument("--text-position", type=lambda s: tuple(map(int, s.split(','))))
    parser.add_argument("--middle-font-color", type=lambda s: tuple(map(int, s.split(','))))
    parser.add_argument("--image-size", type=lambda s: tuple(map(int, s.split(','))))
    parser.add_argument("--bg-color", type=lambda s: tuple(map(int, s.split(','))))
    parser.add_argument("--color-cycle", nargs="+")
    parser.add_argument("--dynamic-bg", action="store_true")
    parser.add_argument("--random-color", action="store_true")
    parser.add_argument("--rainbow-gradient", action="store_true")
    parser.add_argument("--gradient-colors", type=str)
    parser.add_argument("--gradient-cycle", type=int)
    parser.add_argument("--smooth-gradient", action="store_true")
    parser.add_argument("--flash-color", type=str)
    parser.add_argument("--animate-elements", type=lambda s: s.split(','))
    parser.add_argument("--animation-type", choices=["smooth", "random_smooth"])
    parser.add_argument("--animation-amplitude", type=int)
    parser.add_argument("--animation-speed", type=float)
    parser.add_argument("--movement-speed", type=float)
    parser.add_argument("--content-position", choices=["center", "random", "fixed"])
    parser.add_argument("--offset-x", type=int)
    parser.add_argument("--offset-y", type=int)
    parser.add_argument("--shuffle-content", action="store_true")
    parser.add_argument("--show-names-info", action="store_true")
    parser.add_argument("--show-encoding", action="store_true")
    parser.add_argument("--show-block-position", action="store_true")
    parser.add_argument("--show-global-position", action="store_true")
    parser.add_argument("--show-block-progress-bar", action="store_true")
    parser.add_argument("--show-global-progress-bar", action="store_true")
    parser.add_argument("--show-side-spinner", action="store_true")
    parser.add_argument("--spinner-strings", type=str)
    parser.add_argument("--spinner-step-interval", type=int)
    parser.add_argument("--scale", type=float)
    parser.add_argument("--workers", type=int)
    parser.add_argument("--disable-comb-overlay", action="store_true")
    parser.add_argument("--frame-rate", type=float)
    parser.add_argument("--video-name", type=str)
    parser.add_argument("--add-music", action="store_true")
    parser.add_argument("--no-chapters", action="store_true")
    parser.add_argument("--chapter-template", type=str)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging()

    cfg = load_config(args.config)
    args_dict = vars(args)
    ignore_keys = {"config", "output_dir", "no_chapters"}
    override = {k: v for k, v in args_dict.items() if v is not None and k not in ignore_keys}
    cfg.update(override)

    output_dir = args.output_dir
    cfg.output_dir = output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = load_unicode_entries(cfg.unicode_file)
    if not entries:
        logging.error("未加载任何 Unicode 条目")
        return 1

    total_entries = len(entries)

    blocks = load_unicode_blocks(cfg.blocks_file) if cfg.blocks_file.exists() else []
    logging.info(f"加载 {len(blocks)} 个区块")

    unicode_data_path = Path("UnicodeData.txt")
    if unicode_data_path.exists():
        combining_cps = load_combining_marks(unicode_data_path)
        unicode_names = load_unicode_names(unicode_data_path)
    else:
        combining_cps = set()
        unicode_names = {}

    overlay_enabled = not cfg.disable_comb_overlay
    block_index_mapping = build_block_index_mapping(blocks, entries) if blocks else {}
    names_list_parser = NamesListParser(Path("NamesList.txt"))

    color_mgr = None
    if cfg.dynamic_bg and not cfg.rainbow_gradient and not cfg.flash_color:
        color_mgr = ColorManager(cfg.color_cycle_rgba, Path("color_state.json"))
        if not color_mgr.state_file.exists() or not color_mgr._mapping:
            color_mgr.build_initial_mapping(entries)
        unique_colors = list(cfg.color_cycle_rgba) + [cfg.background_color]
        if color_mgr._mapping:
            unique_colors.extend(color_mgr._mapping.values())
        blend_cache, overlay_cache = precompute_blend_colors(cfg, unique_colors)
    else:
        if not cfg.rainbow_gradient and not cfg.flash_color:
            logging.info(f"固定背景: {cfg.background_color}")
        blend_cache, overlay_cache = precompute_blend_colors(cfg, [cfg.background_color])

    gradient_manager = None
    if cfg.rainbow_gradient:
        if cfg.gradient_colors:
            key_colors = parse_color_list(cfg.gradient_colors)
        else:
            key_colors = None
        gradient_manager = ColorGradient(key_colors, cfg.gradient_cycle)
        logging.info(f"彩虹渐变启用，周期 {cfg.gradient_cycle} 张")

    flash_color = None
    if cfg.flash_color:
        flash_color = parse_color_list(cfg.flash_color)
        if flash_color:
            flash_color = flash_color[0]
        else:
            flash_color = get_random_color()
    elif cfg.flash_color == "" and (cfg.random_color or cfg.dynamic_bg or cfg.rainbow_gradient):
        pass
    else:
        flash_color = get_random_color()
        logging.info("使用随机闪出颜色")

    animated_elements = cfg.animate_elements if cfg.animate_elements else []
    position_animator = None
    if animated_elements:
        position_animator = PositionAnimator(
            total_images=total_entries,
            animation_type=cfg.animation_type,
            amplitude=int(cfg.animation_amplitude * cfg.scale),
            speed=cfg.animation_speed,
            movement_speed=cfg.movement_speed
        )

    content_position_random = (cfg.content_position == "random")
    content_position_fixed = None
    if cfg.content_position == "fixed":
        content_position_fixed = (int(cfg.offset_x * cfg.scale), int(cfg.offset_y * cfg.scale))

    scaled_cfg = ScaledConfig(cfg, cfg.scale)
    precomputed = PrecomputedValues(scaled_cfg, cfg.scale)

    bottom_font = ImageFont.truetype(str(cfg.bottom_font_file), cfg.bottom_font_size)
    try:
        ctrl_font = ImageFont.truetype(str(cfg.ctrl_font_file), cfg.middle_font_size)
    except:
        ctrl_font = ImageFont.load_default()

    middle_font_cache, metrics_cache = preload_middle_fonts(entries, cfg)

    text_cache = {}
    overlay_bbox_cache = {}

    ffmpeg_path = find_ffmpeg()
    output_video = output_dir / f"{cfg.video_name}.mp4"
    ffmpeg_cmd = [
        ffmpeg_path, '-y',
        '-r', str(cfg.frame_rate),
        '-f', 'image2pipe',
        '-i', '-',
        '-c:v', 'libx264',
        '-crf', '18',
        '-preset', 'fast',
        '-pix_fmt', 'yuv420p',
        '-fflags', '+genpts+discardcorrupt',
        '-vsync', 'vfr',
        '-avoid_negative_ts', 'make_zero',
        '-threads', str(os.cpu_count() or 4),
        '-flush_packets', '1',
        str(output_video)
    ]

    logging.info(f"启动 FFmpeg: {' '.join(ffmpeg_cmd)}")
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def read_stderr():
        for line in iter(proc.stderr.readline, b''):
            if line:
                logging.debug(f"FFmpeg: {line.decode().strip()}")
    stderr_thread = Thread(target=read_stderr, daemon=True)
    stderr_thread.start()

    total_frames = 0
    entry_frame_counts = {}
    for idx, entry in enumerate(entries):
        if ':' in entry.font_path:
            cnt = len(entry.get_font_paths())
        else:
            cnt = 1
        entry_frame_counts[idx] = cnt
        total_frames += cnt

    workers = cfg.workers
    result_queue = Queue(maxsize=workers * 2)

    def producer():
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            global_frame_idx = 0
            for entry_index, entry in enumerate(entries):
                index_in_block, total_in_block = block_index_mapping.get(entry.code_str, (0, 0))
                all_font_paths = entry.get_font_paths()
                if '|' in entry.font_path:
                    style = 'compare'
                    futures.append((global_frame_idx, entry_index, executor.submit(
                        render_frame,
                        entry, cfg, color_mgr, bottom_font, ctrl_font,
                        middle_font_cache, metrics_cache, text_cache, precomputed,
                        blend_cache, overlay_cache, overlay_enabled, combining_cps,
                        overlay_bbox_cache, blocks, unicode_names, names_list_parser,
                        cfg.random_color, gradient_manager, global_frame_idx, total_frames, flash_color,
                        position_animator, animated_elements, content_position_random,
                        content_position_fixed, cfg.show_names_info, cfg.smooth_gradient,
                        cfg.show_encoding, cfg.show_block_position, cfg.show_global_position,
                        cfg.show_block_progress_bar, cfg.show_global_progress_bar,
                        cfg.show_side_spinner,
                        (global_frame_idx // cfg.spinner_step_interval) % len(cfg.spinner_strings.split(',')),
                        cfg.spinner_strings.split(','), entry_index, total_entries,
                        total_in_block, index_in_block, cfg.scale,
                        style, all_font_paths, 0, 1, ''
                    )))
                    global_frame_idx += 1
                elif ':' in entry.font_path:
                    for fi, font_path in enumerate(all_font_paths):
                        style = 'obo'
                        futures.append((global_frame_idx, entry_index, executor.submit(
                            render_frame,
                            entry, cfg, color_mgr, bottom_font, ctrl_font,
                            middle_font_cache, metrics_cache, text_cache, precomputed,
                            blend_cache, overlay_cache, overlay_enabled, combining_cps,
                            overlay_bbox_cache, blocks, unicode_names, names_list_parser,
                            cfg.random_color, gradient_manager, global_frame_idx, total_frames, flash_color,
                            position_animator, animated_elements, content_position_random,
                            content_position_fixed, cfg.show_names_info, cfg.smooth_gradient,
                            cfg.show_encoding, cfg.show_block_position, cfg.show_global_position,
                            cfg.show_block_progress_bar, cfg.show_global_progress_bar,
                            cfg.show_side_spinner,
                            (global_frame_idx // cfg.spinner_step_interval) % len(cfg.spinner_strings.split(',')),
                            cfg.spinner_strings.split(','), entry_index, total_entries,
                            total_in_block, index_in_block, cfg.scale,
                            style, [font_path], fi, len(all_font_paths), ''
                        )))
                        global_frame_idx += 1
                else:
                    style = 'single'
                    futures.append((global_frame_idx, entry_index, executor.submit(
                        render_frame,
                        entry, cfg, color_mgr, bottom_font, ctrl_font,
                        middle_font_cache, metrics_cache, text_cache, precomputed,
                        blend_cache, overlay_cache, overlay_enabled, combining_cps,
                        overlay_bbox_cache, blocks, unicode_names, names_list_parser,
                        cfg.random_color, gradient_manager, global_frame_idx, total_frames, flash_color,
                        position_animator, animated_elements, content_position_random,
                        content_position_fixed, cfg.show_names_info, cfg.smooth_gradient,
                        cfg.show_encoding, cfg.show_block_position, cfg.show_global_position,
                        cfg.show_block_progress_bar, cfg.show_global_progress_bar,
                        cfg.show_side_spinner,
                        (global_frame_idx // cfg.spinner_step_interval) % len(cfg.spinner_strings.split(',')),
                        cfg.spinner_strings.split(','), entry_index, total_entries,
                        total_in_block, index_in_block, cfg.scale,
                        style, all_font_paths, 0, 1, ''
                    )))
                    global_frame_idx += 1
            for idx, entry_idx, future in futures:
                try:
                    data = future.result()
                    result_queue.put((idx, data, entry_idx))
                except Exception as e:
                    logging.error(f"渲染帧 {idx} 失败: {e}")
                    result_queue.put((idx, b'', entry_idx))
        result_queue.put(None)

    def consumer():
        next_index = 0
        pending = {}
        completed_entries = set()
        received_counts = {i: 0 for i in range(total_entries)}
        with tqdm(total=total_entries, desc="生成字符") as pbar:
            while True:
                item = result_queue.get()
                if item is None:
                    break
                idx, data, entry_idx = item
                if data == b'':
                    received_counts[entry_idx] += 1
                    if received_counts[entry_idx] == entry_frame_counts[entry_idx] and entry_idx not in completed_entries:
                        completed_entries.add(entry_idx)
                        pbar.update(1)
                    next_index += 1
                    while next_index in pending:
                        next_data, next_entry = pending.pop(next_index)
                        proc.stdin.write(next_data)
                        received_counts[next_entry] += 1
                        if received_counts[next_entry] == entry_frame_counts[next_entry] and next_entry not in completed_entries:
                            completed_entries.add(next_entry)
                            pbar.update(1)
                        next_index += 1
                    continue
                if idx == next_index:
                    proc.stdin.write(data)
                    next_index += 1
                    received_counts[entry_idx] += 1
                    if received_counts[entry_idx] == entry_frame_counts[entry_idx] and entry_idx not in completed_entries:
                        completed_entries.add(entry_idx)
                        pbar.update(1)
                    while next_index in pending:
                        next_data, next_entry = pending.pop(next_index)
                        proc.stdin.write(next_data)
                        received_counts[next_entry] += 1
                        if received_counts[next_entry] == entry_frame_counts[next_entry] and next_entry not in completed_entries:
                            completed_entries.add(next_entry)
                            pbar.update(1)
                        next_index += 1
                else:
                    pending[idx] = (data, entry_idx)
        proc.stdin.close()
        logging.info("已关闭 stdin，等待 FFmpeg 结束...")

    prod_thread = Thread(target=producer, daemon=True)
    cons_thread = Thread(target=consumer, daemon=True)
    prod_thread.start()
    cons_thread.start()

    prod_thread.join()
    cons_thread.join()

    try:
        ret = proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
        stderr = proc.stderr.read().decode()
        logging.error(f"FFmpeg 超时，已终止。stderr: {stderr}")
        return 1

    if ret != 0:
        logging.error(f"FFmpeg 编码失败，返回码 {ret}")
        stderr = proc.stderr.read().decode()
        logging.error(stderr)
        return 1

    logging.info(f"视频生成完成: {output_video}")

    if cfg.add_music and cfg.music_file.exists():
        music_out = output_dir / f"{cfg.video_name}_music.mp4"
        if add_music_to_video(output_video, cfg.music_file, music_out, ffmpeg_path):
            logging.info(f"带音乐视频: {music_out}")
        else:
            logging.warning("添加音乐失败，仅保存无音乐版本")
    else:
        if not cfg.add_music:
            logging.info("未启用音乐（未添加 --add-music 参数）")
        elif not cfg.music_file.exists():
            logging.warning(f"音乐文件不存在: {cfg.music_file}")

    if cfg.generate_chapters and blocks:
        chapter_path = output_dir / f"{cfg.video_name}.txt"
        if generate_chapter_file(entries, blocks, cfg.frame_rate, chapter_path, cfg.chapter_template):
            logging.info(f"章节文件: {chapter_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())