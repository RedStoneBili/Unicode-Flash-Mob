#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import List, Tuple, Optional


def write_batch(batch: list):
    """批量写入文件"""
    for data, path in batch:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(data)
        except Exception as e:
            logging.error(f"写入文件失败 {path}: {e}")


def optimized_writer_thread_fn(queue: Queue):
    """优化的写入线程，支持批量写入"""
    batch = []
    batch_size = 10

    while True:
        item = queue.get()
        if item is None:
            if batch:
                write_batch(batch)
            queue.task_done()
            break

        batch.append(item)
        if len(batch) >= batch_size:
            write_batch(batch)
            batch.clear()

        queue.task_done()


def create_filename_mapping(entries) -> dict[str, str]:
    """创建文件名映射：原文件名 -> 随机文件名"""
    import random

    original_filenames = [entry.code_str for entry in entries]
    shuffled_filenames = original_filenames.copy()
    random.shuffle(shuffled_filenames)

    filename_mapping = {}
    for i, original in enumerate(original_filenames):
        filename_mapping[original] = shuffled_filenames[i]

    logging.info(f"创建文件名映射: {len(filename_mapping)} 个文件")
    if len(filename_mapping) > 0:
        sample_keys = list(filename_mapping.keys())[:3]
        for key in sample_keys:
            logging.info(f"  示例: {key} -> {filename_mapping[key]}")

    return filename_mapping


def parse_content_position(position_str: str):
    """解析内容位置参数"""
    if not position_str:
        return None, None

    if position_str.lower() == 'random':
        return 'random', None

    parts = position_str.split(',')
    if len(parts) >= 3 and parts[0].lower() == 'fixed':
        try:
            x = int(parts[1])
            y = int(parts[2])
            return 'fixed', (x, y)
        except ValueError:
            logging.warning(f"无法解析固定位置参数: {position_str}")

    return None, None