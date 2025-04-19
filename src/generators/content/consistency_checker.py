"""
一致性检查模块 - 负责检查和修正章节内容的一致性

此模块提供了两个主要功能：
1. 检查章节内容的一致性，包括主题、情节、角色、世界观和逻辑等五个维度
2. 根据一致性检查报告修正章节内容
"""

import os
import json
import logging
import re
import dataclasses
from typing import Dict, Tuple, Any, List, Optional

# 导入提示词模块
from .. import prompts

class ConsistencyChecker:
    """小说章节内容一致性检查器类"""
    
    def __init__(self, content_model, output_dir: str):
        """
        初始化一致性检查器
        
        Args:
            content_model: 用于生成内容的模型
            output_dir: 输出目录路径
        """
        self.content_model = content_model
        self.output_dir = output_dir
        self.min_acceptable_score = 75  # 最低可接受分数
        self.max_revision_attempts = 3  # 最大修正尝试次数
    
    def check_chapter_consistency(
        self,
        chapter_content: str,
        chapter_outline: Dict[str, Any],
        chapter_idx: int,
        characters: Dict[str, Any] = None,
        previous_scene: str = ""
    ) -> Tuple[str, bool, int]:
        """
        检查章节内容一致性，并返回检查报告和是否需要修改
        
        Args:
            chapter_content: 待检查章节内容
            chapter_outline: 章节大纲
            chapter_idx: 章节索引
            characters: 角色信息字典 (如果需要，应由调用者处理并传入，这里暂时忽略)
            previous_scene: 前一章的场景信息 (由调用者传入)
            
        Returns:
            tuple: (检查报告, 是否需要修改, 评分)
        """
        logging.info(f"第 {chapter_idx + 1} 章: 开始一致性检查...")
        
        # 获取前文摘要
        global_summary = self._get_global_summary(chapter_idx)
        
        # 获取上一章摘要
        previous_summary = self._get_previous_summary(chapter_idx)
        
        # 角色信息获取已注释掉，使用空字符串
        character_info = ""
        
        # 生成一致性检查的提示词 - 使用传入的 previous_scene
        prompt = prompts.get_consistency_check_prompt(
            chapter_content=chapter_content,
            chapter_outline=chapter_outline,
            previous_summary=previous_summary,
            global_summary=global_summary,
            character_info=character_info,
            previous_scene=previous_scene # <--- 使用传入的参数
        )
        
        # 调用模型进行检查
        try:
            check_result = self.content_model.generate(prompt)
            
            # 解析检查结果
            needs_revision = "需要修改" in check_result
            
            # 提取分数
            score_match = re.search(r'\[总体评分\]\s*:\s*(\d+)', check_result)
            score = int(score_match.group(1)) if score_match else 0
            
            logging.info(f"第 {chapter_idx + 1} 章: 一致性检查完成，得分: {score}，{'需要修改' if needs_revision else '无需修改'}")
            
            return check_result, needs_revision, score
        
        except Exception as e:
            logging.error(f"第 {chapter_idx + 1} 章: 一致性检查出错: {str(e)}")
            return "一致性检查出错", True, 0
    
    def revise_chapter(
        self,
        chapter_content: str,
        consistency_report: str,
        chapter_outline: Dict[str, Any],
        chapter_idx: int
    ) -> str:
        """
        根据一致性检查报告修正章节内容
        
        Args:
            chapter_content: 原章节内容
            consistency_report: 一致性检查报告
            chapter_outline: 章节大纲
            chapter_idx: 章节索引
            
        Returns:
            str: 修正后的章节内容
        """
        logging.info(f"第 {chapter_idx + 1} 章: 开始根据一致性检查报告修正内容...")
        
        # 获取前文摘要
        global_summary = self._get_global_summary(chapter_idx)
        
        # 获取上一章摘要
        previous_summary = self._get_previous_summary(chapter_idx)
        
        # 生成修正提示词
        prompt = prompts.get_chapter_revision_prompt(
            original_content=chapter_content,
            consistency_report=consistency_report,
            chapter_outline=chapter_outline,
            previous_summary=previous_summary,
            global_summary=global_summary
        )
        
        # 调用模型进行修正
        try:
            revised_content = self.content_model.generate(prompt)
            logging.info(f"第 {chapter_idx + 1} 章: 内容修正完成")
            return revised_content
        except Exception as e:
            logging.error(f"第 {chapter_idx + 1} 章: 内容修正出错: {str(e)}")
            return chapter_content  # 修正失败时返回原内容
    
    def ensure_chapter_consistency(
        self,
        chapter_content: str,
        chapter_outline: Dict[str, Any],
        chapter_idx: int,
        characters: Dict[str, Any] = None,
        previous_scene: str = ""
    ) -> str:
        """
        确保章节内容的一致性，进行必要的检查和修正
        
        Args:
            chapter_content: 章节内容
            chapter_outline: 章节大纲
            chapter_idx: 章节索引
            characters: 角色信息字典 (暂时忽略)
            previous_scene: 前一章的场景信息 (传递给 check_chapter_consistency)
            
        Returns:
            str: 修正后的章节内容
        """
        # 进行一致性检查和修正的循环
        for attempt in range(self.max_revision_attempts):
            # 进行一致性检查 - 传递 previous_scene
            consistency_report, needs_revision, score = self.check_chapter_consistency(
                chapter_content, chapter_outline, chapter_idx, characters, previous_scene
            )
            
            # 如果分数达标或不需要修改，则跳出循环
            if score >= self.min_acceptable_score or not needs_revision:
                logging.info(f"第 {chapter_idx + 1} 章: 内容一致性检查通过，得分: {score}")
                break
                
            # 否则进行修正
            logging.info(f"第 {chapter_idx + 1} 章: 第 {attempt + 1} 次修正尝试，当前分数: {score}")
            chapter_content = self.revise_chapter(
                chapter_content, consistency_report, chapter_outline, chapter_idx
            )
            
            # 如果是最后一次尝试，再次检查但不再修改
            if attempt == self.max_revision_attempts - 1:
                final_report, _, final_score = self.check_chapter_consistency(
                    chapter_content, chapter_outline, chapter_idx, characters, previous_scene
                )
                logging.info(f"第 {chapter_idx + 1} 章: 完成所有修正尝试，最终分数: {final_score}")
        
        return chapter_content
    
    def _get_global_summary(self, chapter_idx: int) -> str:
        """获取全局摘要"""
        method_name = "_get_global_summary" # For logging clarity
        logging.debug(f"[{method_name}] Called for chapter_idx: {chapter_idx}")
        global_summary = ""
        summary_file = os.path.join(self.output_dir, "summary.json")
        logging.debug(f"[{method_name}] Summary file path: {summary_file}")
        # 检查摘要文件是否存在
        if os.path.exists(summary_file):
            logging.debug(f"[{method_name}] Summary file exists.")
            try:
                logging.debug(f"[{method_name}] Entering try block to read summary file.")
                # 打开并读取摘要文件
                with open(summary_file, 'r', encoding='utf-8') as f:
                    # 首先加载摘要文件内容到 summaries 字典
                    logging.debug(f"[{method_name}] Loading JSON from file...")
                    summaries = json.load(f)
                    logging.debug(f"[{method_name}] JSON loaded. Type: {type(summaries)}. Content (first 500 chars): {str(summaries)[:500]}")

                    # 确保 summaries 是字典
                    if not isinstance(summaries, dict):
                         logging.error(f"[{method_name}] Loaded summaries is not a dictionary! Type: {type(summaries)}")
                         return "" # 返回空字符串，避免后续错误

                    # 全局摘要可以考虑组合多个章节的摘要
                    if len(summaries) > 0:
                        logging.debug(f"[{method_name}] Processing summaries dictionary...")
                        # 使用列表推导式构建摘要列表
                        summary_parts = []
                        for k, v in summaries.items():
                            logging.debug(f"[{method_name}] Checking summary key: '{k}'")
                            try:
                                # 尝试将 key 转换为整数进行比较
                                if int(k) < chapter_idx:
                                    logging.debug(f"[{method_name}] Key '{k}' is valid and less than {chapter_idx}. Adding value.")
                                    summary_parts.append(v)
                                else:
                                     logging.debug(f"[{method_name}] Key '{k}' is not less than {chapter_idx}. Skipping.")
                            except ValueError:
                                # 如果 key 不能转换为整数，记录警告并跳过
                                logging.warning(f"[{method_name}] Summary key '{k}' is not a valid integer. Skipping.")
                        # 组合摘要并截取最后 2000 字符
                        global_summary = "\n".join(summary_parts)[-2000:]
                        logging.debug(f"[{method_name}] Combined global_summary (first 100 chars): '{global_summary[:100]}'")
                    else:
                        logging.debug(f"[{method_name}] Summaries dictionary is empty.")

            # 使用更具体的异常处理
            except json.JSONDecodeError as e:
                logging.error(f"[{method_name}] 解析摘要文件 {summary_file} 失败: {e}")
            except Exception as e:
                # Log the full traceback for unexpected errors
                logging.error(f"[{method_name}] 读取全局摘要时发生未知错误: {str(e)}", exc_info=True) # 添加 exc_info=True
        else:
            logging.warning(f"[{method_name}] Summary file does not exist: {summary_file}")

        # 返回获取到的全局摘要（可能为空字符串）
        logging.debug(f"[{method_name}] Returning global_summary (first 100 chars): '{global_summary[:100]}'")
        return global_summary
    
    def _get_previous_summary(self, chapter_idx: int) -> str:
        """获取上一章摘要"""
        method_name = "_get_previous_summary" # For logging clarity
        logging.debug(f"[{method_name}] Called for chapter_idx: {chapter_idx}")
        previous_summary = ""
        # 检查 chapter_idx 是否大于 0，确保有上一章
        if chapter_idx > 0:
            summary_file = os.path.join(self.output_dir, "summary.json")
            logging.debug(f"[{method_name}] Summary file path: {summary_file}")
            # 检查摘要文件是否存在
            if os.path.exists(summary_file):
                logging.debug(f"[{method_name}] Summary file exists.")
                try:
                    logging.debug(f"[{method_name}] Entering try block to read summary file.")
                    # 打开并读取摘要文件
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        # 首先加载摘要文件内容到 summaries 字典
                        logging.debug(f"[{method_name}] Loading JSON from file...")
                        summaries = json.load(f)
                        logging.debug(f"[{method_name}] JSON loaded. Type: {type(summaries)}. Content (first 500 chars): {str(summaries)[:500]}")

                        # 确保 summaries 是字典
                        if not isinstance(summaries, dict):
                             logging.error(f"[{method_name}] Loaded summaries is not a dictionary! Type: {type(summaries)}")
                             # 返回空字符串，避免后续错误
                             return ""

                        # 正确获取上一章的 key (章节索引从 0 开始，章节号从 1 开始)
                        prev_chapter_num_str = str(chapter_idx) # 上一章的章节号是 chapter_idx
                        logging.debug(f"[{method_name}] Previous chapter key to lookup: '{prev_chapter_num_str}'")

                        # 使用 .get() 安全访问，如果 key 不存在则返回空字符串
                        logging.debug(f"[{method_name}] Attempting to get summary for key '{prev_chapter_num_str}' using .get()")
                        previous_summary = summaries.get(prev_chapter_num_str, "")
                        logging.debug(f"[{method_name}] .get() returned. previous_summary is now (first 100 chars): '{previous_summary[:100]}'")

                        # 如果未找到摘要，记录警告
                        if not previous_summary:
                            logging.warning(f"[{method_name}] 未能找到第 {prev_chapter_num_str} 章的摘要。")

                # 使用更具体的异常处理
                except json.JSONDecodeError as e:
                    logging.error(f"[{method_name}] 解析摘要文件 {summary_file} 失败: {e}")
                except Exception as e:
                    # Log the full traceback for unexpected errors
                    logging.error(f"[{method_name}] 读取上一章摘要时发生未知错误: {str(e)}", exc_info=True) # 添加 exc_info=True
            else:
                logging.warning(f"[{method_name}] Summary file does not exist: {summary_file}")
        else:
            logging.debug(f"[{method_name}] chapter_idx is 0, no previous summary to get.")

        # 返回获取到的摘要（可能为空字符串）
        logging.debug(f"[{method_name}] Returning previous_summary (first 100 chars): '{previous_summary[:100]}'")
        return previous_summary
    
    # def _get_previous_scene(self, chapter_idx: int) -> str:
    #     ...
    
    # def _get_character_info(self, characters: Dict[str, Any], chapter_outline: Dict[str, Any]) -> str:
    #     ... 