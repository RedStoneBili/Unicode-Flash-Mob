#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import colorsys
from typing import List, Tuple, Optional


class ColorGradient:
    """颜色渐变管理器，支持关键颜色插值和平滑HSV渐变"""

    def __init__(self, key_colors: Optional[List[Tuple[int, int, int, int]]] = None,
                 cycle_length: int = 225):
        if key_colors is None:
            self.key_colors = [
                (255, 0, 0, 255),
                (255, 127, 0, 255),
                (255, 255, 0, 255),
                (0, 255, 0, 255),
                (0, 255, 255, 255),
                (0, 0, 255, 255),
                (127, 0, 255, 255)
            ]
        else:
            self.key_colors = key_colors

        self.cycle_length = cycle_length

        if self.key_colors and len(self.key_colors) > 1:
            self.extended_colors = self.key_colors + [self.key_colors[0]]
        else:
            self.extended_colors = self.key_colors

    def get_gradient_color(self, position: float) -> Tuple[int, int, int, int]:
        """通过关键颜色插值获取渐变颜色"""
        if not self.extended_colors or len(self.extended_colors) <= 1:
            return (255, 255, 255, 255) if not self.extended_colors else self.extended_colors[0]

        t = position / self.cycle_length
        t = t % 1.0

        segment = t * (len(self.key_colors) - 1)

        idx1 = int(math.floor(segment))
        idx2 = idx1 + 1

        if idx1 < 0:
            idx1 = 0
        if idx2 >= len(self.extended_colors):
            idx2 = len(self.extended_colors) - 1

        if idx1 == idx2:
            return self.extended_colors[idx1]

        ratio = segment - idx1

        color1 = self.extended_colors[idx1]
        color2 = self.extended_colors[idx2]

        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        a = int(color1[3] * (1 - ratio) + color2[3] * ratio)

        return (r, g, b, a)

    def get_smooth_gradient_color(self, position: float) -> Tuple[int, int, int, int]:
        """通过HSV色彩空间获取平滑渐变颜色"""
        if not self.key_colors or len(self.key_colors) <= 1:
            return (255, 255, 255, 255) if not self.key_colors else self.key_colors[0]

        t = position / self.cycle_length
        angle = t * 2 * math.pi
        hue = (angle / (2 * math.pi)) % 1.0

        saturation = 1.0
        value = 1.0

        rgb = colorsys.hsv_to_rgb(hue, saturation, value)

        r = int(rgb[0] * 255)
        g = int(rgb[1] * 255)
        b = int(rgb[2] * 255)
        a = 255

        return (r, g, b, a)