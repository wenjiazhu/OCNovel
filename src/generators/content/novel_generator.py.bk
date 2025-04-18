import asyncio
import os
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_fixed, RetryError, wait_exponential
import dataclasses
import math # 导入 math 模块用于 ceil
import re # 导入 re 模块用于清理文件名
from . import prompts # 导入新的 prompts 模块
from .content.consistency_checker import ConsistencyChecker # 导入一致性检查器
from .content.validators import LogicValidator, DuplicateValidator
from ..models import ContentModel, OutlineModel, EmbeddingModel
from ..knowledge_base.knowledge_base import KnowledgeBase
from ..config.config import Config
import time # 需要import time
# import asyncio # 需要导入 asyncio 来处理可能的 TimeoutError
import string # 导入 string 模块用于字符串处理
from opencc import OpenCC
from datetime import datetime

# 配置日志记录器
logger = logging.getLogger(__name__)

@dataclass
class ChapterOutline:
    """章节大纲数据结构"""
    chapter_number: int
    title: str
    key_points: List[str]
    characters: List[str]
    settings: List[str]
    conflicts: List[str]

@dataclass
class NovelOutline:
    """小说大纲数据结构"""
    title: str
    chapters: List[ChapterOutline]

@dataclass
class Character:
    """角色数据结构"""
    name: str
    role: str  # 主角、配角、反派等
    personality: Dict[str, float]  # 性格特征权重
    goals: List[str]
    relationships: Dict[str, str]
    development_stage: str  # 当前发展阶段
    alignment: str = "中立"  # 阵营：正派、反派、中立等，默认为中立
    realm: str = "凡人"      # 境界，例如：凡人、炼气、筑基、金丹等，默认为凡人
    level: int = 1          # 等级，默认为1
    cultivation_method: str = "无" # 功法，默认为无
    magic_treasure: List[str] = dataclasses.field(default_factory=list) # 法宝列表，默认为空列
    temperament: str = "平和"    # 性情，默认为平和
    ability: List[str] = dataclasses.field(default_factory=list)      # 能力列表，默认为空列
    stamina: int = 100        # 体力值，默认为100
    sect: str = "无门无派"      # 门派，默认为无门无派
    position: str = "普通弟子"    # 职务，默认为普通弟子
    emotions_history: List[str] = dataclasses.field(default_factory=list)  # 情绪历史记录
    states_history: List[str] = dataclasses.field(default_factory=list)    # 状态历史记录
    descriptions_history: List[str] = dataclasses.field(default_factory=list)  # 描述历史记录
class NovelGenerator:
    def __init__(self, config, outline_model, content_model, knowledge_base):
        self.config = config
        self.outline_model = outline_model
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        
        # 初始化重生成相关的属性
        self.target_chapter = None
        self.external_prompt = None
        
        # 验证模型配置
        self._validate_model_config()
        
        # 初始化一致性检查器
        self.consistency_checker = ConsistencyChecker(self.content_model, config.output_config["output_dir"])
        
        # 初始化验证器
        self.logic_validator = LogicValidator(self.content_model)
        self.duplicate_validator = DuplicateValidator(self.content_model)
        
        # 设置输出目录
        self.output_dir = config.output_config["output_dir"]
        print(f"Output directory: {self.output_dir}") # 添加这行代码
        
        # 设置角色库文件路径
        self.characters_file = os.path.join(self.output_dir, "characters.json")
        
        # --- 调整加载顺序 ---
        # 1. 初始化默认值
        self.characters = {} 
        self.chapter_outlines = []
        self.current_chapter = 0 # 默认为0 开始
        logging.debug("Initialized defaults before loading.")

        # 2. 加载大纲 (如果存在)
        self._load_outline_file()
        logging.info(f"Loaded {len(self.chapter_outlines)} outlines initially.")

        # 3. 加载角色库(如果存在)
        self._load_characters()
        logging.info(f"Loaded characters. Count: {len(self.characters)}")
        
        # 4. 加载进度 (如果存在，会覆盖 self.current_chapter 和 self.characters)
        self._load_progress() 
        logging.info(f"Progress loaded. Current chapter set to: {self.current_chapter}")
        logging.info(f"Characters after loading progress. Count: {len(self.characters)}")

        # 5. 设置日志 (可以在前面或后面)
        self._setup_logging()

    def _setup_logging(self):
        """设置日志"""
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        log_file = os.path.join(self.output_dir, "generation.log")
        print(f"日志文件路径: {log_file}") # 打印日志文件路径

        try:
            # 使用 FileHandler 并指定 UTF-8 编码
            handler = logging.FileHandler(log_file, encoding='utf-8')
            print("FileHandler 创建成功") # 确认 FileHandler 创建

            handler.setLevel(logging.INFO) # 设置 handler 的日志级别
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            logger = logging.getLogger() # 获取 root logger
            logger.addHandler(handler) # 添加 handler 到 root logger
            logger.setLevel(logging.INFO) # 设置 root logger 的日志级别

            print("日志 Handler 添加到 Logger") # 确认 Handler 添加成功
            logging.info("日志系统初始化完成") # 添加一条日志，确认日志系统工作

        except Exception as e:
            print(f"日志系统初始化失败: {e}") # 捕获并打印初始化异常
    
    def _load_progress(self):
        """加载生成进度"""
        progress_file = os.path.join(self.output_dir, "progress.json")
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        if os.path.exists(progress_file):
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)
                    self.current_chapter = progress.get("current_chapter", 0)
                    logging.info(f"从 progress.json 加载当前章节: {self.current_chapter}")
            except Exception as e:
                logging.error(f"加载 progress.json 文件时出错: {str(e)}")
                self.current_chapter = 0  # 出错时重置
            
            # 确保角色库已加载
            if not self.characters:
                self._load_characters()
        
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    # 处理可能的旧格式（包含元数据）和新格式（仅含章节列表）
                    chapters_list = outline_data.get("chapters", outline_data) if isinstance(outline_data, dict) else outline_data
                    if isinstance(chapters_list, list):
                        self.chapter_outlines = [
                            ChapterOutline(**chapter)
                            for chapter in chapters_list
                        ]
                    else:
                        logging.error("大纲文件格式无法识别，应为列表或包含'chapters'键的字典")
                        self.chapter_outlines = []
            except Exception as e:
                logging.error(f"加载大纲文件时出错: {str(e)}")
                self.chapter_outlines = []

    def _save_progress(self):
        """保存生成进度（仅章节号）"""
        progress_file = os.path.join(self.output_dir, "progress.json")
        
        # 保存进度 (只保存章节号)
        progress = {
            "current_chapter": self.current_chapter
        }
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
                logging.info(f"进度已保存，当前章节: {self.current_chapter}")
        except Exception as e:
            logging.error(f"保存 progress.json 时出错: {str(e)}")

    def _load_characters(self):
        """从文件加载角色库"""
        if os.path.exists(self.characters_file):
            try:
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                    # 尝试解析为 JSON
                    try:
                        characters_data = json.loads(raw_content)
                        if not isinstance(characters_data, dict):
                            logging.error(f"角色库文件 {self.characters_file} 包含无效数据 (不是字典): {type(characters_data)}")
                            return  # 保留空字典
                        
                        logging.info(f"从文件中加载到角色数量: {len(characters_data)}")
                        
                        # 尝试构建 Character 对象
                        temp_chars = {}
                        for name, data in characters_data.items():
                            try:
                                # 确保 personality 是字典
                                if isinstance(data.get("personality"), list):
                                    data["personality"] = {}  # 或者尝试转换，这里先置空
                                
                                # 创建角色对象
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
                                char = Character(**char_data)
                                temp_chars[name] = char
                            except TypeError as te:
                                logging.warning(f"创建角色 '{name}' 时数据字段不匹配或缺失 {te}. Data: {data}")
                            except Exception as char_e:
                                logging.error(f"创建角色 '{name}' 时发生未知错误 {char_e}. Data: {data}")
                        
                        self.characters = temp_chars
                    except json.JSONDecodeError as json_e:
                        logging.warning(f"加载角色库文件 {self.characters_file} 时JSON解析失败: {json_e}。文件可能不是标准JSON格式。将尝试保留空角色库。")
            except Exception as e:
                logging.error(f"读取角色库文件 {self.characters_file} 时出错: {str(e)}")
                self.characters = {}
        else:
            logging.info(f"角色库文件 {self.characters_file} 不存在，将创建新文件")
            self.characters = {}
            # 创建一个空的 characters.json 文件
            try:
                with open(self.characters_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
                logging.info(f"已创建空的 {self.characters_file}")
            except Exception as e:
                logging.error(f"创建空的 {self.characters_file} 时出错: {str(e)}")

    def _save_characters(self, new_state_text: Optional[str] = None):
        """
        保存角色库。
        如果提供了 new_state_text，则直接将其写入文件。
        否则，将内存中的 self.characters 对象序列化后写入。
        """
        logging.info(f"开始保存角色库到 {self.characters_file}")
        
        try:
            if new_state_text:
                # 验证并解析 JSON
                try:
                    json_data = json.loads(new_state_text)
                    if not isinstance(json_data, dict):
                        raise ValueError("角色数据必须是字典格式")
                    
                    # 保存到文件
                    with open(self.characters_file, 'w', encoding='utf-8') as f:
                        f.write(new_state_text)
                    logging.info("已保存 LLM 生成的新角色状态")
                    
                    # 更新内存中的对象
                    self.characters = {}
                    for name, data in json_data.items():
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
                        except Exception as char_e:
                            logging.error(f"更新角色 '{name}' 时出错: {str(char_e)}")
                except (json.JSONDecodeError, ValueError) as e:
                    logging.error(f"处理新的角色状态文本时出错: {str(e)}")
                    raise
            else:
                # 保存内存中的对象
                characters_data = {}
                for name, char in (self.characters or {}).items():
                    try:
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
                    except Exception as e:
                        logging.error(f"序列化角色 '{name}' 时出错: {str(e)}")
                
                with open(self.characters_file, 'w', encoding='utf-8') as f:
                    json.dump(characters_data, f, ensure_ascii=False, indent=2)
                logging.info(f"已将内存中的角色状态保存到 {self.characters_file}")
        except Exception as e:
            logging.error(f"保存角色库时发生错误: {str(e)}")
            raise  # 重新抛出异常，让调用者知道保存失败

    def _create_basic_character(self, name: str) -> Character:
        """创建基本角色信息"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        # 检查是否存在简体版本
        simplified_name = t2s.convert(name)
        if simplified_name != name and simplified_name in self.characters:
            # 如果存在简体版本，返回已存在的角色对象
            return self.characters[simplified_name]
        
        # 使用简体名称创建新角色
        return Character(
            name=simplified_name,
            role="配角",
            personality={"平和": 0.5},
            goals=["暂无明确目标"],
            relationships={},
            development_stage="初次登场"
        )

    def _is_valid_character_name(self, name: str) -> bool:
        """
        验证角色名是否有效
        """
        # 主要角色列表
        main_characters = ['陆沉', '噬元兽娘', '数据天魔', '机械天尊']
        if name in main_characters:
            return True
        
        # 基本长度检查
        if len(name) < 2 or len(name) > 4:
            return False
        
        # 检查是否包含无效字符
        invalid_chars = ['。', '，', '！', '？', '；', '：', '"', '"', ''', ''', '（', '）', 
                        '(', ')', '[', ']', '{', '}', '、', '|', '/', '\\', ' ', '\t', '\n']
        if any(char in name for char in invalid_chars):
            return False
        
        # 检查是否包含无效关键词
        invalid_keywords = ['一切', '这个', '那个', '他们', '我们', '你们', '自己', '对方',
                           '突然', '似乎', '知道', '看到', '听到', '感觉', '表面', '内心',
                           '猛然', '顿时', '仿佛', '好像', '也许', '可能', '应该', '必须',
                           '开始', '结束', '之前', '之后', '现在', '曾经', '以后', '地',
                           '的', '得', '着', '了', '过', '在', '和', '与', '或', '且']
        if any(keyword in name for keyword in invalid_keywords):
            return False
        
        # 检查是否包含重复字符
        if any(name.count(char) > 1 for char in name):
            return False
        
        # 检查是否以动词或形容词结尾
        invalid_endings = ['着', '了', '过', '的', '地', '得']
        if any(name.endswith(end) for end in invalid_endings):
            return False
        
        # 检查是否包含数字
        if any(char.isdigit() for char in name):
            return False
        
        return True

    def _parse_new_characters(self, content: str) -> List[Dict[str, Any]]:
        """
        从章节内容中解析新角色信息
        """
        new_characters = []
        
        # 对话标识词
        dialogue_markers = ['说道', '喊道', '回答', '问道', '叹道', '笑道', '怒道', '低声道']
        # 动作标识词
        action_markers = ['抬头', '低头', '转身', '走向', '看向', '伸手', '出手', '站在']
        # 状态标识词
        state_markers = ['眼神', '表情', '神色', '脸色', '语气', '姿态', '气息', '状态']
        
        # 提取对话中的角色
        for marker in dialogue_markers:
            pattern = f'([^，。！？；：""''（）\\s]{2,4}){marker}'
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1)
                if self._is_valid_character_name(name):
                    stage = self._determine_character_stage(name, content)
                    new_characters.append({
                        'name': name,
                        'stage': stage,
                        'first_appearance': False
                    })
        
        # 提取动作描述中的角色
        for marker in action_markers + state_markers:
            pattern = f'([^，。！？；：""''（）\\s]{2,4})(的)?{marker}'
            matches = re.finditer(pattern, content)
            for match in matches:
                name = match.group(1)
                if self._is_valid_character_name(name):
                    stage = self._determine_character_stage(name, content)
                    new_characters.append({
                        'name': name,
                        'stage': stage,
                        'first_appearance': False
                    })
        
        # 去重
        seen_names = set()
        unique_characters = []
        for char in new_characters:
            if char['name'] not in seen_names:
                seen_names.add(char['name'])
                unique_characters.append(char)
        
        return unique_characters

    def _determine_character_stage(self, name: str, content: str) -> str:
        """
        根据上下文确定角色发展阶段
        """
        # 战斗相关关键词
        battle_keywords = ['战斗', '厮杀', '对决', '交手', '激战', '搏杀', '出手', '攻击']
        # 突破相关关键词
        breakthrough_keywords = ['突破', '晋升', '提升', '进阶', '蜕变', '觉醒', '领悟']
        # 危机相关关键词
        crisis_keywords = ['危机', '危险', '生死', '绝境', '困境', '险境', '命悬一线']
        # 转折相关关键词
        turning_keywords = ['转折', '改变', '转变', '蜕变', '转机', '机遇', '契机']
        # 成长相关关键词
        growth_keywords = ['成长', '进步', '提升', '领悟', '感悟', '明悟', '顿悟']
        
        # 获取角色相关的上下文（前后100个字）
        name_index = content.find(name)
        if name_index == -1:
            return '剧情发展中'
        
        start = max(0, name_index - 100)
        end = min(len(content), name_index + 100)
        context = content[start:end]
        
        # 根据关键词确定阶段
        if any(keyword in context for keyword in crisis_keywords):
            return '危机阶段'
        elif any(keyword in context for keyword in breakthrough_keywords):
            return '突破阶段'
        elif any(keyword in context for keyword in battle_keywords):
            return '战斗阶段'
        elif any(keyword in context for keyword in turning_keywords):
            return '转折阶段'
        elif any(keyword in context for keyword in growth_keywords):
            return '成长阶段'
        else:
            return '剧情发展中'

    def _parse_character_update(self, update_text: str, chapter_num: int, current_chapter_characters: set = None):
        """解析角色更新信息"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        try:
            current_character = None
            in_format_block = False
            character_data = {}  # 临时存储当前角色的更新数据
            
            for line in update_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 跳过格式符号行
                if any(symbol in line for symbol in ["├──", "└──", "│"]):
                    continue
                
                # 检测角色名行（以冒号结尾）
                if (':' in line or '：' in line):
                    # 提取角色名部分
                    char_part = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    # 清理可能的格式符号和标记
                    char_name = char_part.replace('角色名', '').replace('：', '').replace(':', '').strip()
                    char_name = re.sub(r'[├──│└]', '', char_name).strip()
                    
                    # 转换为简体
                    char_name = t2s.convert(char_name)
                    
                    # 如果之前有未保存的角色数据，先保存
                    if current_character and character_data:
                        self._update_character_with_data(current_character, character_data)
                        character_data = {}
                    
                    # 检查是否是有效的角色名
                    if char_name and len(char_name) <= 4 and self._is_valid_character_name(char_name):
                        if char_name in self.characters:
                            current_character = char_name
                            logging.info(f"开始更新角色信息: {char_name}")
                        elif current_chapter_characters and char_name in current_chapter_characters:
                            # 如果是当前章节中的新角色，添加它
                            self.characters[char_name] = self._create_basic_character(char_name)
                            current_character = char_name
                            logging.info(f"添加并开始更新新角色: {char_name}")
                        else:
                            current_character = None
                    else:
                        current_character = None
                    continue
                
                # 如果有当前角色且该行包含属性更新信息
                if current_character and (':' in line or '：' in line):
                    key, value = line.split(':' if ':' in line else '：', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # 清理键名中的格式符号
                    key = re.sub(r'[├──│└]', '', key).strip()
                    
                    # 跳过无效的键
                    if key in ["物品", "能力", "状态", "主要角色间关系网", "触发或加深的事件"]:
                        continue
                    
                    # 将属性数据添加到临时存储
                    character_data[key] = value
            
            # 处理最后一个角色的数据
            if current_character and character_data:
                self._update_character_with_data(current_character, character_data)
        
        except Exception as e:
            logging.error(f"解析角色更新信息时出错: {str(e)}")
        
        # 保存更新后的角色库
        self._save_characters()

    def _update_character_with_data(self, character_name: str, data: dict):
        """使用收集的数据更新角色属性"""
        try:
            char = self.characters[character_name]
            
            # 映射关系，将可能的键名映射到标准键名
            key_mapping = {
                '发展阶段': 'development_stage',
                '当前状态': 'development_stage',
                '关系': 'relationships',
                '人物关系': 'relationships',
                '目标': 'goals',
                '当前目标': 'goals',
                '性格': 'personality',
                '性格特征': 'personality',
                '境界': 'realm',
                '修为境界': 'realm',
                '功法': 'cultivation_method',
                '修炼功法': 'cultivation_method',
                '法宝': 'magic_treasure',
                '法器': 'magic_treasure',
                '情绪': 'emotions_history',
                '当前情绪': 'emotions_history',
                '状态': 'states_history',
                '描述': 'descriptions_history'
            }
            
            for key, value in data.items():
                standard_key = key_mapping.get(key)
                if not standard_key:
                    continue
                    
                if standard_key == 'development_stage':
                    current_stages = set(char.development_stage.split(", "))
                    new_stages = set(value.split("，"))
                    all_stages = current_stages.union(new_stages)
                    char.development_stage = ", ".join(all_stages)
                    
                elif standard_key == 'relationships':
                    for relation in value.split('，'):
                        if ':' in relation or '：' in relation:
                            target, rel_type = relation.split(':' if ':' in relation else '：')
                            char.relationships[target.strip()] = rel_type.strip()
                            
                elif standard_key == 'goals':
                    new_goals = [g.strip() for g in value.split('，')]
                    for goal in new_goals:
                        if goal and goal not in char.goals:
                            char.goals.append(goal)
                            
                elif standard_key == 'personality':
                    traits = value.split('，')
                    for trait in traits:
                        if ':' in trait or '：' in trait:
                            t, weight = trait.split(':' if ':' in trait else '：')
                            try:
                                char.personality[t.strip()] = float(weight)
                            except ValueError:
                                char.personality[t.strip()] = 1.0
                        else:
                            char.personality[trait.strip()] = 1.0
                            
                elif standard_key in ['emotions_history', 'states_history', 'descriptions_history']:
                    current_list = getattr(char, standard_key)
                    new_items = [item.strip() for item in value.split('，')]
                    for item in new_items:
                        if item and item not in current_list:
                            current_list.append(item)
                            
                elif hasattr(char, standard_key):
                    if standard_key == 'magic_treasure':
                        new_items = [item.strip() for item in value.split('，')]
                        current_items = getattr(char, standard_key)
                        for item in new_items:
                            if item and item not in current_items:
                                current_items.append(item)
                    else:
                        setattr(char, standard_key, value)
                    
        except Exception as e:
            logging.error(f"更新角色 {character_name} 的属性时出错: {str(e)}")

    def _verify_character_consistency(self, content: str, current_chapter_characters: set = None) -> bool:
        """验证更新后的角色信息与章节内容的一致性"""
        try:
            for name, char in self.characters.items():
                # 只验证当前章节出现的角色
                if current_chapter_characters is not None and name not in current_chapter_characters:
                    continue
                    
                # 验证状态描述是否与章节内容一致
                if char.realm not in content and char.temperament not in content:
                    logging.warning(f"角色 {name} 的状态描述与章节内容不一致")
                    return False
                    
                # 验证能力描述是否与章节内容一致
                for ability in char.ability:
                    if ability not in content:
                        logging.warning(f"角色 {name} 的能力 {ability} 在章节中未体现")
                        return False
                        
                # 验证关系网络是否与章节内容一致
                for rel_name, rel_type in char.relationships.items():
                    if rel_name not in content or rel_type not in content:
                        logging.warning(f"角色 {name} 与 {rel_name} 的关系描述与章节内容不一致")
                        return False
                        
            return True
        except Exception as e:
            logging.error(f"验证角色一致性时发生错误: {str(e)}")
            return False

    def _correct_character_inconsistencies(self, content: str, current_chapter_characters: set = None):
        """修正角色信息与章节内容的不一致"""
        try:
            # 重新生成角色更新提示词，强调内容一致性
            prompt = prompts.get_character_update_prompt(
                content,
                self._format_characters_for_update(current_chapter_characters)
            )
            try:
                 characters_update = self.content_model.generate(prompt)
                 if self._validate_character_update(characters_update):
                     self._parse_character_update(characters_update, 0, current_chapter_characters) 
                 else:
                     logging.error("角色信息修正失败，保留原有信息")
            except Exception as e:
                 logging.error(f"修正角色信息时模型调用或解析出错: {str(e)}")
        except Exception as e:
            logging.error(f"修正角色信息时发生意外错误 {str(e)}")

    def _validate_character_update(self, update_text: str) -> bool:
        """验证角色更新内容的格式和完整性"""
        try:
            # 检查基本格式
            if not update_text or not isinstance(update_text, str):
                return False
                
            # 检查是否包含必要的字段
            required_fields = ["物品", "能力", "状态", "主要角色间关系网", "触发或加深的事件"]
            for field in required_fields:
                if field not in update_text:
                    logging.error(f"角色更新内容缺少必要字段: {field}")
                    return False
                    
            # 检查状态字段是否包含身体和心理两个维度
            if "身体状态" not in update_text or "心理状态" not in update_text:
                logging.error("角色状态缺少必要的维度信息")
                return False
                
            return True
        except Exception as e:
            logging.error(f"验证角色更新内容时发生错误: {str(e)}")
            return False

    def _update_summary(self, chapter_num: int, content: str):
        """生成并更新指定章节的摘要"""
        summary_file = os.path.join(self.output_dir, "summary.json")
        summaries = {}
        try:
            # 加载现有摘要
            if os.path.exists(summary_file):
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summaries = json.load(f)

            # 生成新摘要，使用 prompts 模块
            prompt = prompts.get_summary_prompt(content[:4000])
            new_summary = self.content_model.generate(prompt)
            
            # 清理摘要文本，移除可能的描述性文字
            new_summary = new_summary.strip()
            # 移除常见的描述性开头
            descriptive_starts = [
                "本章讲述", "本章主要讲述", "本章描述", "本章主要描述",
                "本章叙述", "本章主要叙述", "本章介绍", "本章主要介绍",
                "本章", "这一章", "这一章节", "这一章节主要",
                "本章？", "本章节主要？", "这一章节主要", "这一回主要？"
            ]
            
            for start in descriptive_starts:
                if new_summary.startswith(start):
                    new_summary = new_summary[len(start):].strip()
                    break
            
            summaries[str(chapter_num)] = new_summary

            # 保存更新后的摘要
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summaries, f, ensure_ascii=False, indent=2)
            logging.info(f"已更新第 {chapter_num} 章摘要")

        except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
            logging.error(f"更新第{chapter_num} 章摘要时请求超时: {str(e)}")
        except Exception as e:
            logging.error(f"更新第{chapter_num} 章摘要时出错: {str(e)}")

    def generate_novel(self):
        """生成小说内容"""
        try:
            # 如果指定了目标章节，验证章节号的有效性
            if self.target_chapter is not None:
                if self.target_chapter <= 0:
                    raise ValueError(f"无效的目标章节号: {self.target_chapter}")
                if not self.chapter_outlines or self.target_chapter > len(self.chapter_outlines):
                    raise ValueError(f"目标章节号 {self.target_chapter} 超出大纲范围")
                
                # 获取目标章节的大纲
                chapter_outline = self.chapter_outlines[self.target_chapter - 1]
                logging.info(f"开始重新生成第 {self.target_chapter} 章")
                
                # 生成章节内容
                content = self._generate_chapter_content(chapter_outline, self.external_prompt)
                
                # 保存章节内容
                self._save_chapter_content(self.target_chapter, content)
                
                # 更新角色状态
                self._update_character_states(content, self.target_chapter)
                
                logging.info(f"第 {self.target_chapter} 章重新生成完成")
                return
            
            # 如果没有指定目标章节，继续正常的生成流程
            while self.current_chapter < len(self.chapter_outlines):
                current_chapter_num = self.current_chapter + 1
                chapter_retries = 0
                chapter_generated = False
                
                while chapter_retries < max_retries and not chapter_generated:
                    try:
                        # 获取当前章节大纲
                        chapter_outline_obj = self.chapter_outlines[self.current_chapter]
                        logging.info(f"开始生成第 {current_chapter_num} 章: {chapter_outline_obj.title} (尝试 {chapter_retries + 1}/{max_retries})")
                        
                        # 构建提示词
                        prompt = self._get_context_for_chapter(current_chapter_num)
                        
                        # 生成章节内容
                        logging.info(f"正在调用内容模型生成第 {current_chapter_num} 章内容...")
                        content = self.content_model.generate(prompt)
                        
                        # 验证章节内容
                        if self._validate_chapter_content(content, chapter_outline_obj):
                            # 保存章节
                            self._save_chapter(current_chapter_num, content)
                            
                            # 更新进度
                            self.current_chapter += 1
                            self._save_progress()
                            chapter_generated = True  # 标记成功，跳出重试循环
                            break
                        else:
                            logging.error(f"第 {current_chapter_num} 章内容验证失败 (尝试 {chapter_retries + 1}/{max_retries})")
                            chapter_retries += 1
                            if chapter_retries >= max_retries:
                                logging.warning(f"第 {current_chapter_num} 章已达到最大重试次数，将使用最后生成的内容（可能不符合要求）。")
                                self._save_chapter(current_chapter_num, content, skip_character_update=True)  # 保存但不更新角色状态
                                logging.warning(f"第 {current_chapter_num} 章已强制保存（警告：内容可能不完全符合要求，且未更新角色状态）。")
                                self.current_chapter += 1  # 强制推进进度
                                self._save_progress()
                                chapter_generated = True  # 标记完成（虽然有警告）
                                break
                            # 重试前等待
                            wait_time = 15 * (chapter_retries + 1)  # 增加等待时间
                            logging.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                    
                    except (TimeoutError, asyncio.TimeoutError) as e:
                        logging.error(f"生成第 {current_chapter_num} 章时请求超时 (尝试 {chapter_retries + 1}/{max_retries}): {str(e)}")
                        chapter_retries += 1
                        if chapter_retries >= max_retries:
                            logging.error(f"第 {current_chapter_num} 章因超时达到最大重试次数，跳过此章节。")
                            # 不保存，不更新进度，让下一次运行时重试
                            break  # 跳出重试，但 chapter_generated 仍为 False
                        wait_time = 30 * (chapter_retries + 1)
                        logging.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    
                    except Exception as e:
                        logging.error(f"生成第 {current_chapter_num} 章时发生意外错误 (尝试 {chapter_retries + 1}/{max_retries}): {str(e)}", exc_info=True)
                        chapter_retries += 1
                        if chapter_retries >= max_retries:
                            logging.error(f"第 {current_chapter_num} 章因错误达到最大重试次数，跳过此章节。")
                            # 不保存，不更新进度
                            break  # 跳出重试，但 chapter_generated 仍为 False
                        wait_time = 20 * (chapter_retries + 1)
                        logging.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                
                # 如果因为重试失败而未生成章节，则停止整个过程
                if not chapter_generated:
                    logging.error(f"第 {current_chapter_num} 章生成失败，停止生成。")
                    break

        except Exception as e:
            logging.error(f"生成小说内容时发生错误: {str(e)}")

    def _validate_chapter_content(self, content: str, outline: ChapterOutline) -> bool:
        """验证章节内容是否符合要求"""
        try:
            # 基本检查
            if not content or not content.strip():
                logging.error("章节内容为空。")
                return False

            # 检查内容长度
            min_length = self.config.generation_config.get("min_chapter_length", 1000)
            if len(content) < min_length:
                logging.error(f"章节内容过短，少于 {min_length} 字符。")
                return False
                
            # 检查是否包含关键情节点（更灵活的检查）
            missing_points_count = 0
            for point in outline.key_points:
                # 提取关键词
                keywords = re.findall(r'[\u4e00-\u9fffA-Za-z0-9]+', point) # 提取中文、英文、数字
                keywords = [k for k in keywords if len(k) > 1 and k not in ['的', '地', '得', '了', '和', '与', '或', '而', '在', '是', '了']] # 过滤常见词

                if not keywords: continue # 如果情节点没有有效关键词，跳过

                matches = sum(1 for k in keywords if k in content)
                # 要求至少匹配一半或至少一个关键词（对于短情节点）
                required_matches = max(1, math.ceil(len(keywords) * 0.5))

                if matches < required_matches:
                    missing_points_count += 1
                    logging.warning(f"可能缺少关键情节点 '{point}' (匹配 {matches}/{len(keywords)} 关键词, 需要 {required_matches})")

            # 允许一定比例的情节点缺失
            allowed_missing_ratio = 0.5
            if len(outline.key_points) > 0 and (missing_points_count / len(outline.key_points)) > allowed_missing_ratio:
                 logging.error(f"缺失过多关键情节点 ({missing_points_count}/{len(outline.key_points)})")
                 # return False # 暂时注释掉，允许更多灵活性

            # 检查是否包含主要角色
            missing_chars_count = 0
            for character in outline.characters:
                if character not in content:
                    # 尝试检查变体
                    found_variant = False
                    if len(character) > 1:
                        # 检查姓氏或名字
                        if character[0] in content or character[1:] in content:
                             found_variant = True
                    if not found_variant:
                        missing_chars_count += 1
                        logging.warning(f"可能缺少主要角色: {character}")

            # 允许一定比例的角色缺失
            if len(outline.characters) > 0 and (missing_chars_count / len(outline.characters)) > allowed_missing_ratio:
                 logging.error(f"缺失过多主要角色 ({missing_chars_count}/{len(outline.characters)})")
                 # return False # 暂时注释掉

            # （可选）检查场景和冲突的关键词匹配，类似情节点检查
            # ...

            # （可选）调用其他验证器
            # if not self.logic_validator.validate(content): return False
            # if not self.duplicate_validator.validate(content): return False


            logging.info("章节内容基本验证通过。")
            return True
            
        except Exception as e:
            logging.error(f"验证章节内容时发生错误: {str(e)}")
            return False

    def generate_outline_chapters(self, novel_type: str, theme: str, style: str, mode: str = 'replace', replace_range: Tuple[int, int] = None, extra_prompt: str = None) -> bool:
        """生成指定范围的章节大纲"""
        try:
            if mode == 'replace' and replace_range:
                start_chapter, end_chapter = replace_range
                if start_chapter < 1 or end_chapter < start_chapter:
                    logging.error("无效的章节范围")
                    return False

                # 计算总共需要生成的章节数
                total_chapters = end_chapter - start_chapter + 1
                batch_size = 50  # 每批次生成50章
                successful_outlines = []  # 用于存储所有成功生成的大纲

                # 分批次生成大纲
                num_batches = (total_chapters + batch_size - 1) // batch_size
                
                for batch_idx in range(num_batches):
                    batch_start = start_chapter + (batch_idx * batch_size)
                    batch_end = min(batch_start + batch_size - 1, end_chapter)
                    current_batch_size = batch_end - batch_start + 1

                    logging.info(f"开始生成第 {batch_start} 到 {batch_end} 章的大纲（共 {current_batch_size} 章）")

                    # 获取当前批次的上下文
                    existing_context = self._get_context_for_chapter(batch_start, successful_outlines)
                    
                    # 生成大纲
                    prompt = prompts.get_outline_prompt(
                        novel_type=novel_type,
                        theme=theme,
                        style=style,
                        current_start_chapter_num=batch_start,
                        current_batch_size=current_batch_size,
                        existing_context=existing_context,
                        extra_prompt=extra_prompt
                    )
                    
                    # 当前批次的重试逻辑
                    max_retries = 3
                    batch_success = False
                    
                    for attempt in range(max_retries):
                        try:
                            # 调用模型生成大纲
                            outline_text = self.outline_model.generate(prompt)
                            if not outline_text:
                                logging.error(f"生成大纲失败：模型返回空内容（第 {attempt + 1} 次尝试）")
                                continue
                            
                            # 解析大纲文本
                            outline_data = json.loads(outline_text)
                            
                            # 验证大纲数据
                            if not isinstance(outline_data, list):
                                logging.error(f"生成的大纲格式不正确：不是数组（第 {attempt + 1} 次尝试）")
                                continue
                            
                            if len(outline_data) != current_batch_size:
                                logging.error(f"生成的章节数量不正确：期望 {current_batch_size}，实际 {len(outline_data)}（第 {attempt + 1} 次尝试）")
                                continue
                            
                            # 创建新的章节大纲对象
                            new_outlines = []
                            for i, chapter in enumerate(outline_data):
                                chapter_num = batch_start + i
                                new_outline = ChapterOutline(
                                    chapter_number=chapter_num,
                                    title=chapter.get('title', f'第{chapter_num}章'),
                                    key_points=chapter.get('key_points', []),
                                    characters=chapter.get('characters', []),
                                    settings=chapter.get('settings', []),
                                    conflicts=chapter.get('conflicts', [])
                                )
                                new_outlines.append(new_outline)
                            
                            # 替换指定范围的章节
                            self.chapter_outlines[batch_start-1:batch_end] = new_outlines
                            
                            # 保存当前批次的大纲
                            try:
                                self._save_outline()
                                # 只有在成功保存后才更新 successful_outlines
                                successful_outlines.extend(new_outlines)
                                batch_success = True
                                logging.info(f"成功生成并保存第 {batch_start} 到 {batch_end} 章的大纲")
                                break  # 成功生成和保存，跳出重试循环
                            except Exception as save_error:
                                logging.error(f"保存大纲时发生错误：{str(save_error)}")
                                continue
                                
                        except json.JSONDecodeError as e:
                            logging.error(f"解析大纲JSON时出错（第 {attempt + 1} 次尝试）：{str(e)}")
                        except Exception as e:
                            logging.error(f"处理大纲数据时出错（第 {attempt + 1} 次尝试）：{str(e)}")
                        
                        # 重试前等待
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 30
                            logging.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                    
                    # 如果当前批次处理失败，则终止整个生成过程
                    if not batch_success:
                        logging.error(f"在处理第 {batch_start} 到 {batch_end} 章的大纲时失败，终止生成过程")
                        return False
                    
                    # 每批次之间添加间隔，避免频繁请求
                    if batch_end < end_chapter:
                        wait_time = 60  # 每批次之间等待60秒
                        logging.info(f"本批次完成，等待 {wait_time} 秒后继续下一批次...")
                        time.sleep(wait_time)

                logging.info(f"所有批次的大纲生成完成，共生成 {len(successful_outlines)} 章")
                return True
            else:
                logging.error("不支持的生成模式或缺少必要参数")
                return False
                
        except Exception as e:
            logging.error(f"生成大纲时发生错误：{str(e)}")
            return False

    def _validate_model_config(self):
        """验证模型配置是否有效"""
        try:
            # 检查必要的模型是否存在
            if not self.outline_model:
                logging.error("大纲生成模型未初始化")
                return False
            
            if not self.content_model:
                logging.error("内容生成模型未初始化")
                return False
            
            if not self.knowledge_base:
                logging.error("知识库未初始化")
                return False
            
            # 检查配置是否完整
            if not self.config:
                logging.error("配置对象未初始化")
                return False
            
            # 检查输出目录配置
            if not self.config.output_config or "output_dir" not in self.config.output_config:
                logging.error("输出目录配置缺失")
                return False
            
            logging.info("模型配置验证通过")
            return True
            
        except Exception as e:
            logging.error(f"验证模型配置时出错: {str(e)}")
            return False

    def _load_outline_file(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    # 处理可能的旧格式（包含元数据）和新格式（仅含章节列表）
                    chapters_list = outline_data.get("chapters", outline_data) if isinstance(outline_data, dict) else outline_data
                    if isinstance(chapters_list, list):
                        self.chapter_outlines = [
                            ChapterOutline(**chapter)
                            for chapter in chapters_list
                        ]
                        logging.info(f"从文件加载了 {len(self.chapter_outlines)} 章大纲")
                    else:
                        logging.error("大纲文件格式无法识别，应为列表或包含'chapters'键的字典")
                        self.chapter_outlines = []
            except Exception as e:
                logging.error(f"加载大纲文件时出错: {str(e)}")
                self.chapter_outlines = []
        else:
            logging.warning(f"大纲文件不存在: {outline_file}")
            self.chapter_outlines = []

    def _save_outline(self):
        """保存大纲到文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        try:
            # 将大纲对象转换为可序列化的字典列表
            outline_data = []
            for outline in self.chapter_outlines:
                outline_dict = {
                    "chapter_number": outline.chapter_number,
                    "title": outline.title,
                    "key_points": outline.key_points,
                    "characters": outline.characters,
                    "settings": outline.settings,
                    "conflicts": outline.conflicts
                }
                outline_data.append(outline_dict)
            
            # 保存到文件
            with open(outline_file, 'w', encoding='utf-8') as f:
                json.dump(outline_data, f, ensure_ascii=False, indent=2)
            logging.info(f"大纲已保存到文件: {outline_file}")
        except Exception as e:
            logging.error(f"保存大纲文件时出错: {str(e)}")
            raise

    def _generate_chapter_content(self, chapter_outline, extra_prompt: Optional[str] = None):
        """生成章节内容"""
        max_retries = 3
        base_wait_time = 30  # 基础等待时间（秒）
        
        for attempt in range(max_retries):
            try:
                # 获取上下文信息
                context = self._get_context_for_chapter(chapter_outline.chapter_number)
                
                # 将 ChapterOutline 对象转换为字典
                outline_dict = {
                    "chapter_number": chapter_outline.chapter_number,
                    "title": chapter_outline.title,
                    "key_points": chapter_outline.key_points,
                    "characters": chapter_outline.characters,
                    "settings": chapter_outline.settings,
                    "conflicts": chapter_outline.conflicts
                }
                
                # 构建参考信息字典
                references = {
                    "plot_references": [],
                    "character_references": [],
                    "setting_references": []
                }
                
                # 从知识库获取参考内容
                if hasattr(self.knowledge_base, 'get_all_references'):
                    kb_refs = self.knowledge_base.get_all_references()
                    # 将知识库内容平均分配到三个类别中
                    refs = list(kb_refs.values())
                    total_refs = len(refs)
                    if total_refs > 0:
                        plot_end = total_refs // 3
                        char_end = (total_refs * 2) // 3
                        references["plot_references"] = refs[:plot_end]
                        references["character_references"] = refs[plot_end:char_end]
                        references["setting_references"] = refs[char_end:]
                
                # 构建提示词
                prompt = prompts.get_chapter_prompt(
                    outline=outline_dict,
                    references=references,
                    extra_prompt=extra_prompt or "",
                    context_info=context
                )
                
                # 生成内容
                logging.info(f"正在生成第 {chapter_outline.chapter_number} 章内容（尝试 {attempt + 1}/{max_retries}）...")
                content = self.content_model.generate(prompt)
                
                if not content or len(content.strip()) < 100:  # 内容太短，视为生成失败
                    raise ValueError("生成的内容过短或为空")
                
                # 验证内容
                if self._validate_chapter_content(content, chapter_outline):
                    logging.info(f"第 {chapter_outline.chapter_number} 章内容生成成功")
                    return content
                else:
                    logging.warning(f"第 {chapter_outline.chapter_number} 章内容验证未通过，将重试")
                    if attempt < max_retries - 1:
                        wait_time = base_wait_time * (attempt + 1)
                        logging.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    continue
                    
            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.error(f"生成内容超时 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = base_wait_time * (2 ** attempt)  # 指数退避
                    logging.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise
                    
            except Exception as e:
                logging.error(f"生成内容时出错 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    wait_time = base_wait_time * (attempt + 1)
                    logging.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                else:
                    raise
        
        raise Exception(f"生成第 {chapter_outline.chapter_number} 章内容失败，已达到最大重试次数")

    def _get_context_for_chapter(self, chapter_num: int, existing_outlines: Optional[List[ChapterOutline]] = None) -> str:
        """获取章节的上下文信息"""
        try:
            context_parts = []
            
            # 获取前一章的内容（如果存在）
            if chapter_num > 1:
                # 获取前一章的标题
                prev_chapter_outline = self.chapter_outlines[chapter_num - 2]
                prev_chapter_title = prev_chapter_outline.title
                prev_chapter_file = os.path.join(self.output_dir, f"第{chapter_num-1}章_{prev_chapter_title}.txt")
                
                if os.path.exists(prev_chapter_file):
                    try:
                        with open(prev_chapter_file, 'r', encoding='utf-8') as f:
                            prev_content = f.read()
                            # 只取最后一部分作为上下文
                            max_prev_content_length = 2000  # 限制前文长度
                            if len(prev_content) > max_prev_content_length:
                                prev_content = prev_content[-max_prev_content_length:]
                            context_parts.append(f"前一章内容：\n{prev_content}")
                    except Exception as e:
                        logging.warning(f"读取前一章内容时出错: {str(e)}")
            
            # 获取相关的知识库内容
            try:
                # 构建查询文本
                query_text = ""
                if existing_outlines and chapter_num <= len(existing_outlines):
                    outline = existing_outlines[chapter_num - 1]
                    query_text = f"{outline.title} {' '.join(outline.key_points)}"
                elif self.chapter_outlines and chapter_num <= len(self.chapter_outlines):
                    outline = self.chapter_outlines[chapter_num - 1]
                    query_text = f"{outline.title} {' '.join(outline.key_points)}"
                
                if query_text:
                    relevant_knowledge = self.knowledge_base.search(query_text)
                    if relevant_knowledge:
                        context_parts.append("相关参考内容：\n" + "\n".join(relevant_knowledge))
            except Exception as e:
                logging.warning(f"获取知识库内容时出错: {str(e)}")
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logging.error(f"获取章节上下文时出错: {str(e)}")
            return ""

    def _save_chapter_content(self, chapter_num: int, content: str):
        """保存章节内容到文件"""
        try:
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 获取章节标题
            chapter_outline = self.chapter_outlines[chapter_num - 1]
            chapter_title = chapter_outline.title
            
            # 构建文件名：第X章_标题.txt
            filename = f"第{chapter_num}章_{chapter_title}.txt"
            chapter_file = os.path.join(self.output_dir, filename)
            
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"已保存第 {chapter_num} 章内容: {filename}")
            
            # 更新摘要
            self._update_summary(chapter_num, content)
            
            # 更新角色状态
            self._update_character_states(content, chapter_num)
            
        except Exception as e:
            logging.error(f"保存章节内容时出错: {str(e)}")
            raise

    def _update_character_states(self, content: str, chapter_num: int):
        """更新角色状态"""
        try:
            # 获取当前章节的角色列表
            current_chapter_characters = set()
            if self.chapter_outlines and chapter_num <= len(self.chapter_outlines):
                current_chapter_characters.update(self.chapter_outlines[chapter_num - 1].characters)
            
            # 解析新出现的角色
            self._parse_new_characters(content)
            
            # 生成角色更新提示词
            prompt = prompts.get_character_update_prompt(
                content,
                self._format_characters_for_update(current_chapter_characters)
            )
            
            # 获取角色更新信息
            try:
                characters_update = self.content_model.generate(prompt)
                if self._validate_character_update(characters_update):
                    self._parse_character_update(characters_update, chapter_num, current_chapter_characters)
                else:
                    logging.error("角色更新信息验证失败")
            except Exception as e:
                logging.error(f"生成角色更新信息时出错: {str(e)}")
            
            # 验证更新后的角色信息
            if not self._verify_character_consistency(content, current_chapter_characters):
                logging.warning("角色信息与章节内容不一致，尝试修正")
                self._correct_character_inconsistencies(content, current_chapter_characters)
            
        except Exception as e:
            logging.error(f"更新角色状态时出错: {str(e)}")

    def _format_characters_for_update(self, current_chapter_characters: Optional[set] = None) -> str:
        """格式化角色信息用于更新"""
        try:
            formatted_chars = []
            for name, char in self.characters.items():
                # 如果指定了当前章节角色集合，只处理其中的角色
                if current_chapter_characters is not None and name not in current_chapter_characters:
                    continue
                
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
            
        except Exception as e:
            logging.error(f"格式化角色信息时出错: {str(e)}")
            return ""

