import os
import logging
import re
import string
from typing import Optional, Set, Dict, List
from opencc import OpenCC
from ..common.data_structures import Character, ChapterOutline
from ..common.utils import load_json_file, save_json_file, clean_text, validate_directory

class NovelFinalizer:
    def __init__(self, config, content_model, knowledge_base):
        self.config = config
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.output_dir = config.output_config["output_dir"]
        # self.characters_file = os.path.join(self.output_dir, "characters.json")  # 注释掉角色库文件路径
        # self.characters: Dict[str, Character] = {}  # 注释掉角色库字典
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)
        # 加载角色库
        # self._load_characters()  # 注释掉角色库加载

    # def _load_characters(self):  # 注释掉角色库加载方法
    #     """从文件加载角色库"""
    #     characters_data = load_json_file(self.characters_file, default_value={})
    #     if characters_data:
    #         for name, data in characters_data.items():
    #             try:
    #                 char_data = {
    #                     "name": name,
    #                     "role": data.get("role", "未知"),
    #                     "personality": data.get("personality", {}),
    #                     "goals": data.get("goals", []),
    #                     "relationships": data.get("relationships", {}),
    #                     "development_stage": data.get("development_stage", "初始"),
    #                     "alignment": data.get("alignment", "中立"),
    #                     "realm": data.get("realm", "凡人"),
    #                     "level": data.get("level", 1),
    #                     "cultivation_method": data.get("cultivation_method", "无"),
    #                     "magic_treasure": data.get("magic_treasure", []),
    #                     "temperament": data.get("temperament", "平和"),
    #                     "ability": data.get("ability", []),
    #                     "stamina": data.get("stamina", 100),
    #                     "sect": data.get("sect", "无门无派"),
    #                     "position": data.get("position", "普通弟子"),
    #                     "emotions_history": data.get("emotions_history", []),
    #                     "states_history": data.get("states_history", []),
    #                     "descriptions_history": data.get("descriptions_history", [])
    #                 }
    #                 self.characters[name] = Character(**char_data)
    #             except Exception as e:
    #                 logging.error(f"创建角色 '{name}' 时出错: {str(e)}")

    # def _save_characters(self):  # 注释掉角色库保存方法
    #     """保存角色库到文件"""
    #     try:
    #         characters_data = {}
    #         for name, char in self.characters.items():
    #             characters_data[name] = {
    #                 "role": char.role,
    #                 "personality": char.personality,
    #                 "goals": char.goals,
    #                 "relationships": char.relationships,
    #                 "development_stage": char.development_stage,
    #                 "alignment": char.alignment,
    #                 "realm": char.realm,
    #                 "level": char.level,
    #                 "cultivation_method": char.cultivation_method,
    #                 "magic_treasure": char.magic_treasure,
    #                 "temperament": char.temperament,
    #                 "ability": char.ability,
    #                 "stamina": char.stamina,
    #                 "sect": char.sect,
    #                 "position": char.position,
    #                 "emotions_history": char.emotions_history,
    #                 "states_history": char.states_history,
    #                 "descriptions_history": char.descriptions_history
    #             }
    #         if save_json_file(self.characters_file, characters_data):
    #             logging.info("角色库保存成功")
    #             return True
    #         return False
    #     except Exception as e:
    #         logging.error(f"保存角色库时出错: {str(e)}")
    #         return False

    def finalize_chapter(self, chapter_num: int, update_characters: bool = True, update_summary: bool = True) -> bool:
        """处理章节的定稿工作
        
        Args:
            chapter_num: 要处理的章节号
            update_characters: 是否更新角色状态
            update_summary: 是否更新章节摘要
            
        Returns:
            bool: 处理是否成功
        """
        try:
            # 读取章节内容
            chapter_file = os.path.join(self.output_dir, f"chapter_{chapter_num}.txt")
            if not os.path.exists(chapter_file):
                logging.error(f"章节文件不存在: {chapter_file}")
                return False
                
            with open(chapter_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新角色状态
            # if update_characters:  # 注释掉角色状态更新
            #     if not self._update_character_states(content, chapter_num):
            #         logging.error("更新角色状态失败")
            #         return False
            
            # 生成/更新摘要
            if update_summary:
                if not self._update_summary(chapter_num, content):
                    logging.error("更新摘要失败")
                    return False
            
            logging.info(f"第 {chapter_num} 章定稿完成")
            return True
            
        except Exception as e:
            logging.error(f"处理章节定稿时出错: {str(e)}")
            return False

    # 注释掉所有与角色库相关的方法
    # def _update_character_states(self, content: str, chapter_num: int) -> bool:
    # def _parse_new_characters(self, content: str):
    # def _create_basic_character(self, name: str) -> Character:
    # def _is_valid_character_name(self, name: str) -> bool:
    # def _get_current_chapter_characters(self, chapter_num: int) -> Set[str]:
    # def _create_character_update_prompt(self, content: str, current_characters: Set[str]) -> str:
    # def _format_characters_for_update(self, current_characters: Set[str]) -> str:
    # def _validate_character_update(self, update_text: str) -> bool:
    # def _parse_character_update(self, update_text: str, chapter_num: int, current_characters: Set[str]):
    # def _update_character_attribute(self, character_name: str, key: str, value: str, chapter_num: int):
    # def _verify_character_consistency(self, content: str, current_characters: Set[str]) -> bool:
    # def _correct_character_inconsistencies(self, content: str, current_characters: Set[str]):

    def _update_summary(self, chapter_num: int, content: str) -> bool:
        """生成并更新章节摘要"""
        try:
            summary_file = os.path.join(self.output_dir, "summary.json")
            summaries = load_json_file(summary_file, default_value={})
            
            # 生成新摘要
            prompt = self._create_summary_prompt(content[:4000])  # 限制内容长度
            new_summary = self.content_model.generate(prompt)
            
            # 清理摘要文本
            new_summary = self._clean_summary(new_summary)
            
            # 更新摘要
            summaries[str(chapter_num)] = new_summary
            
            # 保存更新后的摘要
            if save_json_file(summary_file, summaries):
                logging.info(f"已更新第 {chapter_num} 章摘要")
                return True
            return False
            
        except Exception as e:
            logging.error(f"更新摘要时出错: {str(e)}")
            return False

    def _create_summary_prompt(self, content: str) -> str:
        """创建摘要生成的提示词"""
        return f"""请为以下内容生成简洁的章节摘要，包含以下要素：
1. 主要情节发展
2. 重要人物行动
3. 关键事件结果
4. 重要信息揭示

内容：
{content}

要求：
1. 摘要长度控制在300字以内
2. 突出重点，避免细节
3. 保持客观性
4. 使用第三人称叙述
"""

    def _clean_summary(self, summary: str) -> str:
        """清理摘要文本"""
        # 移除常见的描述性开头
        descriptive_starts = [
            "本章讲述", "本章主要讲述", "本章描述", "本章主要描述",
            "本章叙述", "本章主要叙述", "本章介绍", "本章主要介绍",
            "本章", "这一章", "这一章节", "这一章节主要"
        ]
        
        summary = summary.strip()
        for start in descriptive_starts:
            if summary.startswith(start):
                summary = summary[len(start):].strip()
                break
        
        return summary

if __name__ == "__main__":
    import argparse
    from ..config.config import Config
    from ..models import ContentModel, KnowledgeBase
    
    parser = argparse.ArgumentParser(description='处理小说章节的定稿工作')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    parser.add_argument('--chapter', type=int, required=True, help='要处理的章节号')
    
    args = parser.parse_args()
    
    # 加载配置
    config = Config(args.config)
    
    # 初始化模型和知识库
    content_model = ContentModel()
    knowledge_base = KnowledgeBase()
    
    # 创建定稿器
    finalizer = NovelFinalizer(config, content_model, knowledge_base)
    
    # 处理定稿
    success = finalizer.finalize_chapter(args.chapter)
    
    if success:
        print("章节定稿处理成功！")
    else:
        print("章节定稿处理失败，请查看日志文件了解详细信息。") 