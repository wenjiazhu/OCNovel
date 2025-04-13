import os
import re
import argparse
from opencc import OpenCC

# 创建 OpenCC 实例用于繁转简
cc = OpenCC('t2s')

def standardize_punctuation(text):
    """将常用半角标点替换为全角中文标点，并将单省略号替换为双省略号"""
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
        # 添加省略号替换规则
        '…': '……', # 将单个省略号替换为双省略号
        '...': '……' # 也处理三个点的英文省略号
    }
    # 先执行省略号替换，避免三个点被先替换成句号
    text = text.replace('...', '……')
    text = text.replace('…', '……')

    for half, full in replacements.items():
        # 跳过已经处理的省略号规则
        if half == '…' or half == '...':
            continue
        text = text.replace(half, full)
    # 移除所有其他类型的空白字符，保留换行符用于可能的初始段落结构
    # 但通常在处理前会合并成一个长字符串，所以移除所有 \s+ 是合适的
    text = re.sub(r'\s+', '', text)
    return text

def split_sentences_to_paragraphs(text):
    """
    将文本拆分为段落。引号(“...”)内的内容视为一个整体，不按其内部标点拆分。
    仅根据引号外部的句末标点(。？！)进行拆分。
    在相邻的结束引号(")和开始引号(")之间强制分段。
    段落不以 】、）、，、。、！、？、； 开头。
    """
    if not text:
        return ""

    quotes = {}
    placeholder_template = "__QUOTE_{}__"
    quote_index = 0

    def replace_quote(match):
        nonlocal quote_index
        placeholder = placeholder_template.format(quote_index)
        # 使用 re.escape 确保占位符本身在后续正则中安全
        quotes[re.escape(placeholder)] = match.group(0)
        quote_index += 1
        return placeholder

    # 1. 保护引号内容: 替换所有 "..." 为占位符
    quote_pattern = r'\u201C[^\u201D]*\u201D' # "..."
    text_with_placeholders = re.sub(quote_pattern, replace_quote, text)

    # 2. 按句末标点分割 (仅在引号外部)
    sentence_enders_pattern = r'[\u3002\uFF1F\uFF01]' # .?!
    split_points = [0] # Start of text
    for match in re.finditer(sentence_enders_pattern, text_with_placeholders):
        split_points.append(match.end()) # End of punctuation is a split point

    # 如果文本末尾没有句末标点，确保包含最后一部分
    if split_points[-1] < len(text_with_placeholders):
         split_points.append(len(text_with_placeholders))

    # 根据分割点创建初步的段落列表
    initial_segments_with_placeholders = []
    for i in range(len(split_points) - 1):
        segment = text_with_placeholders[split_points[i]:split_points[i+1]].strip()
        if segment:
            initial_segments_with_placeholders.append(segment)

    # 如果没有有效的分割（例如，文本不包含句末标点），则处理整个文本块
    if not initial_segments_with_placeholders and text_with_placeholders.strip():
        initial_segments_with_placeholders = [text_with_placeholders.strip()]

    # 3. Refine Split: 在相邻占位符之间分割 (避免使用变长 lookbehind)
    refined_segments_with_placeholders = []
    # 定义一个独特的分隔符
    delimiter = "@@ADJACENT_QUOTE_SPLIT@@"
    # 正则：匹配第一个占位符及其后的空格，当其后紧跟另一个占位符时
    # 使用先行断言 (?=...) 来检查后面的占位符，但不消耗它
    adjacency_pattern = r'(\b__QUOTE_\d+__\b)\s*(?=\b__QUOTE_\d+__\b)'

    for segment in initial_segments_with_placeholders:
        # 使用 re.sub 将匹配到的 '占位符1 + 空格' 替换为 '占位符1 + 分隔符'
        modified_segment = re.sub(adjacency_pattern, r'\1' + delimiter, segment)
        # 按分隔符分割
        sub_segments = modified_segment.split(delimiter)
        # 添加非空、去除首尾空格的子段落
        refined_segments_with_placeholders.extend([s.strip() for s in sub_segments if s.strip()])


    # 4. 恢复引号内容
    restored_segments = []
    for segment in refined_segments_with_placeholders:
        restored_segment = segment
        # 迭代恢复占位符
        # 注意：字典迭代顺序在Python 3.7+是插入顺序，但这里顺序不重要
        for placeholder_escaped, original_quote in quotes.items():
             # 使用 re.sub 替换，因为 placeholder_escaped 已经是转义过的正则模式
             restored_segment = re.sub(placeholder_escaped, original_quote, restored_segment)
        if restored_segment:
             restored_segments.append(restored_segment)


    # 5. 后处理：合并以特定标点开头的段落
    if not restored_segments:
        return ""

    processed_paragraphs = []
    if restored_segments:
        processed_paragraphs.append(restored_segments[0])

        # 定义不允许出现在段首的标点 (使用 Unicode 转义)
        forbidden_leading_chars = (
            '\u3011', # 】
            '\uFF09', # ）
            '\uFF0C', # ，
            '\u3002', # 。
            '\uFF01', # ！
            '\uFF1F', # ？
            '\uFF1B'  # ；
            # 注意：这里不包含开始引号" (\u201C)，因为我们希望它能开启新段落
        )

        for i in range(1, len(restored_segments)):
            current_segment = restored_segments[i]
            if current_segment.startswith(forbidden_leading_chars):
                processed_paragraphs[-1] += current_segment
            else:
                processed_paragraphs.append(current_segment)

    return '\n\n'.join(processed_paragraphs)

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