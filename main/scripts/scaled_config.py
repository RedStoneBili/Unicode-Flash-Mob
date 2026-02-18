#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class ScaledConfig:
    """等比缩放配置"""

    def __init__(self, base_cfg, scale_factor: float):
        self.base_cfg = base_cfg
        self.scale_factor = scale_factor

        # 等比缩放所有尺寸相关参数
        self.image_size = (
            int(base_cfg.image_size[0] * scale_factor),
            int(base_cfg.image_size[1] * scale_factor)
        )
        self.middle_font_size = int(base_cfg.middle_font_size * scale_factor)
        self.bottom_font_size = int(base_cfg.bottom_font_size * scale_factor)
        self.text_position = (
            int(base_cfg.text_position[0] * scale_factor),
            int(base_cfg.text_position[1] * scale_factor)
        )

        # 其他参数保持不变
        self.output_dir = base_cfg.output_dir
        self.unicode_file = base_cfg.unicode_file
        self.font_files = base_cfg.font_files
        self.bottom_font_file = base_cfg.bottom_font_file
        self.ctrl_font_file = base_cfg.ctrl_font_file
        self.middle_font_color = base_cfg.middle_font_color
        self.background_color = base_cfg.background_color
        self.color_cycle = base_cfg.color_cycle
        self.png_compress_level = base_cfg.png_compress_level
        self.png_optimize = base_cfg.png_optimize

        # 标记为缩放配置
        self.scaled = True