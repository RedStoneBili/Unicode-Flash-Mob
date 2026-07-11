#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, messagebox, simpledialog


class UnicodeFlashMobGUI:
    def __init__(self, root):
        self.root = root
        root.title("Unicode Flash Mob 命令生成器")
        root.geometry("1100x780")
        root.resizable(True, True)

        self.step_vars = {i: tk.BooleanVar(value=False) for i in range(1, 9)}

        self.write_settings_var = tk.BooleanVar(value=False)
        self.process_block_var = tk.BooleanVar(value=False)
        self.process_data_var = tk.BooleanVar(value=False)

        self.list_gen_mode = tk.StringVar(value='extract')

        self.extract_slots_text = None
        self.extract_mode_var = tk.StringVar(value='any')
        self.extract_style_var = tk.StringVar(value='fallback')
        self.extract_out_var = tk.StringVar(value='combined_unicode_list.txt')

        self.range_start_var = tk.StringVar(value='0000')
        self.range_end_var = tk.StringVar(value='10FFFF')
        self.range_font_var = tk.StringVar(value='font.ttf')
        self.range_out_var = tk.StringVar(value='combined_unicode_list.txt')

        self.replace_mode = tk.StringVar(value='3')

        self.bg_mode = tk.StringVar(value='dynamic')
        self.gradient_cycle_var = tk.StringVar(value='100')
        self.gradient_type_var = tk.StringVar(value='smooth')
        self.gradient_colors_var = tk.StringVar(value='')
        self.flash_color_var = tk.StringVar(value='')

        self.animate_vars = {
            'code': tk.BooleanVar(value=False),
            'name': tk.BooleanVar(value=False),
            'block': tk.BooleanVar(value=False),
            'font': tk.BooleanVar(value=False),
            'content': tk.BooleanVar(value=False)
        }
        self.animation_type_var = tk.StringVar(value='smooth')
        self.amplitude_var = tk.StringVar(value='50')
        self.movement_speed_var = tk.StringVar(value='0.1')
        self.animation_speed_var = tk.StringVar(value='1.0')

        self.info_vars = {
            '显示编码': tk.BooleanVar(value=False),
            '显示区块内位置': tk.BooleanVar(value=False),
            '显示全局位置': tk.BooleanVar(value=False),
            '显示区块进度条': tk.BooleanVar(value=False),
            '显示全局进度条': tk.BooleanVar(value=False),
            '显示 NamesList 详细信息': tk.BooleanVar(value=False),
            '禁用组合标记覆盖': tk.BooleanVar(value=False),
        }

        self.show_spinner_var = tk.BooleanVar(value=False)
        self.spinner_strings_var = tk.StringVar(value='-,\\,|,/')
        self.spinner_step_var = tk.StringVar(value='1')

        self.content_pos_var = tk.StringVar(value='center')
        self.offset_x_var = tk.StringVar(value='0')
        self.offset_y_var = tk.StringVar(value='0')
        self.scale_var = tk.StringVar(value='1.0')
        self.shuffle_var = tk.BooleanVar(value=False)

        self.workers_var = tk.StringVar(value='8')
        self.png_quality_var = tk.StringVar(value='balanced')
        self.force_var = tk.BooleanVar(value=False)

        self.open_output_var = tk.BooleanVar(value=False)
        self.cleanup_var = tk.BooleanVar(value=False)

        self.create_widgets()
        self.update_command()

    def create_widgets(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(top_frame, text="生成命令", command=self.update_command).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="复制命令", command=self.copy_command).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="运行选中步骤", command=self.run_selected_steps).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="清空选择", command=self.clear_all).pack(side=tk.LEFT, padx=5)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.build_step1()
        self.build_step2()
        self.build_step3()
        self.build_step4()
        self.build_step5()
        self.build_step6()
        self.build_step7()
        self.build_step8()

        output_frame = tk.LabelFrame(self.root, text="生成的命令（可编辑）")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.cmd_output = scrolledtext.ScrolledText(output_frame, height=12, wrap=tk.WORD, font=("Consolas", 10))
        self.cmd_output.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.output_window = None

    def add_step_check(self, parent, step_num, text, var=None):
        if var is None:
            var = self.step_vars[step_num]
        cb = tk.Checkbutton(parent, text=text, variable=var, command=self.update_command)
        cb.pack(anchor=tk.W, padx=5, pady=2)
        return cb

    def add_label_entry(self, parent, label, var):
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(frame, text=label, width=20, anchor='w').pack(side=tk.LEFT)
        entry = tk.Entry(frame, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return entry

    def add_label_combobox(self, parent, label, values, var, display_values=None):
        frame = tk.Frame(parent)
        frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(frame, text=label, width=20, anchor='w').pack(side=tk.LEFT)
        if display_values is None:
            display_values = values
        cb = ttk.Combobox(frame, textvariable=var, values=values, state="readonly")
        cb.pack(side=tk.LEFT, fill=tk.X, expand=True)
        cb.bind('<<ComboboxSelected>>', lambda e: self.update_command())
        return cb

    def add_checkbox(self, parent, text, var):
        cb = tk.Checkbutton(parent, text=text, variable=var, command=self.update_command)
        cb.pack(anchor=tk.W, padx=5, pady=2)
        return cb

    def build_step1(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤1: 下载")
        self.add_step_check(frame, 1, "下载 UnicodeData.txt, Blocks.txt, NamesList.txt")
        tk.Label(frame, text="命令: ./unicode_flash_mob.exe download", fg="green", font=("Consolas", 9))\
            .pack(anchor=tk.W, padx=20, pady=5)

    def build_step2(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤2: 配置处理")
        self.add_step_check(frame, 2, "重置 Module.py (write-settings)", var=self.write_settings_var)
        self.add_step_check(frame, 2, "处理 Unicode 区块 (process-unicode-block)", var=self.process_block_var)
        self.add_step_check(frame, 2, "处理 Unicode 数据 (process-unicode-data)", var=self.process_data_var)

    def build_step3(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤3: 生成列表")
        self.add_step_check(frame, 3, "生成字符列表")

        radio_frame = tk.Frame(frame)
        radio_frame.pack(anchor=tk.W, padx=20, pady=5)
        tk.Radiobutton(radio_frame, text="从字体提取", variable=self.list_gen_mode, value='extract',
                       command=lambda: (self.toggle_range_extract(), self.update_command())).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(radio_frame, text="从Unicode范围生成", variable=self.list_gen_mode, value='range',
                       command=lambda: (self.toggle_range_extract(), self.update_command())).pack(side=tk.LEFT, padx=5)

        self.extract_frame = tk.LabelFrame(frame, text="字体提取设置")
        self.extract_frame.pack(fill=tk.X, padx=20, pady=5)

        style_frame = tk.Frame(self.extract_frame)
        style_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(style_frame, text="字体使用样式", width=20, anchor='w').pack(side=tk.LEFT)
        self.style_combobox = ttk.Combobox(style_frame, textvariable=self.extract_style_var,
                                           values=['fallback', 'compare'], state="readonly")
        self.style_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.style_combobox.bind('<<ComboboxSelected>>', lambda e: (self.toggle_mode_for_style(), self.update_command()))

        self.mode_frame = tk.Frame(self.extract_frame)
        self.mode_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.mode_frame, text="提取模式", width=20, anchor='w').pack(side=tk.LEFT)
        self.mode_combobox = ttk.Combobox(self.mode_frame, textvariable=self.extract_mode_var,
                                          values=['any', 'all'], state="readonly")
        self.mode_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.mode_combobox.bind('<<ComboboxSelected>>', lambda e: self.update_command())

        self.extract_slots_label = tk.Label(self.extract_frame, text="字体槽位（每行一个，格式: font.ttf 或 (font1,font2)）")
        self.extract_slots_label.pack(anchor=tk.W, padx=5)
        self.extract_slots_text = tk.Text(self.extract_frame, height=4, width=50)
        self.extract_slots_text.insert("1.0", "font.ttf")
        self.extract_slots_text.pack(fill=tk.X, padx=5, pady=5)
        self.extract_slots_text.bind("<KeyRelease>", lambda e: self.update_command())

        self.add_label_entry(self.extract_frame, "输出文件名", self.extract_out_var)

        self.toggle_mode_for_style()

        self.range_frame = tk.LabelFrame(frame, text="Unicode范围生成设置")
        self.range_frame.pack(fill=tk.X, padx=20, pady=5)
        self.add_label_entry(self.range_frame, "起始码位 (hex)", self.range_start_var)
        self.add_label_entry(self.range_frame, "结束码位 (hex)", self.range_end_var)
        self.add_label_entry(self.range_frame, "字体路径", self.range_font_var)
        self.add_label_entry(self.range_frame, "输出文件名", self.range_out_var)

        self.toggle_range_extract()

    def toggle_mode_for_style(self):
        if self.extract_style_var.get() == 'fallback':
            self.mode_combobox.config(state='disabled')
            self.mode_frame.config(bg='#f0f0f0')
            self.extract_slots_label.config(text="字体槽位（每行一个，只支持单字体，不支持括号组）")
        else:
            self.mode_combobox.config(state='readonly')
            self.mode_frame.config(bg=self.root.cget('bg'))
            self.extract_slots_label.config(text="字体槽位（每行一个，格式: font.ttf 或 (font1,font2)）")

    def toggle_range_extract(self):
        if self.list_gen_mode.get() == 'extract':
            self.extract_frame.pack(fill=tk.X, padx=20, pady=5)
            self.range_frame.pack_forget()
        else:
            self.range_frame.pack(fill=tk.X, padx=20, pady=5)
            self.extract_frame.pack_forget()

    def build_step4(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤4: 重命名")
        self.add_step_check(frame, 4, "重命名为 Unicode.txt")
        tk.Label(frame, text='命令: Rename-Item "combined_unicode_list.txt" "Unicode.txt" -ErrorAction Stop',
                 fg="green", font=("Consolas", 9)).pack(anchor=tk.W, padx=20, pady=5)

    def build_step5(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤5: 注入描述")
        self.add_step_check(frame, 5, "注入描述信息")
        radio_frame = tk.Frame(frame)
        radio_frame.pack(anchor=tk.W, padx=20, pady=5)
        tk.Radiobutton(radio_frame, text="仅区块名 (1)", variable=self.replace_mode, value='1',
                       command=self.update_command).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(radio_frame, text="仅字符名 (2)", variable=self.replace_mode, value='2',
                       command=self.update_command).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(radio_frame, text="区块|字符名 (3) 推荐", variable=self.replace_mode, value='3',
                       command=self.update_command).pack(side=tk.LEFT, padx=5)

    def build_step6(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤6: 生成PNG")
        self.add_step_check(frame, 6, "生成 PNG 图片")

        bg_frame = tk.LabelFrame(frame, text="背景颜色模式")
        bg_frame.pack(fill=tk.X, padx=10, pady=5)
        for mode, label in [('dynamic','动态背景'), ('fixed','固定背景'), ('random','完全随机'), ('rainbow','彩虹渐变')]:
            rb = tk.Radiobutton(bg_frame, text=label, variable=self.bg_mode, value=mode,
                                command=lambda m=mode: (self.toggle_rainbow(), self.update_command()))
            rb.pack(anchor=tk.W, padx=10)

        self.rainbow_frame = tk.LabelFrame(frame, text="彩虹渐变配置")
        self.rainbow_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_label_entry(self.rainbow_frame, "渐变周期(张)", self.gradient_cycle_var)
        self.add_label_combobox(self.rainbow_frame, "渐变类型", ['smooth', 'interpolate'], self.gradient_type_var)
        self.add_label_entry(self.rainbow_frame, "自定义关键颜色(R,G,B,A;...)", self.gradient_colors_var)

        anim_frame = tk.LabelFrame(frame, text="动画效果")
        anim_frame.pack(fill=tk.X, padx=10, pady=5)
        anim_elems_frame = tk.Frame(anim_frame)
        anim_elems_frame.pack(anchor=tk.W, padx=5, pady=2)
        for elem in ['code','name','block','font','content']:
            cb = tk.Checkbutton(anim_elems_frame, text=elem, variable=self.animate_vars[elem],
                                command=self.update_command)
            cb.pack(side=tk.LEFT, padx=5)

        self.add_label_combobox(anim_frame, "动画类型", ['smooth', 'random_smooth'], self.animation_type_var)
        self.add_label_entry(anim_frame, "幅度(像素)", self.amplitude_var)
        self.add_label_entry(anim_frame, "飘动速度", self.movement_speed_var)
        self.add_label_entry(anim_frame, "颜色变化速度", self.animation_speed_var)

        info_frame = tk.LabelFrame(frame, text="信息显示")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        for label, var in self.info_vars.items():
            self.add_checkbox(info_frame, label.replace('_', ' ').title(), var)

        spinner_frame = tk.LabelFrame(frame, text="底部转圈动画")
        spinner_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_checkbox(spinner_frame, "启用转圈", self.show_spinner_var)
        self.add_label_entry(spinner_frame, "动画字符串(逗号分隔)", self.spinner_strings_var)
        self.add_label_entry(spinner_frame, "切换间隔(张)", self.spinner_step_var)

        layout_frame = tk.LabelFrame(frame, text="布局控制")
        layout_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_label_combobox(layout_frame, "内容位置", ['center', 'fixed', 'random'], self.content_pos_var)
        self.add_label_entry(layout_frame, "偏移X (fixed)", self.offset_x_var)
        self.add_label_entry(layout_frame, "偏移Y (fixed)", self.offset_y_var)
        self.add_label_entry(layout_frame, "缩放因子", self.scale_var)
        self.add_checkbox(layout_frame, "文件名随机化", self.shuffle_var)

        perf_frame = tk.LabelFrame(frame, text="性能与输出")
        perf_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_label_entry(perf_frame, "并发线程数", self.workers_var)
        self.add_label_combobox(perf_frame, "PNG质量", ['fast', 'balanced', 'best'], self.png_quality_var)
        self.add_checkbox(perf_frame, "强制重新生成", self.force_var)

        flash_frame = tk.LabelFrame(frame, text="闪出颜色 (覆盖背景)")
        flash_frame.pack(fill=tk.X, padx=10, pady=5)
        self.add_label_entry(flash_frame, "颜色 (R,G,B,A)", self.flash_color_var)

        self.toggle_rainbow()

    def toggle_rainbow(self):
        if self.bg_mode.get() == 'rainbow':
            self.rainbow_frame.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.rainbow_frame.pack_forget()

    def build_step7(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤7: 生成MP4")
        self.add_step_check(frame, 7, "生成 MP4 视频")
        tk.Label(frame, text='命令: .\\python\\python.exe ".\\scripts\\generate_mp4.py"',
                 fg="green", font=("Consolas", 9)).pack(anchor=tk.W, padx=20, pady=5)

    def build_step8(self):
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="步骤8: 清理")
        self.add_step_check(frame, 8, "打开输出目录", var=self.open_output_var)
        self.add_step_check(frame, 8, "清理临时文件", var=self.cleanup_var)
        tk.Label(frame, text="命令: Start-Process .\\output", fg="green", font=("Consolas", 9))\
            .pack(anchor=tk.W, padx=20, pady=2)
        tk.Label(frame, text='命令: Remove-Item "Unicode.txt","color_state.json" -Force -ErrorAction SilentlyContinue',
                 fg="green", font=("Consolas", 9)).pack(anchor=tk.W, padx=20, pady=2)

    def update_command(self):
        selected_steps = [i for i in range(1, 9) if self.step_vars[i].get()]
        if not selected_steps:
            self.cmd_output.delete(1.0, tk.END)
            self.cmd_output.insert(tk.END, "# 请勾选至少一个步骤")
            return

        lines = ["# Unicode Flash Mob 命令序列",
                 f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 ""]

        for step in sorted(selected_steps):
            cmds = self.generate_step_commands(step)
            if cmds:
                lines.append(f"# 步骤 {step}")
                for cmd in cmds:
                    lines.append(cmd)
                lines.append("")

        self.cmd_output.delete(1.0, tk.END)
        self.cmd_output.insert(tk.END, "\n".join(lines))

    def generate_step_commands(self, step):
        if step == 1:
            return ["./unicode_flash_mob.exe download"]

        if step == 2:
            cmds = []
            if self.write_settings_var.get():
                cmds.append("./unicode_flash_mob.exe write-settings")
            if self.process_block_var.get():
                cmds.append("./unicode_flash_mob.exe process-unicode-block")
            if self.process_data_var.get():
                cmds.append("./unicode_flash_mob.exe process-unicode-data")
            return cmds

        if step == 3:
            mode = self.list_gen_mode.get()
            if mode == 'extract':
                text = self.extract_slots_text.get("1.0", tk.END).strip()
                slots = [line.strip() for line in text.splitlines() if line.strip()]
                if not slots:
                    return ["# 错误: 未输入任何字体槽位"]
                pos_args = ' '.join([f'"{s}"' for s in slots])
                out = self.extract_out_var.get().strip() or "combined_unicode_list.txt"
                mode_val = self.extract_mode_var.get()
                style_val = self.extract_style_var.get()
                cmd = f'./unicode_flash_mob.exe extract {pos_args} --out "{out}" --style {style_val}'
                if style_val != 'fallback':
                    cmd += f' --mode {mode_val}'
                return [cmd]
            else:
                start = self.range_start_var.get().strip() or "0000"
                end = self.range_end_var.get().strip() or "10FFFF"
                font = self.range_font_var.get().strip() or "font.ttf"
                out = self.range_out_var.get().strip() or "combined_unicode_list.txt"
                return [f'./unicode_flash_mob.exe generate-unicode-range --file "{out}" --start {start} --end {end} --font "{font}"']

        if step == 4:
            return ['Rename-Item "combined_unicode_list.txt" "Unicode.txt" -ErrorAction Stop']

        if step == 5:
            return [f'./unicode_flash_mob.exe replace-unicode-data {self.replace_mode.get()}']

        if step == 6:
            args = []
            bg = self.bg_mode.get()
            if bg == 'dynamic':
                args.append('--dynamic-bg')
            elif bg == 'random':
                args.append('--random-color')
            elif bg == 'rainbow':
                args.append('--rainbow-gradient')
                args.append(f'--gradient-cycle {self.gradient_cycle_var.get() or 100}')
                if self.gradient_type_var.get() == 'interpolate':
                    args.append('--no-smooth-gradient')
                colors = self.gradient_colors_var.get().strip()
                if colors:
                    args.append(f'--gradient-colors "{colors}"')

            flash = self.flash_color_var.get().strip()
            if flash:
                args.append(f'--flash-color "{flash}"')

            anim_elems = [k for k, v in self.animate_vars.items() if v.get()]
            if anim_elems:
                args.append(f'--animate-elements {",".join(anim_elems)}')
                args.append(f'--animation-type {self.animation_type_var.get()}')
                args.append(f'--animation-amplitude {self.amplitude_var.get() or 50}')
                args.append(f'--movement-speed {self.movement_speed_var.get() or 0.1}')
                args.append(f'--animation-speed {self.animation_speed_var.get() or 1.0}')

            for flag, var in self.info_vars.items():
                if var.get():
                    args.append('--' + flag.replace('_', '-'))

            if self.show_spinner_var.get():
                args.append('--show-side-spinner')
                args.append(f'--spinner-strings "{self.spinner_strings_var.get() or "-,\\,|,/"}"')
                args.append(f'--spinner-step-interval {self.spinner_step_var.get() or 1}')

            pos = self.content_pos_var.get()
            if pos == 'random':
                args.append('--content-position random')
            elif pos == 'fixed':
                x = self.offset_x_var.get().strip() or '0'
                y = self.offset_y_var.get().strip() or '0'
                args.append(f'--content-position fixed,{x},{y}')

            scale = self.scale_var.get().strip()
            if scale and scale != '1.0':
                args.append(f'--scale {scale}')

            if self.shuffle_var.get():
                args.append('--shuffle-content')
            if self.force_var.get():
                args.append('--force')
            args.append(f'--workers {self.workers_var.get() or 8}')
            args.append(f'--png-quality {self.png_quality_var.get()}')

            return [f'.\\python\\python.exe ".\\scripts\\generate_png.py" {" ".join(args)}']

        if step == 7:
            return ['.\\python\\python.exe ".\\scripts\\generate_mp4.py"']

        if step == 8:
            cmds = []
            if self.open_output_var.get():
                cmds.append('Start-Process .\\output')
            if self.cleanup_var.get():
                cmds.append('Remove-Item "Unicode.txt","color_state.json" -Force -ErrorAction SilentlyContinue')
            return cmds

        return []

    def copy_command(self):
        text = self.cmd_output.get(1.0, tk.END).strip()
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("复制成功", "命令已复制到剪贴板")

    def clear_all(self):
        for var in self.step_vars.values():
            var.set(False)
        self.write_settings_var.set(False)
        self.process_block_var.set(False)
        self.process_data_var.set(False)
        self.open_output_var.set(False)
        self.cleanup_var.set(False)
        self.cmd_output.delete(1.0, tk.END)
        self.cmd_output.insert(tk.END, "# 已清空选择")

    def run_selected_steps(self):
        text = self.cmd_output.get(1.0, tk.END).strip()
        if not text or text.startswith("# 请勾选"):
            messagebox.showwarning("警告", "请先生成命令并勾选步骤")
            return

        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#')]
        if not lines:
            messagebox.showwarning("警告", "没有可执行的命令")
            return

        mp4_inputs = {}
        if any('generate_mp4.py' in line for line in lines):
            video_name = simpledialog.askstring("输入", "请输入输出视频名称（不含扩展名）:", parent=self.root)
            if video_name is None:
                return
            frame_rate = simpledialog.askstring("输入", "请输入帧率（默认30）:", parent=self.root, initialvalue="30")
            if frame_rate is None:
                return
            mp4_inputs['video_name'] = video_name
            mp4_inputs['frame_rate'] = frame_rate

        win = tk.Toplevel(self.root)
        win.title("运行输出")
        win.geometry("800x500")
        output_text = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10))
        output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def runner():
            for cmd in lines:
                output_text.insert(tk.END, f">>> {cmd}\n")
                output_text.see(tk.END)
                if 'generate_mp4.py' in cmd:
                    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            stdin=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True)
                    try:
                        outs, _ = proc.communicate(input=f"{mp4_inputs['video_name']}\n{mp4_inputs['frame_rate']}\n", timeout=600)
                        output_text.insert(tk.END, outs)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        output_text.insert(tk.END, "\n!!! 执行超时\n")
                else:
                    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, bufsize=1, universal_newlines=True)
                    for line in proc.stdout:
                        output_text.insert(tk.END, line)
                        output_text.see(tk.END)
                    proc.wait()
                output_text.insert(tk.END, f"\n>>> 命令完成 (返回码: {proc.returncode})\n")
                output_text.see(tk.END)
            output_text.insert(tk.END, "\n所有步骤执行完毕。")

        threading.Thread(target=runner, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = UnicodeFlashMobGUI(root)
    root.mainloop()