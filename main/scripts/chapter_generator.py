#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import List, Tuple, Optional
import logging
import math


class ChapterGenerator:
    def __init__(self, min_seconds: int = 0):
        self.min_seconds = min_seconds

    def seconds_to_time_str(self, seconds: float) -> str:
        """将秒数转换为 HH:MM:SS 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"

    def generate_chapters_by_blocks(
            self,
            blocks: List[Tuple[int, int, str]],
            entries: List,
            frame_rate: float,
            chapter_name_template: str = "{block_name}"
    ) -> List[Tuple[float, str]]:
        if not blocks or not entries:
            return []

        sorted_entries = sorted(entries, key=lambda x: int(x.code_str[2:], 16))

        cp_to_index = {}
        for i, entry in enumerate(sorted_entries):
            cp = int(entry.code_str[2:], 16)
            cp_to_index[cp] = i

        chapters = []
        last_chapter_time = -self.min_seconds

        for start_cp, end_cp, block_name in blocks:
            block_start_index = None

            for cp in range(start_cp, end_cp + 1):
                if cp in cp_to_index:
                    block_start_index = cp_to_index[cp]
                    break

            if block_start_index is None:
                continue

            start_time = block_start_index / frame_rate

            if self.min_seconds > 0:
                time_gap = start_time - last_chapter_time
                if time_gap < self.min_seconds:
                    start_time = last_chapter_time + self.min_seconds

            # 生成章节名称
            chapter_name = chapter_name_template.format(
                block_name=block_name
            )

            chapters.append((start_time, chapter_name))
            last_chapter_time = start_time

        return chapters

    def save_chapter_file(self, chapters: List[Tuple[float, str]], output_path: Path) -> bool:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for time_point, name in chapters:
                    time_str = self.seconds_to_time_str(time_point)
                    f.write(f"{time_str} {name}\n")

            logging.info(f"章节文件已保存: {output_path}")
            return True
        except Exception as e:
            logging.error(f"保存章节文件失败: {e}")
            return False

    def print_chapters(self, chapters: List[Tuple[float, str]]):
        logging.info("生成的章节列表（起始时间）：")
        for i, (time_point, name) in enumerate(chapters):
            time_str = self.seconds_to_time_str(time_point)
            if i < len(chapters) - 1:
                next_time = chapters[i + 1][0]
                duration = next_time - time_point
                logging.info(f"  {i + 1}. {time_str} {name} (持续 {duration:.2f}秒)")
            else:
                logging.info(f"  {i + 1}. {time_str} {name} (持续到最后)")


def create_chapters_from_blocks(
        blocks_path: Path,
        entries: List,
        frame_rate: float,
        output_path: Path,
        min_seconds: int = 0,
        template: str = "{block_name}"
) -> bool:
    from Module import load_unicode_blocks

    if not blocks_path.exists():
        logging.error(f"区块文件不存在: {blocks_path}")
        return False

    blocks = load_unicode_blocks(blocks_path)
    if not blocks:
        logging.error("没有加载到任何区块")
        return False

    generator = ChapterGenerator(min_seconds=min_seconds)
    chapters = generator.generate_chapters_by_blocks(
        blocks=blocks,
        entries=entries,
        frame_rate=frame_rate,
        chapter_name_template=template
    )

    if chapters:
        generator.print_chapters(chapters)
        return generator.save_chapter_file(chapters, output_path)
    else:
        logging.warning("没有生成任何章节")
        return False