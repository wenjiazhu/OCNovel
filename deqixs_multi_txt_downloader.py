# deqixs_multi_txt_downloader.py

import requests
from bs4 import BeautifulSoup, Tag
import re
import os
import time

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

def download_all_txt_by_id(novel_id, novel_name, max_p=10, out_dir='data/reference'):
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

def download_all_txt_by_id_sudugu(novel_id, novel_name, max_p=10, out_dir='data/reference'):
    """
    下载速读谷小说的所有分卷txt文件（p=1~max_p），每个文件单独保存，失败自动重试3次，最后汇总失败分卷
    """
    os.makedirs(out_dir, exist_ok=True)
    found = False
    failed_parts = []
    for p in range(1, max_p + 1):
        txt_url = f"https://www.sudugu.com/txt/?id={novel_id}&p={p}"
        success = False
        for attempt in range(3):
            try:
                resp = requests.get(txt_url, timeout=15)
                resp.encoding = 'utf-8'
                # 判断是否为有效txt内容（与得奇相同）
                if resp.headers.get('Content-Type', '').startswith('text/plain') or len(resp.text) > 1000:
                    out_path = os.path.join(out_dir, f"{novel_name}_sudugu_part{p}.txt")
                    try:
                        with open(out_path, 'w', encoding='utf-8') as f:
                            f.write(resp.text)
                        print(f"[速读谷] 已下载: {out_path}，内容摘要：{resp.text[:30]}...")
                        found = True
                        success = True
                        break
                    except Exception as e:
                        print(f"[速读谷] 第{p}部分保存失败，原因：{e}，跳过。")
                        break
                else:
                    print(f"[速读谷] 第{p}部分内容无效，跳过保存。")
                    success = True  # 内容无效不再重试
                    break
            except Exception as e:
                print(f"[速读谷] 第{p}部分下载失败（第{attempt+1}次），原因：{e}，重试..." if attempt < 2 else f"[速读谷] 第{p}部分下载失败（第3次），原因：{e}，跳过。")
                time.sleep(2)
        if not success:
            failed_parts.append(p)
    if not found:
        print("[速读谷] 未获取到有效TXT内容，可能小说不存在或接口变更。")
    if failed_parts:
        print(f"[速读谷] 以下分卷下载失败：{failed_parts}，可稍后重试或手动补下。")

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
