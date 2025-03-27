"""
验证器模块 - 负责处理小说内容的各类验证

此模块提供了以下验证功能：
1. 逻辑严密性验证
2. 重复文字验证
"""

import logging
from typing import Dict, List, Tuple
import re
from . import prompts

class LogicValidator:
    """逻辑严密性验证器"""
    
    def __init__(self, content_model):
        self.content_model = content_model
    
    def check_logic(self, chapter_content: str, chapter_outline: Dict) -> Tuple[str, bool]:
        """
        检查章节内容的逻辑严密性
        
        Args:
            chapter_content: 章节内容
            chapter_outline: 章节大纲
            
        Returns:
            tuple: (验证报告, 是否需要修改)
        """
        prompt = prompts.get_logic_check_prompt(
            chapter_content=chapter_content,
            chapter_outline=chapter_outline
        )
        
        try:
            check_result = self.content_model.generate(prompt)
            needs_revision = "需要修改" in check_result
            return check_result, needs_revision
        except Exception as e:
            logging.error(f"逻辑验证失败: {str(e)}")
            return "逻辑验证出错", True

class DuplicateValidator:
    """重复文字验证器"""
    
    def __init__(self, content_model):
        self.content_model = content_model
        self.min_duplicate_length = 50  # 最小重复文字长度
        self.max_duplicate_ratio = 0.3  # 最大允许重复比例
    
    def check_duplicates(
        self,
        chapter_content: str,
        prev_content: str = "",
        next_content: str = ""
    ) -> Tuple[str, bool]:
        """
        检查章节内容的重复文字
        
        Args:
            chapter_content: 当前章节内容
            prev_content: 上一章内容
            next_content: 下一章内容
            
        Returns:
            tuple: (验证报告, 是否需要修改)
        """
        # 1. 检查章节内部重复
        internal_duplicates = self._find_internal_duplicates(chapter_content)
        
        # 2. 检查与前后章节的重复
        cross_chapter_duplicates = self._find_cross_chapter_duplicates(
            chapter_content, prev_content, next_content
        )
        
        # 3. 生成验证报告
        report = self._generate_report(internal_duplicates, cross_chapter_duplicates)
        
        # 4. 判断是否需要修改
        needs_revision = (
            len(internal_duplicates) > 0 or
            len(cross_chapter_duplicates) > 0
        )
        
        return report, needs_revision
    
    def _find_internal_duplicates(self, content: str) -> List[Tuple[str, int, int]]:
        """查找章节内部的重复文字"""
        duplicates = []
        content_length = len(content)
        
        # 使用滑动窗口查找重复片段
        for length in range(self.min_duplicate_length, content_length // 2):
            for start in range(content_length - length * 2):
                pattern = content[start:start + length]
                # 在当前片段之后查找相同内容
                next_start = start + length
                while True:
                    next_start = content.find(pattern, next_start)
                    if next_start == -1:
                        break
                    duplicates.append((pattern, start, next_start))
                    next_start += 1
        
        return duplicates
    
    def _find_cross_chapter_duplicates(
        self,
        current_content: str,
        prev_content: str,
        next_content: str
    ) -> List[Tuple[str, str, int, int]]:
        """查找与前后章节的重复文字"""
        duplicates = []
        
        # 检查与上一章的重复
        if prev_content:
            for length in range(self.min_duplicate_length, len(current_content) // 2):
                for start in range(len(current_content) - length):
                    pattern = current_content[start:start + length]
                    if pattern in prev_content:
                        duplicates.append(("prev", pattern, start, prev_content.find(pattern)))
        
        # 检查与下一章的重复
        if next_content:
            for length in range(self.min_duplicate_length, len(current_content) // 2):
                for start in range(len(current_content) - length):
                    pattern = current_content[start:start + length]
                    if pattern in next_content:
                        duplicates.append(("next", pattern, start, next_content.find(pattern)))
        
        return duplicates
    
    def _generate_report(
        self,
        internal_duplicates: List[Tuple[str, int, int]],
        cross_chapter_duplicates: List[Tuple[str, str, int, int]]
    ) -> str:
        """生成验证报告"""
        report = "重复文字验证报告\n\n"
        
        # 内部重复报告
        if internal_duplicates:
            report += "1. 章节内部重复：\n"
            for pattern, start1, start2 in internal_duplicates:
                report += f"- 重复内容：{pattern}\n"
                report += f"  位置：{start1} 和 {start2}\n"
        else:
            report += "1. 章节内部重复：未发现\n"
        
        # 跨章节重复报告
        if cross_chapter_duplicates:
            report += "\n2. 跨章节重复：\n"
            for chapter, pattern, start1, start2 in cross_chapter_duplicates:
                chapter_name = "上一章" if chapter == "prev" else "下一章"
                report += f"- 与{chapter_name}重复：{pattern}\n"
                report += f"  位置：当前章节 {start1}，{chapter_name} {start2}\n"
        else:
            report += "\n2. 跨章节重复：未发现\n"
        
        # 统计信息
        total_duplicates = len(internal_duplicates) + len(cross_chapter_duplicates)
        report += f"\n总计发现 {total_duplicates} 处重复\n"
        
        return report 