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
import time # 需要 import time
import asyncio # 需要导入 asyncio 来处理可能的 TimeoutError
import string # 导入 string 模块用于字符串处理
from opencc import OpenCC

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
    level: int = 1          # 等级，默认为1级
    cultivation_method: str = "无" # 功法，默认为无
    magic_treasure: List[str] = dataclasses.field(default_factory=list) # 法宝列表，默认为空列表
    temperament: str = "平和"    # 性情，默认为平和
    ability: List[str] = dataclasses.field(default_factory=list)      # 能力列表，默认为空列表
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
        self.current_chapter = 0 # 默认从 0 开始
        logging.debug("Initialized defaults before loading.")

        # 2. 加载大纲 (如果存在)
        self._load_outline_file()
        logging.info(f"Loaded {len(self.chapter_outlines)} outlines initially.")

        # 3. 加载角色库 (如果存在)
        loaded_chars = self._load_characters() 
        if isinstance(loaded_chars, dict):
             self.characters = loaded_chars
             logging.info(f"Successfully loaded characters. Count: {len(self.characters)}")
        else:
             logging.warning("_load_characters did not return a valid dictionary. Keeping characters empty.")
        
        # 4. 加载进度 (如果存在，会覆盖 self.current_chapter 和 self.characters)
        self._load_progress() 
        logging.info(f"Progress loaded. Current chapter set to: {self.current_chapter}")
        logging.info(f"Characters after loading progress. Count: {len(self.characters)}")

        # 5. 设置日志 (可以在前面或后面)
        self._setup_logging()

        # 加载角色库后进行清理
        if self.characters:
            self.clean_character_library()

    def _setup_logging(self):
        """设置日志"""
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        
        log_file = os.path.join(self.output_dir, "generation.log")
        print(f"日志文件路径: {log_file}") # 打印日志文件路径

        try:
            # 使用 FileHandler 并指定 UTF-8 编码
            handler = logging.FileHandler(log_file, encoding='utf-8')
            print("FileHandler 创建成功。") # 确认 FileHandler 创建

            handler.setLevel(logging.INFO) # 设置 handler 的日志级别
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            logger = logging.getLogger() # 获取 root logger
            logger.addHandler(handler) # 将 handler 添加到 root logger
            logger.setLevel(logging.INFO) # 设置 root logger 的日志级别

            print("日志 Handler 添加到 Logger。") # 确认 Handler 添加成功
            logging.info("日志系统初始化完成。") # 添加一条日志，确认日志系统工作

        except Exception as e:
            print(f"日志系统初始化失败: {e}") # 捕获并打印初始化异常
    
    def _load_progress(self):
        """加载生成进度"""
        progress_file = os.path.join(self.output_dir, "progress.json")
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)
                self.current_chapter = progress.get("current_chapter", 0)
                self.characters = {
                    name: Character(**data)
                    for name, data in progress.get("characters", {}).items()
                }
                # 从角色库文件加载角色信息，如果进度文件中没有，则从角色库加载
                if not self.characters:
                    self._load_characters()
                    
                    # 如果角色库仍为空但已有生成的章节，尝试从已有章节中提取角色信息
                    if not self.characters and self.current_chapter > 0:
                        logging.info(f"检测到续写模式，角色库为空，但已有{self.current_chapter}章内容，尝试从已生成章节中提取角色信息...")
                        self._extract_characters_from_existing_chapters()
                
            if os.path.exists(outline_file):
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    self.chapter_outlines = [
                        ChapterOutline(**chapter)
                        for chapter in outline_data
                    ]
    
    def _extract_characters_from_existing_chapters(self):
        """从已生成的章节中提取角色信息"""
        logging.info("开始从已生成章节中提取角色信息...")
        
        try:
            # 查找已生成的章节文件
            chapter_files = []
            for filename in os.listdir(self.output_dir):
                if filename.startswith("第") and filename.endswith(".txt"):
                    chapter_files.append(os.path.join(self.output_dir, filename))
            
            chapter_files.sort()  # 按文件名排序
            
            # 从最近的3章中提取角色信息（避免处理太多内容）
            recent_chapters = chapter_files[-3:] if len(chapter_files) > 3 else chapter_files
            
            if not recent_chapters:
                logging.warning("未找到已生成的章节文件，无法提取角色信息")
                return
            
            # 合并最近章节的内容
            combined_content = ""
            for chapter_file in recent_chapters:
                try:
                    with open(chapter_file, 'r', encoding='utf-8') as f:
                        chapter_content = f.read()
                        combined_content += chapter_content + "\n\n"
                        logging.info(f"已读取章节文件: {chapter_file}")
                except Exception as e:
                    logging.error(f"读取章节文件 {chapter_file} 时出错: {str(e)}")
            
            if not combined_content:
                logging.warning("未能读取任何章节内容，无法提取角色信息")
                return
            
            # 使用角色导入提示词提取角色信息
            logging.info("使用AI从章节内容中提取角色信息...")
            prompt = prompts.get_character_import_prompt(combined_content)
            try:
                 characters_info = self.content_model.generate(prompt)
                 self._parse_character_update(characters_info, self.current_chapter)
                 self._save_characters()
                 logging.info(f"从已生成章节成功提取了 {len(self.characters)} 个角色信息")
            except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
                 logging.error(f"从已生成章节提取角色信息时请求超时: {str(e)}")
            except Exception as e:
                 logging.error(f"解析或保存提取的角色信息时出错: {str(e)}")

        except Exception as e:
            logging.error(f"从已生成章节提取角色信息时发生错误: {str(e)}", exc_info=True)

    def _save_progress(self):
        """保存生成进度"""
        progress_file = os.path.join(self.output_dir, "progress.json")
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        # 保存进度
        progress = {
            "current_chapter": self.current_chapter,
            "characters": {
                name: {
                    "name": char.name,
                    "role": char.role,
                    "personality": char.personality,
                    "goals": char.goals,
                    "relationships": char.relationships,
                    "development_stage": char.development_stage
                }
                # 使用 (self.characters or {}) 确保即使 self.characters 是 None 也不会出错
                for name, char in (self.characters or {}).items()
            }
        }
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
            
        self._save_characters() # 保存角色库
            
        # 保存大纲
        outline_data = [
            {
                "chapter_number": outline.chapter_number,
                "title": outline.title,
                "key_points": outline.key_points,
                "characters": outline.characters,
                "settings": outline.settings,
                "conflicts": outline.conflicts
            }
            for outline in self.chapter_outlines
        ]
        with open(outline_file, 'w', encoding='utf-8') as f:
            json.dump(outline_data, f, ensure_ascii=False, indent=2)
    
    def _load_characters(self):
        """加载角色库, 返回字典或 None"""
        logging.info("开始加载角色库...")
        characters_dict = {}
        if os.path.exists(self.characters_file):
            try:
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    characters_data = json.load(f)
                    # 检查加载的数据是否为字典
                    if not isinstance(characters_data, dict):
                        logging.error(f"角色库文件 {self.characters_file} 包含无效数据 (不是字典): {type(characters_data)}")
                        return None # 返回 None 表示加载失败

                    logging.info(f"从文件中加载到角色数据 (前 500 字符): {str(characters_data)[:500]}") # 记录加载内容（部分）
                    
                    # 尝试构建 Character 对象
                    temp_chars = {}
                    for name, data in characters_data.items():
                        try:
                            char = Character(**data)
                            # 补充旧数据兼容性处理
                            if not hasattr(char, 'sect'): char.sect = "无门无派"
                            if not hasattr(char, 'position'): char.position = "普通弟子"
                            temp_chars[name] = char
                        except TypeError as te:
                            logging.warning(f"创建角色 '{name}' 时数据字段不匹配或缺失: {te}. Data: {data}")
                        except Exception as char_e:
                            logging.error(f"创建角色 '{name}' 时发生未知错误: {char_e}. Data: {data}")
                    
                    characters_dict = temp_chars # 赋值给局部变量
                    
                    # 加载后立即清理
                    self.characters = characters_dict
                    self.clean_character_library()
                    characters_dict = self.characters

            except json.JSONDecodeError as e:
                logging.error(f"加载角色库文件 {self.characters_file} 时 JSON 解析失败: {e}")
                return None # 返回 None 表示加载失败
            except Exception as e:
                logging.error(f"加载角色库文件 {self.characters_file} 时发生未知错误: {e}", exc_info=True)
                return None # 返回 None 表示加载失败
        else:
            # 初始化一些基础角色
            characters_dict = {
                "陆沉": Character(
                    name="陆沉",
                    role="主角",
                    personality={"坚韧": 0.8, "机智": 0.7},
                    goals=["对抗伪天庭", "收集道纹"],
                    relationships={"机械天尊": "盟友"},
                    development_stage="成长初期"
                )
            }
            logging.info("角色库文件不存在，已初始化基础角色。")
        return characters_dict

    def _save_characters(self):
        """保存角色库"""
        logging.info("开始保存角色库...") # 添加日志：开始保存角色库
        logging.info(f"当前角色库数据: {self.characters}") # 添加日志：打印当前角色库数据
        print(f"正在保存角色库到文件: {self.characters_file}") # 打印文件路径，**新增日志**
        characters_data = {
            name: {
                "name": char.name,
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
                "position": char.position
            }
            # 使用 (self.characters or {}) 确保即使 self.characters 是 None 也不会出错
            for name, char in (self.characters or {}).items()
        }
        logging.debug(f"即将保存的角色库 JSON 数据: {characters_data}") # 打印 JSON 数据 **新增日志**
        with open(self.characters_file, 'w', encoding='utf-8') as f:
            json.dump(characters_data, f, ensure_ascii=False, indent=2)
        logging.info("角色库保存完成。") # 添加日志：角色库保存完成 
        
        # 运行清理脚本
        try:
            import subprocess
            logging.info("开始运行角色库清理脚本...")
            subprocess.run(['python', 'scripts/clean_characters.py'], check=True)
            logging.info("角色库清理脚本运行完成。")
            
            # 重新加载清理后的角色库
            cleaned_file = os.path.join(self.output_dir, "characters_cleaned.json")
            if os.path.exists(cleaned_file):
                with open(cleaned_file, 'r', encoding='utf-8') as f:
                    cleaned_data = json.load(f)
                    self.characters = {
                        name: Character(**data)
                        for name, data in cleaned_data.items()
                    }
                logging.info("已加载清理后的角色库。")
                
                # 将清理后的文件复制回原始文件
                import shutil
                shutil.copy2(cleaned_file, self.characters_file)
                logging.info("已更新原始角色库文件。")
        except Exception as e:
            logging.error(f"运行角色库清理脚本时出错: {str(e)}")

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
            "├", "│", "└", "─", "主要角色", "次要角色", "配角"
        ]
        
        for line in lines:
            # 跳过空行或只包含标点的行
            if not line.strip() or all(c in string.punctuation for c in line.strip()):
                continue
                
            # 跳过包含过滤关键词的行
            if any(keyword in line for keyword in filter_keywords):
                continue
                
            # 跳过以特殊字符开头的行
            if line.strip().startswith(('##', '**', '第', '[', '├', '│', '└', '─')):
                continue
                
            valid_lines.append(line)
        
        # 使用处理后的文本进行解析
        cleaned_text = '\n'.join(valid_lines)
        
        try:
            # 定义不同的括号对
            brackets = [
                ('【', '】'),
                ('[', ']'),
                ('"', '"'),
                (''', '''),
                ('「', '」'),
                ('『', '』'),
                ('（', '）'),
                ('(', ')')
            ]
            
            # 从文本中提取可能的角色名
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
                except re.error:
                    continue
                    
            # 显式检查常见角色名 - 针对当前小说内容
            common_characters = ["王大锤", "丹辰子", "钱小小", "拾荒道人"]
            for name in common_characters:
                # 检查这些角色名是否出现在文本中
                if name in cleaned_text:
                    # 如果角色不在角色库中，则添加
                    if name not in self.characters:
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"显式添加常见角色: {name}")
                        
            # 直接在文本中搜索可能的角色名（根据语境）
            # 查找"XX说道"、"XX道"等模式来识别角色
            patterns = [
                r'([^，。？！；、\s]{2,4})(?:说道|道|喊道|叫道|回答道|问道|怒道|笑道|低声道)',
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
        """检查是否为有效的角色名称"""
        # 常见角色名直接通过验证
        common_characters = ["陆沉"]
        if name in common_characters:
            return True
            
        # 如果名称过长，可能是描述性文本
        if len(name) > 12:
            return False
            
        # 如果包含特定关键词，可能是属性或描述
        invalid_keywords = [
            "物品", "能力", "状态", "关系", "事件", "技能", "装备",
            "道具", "功法", "法宝", "境界", "实力", "修为", "天赋",
            "资质", "性格", "性情", "特点", "背景", "经历", "职业",
            "职责", "身份", "地位", "关系网", "势力", "组织", "门派",
            "宗门", "家族", "├", "│", "└", "─", "装备", "状态"
        ]
        
        if any(keyword in name for keyword in invalid_keywords):
            return False
            
        # 如果包含标点符号或特殊字符，可能不是名称
        if any(char in name for char in "，。！？；：""''【】《》（）()[]{}├│└─"):
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
                if any(symbol in line for symbol in ["├──", "│", "└──"]):
                    in_format_block = True
                    continue
                    
                # 检测角色名行（以冒号结尾）
                if (':' in line or '：' in line) and not in_format_block:
                    char_part = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    # 清理可能的格式符号
                    char_name = char_part.replace('├──', '').replace('│  ├──', '').replace('│  └──', '').replace('└──', '').strip()
                    
                    # 转换为简体
                    char_name = t2s.convert(char_name)
                    
                    # 检查是否是受保护的主要角色
                    protected_characters = ["陆沉"]
                    if char_name in protected_characters:
                        current_character = char_name
                        logging.info(f"开始更新角色信息: {char_name}")
                        in_format_block = False
                        continue
                    
                    # 检查是否在角色库中
                    if char_name in self.characters:
                        current_character = char_name
                        logging.info(f"开始更新角色信息: {char_name}")
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
                            logging.warning(f"未找到角色: {char_name}，跳过相关更新")
                    continue
                
                # 如果有当前角色且该行包含更新信息
                if current_character and (':' in line or '：' in line) and not line.startswith(('├', '│', '└')):
                    key = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    value = line.split(':')[1].strip() if ':' in line else line.split('：')[1].strip()
                    
                    # 清理可能的格式符号
                    key = key.replace('├──', '').replace('│  ├──', '').replace('│  └──', '').replace('└──', '').strip()
                    
                    # 跳过无效的键
                    if key in ["├──", "│", "└──", "物品", "能力", "状态", "主要角色间关系网", "触发或加深的事件"]:
                        continue
                    
                    # 转换value为简体（如果包含人名）
                    if key in ['关系', '目标']:
                        value = t2s.convert(value)
                    
                    try:
                        self._update_character_attribute(current_character, key, value, chapter_num)
                    except Exception as e:
                        logging.error(f"更新角色 {current_character} 的属性 {key} 时出错: {str(e)}")
            
            # 结束后重置格式块标记
            in_format_block = False
        
        except Exception as e:
            logging.error(f"解析角色更新信息时出错: {str(e)}")
        
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
            except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
                 logging.error(f"修正角色信息时请求超时: {str(e)}，跳过修正。")
            except Exception as e:
                 logging.error(f"修正角色信息时模型调用或解析出错: {str(e)}")
        except Exception as e:
            logging.error(f"修正角色信息时发生意外错误: {str(e)}")

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
            if "身体状态:" not in update_text or "心理状态:" not in update_text:
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
                "本章讲述了", "本章主要讲述了", "本章描述了", "本章主要描述了",
                "本章叙述了", "本章主要叙述了", "本章介绍了", "本章主要介绍了",
                "本章", "这一章", "这一章节", "这一回", "这一章节主要",
                "本章节", "本章节主要", "这一章节主要", "这一回主要"
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
            logging.error(f"更新第 {chapter_num} 章摘要时请求超时: {str(e)}")
        except Exception as e:
            logging.error(f"更新第 {chapter_num} 章摘要时出错: {str(e)}")
    
    def _save_chapter(self, chapter_num: int, content: str, skip_character_update: bool = False):
        """保存章节文件，并可选择更新摘要和角色信息"""
        try:
            # 从大纲中获取章节标题 (注意 chapter_num 是从1开始的，列表索引需要减1)
            chapter_idx = chapter_num - 1
            if chapter_idx < 0 or chapter_idx >= len(self.chapter_outlines):
                logging.error(f"尝试保存章节 {chapter_num} 时发生错误：无效的章节索引 {chapter_idx}")
                # 使用默认标题或抛出错误
                title = f"未知标题_{chapter_num}"
            else:
                title = self.chapter_outlines[chapter_idx].title

            # 清理标题以创建安全的文件名
            # 移除或替换可能导致问题的字符：/ \ : * ? " < > | 以及控制字符
            safe_title = re.sub(r'[\\/*?:"<>|\x00-\x1f]', '', title)
            safe_title = safe_title.replace(" ", "_") # 可选：用下划线替换空格
            if not safe_title: # 如果清理后标题为空，使用默认名称
                safe_title = f"章节_{chapter_num}"

            # 构建文件名和路径
            filename = f"第{chapter_num}章_{safe_title}.txt"
            filepath = os.path.join(self.output_dir, filename)

            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"章节 {chapter_num} 已成功保存到: {filepath}")

            # --- 更新摘要 ---
            if not skip_character_update: # 复用这个标志，表示是否需要更新摘要
                self._update_summary(chapter_num, content)
            
            # --- 更新角色信息 ---
            if not skip_character_update:
                self._update_characters_from_content(chapter_num, content)

        except Exception as e:
            logging.error(f"保存章节 {chapter_num} 时发生错误: {str(e)}")
            # 可以选择在这里重新抛出异常，或者仅记录错误
            # raise

    def _update_characters_from_content(self, chapter_num: int, content: str):
        """分析章节内容并更新角色信息"""
        logging.info(f"开始从第 {chapter_num} 章内容更新角色信息...")
        
        try:
            # 首先清理内容，移除可能的分析性文字
            content_lines = content.split('\n')
            story_content = []
            for line in content_lines:
                # 跳过分析性文字
                if any(keyword in line for keyword in [
                    "角色属性分析",
                    "人物分析",
                    "总结如下",
                    "分析结果",
                    "**"
                ]):
                    continue
                story_content.append(line)
            
            # 使用清理后的内容
            cleaned_content = '\n'.join(story_content)
            
            # 从章节内容中提取出现的角色名称
            current_chapter_characters = set()
            # 遍历现有角色名称，检查是否在章节内容中出现
            for name in self.characters.keys():
                if name in cleaned_content:
                    current_chapter_characters.add(name)
            
            # 检查是否需要从内容中发现新角色
            prompt = prompts.get_character_import_prompt(cleaned_content)
            try:
                new_characters_update = self.content_model.generate(prompt)
                self._parse_new_characters(new_characters_update)
                # 更新后立即清理
                self.clean_character_library()
            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.error(f"第 {chapter_num} 章: 发现新角色请求超时: {str(e)}，跳过新角色发现。")
            except Exception as e:
                logging.error(f"第 {chapter_num} 章: 发现新角色时出错: {str(e)}")

            # 再次检查新发现的角色是否在内容中出现
            for name in list(self.characters.keys()):
                if name in cleaned_content and name not in current_chapter_characters:
                    current_chapter_characters.add(name)
            
            # 手动检查常见角色名
            common_characters = ["王大锤", "丹辰子", "钱小小", "拾荒道人"]
            for name in common_characters:
                if name in cleaned_content:
                    # 如果角色不在角色库中，添加它
                    if name not in self.characters:
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"手动添加常见角色: {name}")
                    
                    # 确保将这个角色添加到当前章节的角色列表中
                    current_chapter_characters.add(name)
            
            if not current_chapter_characters:
                logging.warning(f"第 {chapter_num} 章未发现任何角色，跳过角色更新")
                return
                
            # 只获取当前章节出现的角色的状态文本
            existing_characters_text = self._format_characters_for_update(current_chapter_characters)
            
            # 使用角色更新提示词
            prompt = prompts.get_character_update_prompt(cleaned_content, existing_characters_text)
            try:
                characters_update = self.content_model.generate(prompt)
                if not self._validate_character_update(characters_update):
                    logging.error("角色更新内容格式验证失败，保留原有角色信息")
                    return
                self._parse_character_update(characters_update, chapter_num, current_chapter_characters)
                # 更新后立即清理
                self.clean_character_library()
                
                # 验证一致性...
                if not self._verify_character_consistency(cleaned_content, current_chapter_characters):
                     logging.warning("角色信息与章节内容存在不一致，尝试进行修正...")
                     self._correct_character_inconsistencies(cleaned_content, current_chapter_characters)
                
                logging.info(f"第 {chapter_num} 章角色信息更新完成...")
                
                # 确保常见角色信息得到保留
                for name in common_characters:
                    if name in cleaned_content and name not in self.characters:
                        # 如果清理过程中删除了这些角色，重新添加它们
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"清理后恢复常见角色: {name}")
                
                # 在进行完所有更新后再次保存角色库
                self._save_characters()

            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.error(f"第 {chapter_num} 章: 角色更新请求超时: {str(e)}，跳过本次更新。")
            except Exception as e:
                 logging.error(f"第 {chapter_num} 章: 更新角色信息时出错（模型调用或解析阶段）: {str(e)}")

        except Exception as e:
            logging.error(f"更新角色信息时发生意外错误: {str(e)}", exc_info=True)

    def _format_characters_for_update(self, character_names: set = None) -> str:
        """格式化现有角色信息用于更新"""
        formatted_text = ""
        for name, char in self.characters.items():
            # 如果提供了角色名集合，只格式化这些角色的信息
            if character_names is not None and name not in character_names:
                continue
                
            formatted_text += f"{name}：\n"
            formatted_text += f"├──物品: {', '.join(char.magic_treasure)}\n"
            formatted_text += f"├──能力: {', '.join(char.ability)}\n"
            formatted_text += f"├──状态\n"
            formatted_text += f"│  ├──身体状态: {char.realm}, {char.temperament}\n"
            formatted_text += f"│  └──心理状态: {char.development_stage}\n"
            formatted_text += f"├──主要角色间关系网\n"
            for rel_name, rel_type in char.relationships.items():
                formatted_text += f"│  └──{rel_name}: {rel_type}\n"
            formatted_text += f"└──触发或加深的事件: {', '.join(char.goals)}\n\n"
        return formatted_text

    def _merge_duplicate_characters(self):
        """合并重复的角色（包括繁简体变体）"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        # 用于存储需要合并的角色
        to_merge = {}  # 格式: {简体名: [异体名1, 异体名2, ...]}
        
        # 第一步：找出所有需要合并的角色
        character_names = list(self.characters.keys())
        for name in character_names:
            # 转换为简体
            simplified_name = t2s.convert(name)
            if simplified_name != name:  # 如果是繁体字
                if simplified_name in self.characters:  # 如果简体版本已存在
                    if simplified_name not in to_merge:
                        to_merge[simplified_name] = []
                    to_merge[simplified_name].append(name)
        
        # 第二步：合并角色信息
        for simplified_name, variant_names in to_merge.items():
            for variant_name in variant_names:
                if variant_name in self.characters:
                    # 合并角色发展阶段
                    main_stages = set(self.characters[simplified_name].development_stage.split(", "))
                    variant_stages = set(self.characters[variant_name].development_stage.split(", "))
                    combined_stages = main_stages.union(variant_stages)
                    self.characters[simplified_name].development_stage = ", ".join(combined_stages)
                    
                    # 合并关系
                    self.characters[simplified_name].relationships.update(
                        self.characters[variant_name].relationships
                    )
                    
                    # 合并目标
                    self.characters[simplified_name].goals.extend(
                        [g for g in self.characters[variant_name].goals 
                         if g not in self.characters[simplified_name].goals]
                    )
                    
                    # 合并能力
                    self.characters[simplified_name].ability.extend(
                        [a for a in self.characters[variant_name].ability 
                         if a not in self.characters[simplified_name].ability]
                    )
                    
                    # 合并法宝
                    self.characters[simplified_name].magic_treasure.extend(
                        [t for t in self.characters[variant_name].magic_treasure 
                         if t not in self.characters[simplified_name].magic_treasure]
                    )
                    
                    # 删除繁体变体
                    del self.characters[variant_name]
                    logging.info(f"合并角色 '{variant_name}' 到 '{simplified_name}'")

    def clean_character_library(self):
        """清理角色库中的非角色条目"""
        # 首先合并重复角色
        self._merge_duplicate_characters()
        
        # 需要删除的条目的关键词列表
        non_character_keywords = [
            # 分析相关词
            "收到文本后",
            "分析步骤",
            "通读文本",
            "角色识别",
            "属性提取",
            "格式化输出",
            "检查与校对",
            "好的",
            "请看",
            "总结",
            "分析结果",
            "整理如下",
            "步骤",
            "如下",
            "发现以下",
            "新角色",
            "分析",
            "说明",
            "介绍",
            "描述",
            "特征",
            "属性",
            "文本",
            "内容",
            "情节",
            "故事",
            "场景",
            # 属性相关词
            "物品",
            "能力",
            "状态",
            "关系",
            "事件",
            "技能",
            "装备",
            "道具",
            "功法",
            "法宝",
            "境界",
            "实力",
            "修为",
            "天赋",
            "资质",
            "性格",
            "性情",
            "特点",
            "背景",
            "经历",
            "职业",
            "职责",
            "身份",
            "地位",
            "关系网",
            "势力",
            "组织",
            "门派",
            "宗门",
            "家族",
            # 目录结构相关
            "├",
            "│",
            "└",
            "─",
            "主要角色",
            "次要角色",
            "配角",
            "反派",
            "路人"
        ]
        
        # 保护列表 - 这些角色不会被删除
        protected_characters = ["陆沉"]
        
        # 记录要删除的角色名
        to_delete = []
        for name in self.characters.keys():
            # 如果在保护列表中，跳过检查
            if name in protected_characters:
                continue
                
            # 检查是否包含非角色关键词
            if any(keyword in name for keyword in non_character_keywords):
                to_delete.append(name)
                continue
                
            # 检查是否以数字、特殊字符或目录符号开头
            if name[0].isdigit() or name.startswith(('##', '**', '第', '[', '├', '│', '└', '─')):
                to_delete.append(name)
                continue
                
            # 检查名称长度是否过长（正常人名一般不会超过8个汉字）
            if len(name) > 12:
                to_delete.append(name)
                continue
                
            # 检查是否为描述性文本而不是名字
            if len(name.split()) > 2:  # 如果包含多个词，可能是描述性文本
                to_delete.append(name)
                continue
                
            # 检查是否为通用描述
            generic_terms = [
                "的修士", "的人", "首领", "散修", "弟子", "修者", "者",
                "长老", "护法", "执事", "堂主", "掌门", "帮主", "门主",
                "势力", "组织", "门派", "宗门", "家族", "帮派", "势力"
            ]
            if any(term in name for term in generic_terms) and name not in protected_characters:
                to_delete.append(name)
                continue
                
            # 检查是否包含标点符号或特殊字符
            if any(char in name for char in "，。！？；：""''【】《》（）()[]{}├│└─") and name not in protected_characters:
                to_delete.append(name)
                continue
                
            # 检查是否为有效的中文名称（至少包含一个中文字符）
            if not any('\u4e00' <= c <= '\u9fff' for c in name):
                to_delete.append(name)
                continue

            # 检查是否只包含属性词
            attribute_only = ["物品", "能力", "状态", "关系", "事件", "技能", "装备", "道具", "功法", "法宝"]
            if all(word in attribute_only for word in name.split()):
                to_delete.append(name)
                continue

        # 删除非角色条目
        for name in to_delete:
            if name not in protected_characters:  # 再次确认不删除保护角色
                del self.characters[name]
                logging.info(f"从角色库中删除非角色条目: {name}")
        
        # 确保保护角色存在于角色库中
        for name in protected_characters:
            if name not in self.characters:
                self.characters[name] = self._create_basic_character(name)
                logging.info(f"添加保护角色到角色库: {name}")
        
        # 保存清理后的角色库
        self._save_characters()
        logging.info(f"角色库清理完成，删除了 {len(to_delete)} 个非角色条目，当前剩余 {len(self.characters)} 个角色")

    def _load_outline_file(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    self.chapter_outlines = [
                        ChapterOutline(**chapter)
                        for chapter in outline_data
                    ]
                logging.info(f"成功从文件加载大纲，共 {len(self.chapter_outlines)} 章")
            except Exception as e:
                logging.error(f"加载大纲文件时出错: {str(e)}")
                self.chapter_outlines = []
        else:
            logging.info("大纲文件不存在，初始化为空大纲")
            self.chapter_outlines = []

    def generate_outline(
        self,
        novel_type: str,
        theme: str,
        style: str,
        current_start_chapter_num: int = 1,
        current_batch_size: int = None,
        mode: str = "append",
        replace_range: tuple = None,
        extra_prompt: str = None
    ):
        """生成小说大纲。"""
        # 设置默认批次大小
        if current_batch_size is None:
            current_batch_size = self.config.novel_config.get("batch_size", 3)

        # 处理替换模式的参数
        if mode == "replace":
            if not replace_range or len(replace_range) != 2:
                raise ValueError("替换模式需要提供有效的替换范围 (start, end)")
            start, end = replace_range
            if start < 1 or end < start:
                raise ValueError(f"无效的替换范围: ({start}, {end})")
            if end > len(self.chapter_outlines):
                raise ValueError(f"替换范围超出现有大纲长度: {len(self.chapter_outlines)}")
            current_start_chapter_num = start
            current_batch_size = end - start + 1

        # 获取现有大纲内容作为上下文
        existing_context = ""
        if self.chapter_outlines:
            # 获取最近的3章作为上下文
            context_start = max(0, current_start_chapter_num - 4)
            context_chapters = self.chapter_outlines[context_start:current_start_chapter_num - 1]
            if context_chapters:
                existing_context = "已有章节概要：\n" + "\n".join([
                    f"第{c.chapter_number}章 {c.title}\n"
                    f"- 关键情节：{', '.join(c.key_points)}\n"
                    f"- 涉及角色：{', '.join(c.characters)}\n"
                    f"- 场景：{', '.join(c.settings)}\n"
                    f"- 冲突：{', '.join(c.conflicts)}\n"
                    for c in context_chapters
                ])

        # 生成大纲提示词
        prompt = prompts.get_outline_prompt(
            novel_type=novel_type,
            theme=theme,
            style=style,
            current_start_chapter_num=current_start_chapter_num,
            current_batch_size=current_batch_size,
            existing_context=existing_context,
            extra_prompt=extra_prompt
        )

        try:
            # 调用模型生成大纲
            outline_text = self.outline_model.generate(prompt)
            if not outline_text:
                raise ValueError("模型返回空内容")

            # 解析大纲
            try:
                batch_outlines = self._parse_outline(outline_text)
                if not batch_outlines:
                    raise ValueError("解析结果为空")
                
                # 验证生成的章节数量
                if len(batch_outlines) != current_batch_size:
                    raise ValueError(f"生成的章节数量不符：期望 {current_batch_size} 章，实际生成 {len(batch_outlines)} 章")
                
                # 验证章节号的连续性和正确性
                expected_numbers = list(range(current_start_chapter_num, current_start_chapter_num + current_batch_size))
                actual_numbers = [o.chapter_number for o in batch_outlines]
                if actual_numbers != expected_numbers:
                    raise ValueError(f"章节号不连续或不正确。期望: {expected_numbers}，实际: {actual_numbers}")

                # 处理生成的大纲
                if mode == "replace":
                    # 替换指定范围的章节
                    self.chapter_outlines[start - 1 : end] = batch_outlines
                    logging.info(f"已替换第 {start} 至 {end} 章的大纲")
                else:
                    # 追加新章节
                    self.chapter_outlines.extend(batch_outlines)
                    logging.info(f"已追加 {len(batch_outlines)} 章新大纲")
                
                # 保存大纲
                self._save_outline()
                logging.info(f"大纲更新完成，当前共有 {len(self.chapter_outlines)} 章")
                return True

            except ValueError as parse_err:
                logging.error(f"解析大纲失败: {str(parse_err)}")
                logging.error(f"原始大纲文本: {outline_text}")
                # 对于解析错误，我们可以选择重试或返回失败
                return False

        except Exception as e:
            logging.error(f"生成大纲时发生错误: {str(e)}")
            logging.error(f"使用的提示词: {prompt}")
            return False

        return True

    def _parse_outline(self, outline_text: str) -> List[ChapterOutline]:
        """解析生成的大纲文本。"""
        try:
            # 尝试清理可能的前后缀文本
            outline_text = outline_text.strip()
            # 找到第一个 '[' 和最后一个 ']'
            start_idx = outline_text.find('[')
            end_idx = outline_text.rfind(']')
            
            if start_idx == -1 or end_idx == -1:
                raise ValueError(f"无法找到有效的JSON数组标记。start_idx={start_idx}, end_idx={end_idx}")
            
            # 提取JSON数组部分
            outline_text = outline_text[start_idx:end_idx + 1]
            
            # 尝试解析JSON
            data = json.loads(outline_text)
            
            if not isinstance(data, list):
                raise ValueError(f"解析结果不是列表类型: {type(data)}")
            
            outlines = []
            for item in data:
                # 验证必需字段
                required_fields = ['chapter_number', 'title', 'key_points', 'characters', 'settings', 'conflicts']
                missing_fields = [field for field in required_fields if field not in item]
                if missing_fields:
                    raise ValueError(f"章节 {item.get('chapter_number', '未知')} 缺少必需字段: {', '.join(missing_fields)}")
                
                # 验证字段类型
                if not isinstance(item['chapter_number'], int):
                    raise ValueError(f"章节号必须是整数: {item['chapter_number']}")
                if not isinstance(item['title'], str):
                    raise ValueError(f"标题必须是字符串: {item['title']}")
                if not isinstance(item['key_points'], list) or not all(isinstance(x, str) for x in item['key_points']):
                    raise ValueError(f"key_points 必须是字符串列表: {item['key_points']}")
                if not isinstance(item['characters'], list) or not all(isinstance(x, str) for x in item['characters']):
                    raise ValueError(f"characters 必须是字符串列表: {item['characters']}")
                if not isinstance(item['settings'], list) or not all(isinstance(x, str) for x in item['settings']):
                    raise ValueError(f"settings 必须是字符串列表: {item['settings']}")
                if not isinstance(item['conflicts'], list) or not all(isinstance(x, str) for x in item['conflicts']):
                    raise ValueError(f"conflicts 必须是字符串列表: {item['conflicts']}")
                
                # 验证列表长度要求
                if len(item['key_points']) < 3:
                    raise ValueError(f"章节 {item['chapter_number']} 的 key_points 至少需要3个元素")
                if len(item['characters']) < 2:
                    raise ValueError(f"章节 {item['chapter_number']} 的 characters 至少需要2个元素")
                if len(item['settings']) < 1:
                    raise ValueError(f"章节 {item['chapter_number']} 的 settings 至少需要1个元素")
                if len(item['conflicts']) < 1:
                    raise ValueError(f"章节 {item['chapter_number']} 的 conflicts 至少需要1个元素")
                
                outline = ChapterOutline(
                    chapter_number=item['chapter_number'],
                    title=item['title'],
                    key_points=item['key_points'],
                    characters=item['characters'],
                    settings=item['settings'],
                    conflicts=item['conflicts']
                )
                outlines.append(outline)
            
            # 验证章节号的连续性
            chapter_numbers = [o.chapter_number for o in outlines]
            expected_numbers = list(range(min(chapter_numbers), max(chapter_numbers) + 1))
            if chapter_numbers != expected_numbers:
                raise ValueError(f"章节号不连续。期望: {expected_numbers}，实际: {chapter_numbers}")
            
            return outlines
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析错误: {str(e)}")
            logging.error(f"原始文本: {outline_text}")
            raise ValueError(f"无法解析大纲JSON: {str(e)}")
        except Exception as e:
            logging.error(f"解析大纲时出错: {str(e)}")
            logging.error(f"原始文本: {outline_text}")
            raise

    def _save_outline(self):
        """保存大纲到文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        try:
            outline_data = [
                {
                    "chapter_number": outline.chapter_number,
                    "title": outline.title,
                    "key_points": outline.key_points,
                    "characters": outline.characters,
                    "settings": outline.settings,
                    "conflicts": outline.conflicts
                }
                for outline in self.chapter_outlines
            ]
            with open(outline_file, 'w', encoding='utf-8') as f:
                json.dump(outline_data, f, ensure_ascii=False, indent=2)
            logging.info(f"大纲已保存到: {outline_file}")
        except Exception as e:
            logging.error(f"保存大纲时出错: {str(e)}")

    def _format_references(self, outline_dict):
        """格式化参考信息供章节生成使用"""
        # 构建搜索查询
        query = f"{outline_dict['title']} {', '.join(outline_dict['key_points'])} {', '.join(outline_dict['characters'])} {', '.join(outline_dict['settings'])} {', '.join(outline_dict['conflicts'])}"
        
        # 搜索相关内容
        search_results = []
        try:
            search_results = self.knowledge_base.search(query, k=5)
        except Exception as e:
            logging.error(f"搜索参考信息时出错: {str(e)}")
            # 提供默认参考材料，确保能包含章节大纲中的关键情节点
            return {
                'plot_references': [point for point in outline_dict['key_points']],
                'character_references': [char for char in outline_dict['characters']],
                'setting_references': [setting for setting in outline_dict['settings']]
            }
        
        # 格式化参考信息
        references = {
            'plot_references': [],
            'character_references': [],
            'setting_references': []
        }
        
        # 将搜索结果分类到不同的参考类别
        for chunk, _ in search_results:
            content = chunk.content
            
            # 简单的分类逻辑，根据内容特征决定分到哪个类别
            if any(char in content for char in outline_dict['characters']):
                references['character_references'].append(content[:200])  # 截取前200个字符
            
            if any(setting in content for setting in outline_dict['settings']):
                references['setting_references'].append(content[:200])
            
            # 其他内容归为情节参考
            references['plot_references'].append(content[:200])
        
        # 确保每个类别至少有一个项目
        if not references['plot_references']:
            references['plot_references'] = ["暂无相关情节参考"]
        
        if not references['character_references']:
            references['character_references'] = ["暂无相关角色参考"]
        
        if not references['setting_references']:
            references['setting_references'] = ["暂无相关场景参考"]
        
        return references

    def generate_novel(self):
        """生成小说内容"""
        try:
            # 检查是否有大纲
            if not self.chapter_outlines:
                logging.error("没有找到大纲，请先生成大纲")
                return
            
            # 从当前章节开始生成
            total_chapters = len(self.chapter_outlines)
            max_retries = 3  # 每章最多重试3次
            
            while self.current_chapter < total_chapters:
                chapter_retries = 0
                while chapter_retries < max_retries:
                    try:
                        # 获取当前章节大纲
                        chapter_outline = self.chapter_outlines[self.current_chapter]
                        logging.info(f"开始生成第 {self.current_chapter + 1} 章: {chapter_outline.title}")
                        
                        # 将 ChapterOutline 对象转换为字典
                        outline_dict = {
                            "chapter_number": chapter_outline.chapter_number,
                            "title": chapter_outline.title,
                            "key_points": chapter_outline.key_points,
                            "characters": chapter_outline.characters,
                            "settings": chapter_outline.settings,
                            "conflicts": chapter_outline.conflicts
                        }
                        
                        # 构建提示词 - 在重试时添加额外指导
                        extra_prompt = ""
                        if chapter_retries > 0:
                            extra_prompt = f"""
                            注意：这是第{chapter_retries+1}次尝试生成。请确保包含以下关键情节点：
                            - {chr(10).join(['- ' + point for point in chapter_outline.key_points])}
                            
                            请确保包含以下角色：
                            - {chr(10).join(['- ' + character for character in chapter_outline.characters])}
                            
                            请确保描述以下场景：
                            - {chr(10).join(['- ' + setting for setting in chapter_outline.settings])}
                            
                            请确保包含以下冲突：
                            - {chr(10).join(['- ' + conflict for conflict in chapter_outline.conflicts])}
                            """
                        
                        # 尝试从前一章获取上下文信息
                        context_info = ""
                        if self.current_chapter > 0:
                            prev_chapter_num = self.current_chapter
                            prev_chapter_file = None
                            for filename in os.listdir(self.output_dir):
                                if filename.startswith(f"第{prev_chapter_num}章") and filename.endswith(".txt"):
                                    prev_chapter_file = os.path.join(self.output_dir, filename)
                                    break
                                    
                            if prev_chapter_file and os.path.exists(prev_chapter_file):
                                try:
                                    with open(prev_chapter_file, 'r', encoding='utf-8') as f:
                                        prev_content = f.read()
                                    context_info = prev_content[-1000:]  # 使用前一章最后1000字符作为上下文
                                except Exception as e:
                                    logging.warning(f"读取前一章内容时出错: {str(e)}")
                        
                        # 获取章节内容
                        prompt = prompts.get_chapter_prompt(
                            outline=outline_dict,
                            references=self._format_references(outline_dict),
                            extra_prompt=extra_prompt,
                            context_info=context_info
                        )
                        
                        # 生成章节内容
                        try:
                            logging.info(f"正在生成第 {self.current_chapter + 1} 章内容...")
                            content = self.content_model.generate(prompt)
                            
                            # 验证章节内容
                            if self._validate_chapter_content(content, chapter_outline):
                                # 保存章节
                                self._save_chapter(self.current_chapter + 1, content)
                                logging.info(f"第 {self.current_chapter + 1} 章生成完成")
                                
                                # 更新进度
                                self.current_chapter += 1
                                self._save_progress()
                                break  # 跳出重试循环，继续下一章
                            else:
                                logging.error(f"第 {self.current_chapter + 1} 章内容验证失败，这是第 {chapter_retries + 1} 次尝试")
                                chapter_retries += 1
                                
                                # 如果所有重试都失败，尝试放宽验证标准
                                if chapter_retries >= max_retries:
                                    logging.warning(f"已达到最大重试次数，使用最后一次生成的内容并继续...")
                                    self._save_chapter(self.current_chapter + 1, content)
                                    logging.info(f"第 {self.current_chapter + 1} 章已保存（警告：内容可能不完全符合要求）")
                                    self.current_chapter += 1
                                    self._save_progress()
                                    break
                                
                                # 重试前等待一段时间
                                wait_time = 10 * (chapter_retries + 1)  # 逐次增加等待时间
                                logging.info(f"等待 {wait_time} 秒后重试...")
                                time.sleep(wait_time)
                                
                        except (TimeoutError, asyncio.TimeoutError) as e:
                            logging.error(f"生成第 {self.current_chapter + 1} 章时请求超时: {str(e)}")
                            chapter_retries += 1
                            wait_time = 30 * (chapter_retries + 1)
                            logging.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                        except Exception as e:
                            logging.error(f"生成第 {self.current_chapter + 1} 章时出错: {str(e)}")
                            chapter_retries += 1
                            wait_time = 30 * (chapter_retries + 1)
                            logging.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)
                            
                    except Exception as e:
                        logging.error(f"处理第 {self.current_chapter + 1} 章时出错: {str(e)}")
                        chapter_retries += 1
                        wait_time = 30 * (chapter_retries + 1)
                        logging.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                
                # 检查是否因为重试次数用尽而没有成功生成当前章节
                if chapter_retries >= max_retries:
                    logging.error(f"在 {max_retries} 次尝试后未能成功生成第 {self.current_chapter + 1} 章，但仍将继续下一章")
                    # 在这种情况下，我们已经在内部循环中处理了进度更新，所以这里不需要额外处理
                    
            logging.info("小说生成完成！")
            
        except Exception as e:
            logging.error(f"生成小说时发生错误: {str(e)}")
            raise

    def _validate_chapter_content(self, content: str, outline: ChapterOutline) -> bool:
        """验证章节内容是否符合要求"""
        try:
            # 检查内容长度
            if len(content) < 1000:  # 假设最小1000字
                logging.error("章节内容过短")
                return False
                
            # 检查是否包含关键情节点（改为更灵活的检查）
            missing_points = []
            for point in outline.key_points:
                # 提取关键词（去除常见连接词和标点）
                keywords = re.sub(r'[，。！？；：""''【】《》（）()[\]{}、]', ' ', point)
                keywords = re.sub(r'\s+', ' ', keywords).strip()
                keywords = [k for k in keywords.split() if len(k) > 1 and k not in ['的', '了', '和', '与', '在', '对', '是']]
                
                # 只要包含一半以上的关键词就算通过
                matches = sum(1 for k in keywords if k in content)
                if matches < len(keywords) / 2:
                    missing_points.append(point)
                    logging.warning(f"可能缺少关键情节点: {point}，只匹配到 {matches}/{len(keywords)} 个关键词")
            
            if missing_points:
                logging.error(f"缺少 {len(missing_points)}/{len(outline.key_points)} 个关键情节点")
                for point in missing_points[:3]:  # 只显示前三个，避免日志过长
                    logging.error(f"缺少关键情节点: {point}")
                
                # 如果缺失太多关键情节点，验证失败
                if len(missing_points) > len(outline.key_points) // 2:
                    return False
                
            # 检查是否包含主要角色（改为更灵活的检查）
            missing_chars = []
            for character in outline.characters:
                if character not in content:
                    # 尝试检查角色名的变体（例如：只用姓或名）
                    if len(character) > 1 and (character[0] in content or character[1:] in content):
                        continue
                    missing_chars.append(character)
            
            if missing_chars:
                logging.error(f"缺少 {len(missing_chars)}/{len(outline.characters)} 个主要角色")
                for char in missing_chars:
                    logging.error(f"缺少主要角色: {char}")
                
                # 如果缺失太多角色，验证失败
                if len(missing_chars) > len(outline.characters) // 2:
                    return False
                
            # 检查是否包含场景描写和冲突（采用同样灵活的策略）
            missing_settings = []
            for setting in outline.settings:
                # 提取关键词
                setting_keywords = re.sub(r'[，。！？；：""''【】《》（）()[\]{}、]', ' ', setting)
                setting_keywords = re.sub(r'\s+', ' ', setting_keywords).strip()
                setting_keywords = [k for k in setting_keywords.split() if len(k) > 1 and k not in ['的', '了', '和', '与', '在', '对', '是']]
                
                matches = sum(1 for k in setting_keywords if k in content)
                if matches < len(setting_keywords) / 2:
                    missing_settings.append(setting)
            
            if missing_settings and len(missing_settings) > len(outline.settings) // 2:
                logging.error(f"缺少场景描写: {missing_settings}")
                return False
            
            missing_conflicts = []
            for conflict in outline.conflicts:
                # 提取关键词
                conflict_keywords = re.sub(r'[，。！？；：""''【】《》（）()[\]{}、]', ' ', conflict)
                conflict_keywords = re.sub(r'\s+', ' ', conflict_keywords).strip()
                conflict_keywords = [k for k in conflict_keywords.split() if len(k) > 1 and k not in ['的', '了', '和', '与', '在', '对', '是']]
                
                matches = sum(1 for k in conflict_keywords if k in content)
                if matches < len(conflict_keywords) / 2:
                    missing_conflicts.append(conflict)
            
            if missing_conflicts and len(missing_conflicts) > len(outline.conflicts) // 2:
                logging.error(f"缺少冲突: {missing_conflicts}")
                return False
                    
            # 使用一致性检查器验证
            if not self.consistency_checker.check(content):
                logging.error("一致性检查失败")
                return False
                
            # 使用逻辑验证器验证
            if not self.logic_validator.validate(content):
                logging.error("逻辑验证失败")
                return False
                
            # 使用重复内容验证器验证
            if not self.duplicate_validator.validate(content):
                logging.error("发现重复内容")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"验证章节内容时出错: {str(e)}")
            return False