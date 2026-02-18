#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from typing import Dict, List


class NamesListParser:
    """解析NamesList.txt文件，提供Unicode字符的详细信息"""

    def __init__(self, path: Path):
        self.path = path
        self.entries: Dict[str, List[str]] = {}
        self._parse_file()

    def _parse_file(self):
        if not self.path.exists():
            logging.warning(f"NamesList.txt 未找到: {self.path}")
            return

        current_code = None
        current_lines = []

        try:
            content = self.path.read_text(encoding='utf-8')
            lines = content.splitlines()

            for line in lines:
                line = line.rstrip('\n')

                if len(line) >= 4 and line[0:4].isalnum():
                    if current_code and current_lines:
                        self.entries[current_code] = current_lines

                    parts = line.split('\t', 1)
                    if len(parts) > 0:
                        current_code = parts[0].strip().upper()
                        current_lines = [line]
                elif current_code is not None:
                    current_lines.append(line)

            if current_code and current_lines:
                self.entries[current_code] = current_lines

            logging.info(f"加载 NamesList.txt: {len(self.entries)} 个条目")

        except Exception as e:
            logging.error(f"解析 NamesList.txt 失败: {e}")

    def get_info_for_code(self, code_str: str) -> List[str]:
        """获取指定码位的详细信息"""
        if code_str.startswith("U+"):
            hex_code = code_str[2:].upper().zfill(4)
        else:
            hex_code = code_str.upper().zfill(4)

        return self.entries.get(hex_code, [])