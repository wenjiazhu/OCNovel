import os
import logging
import re
import string
import random
from typing import Optional, Set, Dict, List
# from opencc import OpenCC # Keep if used elsewhere, otherwise remove
from ..common.data_structures import Character, ChapterOutline # Keep if Character is used later
from ..common.utils import load_json_file, save_json_file, clean_text, validate_directory
# --- Import the correct prompt function ---
from .. import prompts # Import the prompts module

# Get logger
logger = logging.getLogger(__name__)

class NovelFinalizer:
    def __init__(self, config, content_model, knowledge_base):
        self.config = config
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.output_dir = config.output_config["output_dir"]
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)

    def finalize_chapter(self, chapter_num: int, update_characters: bool = False, update_summary: bool = True) -> bool:
        """处理章节的定稿工作
        
        Args:
            chapter_num: 要处理的章节号
            update_characters: 是否更新角色状态
            update_summary: 是否更新章节摘要
            
        Returns:
            bool: 处理是否成功
        """
        logger.info(f"开始定稿第 {chapter_num} 章...")
        try:
            # Load outline to get the title for the filename
            outline_file = os.path.join(self.output_dir, "outline.json")
            logger.info(f"实际读取的大纲文件路径: {outline_file}")
            if not os.path.exists(outline_file):
                logger.error(f"无法找到大纲文件: {outline_file}")
                return False

            outline_data = load_json_file(outline_file, default_value={})
            # Handle both dict {chapters: []} and list [] formats
            chapters_list = []
            if isinstance(outline_data, dict) and "chapters" in outline_data and isinstance(outline_data["chapters"], list):
                 chapters_list = outline_data["chapters"]
            elif isinstance(outline_data, list):
                 chapters_list = outline_data
            else:
                 logger.error(f"无法识别的大纲文件格式: {outline_file}")
                 return False

            if not (1 <= chapter_num <= len(chapters_list)):
                logger.error(f"章节号 {chapter_num} 超出大纲范围 (1-{len(chapters_list)})")
                return False

            chapter_outline_data = chapters_list[chapter_num - 1]
            if not isinstance(chapter_outline_data, dict):
                 logger.error(f"第 {chapter_num} 章的大纲条目不是有效的字典格式。")
                 return False

            title = chapter_outline_data.get('title', f'无标题章节{chapter_num}') # Default title if missing
            cleaned_title = self._clean_filename(title) # Use helper method

            # Construct the chapter filename
            chapter_file = os.path.join(self.output_dir, f"第{chapter_num}章_{cleaned_title}.txt")
            logger.debug(f"尝试读取章节文件: {chapter_file}")

            if not os.path.exists(chapter_file):
                logger.error(f"章节文件不存在: {chapter_file}")
                return False

            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug(f"成功读取章节 {chapter_num} 内容，长度: {len(content)}")
            
            # Generate/update summary
            if update_summary:
                logger.info(f"开始更新第 {chapter_num} 章摘要...")
                if not self._update_summary(chapter_num, content):
                    # _update_summary logs its own errors
                    return False
                logger.info(f"第 {chapter_num} 章摘要更新成功。")
            
            logging.info(f"第 {chapter_num} 章定稿完成")
            
            # 新增：定稿章节号为5的倍数时，自动更新sync_info.json
            if chapter_num % 5 == 0:
                try:
                    from ..content.content_generator import ContentGenerator
                    # 构造临时ContentGenerator实例，仅用于同步信息更新
                    temp_content_gen = ContentGenerator(self.config, self.content_model, self.knowledge_base)
                    temp_content_gen.current_chapter = chapter_num
                    temp_content_gen._load_outline()  # 修复：主动加载大纲
                    temp_content_gen._trigger_sync_info_update(self.content_model)
                    logger.info(f"章节号 {chapter_num} 为5的倍数，已自动更新sync_info.json")
                except Exception as sync_e:
                    logger.error(f"章节号 {chapter_num} 为5的倍数，但自动更新sync_info.json失败: {sync_e}", exc_info=True)
            
            return True
            
        except Exception as e:
            # Log the full traceback for unexpected errors
            logger.error(f"处理章节 {chapter_num} 定稿时发生意外错误: {str(e)}", exc_info=True)
            return False

    def _clean_filename(self, filename: str) -> str:
        """清理字符串，使其适合作为文件名"""
        # Remove common illegal characters
        cleaned = re.sub(r'[\\/*?:"<>|]', "", str(filename)) # Ensure input is string
        # Remove potentially problematic leading/trailing spaces or dots
        cleaned = cleaned.strip(". ")
        # Prevent overly long filenames (optional)
        # max_len = 100
        # if len(cleaned) > max_len:
        #     name_part, ext = os.path.splitext(cleaned)
        #     cleaned = name_part[:max_len-len(ext)-3] + "..." + ext
        # Provide a default name if cleaned is empty
        if not cleaned:
            # Use chapter number if available, otherwise random int
            # This method doesn't know the chapter number directly, so use random
            return f"untitled_chapter_{random.randint(1000,9999)}"
        return cleaned

    def _update_summary(self, chapter_num: int, content: str) -> bool:
        """生成并更新章节摘要"""
        try:
            summary_file = os.path.join(self.output_dir, "summary.json")
            # Load existing summaries safely
            summaries = load_json_file(summary_file, default_value={})
            if not isinstance(summaries, dict):
                 logger.warning(f"摘要文件 {summary_file} 内容不是字典，将重新创建。")
                 summaries = {}

            # Generate new summary
            # Limit content length to avoid excessive prompt size/cost
            max_content_for_summary = self.config.generation_config.get("summary_max_content_length", 4000)
            # --- Call the imported prompt function ---
            prompt = prompts.get_summary_prompt(content[:max_content_for_summary])
            # --- End of change ---
            logger.debug(f"为第 {chapter_num} 章生成摘要的提示词 (前100字符): {prompt[:100]}...")
            new_summary = self.content_model.generate(prompt)

            if not new_summary or not new_summary.strip():
                 logger.error(f"模型未能为第 {chapter_num} 章生成有效摘要。")
                 return False # Treat empty summary as failure

            # Clean the summary text
            cleaned_summary = self._clean_summary(new_summary)
            logger.debug(f"第 {chapter_num} 章生成的原始摘要 (前100字符): {new_summary[:100]}...")
            logger.debug(f"第 {chapter_num} 章清理后的摘要 (前100字符): {cleaned_summary[:100]}...")

            # Update the summaries dictionary
            summaries[str(chapter_num)] = cleaned_summary # Use string key

            # Save updated summaries
            if save_json_file(summary_file, summaries):
                # logger.info(f"已更新第 {chapter_num} 章摘要") # Moved success log to finalize_chapter
                return True
            else:
                 logger.error(f"保存摘要文件 {summary_file} 失败。")
                 return False

        except Exception as e:
            logger.error(f"更新第 {chapter_num} 章摘要时出错: {str(e)}", exc_info=True)
            return False

    def _clean_summary(self, summary: str) -> str:
        """清理摘要文本，移除常见的前缀、格式和多余空白"""
        if not summary:
            return ""

        cleaned_summary = summary.strip() # Initial trim

        # Patterns to remove at the beginning (case-insensitive)
        patterns_to_remove = [
            r"^\s*好的，根据你提供的内容，以下是章节摘要[:：\s]*",
            r"^\s*好的，这是章节摘要[:：\s]*",
            r"^\s*以下是章节摘要[:：\s]*",
            r"^\s*章节摘要[:：\s]*",
            r"^\s*摘要[:：\s]*",
            r"^\s*\*\*摘要[:：\s]*\*\*", # Handle markdown bold
            r"^\s*本章讲述了?[:：\s]*",
            r"^\s*本章主要讲述了?[:：\s]*",
            r"^\s*本章描述了?[:：\s]*",
            r"^\s*本章主要描述了?[:：\s]*",
            r"^\s*本章叙述了?[:：\s]*",
            r"^\s*本章主要叙述了?[:：\s]*",
            r"^\s*本章介绍了?[:：\s]*",
            r"^\s*本章主要介绍了?[:：\s]*",
            r"^\s*这一章?节?主要[:：\s]*",
            r"^\s*本章内容摘要如下[:：\s]*",
            # Add more patterns as needed
        ]

        # Remove patterns iteratively
        for pattern in patterns_to_remove:
            # Use re.IGNORECASE for case-insensitivity
            # Use re.DOTALL in case newlines are part of the pattern
            cleaned_summary = re.sub(pattern, "", cleaned_summary, flags=re.IGNORECASE | re.DOTALL).strip()

        # Final trim to remove any leading/trailing whitespace possibly left by removal
        cleaned_summary = cleaned_summary.strip()

        return cleaned_summary

if __name__ == "__main__":
    import argparse
    # 绝对导入，兼容直接运行
    from src.config.config import Config
    from src.models import ContentModel, KnowledgeBase
    
    parser = argparse.ArgumentParser(description='处理小说章节的定稿工作')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    parser.add_argument('--chapter', type=int, required=True, help='要处理的章节号')
    
    args = parser.parse_args()
    
    # 加载配置
    config = Config(args.config)
    
    # 初始化模型和知识库
    content_model = ContentModel(config)
    knowledge_base = KnowledgeBase(config)
    
    # 创建定稿器
    finalizer = NovelFinalizer(config, content_model, knowledge_base)
    
    # 处理定稿
    success = finalizer.finalize_chapter(args.chapter)
    
    if success:
        print("章节定稿处理成功！")
    else:
        print("章节定稿处理失败，请查看日志文件了解详细信息。") 