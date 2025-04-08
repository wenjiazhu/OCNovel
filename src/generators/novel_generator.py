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
        self.chapter_outlines = self._load_outline()
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
        characters_dict = {} # 使用局部变量
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

            except json.JSONDecodeError as e:
                logging.error(f"加载角色库文件 {self.characters_file} 时 JSON 解析失败: {e}")
                return None # 返回 None 表示加载失败
            except Exception as e:
                logging.error(f"加载角色库文件 {self.characters_file} 时发生未知错误: {e}", exc_info=True)
                return None # 返回 None 表示加载失败
        else:
            logging.info("角色库文件不存在，初始化为空角色库。")
            # characters_dict 保持为空 {}

        logging.info("角色库加载完成。")
        return characters_dict # 返回加载的字典（可能为空）

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

    def _create_basic_character(self, name: str):
        """创建基本角色，当无法从模型输出解析有效数据时使用"""
        logging.info(f"为 {name} 创建基本角色")
        self.characters[name] = Character(
            name=name,
            role="配角",
            personality={"平和": 0.5},
            goals=["暂无明确目标"],
            relationships={},
            development_stage="初次登场",
            alignment="中立",
            realm="凡人",
            level=1,
            cultivation_method="无",
            magic_treasure=[],
            temperament="平和",
            ability=[],
            stamina=100,
            sect="无门无派",
            position="普通人物"
        )
        logging.info(f"成功创建基本角色 {name}")
    
    # 这里需要添加其他必要的方法，如 _create_chapter_prompt, _count_chinese_chars, _adjust_content_length 等
    # 由于这些方法没在当前查看的代码中，我们需要补充
    
    def _create_chapter_prompt(self, outline: ChapterOutline, references: Dict, review_result: Optional[str] = None) -> str:
        """创建章节生成提示词"""
        # 实现提示词生成逻辑
        # 此处仅为占位实现
        return "请根据大纲生成章节内容"
    
    def _count_chinese_chars(self, text: str) -> int:
        """计算文本中的中文字符数量"""
        return sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
    
    def _adjust_content_length(self, content: str, target_length: int) -> str:
        """调整内容长度"""
        current_length = self._count_chinese_chars(content)
        if current_length >= target_length:
            return content

        # 如果当前字数不足目标字数的60%，需要扩充内容
        if current_length < target_length * 0.6:
            logging.info(f"当前字数({current_length})不足目标字数({target_length})的60%，开始扩充内容...")
            
            expansion_prompt = f"""
            请扩充以下小说章节内容，要求：
            1. 保持原有情节和风格不变
            2. 在适当位置增加细节描写、人物心理活动或对话，使内容更丰富生动
            3. 确保扩充的内容与原文自然衔接，保持逻辑连贯
            4. **扩充后的总字数应尽可能接近 {target_length} 字，请避免大幅超过此目标。**
            
            原文内容：
            {content}
            """
            
            logging.debug(f"Expansion prompt (first 300 chars): {expansion_prompt[:300]}")
            try:
                logging.info("Calling content model for expansion...")
                start_time = time.time()
                logging.debug("Calling content_model.generate for expansion...")
                expanded_content = self.content_model.generate(expansion_prompt)
                logging.debug("Expansion content generation finished.")
                end_time = time.time()
                expanded_length = self._count_chinese_chars(expanded_content)
                logging.info(f"Content model expansion finished in {end_time - start_time:.2f} seconds. Expanded length: {expanded_length}")
                
                # --- 修改：移除截断逻辑，只保留警告 ---
                max_allowed_length = target_length * 1.2 
                if expanded_length > max_allowed_length:
                    # 只记录警告，不再截断
                    logging.warning(f"扩写后字数({expanded_length})显著超过目标({target_length})，超过了{max_allowed_length}字的上限。将保留扩写后的完整内容。")
                    
                # 检查扩写后是否仍然严重不足 (保留)
                elif expanded_length < target_length * 0.6:
                    logging.warning(f"Expansion attempt resulted in insufficient length ({expanded_length}/{target_length}). Model might not be following instructions or hitting limits.")
                
                return expanded_content
                # --- 修改结束 ---

            except (TimeoutError, asyncio.TimeoutError) as e: 
                logging.error(f"内容扩充请求超时: {str(e)}，将返回原始内容。")
                return content
            except KeyError as e:
                logging.error(f"内容扩充时捕获到 KeyError: {e}", exc_info=True)
                return content
            except Exception as e:
                logging.error(f"内容扩充失败：{str(e)}，返回原始内容", exc_info=True)
                return content
        
        return content
    
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate_chapter(self, 
                         chapter_idx: int, 
                         extra_prompt: str = "", 
                         original_content: str = "", 
                         prev_content: str = "", 
                         next_content: str = "",
                         prev_summaries: str = "", # 新增参数
                         next_summaries: str = ""   # 新增参数
                         ) -> str:
        """生成章节内容"""
        logging.debug(f"Start generate_chapter for index {chapter_idx}. self.characters is: {type(self.characters)}") 
        outline = self.chapter_outlines[chapter_idx]
        
        logging.info(f"开始生成第 {chapter_idx + 1} 章内容")
        
        # 创建一个空的参考材料结构，避免使用知识库
        reference_materials = {
            "plot_references": [],
            "character_references": [],
            "setting_references": []
        }
        
        logging.info(f"第 {chapter_idx + 1} 章: 参考材料准备完成。开始生成章节内容...")
        
        # --- 修改：优先使用传入的摘要信息 ---
        # 获取上一章摘要 (如果未传入，尝试从文件加载)
        if not prev_summaries and chapter_idx > 0:
            summary_file = os.path.join(self.output_dir, "summary.json")
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summaries = json.load(f)
                        prev_chapter_num_str = str(chapter_idx) # 上一章是 chapter_idx，因为 idx 是 0-based
                        if prev_chapter_num_str in summaries:
                            prev_summaries = summaries[prev_chapter_num_str] # 使用加载的摘要
                            logging.info(f"从文件加载了第 {chapter_idx} 章摘要用于参考")
                except Exception as e:
                    logging.error(f"读取上一章摘要失败: {str(e)}")
        elif prev_summaries:
             logging.info(f"使用了传入的 {len(prev_summaries.splitlines())} 个前续章节摘要。")


        # 获取下一章大纲
        next_outline = None
        if chapter_idx + 1 < len(self.chapter_outlines):
            next_outline = self.chapter_outlines[chapter_idx + 1]
            logging.info(f"已获取第 {chapter_idx + 2} 章大纲用于参考")
        
        # 构建上下文信息 (优先使用摘要)
        context_info = ""
        if prev_summaries:
            context_info += f"""
            [前续章节摘要]
            {prev_summaries}
            """
        elif prev_content:  # 如果没有摘要，仍然使用原始内容
            context_info += f"""
            [上一章内容]
            {prev_content[:2000]}...（内容过长已省略）
            """
            
        if next_summaries:
             context_info += f"""
             [后续章节摘要]
             {next_summaries}
             """
        elif next_outline:
            context_info += f"""
            [下一章大纲]
            标题：{next_outline.title}
            关键剧情：{' '.join(next_outline.key_points)}
            涉及角色：{' '.join(next_outline.characters)}
            场景设定：{' '.join(next_outline.settings)}
            核心冲突：{' '.join(next_outline.conflicts)}
            """
        elif next_content:  # 如果没有后续摘要或大纲，使用后续内容
            context_info += f"""
            [下一章内容]
            {next_content[:2000]}...（内容过长已省略）
            """
        
        if original_content:
            context_info += f"""
            [原章节内容参考]
            {original_content[:3000]}...（内容过长已省略）
            """
        
        # 使用 prompts 模块生成提示词
        # 将 ChapterOutline 对象转换为字典传递
        outline_dict = dataclasses.asdict(outline)
        chapter_prompt = prompts.get_chapter_prompt(
            outline=outline_dict,
            references=reference_materials,
            extra_prompt=extra_prompt,
            context_info=context_info # 传递更新后的上下文
        )
        
        try:
            logging.debug("Calling content_model.generate for initial content...")
            chapter_content = self.content_model.generate(chapter_prompt)
            logging.debug("Initial content generation finished.")
            if not chapter_content or chapter_content.strip() == "":
                logging.error(f"第 {chapter_idx + 1} 章: 生成的内容为空")
                raise ValueError("生成的章节内容为空")
        except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
            logging.error(f"第 {chapter_idx + 1} 章: 初始内容生成请求超时: {str(e)}")
            # 重试装饰器会处理重试，如果最终还是超时，错误会被重新抛出
            raise
        except KeyError as e:
            logging.error(f"第 {chapter_idx + 1} 章: 初始内容生成时捕获到 KeyError: {e}", exc_info=True)
            raise 
        except Exception as e:
            logging.error(f"第 {chapter_idx + 1} 章: 章节内容生成失败: {str(e)}")
            raise

        logging.info(f"第 {chapter_idx + 1} 章: 章节内容生成完成，字数: {self._count_chinese_chars(chapter_content)}...")
        target_length = self.config.novel_config.get("chapter_length", 2500) # 使用 .get() 并提供默认值

        # --- 添加日志：调用 _adjust_content_length 之前 ---
        logging.debug(f"[{chapter_idx + 1}] Calling _adjust_content_length...")
        try:
            chapter_content = self._adjust_content_length(chapter_content, target_length)
            # --- 添加日志：调用 _adjust_content_length 之后 ---
            logging.debug(f"[{chapter_idx + 1}] Finished _adjust_content_length.")
            logging.info(f"第 {chapter_idx + 1} 章: 字数调整完成，调整后字数: {self._count_chinese_chars(chapter_content)}")
        except Exception as e:
            # --- 添加日志：_adjust_content_length 异常 ---
            logging.error(f"[{chapter_idx + 1}] Exception during _adjust_content_length: {e}", exc_info=True)
            logging.error(f"第 {chapter_idx + 1} 章: 字数调整失败: {str(e)}，使用原始内容继续")

        # --- 根据配置进行验证 ---
        validation_config = self.config.generation_config["validation"]
        logging.debug(f"[{chapter_idx + 1}] Before validation block. Validation config: {validation_config}") # 确认配置

        if validation_config.get('check_logic', True):
            logging.info(f"第 {chapter_idx + 1} 章: 开始逻辑严密性验证...")
            logic_report, needs_logic_revision = self.logic_validator.check_logic(
                chapter_content=chapter_content,
                chapter_outline=outline_dict
            )
            if needs_logic_revision:
                logging.warning(f"第 {chapter_idx + 1} 章: 逻辑验证发现问题，开始修正...")
                # 生成修正提示词 (传递正确的 prev_summary)
                revision_prompt = prompts.get_chapter_revision_prompt(
                    original_content=chapter_content,
                    consistency_report=logic_report,
                    chapter_outline=outline_dict,
                    previous_summary=prev_summaries.splitlines()[-1] if prev_summaries else "", # 只用最近一个摘要
                    global_summary=""  # 暂时不需要全局摘要
                )
                try:
                    chapter_content = self.content_model.generate(revision_prompt)
                    logging.info(f"第 {chapter_idx + 1} 章: 逻辑问题修正完成")
                except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
                    logging.error(f"第 {chapter_idx + 1} 章: 逻辑问题修正请求超时: {str(e)}，将跳过本次修正。")
                except Exception as e:
                    logging.error(f"第 {chapter_idx + 1} 章: 逻辑问题修正失败: {str(e)}")
            
        if validation_config.get('check_consistency', True):
            logging.info(f"第 {chapter_idx + 1} 章: 开始内容一致性验证...")
            # 为 consistency_checker 调用添加更安全的处理
            try:
                # 确保传递的是字典，即使是空的
                characters_to_check = self.characters if isinstance(self.characters, dict) else {}
                chapter_content = self.consistency_checker.ensure_chapter_consistency(
                    chapter_content=chapter_content,
                    chapter_outline=outline_dict,
                    chapter_idx=chapter_idx,
                    characters=characters_to_check 
                )
            except KeyError as e:
                logging.error(f"KeyError during consistency check: {e}. Characters data might be incomplete or None.", exc_info=True)
                # 决定如何处理：可以跳过一致性检查，或者重新抛出错误
                # logging.warning("Skipping consistency check due to error.")
                raise # 暂时重新抛出以观察错误
            except Exception as e:
                logging.error(f"Unexpected error during consistency check: {e}", exc_info=True)
                raise # 暂时重新抛出
            
        if validation_config.get('check_duplicates', True):
            logging.info(f"第 {chapter_idx + 1} 章: 开始重复文字验证...")
            duplicate_report, needs_duplicate_revision = self.duplicate_validator.check_duplicates(
                chapter_content=chapter_content,
                prev_content=prev_content,
                next_content=next_content
            )
            if needs_duplicate_revision:
                logging.warning(f"第 {chapter_idx + 1} 章: 重复文字验证发现问题，开始修正...")
                # 生成修正提示词 (传递正确的 prev_summary)
                revision_prompt = prompts.get_chapter_revision_prompt(
                    original_content=chapter_content,
                    consistency_report=duplicate_report,
                    chapter_outline=outline_dict,
                    previous_summary=prev_summaries.splitlines()[-1] if prev_summaries else "", # 只用最近一个摘要
                    global_summary=""  # 暂时不需要全局摘要
                )
                try:
                    chapter_content = self.content_model.generate(revision_prompt)
                    logging.info(f"第 {chapter_idx + 1} 章: 重复文字问题修正完成")
                except (TimeoutError, asyncio.TimeoutError) as e: # 捕获超时错误
                    logging.error(f"第 {chapter_idx + 1} 章: 重复文字修正请求超时: {str(e)}，将跳过本次修正。")
                except Exception as e:
                    logging.error(f"第 {chapter_idx + 1} 章: 重复文字问题修正失败: {str(e)}")

        # 最终验证
        logging.debug(f"[{chapter_idx + 1}] Before final validation block.") # 确认执行到这里
        logging.info(f"第 {chapter_idx + 1} 章: 开始最终验证...")
        final_logic_report, final_logic_needs_revision = self.logic_validator.check_logic(
            chapter_content=chapter_content,
            chapter_outline=outline_dict
        )
        final_duplicate_report, final_duplicate_needs_revision = self.duplicate_validator.check_duplicates(
            chapter_content=chapter_content,
            prev_content=prev_content,
            next_content=next_content
        )
        
        if final_logic_needs_revision or final_duplicate_needs_revision:
            logging.warning(f"第 {chapter_idx + 1} 章: 最终验证未通过，但已达到最大修正次数，将使用当前版本")
        else:
            logging.info(f"第 {chapter_idx + 1} 章: 最终验证通过")

        # --- 添加日志：调用 _save_chapter 之前 ---
        logging.debug(f"[{chapter_idx + 1}] Calling _save_chapter...")
        logging.info(f"第 {chapter_idx + 1} 章: 准备保存章节...")
        try:
            self._save_chapter(chapter_idx + 1, chapter_content, skip_character_update=False)
             # --- 添加日志：调用 _save_chapter 之后 ---
            logging.debug(f"[{chapter_idx + 1}] Finished _save_chapter.")
        except Exception as e:
             # --- 添加日志：_save_chapter 异常 ---
            logging.error(f"[{chapter_idx + 1}] Exception during _save_chapter: {e}", exc_info=True)
            # 注意：原始代码在这里没有重新抛出异常，如果保存失败，函数仍会继续

        # --- 添加日志：返回之前 ---
        logging.debug(f"[{chapter_idx + 1}] Preparing to return chapter content.")
        logging.info(f"第 {chapter_idx + 1} 章内容生成完成") # 这是函数成功返回前的最后一条 INFO 日志

        return chapter_content
    
    def generate_novel(self):
        """生成完整小说"""
        logging.info("开始生成小说")
        
        try:
            target_chapters = self.config.novel_config["target_chapters"]
            logging.info(f"目标章节数: {target_chapters}")

            # 如果大纲章节数不足，生成后续章节的大纲
            if len(self.chapter_outlines) < target_chapters:
                logging.info(f"当前大纲只有{len(self.chapter_outlines)}章，需要生成后续章节大纲以达到{target_chapters}章")
                try:
                    # 从novel_config中获取小说信息
                    novel_config = self.config.novel_config
                    self.generate_outline(
                        novel_config.get("type", "玄幻"),
                        novel_config.get("theme", "修真逆袭"),
                        novel_config.get("style", "热血"),
                        mode='append' # 明确指定追加模式 (虽然是默认值，但更清晰)
                        # continue_from_existing=True 这个参数在 generate_outline 中不存在，移除
                    )
                except RetryError as retry_err: # 捕获 RetryError
                    # 记录 RetryError 本身以及导致重试失败的根本原因 (cause)
                    logging.error(f"生成大纲失败 (重试耗尽): {retry_err}. 根本原因: {retry_err.cause}", exc_info=True) 
                    logging.error("将使用现有大纲或空大纲继续...")
                except Exception as e: # 捕获其他可能的异常
                    # 记录其他类型的异常
                    logging.error(f"生成大纲时发生意外错误: {str(e)}", exc_info=True)
                    logging.error("将使用现有大纲或空大纲继续...")
            
            # 记录成功和失败的章节
            success_chapters = []
            failed_chapters = []
            
            # 在循环开始前添加日志，检查实际使用的值
            logging.info(f"准备进入章节生成循环: self.current_chapter = {self.current_chapter}, len(self.chapter_outlines) = {len(self.chapter_outlines)}")
            
            # 如果是续写模式且角色库为空，尝试从已有章节中提取角色信息
            if self.current_chapter > 0 and not self.characters:
                logging.info("续写模式下角色库为空，尝试从已有章节中提取角色信息...")
                self._extract_characters_from_existing_chapters()
            
            # 从当前章节开始生成
            for chapter_idx in range(self.current_chapter, len(self.chapter_outlines)):
                logging.info(f"正在生成第 {chapter_idx + 1} 章")
                
                try:
                    # 获取上一章摘要
                    prev_summary = ""
                    if chapter_idx > 0:
                        # 先检查是否已经生成了上一章
                        prev_chapter_file = os.path.join(self.output_dir, f"第{chapter_idx}章_{self.chapter_outlines[chapter_idx-1].title}.txt")
                        if os.path.exists(prev_chapter_file):
                            # 如果已经生成了上一章，获取其摘要
                            summary_file = os.path.join(self.output_dir, "summary.json")
                            if os.path.exists(summary_file):
                                with open(summary_file, 'r', encoding='utf-8') as f:
                                    summaries = json.load(f)
                                    if str(chapter_idx) in summaries:
                                        prev_summary = summaries[str(chapter_idx)]
                    
                    # 生成章节
                    chapter_content = self.generate_chapter(
                        chapter_idx,
                        prev_content=prev_summary  # 使用摘要而不是完整内容
                    )
                    
                    # 保存章节
                    self._save_chapter(chapter_idx + 1, chapter_content, skip_character_update=False)  # 确保更新角色信息
                    
                    # 更新进度
                    self.current_chapter = chapter_idx + 1
                    self._save_progress()  # 这会调用 _save_characters()
                    
                    logging.info(f"第 {chapter_idx + 1} 章生成完成")
                    success_chapters.append(chapter_idx + 1)
                    
                except Exception as e:
                    logging.error(f"生成第 {chapter_idx + 1} 章时出错: {str(e)}")
                    failed_chapters.append(chapter_idx + 1)
                    # 尝试保存当前进度
                    try:
                        self._save_progress()
                    except:
                        logging.error("保存进度失败")
                    
                    # 继续生成下一章，而不是中断整个过程
                    continue
                
            # 生成小说完成后的总结
            total_chapters = len(self.chapter_outlines)
            completed_chapters = len(success_chapters)
            failed_count = len(failed_chapters)
            
            completion_rate = completed_chapters / total_chapters * 100 if total_chapters > 0 else 0
            logging.info(f"小说生成完成。总章节数: {total_chapters}，成功生成: {completed_chapters}，" 
                        f"失败: {failed_count}，完成率: {completion_rate:.2f}%")
            
            if failed_chapters:
                logging.info(f"失败的章节: {failed_chapters}")
                
            return {
                "success": True,
                "total_chapters": total_chapters,
                "completed_chapters": completed_chapters,
                "failed_chapters": failed_chapters,
                "completion_rate": completion_rate
            }
            
        except Exception as e:
            logging.error(f"生成小说过程中发生严重错误: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10)) # 添加重试机制
    def generate_outline(self, novel_type: str, theme: str, style: str,
                         mode: str = 'append', # 'append' (追加) or 'replace' (替换)
                         replace_range: Optional[Tuple[int, int]] = None, # (start_chap_num, end_chap_num) for replace mode
                         extra_prompt: Optional[str] = None, # 新增：用户额外提示词
                         batch_size: int = 10): # 减小默认 batch_size
        """生成或续写/替换小说大纲"""
        logging.info(f"开始 {mode} 小说大纲...")
        target_chapters = self.config.novel_config["target_chapters"]
        start_chapter_index = 0 # 索引起始为 0
        num_to_generate = 0

        # --- 根据模式确定起始索引和生成数量 ---
        if mode == 'append':
            start_chapter_index = len(self.chapter_outlines)
            num_to_generate = target_chapters - start_chapter_index
            logging.info(f"追加大纲：从第 {start_chapter_index + 1} 章开始，目标总章数 {target_chapters}，需要生成 {num_to_generate} 章。")
            if num_to_generate <= 0:
                logging.info("当前大纲章节数已达到或超过目标，无需追加。")
                return
            context_start_index = max(0, start_chapter_index - 5) # 上下文取追加点之前的
        elif mode == 'replace':
            if replace_range is None or len(replace_range) != 2:
                logging.error("替换模式需要提供有效的 replace_range=(start_chap_num, end_chap_num)")
                return
            start_chap_num, end_chap_num = replace_range
            # 检查范围是否在现有大纲内
            if not (1 <= start_chap_num <= end_chap_num <= len(self.chapter_outlines)):
                 logging.error(f"无效的替换范围: {replace_range}。当前总章数: {len(self.chapter_outlines)}")
                 return

            start_chapter_index = start_chap_num - 1 # 转换为 0-based index
            num_to_generate = end_chap_num - start_chap_num + 1
            logging.info(f"替换大纲：范围 {start_chap_num}-{end_chap_num} (索引 {start_chapter_index}-{start_chapter_index + num_to_generate - 1}，共 {num_to_generate} 章)。")
            context_start_index = max(0, start_chapter_index - 5) # 上下文取替换范围之前的
        else:
            logging.error(f"无效的模式: {mode}。请使用 'append' 或 'replace'。")
            return

        # --- 上下文准备 ---
        context = f"小说基本信息：\n类型：{novel_type}\n主题：{theme}\n风格：{style}\n"
        if start_chapter_index > 0: # 无论是追加还是替换，只要不是从第一章开始，都需要上下文
            context += "\n[参考：之前的章节大纲结尾部分]\n"
            # 包含前面几章（最多5章）的大纲作为上下文
            actual_context_start = max(0, start_chapter_index - 5) # 确保不越界
            for i in range(actual_context_start, start_chapter_index):
                 # 健壮性检查：确保索引有效
                 if i < len(self.chapter_outlines):
                     outline = self.chapter_outlines[i]
                     context += f"第{outline.chapter_number}章 {outline.title}: 关键剧情点: {', '.join(outline.key_points)}; 涉及角色: {', '.join(outline.characters)};\n"
                 else:
                      logging.warning(f"尝试访问越界的大纲索引 {i}，跳过。")
            logging.info(f"已添加章节 {actual_context_start + 1} 到 {start_chapter_index} 的大纲到上下文。")

        # --- 分批生成循环 ---
        generated_outlines_batch = [] # 存储当前批次生成的所有新大纲
        total_batches = math.ceil(num_to_generate / batch_size)
        for batch_num in range(total_batches):
            # 计算当前批次应生成的数量和起始章节号
            current_generated_count = len(generated_outlines_batch)
            current_batch_size = min(batch_size, num_to_generate - current_generated_count)
            # 章节号是 1-based
            current_start_chapter_num = start_chapter_index + current_generated_count + 1

            if current_batch_size <= 0: # 如果已经生成足够数量，则跳出
                 break

            logging.info(f"--- 开始生成批次 {batch_num + 1}/{total_batches} (请求章节 {current_start_chapter_num} - {current_start_chapter_num + current_batch_size - 1}) ---")

            # --- 使用 prompts 模块生成提示词 ---
            prompt = prompts.get_outline_prompt(
                novel_type=novel_type,
                theme=theme,
                style=style,
                current_start_chapter_num=current_start_chapter_num,
                current_batch_size=current_batch_size,
                existing_context=context,
                extra_prompt=extra_prompt # 传递 extra_prompt
            )

            try:
                # --- 调用 AI 模型 ---
                logging.debug(f"发送给 AI 的提示词 (部分):\n{prompt[:500]}...")
                response = self.outline_model.generate(prompt)
                logging.debug(f"从 AI 收到的原始响应 (部分):\n{response[:500]}...")

                # --- 解析响应 ---
                try:
                    # 尝试清理响应
                    response = response.strip()
                    if response.startswith("```json"):
                        response = response[7:]
                    if response.endswith("```"):
                        response = response[:-3]
                    response = response.strip()

                    new_outlines_data = json.loads(response)
                    if not isinstance(new_outlines_data, list):
                        raise ValueError("AI 返回的不是 JSON 列表")

                    # --- 验证并添加到批处理结果列表 ---
                    batch_added_count = 0
                    for i, outline_data in enumerate(new_outlines_data):
                        # 预期章节号
                        expected_chapter_num = current_start_chapter_num + i
                        # 基本结构验证
                        required_keys = ["chapter_number", "title", "key_points", "characters", "settings", "conflicts"]
                        if not isinstance(outline_data, dict) or not all(k in outline_data for k in required_keys):
                            logging.warning(f"批次 {batch_num + 1} 中第 {i+1} 个大纲数据结构不完整或格式错误，跳过: {str(outline_data)[:200]}")
                            continue

                        # 章节号验证和修正
                        if not isinstance(outline_data.get("chapter_number"), int) or outline_data["chapter_number"] != expected_chapter_num:
                            actual_num = outline_data.get('chapter_number')
                            logging.warning(f"批次 {batch_num + 1} 中第 {i+1} 个大纲章节号与预期不符 (预期 {expected_chapter_num}，实际 {actual_num})，尝试修正...")
                            outline_data["chapter_number"] = expected_chapter_num

                        # 列表字段验证和修正 (确保是列表)
                        list_keys = ["key_points", "characters", "settings", "conflicts"]
                        for key in list_keys:
                            if key not in outline_data or not isinstance(outline_data[key], list):
                                logging.warning(f"章节 {expected_chapter_num} 大纲的 '{key}' 字段缺失或不是列表 (实际类型: {type(outline_data.get(key))})，尝试修正为空列表...")
                                outline_data[key] = []

                        # 标题验证 (确保是字符串且非空)
                        if not isinstance(outline_data.get("title"), str) or not outline_data["title"]:
                             logging.warning(f"章节 {expected_chapter_num} 大纲标题无效，使用默认标题。")
                             outline_data["title"] = f"第 {expected_chapter_num} 章（标题生成失败）"

                        try:
                            new_outline = ChapterOutline(**outline_data)
                            generated_outlines_batch.append(new_outline) # 添加到总列表
                            batch_added_count += 1
                        except Exception as e:
                            logging.error(f"根据解析数据创建 ChapterOutline 对象失败 (章节 {expected_chapter_num}): {e} 数据: {outline_data}")

                    logging.info(f"批次 {batch_num + 1}: 成功解析并添加了 {batch_added_count} 个大纲。")

                    # 如果该批次未能成功添加任何章节，并且请求的数量大于0，记录错误并可能停止
                    if batch_added_count == 0 and current_batch_size > 0:
                         logging.error(f"批次 {batch_num + 1} 未能成功添加任何章节，但请求数量为 {current_batch_size}。可能存在严重问题，停止后续大纲生成。")
                         break # 停止生成

                except json.JSONDecodeError as e:
                    logging.error(f"批次 {batch_num + 1}: 解析AI返回的大纲JSON失败: {e}\n原始响应 (部分): {response[:500]}...")
                    break # 停止
                except ValueError as e:
                    logging.error(f"批次 {batch_num + 1}: AI返回的数据格式或内容错误: {e}\n原始响应 (部分): {response[:500]}...")
                    break # 停止

                # (可选) 更新上下文，为下一批次准备 (如果需要基于上一批生成结果的话)
                # context += "\n[刚生成的批次摘要]...\n" # 示例

            except Exception as e:
                logging.error(f"批次 {batch_num + 1}: 调用AI生成大纲时发生意外错误: {str(e)}")
                break # 发生其他错误也停止

        # --- 处理生成结果 ---
        actual_generated_count = len(generated_outlines_batch)
        if actual_generated_count != num_to_generate:
            logging.warning(f"警告：请求生成 {num_to_generate} 个大纲，但实际只成功生成了 {actual_generated_count} 个。")
            # 替换模式下，数量不匹配则中止操作
            if mode == 'replace':
                logging.error("替换模式下，生成的大纲数量与请求不符，操作中止，未修改原大纲。")
                return # 不进行替换

        # --- 应用更改 ---
        if generated_outlines_batch: # 确保有新内容生成
            if mode == 'append':
                self.chapter_outlines.extend(generated_outlines_batch)
                logging.info(f"成功追加 {actual_generated_count} 个大纲。当前总数: {len(self.chapter_outlines)}")
            elif mode == 'replace':
                # 验证 generated_outlines_batch 中的章节号是否连续且与请求范围一致
                is_consistent = True
                for i, outline in enumerate(generated_outlines_batch):
                    if outline.chapter_number != start_chap_num + i:
                        logging.error(f"生成的第 {i+1} 个大纲章节号 ({outline.chapter_number}) 与预期 ({start_chap_num + i}) 不符。替换中止。")
                        is_consistent = False
                        break
                if not is_consistent:
                    return # 中止替换

                # 执行替换
                # 计算结束索引 (exclusive)
                end_replace_index = start_chapter_index + num_to_generate
                self.chapter_outlines = self.chapter_outlines[:start_chapter_index] + \
                                        generated_outlines_batch + \
                                        self.chapter_outlines[end_replace_index:]
                logging.info(f"成功替换章节 {start_chap_num}-{end_chap_num} (共 {actual_generated_count} 章) 的大纲。当前总章数: {len(self.chapter_outlines)}")

            # 保存结果
            logging.info("正在保存更新后的大纲及进度...")
            try:
                self._save_progress() # 保存大纲和进度
                logging.info("大纲及进度保存完成。")
            except Exception as e:
                logging.error(f"保存大纲或进度时出错: {e}", exc_info=True)
        else:
             logging.info("没有生成任何有效的新大纲，未做修改。")

    def _load_outline(self):
        """加载小说大纲"""
        logging.info("开始加载小说大纲...")
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    logging.info(f"从文件中加载到大纲数据: {outline_data}")
                    outlines = [
                        ChapterOutline(**chapter)
                        for chapter in outline_data
                    ]
                    logging.info(f"成功加载 {len(outlines)} 章大纲")
                    return outlines
            except Exception as e:
                logging.error(f"加载大纲文件时出错: {str(e)}")
                return []
        else:
            logging.info("大纲文件不存在，初始化为空大纲")
            return [] 

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
            except (TimeoutError, asyncio.TimeoutError) as e:
                logging.error(f"第 {chapter_num} 章: 发现新角色请求超时: {str(e)}，跳过新角色发现。")
            except Exception as e:
                logging.error(f"第 {chapter_num} 章: 发现新角色时出错: {str(e)}")

            # 再次检查新发现的角色是否在内容中出现
            for name in list(self.characters.keys()):
                if name in cleaned_content and name not in current_chapter_characters:
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
                
                # 验证一致性...
                if not self._verify_character_consistency(cleaned_content, current_chapter_characters):
                     logging.warning("角色信息与章节内容存在不一致，尝试进行修正...")
                     self._correct_character_inconsistencies(cleaned_content, current_chapter_characters)
                
                logging.info(f"第 {chapter_num} 章角色信息更新完成...")

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

    def _parse_new_characters(self, update_text: str):
        """解析新发现的角色信息"""
        try:
            current_character = None
            # 扩展过滤关键词列表
            filter_keywords = [
                "属性分析结果", "角色分析", "人物总结", "人物分析", 
                "角色总结", "分析结果", "总结如下", "我的分析", 
                "步骤", "请看", "分析步骤", "好的", "总结", 
                "通读文本", "角色识别", "属性提取", "格式化输出", 
                "检查与校对", "整理如下", "名称：", "如下", 
                "发现以下", "新角色", "##", "的修士", "的人",
                "首领", "散修", "分析", "总结", "说明",
                "介绍", "描述", "特征", "属性"
            ]
            
            # 正则表达式模式，用于识别可能的序号或列表标记
            import re
            number_pattern = re.compile(r'^\d+[\.\s、]|^第\d+步|^\d+\)|^\(\d+\)')
            # 正则表达式模式，用于识别描述性文本
            descriptive_pattern = re.compile(r'的$|者$|人$|修士$|首领$')
            
            for line in update_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 检测角色名行（以冒号结尾）
                if ':' in line or '：' in line:
                    char_name = line.split(':')[0].strip() if ':' in line else line.split('：')[0].strip()
                    
                    # 1. 过滤以特殊字符开头的名称
                    if char_name.startswith(('**', '##', '第')):
                        logging.warning(f"跳过以特殊字符开头的非角色名称: {char_name}")
                        continue
                    
                    # 2. 过滤包含关键词的名称
                    if any(keyword in char_name for keyword in filter_keywords):
                        logging.warning(f"跳过包含过滤关键词的非角色名称: {char_name}")
                        continue
                    
                    # 3. 过滤数字或序号开头的名称
                    if number_pattern.match(char_name):
                        logging.warning(f"跳过以数字或序号开头的非角色名称: {char_name}")
                        continue
                    
                    # 4. 过滤过长的名称
                    if len(char_name) > 15:
                        logging.warning(f"跳过过长的非角色名称: {char_name}")
                        continue
                    
                    # 5. 过滤描述性文本
                    if descriptive_pattern.search(char_name):
                        logging.warning(f"跳过描述性文本: {char_name}")
                        continue
                    
                    # 6. 过滤包含空格或特殊字符的名称
                    if len(char_name.split()) > 1:
                        logging.warning(f"跳过包含空格的非角色名称: {char_name}")
                        continue
                    
                    # 7. 检查是否为有效的中文名称（至少包含一个中文字符）
                    if not any('\u4e00' <= c <= '\u9fff' for c in char_name):
                        logging.warning(f"跳过不包含中文字符的名称: {char_name}")
                        continue
                    
                    current_character = char_name
                    if char_name not in self.characters:
                        logging.info(f"发现新角色: {char_name}，创建基本信息")
                        self._create_basic_character(char_name)
                    
        except Exception as e:
            logging.error(f"解析新角色信息时发生错误: {str(e)}")

    def _parse_character_update(self, update_text: str, chapter_num: int, current_chapter_characters: set = None):
        """解析角色更新信息，更新角色库"""
        current_character = None
        section = None
        characters_updated = set()
        
        for line in update_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 检测角色名行
            if ':' in line and '：' not in line and '├' not in line and '│' not in line and '└' not in line:
                char_name = line.split(':')[0].strip()
                # 只处理当前章节出现的角色
                if current_chapter_characters is not None and char_name not in current_chapter_characters:
                    current_character = None
                    continue
                current_character = char_name
                characters_updated.add(char_name)
            elif '：' in line and '├' not in line and '│' not in line and '└' not in line:
                char_name = line.split('：')[0].strip()
                # 只处理当前章节出现的角色
                if current_chapter_characters is not None and char_name not in current_chapter_characters:
                    current_character = None
                    continue
                current_character = char_name
                characters_updated.add(char_name)
                
            # 处理角色信息更新
            if current_character and current_character in self.characters:
                # 检测部分标记
                if line.startswith('├──物品:') or line.startswith('├──物品：'):
                    section = "items"
                    continue
                elif line.startswith('├──能力:') or line.startswith('├──能力：'):
                    section = "abilities"
                    continue
                elif line.startswith('├──状态'):
                    section = "status"
                    continue
                elif line.startswith('├──主要角色间关系网'):
                    section = "relationships"
                    continue
                elif line.startswith('├──触发或加深的事件') or line.startswith('└──触发或加深的事件'):
                    section = "events"
                    continue
                
                # 处理具体内容
                if section and (line.startswith('│  ├') or line.startswith('│  └') or line.startswith('└')):
                    char = self.characters[current_character]
                    line_content = line.split(':', 1)[-1].strip() if ':' in line else line.split('：', 1)[-1].strip()
                    
                    if section == "items" and line_content:
                        # 合并物品信息，避免重复
                        new_items = [item.strip() for item in line_content.split(',')]
                        existing_items = set(char.magic_treasure)
                        for item in new_items:
                            if item and item not in existing_items:
                                char.magic_treasure.append(item)
                    
                    elif section == "abilities" and line_content:
                        # 合并能力信息，避免重复
                        new_abilities = [ability.strip() for ability in line_content.split(',')]
                        existing_abilities = set(char.ability)
                        for ability in new_abilities:
                            if ability and ability not in existing_abilities:
                                char.ability.append(ability)
                    
                    elif section == "status":
                        if "身体状态" in line and line_content:
                            # 追加身体状态，用逗号分隔
                            if not char.realm or char.realm == "凡人" or char.realm == "无":
                                char.realm = line_content
                            elif line_content not in char.realm:
                                char.realm = f"{char.realm}, {line_content}"
                        
                        elif "心理状态" in line and line_content:
                            # 追加心理状态，用逗号分隔
                            if not char.development_stage or char.development_stage == "初次登场":
                                char.development_stage = line_content
                            elif line_content not in char.development_stage:
                                char.development_stage = f"{char.development_stage}, {line_content}"
                    
                    elif section == "relationships" and line_content:
                        rel_parts = line_content.split(':', 1) if ':' in line_content else line_content.split('：', 1)
                        if len(rel_parts) > 1:
                            rel_name = rel_parts[0].strip()
                            rel_type = rel_parts[1].strip()
                            # 如果已存在关系，追加新的描述
                            if rel_name in char.relationships:
                                existing_relation = char.relationships[rel_name]
                                if rel_type not in existing_relation:
                                    char.relationships[rel_name] = f"{existing_relation}, {rel_type}"
                            else:
                                char.relationships[rel_name] = rel_type
                    
                    elif section == "events" and line_content:
                        # 避免添加重复的目标/事件
                        if line_content and line_content not in char.goals:
                            char.goals.append(line_content)
        
        if characters_updated:
            logging.info(f"角色更新完成，更新了 {len(characters_updated)} 个角色: {', '.join(characters_updated)}")
        else:
            logging.warning("未更新任何角色信息")

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
    
    def _load_outline(self):
        """加载小说大纲"""
        logging.info("开始加载小说大纲...")
        outline_file = os.path.join(self.output_dir, "outline.json")
        
        if os.path.exists(outline_file):
            try:
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    logging.info(f"从文件中加载到大纲数据: {outline_data}")
                    outlines = [
                        ChapterOutline(**chapter)
                        for chapter in outline_data
                    ]
                    logging.info(f"成功加载 {len(outlines)} 章大纲")
                    return outlines
            except Exception as e:
                logging.error(f"加载大纲文件时出错: {str(e)}")
                return []
        else:
            logging.info("大纲文件不存在，初始化为空大纲")
            return [] 