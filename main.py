# -*- coding: utf-8 -*-
"""
番茄小说自动发布系统 - 主入口
支持多种运行模式：解析预览、完整上传、断点续传
"""

import sys
import os
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt

import config
from txt_parser import parse_chapters_dir, preview_chapters
from uploader import FanqieUploader

console = Console()


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════╗
║     🍅  番茄小说自动发布系统  🍅             ║
║                                              ║
║     自动解析章节文件夹 → 自动上传 → 自动发布  ║
║     支持断点续传 / 错别字跳过 / AI 勾选       ║
╚══════════════════════════════════════════════╝
    """
    console.print(Panel(banner, border_style="bright_red"))


def load_chapters():
    """加载并返回章节列表"""
    return parse_chapters_dir(
        config.CHAPTERS_DIR,
        config.FILENAME_PATTERN,
        config.CONTENT_TITLE_PATTERN,
        config.START_CHAPTER,
        config.END_CHAPTER
    )


def check_config():
    """检查必要的配置项"""
    errors = []

    if not config.WORK_URL:
        errors.append("WORK_URL 未设置（番茄小说作品的章节管理页面 URL）")

    if not config.CHAPTERS_DIR:
        errors.append("CHAPTERS_DIR 未设置（章节文件夹路径）")
    elif not os.path.isdir(config.CHAPTERS_DIR):
        errors.append(f"章节文件夹不存在: {config.CHAPTERS_DIR}")

    if errors:
        console.print("[bold red]❌ 配置检查失败:[/bold red]")
        for err in errors:
            console.print(f"  [red]• {err}[/red]")
        console.print("\n[yellow]请编辑 config.py 文件填写正确的配置信息[/yellow]")
        return False

    return True


def mode_preview():
    """模式1: 仅解析预览，不上传"""
    console.print("\n[bold cyan]📖 模式: 解析预览[/bold cyan]\n")

    chapters = load_chapters()
    if not chapters:
        console.print("[red]未解析到任何章节[/red]")
        return

    preview_chapters(chapters, max_preview=20)


def mode_upload():
    """模式2: 完整上传流程"""
    console.print("\n[bold green]📤 模式: 自动上传[/bold green]\n")

    chapters = load_chapters()
    if not chapters:
        console.print("[red]未解析到任何章节，无法上传[/red]")
        return

    # 预览
    preview_chapters(chapters, max_preview=5)

    # 确认上传
    console.print()
    if not Confirm.ask(f"[bold]确认上传以上 {len(chapters)} 个章节吗？[/bold]"):
        console.print("[yellow]已取消[/yellow]")
        return

    # 开始上传
    uploader = FanqieUploader()
    try:
        uploader.start_browser()
        uploader.ensure_login()
        uploader.navigate_to_chapter_list()
        uploader.upload_all_chapters(chapters)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ 用户中断操作[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]❌ 发生异常: {str(e)}[/bold red]")
    finally:
        uploader.close()


def mode_single():
    """模式3: 上传单个章节（用于测试）"""
    console.print("\n[bold magenta]🧪 模式: 单章测试[/bold magenta]\n")

    chapters = load_chapters()
    if not chapters:
        console.print("[red]未解析到任何章节[/red]")
        return

    preview_chapters(chapters, max_preview=20)

    chapter_num = IntPrompt.ask(
        "\n请输入要测试上传的章节号（如 31）",
        default=chapters[0].number
    )

    target = None
    for ch in chapters:
        if ch.number == chapter_num:
            target = ch
            break

    if not target:
        console.print(f"[red]未找到第 {chapter_num} 章[/red]")
        return

    console.print(f"\n[green]将测试上传: {target.full_title} ({target.char_count}字)[/green]")
    console.print(f"[dim]来源文件: {target.filename}[/dim]")

    # 计算定时发布时间
    scheduled_time = ""
    if config.SCHEDULED_PUBLISH:
        scheduled_time = config.SCHEDULED_FIRST_TIME
        console.print(f"[cyan]定时发布: {scheduled_time}[/cyan]")
    else:
        console.print(f"[dim]定时发布: 关闭（立即发布）[/dim]")

    if not Confirm.ask("确认上传？"):
        console.print("[yellow]已取消[/yellow]")
        return

    uploader = FanqieUploader()
    try:
        uploader.start_browser()
        uploader.ensure_login()
        uploader.navigate_to_chapter_list()
        uploader.upload_single_chapter(target, scheduled_time=scheduled_time)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ 用户中断操作[/yellow]")
    except Exception as e:
        console.print(f"\n[bold red]❌ 发生异常: {str(e)}[/bold red]")
    finally:
        uploader.close()


def mode_login_only():
    """模式4: 仅登录保存状态"""
    console.print("\n[bold blue]🔐 模式: 登录保存[/bold blue]\n")
    console.print("[cyan]将打开浏览器让你手动登录，登录状态会被保存。[/cyan]")
    console.print("[cyan]之后运行上传时无需再次登录。[/cyan]\n")

    uploader = FanqieUploader()
    try:
        uploader.start_browser()

        if config.WORK_URL:
            uploader.page.goto(config.WORK_URL)
        else:
            uploader.page.goto("https://writer.fanqie.com")

        console.print(Panel(
            "[bold yellow]请在浏览器中完成登录。\n"
            "登录成功后回到此终端按 Enter 键保存状态并退出。[/bold yellow]",
            border_style="yellow",
            title="等待登录"
        ))
        input("按 Enter 键保存并退出...")

    except Exception as e:
        console.print(f"\n[bold red]❌ 发生异常: {str(e)}[/bold red]")
    finally:
        uploader.close()
        console.print("[green]✅ 登录状态已保存[/green]")


def main():
    """主函数"""
    print_banner()

    # 显示当前配置
    console.print("[dim]当前配置:[/dim]")
    console.print(f"  [dim]作品URL:   {config.WORK_URL or '(未设置)'}[/dim]")
    console.print(f"  [dim]章节目录:  {config.CHAPTERS_DIR or '(未设置)'}[/dim]")
    console.print(f"  [dim]起始章节:  第 {config.START_CHAPTER} 章[/dim]")
    end_text = '最后' if config.END_CHAPTER == 0 else f'第 {config.END_CHAPTER} 章'
    console.print(f"  [dim]结束章节:  {end_text}[/dim]")
    console.print(f"  [dim]章节延迟:  {config.CHAPTER_DELAY} 秒[/dim]")
    console.print(f"  [dim]使用AI:    {'是' if config.USE_AI else '否'}[/dim]")
    if config.SCHEDULED_PUBLISH:
        console.print(f"  [dim]定时发布:  开启[/dim]")
        console.print(f"  [dim]首章时间:  {config.SCHEDULED_FIRST_TIME}[/dim]")
        console.print(f"  [dim]章节间隔:  {config.SCHEDULED_INTERVAL_MINUTES} 分钟[/dim]")
    else:
        console.print(f"  [dim]定时发布:  关闭（立即发布）[/dim]")
    console.print()

    # 选择运行模式
    console.print("[bold]请选择运行模式:[/bold]")
    console.print("  [cyan]1[/cyan] - 📖 解析预览（仅解析章节文件夹，不上传）")
    console.print("  [cyan]2[/cyan] - 📤 自动上传（批量上传所有章节）")
    console.print("  [cyan]3[/cyan] - 🧪 单章测试（上传一章测试流程）")
    console.print("  [cyan]4[/cyan] - 🔐 登录保存（仅登录并保存状态）")
    console.print("  [cyan]0[/cyan] - 🚪 退出")
    console.print()

    choice = Prompt.ask("请输入选项", choices=["0", "1", "2", "3", "4"], default="1")

    if choice == "0":
        console.print("[yellow]再见！[/yellow]")
        sys.exit(0)
    elif choice == "1":
        if not config.CHAPTERS_DIR or not os.path.isdir(config.CHAPTERS_DIR):
            console.print("[red]请先在 config.py 中设置 CHAPTERS_DIR[/red]")
            return
        mode_preview()
    elif choice == "2":
        if not check_config():
            return
        mode_upload()
    elif choice == "3":
        if not check_config():
            return
        mode_single()
    elif choice == "4":
        mode_login_only()


if __name__ == "__main__":
    main()
