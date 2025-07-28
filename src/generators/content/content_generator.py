import os
import logging
import time
from typing import Optional, List, Any, Dict
import math
from .consistency_checker import ConsistencyChecker
from .validators import LogicValidator, DuplicateValidator
from ..common.data_structures import ChapterOutline
from ..common.utils import load_json_file, save_json_file, validate_directory
import re
from logging.handlers import RotatingFileHandler
import sys
import json
from ..prompts import (
    get_chapter_prompt,
    get_sync_info_prompt,
    get_knowledge_search_prompt
)
import numpy as np
import functools

# Get a logger specific to this module
logger = logging.getLogger(__name__)

class ContentGenerator:
    def __init__(self, config, content_model, knowledge_base, finalizer: Optional[Any] = None):
        self.config = config
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.output_dir = config.output_config["output_dir"]
        self.chapter_outlines = []
        self.current_chapter = 0
        self.finalizer = finalizer
        
        # 新增：缓存计数器和同步信息生成器
        self.chapters_since_last_cache = 0
        self.content_kb_dir = os.path.join(self.output_dir, "content_kb")
        self.sync_info_file = os.path.join(self.output_dir, "sync_info.json")
        
        # 验证并创建缓存目录
        os.makedirs(self.content_kb_dir, exist_ok=True)
        
        # 初始化重生成相关的属性
        self.target_chapter = None
        self.external_prompt = None
        
        # 初始化验证器和检查器
        self.consistency_checker = ConsistencyChecker(content_model, self.output_dir)
        self.logic_validator = LogicValidator(content_model)
        self.duplicate_validator = DuplicateValidator(content_model)
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)
        # 加载现有大纲和进度
        self._load_progress()
        
        # 初始化知识库
        self._init_knowledge_base()

        self.imitation_config = getattr(config, 'imitation_config', {})
        self.default_style = '古风雅致'  # 默认风格

    def _load_outline(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        outline_data = load_json_file(outline_file, default_value=[])
        
        if outline_data:
            chapters_list = outline_data.get("chapters", outline_data) if isinstance(outline_data, dict) else outline_data
            if isinstance(chapters_list, list):
                try:
                    valid_chapters = [ch for ch in chapters_list if isinstance(ch, dict)]
                    if len(valid_chapters) != len(chapters_list):
                         logger.warning(f"大纲文件中包含非字典元素，已跳过。")
                    self.chapter_outlines = [ChapterOutline(**chapter) for chapter in valid_chapters]
                    logger.info(f"从文件加载了 {len(self.chapter_outlines)} 章大纲")
                except TypeError as e:
                    logger.error(f"加载大纲时字段不匹配或类型错误: {e} - 请检查 outline.json 结构是否与 ChapterOutline 定义一致。问题可能出在: {chapters_list[:2]}...")
                    self.chapter_outlines = []
                except Exception as e:
                     logger.error(f"加载大纲时发生未知错误: {e}", exc_info=True)
                     self.chapter_outlines = []
            else:
                logger.error("大纲文件格式无法识别，应为列表或包含 'chapters' 键的字典。")
                self.chapter_outlines = []
        else:
            logger.info("未找到大纲文件或文件为空。")
            self.chapter_outlines = []

    def _load_progress(self):
        """从 summary.json 加载生成进度"""
        summary_file = os.path.join(self.output_dir, "summary.json")
        try:
            if os.path.exists(summary_file):
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summary_data = json.load(f)
                    # 获取最大的章节号作为当前进度
                    chapter_numbers = [int(k) for k in summary_data.keys() if k.isdigit()]
                    self.current_chapter = max(chapter_numbers) if chapter_numbers else 0
            else:
                self.current_chapter = 0
            logger.info(f"从 summary.json 加载进度，下一个待处理章节索引: {self.current_chapter}")
        except Exception as e:
            logger.error(f"加载进度时出错: {str(e)}")
            self.current_chapter = 0

    def _save_progress(self):
        """保存生成进度到 summary.json"""
        # 不再需要单独保存 progress.json
        # 因为进度信息已经包含在 summary.json 中的最大章节号中
        logger.info(f"进度已更新，下一个待处理章节索引: {self.current_chapter}")

    def get_style_prompt(self, style_name: Optional[str] = None) -> str:
        """
        根据风格名获取extra_prompt，若未指定则用默认风格。
        """
        imitation = self.imitation_config.get('auto_imitation', {})
        style_sources = imitation.get('style_sources', [])
        # 优先用参数，否则用imitation_config.default_style，否则用self.default_style
        style = style_name or imitation.get('default_style') or self.default_style
        for s in style_sources:
            if s.get('name') == style:
                return s.get('extra_prompt', '')
        # 未找到则返回空
        return ''

    def get_style_reference(self, style_name: Optional[str] = None, max_length: int = 3000) -> (str, str):
        """
        获取风格extra_prompt和file_path指定的风格示例文本内容。
        Args:
            style_name: 风格名
            max_length: 示例文本最大长度（字符）
        Returns:
            (extra_prompt, style_example_text)
        """
        imitation = self.imitation_config.get('auto_imitation', {})
        style_sources = imitation.get('style_sources', [])
        style = style_name or imitation.get('default_style') or self.default_style
        for s in style_sources:
            if s.get('name') == style:
                extra_prompt = s.get('extra_prompt', '')
                file_path = s.get('file_path')
                style_example = ''
                if file_path:
                    abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.config.base_dir, file_path)
                    try:
                        with open(abs_path, 'r', encoding='utf-8') as f:
                            style_example = f.read()
                            if max_length > 0 and len(style_example) > max_length:
                                style_example = style_example[:max_length] + '\n...（示例已截断）'
                    except Exception as e:
                        logger.warning(f"读取风格示例文本失败: {abs_path} - {e}")
                        style_example = ''
                return extra_prompt, style_example
        return '', ''

    def generate_content(self, target_chapter: Optional[int] = None, external_prompt: Optional[str] = None, style_name: Optional[str] = None) -> bool:
        """
        生成章节内容，支持传入风格名
        """
        self._load_outline()
        if not self.chapter_outlines:
            logger.error("无法生成内容：大纲未加载或为空。请先生成大纲。")
            return False
        try:
            if target_chapter is not None:
                if 1 <= target_chapter <= len(self.chapter_outlines):
                    return self._process_single_chapter(target_chapter, external_prompt, style_name=style_name)
                else:
                    logger.error(f"目标章节 {target_chapter} 超出大纲范围 (1-{len(self.chapter_outlines)})。")
                    return False
            else:
                return self._generate_remaining_chapters(style_name=style_name)
        except Exception as e:
            logger.error(f"生成章节内容时发生未预期错误: {str(e)}", exc_info=True)
            return False

    def _process_single_chapter(self, chapter_num: int, external_prompt: Optional[str] = None, max_retries: int = 3, style_name: Optional[str] = None) -> bool:
        """
        处理单个章节的生成、验证、保存和定稿，支持风格名
        """
        if not (1 <= chapter_num <= len(self.chapter_outlines)):
            logger.error(f"无效的章节号: {chapter_num}")
            return False
        chapter_outline = self.chapter_outlines[chapter_num - 1]
        logger.info(f"[Chapter {chapter_num}] 开始处理章节: {chapter_outline.title}")
        success = False
        for attempt in range(max_retries):
            logger.info(f"[Chapter {chapter_num}] 尝试 {attempt + 1}/{max_retries}")
            try:
                # 1. 生成原始内容，拼接风格示例和风格要求
                extra_prompt, style_example = self.get_style_reference(style_name)
                style_block = ''
                if style_example:
                    style_block += f"【风格示例】\n{style_example}\n"
                if extra_prompt:
                    style_block += f"【风格要求】{extra_prompt}\n"
                merged_prompt = style_block + (external_prompt or '')
                raw_content = self._generate_chapter_content(chapter_outline, merged_prompt)
                if not raw_content:
                    raise Exception("原始内容生成失败，返回为空。")

                # 2. 加载同步信息
                sync_info = self._load_sync_info()
                
                # 3. 逻辑验证
                logic_report, needs_logic_revision = self.logic_validator.check_logic(
                    raw_content, 
                    chapter_outline.__dict__,
                    sync_info
                )
                logger.info(
                    f"[Chapter {chapter_num}] 逻辑验证报告 (摘要): {logic_report[:200]}..."
                    f"\n需要修改: {'是' if needs_logic_revision else '否'}"
                )

                # 4. 一致性验证
                logger.info(f"[Chapter {chapter_num}] 开始一致性检查...")
                final_content = self.consistency_checker.ensure_chapter_consistency(
                    chapter_content=raw_content,
                    chapter_outline=chapter_outline.__dict__,
                    sync_info=sync_info,
                    chapter_idx=chapter_num - 1
                )
                logger.info(f"[Chapter {chapter_num}] 一致性检查完成")

                # 5. 重复文字验证
                duplicate_report, needs_duplicate_revision = self.duplicate_validator.check_duplicates(
                    final_content,
                    self._load_adjacent_chapter(chapter_num - 1),
                    self._load_adjacent_chapter(chapter_num + 1) if chapter_num < len(self.chapter_outlines) else ""
                )
                logger.info(
                    f"[Chapter {chapter_num}] 重复文字验证报告 (摘要): {duplicate_report[:200]}..."
                    f"\n需要修改: {'是' if needs_duplicate_revision else '否'}"
                )

                # 6. 保存最终内容
                if self._save_chapter_content(chapter_num, final_content):
                    logger.info(f"[Chapter {chapter_num}] 内容保存成功")

                    # 7. 调用 Finalizer (如果提供了)
                    if self.finalizer:
                        logger.info(f"[Chapter {chapter_num}] 开始调用 Finalizer 进行定稿...")
                        finalize_success = self.finalizer.finalize_chapter(
                            chapter_num=chapter_num,
                            update_summary=True
                        )
                        if finalize_success:
                            logger.info(f"[Chapter {chapter_num}] 定稿成功")
                            self.current_chapter = chapter_num
                        else:
                            logger.error(f"[Chapter {chapter_num}] 定稿失败")
                    else:
                        logger.warning(f"[Chapter {chapter_num}] Finalizer 未提供，跳过定稿步骤。")
                        self.current_chapter = chapter_num
                    self._check_and_update_cache(chapter_num)
                    success = True
                    break
                else:
                    raise Exception("保存最终内容失败")
            except Exception as e:
                logger.error(f"[Chapter {chapter_num}] 处理出错: {str(e)}", exc_info=True)
                success = False
                if attempt >= max_retries - 1:
                    logger.error(f"[Chapter {chapter_num}] 达到最大重试次数")
                    return False
                time.sleep(self.config.generation_config.get("retry_delay", 10))
        return success

    def _load_adjacent_chapter(self, chapter_num: int) -> str:
        """加载相邻章节内容（用于重复验证）"""
        try:
            if 1 <= chapter_num <= len(self.chapter_outlines):
                filename = f"第{chapter_num}章_{self._clean_filename(self.chapter_outlines[chapter_num-1].title)}.txt"
                filepath = os.path.join(self.output_dir, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return f.read()
        except Exception as e:
            logger.warning(f"加载第 {chapter_num} 章内容失败: {str(e)}")
        return ""

    def _generate_remaining_chapters(self, style_name: Optional[str] = None) -> bool:
        """
        生成所有剩余章节，支持风格名
        """
        logger.info(f"开始生成剩余章节，从索引 {self.current_chapter} (即第 {self.current_chapter + 1} 章) 开始...")
        initial_start_chapter_index = self.current_chapter
        while self.current_chapter < len(self.chapter_outlines):
            current_chapter_num = self.current_chapter + 1
            success = self._process_single_chapter(current_chapter_num, style_name=style_name)
            if not success:
                logger.error(f"处理第 {current_chapter_num} 章失败，中止剩余章节生成。")
                return False
            self._save_progress()
        if self.current_chapter > initial_start_chapter_index:
            logger.info("所有剩余章节处理完成。")
            return True
        elif self.current_chapter == len(self.chapter_outlines):
            logger.info("所有章节均已处理完成。")
            return True
        else:
            logger.info(f"没有需要生成的剩余章节（当前进度索引: {self.current_chapter}）。")
            return True

    def _regenerate_specific_chapter(self, chapter_num: int, external_prompt: Optional[str] = None) -> bool:
         """重新生成指定章节的入口"""
         logger.info(f"请求重新生成第 {chapter_num} 章...")
         return self._process_single_chapter(chapter_num, external_prompt)

    def _generate_chapter_content(self, chapter_outline: ChapterOutline, extra_prompt: Optional[str] = None) -> Optional[str]:
        """生成单章的原始内容"""
        try:
            chapter_num = chapter_outline.chapter_number
            logger.info(f"开始为第 {chapter_num} 章生成原始内容...")
            context = self._get_context_for_chapter(chapter_num)
            references = self._get_references_for_chapter(chapter_outline)
            
            # 获取故事设定和同步信息
            story_config = self.config.novel_config if hasattr(self.config, 'novel_config') else None
            sync_info = self._load_sync_info()

            # 使用 prompts.py 中的方法
            prompt = get_chapter_prompt(
                outline=chapter_outline.__dict__,
                references=references,
                extra_prompt=extra_prompt or "",
                context_info=context,
                story_config=story_config,  # 新增：传递故事设定
                sync_info=sync_info  # 新增：传递同步信息
            )
            logger.debug(f"完整提示词: {prompt}")

            # 调用模型生成内容
            content = self.content_model.generate(prompt)
            if not content or not content.strip():
                logger.error(f"第 {chapter_num} 章：模型返回内容为空或仅包含空白字符。")
                return None

            logger.info(f"第 {chapter_num} 章：原始内容生成成功，字数: {len(content)}")
            return content

        except Exception as e:
            logger.error(f"生成第 {chapter_outline.chapter_number} 章原始内容时出错: {str(e)}", exc_info=True)
            return None

    def _clean_filename(self, filename: str) -> str:
        """清理字符串，使其适合作为文件名"""
        # 移除常见非法字符
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
        # 替换空格为下划线（可选）
        # cleaned = cleaned.replace(" ", "_")
        # 移除可能导致问题的首尾空格或点
        cleaned = cleaned.strip(". ")
        # 防止文件名过长 (可选)
        # max_len = 100
        # if len(cleaned) > max_len:
        #     name_part, ext = os.path.splitext(cleaned)
        #     cleaned = name_part[:max_len-len(ext)-3] + "..." + ext
        # 如果清理后为空，提供默认名称
        if not cleaned:
            return "untitled_chapter"
        return cleaned

    def _save_chapter_content(self, chapter_num: int, content: str) -> bool:
        """保存章节内容，使用 '第X章_标题.txt' 格式"""
        try:
            # 检查 chapter_num 是否在有效范围内
            if not (1 <= chapter_num <= len(self.chapter_outlines)):
                logger.error(f"无法保存章节 {chapter_num}：无效的章节号。")
                return False

            # 获取章节大纲和标题
            chapter_outline = self.chapter_outlines[chapter_num - 1]
            title = chapter_outline.title

            # 清理标题作为文件名的一部分
            cleaned_title = self._clean_filename(title)

            # 构建新的文件名格式
            filename = f"第{chapter_num}章_{cleaned_title}.txt"
            chapter_file = os.path.join(self.output_dir, filename)

            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"已保存第 {chapter_num} 章内容到 {chapter_file}")
            return True

        except IndexError:
             logger.error(f"无法获取第 {chapter_num} 章的大纲信息来生成文件名。")
             return False
        except Exception as e:
            logger.error(f"保存第 {chapter_num} 章内容时出错: {str(e)}")
            return False

    def _get_context_for_chapter(self, chapter_num: int) -> str:
        """获取章节的上下文信息（包括前一章摘要和内容）"""
        if chapter_num > 1:
            context_parts = []
            
            # 1. 尝试获取前一章摘要（限制长度）
            try:
                prev_summary = self.consistency_checker._get_previous_summary(chapter_num - 1)
                if prev_summary:
                    # 限制摘要长度
                    max_summary_length = 500
                    if len(prev_summary) > max_summary_length:
                        prev_summary = prev_summary[:max_summary_length] + "..."
                    context_parts.append(f"前一章摘要：{prev_summary}")
                    logger.debug(f"获取到第 {chapter_num-1} 章摘要")
            except Exception as e:
                logger.warning(f"获取第 {chapter_num-1} 章摘要时出错: {e}")

            # 2. 获取前一章内容（进一步限制长度）
            try:
                prev_chapter_num = chapter_num - 1
                if 0 <= prev_chapter_num - 1 < len(self.chapter_outlines):
                    prev_chapter_title = self.chapter_outlines[prev_chapter_num - 1].title
                    cleaned_prev_title = self._clean_filename(prev_chapter_title)
                    prev_chapter_filename = f"第{prev_chapter_num}章_{cleaned_prev_title}.txt"
                    prev_chapter_file = os.path.join(self.output_dir, prev_chapter_filename)
                    
                    if os.path.exists(prev_chapter_file):
                        with open(prev_chapter_file, 'r', encoding='utf-8') as f:
                            prev_content = f.read()
                            # 进一步限制内容长度，只取最后一部分
                            max_prev_content_length = 1500  # 减少到1500字符
                            if len(prev_content) > max_prev_content_length:
                                context_parts.append(f"前一章结尾：{prev_content[-max_prev_content_length:]}")
                            else:
                                context_parts.append(f"前一章内容：{prev_content}")
                            logger.debug(f"获取到第 {prev_chapter_num} 章内容")
                    else:
                        logger.warning(f"未找到前一章文件 {prev_chapter_file}")
            except Exception as e:
                logger.warning(f"读取第 {prev_chapter_num} 章内容时出错: {str(e)}")

            # 返回所有上下文信息，并限制总长度
            if context_parts:
                combined_context = "\n".join(context_parts)
                # 限制总上下文长度
                max_total_context_length = 2000
                if len(combined_context) > max_total_context_length:
                    combined_context = combined_context[-max_total_context_length:] + "...(前文已省略)"
                return combined_context
            return "（无法获取前一章信息）"
        else:
            return "（这是第一章，无前文）"

    def _get_references_for_chapter(self, chapter_outline: ChapterOutline) -> dict:
        """获取章节的参考信息（从知识库），使用优化后的检索逻辑"""
        references = {
            "plot_references": [],
            "character_references": [],
            "setting_references": []
        }

        try:
            # 检查知识库状态
            if not hasattr(self.knowledge_base, 'is_built') or not self.knowledge_base.is_built:
                logging.warning("知识库未构建，跳过检索")
                return references
                
            if not hasattr(self.knowledge_base, 'index') or self.knowledge_base.index is None:
                logging.warning("知识库索引不存在，跳过检索")
                return references
            
            # 生成检索关键词
            search_prompt = get_knowledge_search_prompt(
                chapter_number=chapter_outline.chapter_number,
                chapter_title=chapter_outline.title,
                characters_involved=chapter_outline.characters,
                key_items=chapter_outline.key_points,  # 假设关键点可作为检索项
                scene_location=", ".join(chapter_outline.settings),
                chapter_role="发展",  # 可根据实际需求调整
                chapter_purpose="推动主线",  # 可根据实际需求调整
                foreshadowing="",  # 可根据实际需求补充
                short_summary="",  # 可根据实际需求补充
            )

            # 添加日志，记录搜索提示词
            logger.info(f"搜索提示词: {search_prompt[:100]}...，长度: {len(search_prompt)}")
            
            # 检查知识库对象
            logger.info(f"知识库对象类型: {type(self.knowledge_base)}")
            logger.info(f"知识库是否已构建: {getattr(self.knowledge_base, 'is_built', False)}")
            logger.info(f"知识库索引类型: {type(getattr(self.knowledge_base, 'index', None))}")
            
            # 调用知识库检索
            logger.info("开始调用知识库搜索方法...")
            relevant_knowledge = self.knowledge_base.search(search_prompt)
            
            # 检查返回结果
            logger.info(f"知识库搜索返回结果类型: {type(relevant_knowledge)}")
            logger.info(f"知识库搜索返回结果长度: {len(relevant_knowledge) if relevant_knowledge else 0}")
            
            if relevant_knowledge and isinstance(relevant_knowledge, list):
                references["plot_references"] = relevant_knowledge[:3]  # 限制数量
                references["character_references"] = relevant_knowledge[3:6]
                references["setting_references"] = relevant_knowledge[6:9]
                logger.info(f"成功分配参考信息，共 {len(relevant_knowledge)} 项")
            else:
                logger.warning(f"知识库返回结果无效或为空: {relevant_knowledge}")

        except Exception as e:
            logger.error(f"优化检索章节参考信息时出错: {str(e)}", exc_info=True)  # 添加exc_info获取完整堆栈

        return references

    def _init_knowledge_base(self):
        """初始化知识库，确保在使用前已构建"""
        try:
            if not hasattr(self.knowledge_base, 'is_built') or not self.knowledge_base.is_built:
                kb_files = self.config.knowledge_base_config.get("reference_files", [])
                if not kb_files:
                    logger.warning("配置中未找到知识库参考文件路径")
                    return
                
                # 检查文件是否存在
                existing_files = []
                for file_path in kb_files:
                    if os.path.exists(file_path):
                        existing_files.append(file_path)
                    else:
                        logger.warning(f"参考文件不存在: {file_path}")
                
                if existing_files:
                    logger.info("开始构建知识库...")
                    self.knowledge_base.build_from_files(existing_files)
                    logger.info("知识库构建完成")
                else:
                    logger.error("没有找到任何可用的参考文件")
        except Exception as e:
            logger.error(f"初始化知识库时出错: {str(e)}")

    def _check_and_update_cache(self, chapter_num: int) -> None:
        """检查是否需要更新缓存，每5章更新一次"""
        # 修改判断逻辑，检查是否是第5/10/15...章
        logger.info(f"检查是否需要更新缓存，当前章节: {chapter_num}, 缓存条件: (chapter_num % 5) == 0, 结果: {(chapter_num % 5) == 0}")
        if (chapter_num % 5) == 0:  # 正好是5的倍数章节
            # 先更新当前章节进度，确保包含当前章节
            self.current_chapter = chapter_num
            logger.info(f"已完成第 {chapter_num} 章，开始更新缓存...")
            self._update_content_cache()
            logger.info(f"开始更新同步信息文件: {self.sync_info_file}")
            self._trigger_sync_info_update(self.content_model)
            self.chapters_since_last_cache = 0
        else:
            self.chapters_since_last_cache += 1
            logger.info(f"当前章节 {chapter_num} 不需要更新缓存，距离上次更新已经处理了 {self.chapters_since_last_cache} 章。")

    def _update_content_cache(self) -> None:
        """更新正文知识库缓存"""
        try:
            # 获取所有已完成章节的内容（包括当前章节）
            chapter_contents = []
            # 修改这里，使用 self.current_chapter + 1 确保包含当前章节
            for chapter_num in range(1, self.current_chapter + 1):
                filename = f"第{chapter_num}章_{self._clean_filename(self.chapter_outlines[chapter_num-1].title)}.txt"
                filepath = os.path.join(self.output_dir, filename)
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        chapter_contents.append(content)
                        logger.debug(f"已读取第 {chapter_num} 章内容，长度: {len(content)}")

            if chapter_contents:
                # 使用嵌入模型对内容进行向量化
                self.knowledge_base.build_from_texts(
                    texts=chapter_contents,
                    cache_dir=self.content_kb_dir
                )
                logger.info(f"正文知识库缓存更新完成，共处理 {len(chapter_contents)} 章内容")
            else:
                logger.warning("未找到任何已完成的章节内容")

        except Exception as e:
            logger.error(f"更新正文知识库缓存时出错: {str(e)}")

    def _trigger_sync_info_update(self, sync_model=None) -> None:
        """触发同步信息更新"""
        os.makedirs(os.path.dirname(self.sync_info_file), exist_ok=True)
        # 使用 self.current_chapter 而不是其他变量
        logger.info(f"准备更新同步信息，当前章节进度: {self.current_chapter}，同步信息文件: {self.sync_info_file}")
        try:
            all_content = ""
            # 修改：只读取最近5章的内容来更新同步信息
            # 确保从第1章开始，且不超过当前已完成的章节
            num_chapters_to_include = 5
            start_chapter_for_sync = max(1, self.current_chapter - num_chapters_to_include + 1)
            
            logger.info(f"将读取第 {start_chapter_for_sync} 章到第 {self.current_chapter} 章的内容来生成同步信息。")

            for chapter_num in range(start_chapter_for_sync, self.current_chapter + 1):
                if chapter_num - 1 < len(self.chapter_outlines): # 确保章节索引有效
                    filename = f"第{chapter_num}章_{self._clean_filename(self.chapter_outlines[chapter_num-1].title)}.txt"
                    filepath = os.path.join(self.output_dir, filename)
                    logger.debug(f"尝试读取章节文件: {filepath}")
                    if os.path.exists(filepath):
                        with open(filepath, 'r', encoding='utf-8') as f:
                            all_content += f.read() + "\n\n"
                    else:
                        logger.warning(f"文件不存在，无法读取: {filepath}")
                else:
                    logger.warning(f"章节大纲中不存在章节 {chapter_num}，跳过读取。")


            if all_content:
                logger.info(f"成功读取最近章节内容，总字数: {len(all_content)}，开始生成同步信息")
                prompt = self._create_sync_info_prompt(all_content)
                
                # 使用指定的模型或默认使用content_model
                model_to_use = sync_model if sync_model is not None else self.content_model
                
                # 增加重试机制和错误处理
                max_retries = 5  # 增加重试次数
                sync_info = None
                
                for attempt in range(max_retries):
                    try:
                        sync_info = model_to_use.generate(prompt)
                        if sync_info:
                            break
                        else:
                            logger.warning(f"模型返回空的同步信息，尝试 {attempt + 1}/{max_retries}")
                            if attempt == max_retries - 1:
                                logger.warning("模型返回空的同步信息，使用降级方案")
                                self._fallback_sync_info_update()
                                return
                    except Exception as e:
                        logger.error(f"模型调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                        if attempt == max_retries - 1:
                            logger.error("所有重试都失败了，使用降级方案")
                            self._fallback_sync_info_update()
                            return
                        # 等待一段时间后重试
                        time.sleep(10 * (attempt + 1))  # 递增等待时间
                
                if not sync_info:
                    logger.warning("模型返回空的同步信息，使用降级方案")
                    self._fallback_sync_info_update()
                    return
                
                try:
                    # 尝试提取JSON部分 - 有时模型会生成额外文本
                    json_start = sync_info.find('{')
                    json_end = sync_info.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_content = sync_info[json_start:json_end]
                        logger.info(f"提取到JSON内容，长度: {len(json_content)}")
                        sync_info_dict = json.loads(json_content)
                        # 在保存前，确保更新时间字段
                        sync_info_dict["最后更新时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"成功解析同步信息JSON，准备写入文件: {self.sync_info_file}")
                        with open(self.sync_info_file, 'w', encoding='utf-8') as f:
                            json.dump(sync_info_dict, f, ensure_ascii=False, indent=2)
                        logger.info(f"同步信息更新完成，文件大小: {os.path.getsize(self.sync_info_file)} 字节")
                    else:
                        logger.error(f"无法在生成的内容中找到JSON格式数据，原始内容前200个字符: {sync_info[:200]}...")
                        # 保存原始输出以供调试
                        debug_file = os.path.join(os.path.dirname(self.sync_info_file), "sync_info_raw.txt")
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(sync_info)
                        logger.info(f"已保存原始输出到 {debug_file} 以供调试")
                        self._fallback_sync_info_update()
                except json.JSONDecodeError as e:
                    logger.error(f"生成的同步信息不是有效的JSON格式: {e}")
                    logger.debug(f"无效的JSON内容前200个字符: {sync_info[:200]}...")
                    # 保存原始输出以供调试
                    debug_file = os.path.join(os.path.dirname(self.sync_info_file), "sync_info_raw.txt")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(sync_info)
                    logger.info(f"已保存原始输出到 {debug_file} 以供调试")
                    self._fallback_sync_info_update()
            else:
                logger.warning("未找到任何已完成的章节内容，使用降级方案")
                self._fallback_sync_info_update()
        except Exception as e:
            logger.error(f"更新同步信息时出错: {str(e)}", exc_info=True)
            self._fallback_sync_info_update()

    def _fallback_sync_info_update(self) -> None:
        """降级方案：手动更新同步信息"""
        try:
            logger.info("使用降级方案更新同步信息")
            
            # 加载现有同步信息
            existing_sync_info = {}
            if os.path.exists(self.sync_info_file):
                try:
                    with open(self.sync_info_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            existing_sync_info = json.loads(content)
                except Exception as e:
                    logger.warning(f"读取现有同步信息失败: {e}")
            
            # 更新当前章节进度
            existing_sync_info["当前章节"] = self.current_chapter
            existing_sync_info["最后更新时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 添加新的前情提要
            if "前情提要" not in existing_sync_info:
                existing_sync_info["前情提要"] = []
            
            # 获取最近完成的章节信息
            recent_chapters = []
            for chapter_num in range(max(1, self.current_chapter - 4), self.current_chapter + 1):
                if chapter_num - 1 < len(self.chapter_outlines):
                    outline = self.chapter_outlines[chapter_num - 1]
                    if outline:
                        recent_chapters.append(f"第{chapter_num}章：{outline.title}")
            
            if recent_chapters:
                summary = f"最近完成章节：{', '.join(recent_chapters)}"
                if summary not in existing_sync_info["前情提要"]:
                    existing_sync_info["前情提要"].append(summary)
            
            # 保存更新后的同步信息
            with open(self.sync_info_file, 'w', encoding='utf-8') as f:
                json.dump(existing_sync_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"降级方案同步信息更新完成")
            
        except Exception as e:
            logger.error(f"降级方案也失败了: {str(e)}", exc_info=True)

    def _create_sync_info_prompt(self, story_content: str) -> str:
        """创建生成同步信息的提示词"""
        existing_sync_info = ""
        if os.path.exists(self.sync_info_file):
            try:
                with open(self.sync_info_file, 'r', encoding='utf-8') as f:
                    existing_sync_info = f.read()
            except Exception as e:
                logger.warning(f"读取现有同步信息时出错: {str(e)}")

        return get_sync_info_prompt(
            story_content=story_content,
            existing_sync_info=existing_sync_info,
            current_chapter=self.current_chapter
        )

    def _load_sync_info(self) -> dict:
        """加载同步信息并解析为字典"""
        if os.path.exists(self.sync_info_file):
            try:
                with open(self.sync_info_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 处理空文件的情况
                    if not content.strip():
                         logger.warning(f"同步信息文件 {self.sync_info_file} 为空，返回空字典。")
                         return {}
                    # 解析 JSON 内容
                    return json.loads(content)
            except json.JSONDecodeError as e:
                # 处理 JSON 解析错误
                logger.error(f"解析同步信息文件 {self.sync_info_file} 失败: {e}。返回空字典。")
                # 可以选择保存错误内容以便调试
                # try:
                #     with open(self.sync_info_file + ".error", 'w', encoding='utf-8') as f_err:
                #         f_err.write(content)
                # except NameError: # Handle case where 'content' might not be defined if open failed
                #     logger.error(f"无法写入错误日志，因为读取 {self.sync_info_file} 可能已失败。")
                # except Exception as write_err:
                #     logger.error(f"写入 sync_info.error 文件失败: {write_err}")
                return {}
            except Exception as e:
                 # 处理其他可能的读取错误
                 logger.error(f"读取同步信息文件 {self.sync_info_file} 时发生其他错误: {e}。返回空字典。")
                 return {}
        else:
            # 文件不存在，返回空字典
            logger.warning(f"同步信息文件 {self.sync_info_file} 不存在，返回空字典。")
            return {}

if __name__ == "__main__":
    import argparse
    # Import necessary modules, handling potential ImportErrors for standalone testing
    try:
        from src.config.config import Config # Config is usually needed
        # Need re for MockConsistencyChecker's parsing of score
        import re
        # Need json for MockConsistencyChecker's _get_previous_summary
        import json
    except ImportError:
        logger.warning("无法导入实际的 Config 类，将使用占位符。")
        class Config: pass
        # Define re and json locally if import fails (less likely but for completeness)
        import re
        import json

    # --- Mock Class Definitions ---
    class MockModel:
        # Correct indentation for methods
        def generate(self, prompt):
            logger.debug(f"[MockModel] Generating based on prompt starting with: {prompt[:100]}...")
            if "一致性检查" in prompt:
                logger.debug("[MockModel] Simulating consistency check report generation.")
                # Simulate a report that passes
                return "一致性检查报告：\n[主题]：符合\n[情节]：连贯\n[角色]：一致\n[世界观]：符合\n[逻辑]：无明显问题\n[总体评分]：85\n结论：无需修改"
            elif "修正章节内容" in prompt:
                logger.debug("[MockModel] Simulating chapter revision generation.")
                return f"[Mock] 这是模拟修正后的内容，基于报告：{prompt[:100]}..."
            else:
                logger.debug("[MockModel] Simulating raw content generation.")
                return f"[Mock] 这是模拟生成的章节内容，基于提示：{prompt[:100]}..."

    class MockKB:
        # Correct indentation for methods
        def search(self, query: str, k: int = 5) -> List[str]:
            """搜索相关内容"""
            logger.debug(f"[MockKB] Searching for: {query}")
            
            if not self.index:
                logger.error("知识库索引未构建")
                raise ValueError("Knowledge base not built yet")
            
            # 安全地记录索引类型，不访问.d属性
            logger.info(f"知识库索引类型: {type(self.index)}")
            
            query_vector = self.embedding_model.embed(query)
            
            if query_vector is None:
                logger.error("嵌入模型返回空向量")
                return []
            
            logger.info(f"查询向量类型: {type(query_vector)}, 长度: {len(query_vector)}")
            
            # 搜索最相似的文本块
            query_vector_array = np.array([query_vector]).astype('float32')
            logger.info(f"处理后的查询向量数组形状: {query_vector_array.shape}")
            
            try:
                logger.info(f"调用faiss搜索，参数: 向量形状={query_vector_array.shape}, k={k}")
                distances, indices = self.index.search(query_vector_array, k)
                logger.info(f"搜索结果: 距离形状={distances.shape}, 索引形状={indices.shape}")
            except Exception as e:
                logger.error(f"faiss搜索失败: {str(e)}", exc_info=True)
                raise
            
            # 返回相关文本内容
            results = []
            for idx in indices[0]:
                if idx < len(self.chunks):
                    results.append(self.chunks[idx].content)
                else:
                    logger.warning(f"索引越界: idx={idx}, chunks长度={len(self.chunks)}")
            
            logger.info(f"返回结果数量: {len(results)}")
            return results

    class MockConsistencyChecker:
        # Correct indentation for methods
        def __init__(self, model, output_dir):
            logger.info(f"[MockConsistencyChecker] Initialized with model {type(model)} and output_dir {output_dir}.")
            self.model = model
            self.output_dir = output_dir

        # Correct indentation for methods
        def ensure_chapter_consistency(self, chapter_content, chapter_outline, chapter_idx, characters=None):
            logger.info(f"[MockConsistencyChecker] Ensuring consistency for chapter_idx {chapter_idx}")
            # Simulate check
            check_prompt = f"模拟一致性检查提示 for chapter {chapter_idx+1}"
            consistency_report = self.model.generate(check_prompt)
            logger.info(f"[MockConsistencyChecker] Received report:\n{consistency_report}")

            needs_revision = "需要修改" in consistency_report
            score_match = re.search(r'\[总体评分\]\s*:\s*(\d+)', consistency_report)
            score = int(score_match.group(1)) if score_match else 0

            if not needs_revision or score >= 75:
                logger.info(f"[MockConsistencyChecker] Chapter {chapter_idx+1} passed consistency check (Score: {score}).")
                return chapter_content
            else:
                logger.warning(f"[MockConsistencyChecker] Chapter {chapter_idx+1} needs revision (Score: {score}). Simulating revision...")
                revise_prompt = f"模拟修正提示 for chapter {chapter_idx+1} based on report: {consistency_report[:50]}..."
                revised_content = self.model.generate(revise_prompt)
                logger.info(f"[MockConsistencyChecker] Simulated revision complete for chapter {chapter_idx+1}.")
                return revised_content

        # Correct indentation for methods
        def _get_previous_summary(self, chapter_idx):
            logger.debug(f"[MockConsistencyChecker] Getting previous summary for chapter_idx {chapter_idx}")
            summary_file = os.path.join(self.output_dir, "summary.json")
            if chapter_idx >= 0 and os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summaries = json.load(f)
                        # Summaries keys are chapter numbers (1-based string)
                        return summaries.get(str(chapter_idx + 1 - 1), f"[Mock] Default Summary for Ch {chapter_idx}") # Get previous chapter's summary key is chapter_idx
                except Exception as e:
                    logger.error(f"[MockConsistencyChecker] Error reading summary file {summary_file}: {e}")
                    return f"[Mock] Error reading summary for Ch {chapter_idx}"
            return "" # No previous chapter or file not found

    class MockLogicValidator:
        # Correct indentation for methods
        def __init__(self, model):
            logger.info(f"[MockLogicValidator] Initialized with model {type(model)}.")
            self.model = model

        # Correct indentation for methods
        def check_logic(self, content, outline):
            logger.info(f"[MockLogicValidator] Checking logic for content starting with: {content[:50]}...")
            # Simulate check
            check_prompt = f"模拟逻辑检查提示 for content: {content[:50]}"
            report = self.model.generate(check_prompt)
            needs_revision = "需要修改" in report
            logger.info(f"[MockLogicValidator] Logic check report generated. Needs revision: {needs_revision}")
            return report, needs_revision
    # --- Mock 类定义结束 ---

    parser = argparse.ArgumentParser(description='生成小说章节内容（带验证）')
    parser.add_argument('--config', type=str, default='config.json', help='配置文件路径')
    parser.add_argument('--target-chapter', type=int, help='指定要重新生成的章节号')
    parser.add_argument('--start-chapter', type=int, help='指定开始生成的章节号 (注意: main.py 中处理)')
    parser.add_argument('--extra-prompt', type=str, help='额外提示词')

    args = parser.parse_args()

    # 加载配置
    try:
        config = Config(args.config)
    except NameError:
         print("错误：Config 类未定义（可能由于导入失败）。无法加载配置。")
         exit(1)
    except FileNotFoundError:
        print(f"错误：找不到配置文件 {args.config}")
        exit(1)
    except Exception as e:
        print(f"加载配置 '{args.config}' 时出错: {e}")
        exit(1)

    # 设置日志 (Main block uses basicConfig for simplicity in test)
    log_dir = "data/logs" # Default log dir
    if hasattr(config, 'log_config') and isinstance(config.log_config, dict) and "log_dir" in config.log_config:
         log_dir = config.log_config["log_dir"]
    else:
         logging.warning("log_config 或 log_dir 未在配置中找到，将使用默认目录 'data/logs'") # Basic config will handle this logger call

    os.makedirs(log_dir, exist_ok=True)
    # Use basicConfig for standalone test - note this configures the root logger
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s.%(funcName)s:%(lineno)d] - %(message)s',
                        handlers=[logging.FileHandler(os.path.join(log_dir, "content_gen_test.log"), encoding='utf-8', mode='w'),
                                  logging.StreamHandler()])
    
    # Get the named logger AFTER basicConfig is called
    logger = logging.getLogger(__name__) 
    
    logger.info(f"--- 开始独立测试 content_generator.py ---") # Now uses the configured logger
    logger.info(f"命令行参数: {args}") # Now uses the configured logger

    # 初始化 Mock 对象
    logger.info("使用 Mock 对象进行独立测试...") # Now uses the configured logger
    mock_content_model = MockModel()
    mock_knowledge_base = MockKB()

    # 创建 ContentGenerator 实例 (传入 Mock Model/KB)
    logger.info("创建 ContentGenerator 实例 (使用 Mock Model/KB)...") # Now uses the configured logger
    try:
        # Need to ensure the config object has 'output_config' attribute needed by ContentGenerator.__init__
        if not hasattr(config, 'output_config') or not isinstance(config.output_config, dict) or "output_dir" not in config.output_config:
             logger.error("配置文件缺少必要的 'output_config' 或 'output_dir'。") # Now uses the configured logger
             # Assign a default if possible for testing, or exit
             config.output_config = {"output_dir": "data/output_test"} # Example default
             logger.warning(f"使用默认 output_dir: {config.output_config['output_dir']}") # Now uses the configured logger
             os.makedirs(config.output_config['output_dir'], exist_ok=True)
             # exit(1) # Or exit if config is unusable

        generator = ContentGenerator(config, mock_content_model, mock_knowledge_base)
    except Exception as e:
        logger.error(f"创建 ContentGenerator 实例时出错: {e}", exc_info=True) # Now uses the configured logger
        exit(1)

    # 替换内部检查器为 Mock 版本
    logger.info("将生成器内部的检查器替换为 Mock 版本...") # Now uses the configured logger
    generator.consistency_checker = MockConsistencyChecker(mock_content_model, generator.output_dir)
    generator.logic_validator = MockLogicValidator(mock_content_model)

    # 检查大纲加载
    if not generator.chapter_outlines:
         logger.error("未能加载大纲，无法继续生成。请确保 outline.json 文件存在于 %s 且格式正确。", generator.output_dir) # Now uses the configured logger
    else:
        logger.info(f"成功加载 {len(generator.chapter_outlines)} 章大纲。") # Now uses the configured logger
        # 模拟设置起始章节
        if args.start_chapter and args.target_chapter is None:
             if 1 <= args.start_chapter <= len(generator.chapter_outlines) + 1:
                  generator.current_chapter = args.start_chapter - 1
                  logger.info(f"测试：模拟设置起始章节索引为 {generator.current_chapter}") # Now uses the configured logger
             else:
                  logger.error(f"测试：无效的起始章节 {args.start_chapter}，将使用加载的进度 {generator.current_chapter}") # Now uses the configured logger

        # 调用生成内容方法
        logger.info("调用 generator.generate_content...") # Now uses the configured logger
        try:
            success = generator.generate_content(
                target_chapter=args.target_chapter,
                external_prompt=args.extra_prompt
            )
        except Exception as e:
             logger.error(f"调用 generate_content 时发生错误: {e}", exc_info=True) # Now uses the configured logger
             success = False # Mark as failed

        # Standard print for final output
        print("\n内容生成流程结束。")
        print("结果：", "成功！" if success else "失败。")
        print(f'请查看日志文件 "{os.path.join(log_dir, "content_gen_test.log")}" 了解详细信息。')

    logger.info("--- 独立测试 content_generator.py 结束 ---") # Now uses the configured logger 