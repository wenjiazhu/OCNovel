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
# from nltk.tokenize import word_tokenize # 可以移除 nltk 依赖
# from nltk.corpus import wordnet # 可以移除 nltk 依赖
try:
    import jieba # 尝试导入 jieba
except ImportError:
    logging.warning("jieba 库未安装，关键词提取可能效果不佳。请运行 'pip install jieba'")
    jieba = None # 设置为 None，以便后续检查

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
    def __init__(self, config, outline_model, content_model, knowledge_base, target_chapter=None, external_prompt: Optional[str] = None):
        self.config = config
        self.outline_model = outline_model
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.target_chapter = target_chapter  # 设置 target_chapter
        self.external_prompt = external_prompt  # <--- 保存外部提示词
        
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
            print("FileHandler 创建成功") # 确认 FileHandler 创建

            handler.setLevel(logging.DEBUG) # 设置 handler 的日志级别
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)

            logger = logging.getLogger() # 获取 root logger
            logger.addHandler(handler) # 添加 handler 到 root logger
            logger.setLevel(logging.DEBUG) # 设置 root logger 的日志级别

            print("日志 Handler 添加到 Logger") # 确认 Handler 添加成功
            logging.info("日志系统初始化完成") # 添加一条日志，确认日志系统工作

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
                    for chapter in outline_data  # 直接迭代列表
                ]
    
    def _extract_characters_from_existing_chapters(self):
        """从已生成的章节中提取角色信息"""
        logging.info("开始从已生成章节中提取角色信息...")
        
        try:
            # 查找已生成的章节文件
            chapter_files = []
            for filename in os.listdir(self.output_dir):
                if filename.startswith("已生成") and filename.endswith(".txt"):
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
            except Exception as e:
                 logging.error(f"从已生成章节提取角色信息时出错: {str(e)}")

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
                # 使用 (self.characters or {}) 确保即使 self.characters 为None 也不会出错
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
        """加载角色库 返回字典或None"""
        logging.info("开始加载角色库...")
        characters_dict = {}
        if os.path.exists(self.characters_file):
            try:
                with open(self.characters_file, 'r', encoding='utf-8') as f:
                    characters_data = json.load(f)
                    # 检查加载的数据是否为字典
                    if not isinstance(characters_data, dict):
                        logging.error(f"角色库文件{self.characters_file} 包含无效数据 (不是字典): {type(characters_data)}")
                        return None # 返回 None 表示加载失败

                    logging.info(f"从文件中加载到角色数量(前500 字符): {str(characters_data)[:500]}") # 记录加载内容（部分）

                    # 尝试构建 Character 对象
                    temp_chars = {}
                    for name, data in characters_data.items():
                        try:
                            char = Character(**data)
                            # 补充旧数据兼容性处理
                            if not hasattr(char, 'sect'): char.sect = "无门无派"
                            if not hasattr(char, 'position'): char.position = "普通弟子"
                            # 补充更多可能缺失的字段
                            if not hasattr(char, 'alignment'): char.alignment = "中立"
                            if not hasattr(char, 'realm'): char.realm = "凡人"
                            if not hasattr(char, 'level'): char.level = 1
                            if not hasattr(char, 'cultivation_method'): char.cultivation_method = "无"
                            if not hasattr(char, 'magic_treasure'): char.magic_treasure = []
                            if not hasattr(char, 'temperament'): char.temperament = "平和"
                            if not hasattr(char, 'ability'): char.ability = []
                            if not hasattr(char, 'stamina'): char.stamina = 100
                            if not hasattr(char, 'emotions_history'): char.emotions_history = []
                            if not hasattr(char, 'states_history'): char.states_history = []
                            if not hasattr(char, 'descriptions_history'): char.descriptions_history = []
                            temp_chars[name] = char
                        except TypeError as te:
                            logging.warning(f"创建角色 '{name}' 时数据字段不匹配或缺失 {te}. Data: {data}")
                        except Exception as char_e:
                            logging.error(f"创建角色 '{name}' 时发生未知错误 {char_e}. Data: {data}")

                    characters_dict = temp_chars # 赋值给局部变量

                    # 加载后立即清理
                    self.characters = characters_dict
                    self.clean_character_library()
                    characters_dict = self.characters # 获取清理后的结果

            except json.JSONDecodeError as e:
                logging.error(f"加载角色库文件{self.characters_file} 从JSON 解析失败: {e}")
                return None # 返回 None 表示加载失败
            except Exception as e:
                logging.error(f"加载角色库文件{self.characters_file} 时发生未知错误 {e}", exc_info=True)
                return None # 返回 None 表示加载失败
        else:
            logging.info("角色库文件不存在，根据配置初始化基础角色...")
            characters_dict = {}
            try:
                # 尝试从 config.json 加载初始角色
                character_guide = self.config.novel_config.get("writing_guide", {}).get("character_guide", {})

                # 1. 处理主角
                protagonist_data = character_guide.get("protagonist", {})
                protagonist_bg = protagonist_data.get("background", "")
                # 尝试从背景描述中提取主角名（这里假设主角名为"陆沉"）
                # 注意：这种提取方式比较脆弱，最好在config中明确指定主角名
                protagonist_name = "主角" # 默认名
                match = re.search(r"([^\s，。；：？！]{2,4})(?:意外觉醒|继承)", protagonist_bg) # 尝试匹配名字
                if match:
                    protagonist_name = match.group(1)
                elif "陆沉" in protagonist_bg: # B方案：直接查找特定名字
                    protagonist_name = "陆沉"

                if protagonist_name:
                    char = self._create_basic_character(protagonist_name)
                    char.role = "主角"
                    # 可以根据config中的描述稍微丰富一下初始设定
                    if "坚韧" in protagonist_bg or "机智" in protagonist_bg:
                         char.personality = {"坚韧": 0.8, "机智": 0.7}
                    # 从背景中提取目标
                    goals = re.findall(r"对抗(.+?)[\s，。；：？！]", protagonist_bg) + re.findall(r"收集(.+?)[\s，。；：？！]", protagonist_bg)
                    if goals:
                         char.goals = goals

                    characters_dict[char.name] = char # 使用 _create_basic_character 返回的名字（可能是简体）
                    logging.info(f"已初始化主角: {char.name}")

                # 2. 处理配角
                supporting_roles_data = character_guide.get("supporting_roles", [])
                for i, role_data in enumerate(supporting_roles_data):
                    role_name = role_data.get("role_type")
                    if role_name:
                        char = self._create_basic_character(role_name)
                        char.role = "配角"
                        characters_dict[char.name] = char
                        logging.info(f"已初始化配角: {char.name}")
                    else:
                         logging.warning(f"配置文件中第 {i+1} 个配角缺少 'role_type'")

                # 3. 处理反派
                antagonists_data = character_guide.get("antagonists", [])
                for i, role_data in enumerate(antagonists_data):
                    role_name = role_data.get("role_type")
                    if role_name:
                        char = self._create_basic_character(role_name)
                        char.role = "反派"
                        characters_dict[char.name] = char
                        logging.info(f"已初始化反派: {char.name}")
                    else:
                         logging.warning(f"配置文件中第 {i+1} 个反派缺少 'role_type'")

                # 如果经过以上步骤，角色库仍然为空，则添加一个默认角色以防万一
                if not characters_dict:
                     logging.warning("未能从配置中初始化任何角色，添加默认主角 '陆沉'")
                     char = self._create_basic_character("陆沉")
                     char.role = "主角"
                     characters_dict[char.name] = char

            except Exception as e:
                logging.error(f"从配置初始化角色时出错: {str(e)}，将使用默认主角 '陆沉'")
                # 出错时回退到只添加默认主角
                char = self._create_basic_character("陆沉")
                char.role = "主角"
                characters_dict = {char.name: char}

        return characters_dict

    def _save_characters(self):
        """保存角色库"""
        logging.info("开始保存角色库...") # 添加日志：开始保存角色库
        logging.info(f"当前角色库数量 {self.characters}") # 添加日志：打印当前角色库数据
        print(f"正在保存角色库到文件: {self.characters_file}") # 打印文件路径**新增日志**
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
            # 使用 (self.characters or {}) 确保即使 self.characters 为None 也不会出错
            for name, char in (self.characters or {}).items()
        }
        logging.debug(f"即将保存的角色库 JSON 数据: {characters_data}") # 打印 JSON 数据 **新增日志**
        with open(self.characters_file, 'w', encoding='utf-8') as f:
            json.dump(characters_data, f, ensure_ascii=False, indent=2)
        logging.info("角色库保存完成") # 添加日志：角色库保存完成 
        
        # 注释掉自动运行清理脚本的部分
        """
        # 运行清理脚本
        try:
            import subprocess
            logging.info("开始运行角色库清理脚本...")
            subprocess.run(['python', 'scripts/clean_characters.py'], check=True)
            logging.info("角色库清理脚本运行完成")
            
            # 重新加载清理后的角色
            cleaned_file = os.path.join(self.output_dir, "characters_cleaned.json")
            if os.path.exists(cleaned_file):
                with open(cleaned_file, 'r', encoding='utf-8') as f:
                    cleaned_data = json.load(f)
                    self.characters = {
                        name: Character(**data)
                        for name, data in cleaned_data.items()
                    }
                logging.info("已加载清理后的角色库")
                
                # 将清理后的文件复制回原始文件
                import shutil
                shutil.copy2(cleaned_file, self.characters_file)
                logging.info("已更新原始角色库文件")
        except Exception as e:
            logging.error(f"运行角色库清理脚本时出错: {str(e)}")
        """

    def _create_basic_character(self, name: str) -> Character:
        """创建基本角色信息"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体

        # 检查是否存在简体版本
        simplified_name = t2s.convert(name)
        # 如果存在简体版本，则使用简体名称（避免因为繁简体导致重复添加）
        # if simplified_name != name and simplified_name in self.characters:
        #     return self.characters[simplified_name] # 不在这里检查 self.characters，因为此函数可能在初始化时调用

        # 使用简体名称创建新角色
        return Character(
            name=simplified_name,
            role="配角", # 默认角色为配角，调用者可以覆盖
            personality={"平和": 0.5}, # 默认性格
            goals=["暂无明确目标"], # 默认目标
            relationships={}, # 默认关系
            development_stage="初次登场", # 默认发展阶段
            # 添加其他基础默认值
            alignment="中立",
            realm="凡人",
            level=1,
            cultivation_method="无",
            magic_treasure=[],
            temperament="平和",
            ability=[],
            stamina=100,
            sect="无门无派",
            position="普通弟子",
            emotions_history=[],
            states_history=[],
            descriptions_history=[]
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
                    # Escape delimiters to handle regex special characters
                    escaped_left = re.escape(left)
                    escaped_right = re.escape(right)
                    # Construct pattern using escaped delimiters
                    # Using non-greedy match (safer for nested structures):
                    pattern = f'{escaped_left}(.*?){escaped_right}' # 使用非贪婪匹配替代原来的 negated character set

                    try:
                        # Use the constructed pattern
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
                    except re.error as regex_e: # Catch regex specific errors
                        logging.error(f"正则表达式处理时出错 (pattern: {pattern}): {regex_e}")
                    except Exception as e:
                        # Log general errors during matching/processing
                        logging.error(f"处理匹配项时出错 (pattern: {pattern}): {e}")
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
    
    def _save_chapter(self, chapter_num: int, content: str, skip_character_update: bool = False):
        """保存章节文件，并可选择更新摘要和角色信息"""
        try:
            # 从大纲中获取章节标题 (注意 chapter_num 是从1开始的，列表索引需要减1)
            chapter_idx = chapter_num - 1
            if chapter_idx < 0 or chapter_idx >= len(self.chapter_outlines):
                logging.error(f"尝试保存章节 {chapter_num} 时发生错误：无效的章节索引{chapter_idx}")
                # 使用默认标题或抛出错误
                title = f"未知标题_{chapter_num}"
            else:
                title = self.chapter_outlines[chapter_idx].title

            # 清理标题以创建安全的文件名
            # 移除或替换可能导致问题的字符： \ : * ? " < > | 以及控制字符
            safe_title = re.sub(r'[\\/*?:"<>|\x00-\x1f]', '', title)
            safe_title = safe_title.replace(" ", "_") # 可选：用下划线替换空格
            if not safe_title: # 如果清理后标题为空，使用默认名称
                safe_title = f"章节_{chapter_num}"

            # 在保存之前，将连续的空格替换为一个换行符
            content = re.sub(r' +', '\n', content)

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
            logging.error(f"保存章节 {chapter_num} 时发生错误 {str(e)}")
            # 可以选择在这里重新抛出异常，或者仅记录错误
            # raise

    def _update_characters_from_content(self, chapter_num: int, content: str):
        """分析章节内容并更新角色信息"""
        logging.info(f"开始从第{chapter_num} 章内容更新角色信息..")
        
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
            
            # 从章节内容中提取出现的角色名字
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
                logging.error(f"第{chapter_num} 章 发现新角色请求超时 {str(e)}，跳过新角色发现")
            except Exception as e:
                logging.error(f"第{chapter_num} 章 发现新角色时出错: {str(e)}")

            # 再次检查新发现的角色是否在内容中出现
            for name in list(self.characters.keys()):
                if name in cleaned_content and name not in current_chapter_characters:
                    current_chapter_characters.add(name)
            
            # 手动检查常见角色名
            common_characters = ["陆沉"]
            for name in common_characters:
                if name in cleaned_content:
                    # 如果角色不在角色库中，添加它
                    if name not in self.characters:
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"手动添加常见角色: {name}")
                    
                    # 确保将这个角色添加到当前章节的角色列表中
                    current_chapter_characters.add(name)
            
            if not current_chapter_characters:
                logging.warning(f"第{chapter_num} 章未发现任何角色，跳过角色更新")
                return
                
            # 只获取当前章节出现的角色的状态文字
            existing_characters_text = self._format_characters_for_update(current_chapter_characters)
            
            # 使用角色更新提示
            prompt = prompts.get_character_update_prompt(cleaned_content, existing_characters_text)
            try:
                characters_update = self.content_model.generate(prompt)
                if not self._validate_character_update(characters_update):
                    logging.error("角色更新内容格式验证失败，保留原有角色信息")
                    return
                self._parse_character_update(characters_update, chapter_num, current_chapter_characters)
                # 更新后立即清理
                self.clean_character_library()
                
                # 验证一致性..
                if not self._verify_character_consistency(cleaned_content, current_chapter_characters):
                     logging.warning("角色信息与章节内容存在不一致，尝试进行修正...")
                     self._correct_character_inconsistencies(cleaned_content, current_chapter_characters)
                
                logging.info(f"第{chapter_num} 章角色信息更新完成..")
                
                # 确保常见角色信息得到保留
                for name in common_characters:
                    if name in cleaned_content and name not in self.characters:
                        # 如果清理过程中删除了这些角色，重新添加它们
                        self.characters[name] = self._create_basic_character(name)
                        logging.info(f"清理后恢复常见角色 {name}")
                
                # 在进行完所有更新后再次保存角色库
                self._save_characters()

            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.error(f"第{chapter_num} 章 角色更新请求超时: {str(e)}，跳过本次更新")
            except Exception as e:
                 logging.error(f"第{chapter_num} 章 更新角色信息时出错（模型调用或解析阶段）: {str(e)}")

        except Exception as e:
            logging.error(f"更新角色信息时发生意外错误 {str(e)}", exc_info=True)

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
            formatted_text += f"│ ├──身体状态 {char.realm}, {char.temperament}\n"
            formatted_text += f"│ └──心理状态 {char.development_stage}\n"
            formatted_text += f"├──主要角色间关系网\n"
            for rel_name, rel_type in char.relationships.items():
                formatted_text += f"│ └──{rel_name}: {rel_type}\n"
            formatted_text += f"└──触发或加深的事件: {', '.join(char.goals)}\n\n"
        return formatted_text

    def _merge_duplicate_characters(self):
        """合并重复的角色（包括繁简体变体）"""
        # 创建繁简转换器
        t2s = OpenCC('t2s')  # 繁体转简体
        
        # 用于存储需要合并的角色
        to_merge = {}  # 格式: {简体名: [异体名, 异体名, ...]}
        
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
                    logging.info(f"合并角色 '{variant_name}' 为 '{simplified_name}'")

    def clean_character_library(self):
        """清理角色库中的非角色条目"""
        # 首先合并重复角色
        self._merge_duplicate_characters()
        
        # 需要删除的条目的关键词列表
        non_character_keywords = [
            # 分析相关词
            "收到文本",
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
            "帮派",
            "势力"
        ]
        
        # 保护列表 - 这些角色不会被删除
        protected_characters = ["陆沉"]
        
        # 记录要删除的角色
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
            if name[0].isdigit() or name.startswith(('##', '**', '？', '[', '？', '？', '？', '─')):
                to_delete.append(name)
                continue
                
            # 检查名称长度是否过长（正常人名一般不会超过12个汉字）
            if len(name) > 12:
                to_delete.append(name)
                continue
                
            # 检查是否为描述性文本而不是名字
            if len(name.split()) > 2:  # 如果包含多个词，可能是描述性文字
                to_delete.append(name)
                continue
                
            # 检查是否为通用描述
            generic_terms = [
                "的修行", "的人", "首领", "散修", "弟子", "修行", "？", "？",
                "长者", "护法", "执事", "堂主", "掌门", "帮主", "门主",
                "势力", "组织", "门派", "宗门", "家族", "帮派", "势力"
            ]
            if any(term in name for term in generic_terms) and name not in protected_characters:
                to_delete.append(name)
                continue
                
            # 检查是否包含标点符号或特殊字符
            if any(char in name for char in "，。！？；？''【】《》（）[]{}├│└─:：\n") and name not in protected_characters:
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
        num_deleted = 0
        for name in to_delete:
            if name not in protected_characters:  # 再次确认不删除保护角色
                del self.characters[name]
                logging.info(f"从角色库中删除非角色条目: '{name}' (原因: 包含非角色关键词)")
                num_deleted += 1

        # 确保保护角色存在于角色库中
        for name in protected_characters:
            if name not in self.characters:
                self.characters[name] = self._create_basic_character(name)
                logging.info(f"添加保护角色到角色库: {name}")

        # 不在此处保存，保存操作移至更高层级
        # self._save_characters()
        logging.info(f"角色库清理完成，尝试删除了 {len(to_delete)} 个条目，实际删除 {num_deleted} 个 (保护角色除外)，当前剩余 {len(self.characters)} 个角色")

    def _load_outline_file(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    # 检查加载的数据是否为列表
                    if not isinstance(outline_data, list):
                        logging.error(f"大纲文件 {outline_file} 格式不正确，期望列表，实际为 {type(outline_data)}")
                        self.chapter_outlines = []
                        return # 格式不正确则返回

                    # 直接迭代列表来创建 ChapterOutline 对象
                    self.chapter_outlines = [
                        ChapterOutline(**chapter)
                        for chapter in outline_data # <--- 修改这里，直接迭代列表
                    ]
                logging.info(f"成功从文件加载大纲，共 {len(self.chapter_outlines)} 章")
            except json.JSONDecodeError as e:
                logging.error(f"加载大纲文件 {outline_file} 时 JSON 解析失败: {str(e)}")
                self.chapter_outlines = []
            except Exception as e:
                logging.error(f"加载大纲文件时出错 {str(e)}")
                self.chapter_outlines = []
        else:
            logging.info("大纲文件不存在，初始化为空大纲")
            self.chapter_outlines = []

    def _get_context_for_chapter(self, chapter_num: int, successful_outlines: List[ChapterOutline] = None) -> str:
        """获取指定章节的上下文信息"""
        context_parts = []
        
        # 获取已有的上下文（从原有大纲或已成功生成的大纲中获取）
        prev_chapters = []
        
        # 首先检查已成功生成的大纲中的前几章
        if successful_outlines:
            prev_chapters.extend([
                o for o in successful_outlines 
                if o.chapter_number < chapter_num
            ])
        
        # 如果是替换模式，也要考虑原有大纲中的内容
        if chapter_num > 1:
            # 获取原有大纲中的前几章
            start_idx = max(0, chapter_num - 4)
            orig_prev_chapters = self.chapter_outlines[start_idx:chapter_num-1]
            # 只添加不在 successful_outlines 中的章节
            for chapter in orig_prev_chapters:
                if not any(o.chapter_number == chapter.chapter_number for o in prev_chapters):
                    prev_chapters.append(chapter)
        
        # 按章节号排序
        prev_chapters.sort(key=lambda x: x.chapter_number)
        # 只保留最近的3章
        prev_chapters = prev_chapters[-3:]
        
        if prev_chapters:
            context_parts.append("已有章节概要")
            for chapter in prev_chapters:
                context_parts.extend([
                    f"第{chapter.chapter_number}章 {chapter.title}",
                    f"- 关键情节：{', '.join(chapter.key_points)}",
                    f"- 涉及角色：{', '.join(chapter.characters)}",
                    f"- 场景：{', '.join(chapter.settings)}",
                    f"- 冲突：{', '.join(chapter.conflicts)}",
                    ""  # 添加空行分隔
                ])
        
        # 如果有后续成功生成的章节，也添加其信息
        if successful_outlines:
            next_chapters = [
                o for o in successful_outlines 
                if o.chapter_number > chapter_num
            ][:2]  # 只取接下来的2章
            
            if next_chapters:
                context_parts.append("后续章节概要")
                for chapter in next_chapters:
                    context_parts.extend([
                        f"第{chapter.chapter_number}章 {chapter.title}",
                        f"- 关键情节：{', '.join(chapter.key_points)}",
                        f"- 涉及角色：{', '.join(chapter.characters)}",
                        f"- 场景：{', '.join(chapter.settings)}",
                        f"- 冲突：{', '.join(chapter.conflicts)}",
                        ""  # 添加空行分隔
                    ])
        
        return "\n".join(context_parts)

    def _validate_model_config(self) -> bool:
        """验证模型配置"""
        try:
            model_name = self.outline_model.model_name.lower()
            if not model_name:
                logger.error("模型名称未设置")
                raise ValueError("模型名称不能为空")

            # 根据模型类型设置最大批次大小
            if "flash" in model_name:
                self.max_batch_size = 50
                logger.info(f"使用 Flash 模型，设置最大批次大小为 {self.max_batch_size}")
            elif "pro" in model_name:
                self.max_batch_size = 100
                logger.info(f"使用 Pro 模型，设置最大批次大小为 {self.max_batch_size}")
            else:
                self.max_batch_size = 3
                logger.info(f"使用默认模型，设置最大批次大小为 {self.max_batch_size}")

            return True

        except Exception as e:
            logger.error(f"验证模型配置时发生错误 {str(e)}")
            return False

    def _split_into_batches(self, start: int, end: int) -> List[Tuple[int, int]]:
        """将章节范围分割为适合的批次"""
        batches = []
        current_start = start
        while current_start <= end:
            batch_size = min(self.max_batch_size, end - current_start + 1)
            batches.append((current_start, current_start + batch_size - 1))
            current_start += batch_size
        return batches

    def generate_outline(self, prompt: str, retry_count: int = 3) -> Optional[NovelOutline]:
        """生成小说大纲

        Args:
            prompt: 生成提示
            retry_count: 重试次数，默认为3

        Returns:
            NovelOutline: 生成的小说大纲对象，失败返回 None
        """
        try:
            if not prompt:
                logger.error("生成大纲的提示词不能为空")
                raise ValueError("提示词不能为空")

            logger.info(f"开始生成大纲，提示词 {prompt[:50]}...")
            
            for attempt in range(retry_count):
                try:
                    # 生成大纲文本
                    outline_text = self.outline_model.generate(prompt)
                    if not outline_text:
                        logger.warning(f"第{attempt + 1}次尝试生成大纲失败，返回空文本")
                        continue

                    logging.debug(f"Generated outline text (first 400 chars): {outline_text[:400]}")

                    # 解析大纲
                    outline = self._parse_outline(outline_text)
                    if not outline:
                        logger.warning(f"第{attempt + 1}次尝试解析大纲失败")
                        continue

                    # 验证大纲质量
                    if not self._validate_outline_quality(outline):
                        logger.warning(f"第{attempt + 1}次生成的大纲质量不合格")
                        continue

                    logger.info("成功生成高质量大纲")
                    return outline

                except Exception as e:
                    logger.error(f"第{attempt + 1}次生成大纲时发生错误: {str(e)}")
                    if attempt == retry_count - 1:
                        raise

            logger.error(f"经过{retry_count}次尝试后仍未能生成合格的大纲")
            return None

        except Exception as e:
            logger.error(f"生成大纲过程中发生致命错误 {str(e)}")
            return None

    def _parse_outline(self, outline_text: str) -> Optional[NovelOutline]:
        """解析大纲文本

        Args:
            outline_text: 待解析的大纲文本

        Returns:
            NovelOutline: 解析后的大纲对象，解析失败返回None
        """
        try:
            if not outline_text or not outline_text.strip():
                logger.error("大纲文本为空，无法解析")
                return None

            logger.debug("开始解析大纲文本..")
            
            # 尝试解析 JSON 格式
            try:
                outline_data = json.loads(outline_text)
                logger.debug("成功解析 JSON 格式的大纲")
            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败: {str(e)}，尝试使用正则表达式解析")
                outline_data = self._parse_text_with_regex(outline_text)
                if not outline_data:
                    logger.error("正则表达式解析也失败")
                    return None
            
            # 验证必要字段
            required_fields = ['title', 'chapters']
            missing_fields = [field for field in required_fields if field not in outline_data]
            if missing_fields:
                logger.error(f"大纲缺少必要字段: {', '.join(missing_fields)}")
                return None

            # 验证章节数据
            chapters = outline_data.get('chapters', [])
            if not chapters:
                logger.error("大纲中没有任何章节")
                return None

            # 构建大纲对象
            outline = NovelOutline(
                title=outline_data['title'],
                chapters=[
                    ChapterOutline(
                        chapter_number=i + 1,
                        title=chapter.get('title', f'第{i+1}章'),
                        key_points=chapter.get('key_points', []),
                        characters=chapter.get('characters', []),
                        settings=chapter.get('settings', []),
                        conflicts=chapter.get('conflicts', [])
                    )
                    for i, chapter in enumerate(chapters)
                ]
            )

            logger.info(f"成功解析大纲，包含 {len(outline.chapters)} 个章节")
            return outline

        except Exception as e:
            logger.error(f"解析大纲时发生未预期的错误 {str(e)}")
            return None

    def _parse_text_with_regex(self, text: str) -> Optional[dict]:
        """使用正则表达式解析非 JSON 格式的大纲文本

        Args:
            text: 待解析的文本

        Returns:
            dict: 解析后的大纲数据字典，解析失败返回None
        """
        try:
            # 提取标题
            title_match = re.search(r'标题：\s*(.+)', text)
            if not title_match:
                logger.warning("未找到大纲标题")
                title = "未命名"
            else:
                title = title_match.group(1).strip()

            # 提取章节
            chapter_pattern = r'第\d+章\s*(.+?)\n内容\s*(.+?)(?=\n第\d+章|$)'
            chapters = []
            
            for match in re.finditer(chapter_pattern, text, re.DOTALL):
                chapter_num = int(match.group(1))
                chapter_title = match.group(2).strip()
                chapter_content = match.group(3).strip()
                
                chapters.append({
                    'title': chapter_title,
                    'content': chapter_content
                })

            if not chapters:
                logger.error("未能从文本中提取出任何章节信息")
                return None

            logger.debug(f"使用正则表达式成功解析出 {len(chapters)} 个章节")
            return {
                'title': title,
                'chapters': chapters
            }

        except Exception as e:
            logger.error(f"正则表达式解析失败 {str(e)}")
            return None

    def _save_outline(self):
        """直接保存大纲到 outline.json 文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        # 准备大纲数据
        outline_data = {
            "chapters": [
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
        }
        
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(outline_file), exist_ok=True)
            
            # 直接写入文件
            with open(outline_file, 'w', encoding='utf-8') as f:
                json.dump(outline_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"大纲已成功保存到: {outline_file}")
            logging.info(f"保存了{len(self.chapter_outlines)} 章大纲")
            
            # 输出一些大纲统计信息
            total_key_points = sum(len(chapter["key_points"]) for chapter in outline_data["chapters"])
            total_characters = sum(len(chapter["characters"]) for chapter in outline_data["chapters"])
            logging.info(f"大纲统计: {total_key_points} 个关键情节点, {total_characters} 个角色出现")
            
        except TypeError as je:
            logging.error(f"JSON编码错误: {str(je)}")
            logging.error("尝试保存的大纲数量")
            for i, outline in enumerate(self.chapter_outlines):
                logging.error(f"Chapter {i+1}: {vars(outline)}")
            raise
        except (IOError, OSError) as e:
            logging.error(f"文件操作错误: {str(e)}")
            logging.error(f"文件路径: {outline_file}")
            raise
        except Exception as e:
            logging.error(f"保存大纲时发生未预期的错误 {str(e)}")
            logging.error(f"大纲数据示例（前3章）: {self.chapter_outlines[:3]}")
            raise

    def generate_novel(self):
        """生成小说内容"""
        try:
            # 检查是否有大纲
            if not self.chapter_outlines:
                logging.error("没有找到大纲，请先生成大纲")
                return

            # 从当前章节开始生成
            total_chapters = len(self.chapter_outlines)
            max_retries = 3  # 每章最多重试次数

            while self.current_chapter < total_chapters:
                if self.target_chapter is not None and self.current_chapter == self.target_chapter:
                    # 修改日志，使其更清晰地表明已完成目标章节并停止
                    logging.info(f"已完成目标章节 {self.target_chapter} 的生成，停止生成后续章节。")
                    break

                chapter_retries = 0
                best_content_so_far = None
                best_consistency_score = -1.0 # 初始化为无效分数
                best_logic_passed = False
                retry_suggestions = "" # 初始化当前章节的重试建议

                while chapter_retries < max_retries:
                    try:
                        # 获取当前章节大纲
                        chapter_outline = self.chapter_outlines[self.current_chapter]
                        logging.info(f"开始生成第 {self.current_chapter + 1} 章: {chapter_outline.title} (尝试 {chapter_retries + 1}/{max_retries})")

                        # 将ChapterOutline对象转换为字典
                        outline_dict = {
                            "chapter_number": chapter_outline.chapter_number,
                            "title": chapter_outline.title,
                            "key_points": chapter_outline.key_points,
                            "characters": chapter_outline.characters,
                            "settings": chapter_outline.settings,
                            "conflicts": chapter_outline.conflicts
                        }

                        # --- 修改这里：合并外部提示词和重试提示词 ---
                        combined_extra_prompt = ""
                        # 1. 添加外部提示词 (如果存在)
                        if self.external_prompt:
                            combined_extra_prompt += f"\n**额外指令**：\n{self.external_prompt}\n"
                            logging.info(f"为第 {self.current_chapter + 1} 章添加外部提示词: {self.external_prompt[:100]}...") # 日志记录

                        # 2. 添加重试相关的提示词 (如果不是第一次尝试)
                        if chapter_retries > 0:
                            retry_prompt_header = f"\n注意：这是第{chapter_retries+1}次尝试生成。请务必严格遵循以下章节大纲要点："
                            retry_prompt_body = f"""
                            - 关键情节点：{chr(10).join(['  * ' + point for point in chapter_outline.key_points])}
                            - 涉及角色：{chr(10).join(['  * ' + character for character in chapter_outline.characters])}
                            - 场景：{chr(10).join(['  * ' + setting for setting in chapter_outline.settings])}
                            - 冲突：{chr(10).join(['  * ' + conflict for conflict in chapter_outline.conflicts])}
                            """
                            combined_extra_prompt += retry_prompt_header + retry_prompt_body
                            # 如果有上一轮的修改建议，添加到提示词中
                            if retry_suggestions:
                                combined_extra_prompt += f"\n\n**重要：请根据上次尝试失败后的以下建议进行修改和优化：**\n{retry_suggestions}\n"
                        # --- 合并结束 ---

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

                        # 获取章节内容 - 使用合并后的提示词
                        prompt = prompts.get_chapter_prompt(
                            outline=outline_dict,
                            references=self._format_references(outline_dict),
                            extra_prompt=combined_extra_prompt.strip(), # <--- 使用合并后的提示词
                            context_info=context_info
                        )
                        # logging.debug(f"最终传递给 get_chapter_prompt 的 extra_prompt:\n{combined_extra_prompt.strip()}") # 可选：调试日志

                        # 生成章节内容
                        try:
                            logging.info(f"正在生成第{self.current_chapter + 1} 章内容...")
                            current_content = self.content_model.generate(prompt) # 使用 current_content 存储当前尝试内容

                            # --- 验证与评分 ---
                            content_valid_for_saving = False # 标记当前内容是否可以直接保存
                            current_consistency_score = -1.0
                            current_logic_passed = False
                            current_attempt_suggestions = "" # 清空当前尝试的建议

                            # 基础内容验证 (例如长度)
                            if self._validate_chapter_content(current_content, chapter_outline):
                                # 一致性检查
                                consistency_report, needs_revision, current_consistency_score = self.consistency_checker.check_chapter_consistency(
                                    current_content, outline_dict, self.current_chapter, self.characters
                                )
                                # --- 添加日志：打印一致性分数 ---
                                logging.info(f"尝试 {chapter_retries + 1}: 一致性分数: {current_consistency_score:.2f}, 是否需要修正: {needs_revision}")
                                logging.debug(f"一致性报告: {consistency_report}") # 可以用 DEBUG 级别记录详细报告
                                # 如果需要修正，提取一致性建议
                                if needs_revision and consistency_report:
                                    match = re.search(r"\[修改建议\]:\s*(.*?)(?=\n\*\*\[修改必要性\]|\n\n|$)", consistency_report, re.DOTALL | re.IGNORECASE)
                                    if match:
                                        current_attempt_suggestions += f"一致性问题建议：\n{match.group(1).strip()}\n"

                                # 逻辑性验证
                                logic_report, logic_needs_revision = self.logic_validator.check_logic(current_content, outline_dict)
                                current_logic_passed = not logic_needs_revision
                                # --- 添加日志：打印逻辑验证结果 ---
                                logging.info(f"尝试 {chapter_retries + 1}: 逻辑验证通过: {current_logic_passed}, 是否需要修正: {logic_needs_revision}")
                                logging.debug(f"逻辑验证报告: {logic_report}") # 可以用 DEBUG 级别记录详细报告
                                # 如果需要修正，提取逻辑建议
                                if logic_needs_revision and logic_report:
                                     match = re.search(r"\[修改建议\]:\s*(.*?)(?=\n\*\*\[修改必要性\]|\n\n|$)", logic_report, re.DOTALL | re.IGNORECASE)
                                     if match:
                                         # 避免重复添加相同的建议标题
                                         prefix = "逻辑问题建议：\n" if not current_attempt_suggestions else ""
                                         current_attempt_suggestions += f"{prefix}{match.group(1).strip()}\n"


                                # --- 更新最佳尝试 ---
                                if current_consistency_score > best_consistency_score:
                                    best_consistency_score = current_consistency_score
                                    best_logic_passed = current_logic_passed
                                    best_content_so_far = current_content
                                    logging.info(f"尝试 {chapter_retries + 1} 获得新的最高一致性分数: {best_consistency_score:.2f}, 逻辑通过: {best_logic_passed}")
                                elif current_consistency_score == best_consistency_score and current_logic_passed and not best_logic_passed:
                                    # 一致性分数相同，但当前逻辑通过，而之前最佳未通过
                                    best_logic_passed = True
                                    best_content_so_far = current_content
                                    logging.info(f"尝试 {chapter_retries + 1} 一致性分数相同 ({best_consistency_score:.2f}) 但逻辑验证通过，更新最佳内容")


                                # --- 检查是否可以直接保存 ---
                                if not needs_revision and not logic_needs_revision:
                                     # 如果一致性和逻辑都通过，直接保存当前内容并结束重试
                                     logging.info(f"尝试 {chapter_retries + 1} 内容通过所有验证，直接保存。")
                                     # 可选：一致性修正（如果需要，即使验证通过也可以运行修正）
                                     # if needs_revision:
                                     #    logging.info(f"第{self.current_chapter + 1} 章需要一致性修正，得分: {current_consistency_score}")
                                     #    current_content = self.consistency_checker.ensure_chapter_consistency(
                                     #        current_content, outline_dict, self.current_chapter, self.characters
                                     #    )

                                     # 重复文本验证 (可以放在保存前)
                                     prev_content = ""
                                     next_content = ""
                                     duplicate_report, duplicate_needs_revision = self.duplicate_validator.check_duplicates(
                                         current_content, prev_content, next_content
                                     )
                                     if duplicate_needs_revision:
                                         logging.warning(f"第{self.current_chapter + 1} 章重复文本验证失败: {duplicate_report}")

                                     # 保存章节
                                     self._save_chapter(self.current_chapter + 1, current_content)
                                     logging.info(f"第{self.current_chapter + 1} 章生成完成")

                                     # 更新进度
                                     self.current_chapter += 1
                                     self._save_progress()
                                     content_valid_for_saving = True # 标记成功
                                     break # 成功，跳出重试循环

                                else:
                                     logging.warning(f"尝试 {chapter_retries + 1} 未完全通过验证 (一致性修正: {needs_revision}, 逻辑修正: {logic_needs_revision})")
                                     # 保存当前尝试的建议，用于下一次重试
                                     retry_suggestions = current_attempt_suggestions

                            else:
                                logging.error(f"尝试 {chapter_retries + 1}: 第{self.current_chapter + 1} 章基础内容验证失败")
                                # 基础验证失败也可能产生建议（如果验证函数能提供），这里假设基础验证不产生建议
                                # 如果基础验证失败，也保存已有的建议（一致性/逻辑性）用于下次重试
                                retry_suggestions = current_attempt_suggestions

                            # 如果当前尝试未成功保存，增加重试次数
                            if not content_valid_for_saving:
                                chapter_retries += 1
                                # 重试前等待
                                if chapter_retries < max_retries:
                                     wait_time = 10 * (chapter_retries + 1)
                                     logging.info(f"等待 {wait_time} 秒后重试...")
                                     time.sleep(wait_time)

                        except (TimeoutError, asyncio.TimeoutError) as e:
                            logging.error(f"生成第{self.current_chapter + 1} 章时请求超时: {str(e)}")
                            # 超时也保存已有的建议，用于下次重试
                            retry_suggestions = current_attempt_suggestions
                            chapter_retries += 1
                            if chapter_retries < max_retries:
                                wait_time = 30 * (chapter_retries + 1)
                                logging.info(f"等待 {wait_time} 秒后重试...")
                                time.sleep(wait_time)
                        except Exception as e:
                            logging.error(f"生成第{self.current_chapter + 1} 章时出错: {str(e)}")
                             # 出错也保存已有的建议，用于下次重试
                            retry_suggestions = current_attempt_suggestions
                            chapter_retries += 1
                            if chapter_retries < max_retries:
                                wait_time = 30 * (chapter_retries + 1)
                                logging.info(f"等待 {wait_time} 秒后重试...")
                                time.sleep(wait_time)

                    except Exception as e:
                        logging.error(f"处理第{self.current_chapter + 1} 章时发生意外错误: {str(e)}")
                        # 出错也保存已有的建议，用于下次重试
                        retry_suggestions = current_attempt_suggestions
                        chapter_retries += 1
                        if chapter_retries < max_retries:
                            wait_time = 30 * (chapter_retries + 1)
                            logging.info(f"等待 {wait_time} 秒后重试...")
                            time.sleep(wait_time)

                # --- 重试循环结束 ---
                # 检查是否因为重试次数用尽而退出循环
                if chapter_retries >= max_retries:
                    logging.warning(f"已达到最大重试次数 ({max_retries})")
                    if best_content_so_far:
                        logging.warning(f"使用评分最高的尝试内容 (一致性: {best_consistency_score:.2f}, 逻辑通过: {best_logic_passed})")

                        # 可选：在保存最佳内容前再次进行一致性修正
                        # logging.info("尝试对最佳内容进行最终一致性修正...")
                        # best_content_so_far = self.consistency_checker.ensure_chapter_consistency(
                        #     best_content_so_far, outline_dict, self.current_chapter, self.characters
                        # )

                        # 保存评分最高的内容
                        self._save_chapter(self.current_chapter + 1, best_content_so_far)
                        logging.info(f"第{self.current_chapter + 1} 章已使用最佳尝试内容保存")
                        self.current_chapter += 1
                        self._save_progress()
                    else:
                        logging.error(f"所有 {max_retries} 次尝试均未生成有效内容或评分，无法保存第{self.current_chapter + 1} 章")
                        # 决定如何处理：是跳过本章还是停止？
                        # 这里选择跳过本章以避免卡住，但可能导致后续问题
                        logging.warning(f"跳过第 {self.current_chapter + 1} 章的生成")
                        self.current_chapter += 1
                        self._save_progress() # 仍然保存进度，避免下次从同一章开始

            logging.info("小说生成完成！")

        except Exception as e:
            logging.error(f"生成小说时发生错误: {str(e)}")
            raise

    def _validate_chapter_content(self, content: str, outline: ChapterOutline) -> bool:
        """验证章节内容是否符合要求 (使用 jieba 分词优化)"""
        try:
            # 检查内容长度
            if len(content) < 1000:  # 假设最少1000字
                logging.error("章节内容过短")
                return False

            # --- 使用 jieba 进行关键词提取 ---
            def extract_keywords_jieba(text):
                if jieba is None: # 如果 jieba 未安装，回退到简单方法
                    keywords_raw = re.sub(r'[，。！？；?"''【】《》（）\[\]{}、\s]+', ' ', text).strip()
                    return [k for k in keywords_raw.split() if len(k) > 1 and k not in ['的', '地', '得', '了', '和', '与', '或', '而']]

                # 使用 jieba 分词 (精确模式)
                seg_list = jieba.cut(text, cut_all=False)
                # 过滤掉单个字符和常见停用词 (可以根据需要扩展停用词列表)
                stopwords = {'的', '地', '得', '了', '和', '与', '或', '而', '在', '是', '了', '着', '将', '把', '被'}
                keywords = [word for word in seg_list if len(word) > 1 and word not in stopwords]
                # 去重保持顺序（可选）
                return list(dict.fromkeys(keywords))

            # --- 对章节内容进行分词 (只做一次) ---
            content_words = set() # 使用 set 以提高查找效率
            if jieba:
                content_seg_list = jieba.cut(content, cut_all=False)
                content_words = {word for word in content_seg_list if len(word) > 0} # 保留单字，因为内容中可能包含
            else: # Fallback if jieba not installed
                content_words_raw = re.sub(r'[，。！？；?"''【】《》（）\[\]{}、\s]+', ' ', content).strip()
                content_words = set(content_words_raw.split())


            # 检查是否包含关键情节点 (基于分词后的词语匹配)
            missing_points = []
            min_keyword_match_ratio = 0.3 # 降低阈值，比如30%的关键词在内容词中出现即可

            for point in outline.key_points:
                keywords = extract_keywords_jieba(point)
                if not keywords:
                    logging.warning(f"无法从关键情节点 '{point}' 提取有效关键词，视为未覆盖")
                    missing_points.append(point)
                    continue

                found_count = 0
                for k in keywords:
                    if k in content_words: # 在分词后的内容词集合中查找
                        found_count += 1
                    # else: # 可选：增加日志，查看哪些关键词未匹配
                    #    logging.debug(f"Keyword '{k}' from point '{point}' not found in content words.")


                if not keywords: # 避免除以零
                     actual_match_ratio = 0.0
                else:
                     actual_match_ratio = found_count / len(keywords)


                if actual_match_ratio < min_keyword_match_ratio:
                    missing_points.append(point)
                    logging.warning(
                        f"关键情节点 '{point}' 覆盖率不足: "
                        f"内容词中仅找到 {found_count}/{len(keywords)} ({actual_match_ratio:.2f}) 个分词关键词 "
                        f"(要求至少达到 {min_keyword_match_ratio:.2f})"
                    )

            if missing_points:
                max_missing_points_ratio = 0.75
                # 避免除以零
                if not outline.key_points:
                     missing_ratio = 0.0
                else:
                     missing_ratio = len(missing_points) / len(outline.key_points)

                if missing_ratio > max_missing_points_ratio:
                    logging.error(
                        f"严重缺少关键情节点覆盖: "
                        f"{len(missing_points)}/{len(outline.key_points)} ({missing_ratio:.2f}) 的情节点关键词匹配率低于 {min_keyword_match_ratio:.2f}, "
                        f"超过了允许的 {max_missing_points_ratio:.2f} 缺失比例)"
                    )
                    return False

            # --- 角色、场景、冲突的检查也可以类似地优化 (使用分词) ---

            # 检查是否包含主要角色 (基于分词)
            missing_chars = []
            for character in outline.characters:
                 # 直接检查角色名是否在内容词集合中，或者在原始内容中 (处理特殊名字)
                 if character not in content_words and character not in content:
                    # 可以添加更复杂的检查，比如只检查姓氏或名字
                    if len(character) > 1 and (character[0] in content_words or character[1:] in content_words):
                         continue
                    missing_chars.append(character)

            if missing_chars:
                # 避免除以零
                if not outline.characters:
                     missing_char_ratio = 0.0
                else:
                     missing_char_ratio = len(missing_chars) / len(outline.characters)

                if missing_char_ratio > 0.75: # 阈值可调
                    logging.error(f"严重缺少主要角色 ({len(missing_chars)}/{len(outline.characters)})")
                    return False

            # 检查是否包含场景描写 (基于分词，至少一个关键词匹配)
            missing_settings = []
            for setting in outline.settings:
                setting_keywords = extract_keywords_jieba(setting)
                if not setting_keywords: continue
                # 检查是否有任何一个场景关键词出现在内容词中
                if not any(k in content_words for k in setting_keywords):
                    missing_settings.append(setting)
                    logging.warning(f"可能缺少场景描写 '{setting}'，未在内容词中找到任何关键词: {setting_keywords}")


            if missing_settings:
                 # 如果完全没有匹配到任何场景的关键词，则失败
                 if len(missing_settings) == len(outline.settings) and outline.settings:
                      logging.error(f"完全缺少场景描写")
                      return False


            # 检查冲突描写 (基于分词，至少一个关键词匹配)
            missing_conflicts = []
            for conflict in outline.conflicts:
                conflict_keywords = extract_keywords_jieba(conflict)
                if not conflict_keywords: continue
                 # 检查是否有任何一个冲突关键词出现在内容词中
                if not any(k in content_words for k in conflict_keywords):
                    missing_conflicts.append(conflict)
                    logging.warning(f"可能缺少冲突描写 '{conflict}'，未在内容词中找到任何关键词: {conflict_keywords}")


            if missing_conflicts:
                 # 如果完全没有匹配到任何冲突的关键词，则失败
                 if len(missing_conflicts) == len(outline.conflicts) and outline.conflicts:
                      logging.error(f"完全缺少冲突描写")
                      return False


            # 所有检查都通过或在容忍范围内
            logging.info("章节内容基础验证通过 (使用 jieba 分词优化)。")
            return True

        except Exception as e:
            logging.error(f"验证章节内容时发生错误: {str(e)}")
            return False

    def _format_references(self, chapter_outline_dict: dict) -> dict:
        """格式化当前章节大纲的关键信息作为引用"""
        references = {
            'plot_references': [],
            'character_references': [],
            'setting_references': []
        }
        
        if chapter_outline_dict.get('key_points'):
            references['plot_references'] = chapter_outline_dict['key_points']
        if chapter_outline_dict.get('characters'):
            references['character_references'] = chapter_outline_dict['characters']
        if chapter_outline_dict.get('settings'):
            references['setting_references'] = chapter_outline_dict['settings']
        
        return references

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
