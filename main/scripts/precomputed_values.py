#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class PrecomputedValues:
    """预计算常用值以避免重复计算"""

    def __init__(self, cfg, scale_factor: float = 1.0):
        # 使用缩放后的配置
        if hasattr(cfg, 'scaled'):
            self.W, self.H = cfg.image_size
            self.bottom_font_size = cfg.bottom_font_size
            self.middle_font_size = cfg.middle_font_size
        else:
            self.W, self.H = cfg.image_size
            self.bottom_font_size = cfg.bottom_font_size
            self.middle_font_size = cfg.middle_font_size

        self.center_x = self.W // 2
        self.center_y = self.H // 2
        self.bottom_text_y = self.H - self.bottom_font_size - int(125 * scale_factor)
        self.baseline_offset = int(cfg.text_position[1] * scale_factor)
        self.text_x_offset = int(cfg.text_position[0] * scale_factor)
        self.alpha = cfg.middle_font_color[3] / 255
        self.fg_color = tuple(int(c) for c in cfg.middle_font_color[:3])
        self.overlay_alpha = self.alpha * 0.5

        # 统一边距和间距
        self.padding = int(20 * scale_factor)
        self.line_spacing = int(8 * scale_factor)
        self.element_spacing = int(15 * scale_factor)

        # 左上角位置
        self.top_left = (self.padding, self.padding)
        self.top_y = self.padding

        # 右上角位置
        self.top_right_x = self.W - self.padding

        # 底部区域
        self.bottom_margin = self.padding

        # 字体名位置 - 最底部
        self.font_name_y = self.H - self.bottom_font_size - self.bottom_margin
        self.font_name_pos = (self.padding, self.font_name_y)

        # 区块名位置 - 在字体名上方
        self.block_name_y = self.font_name_y - self.bottom_font_size - self.line_spacing
        self.block_name_pos = (self.padding, self.block_name_y)

        # 右下角信息区域
        self.info_right_margin = self.padding
        self.info_bottom_margin = self.bottom_margin
        self.info_line_height = self.bottom_font_size + self.line_spacing
        self.info_max_width = self.W // 3
        self.info_bottom_y = self.font_name_y + self.bottom_font_size
        self.info_start_y = self.info_bottom_y

        # 正上方编码信息位置
        self.encoding_y = self.padding + self.bottom_font_size
        self.encoding_line_height = self.bottom_font_size + self.line_spacing

        # ========== 新的布局：左右竖进度条 ==========

        # 进度条尺寸
        self.progress_bar_width = max(int(15 * scale_factor), 10)  # 进度条宽度（水平方向）
        self.progress_bar_height = self.H // 4  # 进度条高度（垂直方向）

        # 左右进度条的X坐标
        self.left_progress_x = self.padding
        self.right_progress_x = self.W - self.progress_bar_width - self.padding

        # 进度条的Y坐标 - 从顶部码位下方开始，到底部信息上方结束
        self.progress_top_margin = self.padding + self.bottom_font_size * 2 + self.line_spacing * 2
        self.progress_bottom_margin = self.H - self.bottom_font_size * 2 - self.padding - self.line_spacing * 3

        # 进度条的起始Y位置
        self.progress_start_y = self.progress_top_margin
        self.progress_end_y = self.progress_bottom_margin

        # 实际进度条高度
        self.progress_actual_height = self.progress_end_y - self.progress_start_y

        # 百分比文本位置 - 在进度条旁边（左右侧）
        self.percent_spacing = self.element_spacing

        # ========== 底部转圈加载（字符串切换） ==========

        # 转圈圈位置 - 底部正中，在字体名和区块名之间
        spinner_bbox_height = self.bottom_font_size + self.line_spacing
        # 放在字体名上方，留出一些间距
        self.spinner_y = self.font_name_y - spinner_bbox_height - self.line_spacing * 2

        # 底部转圈区域宽度 - 使用画布宽度的2/3，确保有足够空间
        self.bottom_spinner_width = int(self.W * 2 // 3)
        self.spinner_start_x = (self.W - self.bottom_spinner_width) // 2
        self.spinner_end_x = self.spinner_start_x + self.bottom_spinner_width