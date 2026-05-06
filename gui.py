# -*- coding: utf-8 -*-
"""
番茄小说自动发布系统 - GUI 可视化界面
基于 PyQt5 构建的现代化控制面板
"""

import sys
import os
import re
import importlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, 
                             QFormLayout, QTextEdit, QScrollArea, QFileDialog,
                             QDateTimeEdit, QMessageBox, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QDateTime, QTime
from PyQt5.QtGui import QFont, QColor, QTextCursor, QIcon, QPalette

import config

STYLE_SHEET = """
QMainWindow {
    background-color: #f4f6f8;
    font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
}
QGroupBox {
    background-color: #ffffff;
    color: #2f3542;
    font-weight: bold;
    font-size: 14px;
    border: 1px solid #e4e9f0;
    border-radius: 10px;
    margin-top: 24px;
    padding: 20px 15px 15px 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    padding: 4px 12px;
    background-color: #ff4757;
    color: #ffffff;
    border-radius: 6px;
    margin-top: -12px;
}
QLabel {
    color: #57606f;
    font-size: 13px;
    font-weight: 500;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QDateTimeEdit {
    background-color: #f8f9fa;
    color: #2f3542;
    border: 1.5px solid #e4e9f0;
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 13px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateTimeEdit:focus {
    border: 1.5px solid #ff4757;
    background-color: #ffffff;
}
QPushButton {
    background-color: #ffffff;
    color: #2f3542;
    font-weight: bold;
    font-size: 13px;
    border: 1.5px solid #e4e9f0;
    border-radius: 6px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #f1f2f6;
    border-color: #ced6e0;
}
QPushButton:pressed {
    background-color: #e4e9f0;
}
QPushButton#startBtn {
    background-color: #ff4757;
    color: white;
    font-size: 15px;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
}
QPushButton#startBtn:hover {
    background-color: #ff6b81;
}
QPushButton#stopBtn {
    background-color: #747d8c;
    color: white;
    font-size: 15px;
    border: none;
    padding: 12px 20px;
    border-radius: 8px;
}
QPushButton#stopBtn:hover {
    background-color: #a4b0be;
}
QPushButton#saveBtn {
    background-color: #2ed573;
    color: white;
    font-size: 14px;
    border: none;
    padding: 12px;
    border-radius: 8px;
    margin-top: 10px;
}
QPushButton#saveBtn:hover {
    background-color: #7bed9f;
}
QTextEdit {
    background-color: #ffffff;
    color: #2f3542;
    border: 1px solid #e4e9f0;
    border-radius: 10px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    padding: 12px;
}
QCheckBox {
    color: #2f3542;
    font-size: 13px;
    font-weight: bold;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #ced6e0;
    border-radius: 4px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #ff4757;
    border-color: #ff4757;
}
QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
}
QScrollBar::handle:vertical {
    background: #ced6e0;
    min-height: 20px;
    border-radius: 3px;
}
"""

import subprocess

class UploaderThread(QThread):
    """后台运行上传任务的线程"""
    log_signal = pyqtSignal(str, str)  # msg, color
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_running = True
        self.process = None

    def run(self):
        try:
            self.log_signal.emit("✅ 准备启动自动化进程...", "#2ed573")
            
            # 使用 subprocess 调用独立的 runner.py 避免 Playwright 的主线程断言错误
            self.process = subprocess.Popen(
                [sys.executable, "runner.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1, # 行缓冲
                universal_newlines=True
            )
            
            # 实时读取输出并发送到 GUI
            for line in iter(self.process.stdout.readline, ''):
                if not self._is_running:
                    self.process.terminate()
                    break
                    
                line = line.strip()
                if not line: continue
                
                # 根据前缀判断颜色
                color = "#57606f"
                if "[SUCCESS]" in line or "✅" in line or "成功" in line:
                    color = "#2ed573"
                elif "[WARNING]" in line or "⚠️" in line:
                    color = "#ffa502"
                elif "[ERROR]" in line or "❌" in line or "失败" in line or "异常" in line:
                    color = "#ff4757"
                
                # 过滤掉丑陋的前缀显示，让界面更清爽
                clean_line = line.replace("[INFO]", "").replace("[SUCCESS]", "").replace("[WARNING]", "").replace("[ERROR]", "").strip()
                if clean_line:
                    self.log_signal.emit(clean_line, color)
                    
            self.process.stdout.close()
            self.process.wait()
            
            if self._is_running:
                if self.process.returncode == 0:
                    self.log_signal.emit("🎉 自动化流程正常结束", "#2ed573")
                else:
                    self.log_signal.emit(f"⚠️ 自动化进程异常退出，状态码: {self.process.returncode}", "#ff4757")
            else:
                self.log_signal.emit("⚠️ 任务已被用户取消", "#ffa502")
                
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

    def stop(self):
        self._is_running = False
        if self.process:
            try:
                self.process.terminate()
            except:
                pass
        self.log_signal.emit("正在停止任务...", "#ffa502")


class FanqieAutoPublisherGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("番茄小说自动化发布系统 - 智能控制面板")
        self.resize(1150, 800)
        self.setStyleSheet(STYLE_SHEET)
        
        self.thread = None
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 整体采用垂直布局，头部为 banner，下方为内容区
        root_layout = QVBoxLayout(main_widget)
        root_layout.setContentsMargins(25, 25, 25, 25)
        root_layout.setSpacing(20)
        
        # 顶部横幅 Banner
        banner_frame = QFrame()
        banner_frame.setStyleSheet("background-color: #ffffff; border-radius: 12px; border: 1px solid #e4e9f0;")
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setContentsMargins(20, 15, 20, 15)
        
        title_label = QLabel("🍅 番茄小说自动化发布系统")
        title_label.setFont(QFont("Microsoft YaHei", 22, QFont.Bold))
        title_label.setStyleSheet("color: #ff4757; border: none;")
        
        subtitle_label = QLabel("智能 · 高效 · 防风控的全自动草稿与定时发布管家")
        subtitle_label.setFont(QFont("Microsoft YaHei", 12))
        subtitle_label.setStyleSheet("color: #a4b0be; border: none;")
        
        banner_text_layout = QVBoxLayout()
        banner_text_layout.addWidget(title_label)
        banner_text_layout.addWidget(subtitle_label)
        banner_layout.addLayout(banner_text_layout)
        banner_layout.addStretch()
        
        root_layout.addWidget(banner_frame)
        
        # 下方的内容区布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(25)

        # ================= 左侧设置面板 =================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 15, 0)
        scroll_layout.setSpacing(15)

        # 1. 基础设置
        group_basic = QGroupBox("基础设置")
        form_basic = QFormLayout(group_basic)
        
        self.work_url_input = QLineEdit()
        self.work_url_input.setPlaceholderText("https://writer.fanqie.com/works/...")
        form_basic.addRow("作品管理 URL:", self.work_url_input)
        
        dir_layout = QHBoxLayout()
        self.chapters_dir_input = QLineEdit()
        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.chapters_dir_input)
        dir_layout.addWidget(self.browse_btn)
        form_basic.addRow("章节文件夹:", dir_layout)
        scroll_layout.addWidget(group_basic)

        # 2. 章节范围
        group_range = QGroupBox("章节范围 (断点续传)")
        form_range = QFormLayout(group_range)
        
        self.start_chap_spin = QSpinBox()
        self.start_chap_spin.setRange(1, 10000)
        form_range.addRow("起始章节号:", self.start_chap_spin)
        
        self.end_chap_spin = QSpinBox()
        self.end_chap_spin.setRange(0, 10000)
        self.end_chap_spin.setToolTip("0 表示上传直到文件夹结束")
        form_range.addRow("结束章节号:", self.end_chap_spin)
        scroll_layout.addWidget(group_range)

        # 3. 定时发布
        group_schedule = QGroupBox("定时发布")
        form_schedule = QFormLayout(group_schedule)
        
        self.schedule_enable_chk = QCheckBox("启用定时发布")
        self.schedule_enable_chk.toggled.connect(self.toggle_schedule_inputs)
        form_schedule.addRow("", self.schedule_enable_chk)
        
        self.schedule_time_edit = QDateTimeEdit()
        self.schedule_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.schedule_time_edit.setCalendarPopup(True)
        form_schedule.addRow("首章发布时间:", self.schedule_time_edit)
        
        self.schedule_interval_spin = QSpinBox()
        self.schedule_interval_spin.setRange(0, 1440)
        self.schedule_interval_spin.setSuffix(" 分钟")
        form_schedule.addRow("章节发布间隔:", self.schedule_interval_spin)
        scroll_layout.addWidget(group_schedule)

        # 4. 发布选项
        group_options = QGroupBox("自动化操作")
        form_options = QFormLayout(group_options)
        
        self.use_ai_chk = QCheckBox("勾选使用 AI")
        self.skip_typo_chk = QCheckBox("跳过错别字检测")
        self.skip_risk_chk = QCheckBox("跳过风险检测")
        form_options.addRow("", self.use_ai_chk)
        form_options.addRow("", self.skip_typo_chk)
        form_options.addRow("", self.skip_risk_chk)
        scroll_layout.addWidget(group_options)

        # 5. 高级设置
        group_adv = QGroupBox("高级延迟参数 (防风控)")
        form_adv = QFormLayout(group_adv)
        
        self.chapter_delay_spin = QDoubleSpinBox()
        self.chapter_delay_spin.setRange(0, 60)
        self.chapter_delay_spin.setSingleStep(0.5)
        self.chapter_delay_spin.setSuffix(" 秒")
        form_adv.addRow("章间等待:", self.chapter_delay_spin)
        
        self.action_delay_spin = QDoubleSpinBox()
        self.action_delay_spin.setRange(0, 10)
        self.action_delay_spin.setSingleStep(0.5)
        self.action_delay_spin.setSuffix(" 秒")
        form_adv.addRow("UI动作等待:", self.action_delay_spin)
        scroll_layout.addWidget(group_adv)

        scroll_area.setWidget(scroll_widget)
        left_layout.addWidget(scroll_area)
        
        # 保存设置按钮
        self.save_btn = QPushButton("💾 保存所有设置")
        self.save_btn.setObjectName("saveBtn")
        self.save_btn.clicked.connect(self.save_settings)
        left_layout.addWidget(self.save_btn)

        content_layout.addWidget(left_panel, 1)

        # ================= 右侧执行面板 =================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # 顶部按钮
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始自动上传")
        self.start_btn.setObjectName("startBtn")
        self.start_btn.clicked.connect(self.start_upload)
        
        self.stop_btn = QPushButton("⏹ 停止当前任务")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_upload)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(self.stop_btn)
        right_layout.addLayout(btn_layout)

        # 日志输出区域
        log_label = QLabel("🚀 运行日志")
        log_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        log_label.setStyleSheet("color: #ff4757;")
        right_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)

        content_layout.addWidget(right_panel, 2)
        
        # 将水平内容区加入根垂直布局
        root_layout.addLayout(content_layout)

    def load_settings(self):
        """从 config.py 加载配置到 UI"""
        importlib.reload(config)
        
        self.work_url_input.setText(getattr(config, 'WORK_URL', ''))
        self.chapters_dir_input.setText(getattr(config, 'CHAPTERS_DIR', ''))
        
        self.start_chap_spin.setValue(getattr(config, 'START_CHAPTER', 1))
        self.end_chap_spin.setValue(getattr(config, 'END_CHAPTER', 0))
        
        self.use_ai_chk.setChecked(getattr(config, 'USE_AI', True))
        self.skip_typo_chk.setChecked(getattr(config, 'SKIP_TYPO_CHECK', True))
        self.skip_risk_chk.setChecked(getattr(config, 'SKIP_RISK_CHECK', True))
        
        self.schedule_enable_chk.setChecked(getattr(config, 'SCHEDULED_PUBLISH', False))
        self.schedule_interval_spin.setValue(getattr(config, 'SCHEDULED_INTERVAL_MINUTES', 60))
        
        time_str = getattr(config, 'SCHEDULED_FIRST_TIME', "2026-05-01 12:00")
        dt = QDateTime.fromString(time_str, "yyyy-MM-dd HH:mm")
        if not dt.isValid():
            dt = QDateTime.currentDateTime()
        self.schedule_time_edit.setDateTime(dt)
        self.toggle_schedule_inputs()
        
        self.chapter_delay_spin.setValue(getattr(config, 'CHAPTER_DELAY', 8.0))
        self.action_delay_spin.setValue(getattr(config, 'ACTION_DELAY', 1.5))

    def toggle_schedule_inputs(self):
        is_checked = self.schedule_enable_chk.isChecked()
        self.schedule_time_edit.setEnabled(is_checked)
        self.schedule_interval_spin.setEnabled(is_checked)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择章节文件夹", self.chapters_dir_input.text())
        if dir_path:
            self.chapters_dir_input.setText(dir_path)

    def save_settings(self):
        """将 UI 配置写回 config.py"""
        settings = {
            'WORK_URL': self.work_url_input.text(),
            'CHAPTERS_DIR': self.chapters_dir_input.text(),
            'START_CHAPTER': self.start_chap_spin.value(),
            'END_CHAPTER': self.end_chap_spin.value(),
            'SCHEDULED_PUBLISH': self.schedule_enable_chk.isChecked(),
            'SCHEDULED_FIRST_TIME': self.schedule_time_edit.dateTime().toString("yyyy-MM-dd HH:mm"),
            'SCHEDULED_INTERVAL_MINUTES': self.schedule_interval_spin.value(),
            'USE_AI': self.use_ai_chk.isChecked(),
            'SKIP_TYPO_CHECK': self.skip_typo_chk.isChecked(),
            'SKIP_RISK_CHECK': self.skip_risk_chk.isChecked(),
            'CHAPTER_DELAY': self.chapter_delay_spin.value(),
            'ACTION_DELAY': self.action_delay_spin.value()
        }
        
        try:
            with open('config.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            for key, val in settings.items():
                if isinstance(val, str):
                    # 使用 repr 自动处理路径中的转义字符（比如 \U 报错）
                    val_str = repr(val)
                else:
                    val_str = str(val)
                
                pattern = rf'^{key}\s*=\s*.*$'
                replacement = f'{key} = {val_str}'
                
                if re.search(pattern, content, flags=re.MULTILINE):
                    # 使用 lambda 避免 replacement 中的反斜杠（如 C:\Users\...）被解析为转义序列
                    content = re.sub(pattern, lambda m, r=replacement: r, content, flags=re.MULTILINE)
                else:
                    content += f'\n{replacement}\n'
                
            with open('config.py', 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.append_log("💾 设置已成功保存！", "#a6e3a1")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误: {str(e)}")

    def append_log(self, msg, color="#57606f"):
        time_str = QTime.currentTime().toString("HH:mm:ss")
        html_msg = f'<span style="color: #a4b0be;">[{time_str}]</span> <span style="color: {color};">{msg}</span>'
        self.log_text.append(html_msg)
        
        # 自动滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def start_upload(self):
        # 运行前强制保存配置
        self.save_settings()
        
        self.start_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log_text.clear()
        self.append_log("🚀 启动自动化上传任务...", "#1e90ff")
        
        self.thread = UploaderThread()
        self.thread.log_signal.connect(self.append_log)
        self.thread.error_signal.connect(lambda e: self.append_log(f"❌ 发生异常: {e}", "#ff4757"))
        self.thread.finished_signal.connect(self.on_upload_finished)
        self.thread.start()

    def stop_upload(self):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.stop_btn.setEnabled(False)

    def on_upload_finished(self):
        self.start_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.append_log("⏹ 任务结束。", "#57606f")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 使用 Fusion 风格，去除原本的强制黑暗模式
    app.setStyle("Fusion")
    
    gui = FanqieAutoPublisherGUI()
    gui.show()
    sys.exit(app.exec_())
