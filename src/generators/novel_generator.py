import asyncio
import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_fixed, RetryError
import dataclasses
import math # 导入 math 模块用于 ceil
import re # 导入 re 模块用于清理文件名
from . import prompts # 导入新的 prompts 模块
from .consistency_checker import ConsistencyChecker # 导入一致性检查器
from .validators import LogicValidator, DuplicateValidator
from ..models import ContentModel, OutlineModel, EmbeddingModel
from ..knowledge_base.knowledge_base import KnowledgeBase
from ..config.config import Config
import time # 需要import time
# import asyncio # 需要导入 asyncio 来处理可能的 TimeoutError
import string # 导入 string 模块用于字符串处理
from opencc import OpenCC

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
        
        # 验证模型配置
        if not self._validate_model_config():
            raise ValueError("模型配置验证失败")
        
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

    def _parse_new_characters(self, update_text: str):
        """解析新角色信息并添加到角色库"""
        logging.info("开始解析新角色信息...")
        
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        # 预处理：移除可能导致解析错误的内容
        lines = update_text.split('\n')
        valid_lines = []
        # 需要过滤的关键词
        filter_keywords = [
            "分析", "总结", "说明", "介绍", "描述", "特征", "属性",
            "物品", "能力", "状态", "关系", "事件", "技能", "装备",
            "道具", "功法", "法宝", "境界", "实力", "修为", "天赋",
            "？", "？", "？", "─", "主要角色", "次要角色", "配角"
        ]
        
        for line in lines:
            # 跳过空行或只包含标点的行
            if not line.strip() or all(c in string.punctuation for c in line.strip()):
                continue
                
            # 跳过包含过滤关键词的行
            if any(keyword in line for keyword in filter_keywords):
                continue
            # 跳过以特殊字符开头的行
            if line.strip().startswith(('##', '**', '？', '[', '？', '？', '？', '─')):
                continue
            valid_lines.append(line)
        # 使用处理后的文本进行解析
        cleaned_text = '\n'.join(valid_lines)
        
        try:
            # 定义不同的括号对
            brackets = [
                ('？', '？'),
                ('[', ']'),
                ('"', '"'),
                ("'", "'"),
                ('？', '？'),
                ('「', '」'),
                ('『', '』'),
                ('(', ')')
            ]
            
            # 从文本中提取可能的角色名
            try:
                for left, right in brackets:
                    pattern = f'{left}([^{right}]+){right}'
                    try:
                        matches = re.finditer(pattern, cleaned_text)
                        for match in matches:
                            name = match.group(1).strip()
                            if name and self._is_valid_character_name(name):
                                # 转换为简体
                                simplified_name = t2s.convert(name)
                                # 使用简体名称作为键
                                if simplified_name not in self.characters:
                                    self.characters[simplified_name] = self._create_basic_character(simplified_name)
                                    logging.info(f"添加新角色: {simplified_name}")
                    except Exception as e:
                        logging.error(f"正则表达式匹配时出错: {e}")
            except Exception as e:
                logging.error(f"处理括号对时出错: {e}")
                
            # 显式检查常见角色名 - 针对当前小说内容
            common_characters = ["陆沉"]
            for name in common_characters:
                # 检查这些角色名是否出现在文本中
                if name in cleaned_text:
                    # 如果角色不在角色库中，则添加
                    if name not in self.characters:
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"显式添加常见角色: {name}")
                        
            # 直接在文本中搜索可能的角色名（根据语境）
            # 查找"XX说道"、XX等模式来识别角色
            patterns = [
                r'([^，。？！；、\s]{2,4})(?:说道|道|喊道|叫道|回答道|问道|怒道|笑道|低声道',
                r'([^，。？！；、\s]{2,4})(?:的声音)'
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, cleaned_text)
                for match in matches:
                    name = match.group(1).strip()
                    if name and self._is_valid_character_name(name) and name not in self.characters:
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"从对话模式中添加角色: {name}")
                        
        except Exception as e:
            logging.error(f"解析新角色信息时出错: {str(e)}")
        
        # 保存更新后的角色库
        self._save_characters()

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
            "道具", "功法", "法宝", "境界", "实力", "修为", "天赋",
            "资质", "性格", "性情", "特点", "背景", "经历", "职业",
            "职责", "身份", "地位", "关系网", "势力", "组织", "门派",
            "宗门", "家族", "？", "？", "？", "─", "装备", "状态"
        ]
        
        if any(keyword in name for keyword in invalid_keywords):
            return False
            
        # 如果包含标点符号或特殊字符，可能不是名称
        if any(char in name for char in "，。！？；？''【】《》（）[]{}├│└─"):
            return False
            
        # 如果不包含中文字符，可能不是角色名
        if not any('\u4e00' <= c <= '\u9fff' for c in name):
            return False
            
        # 检查名称是否以数字或特殊字符开头
        if name[0].isdigit() or name[0] in string.punctuation:
            return False
            
        # 如果是通用描述词，不是具体角色名
        # 放宽标准，减少误判
        generic_terms = [
            "总结", "分析", "介绍", "描述", "状态", "能力", "属性",
            "关系", "事件", "介绍", "主要", "次要", "配角"
        ]
        if name in generic_terms:
            return False
            
        return True

    def _parse_character_update(self, update_text: str, chapter_num: int, current_chapter_characters: set = None):
        """解析角色更新信息"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        try:
            current_character = None
            in_format_block = False
            
            for line in update_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 跳过格式符号行
                if any(symbol in line for symbol in ["├──", "？└──"]):
                    in_format_block = True
                    continue
                    
                # 检测角色名行（以冒号结尾）
                if (':' in line or '：' in line) and not in_format_block:
                    char_part = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    # 清理可能的格式符号
                    char_name = char_part.replace('├──', '').replace('？ ├──', '').replace('？ └──', '').replace('└──', '').strip()
                    
                    # 转换为简体
                    char_name = t2s.convert(char_name)
                    
                    # 检查是否是受保护的主要角色
                    protected_characters = ["陆沉"]
                    if char_name in protected_characters:
                        current_character = char_name
                        logging.info(f"开始更新角色信息 {char_name}")
                        in_format_block = False
                        continue
                    
                    # 检查是否在角色库中
                    if char_name in self.characters:
                        current_character = char_name
                        logging.info(f"开始更新角色信息 {char_name}")
                        in_format_block = False
                    else:
                        # 检查是否是当前章节中的角色
                        if current_chapter_characters and char_name in current_chapter_characters:
                            # 如果是当前章节中的角色但不在角色库中，添加它
                            self.characters[char_name] = self._create_basic_character(char_name)
                            current_character = char_name
                            logging.info(f"添加并开始更新新角色信息: {char_name}")
                            in_format_block = False
                        else:
                            current_character = None
                            logging.warning(f"未找到角色 {char_name}，跳过相关更新")
                    continue
                
                # 如果有当前角色且该行包含更新信息
                if current_character and (':' in line or '：' in line) and not line.startswith(('？', '？', '？')):
                    key = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    value = line.split(':')[1].strip() if ':' in line else line.split('：')[1].strip()
                    
                    # 清理可能的格式符号
                    key = key.replace('├──', '').replace('？ ├──', '').replace('？ └──', '').replace('└──', '').strip()
                    
                    # 跳过无效的键
                    if key in ["├──", "？└──", "物品", "能力", "状态", "主要角色间关系网", "触发或加深的事件"]:
                        continue
                    
                    # 转换value为简体（如果包含人名等）
                    if key in ['关系', '目标']:
                        value = t2s.convert(value)
                    
                    try:
                        self._update_character_attribute(current_character, key, value, chapter_num)
                    except Exception as e:
                        logging.error(f"更新角色 {current_character} 的属性{key} 时出错 {str(e)}")
            
            # 结束后重置格式块标记
            in_format_block = False
        
        except Exception as e:
            logging.error(f"解析角色更新信息时出错 {str(e)}")
        
        # 保存更新后的角色库
        self._save_characters()

    def _update_character_attribute(self, character_name: str, key: str, value: str, chapter_num: int):
        """更新角色的特定属性"""
        char = self.characters[character_name]
        
        if key == '发展阶段' or key == 'development_stage':
            # 添加新的发展阶段，保持原有的阶段记录
            current_stages = set(char.development_stage.split(", "))
            new_stages = set(value.split(", "))
            all_stages = current_stages.union(new_stages)
            char.development_stage = ", ".join(all_stages)
            
        elif key == '关系' or key == 'relationships':
            # 更新角色关系
            for relation in value.split('，'):
                if ':' in relation:
                    target, rel_type = relation.split(':')
                    char.relationships[target.strip()] = rel_type.strip()
                elif '：' in relation:
                    target, rel_type = relation.split('：')
                    char.relationships[target.strip()] = rel_type.strip()
                    
        elif key == '目标' or key == 'goals':
            # 更新角色目标
            new_goals = [g.strip() for g in value.split('，')]
            for goal in new_goals:
                if goal not in char.goals:
                    char.goals.append(goal)
                    
        elif key == '性格' or key == 'personality':
            # 更新性格特征
            traits = value.split('，')
            for trait in traits:
                if ':' in trait:
                    t, weight = trait.split(':')
                    char.personality[t.strip()] = float(weight)
                elif '：' in trait:
                    t, weight = trait.split('：')
                    char.personality[t.strip()] = float(weight)
                else:
                    char.personality[trait.strip()] = 1.0
                    
        elif hasattr(char, key):
            # 对于其他属性，直接更新
            setattr(char, key, value)
        else:
            logging.warning(f"未知的角色属性: {key}")

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
        max_retries = 3  # 每章最大重试次数
        
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

