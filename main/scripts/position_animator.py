#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import random
from typing import Tuple, Dict


class PositionAnimator:
    """元素位置动画管理器，支持平滑正弦和随机平滑动画"""

    def __init__(self, total_images: int, animation_type: str = "smooth",
                 amplitude: int = 50, speed: float = 0.1,
                 movement_speed: float = None):
        self.total_images = total_images
        self.animation_type = animation_type
        self.amplitude = amplitude
        self.speed = (speed if movement_speed is None else movement_speed) * 0.01

        self.phase_offsets = {
            'code': random.random() * 2 * math.pi,
            'name': random.random() * 2 * math.pi,
            'block': random.random() * 2 * math.pi,
            'font': random.random() * 2 * math.pi,
            'content': random.random() * 2 * math.pi
        }

        self.frequency_offsets = {
            'code': random.uniform(0.9, 1.1),
            'name': random.uniform(0.9, 1.1),
            'block': random.uniform(0.9, 1.1),
            'font': random.uniform(0.9, 1.1),
            'content': random.uniform(0.9, 1.1)
        }

    def get_position_offset(self, index: int, base_x: int, base_y: int,
                            element_type: str = "text") -> Tuple[int, int]:
        """获取指定索引和元素类型的位置偏移量"""
        if self.animation_type == "none":
            return (base_x, base_y)

        phase_offset = self.phase_offsets.get(element_type, random.random() * 2 * math.pi)
        frequency = self.frequency_offsets.get(element_type, 1.0)

        t = index * self.speed * frequency + phase_offset

        if self.animation_type == "smooth":
            dx = int(math.sin(t) * self.amplitude)
            dy = int(math.cos(t * 0.7) * self.amplitude * 0.8)
        elif self.animation_type == "random_smooth":
            dx = int(math.sin(t * 1.3) * self.amplitude * 0.5 +
                     math.cos(t * 0.5) * self.amplitude * 0.3 +
                     math.sin(t * 0.2) * self.amplitude * 0.2)
            dy = int(math.cos(t * 0.9) * self.amplitude * 0.4 +
                     math.sin(t * 0.3) * self.amplitude * 0.4 +
                     math.cos(t * 0.1) * self.amplitude * 0.2)
        else:
            dx = 0
            dy = 0

        max_offset = self.amplitude * 2
        dx = max(-max_offset, min(max_offset, dx))
        dy = max(-max_offset, min(max_offset, dy))

        return (base_x + dx, base_y + dy)