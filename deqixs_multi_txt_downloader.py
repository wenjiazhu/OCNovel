# deqixs_multi_txt_downloader.py

import requests
from bs4 import BeautifulSoup, Tag
import re
import os

def get_novel_id(novel_name):
    """
    通过小说名称在得奇小说网搜索并返回小说id
    """
    search_url = f"https://www.deqixs.com/tag/?key={novel_name}"
    resp = requests.get(search_url)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        m = re.match(r'/xiaoshuo/(\d+)/', a['href'])
        if m and novel_name in a.text:
            return m.group(1)
    return None

def download_all_txt_by_id(novel_id, novel_name, max_p=20, out_dir='data/reference'):
    """
    下载小说的所有分卷txt文件（p=1~max_p），每个文件单独保存
    """
    os.makedirs(out_dir, exist_ok=True)
    found = False
    for p in range(1, max_p + 1):
        txt_url = f"https://www.deqixs.com/txt/?id={novel_id}&p={p}"
        resp = requests.get(txt_url)
        resp.encoding = 'utf-8'
        # 判断是否为有效txt内容
        if resp.headers.get('Content-Type', '').startswith('text/plain') or len(resp.text) > 1000:
            out_path = os.path.join(out_dir, f"{novel_name}_part{p}.txt")
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            print(f"已下载: {out_path}")
            found = True
        else:
            # 如果内容无效，说明没有更多分卷
            break
    if not found:
        print("未获取到有效TXT内容，可能小说不存在或接口变更。")

def get_novel_id_sudugu(novel_name):
    """
    通过小说名称在速读谷搜索并返回小说id
    """
    search_url = f"https://www.sudugu.com/i/sor.aspx?key={novel_name}"
    resp = requests.get(search_url)
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')
    # 搜索结果中小说链接格式为 /数字/
    for a in soup.find_all('a', href=True):
        if isinstance(a, Tag) and 'href' in a.attrs:
            href = a['href']
            if not isinstance(href, str):
                continue
            m = re.match(r'/(\d+)/', href)
            if m and novel_name in a.text:
                return m.group(1)
    return None

def download_all_txt_by_id_sudugu(novel_id, novel_name, max_p=20, out_dir='data/reference'):
    """
    下载速读谷小说的所有分卷txt文件（p=1~max_p），每个文件单独保存
    """
    os.makedirs(out_dir, exist_ok=True)
    found = False
    for p in range(1, max_p + 1):
        txt_url = f"https://www.sudugu.com/txt/?id={novel_id}&p={p}"
        resp = requests.get(txt_url)
        resp.encoding = 'utf-8'
        content = resp.text.strip()
        # 只保存包含章节内容的 txt 文件
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        has_chapter = any(
            re.search(r'(第[\d一二三四五六七八九十百千]+[章节回])|(序章)|(楔子)|(尾声)', line)
            for line in lines
        )
        if has_chapter:
            out_path = os.path.join(out_dir, f"{novel_name}_sudugu_part{p}.txt")
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[速读谷] 已下载: {out_path}，内容摘要：{content[:30]}...")
            found = True
        else:
            print(f"[速读谷] 第{p}部分未检测到章节内容，跳过保存。")
    if not found:
        print("[速读谷] 未获取到有效TXT内容，可能小说不存在或接口变更。")

def main():
    novel_name = input("请输入小说名称：").strip()
    # 先尝试得奇小说网
    novel_id = get_novel_id(novel_name)
    if novel_id:
        download_all_txt_by_id(novel_id, novel_name)
    else:
        print("未在得奇小说网找到该小说，尝试速读谷……")
        novel_id_sudugu = get_novel_id_sudugu(novel_name)
        if not novel_id_sudugu:
            print("[速读谷] 未找到该小说")
            return
        download_all_txt_by_id_sudugu(novel_id_sudugu, novel_name)

if __name__ == "__main__":
    main()
