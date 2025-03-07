import json
import os

def split_novel_analysis_to_txt(json_file_path, output_dir):
    """
    将 novel_analysis.json 文件按章节拆分为多个 TXT 文件。
    每个 TXT 文件包含一个章节的分析结果。

    Args:
        json_file_path (str): novel_analysis.json 文件的路径。
        output_dir (str):  输出 TXT 文件的目录。
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            novel_analysis_data = json.load(f)
    except FileNotFoundError:
        print(f"错误: JSON 文件未找到: {json_file_path}")
        return
    except json.JSONDecodeError:
        print(f"错误: JSON 文件解码失败，请检查文件格式是否正确: {json_file_path}")
        return
    except Exception as e:
        print(f"读取 JSON 文件时发生错误: {e}")
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir) #  如果输出目录不存在，则创建

    chapters = novel_analysis_data.get('chapters', [])
    if not chapters:
        print("JSON 文件中没有章节分析数据。")
        return

    for chapter in chapters:
        chapter_id = chapter.get('id', 'unknown-chapter') # 获取章节 ID，如果没有则使用默认值
        chapter_title = chapter.get('title', 'untitled-chapter') # 获取章节标题，如果没有则使用默认值
        analysis_content = chapter.get('analysis')

        if analysis_content:
            #  构建 TXT 文件名，使用章节 ID 和标题 (如果存在)
            if chapter_title and chapter_title != 'untitled-chapter':
                #  清理标题，移除特殊字符，用下划线替换空格等
                safe_title = chapter_title.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_").replace("?", "_").replace("\"", "_").replace("<", "_").replace(">", "_").replace("|", "_")
                txt_file_name = f"{chapter_id}-{safe_title}.txt"
            else:
                txt_file_name = f"{chapter_id}.txt"

            txt_file_path = os.path.join(output_dir, txt_file_name)

            try:
                with open(txt_file_path, 'w', encoding='utf-8') as txt_file:
                    #  将 analysis_content 写入 TXT 文件
                    if isinstance(analysis_content, dict):
                        #  如果 analysis_content 是 JSON 对象 (字典)，则以格式化的 JSON 字符串写入
                        json.dump(analysis_content, txt_file, indent=2, ensure_ascii=False)
                    elif isinstance(analysis_content, list):
                        #  如果 analysis_content 是 JSON 数组 (列表)，则以格式化的 JSON 字符串写入
                        json.dump(analysis_content, txt_file, indent=2, ensure_ascii=False)
                    else:
                        #  否则，直接写入文本内容 (假设是字符串)
                        txt_file.write(str(analysis_content)) # 确保写入的是字符串

                print(f"章节分析结果已保存到: {txt_file_path}")

            except Exception as e:
                print(f"保存章节 {chapter_id} TXT 文件时发生错误: {e}")
        else:
            print(f"章节 {chapter_id} 没有分析内容，跳过生成 TXT 文件。")

    print("***** JSON 文件拆分完成 *****")


if __name__ == "__main__":
    json_file = "novel_analysis.json" #  替换为您的 novel_analysis.json 文件路径
    output_directory = "chapter_analyses" #  指定输出 TXT 文件的目录名

    split_novel_analysis_to_txt(json_file, output_directory)