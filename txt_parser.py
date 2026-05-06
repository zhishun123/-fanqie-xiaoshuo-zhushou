# -*- coding: utf-8 -*-
"""
番茄小说自动发布系统 - 章节文件夹解析器
从文件夹中读取多个 TXT 文件，每个文件 = 一个章节
文件名格式: 第XX章_标题.txt
文件内容: 第一行是章节标题，后面是正文
"""

import re
import os
from dataclasses import dataclass
from typing import List
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class Chapter:
    """单个章节的数据结构"""
    number: int          # 章节序号（从文件名提取的数字）
    title: str           # 章节标题（如 "审神之书"）
    full_title: str      # 完整标题行（如 "第三十一章 审神之书"，从文件内容第一行获取）
    content: str         # 章节正文内容（不含标题行）
    char_count: int      # 正文字数
    filename: str        # 源文件名


def _read_file_content(file_path: str) -> str:
    """
    尝试多种编码读取文件内容

    参数:
        file_path: 文件路径

    返回:
        文件内容字符串，失败返回空字符串
    """
    for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030']:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    console.print(f"[bold red]无法识别文件编码: {file_path}[/bold red]")
    return ""


def parse_chapters_dir(
    chapters_dir: str,
    filename_pattern: re.Pattern,
    content_title_pattern: re.Pattern,
    start_chapter: int = 1,
    end_chapter: int = 0
) -> List[Chapter]:
    """
    从文件夹中解析所有章节文件

    参数:
        chapters_dir: 章节文件夹路径
        filename_pattern: 文件名正则（从文件名提取章节号和标题）
        content_title_pattern: 内容首行标题正则（用于跳过标题行）
        start_chapter: 起始章节号
        end_chapter: 结束章节号（0表示到最后）

    返回:
        按章节号排序的 Chapter 对象列表
    """
    if not os.path.exists(chapters_dir):
        console.print(f"[bold red]错误: 文件夹不存在 - {chapters_dir}[/bold red]")
        return []

    if not os.path.isdir(chapters_dir):
        console.print(f"[bold red]错误: 路径不是文件夹 - {chapters_dir}[/bold red]")
        return []

    # 获取所有 TXT 文件
    txt_files = [f for f in os.listdir(chapters_dir) if f.endswith('.txt')]

    if not txt_files:
        console.print("[bold red]错误: 文件夹中没有 TXT 文件[/bold red]")
        return []

    console.print(f"[green]✓ 找到 {len(txt_files)} 个 TXT 文件[/green]")

    chapters: List[Chapter] = []

    for filename in txt_files:
        file_path = os.path.join(chapters_dir, filename)

        # 从文件名提取章节号和标题
        match = filename_pattern.match(filename)
        if not match:
            console.print(f"[yellow]⚠ 跳过无法识别的文件: {filename}[/yellow]")
            continue

        chapter_num = int(match.group(1))
        title_from_filename = match.group(2).strip()

        # 读取文件内容
        raw_content = _read_file_content(file_path)
        if not raw_content:
            console.print(f"[red]✗ 无法读取: {filename}[/red]")
            continue

        # 分离标题行和正文
        lines = raw_content.split('\n')
        full_title = ""
        content_lines = []
        title_found = False

        for line in lines:
            stripped = line.strip()
            # 第一行通常是标题（如 "第三十一章 审神之书"）
            if not title_found and content_title_pattern.match(stripped):
                full_title = stripped
                title_found = True
                continue
            content_lines.append(stripped)

        # 如果没有匹配到标题行，用文件名信息构建
        if not full_title:
            full_title = f"第{chapter_num}章 {title_from_filename}"

        # 清理正文：移除首尾空行，保留段落间的换行
        # 去掉开头的连续空行
        while content_lines and not content_lines[0]:
            content_lines.pop(0)
        # 去掉结尾的连续空行
        while content_lines and not content_lines[-1]:
            content_lines.pop()

        content = '\n'.join(content_lines)
        char_count = len(content.replace('\n', '').replace(' ', ''))

        chapters.append(Chapter(
            number=chapter_num,
            title=title_from_filename,
            full_title=full_title,
            content=content,
            char_count=char_count,
            filename=filename
        ))

    # 按章节号排序
    chapters.sort(key=lambda c: c.number)

    # 筛选需要上传的范围
    if end_chapter > 0:
        chapters = [c for c in chapters if start_chapter <= c.number <= end_chapter]
    else:
        chapters = [c for c in chapters if c.number >= start_chapter]

    console.print(f"[green]✓ 已解析 {len(chapters)} 个章节（范围: 第{start_chapter}章 ~ "
                  f"{'最后' if end_chapter == 0 else f'第{end_chapter}章'}）[/green]")

    return chapters


def preview_chapters(chapters: List[Chapter], max_preview: int = 10):
    """
    在终端预览解析到的章节列表

    参数:
        chapters: 章节列表
        max_preview: 最多显示多少章节
    """
    if not chapters:
        console.print("[yellow]没有章节可预览[/yellow]")
        return

    table = Table(title="📚 章节预览", show_lines=True)
    table.add_column("章节号", style="cyan", width=8)
    table.add_column("标题", style="green", width=20)
    table.add_column("完整标题行", style="magenta", width=25)
    table.add_column("字数", style="yellow", width=8)
    table.add_column("文件名", style="dim", width=25)
    table.add_column("正文预览", style="white", width=35)

    for ch in chapters[:max_preview]:
        preview = ch.content[:50].replace('\n', ' ') + "..."
        table.add_row(
            str(ch.number),
            ch.title,
            ch.full_title,
            str(ch.char_count),
            ch.filename,
            preview
        )

    if len(chapters) > max_preview:
        table.add_row("...", "...", "...", "...", "...",
                       f"（还有 {len(chapters) - max_preview} 章）")

    console.print(table)

    # 统计信息
    total_chars = sum(c.char_count for c in chapters)
    avg_chars = total_chars // len(chapters) if chapters else 0
    console.print(f"\n[bold]总计: {len(chapters)} 章 | {total_chars:,} 字 | "
                  f"平均每章 {avg_chars:,} 字[/bold]")


if __name__ == "__main__":
    # 独立测试：解析并预览
    import config
    chapters = parse_chapters_dir(
        config.CHAPTERS_DIR,
        config.FILENAME_PATTERN,
        config.CONTENT_TITLE_PATTERN,
        config.START_CHAPTER,
        config.END_CHAPTER
    )
    if chapters:
        preview_chapters(chapters, max_preview=20)
