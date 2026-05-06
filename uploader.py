# -*- coding: utf-8 -*-
"""
番茄小说自动发布系统 - 浏览器自动化上传器
基于 Playwright 实现番茄小说作者后台的自动章节发布

关键信息（来自实际 DOM 探查）：
- 点击"新建章节"会打开新标签页
- 章节号输入框: input.serial-input (第一个)
- 标题输入框: input[placeholder='请输入标题']
- 正文编辑器: div.ProseMirror (第一个，contenteditable)
- 下一步按钮: button.auto-editor-next
- 使用 Arco Design 组件库
"""

import os
import time
import datetime
from typing import List, Optional
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text

import config
from txt_parser import Chapter

console = Console()


class FanqieUploader:
    """番茄小说自动上传器"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None          # 章节管理页（主页面）
        self.editor_page: Optional[Page] = None   # 编辑器页面（新标签页）
        self.playwright = None
        self.success_count = 0
        self.fail_count = 0
        self.log_entries: List[str] = []

    def _log(self, message: str, level: str = "info"):
        """记录日志到文件和终端"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level.upper()}] {message}"
        self.log_entries.append(log_line)

        # 输出到终端
        color_map = {
            "info": "white",
            "success": "green",
            "warning": "yellow",
            "error": "red",
        }
        color = color_map.get(level, "white")
        console.print(f"  [{color}]{log_line}[/{color}]")

        # 写入日志文件
        try:
            with open(config.LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
        except Exception:
            pass

    def start_browser(self):
        """启动浏览器（使用持久化上下文以保存登录状态）"""
        console.print(Panel(
            "[bold cyan]正在启动浏览器...[/bold cyan]",
            border_style="cyan"
        ))

        self.playwright = sync_playwright().start()

        # 确保浏览器数据目录存在
        os.makedirs(config.BROWSER_DATA_DIR, exist_ok=True)

        # 使用持久化上下文，这样登录状态会被保存
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=os.path.abspath(config.BROWSER_DATA_DIR),
            headless=config.HEADLESS,
            viewport={"width": 1400, "height": 900},
            locale="zh-CN",
            # 模拟正常浏览器行为
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
            ignore_default_args=['--enable-automation'],
        )

        # 获取或创建页面
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()

        self.page.set_default_timeout(config.PAGE_TIMEOUT * 1000)
        self._log("浏览器启动成功", "success")

    def ensure_login(self):
        """
        确保用户已登录番茄作者后台
        如果未登录，会暂停等待用户手动登录
        """
        console.print(Panel(
            "[bold yellow]正在检查登录状态...[/bold yellow]",
            border_style="yellow"
        ))

        # 导航到作品页面
        self.page.goto(config.WORK_URL, wait_until="networkidle")
        time.sleep(3)

        # 检查是否需要登录（通过检测是否存在登录相关元素或URL重定向）
        current_url = self.page.url

        # 如果被重定向到登录页面
        if "login" in current_url or "passport" in current_url:
            console.print(Panel(
                "[bold red]检测到未登录状态！\n\n"
                "请在弹出的浏览器窗口中手动完成登录。\n"
                "登录成功后，请回到此终端按 Enter 键继续...[/bold red]",
                border_style="red",
                title="需要登录"
            ))
            input("按 Enter 键继续...")

            # 登录后重新导航
            self.page.goto(config.WORK_URL, wait_until="networkidle")
            time.sleep(3)

        self._log("登录状态确认", "success")

    def navigate_to_chapter_list(self):
        """导航到章节管理页面"""
        self.page.goto(config.WORK_URL, wait_until="networkidle")
        time.sleep(2)
        self._log("已打开章节管理页面", "info")

    def upload_single_chapter(self, chapter: Chapter, scheduled_time: str = "") -> bool:
        """
        上传单个章节的完整流程

        流程:
        1. 点击 "新建章节" → 等待新标签页打开
        2. 在新标签页中输入章节号和标题
        3. 输入正文内容
        4. 点击 "下一步"
        5. 处理错别字检测弹窗 → 点击 "提交"
        6. 处理风险检测弹窗 → 点击 "取消"
        7. 在发布设置中勾选 "使用AI"，可选开启定时发布 → 点击 "确认发布"
        8. 关闭编辑器标签页，回到章节管理页

        参数:
            chapter: Chapter 对象
            scheduled_time: 定时发布时间字符串 (格式 "YYYY-MM-DD HH:MM")，空字符串表示立即发布

        返回:
            是否上传成功
        """
        try:
            self._log(f"开始上传: {chapter.full_title} ({chapter.char_count}字)", "info")

            # ====== 步骤1: 点击 "新建章节" 并等待新标签页 ======
            self._log("步骤1: 点击 [新建章节] 等待新标签页", "info")

            editor_page = self._click_new_chapter()
            if editor_page is None:
                self._log("无法打开编辑器页面！", "error")
                return False

            self.editor_page = editor_page
            self.editor_page.set_default_timeout(config.PAGE_TIMEOUT * 1000)

            # ====== 步骤2: 输入章节号和标题 ======
            self._log(f"步骤2: 输入章节号={chapter.number}, 标题={chapter.title}", "info")
            self._input_chapter_info(chapter)

            # ====== 步骤3: 输入正文 ======
            self._log("步骤3: 输入正文内容", "info")
            self._input_content(chapter)

            # ====== 步骤4: 点击 "下一步" ======
            self._log("步骤4: 点击 [下一步]", "info")
            self._click_next_step()

            # ====== 步骤5: 处理错别字检测弹窗 ======
            if config.SKIP_TYPO_CHECK:
                self._log("步骤5: 处理错别字检测弹窗", "info")
                self._handle_typo_dialog()
                time.sleep(config.ACTION_DELAY)

            # ====== 步骤6: 处理风险检测弹窗 ======
            if config.SKIP_RISK_CHECK:
                self._log("步骤6: 处理风险检测弹窗", "info")
                self._handle_risk_dialog()
                time.sleep(config.ACTION_DELAY)

            # ====== 步骤7: 发布设置 - 勾选使用AI，可选定时发布，确认发布 ======
            self._log("步骤7: 发布设置", "info")
            self._handle_publish_settings(scheduled_time)

            time.sleep(config.ACTION_DELAY * 2)

            # 保存截图
            if config.SAVE_SCREENSHOTS:
                self._save_screenshot(chapter)

            # ====== 步骤8: 关闭编辑器标签页 ======
            self._close_editor_tab()

            self.success_count += 1
            self._log(f"章节上传成功: {chapter.full_title}", "success")
            return True

        except Exception as e:
            self.fail_count += 1
            self._log(f"章节上传失败: {chapter.full_title} - {str(e)}", "error")

            # 失败时保存错误截图
            if config.SAVE_SCREENSHOTS:
                self._save_screenshot(chapter, is_error=True)

            # 尝试关闭编辑器标签页
            self._close_editor_tab()

            return False

    def _click_new_chapter(self) -> Optional[Page]:
        """
        点击 "新建章节" 按钮并等待新标签页打开

        返回:
            新打开的编辑器页面，失败返回 None
        """
        try:
            # 使用 context.expect_page() 等待新标签页
            with self.context.expect_page(timeout=15000) as new_page_info:
                # 点击 "新建章节" 按钮
                btn = self.page.locator('button:has-text("新建章节")').first
                btn.click()

            editor_page = new_page_info.value

            # 等待新页面完全加载
            editor_page.wait_for_load_state("networkidle")
            time.sleep(3)  # 额外等待 JS 渲染完成

            self._log(f"编辑器页面已打开: {editor_page.url}", "success")
            return editor_page

        except Exception as e:
            self._log(f"等待新标签页失败: {str(e)}", "error")

            # 回退方案：直接检查是否有新页面
            time.sleep(5)
            if len(self.context.pages) > 1:
                editor_page = self.context.pages[-1]
                editor_page.wait_for_load_state("networkidle")
                time.sleep(3)
                self._log(f"通过回退方案找到编辑器页面: {editor_page.url}", "warning")
                return editor_page

            return None

    def _input_chapter_info(self, chapter: Chapter):
        """
        输入章节号和标题

        DOM 结构:
        - 章节号: input.serial-input.byte-input (第一个，pos 398,148)
        - 标题: input[placeholder='请输入标题'] (class 包含 serial-editor-input-hint-area)
        """
        ep = self.editor_page

        # 输入章节号
        try:
            # 章节号输入框：第一个 serial-input
            num_input = ep.locator('input.serial-input.byte-input').first
            num_input.wait_for(state="visible", timeout=5000)
            num_input.click()
            num_input.fill("")  # 清空默认值
            num_input.fill(str(chapter.number))
            time.sleep(0.3)
            self._log(f"章节号已输入: {chapter.number}", "success")
        except Exception as e:
            self._log(f"章节号输入失败: {str(e)}", "warning")

        # 输入标题
        try:
            title_input = ep.locator('input[placeholder="请输入标题"]').first
            title_input.wait_for(state="visible", timeout=5000)
            title_input.click()
            title_input.fill(chapter.title)
            time.sleep(0.3)
            self._log(f"标题已输入: {chapter.title}", "success")
        except Exception as e:
            self._log(f"标题输入失败: {str(e)}", "warning")
            # 回退：尝试通过 class 查找
            try:
                title_input = ep.locator('input.serial-editor-input-hint-area').first
                title_input.click()
                title_input.fill(chapter.title)
                self._log("标题通过回退选择器输入成功", "success")
            except Exception:
                self._log("标题输入完全失败！", "error")

    def _input_content(self, chapter: Chapter):
        """
        输入正文内容

        DOM 结构:
        - 正文编辑器: div.ProseMirror[contenteditable] (第一个，657x603)
        - 这是一个 ProseMirror 富文本编辑器
        """
        ep = self.editor_page

        # 找到正文编辑区域
        content_area = ep.locator('div.ProseMirror').first
        content_area.wait_for(state="visible", timeout=5000)

        # 点击编辑区域获得焦点
        content_area.click()
        time.sleep(0.5)

        # 分段输入正文
        paragraphs = chapter.content.split('\n')
        non_empty_paragraphs = [p.strip() for p in paragraphs if p.strip()]
        total = len(non_empty_paragraphs)

        for idx, paragraph in enumerate(non_empty_paragraphs):
            # 使用 insert_text 高效插入
            ep.keyboard.insert_text(paragraph)

            # 如果不是最后一段，按回车换行
            if idx < total - 1:
                ep.keyboard.press("Enter")

            # 每输入若干段暂停一下，避免页面卡顿
            if idx % 50 == 0 and idx > 0:
                time.sleep(0.3)

        time.sleep(config.ACTION_DELAY)
        self._log(f"正文输入完成，共 {total} 段", "success")

    def _click_next_step(self):
        """
        点击 "下一步" 按钮

        DOM 结构:
        - button.auto-editor-next (class 包含 publish-button)
        """
        ep = self.editor_page

        try:
            next_btn = ep.locator('button.auto-editor-next').first
            next_btn.wait_for(state="visible", timeout=5000)
            next_btn.click()
            self._log("已点击 [下一步]", "success")
        except Exception:
            # 回退方案
            try:
                next_btn = ep.locator('button:has-text("下一步")').first
                next_btn.click()
                self._log("通过回退选择器点击 [下一步]", "success")
            except Exception as e:
                self._log(f"点击 [下一步] 失败: {str(e)}", "error")
                raise

        time.sleep(config.ACTION_DELAY * 2)

    def _handle_typo_dialog(self):
        """
        处理错别字检测弹窗
        弹窗内容: "检测到你还有错别字未修改，是否确定提交？"
        操作: 点击 "提交" 按钮

        番茄使用 Arco Design 的 Modal 组件
        """
        ep = self.editor_page

        try:
            # 等待弹窗出现（Arco Design Modal）
            # 尝试多种选择器
            submit_btn = None
            selectors = [
                # Arco Design 弹窗中的确认/提交按钮
                '.arco-modal button:has-text("提交")',
                '.arco-modal-footer button:has-text("提交")',
                'button:has-text("提交")',
                # 通用弹窗
                'div[role="dialog"] button:has-text("提交")',
            ]

            for sel in selectors:
                try:
                    btn = ep.locator(sel).first
                    if btn.is_visible(timeout=5000):
                        submit_btn = btn
                        break
                except Exception:
                    continue

            if submit_btn:
                submit_btn.click()
                self._log("已点击 [提交] 跳过错别字检测", "success")
            else:
                self._log("未检测到错别字弹窗（可能没有错别字）", "info")

        except Exception as e:
            self._log(f"处理错别字弹窗时出错: {str(e)}", "warning")

    def _handle_risk_dialog(self):
        """
        处理内容风险检测弹窗
        弹窗内容: "是否进行内容风险检测？"
        操作: 点击 "取消" 按钮（不进行风险检测）
        """
        ep = self.editor_page

        try:
            cancel_btn = None
            selectors = [
                '.arco-modal button:has-text("取消")',
                '.arco-modal-footer button:has-text("取消")',
                'button:has-text("取消")',
                'div[role="dialog"] button:has-text("取消")',
            ]

            for sel in selectors:
                try:
                    btn = ep.locator(sel).first
                    if btn.is_visible(timeout=5000):
                        cancel_btn = btn
                        break
                except Exception:
                    continue

            if cancel_btn:
                cancel_btn.click()
                self._log("已点击 [取消] 跳过风险检测", "success")
            else:
                self._log("未检测到风险检测弹窗", "info")

        except Exception as e:
            self._log(f"处理风险检测弹窗时出错: {str(e)}", "warning")

    def _handle_publish_settings(self, scheduled_time: str = ""):
        """
        处理发布设置弹窗
        操作:
        1. 勾选 "是否使用AI" -> 是
        2. 可选：开启定时发布并设置时间
        3. 点击 "确认发布"

        DOM 结构（来自实际探查）:
        - 弹窗: .publish-confirm-container-new (arco-modal)
        - AI 单选: .arco-radio-group label (value=1 是, value=2 否)
        - 定时开关: button.arco-switch[role="switch"] (aria-checked)
        - 确认发布: .arco-modal-footer button:has-text("确认发布")

        参数:
            scheduled_time: 定时发布时间 "YYYY-MM-DD HH:MM"，空字符串表示立即发布
        """
        ep = self.editor_page

        try:
            # 等待发布设置弹窗出现
            time.sleep(config.ACTION_DELAY)

            # ---- 1. 勾选 "使用AI" ----
            if config.USE_AI:
                ai_selectors = [
                    '.publish-confirm-container-new .arco-radio:has-text("是"):not(:has-text("否"))',
                    '.arco-modal .arco-radio:has-text("是"):not(:has-text("否"))',
                    '.arco-radio:first-of-type',
                ]

                for sel in ai_selectors:
                    try:
                        el = ep.locator(sel).first
                        if el.is_visible(timeout=3000):
                            el.click()
                            self._log("已勾选 [使用AI: 是]", "success")
                            break
                    except Exception:
                        continue

            time.sleep(config.ACTION_DELAY)

            # ---- 2. 定时发布 ----
            if scheduled_time:
                self._handle_scheduled_publish(scheduled_time)
            else:
                self._log("定时发布: 关闭（立即发布）", "info")

            time.sleep(config.ACTION_DELAY)

            # ---- 3. 点击 "确认发布" ----
            publish_selectors = [
                '.publish-confirm-container-new button:has-text("确认发布")',
                '.arco-modal button:has-text("确认发布")',
                'button:has-text("确认发布")',
            ]

            for sel in publish_selectors:
                try:
                    btn = ep.locator(sel).first
                    if btn.is_visible(timeout=5000):
                        btn.click()
                        self._log("已点击 [确认发布]", "success")
                        break
                except Exception:
                    continue
            else:
                self._log("找不到 [确认发布] 按钮!", "error")

            time.sleep(config.ACTION_DELAY * 2)

        except Exception as e:
            self._log(f"处理发布设置时出错: {str(e)}", "error")

    def _handle_scheduled_publish(self, scheduled_time: str):
        """
        处理定时发布功能

        关键点：
        1. 页面上有多个 arco-switch，其中只有定时发布区域的才是我们要的
        2. 必须通过 "定时发布" 文字标签定位到正确的开关
        3. 开关打开后会出现日期选择器（只能选日期，不能选时间）

        参数:
            scheduled_time: 发布日期字符串 "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM"
        """
        ep = self.editor_page

        try:
            # ---- 1. 用 JS 精确定位定时发布开关并点击 ----
            # 通过 "定时发布" label 文字找到对应的 switch 按钮
            click_result = ep.evaluate("""() => {
                // 在弹窗中查找所有 label
                const modal = document.querySelector('.publish-confirm-container-new') ||
                              document.querySelector('[role="dialog"]');
                if (!modal) return { success: false, error: '找不到发布设置弹窗' };

                const labels = modal.querySelectorAll('.card-content-line-label');
                for (const label of labels) {
                    if (label.textContent.includes('定时发布')) {
                        const line = label.closest('.card-content-line');
                        if (!line) continue;
                        const switchBtn = line.querySelector('button.arco-switch, button[role="switch"]');
                        if (switchBtn) {
                            const wasChecked = switchBtn.getAttribute('aria-checked');
                            if (wasChecked !== 'true') {
                                switchBtn.click();
                            }
                            return {
                                success: true,
                                wasChecked: wasChecked,
                                clicked: wasChecked !== 'true'
                            };
                        }
                        return { success: false, error: '找到label但没找到switch按钮' };
                    }
                }
                return { success: false, error: '没找到定时发布label' };
            }""")

            if click_result.get('success'):
                if click_result.get('clicked'):
                    self._log("已开启定时发布开关", "success")
                else:
                    self._log("定时发布开关已经是开启状态", "info")
            else:
                self._log(f"定时发布开关操作失败: {click_result.get('error', '未知')}", "warning")
                return

            time.sleep(config.ACTION_DELAY)

            # ---- 2. 设置日期和时间 ----
            date_part = scheduled_time.split(' ')[0]
            time_part = scheduled_time.split(' ')[1] if ' ' in scheduled_time else "12:00"

            # 强制移除所有选择器的 readonly 属性
            ep.evaluate("""() => {
                const pickers = document.querySelectorAll('.publish-confirm-container-new .arco-picker input, [role="dialog"] .arco-picker input');
                pickers.forEach(p => p.readOnly = false);
            }""")
            time.sleep(0.5)

            # 找到所有可用的选择器
            all_pickers = ep.locator('.publish-confirm-container-new .arco-picker input').all()
            if len(all_pickers) < 2:
                all_pickers = ep.locator('[role="dialog"] .arco-picker input').all()

            visible_pickers = []
            for p in all_pickers:
                try:
                    if p.is_visible(timeout=1000):
                        visible_pickers.append(p)
                except:
                    continue

            self._log(f"找到 {len(visible_pickers)} 个可见的时间/日期选择器", "info")

            if len(visible_pickers) >= 1:
                # 设置日期
                visible_pickers[0].click()
                time.sleep(0.5)
                # 使用键盘全选删除并输入，避免 fill() 在受控组件中失效
                ep.keyboard.press("Control+A")
                ep.keyboard.press("Backspace")
                ep.keyboard.insert_text(date_part)
                time.sleep(0.5)
                ep.keyboard.press("Enter")
                time.sleep(0.5)
                self._log(f"已设置日期: {date_part}", "success")

            if len(visible_pickers) >= 2:
                # 设置时间
                visible_pickers[1].click()
                time.sleep(0.5)
                ep.keyboard.press("Control+A")
                ep.keyboard.press("Backspace")
                ep.keyboard.insert_text(time_part)
                time.sleep(0.5)
                ep.keyboard.press("Enter")
                time.sleep(0.5)
                self._log(f"已设置时间: {time_part}", "success")
            elif len(visible_pickers) > 0 and len(visible_pickers) < 2:
                self._log("未找到时间选择器（只找到1个选择器）", "warning")
            else:
                self._log("未找到任何日期/时间选择器！", "error")

        except Exception as e:
            self._log(f"设置定时发布时出错: {str(e)}", "warning")

    def _close_editor_tab(self):
        """关闭编辑器标签页，回到章节管理页面"""
        try:
            if self.editor_page and not self.editor_page.is_closed():
                self.editor_page.close()
                self._log("编辑器标签页已关闭", "info")
            self.editor_page = None

            # 确保焦点回到主页面
            if self.page and not self.page.is_closed():
                self.page.bring_to_front()
        except Exception as e:
            self._log(f"关闭编辑器标签页时出错: {str(e)}", "warning")

    def _save_screenshot(self, chapter: Chapter, is_error: bool = False):
        """保存截图"""
        try:
            os.makedirs(config.SCREENSHOT_DIR, exist_ok=True)
            prefix = "error_" if is_error else ""
            filename = f"{prefix}chapter_{chapter.number}.png"
            filepath = os.path.join(config.SCREENSHOT_DIR, filename)
            target_page = self.editor_page if (self.editor_page and not self.editor_page.is_closed()) else self.page
            target_page.screenshot(path=filepath, full_page=False)
            self._log(f"截图已保存: {filepath}", "info")
        except Exception as e:
            self._log(f"保存截图失败: {str(e)}", "warning")

    def upload_all_chapters(self, chapters: List[Chapter]):
        """
        批量上传所有章节

        参数:
            chapters: 需要上传的章节列表
        """
        total = len(chapters)

        # 计算定时发布时间列表
        scheduled_times = self._calc_scheduled_times(total)

        if scheduled_times:
            console.print(Panel(
                f"[bold green]开始批量上传 {total} 个章节（定时发布模式）[/bold green]\n"
                f"首章发布: {scheduled_times[0]}\n"
                f"末章发布: {scheduled_times[-1]}\n"
                f"间隔: {config.SCHEDULED_INTERVAL_MINUTES} 分钟",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[bold green]开始批量上传 {total} 个章节（立即发布）[/bold green]",
                border_style="green"
            ))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("上传进度", total=total)

            for i, chapter in enumerate(chapters):
                # 获取当前章节的定时时间
                sch_time = scheduled_times[i] if scheduled_times else ""
                desc = f"正在上传: {chapter.full_title}"
                if sch_time:
                    desc += f" (定时: {sch_time})"
                progress.update(task, description=desc)

                # 每次上传前先回到章节列表页（第一次不需要，已经在列表页了）
                if i > 0:
                    self.navigate_to_chapter_list()
                    time.sleep(config.ACTION_DELAY)

                success = self.upload_single_chapter(chapter, scheduled_time=sch_time)

                progress.advance(task)

                if not success:
                    console.print(f"\n[bold red]第 {chapter.number} 章上传失败！[/bold red]")
                    user_input = input("是否继续上传下一章？(y/n): ").strip().lower()
                    if user_input != 'y':
                        console.print("[yellow]用户选择停止上传[/yellow]")
                        break

                # 章节之间的延迟
                if i < total - 1:
                    self._log(f"等待 {config.CHAPTER_DELAY} 秒后上传下一章...", "info")
                    time.sleep(config.CHAPTER_DELAY)

        # 输出最终统计
        self._print_summary(total)

    def _calc_scheduled_times(self, total: int) -> List[str]:
        """
        根据配置计算每个章节的定时发布时间

        参数:
            total: 章节总数

        返回:
            时间字符串列表，空列表表示不使用定时发布
        """
        if not config.SCHEDULED_PUBLISH:
            return []

        try:
            # 解析首章发布时间
            first_time = datetime.datetime.strptime(
                config.SCHEDULED_FIRST_TIME, "%Y-%m-%d %H:%M"
            )

            interval = config.SCHEDULED_INTERVAL_MINUTES
            times = []

            for i in range(total):
                publish_time = first_time + datetime.timedelta(minutes=interval * i)
                times.append(publish_time.strftime("%Y-%m-%d %H:%M"))

            return times

        except Exception as e:
            self._log(f"计算定时发布时间失败: {str(e)}", "error")
            self._log("将使用立即发布模式", "warning")
            return []

    def _print_summary(self, total: int):
        """输出上传统计摘要"""
        summary = Text()
        summary.append("\n上传统计\n", style="bold white")
        summary.append(f"  总计: {total} 章\n", style="white")
        summary.append(f"  成功: {self.success_count} 章\n", style="green")
        summary.append(f"  失败: {self.fail_count} 章\n", style="red")
        summary.append(f"  日志: {config.LOG_FILE}\n", style="cyan")
        if config.SAVE_SCREENSHOTS:
            summary.append(f"  截图: {config.SCREENSHOT_DIR}/\n", style="cyan")

        console.print(Panel(summary, border_style="blue", title="完成"))

    def close(self):
        """关闭浏览器"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
            self._log("浏览器已关闭", "info")
        except Exception:
            pass
