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
        self.characters_file = os.path.join(self.output_dir, "characters.json")
        self.characters: Dict[str, Character] = {}
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)
        # 加载角色库
        self._load_characters()

    def _load_characters(self):
        """从文件加载角色库"""
        characters_data = load_json_file(self.characters_file, default_value={})
        
        if characters_data:
            for name, data in characters_data.items():
                try:
                    char_data = {
                        "name": name,
                        "role": data.get("role", "未知"),
                        "personality": data.get("personality", {}),
                        "goals": data.get("goals", []),
                        "relationships": data.get("relationships", {}),
                        "development_stage": data.get("development_stage", "初始"),
                        "alignment": data.get("alignment", "中立"),
                        "realm": data.get("realm", "凡人"),
                        "level": data.get("level", 1),
                        "cultivation_method": data.get("cultivation_method", "无"),
                        "magic_treasure": data.get("magic_treasure", []),
                        "temperament": data.get("temperament", "平和"),
                        "ability": data.get("ability", []),
                        "stamina": data.get("stamina", 100),
                        "sect": data.get("sect", "无门无派"),
                        "position": data.get("position", "普通弟子"),
                        "emotions_history": data.get("emotions_history", []),
                        "states_history": data.get("states_history", []),
                        "descriptions_history": data.get("descriptions_history", [])
                    }
                    self.characters[name] = Character(**char_data)
                except Exception as e:
                    logging.error(f"创建角色 '{name}' 时出错: {str(e)}")

    def _save_characters(self):
        """保存角色库到文件"""
        try:
            characters_data = {}
            for name, char in self.characters.items():
                characters_data[name] = {
                    "role": char.role,
                    "personality": char.personality,
                    "goals": char.goals,
                    "relationships": char.relationships,
                    "development_stage": char.development_stage,
                    "alignment": char.alignment,
                    "realm": char.realm,
                    "level": char.level,
                    "cultivation_method": char.cultivation_method,
                    "magic_treasure": char.magic_treasure,
                    "temperament": char.temperament,
                    "ability": char.ability,
                    "stamina": char.stamina,
                    "sect": char.sect,
                    "position": char.position,
                    "emotions_history": char.emotions_history,
                    "states_history": char.states_history,
                    "descriptions_history": char.descriptions_history
                }
            
            if save_json_file(self.characters_file, characters_data):
                logging.info("角色库保存成功")
                return True
            return False
            
        except Exception as e:
            logging.error(f"保存角色库时出错: {str(e)}")
            return False

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
            if update_characters:
                if not self._update_character_states(content, chapter_num):
                    logging.error("更新角色状态失败")
                    return False
            
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

    def _update_character_states(self, content: str, chapter_num: int) -> bool:
        """更新角色状态"""
        try:
            # 解析新出现的角色
            self._parse_new_characters(content)
            
            # 获取当前章节的角色列表
            current_chapter_characters = self._get_current_chapter_characters(chapter_num)
            
            # 生成角色更新提示词
            prompt = self._create_character_update_prompt(content, current_chapter_characters)
            
            # 获取角色更新信息
            characters_update = self.content_model.generate(prompt)
            if not self._validate_character_update(characters_update):
                logging.error("角色更新信息验证失败")
                return False
            
            # 解析并应用更新
            self._parse_character_update(characters_update, chapter_num, current_chapter_characters)
            
            # 验证更新后的角色信息
            if not self._verify_character_consistency(content, current_chapter_characters):
                logging.warning("角色信息与章节内容不一致，尝试修正")
                self._correct_character_inconsistencies(content, current_chapter_characters)
            
            # 保存更新后的角色库
            return self._save_characters()
            
        except Exception as e:
            logging.error(f"更新角色状态时出错: {str(e)}")
            return False

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

    def _parse_new_characters(self, content: str):
        """解析新角色信息并添加到角色库"""
        t2s = OpenCC('t2s')  # 繁体转简体
        
        # 从内容中提取可能的角色名
        patterns = [
            r'([^，。？！；、\s]{2,4})(?:说道|道|喊道|叫道|回答道|问道|怒道|笑道|低声道)',
            r'([^，。？！；、\s]{2,4})(?:的声音)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1).strip()
                if name and self._is_valid_character_name(name):
                    # 转换为简体
                    simplified_name = t2s.convert(name)
                    if simplified_name not in self.characters:
                        self.characters[simplified_name] = self._create_basic_character(simplified_name)
                        logging.info(f"添加新角色: {simplified_name}")

    def _create_basic_character(self, name: str) -> Character:
        """创建基本角色信息"""
        return Character(
            name=name,
            role="配角",
            personality={"平和": 0.5},
            goals=["暂无明确目标"],
            relationships={},
            development_stage="初次登场"
        )

    def _is_valid_character_name(self, name: str) -> bool:
        """检查是否为有效的角色名"""
        # 常见角色名直接通过验证
        common_characters = ["陆沉"]
        if name in common_characters:
            return True
            
        # 如果名称过长，可能是描述性文字
        if len(name) > 12:
            return False
            
        # 如果包含特定关键词，可能是属性或描述
        invalid_keywords = [
            "物品", "能力", "状态", "关系", "事件", "技能", "装备",
            "道具", "功法", "法宝", "境界", "实力", "修为", "天赋"
        ]
        
        if any(keyword in name for keyword in invalid_keywords):
            return False
            
        # 如果包含标点符号或特殊字符，可能不是名称
        if any(char in name for char in string.punctuation):
            return False
            
        # 如果不包含中文字符，可能不是角色名
        if not any('\u4e00' <= c <= '\u9fff' for c in name):
            return False
            
        return True

    def _get_current_chapter_characters(self, chapter_num: int) -> Set[str]:
        """获取当前章节的角色列表"""
        current_characters = set()
        
        # 从大纲文件中获取角色列表
        outline_file = os.path.join(self.output_dir, "outline.json")
        outline_data = load_json_file(outline_file)
        
        if outline_data and isinstance(outline_data, list) and chapter_num <= len(outline_data):
            chapter_data = outline_data[chapter_num - 1]
            if isinstance(chapter_data, dict):
                current_characters.update(chapter_data.get("characters", []))
        
        return current_characters

    def _create_character_update_prompt(self, content: str, current_characters: Set[str]) -> str:
        """创建角色更新提示词"""
        prompt = f"""请分析以下内容中的角色状态变化：

{content[:2000]}  # 限制内容长度

当前出场角色：
{chr(10).join(current_characters)}

现有角色信息：
{self._format_characters_for_update(current_characters)}

请提供以下信息：
1. 角色状态变化（包括境界、功法、性格等）
2. 新增或改变的人物关系
3. 角色目标的变化
4. 重要事件对角色的影响

注意：
1. 只更新确实在内容中有变化的属性
2. 保持角色发展的合理性和连贯性
3. 确保更新与内容相符
"""
        return prompt

    def _format_characters_for_update(self, current_characters: Set[str]) -> str:
        """格式化角色信息用于更新"""
        formatted_chars = []
        for name in current_characters:
            if name in self.characters:
                char = self.characters[name]
                char_info = [
                    f"角色名：{name}",
                    f"身份：{char.role}",
                    f"境界：{char.realm}",
                    f"功法：{char.cultivation_method}",
                    f"状态：{char.development_stage}",
                    f"性格：{', '.join(f'{k}:{v}' for k, v in char.personality.items())}",
                    f"目标：{', '.join(char.goals)}",
                    f"关系：{', '.join(f'{k}:{v}' for k, v in char.relationships.items())}"
                ]
                formatted_chars.append("\n".join(char_info))
        
        return "\n\n".join(formatted_chars)

    def _validate_character_update(self, update_text: str) -> bool:
        """验证角色更新内容的格式和完整性"""
        if not update_text or not isinstance(update_text, str):
            return False
            
        required_fields = ["状态变化", "人物关系", "目标变化", "事件影响"]
        return all(field in update_text for field in required_fields)

    def _parse_character_update(self, update_text: str, chapter_num: int, current_characters: Set[str]):
        """解析角色更新信息"""
        try:
            current_character = None
            for line in update_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if ':' in line or '：' in line:
                    parts = line.split(':') if ':' in line else line.split('：')
                    key = parts[0].strip()
                    value = parts[1].strip() if len(parts) > 1 else ""
                    
                    if key in self.characters:
                        current_character = key
                        continue
                    
                    if current_character and current_character in current_characters:
                        self._update_character_attribute(current_character, key, value, chapter_num)
                        
        except Exception as e:
            logging.error(f"解析角色更新信息时出错: {str(e)}")

    def _update_character_attribute(self, character_name: str, key: str, value: str, chapter_num: int):
        """更新角色的特定属性"""
        if character_name not in self.characters:
            return
            
        char = self.characters[character_name]
        
        try:
            if key == '发展阶段':
                current_stages = set(char.development_stage.split(", "))
                new_stages = set(value.split(", "))
                all_stages = current_stages.union(new_stages)
                char.development_stage = ", ".join(all_stages)
                
            elif key == '关系':
                for relation in value.split('，'):
                    if ':' in relation or '：' in relation:
                        target, rel_type = relation.split(':') if ':' in relation else relation.split('：')
                        char.relationships[target.strip()] = rel_type.strip()
                        
            elif key == '目标':
                new_goals = [g.strip() for g in value.split('，')]
                for goal in new_goals:
                    if goal not in char.goals:
                        char.goals.append(goal)
                        
            elif key == '性格':
                traits = value.split('，')
                for trait in traits:
                    if ':' in trait or '：' in trait:
                        t, weight = trait.split(':') if ':' in trait else trait.split('：')
                        char.personality[t.strip()] = float(weight)
                    else:
                        char.personality[trait.strip()] = 1.0
                        
            elif hasattr(char, key):
                setattr(char, key, value)
                
        except Exception as e:
            logging.error(f"更新角色 {character_name} 的属性 {key} 时出错: {str(e)}")

    def _verify_character_consistency(self, content: str, current_characters: Set[str]) -> bool:
        """验证更新后的角色信息与章节内容的一致性"""
        for name in current_characters:
            if name not in self.characters:
                continue
                
            char = self.characters[name]
            
            # 验证状态描述
            if char.realm not in content and char.temperament not in content:
                logging.warning(f"角色 {name} 的状态描述与章节内容不一致")
                return False
            
            # 验证能力描述
            for ability in char.ability:
                if ability not in content:
                    logging.warning(f"角色 {name} 的能力 {ability} 在章节中未体现")
                    return False
            
            # 验证关系网络
            for rel_name, rel_type in char.relationships.items():
                if rel_name not in content or rel_type not in content:
                    logging.warning(f"角色 {name} 与 {rel_name} 的关系描述与章节内容不一致")
                    return False
        
        return True

    def _correct_character_inconsistencies(self, content: str, current_characters: Set[str]):
        """修正角色信息与章节内容的不一致"""
        try:
            # 重新生成角色更新提示词
            prompt = self._create_character_update_prompt(content, current_characters)
            characters_update = self.content_model.generate(prompt)
            
            if self._validate_character_update(characters_update):
                self._parse_character_update(characters_update, 0, current_characters)
            else:
                logging.error("角色信息修正失败，保留原有信息")
                
        except Exception as e:
            logging.error(f"修正角色信息时出错: {str(e)}")

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