#!/usr/bin/env python3
# -*- coding: utf-8 -*-


class PrecomputedValues:
    def __init__(self, cfg, scale_factor: float = 1.0):
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

        self.padding = int(20 * scale_factor)
        self.line_spacing = int(8 * scale_factor)
        self.element_spacing = int(15 * scale_factor)

        self.top_left = (self.padding, self.padding)
        self.top_y = self.padding

        self.top_right_x = self.W - self.padding

        self.bottom_margin = self.padding

        self.font_name_y = self.H - self.bottom_font_size - self.bottom_margin
        self.font_name_pos = (self.padding, self.font_name_y)

        self.block_name_y = self.font_name_y - self.bottom_font_size - self.line_spacing
        self.block_name_pos = (self.padding, self.block_name_y)

        self.info_right_margin = self.padding
        self.info_bottom_margin = self.bottom_margin
        self.info_line_height = self.bottom_font_size + self.line_spacing
        self.info_max_width = self.W // 3
        self.info_bottom_y = self.font_name_y + self.bottom_font_size
        self.info_start_y = self.info_bottom_y

        self.encoding_y = self.padding + self.bottom_font_size
        self.encoding_line_height = self.bottom_font_size + self.line_spacing

        self.progress_bar_width = max(int(15 * scale_factor), 10)
        self.progress_bar_height = self.H // 4

        self.left_progress_x = self.padding
        self.right_progress_x = self.W - self.progress_bar_width - self.padding

        self.progress_top_margin = self.padding + self.bottom_font_size * 2 + self.line_spacing * 2
        self.progress_bottom_margin = self.H - self.bottom_font_size * 2 - self.padding - self.line_spacing * 3

        self.progress_start_y = self.progress_top_margin
        self.progress_end_y = self.progress_bottom_margin

        self.progress_actual_height = self.progress_end_y - self.progress_start_y

        self.percent_spacing = self.element_spacing

        spinner_bbox_height = self.bottom_font_size + self.line_spacing
        self.spinner_y = self.font_name_y - spinner_bbox_height - self.line_spacing * 2

        self.bottom_spinner_width = int(self.W * 2 // 3)
        self.spinner_start_x = (self.W - self.bottom_spinner_width) // 2
        self.spinner_end_x = self.spinner_start_x + self.bottom_spinner_width

        self.multi_font_slot_width = int(self.middle_font_size)
        self.multi_font_spacing = int(15 * scale_factor)
        self.multi_font_total_width = self.multi_font_slot_width