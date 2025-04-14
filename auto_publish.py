from playwright.sync_api import sync_playwright
import os
import json
import time
from typing import List, Dict

class NovelPublisher:
    def __init__(self, novel_id: str):
        self.novel_id = novel_id
        self.base_url = "https://fanqienovel.com"
        self.browser = None
        self.context = None
        self.page = None

    def login(self, cookies_file: str):
        """使用cookies登录番茄小说网"""
        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=False)
            self.context = self.browser.new_context()
            
            # 加载cookies
            if os.path.exists(cookies_file):
                with open(cookies_file, "r") as f:
                    cookies = json.load(f)
                self.context.add_cookies(cookies)
            
            self.page = self.context.new_page()
            self.page.goto(f"{self.base_url}/main/writer/book-manage")
            
            # 等待页面加载完成
            self.page.wait_for_selector(".book-manage")

    def publish_chapter(self, title: str, content: str) -> bool:
        """发布单个章节到草稿箱"""
        try:
            # 进入新建章节页面
            self.page.goto(f"{self.base_url}/main/writer/{self.novel_id}/publish/?enter_from=newdraft")
            self.page.wait_for_selector("input[placeholder='请输入章节标题']")

            # 输入标题
            title_input = self.page.locator("input[placeholder='请输入章节标题']")
            title_input.fill(title)

            # 输入内容
            content_input = self.page.locator(".ProseMirror")
            content_input.fill(content)

            # 点击保存草稿按钮
            save_draft_button = self.page.locator("button:has-text('保存草稿')")
            save_draft_button.click()

            # 等待保存成功
            self.page.wait_for_selector(".success-toast", timeout=10000)
            return True

        except Exception as e:
            print(f"发布章节 {title} 失败: {str(e)}")
            return False

    def publish_chapters(self, chapters: List[Dict[str, str]]):
        """批量发布多个章节"""
        for chapter in chapters:
            success = self.publish_chapter(chapter["title"], chapter["content"])
            if success:
                print(f"章节 {chapter['title']} 发布成功")
            time.sleep(2)  # 添加延时避免请求过快

    def close(self):
        """关闭浏览器"""
        if self.browser:
            self.browser.close()

def read_chapters_from_files(directory: str) -> List[Dict[str, str]]:
    """从指定目录读取章节文件"""
    chapters = []
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".txt"):
            # 从文件名中提取标题（去掉扩展名和字数信息）
            title = filename[:-4]  # 去掉.txt
            if " (" in title:  # 如果有字数信息，去掉它
                title = title.split(" (")[0]
            
            # 读取文件内容作为正文
            with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                content = f.read().strip()
                chapters.append({"title": title, "content": content})
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

    # 初始化发布器并登录
    publisher = NovelPublisher(NOVEL_ID)
    publisher.login(COOKIES_FILE)

    try:
        # 发布章节
        publisher.publish_chapters(chapters)
    finally:
        publisher.close()

if __name__ == "__main__":
    main() 