from playwright.sync_api import sync_playwright
import os
import json
import time
from typing import List, Dict
import re

def process_cookies(cookies):
    """处理cookie格式，添加必要的字段"""
    for cookie in cookies:
        # 处理sameSite字段
        if 'sameSite' not in cookie or cookie['sameSite'] is None:
            cookie['sameSite'] = 'None'
        elif cookie['sameSite'] == 'no_restriction':
            cookie['sameSite'] = 'None'
        
        # 添加其他必要的字段
        if 'secure' not in cookie:
            cookie['secure'] = False
        if 'path' not in cookie:
            cookie['path'] = '/'
            
        # 移除不必要的字段
        keys_to_remove = ['hostOnly', 'session', 'storeId']
        for key in keys_to_remove:
            if key in cookie:
                del cookie[key]
    return cookies

class NovelPublisher:
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.base_url = "https://fanqienovel.com"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        """启动Playwright"""
        self.playwright = sync_playwright().start()
        # 修改这里以启动 Microsoft Edge
        print("正在启动 Microsoft Edge 浏览器...")
        try:
            # 指定 channel='msedge' 通常能确保使用您系统上安装的稳定版Edge
            self.browser = self.playwright.msedge.launch(headless=False, channel="msedge")
            print("Edge 浏览器启动成功")
        except Exception as e:
            print(f"启动 Edge (带 channel) 失败: {e}")
            print("尝试不指定 channel 启动 Edge...")
            # 如果指定 channel 失败，尝试不指定，让 Playwright 查找
            try:
                self.browser = self.playwright.msedge.launch(headless=False)
                print("Edge 浏览器（无 channel 指定）启动成功")
            except Exception as e2:
                 print(f"再次尝试启动 Edge 失败: {e2}")
                 print("请确保已运行 'playwright install msedge' 并安装了 Edge 浏览器。")
                 # 如果仍然失败，尝试回退到 chromium
                 print("尝试回退到 Chromium...")
                 try:
                     self.browser = self.playwright.chromium.launch(headless=False)
                     print("Chromium 浏览器启动成功")
                 except Exception as e3:
                      print(f"启动 Chromium 也失败了: {e3}")
                      raise Exception("无法启动任何支持的浏览器 (Edge 或 Chromium)")

        self.context = self.browser.new_context()

    def login(self, cookies_file: str):
        """使用cookies登录番茄小说网"""
        try:
            # 加载cookies
            if not os.path.exists(cookies_file):
                raise FileNotFoundError(f"Cookie文件 {cookies_file} 不存在")
            
            print(f"正在读取Cookie文件: {cookies_file}")
            with open(cookies_file, "r", encoding='utf-8') as f:
                try:
                    cookies = json.load(f)
                    print(f"成功读取Cookie数据，包含 {len(cookies)} 个Cookie项")
                    
                    # 验证cookies格式
                    if not isinstance(cookies, list):
                        raise ValueError("Cookie数据必须是一个数组")
                    
                    for i, cookie in enumerate(cookies):
                        required_fields = ['name', 'value', 'domain']
                        missing_fields = [field for field in required_fields if field not in cookie]
                        if missing_fields:
                            raise ValueError(f"Cookie项 #{i+1} 缺少必要字段: {', '.join(missing_fields)}")
                    
                    # 处理cookie格式
                    cookies = process_cookies(cookies)
                    print("Cookie格式验证通过")
                    self.context.add_cookies(cookies)
                    print("Cookie已成功添加到浏览器")
                    
                except json.JSONDecodeError as e:
                    raise ValueError(f"Cookie文件格式错误: {str(e)}")
            
            self.page = self.context.new_page()
            print("正在打开作家专区页面...")
            self.page.goto(f"{self.base_url}/main/writer/book-manage")
            
            # 等待页面加载完成
            try:
                self.page.wait_for_selector(".book-manage", timeout=10000)
                print("成功加载作家专区页面")
            except Exception as e:
                print("警告：未检测到作家专区页面元素，可能登录失败")
                print("当前页面URL:", self.page.url)
                raise Exception("登录失败，请检查Cookie是否有效")

        except Exception as e:
            print(f"登录过程出错: {str(e)}")
            raise

    def publish_chapter(self, chapter_data: Dict[str, str]) -> bool:
        """发布单个章节到草稿箱，仅填写章节标题"""
        chapter_title = chapter_data["title"]
        full_title = chapter_data["full_title"]  # 用于日志
        content = chapter_data["content"]  # content 包含 \n 换行符

        try:
            # 进入新建章节页面
            print(f"\n正在发布章节: {full_title}")
            publish_url = f"{self.base_url}/main/writer/{self.novel_id}/publish/?enter_from=newdraft"
            print(f"访问页面: {publish_url}")
            self.page.goto(publish_url)

            # --- 定位并填写章节标题 ---
            print("等待页面加载...")
            title_input_selector = "input[placeholder='请输入标题']"
            print(f"尝试查找章节标题输入框: {title_input_selector}")
            try:
                title_input = self.page.wait_for_selector(title_input_selector, state="visible", timeout=10000)
                print(f"找到章节标题输入框")
                
                print(f"输入章节标题: {chapter_title}")
                title_input.fill("")  # 清空
                time.sleep(0.2)
                title_input.fill(chapter_title)  # 填入纯标题
            except Exception as e:
                print(f"查找或填写章节标题输入框失败: {e}")
                html_content = self.page.content()
                with open(f"page_content_title_error_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                raise Exception(f"无法找到或操作章节标题输入框 ({title_input_selector})")

            # --- 定位并输入正文内容 ---
            print("等待编辑器加载...")
            content_selectors = [
                ".ProseMirror",
                "div[contenteditable='true']",
                ".syl-editor-content",
                "div.ProseMirror[contenteditable='true']"
            ]
            
            content_input = None
            editor_selector = None # 记录找到的编辑器选择器
            for selector in content_selectors:
                try:
                    print(f"尝试使用选择器: {selector}")
                    element = self.page.wait_for_selector(selector, state="visible", timeout=5000) # 缩短超时以便更快尝试下一个
                    if element:
                        content_input = element
                        editor_selector = selector # 记录成功的选择器
                        print(f"找到编辑器元素: {selector}")
                        break
                except Exception as e:
                    print(f"选择器 {selector} 查找失败: {e}")
                    continue

            if not content_input:
                print("无法找到编辑器，保存页面内容以供调试...")
                html_content = self.page.content()
                with open(f"page_content_editor_error_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                raise Exception("无法找到正文编辑器")

            # --- 输入内容 ---
            try:
                print("准备输入章节内容...")
                content_input.click() # 点击以确保编辑器获得焦点
                time.sleep(1)

                # 直接使用原始内容，保持原有格式
                try:
                    print("使用键盘模拟输入内容...")
                    content_input.focus()
                    # 清空编辑器内容
                    content_input.fill("")
                    time.sleep(0.5)

                    # 直接使用原始内容，按行输入
                    lines = content.split('\n')
                    total_lines = len(lines)
                    
                    # 分块处理以避免输入过长导致的问题
                    chunk_size = 500  # 每个块的最大字符数
                    current_chunk = ""
                    
                    for i, line in enumerate(lines):
                        if len(current_chunk) + len(line) > chunk_size:
                            # 输入当前块
                            print(f"输入内容块 {len(current_chunk)} 字符...")
                            self.page.keyboard.type(current_chunk)
                            current_chunk = ""
                        
                        # 添加当前行
                        current_chunk += line
                        
                        # 如果不是最后一行，只添加换行符
                        if i < total_lines - 1:
                            current_chunk += '\n'
                    
                    # 输入最后一块
                    if current_chunk:
                        print(f"输入最后一块内容 {len(current_chunk)} 字符...")
                        self.page.keyboard.type(current_chunk)
                    
                    print("键盘模拟输入完成")

                except Exception as type_error:
                    print(f"键盘模拟输入失败，尝试使用JavaScript方式: {type_error}")
                    # 回退：使用JavaScript方式
                    try:
                        # 保持原始换行格式
                        content_html = content.replace('\n', '<br>')
                        js_code = f"""(content_html) => {{
                            const editor = document.querySelector('{editor_selector}');
                            if (editor) {{
                                editor.innerHTML = content_html;
                                editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                editor.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return true;
                            }}
                            return false;
                        }}"""
                        success = self.page.evaluate(js_code, content_html)
                        if success:
                            print("使用 JavaScript 设置内容成功")
                        else:
                            raise Exception("JavaScript 无法找到编辑器元素")
                    except Exception as js_error:
                        print(f"JavaScript 设置内容也失败: {js_error}")
                        raise

                print("内容输入完成")
                print("等待1秒以确保内容稳定...")
                time.sleep(1)  # 缩短等待时间

            except Exception as e:
                print(f"输入内容失败: {str(e)}")
                html_content = self.page.content()
                with open(f"page_content_content_error_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                raise Exception("无法输入章节内容")

            # --- 点击保存草稿按钮 ---
            print("保存草稿...")
            button_texts = ['存草稿', '保存草稿', '保存到草稿箱']
            save_draft_button = None
            for text in button_texts:
                print(f"尝试查找按钮: {text}")
                button = self.page.locator(f"button:has-text('{text}')")
                try:
                    button.wait_for(state="visible", timeout=10000)
                    if button.is_enabled():
                        save_draft_button = button
                        print(f"找到并启用按钮: {text}")
                        break
                except Exception as e:
                     print(f"查找按钮 '{text}' 失败或未启用: {e}")
                     continue

            if not save_draft_button:
                print("无法找到可用的保存按钮，保存页面内容...")
                html_content = self.page.content()
                with open(f"page_content_save_button_error_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                raise Exception("找不到可用的保存草稿按钮")

            # 最多尝试保存两次
            max_save_attempts = 2
            save_attempt = 0
            save_failed = False

            while save_attempt < max_save_attempts and not save_failed:
                save_attempt += 1
                print(f"第 {save_attempt} 次尝试保存...")
                
                save_draft_button.click()
                print("已点击保存按钮")

                # --- 检查是否有失败提示 ---
                print("检查是否保存失败...")
                fail_selectors = [
                    ".toast-error",  # 通用错误提示类名
                    "//*[contains(text(), '保存失败')]",  # XPath 查找包含"保存失败"的元素
                    "div:has-text('保存失败')",  # Playwright 的文本选择器
                    ".byte-message--error"  # 另一个可能的错误提示类名
                ]
                
                # 等待2秒检查是否有失败提示
                time.sleep(2)
                for selector in fail_selectors:
                    try:
                        error_toast = self.page.locator(selector)
                        if error_toast.is_visible():
                            print(f"检测到失败提示: {selector}")
                            save_failed = True
                            break
                    except Exception:
                        continue

                # 如果检测到失败且不是最后一次尝试，等待1秒后重试
                if save_failed and save_attempt < max_save_attempts:
                    print("检测到失败提示，等待1秒后重试...")
                    time.sleep(1)
                    save_failed = False  # 重置失败标志，准备重试
                elif not save_failed:
                    print("未检测到失败提示，视为保存成功")
                    break

            # 如果最后一次尝试仍然失败，保存错误信息
            if save_failed:
                html_content = self.page.content()
                with open(f"page_content_save_fail_{int(time.time())}.html", "w", encoding="utf-8") as f:
                    f.write(html_content)
                screenshot_path = f"error_save_fail_{int(time.time())}.png"
                self.page.screenshot(path=screenshot_path)
                print(f"保存失败截图已保存至: {screenshot_path}")
                raise Exception("保存失败")

            print(f"章节 {full_title} 发布成功！")
            return True

        except Exception as e:
            print(f"发布章节 {full_title} 失败: {str(e)}")
            # 保存页面截图以便调试
            try:
                safe_filename_part = re.sub(r'[\\/*?:"<>|]', "", full_title)
                screenshot_path = f"error_{safe_filename_part}_{int(time.time())}.png"
                self.page.screenshot(path=screenshot_path)
                print(f"错误截图已保存至: {screenshot_path}")
            except Exception as screen_err:
                print(f"保存截图失败: {screen_err}")
            return False

    def publish_chapters(self, chapters: List[Dict[str, str]]):
        """批量发布多个章节"""
        for chapter_data in chapters:
            success = self.publish_chapter(chapter_data) # 传递整个字典
            if success:
                print(f"章节 {chapter_data['full_title']} 处理完成 - 成功")
            else:
                print(f"章节 {chapter_data['full_title']} 处理完成 - 失败")
            print("-" * 30)
            time.sleep(3) # 发布间隙时间

    def close(self):
        """关闭浏览器和Playwright"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def read_chapters_from_files(directory: str) -> List[Dict[str, str]]:
    """从指定目录读取章节文件，提取章节号、标题、完整标题和内容"""
    chapters = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".txt"):
            chapter_data = {
                "number": None,
                "title": None,
                "full_title": filename[:-4], # 默认完整标题为去扩展名的文件名
                "content": None
            }

            # 从文件名中提取原始标题部分
            title_raw = filename[:-4]
            if " (" in title_raw:
                title_raw = title_raw.split(" (")[0]

            # 尝试匹配 "第X章_标题" 或 "第X章 标题" 格式
            # 正则表达式：匹配 "第" + 数字 + "章" + (可选的分隔符) + 标题
            match = re.match(r"(?:第)\s*(\d+)\s*(?:章)(?:_|\s*)(.*)", title_raw)

            if match:
                chapter_data["number"] = match.group(1).strip() # 提取章节号
                chapter_data["title"] = match.group(2).strip()  # 提取纯标题
                # 格式化完整标题用于日志
                chapter_data["full_title"] = f"第 {chapter_data['number']} 章 {chapter_data['title']}"
            else:
                # 如果不匹配，将整个去除数字和扩展名的部分作为标题，章节号设为 None
                chapter_data["title"] = title_raw.replace("_", " ").strip()
                chapter_data["number"] = None # 无法提取章节号
                chapter_data["full_title"] = chapter_data["title"] # 完整标题也设为这个
                print(f"警告：文件名 '{filename}' 不完全符合 '第X章_标题' 格式。章节号未提取，标题设为: '{chapter_data['title']}'")

            # 读取文件内容作为正文
            try:
                with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                    chapter_data["content"] = f.read().strip()
                # 只有当所有信息都成功提取时才添加到列表
                if chapter_data["number"] and chapter_data["title"] and chapter_data["content"] is not None:
                     chapters.append(chapter_data)
                else:
                    print(f"错误：未能完整处理文件 '{filename}'，已跳过。请检查格式或内容。")
            except Exception as e:
                 print(f"错误：读取文件 '{filename}' 时出错: {e}，已跳过。")

    return chapters

def main():
    # 配置参数
    NOVEL_ID = "7486654521544805400"
    CHAPTERS_DIR = "chapters"  # 章节文件所在目录
    COOKIES_FILE = "cookies.json"  # 存储登录cookies的文件

    # 读取章节文件
    chapters = read_chapters_from_files(CHAPTERS_DIR)
    if not chapters:
        print("未找到章节文件")
        return

    # 初始化发布器
    publisher = NovelPublisher(NOVEL_ID)
    
    try:
        # 启动浏览器
        publisher.start()
        # 登录
        publisher.login(COOKIES_FILE)
        # 发布章节
        publisher.publish_chapters(chapters)
    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        publisher.close()

if __name__ == "__main__":
    main() 