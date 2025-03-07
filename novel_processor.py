# -*- coding: utf-8 -*-
import re
import json
from datetime import datetime
import google.generativeai as genai  # 假设使用 google-generativeai 库
import time
from datetime import datetime, timezone # 导入 timezone
import os  # 导入 os 模块，用于执行系统命令

# 从配置文件中加载 API 密钥和模型名称
def load_config(config_file="config.json"):
    """
    从 JSON 配置文件中加载配置信息，包括 Gemini API 密钥和模型名称。
    """
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"错误: 配置文件未找到: {config_file}")
        exit()
    except json.JSONDecodeError:
        print(f"错误: 配置文件 JSON 格式错误: {config_file}")
        exit()
    except Exception as e:
        print(f"读取配置文件时发生错误: {e}")
        exit()

config = load_config() # 加载配置
GEMINI_API_KEY = config.get("gemini_api_key") # 从配置中获取 API 密钥
MODEL_NAME = config.get("model_name", "gemini-2.0-flash-thinking-exp") #  从配置中获取模型名称，默认为 "gemini-2.0-flash-thinking-exp"

def split_novel_chapters(novel_text):
    """
    将小说文本按章节分割。
    章节标题通常以 "第X章" 或 "第 X 章" 开始。
    """
    chapter_pattern = re.compile(r'第[0-9]+章.*?[\r\n]') # 匹配 "第" + 1个或多个数字 + "章" + 任意字符到换行符
    chapters = []
    start_index = 0

    for match in chapter_pattern.finditer(novel_text):
        chapter_title = match.group(0).strip()
        chapter_start = match.start()
        if chapter_start > start_index:
            chapter_content = novel_text[start_index:chapter_start].strip()
            if chapter_content: # 忽略章节之间的空白内容
                chapters.append({"title": None, "content": chapter_content}) #  对于第一章前的序言或引言，章节标题可能为空

        start_index = match.end()
        chapters.append({"title": chapter_title, "content": ""}) # 初始化章节内容，后续填充

    # 添加最后一章内容
    last_chapter_content = novel_text[start_index:].strip()
    if last_chapter_content and chapters:
         chapters[-1]["content"] = last_chapter_content
    elif last_chapter_content: # 如果 chapters 为空，说明整个文本没有章节标题，作为单章节处理
        chapters.append({"title": None, "content": last_chapter_content})


    # 合并章节内容，处理章节内容跨多个章节标题的情况
    processed_chapters = []
    current_chapter = None
    for chapter_info in chapters:
        if chapter_info["title"]:
            if current_chapter:
                processed_chapters.append(current_chapter)
            current_chapter = {"id": f"chapter-{len(processed_chapters)}", "title": chapter_info["title"], "content": "", "analysis": None, "status": None}
        if current_chapter:
            current_chapter["content"] += chapter_info["content"] + "\n" # 保留章节内容，并添加换行符分隔

    if current_chapter:
        processed_chapters.append(current_chapter) # 添加最后一个章节

    return processed_chapters

def call_gemini_api(chapter_content, analysis_prompt):
    """
    调用 Gemini API 进行文本分析.
    使用 google-generativeai 库和配置文件中的 API 密钥。
    """
    if not GEMINI_API_KEY:
        print("错误: Gemini API 密钥未配置。请检查 config.json 文件。")
        exit()

    genai.configure(api_key=GEMINI_API_KEY) #  使用从配置文件中读取的 API 密钥
    model = genai.GenerativeModel(MODEL_NAME) # 使用配置文件中读取的模型名称

    #  构建完整的 prompt，将分析提示词和章节内容结合起来
    full_prompt = f"{analysis_prompt}\n\n章节内容:\n{chapter_content}"

    print(f"**Debug: Sending prompt to Gemini API:**\n{full_prompt}") # 打印发送给 Gemini API 的完整 prompt

    try:
        response = model.generate_content(full_prompt) #  调用 Gemini API 进行内容生成

        if response.text: # 检查 response.text 是否为空
            gemini_output_text = response.text
            print(f"**Debug: Gemini API response received:**\n{gemini_output_text}") # 打印 Gemini API 返回的原始文本
            return gemini_output_text #  返回 Gemini API 的文本响应
        else:
            error_msg = "Gemini API returned empty response." #  API 返回空文本
            print(f"**Error: {error_msg}") # 打印错误信息
            raise Exception(error_msg) # 抛出异常，由 analyze_chapter_content 函数捕获

    except Exception as e:
        error_msg = f"Gemini API 调用失败: {e}"
        print(f"**Error: {error_msg}") # 打印详细的 API 调用失败错误信息
        raise Exception(error_msg) # 抛出异常，由 analyze_chapter_content 函数捕获

def analyze_chapter_content(chapter_content, analysis_prompt, max_retries=3):
    """
    使用 Gemini 大模型分析章节内容，包含重试机制和更详细的错误处理。
    在 API 调用失败时进行重试，提高成功率。

    Args:
        chapter_content (str): 章节文本内容。
        analysis_prompt (str):  分析提示词。
        max_retries (int): 最大重试次数，默认为 3 次。

    Returns:
        如果 API 返回 JSON 格式，则返回 JSON 对象；否则返回原始文本。
        如果所有重试都失败，则返回错误信息字符串。
    """
    for attempt in range(max_retries):
        try:
            #  调用 Gemini API 获取分析结果
            analysis_result_text = call_gemini_api(chapter_content, analysis_prompt)

            try:
                #  尝试将 Gemini API 返回的文本结果解析为 JSON
                analysis_result_json = json.loads(analysis_result_text)
                return analysis_result_json #  如果成功解析为 JSON，直接返回 JSON 对象

            except json.JSONDecodeError:
                #  如果 Gemini API 返回的不是 JSON 格式，则返回原始文本结果
                return analysis_result_text #  返回原始文本结果

        except Exception as e:
            error_msg = f"Gemini API 调用失败 (尝试次数: {attempt + 1}/{max_retries}): {e}"
            print(f"**警告: {error_msg}") # 打印警告信息，包含尝试次数
            if attempt < max_retries - 1:
                print("等待 1 秒后重试...")
                time.sleep(1) # 等待 1 秒后重试
            else:
                print("**错误: 达到最大重试次数，分析失败。**") # 达到最大重试次数，打印错误信息
                return error_msg #  返回错误信息

    return "章节分析失败，请检查日志。" # 如果所有重试都失败，最终返回一个通用的失败信息

def process_novel(novel_text, analysis_prompt):
    """
    处理小说文本，分割章节并进行分析。
    返回 JSON 数据字典，而不是 JSON 字符串。
    添加控制台输出拆分结果和章节分析进度。
    修改为直接使用 analyze_chapter_content 返回的分析结果。
    新增空白章节检测和跳过机制。
    """
    print("***** process_novel 函数开始执行 *****")  # 添加这行 Debug 输出
    chapters = split_novel_chapters(novel_text)
    print("***** 章节分割结果 (chapters): *****")  # 添加 Debug 输出
    print(json.dumps(chapters, indent=2, ensure_ascii=False)) # 打印章节分割结果, 使用 json.dumps 格式化输出，方便查看
    print("***** 章节分割结果 结束 *****")   # 添加 Debug 输出
    timestamp = datetime.now(timezone.utc).isoformat() + "Z" #  使用 timezone.utc 获取 UTC 时区

    output_data = {
        "version": "1.0",
        "timestamp": timestamp,
        "prompt": analysis_prompt,
        "chapters": []
    }

    for chapter in chapters:
        if chapter["title"]: # 仅当章节有标题时才进行分析， 序言等无标题章节可以跳过分析
            chapter_content = chapter["content"].strip() # 获取章节内容并去除前后空白
            if not chapter_content: # 检查章节内容是否为空
                chapter_output = {
                    "id": chapter["id"],
                    "title": chapter["title"],
                    "content": "", # 空白章节内容
                    "analysis": "Chapter content is blank, analysis skipped.", #  标记为空白章节并跳过分析
                    "status": "skipped"
                }
                print(f"***** 章节: {chapter['title']} 内容为空，跳过分析，状态: {chapter_output['status']} *****") # 添加空白章节跳过分析的输出
            else: # 章节内容不为空，进行分析
                print(f"***** 开始分析章节: {chapter['title']} *****") # 添加章节分析进度输出
                analysis_result = analyze_chapter_content(chapter_content, analysis_prompt) #  直接获取分析结果
                chapter_output = {
                    "id": chapter["id"],
                    "title": chapter["title"],
                    "content": chapter_content, # 使用去除空白后的章节内容
                    "analysis": analysis_result #  直接使用 analyze_chapter_content 返回的分析结果
                }
                print(f"***** 章节: {chapter['title']} 分析完成 *****") # 添加章节分析完成状态输出

        else: #  处理无标题章节，例如序言
            chapter_output = {
                "id": chapter["id"],
                "title": chapter["title"], #  title 可能为 None
                "content": chapter["content"].strip(),
                "analysis": "No title, analysis skipped.", #  对于无标题章节，跳过分析并标记
                "status": "skipped"
            }
            print(f"***** 无标题章节 (id: {chapter_output['id']}) 跳过分析 *****") # 添加无标题章节跳过分析的输出
        output_data["chapters"].append(chapter_output)

    return output_data # 返回 Python 字典对象，而不是 JSON 字符串

# 示例使用
if __name__ == "__main__":
    novel_file_path = "my_novel.txt"  # 替换为您的TXT小说文件路径
    analysis_prompt_template = "请仔细分析本章节内容，并提供以下分析结果：\n\n1. 章节概要：\n   - 主要情节梳理\n   - 时间地点背景\n\n2. 人物分析：\n   - 主要人物及其行为\n   - 人物关系变化\n   - 性格特征展现\n\n3. 情节解析：\n   - 关键场景描写\n   - 重要对话内容\n   - 情节转折点\n\n4. 主题探讨：\n   - 章节主旨\n   - 与整体故事的关联\n   - 伏笔或呼应\n\n5. 写作技巧：\n   - 特色描写手法\n   - 叙事视角运用\n   - 语言风格特点\n\n请确保分析全面且准确，并突出重点内容。"

    try:
        with open(novel_file_path, "r", encoding="utf-8") as f: #  指定UTF-8编码打开文件
            novel_text = f.read()
    except FileNotFoundError:
        print(f"错误: 文件未找到: {novel_file_path}")
        exit()
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        exit()

    print("***** 小说文本内容 (前 500 字符): *****") # 添加 Debug 输出
    print(novel_text[:500]) # 打印小说文本前 500 字符
    print("***** 小说文本内容 结束 *****")      # 添加 Debug 输出

    output_json = process_novel(novel_text, analysis_prompt_template) # process_novel 现在返回 Python 字典

    output_file_path = "novel_analysis.json" #  指定输出 JSON 文件路径
    try:
        with open(output_file_path, "w", encoding="utf-8") as f: #  以 UTF-8 编码打开文件写入
            json.dump(output_json, f, indent=2, ensure_ascii=False) #  将 Python 字典写入 JSON 文件，并格式化
        print(f"分析结果已保存到: {output_file_path}") #  打印提示信息
    except Exception as e:
        print(f"保存 JSON 文件时发生错误: {e}") #  错误处理

    # 在 novel_analysis.json 生成后，自动调用 split_json_to_txt.py 进行拆分
    print("***** 正在自动调用 split_json_to_txt.py 进行文件拆分 *****")
    try:
        # 使用 os.system 执行 split_json_to_txt.py 脚本
        # 假设 split_json_to_txt.py 脚本和 novel_processor.py 脚本在同一目录下
        # 并且 split_json_to_txt.py 脚本的输出目录 chapter_analyses 与 novel_analysis.json 在同一目录下
        os.system("python split_json_to_txt.py")
        print("***** split_json_to_txt.py 执行完成 *****")
    except Exception as e:
        print(f"**错误: 调用 split_json_to_txt.py 失败: {e}**")
