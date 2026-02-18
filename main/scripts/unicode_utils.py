#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import List, Tuple, Dict, Set
import logging


def load_unicode_blocks(path: Path) -> list[tuple[int, int, str]]:
    """加载Unicode区块定义文件"""
    blocks: list[tuple[int, int, str]] = []
    try:
        text = path.read_text(encoding='utf-8')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ';' not in line:
                continue
            range_part, name = line.split(';', 1)
            name = name.strip()
            if '..' not in range_part:
                continue
            start_s, end_s = range_part.split('..', 1)
            try:
                start = int(start_s, 16)
                end = int(end_s, 16)
                blocks.append((start, end, name))
            except Exception:
                continue
    except Exception:
        return []
    blocks.sort(key=lambda x: x[0])
    return blocks


def find_block_name(cp: int, blocks: list[tuple[int, int, str]]) -> str:
    """查找字符所属的区块名称"""
    for start, end, name in blocks:
        if start <= cp <= end:
            return name
    return 'No_Block'


def find_block_index(cp: int, blocks: list[tuple[int, int, str]]) -> Tuple[int, int]:
    """返回 (该字符在区块中的序号, 区块总字符数)"""
    for start, end, name in blocks:
        if start <= cp <= end:
            return (cp - start + 1, end - start + 1)
    return (0, 0)


def load_unicode_names(path: Path) -> dict[int, str]:
    """从UnicodeData.txt加载字符名称"""
    names: dict[int, str] = {}
    try:
        text = path.read_text(encoding='utf-8')
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(';')
            if len(parts) < 2:
                continue
            try:
                cp = int(parts[0], 16)
            except Exception:
                continue
            name = parts[1].strip()
            names[cp] = name
    except Exception:
        return {}
    return names


def load_combining_marks(path: Path) -> set[int]:
    """加载组合标记字符(Mn/Mc/Me)"""
    cps = set()
    try:
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            f = line.split(';')
            if len(f) < 3:
                continue
            cp = int(f[0], 16)
            if f[2] in ('Mn', 'Mc', 'Me'):
                cps.add(cp)
    except Exception as e:
        logging.error(f"读取 UnicodeData.txt 失败: {e}")
    return cps


def build_block_index_mapping(blocks: list[tuple[int, int, str]], entries: list) -> dict[str, Tuple[int, int]]:
    """构建码点到 (区块内序号, 区块总字符数) 的映射"""
    mapping = {}

    # 按码点排序条目
    sorted_entries = sorted(entries, key=lambda x: int(x.code_str[2:], 16))

    for entry in sorted_entries:
        cp = int(entry.code_str[2:], 16)
        for start, end, name in blocks:
            if start <= cp <= end:
                index_in_block = cp - start + 1
                total_in_block = end - start + 1
                mapping[entry.code_str] = (index_in_block, total_in_block)
                break

    return mapping


def get_utf8_encoding(cp: int) -> str:
    """获取字符的UTF-8编码表示"""
    try:
        char = chr(cp)
        utf8_bytes = char.encode('utf-8')
        return ' '.join([f'{b:02X}' for b in utf8_bytes])
    except:
        return 'N/A'


def get_utf16le_encoding(cp: int) -> str:
    """获取字符的UTF-16LE编码表示"""
    try:
        char = chr(cp)
        utf16_bytes = char.encode('utf-16-le')
        return ' '.join([f'{b:02X}' for b in utf16_bytes])
    except:
        return 'N/A'


def get_utf16be_encoding(cp: int) -> str:
    """获取字符的UTF-16BE编码表示"""
    try:
        char = chr(cp)
        utf16_bytes = char.encode('utf-16-be')
        return ' '.join([f'{b:02X}' for b in utf16_bytes])
    except:
        return 'N/A'