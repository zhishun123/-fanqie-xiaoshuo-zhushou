# -*- coding: utf-8 -*-
"""
无头模式运行器 - 专供 GUI 界面后台调用
绕过所有命令行交互提示，直接开始上传
"""
import sys
import io

# 强制禁用 rich 的颜色代码输出，以便 GUI 干净地捕获文本
import os
os.environ["TERM"] = "dumb" 

import config
from txt_parser import parse_chapters_dir
from uploader import FanqieUploader

def run():
    try:
        chapters = parse_chapters_dir(
            config.CHAPTERS_DIR, config.FILENAME_PATTERN,
            config.CONTENT_TITLE_PATTERN, config.START_CHAPTER, config.END_CHAPTER
        )
        if not chapters:
            print("[ERROR] 未找到任何符合条件的章节文件！")
            sys.exit(1)
            
        print(f"[INFO] 成功解析 {len(chapters)} 个章节，准备开始上传...")
        uploader = FanqieUploader()
        
        # 劫持 uploader 的内部 _log，去除所有 rich 颜色标签，变成纯文本前缀
        original_log = uploader._log
        def custom_log(msg, level="info"):
            prefix_map = {
                "info": "[INFO]",
                "success": "[SUCCESS]",
                "warning": "[WARNING]",
                "error": "[ERROR]"
            }
            # 调用原函数写入 log 文件，但终端打印简化版本供 GUI 捕获
            with open(config.LOG_FILE, "a", encoding="utf-8") as f:
                import time
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] {msg}\n")
                
            print(f"{prefix_map.get(level, '[INFO]')} {msg}", flush=True)
            
        uploader._log = custom_log

        uploader.start_browser()
        uploader.ensure_login()
        uploader.navigate_to_chapter_list()
        uploader.upload_all_chapters(chapters)
        
        print("[SUCCESS] 🎉 所有章节上传完成！")
    except Exception as e:
        print(f"[ERROR] 发生致命异常: {str(e)}")
        sys.exit(1)
    finally:
        try:
            uploader.close()
        except:
            pass

if __name__ == "__main__":
    # 强制设置输出编码为 UTF-8，防止 Popen 读取中文乱码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    run()
