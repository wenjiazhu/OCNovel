import os
import re
import argparse
from opencc import OpenCC

# 创建 OpenCC 实例用于繁转简
cc = OpenCC('t2s')

def standardize_punctuation(text):
    """将常用半角标点替换为全角中文标点"""
    replacements = {
        ',': '，',
        '.': '。', # 注意：英文句点统一转为中文句号
        '?': '？',
        '!': '！',
        ':': '：',
        ';': '；',
        '"': '”', # 简单替换，不区分前后引号，可根据需要调整
        "'": '’', # 简单替换，不区分前后引号
        '(': '（',
        ')': '）',
    }
    for half, full in replacements.items():
        text = text.replace(half, full)
    # 移除所有空格（包括全角和半角）
    text = re.sub(r'\s+', '', text)
    return text

def split_sentences_to_paragraphs(text):
    """将每个句子拆分为单独的段落，并正确处理句末标点后的引号和括号"""
    # 修改正则表达式：匹配非结束标点+结束标点+[可选的后引号/括号]
    # [^。？！]     匹配任何不是句末标点的字符
    # +            匹配前面的字符一次或多次
    # [。？！]     匹配句末标点（。、？、！）
    # [”'）]*    匹配零个或多个后引号（"）、单引号（'）或右括号（）
    sentences = re.findall(r"[^。？！]+[。？！][”'）]*", text)
    # 如果原文末尾没有标点，可能最后一部分未被匹配，需要加上
    if text and text[-1] not in '。？！':
        # 找到最后一个标点后的内容
        last_part_start = 0
        for i in range(len(text) - 1, -1, -1):
            if text[i] in '。？！':
                last_part_start = i + 1
                break
        if last_part_start < len(text):
             sentences.append(text[last_part_start:])

    # 用双换行符连接句子，形成段落
    return '\n\n'.join(filter(None, sentences)) # filter(None, ...) 移除可能的空字符串

def count_chinese_chars(text):
    """统计文本中汉字的数量"""
    count = 0
    # 使用正则表达式匹配 Unicode 中 CJK 统一表意文字的基本范围
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            count += 1
    return count

def process_chapter(input_path, output_dir, split_sentences):
    """处理单个章节文件，并在文件名中添加汉字计数"""
    try:
        with open(input_path, 'r', encoding='utf-8') as f_in:
            content = f_in.read()

        # 1. 繁转简
        simplified_content = cc.convert(content)

        # 2. 标准化标点并移除空格
        standardized_content = standardize_punctuation(simplified_content)

        # 3. （可选）句子分段
        if split_sentences:
            final_content = split_sentences_to_paragraphs(standardized_content)
        else:
            final_content = standardized_content

        # 4. 统计汉字数量
        char_count = count_chinese_chars(final_content)

        # 5. 构建新的输出文件名
        base_filename = os.path.basename(input_path)
        name_part, ext_part = os.path.splitext(base_filename)
        # 检查是否已经有括号计数，避免重复添加
        name_part = re.sub(r'\s*\(\d+\)$', '', name_part)
        new_filename = f"{name_part} ({char_count}){ext_part}"
        output_path = os.path.join(output_dir, new_filename)

        # 6. 写入输出文件
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f_out:
            f_out.write(final_content.strip()) # 写入前去除首尾空白

        print(f"成功处理: {base_filename} -> {new_filename} (汉字数: {char_count})")

    except Exception as e:
        print(f"处理文件 {os.path.basename(input_path)} 时出错: {e}")

def main():
    parser = argparse.ArgumentParser(description="批量整理小说章节内容以符合番茄小说投稿要求。")
    parser.add_argument("input_dir", help="包含章节文件的输入目录。")
    parser.add_argument("output_dir", help="保存处理后文件的输出目录。")
    parser.add_argument("-s", "--start", type=int, default=1, help="起始章节号（包含）。")
    parser.add_argument("-e", "--end", type=int, required=True, help="结束章节号（包含）。")
    parser.add_argument("--split-sentences", action='store_true', help="将每个句子拆分为一个段落。")

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"错误：输入目录 '{args.input_dir}' 不存在或不是一个目录。")
        return

    print(f"开始处理章节 {args.start} 到 {args.end}...")
    print(f"输入目录: {args.input_dir}")
    print(f"输出目录: {args.output_dir}")
    print(f"句子分段: {'是' if args.split_sentences else '否'}")

    processed_count = 0
    for filename in os.listdir(args.input_dir):
        # 匹配文件名格式：第{数字}章_任意字符.txt
        match = re.match(r'第(\d+)章_.*\.txt', filename, re.IGNORECASE)
        if match:
            chapter_num = int(match.group(1))
            if args.start <= chapter_num <= args.end:
                input_path = os.path.join(args.input_dir, filename)
                process_chapter(input_path, args.output_dir, args.split_sentences)
                processed_count += 1

    print(f"\n处理完成！共处理了 {processed_count} 个章节文件。")
    if processed_count == 0:
        print("未找到符合条件的章节文件。请检查输入目录、文件名格式和章节范围。")

if __name__ == "__main__":
    main()