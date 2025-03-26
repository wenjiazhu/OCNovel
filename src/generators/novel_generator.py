import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_fixed
import dataclasses
import math # 导入 math 模块用于 ceil
import re # 导入 re 模块用于清理文件名

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
    def __init__(self, config: Dict, outline_model, content_model, knowledge_base):
        self.config = config
        self.outline_model = outline_model
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.characters: Dict[str, Character] = {}
        self.chapter_outlines: List[ChapterOutline] = []
        self.current_chapter = 0
        
        # 从配置中获取输出目录，**提前到这里定义**
        self.output_dir = config.get("output_dir", "data/output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.characters_file = os.path.join(self.output_dir, "characters.json") # 角色库文件路径
        
        self._setup_logging()
        self._load_progress()
        self._load_characters() # 加载角色库
    
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
                
        if os.path.exists(outline_file):
            with open(outline_file, 'r', encoding='utf-8') as f:
                outline_data = json.load(f)
                self.chapter_outlines = [
                    ChapterOutline(**chapter)
                    for chapter in outline_data
                ]
    
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
                for name, char in self.characters.items()
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
    
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate_chapter(self, chapter_idx: int, extra_prompt: str = "", original_content: str = "", prev_content: str = "", next_content: str = "") -> str:
        """生成章节内容"""
        outline = self.chapter_outlines[chapter_idx]
        
        logging.info(f"开始生成第 {chapter_idx + 1} 章内容")
        
        # 创建一个空的参考材料结构，避免使用知识库
        reference_materials = {
            "plot_references": [],
            "character_references": [],
            "setting_references": []
        }
        
        logging.info(f"第 {chapter_idx + 1} 章: 参考材料准备完成。开始生成章节内容...")
        review_result = None
        
        # 获取上一章摘要
        prev_summary = ""
        if chapter_idx > 0:
            summary_file = os.path.join(self.output_dir, "summary.json")
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summaries = json.load(f)
                        prev_chapter_num = str(chapter_idx)
                        if prev_chapter_num in summaries:
                            prev_summary = summaries[prev_chapter_num]
                            logging.info(f"已获取第 {chapter_idx} 章摘要用于参考")
                except Exception as e:
                    logging.error(f"读取上一章摘要失败: {str(e)}")
        
        # 获取下一章大纲
        next_outline = None
        if chapter_idx + 1 < len(self.chapter_outlines):
            next_outline = self.chapter_outlines[chapter_idx + 1]
            logging.info(f"已获取第 {chapter_idx + 2} 章大纲用于参考")
        
        # 构建上下文信息
        context_info = ""
        if prev_summary:
            context_info += f"""
            [上一章摘要]
            {prev_summary}
            """
        elif prev_content:  # 如果没有摘要，仍然使用原始内容
            context_info += f"""
            [上一章内容]
            {prev_content[:2000]}...（内容过长已省略）
            """
            
        if next_outline:
            context_info += f"""
            [下一章大纲]
            标题：{next_outline.title}
            关键剧情：{' '.join(next_outline.key_points)}
            涉及角色：{' '.join(next_outline.characters)}
            场景设定：{' '.join(next_outline.settings)}
            核心冲突：{' '.join(next_outline.conflicts)}
            """
        elif next_content:  # 如果没有大纲，仍然使用原始内容
            context_info += f"""
            [下一章内容]
            {next_content[:2000]}...（内容过长已省略）
            """
        
        if original_content:
            context_info += f"""
            [原章节内容]
            {original_content[:3000]}...（内容过长已省略）
            """
        
        # 创建提示词    
        chapter_prompt = self._create_chapter_prompt(outline, reference_materials, None)
        
        # 添加额外提示词和上下文信息
        if extra_prompt:
            chapter_prompt += f"\n\n[额外要求]\n{extra_prompt}"
            
        if context_info:
            chapter_prompt += f"\n\n[上下文信息]\n{context_info}"
            
        # 添加明确的连贯性指导
        chapter_prompt += f"""
        
        [连贯性要求]
        1. 请确保本章情节与上一章摘要中描述的情节有明确的连接
        2. 章节开头应自然承接上一章的结尾，避免跳跃感
        3. 章节结尾应为下一章大纲中的情节埋下伏笔
        4. 确保人物情感和行为的连续性，避免角色表现前后矛盾
        5. 时间线和场景转换要清晰流畅
        """
        
        try:
            chapter_content = self.content_model.generate(chapter_prompt)
            if not chapter_content or chapter_content.strip() == "":
                logging.error(f"第 {chapter_idx + 1} 章: 生成的内容为空")
                raise ValueError("生成的章节内容为空")
        except Exception as e:
            logging.error(f"第 {chapter_idx + 1} 章: 章节内容生成失败: {str(e)}")
            raise

        logging.info(f"第 {chapter_idx + 1} 章: 章节内容生成完成，字数: {self._count_chinese_chars(chapter_content)}...")
        target_length = self.config['chapter_length']
        
        try:
            chapter_content = self._adjust_content_length(chapter_content, target_length)
            logging.info(f"第 {chapter_idx + 1} 章: 字数调整完成，调整后字数: {self._count_chinese_chars(chapter_content)}")
        except Exception as e:
            logging.error(f"第 {chapter_idx + 1} 章: 字数调整失败: {str(e)}，使用原始内容继续")

        logging.info(f"第 {chapter_idx + 1} 章: 准备保存章节...")
        self._save_chapter(chapter_idx + 1, chapter_content, skip_character_update=True)

        logging.info(f"第 {chapter_idx + 1} 章内容生成完成")

        return chapter_content
    
    def generate_novel(self):
        """生成完整小说"""
        logging.info("开始生成小说")
        
        try:
            target_chapters = self.config['target_length'] // self.config['chapter_length']
            logging.info(f"目标章节数: {target_chapters}")

            # 如果大纲章节数不足，生成后续章节的大纲
            if len(self.chapter_outlines) < target_chapters:
                logging.info(f"当前大纲只有{len(self.chapter_outlines)}章，需要生成后续章节大纲以达到{target_chapters}章")
                try:
                    # 从novel_config中获取小说信息
                    novel_config = self.config.get('novel_config', {})
                    self.generate_outline(
                        novel_config.get('type', '玄幻'),
                        novel_config.get('theme', '修真逆袭'),
                        novel_config.get('style', '热血'),
                        continue_from_existing=True  # 设置为续写模式
                    )
                except Exception as e:
                    logging.error(f"生成大纲失败: {str(e)}，将使用现有大纲继续")
            
            # 记录成功和失败的章节
            success_chapters = []
            failed_chapters = []
            
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
                    self._save_chapter(chapter_idx + 1, chapter_content)
                    
                    # 更新进度
                    self.current_chapter = chapter_idx + 1
                    self._save_progress()
                    
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

    def _load_characters(self):
        """加载角色库"""
        logging.info("开始加载角色库...") # 添加日志：开始加载角色库
        if os.path.exists(self.characters_file):
            with open(self.characters_file, 'r', encoding='utf-8') as f:
                characters_data = json.load(f)
                logging.info(f"从文件中加载到角色数据: {characters_data}") # 添加日志：打印加载到的角色数据
                self.characters = {
                    name: Character(**data)
                    for name, data in characters_data.items()
                }
                # 加载旧的角色库时，如果缺少 sect 和 position 属性，则提供默认值
                for char in self.characters.values():
                    if not hasattr(char, 'sect'):
                        char.sect = "无门无派"
                    if not hasattr(char, 'position'):
                        char.position = "普通弟子"
        else:
            # 如果角色库文件不存在，则初始化为空
            self.characters = {}
            logging.info("角色库文件不存在，初始化为空角色库。") # 添加日志：角色库文件不存在

        logging.info("角色库加载完成。") # 添加日志：角色库加载完成

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
            for name, char in self.characters.items()
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
        # 实现长度调整逻辑
        # 此处仅为占位实现
        return content
    
    def _save_chapter(self, chapter_num: int, content: str, skip_character_update: bool = False):
        """保存章节文件，并可选择更新摘要"""
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

            # --- 可选：更新章节摘要 ---
            if not skip_character_update: # 复用这个标志，表示是否需要更新摘要
                self._update_summary(chapter_num, content)

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

            # 生成新摘要
            prompt = f"""
            请为以下章节内容生成一个200字以内的摘要，要求：
            1. 突出本章的主要情节发展
            2. 包含关键人物的重要行动
            3. 说明本章对整体剧情的影响
            4. 仅返回摘要正文，字数控制在200字以内

            章节内容：
            {content[:4000]}... (内容过长已截断)
            """
            new_summary = self.content_model.generate(prompt) # 假设 content_model 可用
            summaries[str(chapter_num)] = new_summary.strip()

            # 保存更新后的摘要
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summaries, f, ensure_ascii=False, indent=2)
            logging.info(f"已更新第 {chapter_num} 章摘要")

        except Exception as e:
            logging.error(f"更新第 {chapter_num} 章摘要时出错: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10)) # 添加重试机制
    def generate_outline(self, novel_type: str, theme: str, style: str, continue_from_existing: bool = False, batch_size: int = 10): # 减小默认 batch_size
        """生成或续写小说大纲"""
        logging.info(f"开始{'续写' if continue_from_existing else '生成'}小说大纲...")
        target_chapters = self.config['target_length'] // self.config['chapter_length']
        start_chapter_index = 0 # 索引起始为 0
        num_to_generate = target_chapters

        if continue_from_existing:
            start_chapter_index = len(self.chapter_outlines)
            num_to_generate = target_chapters - start_chapter_index
            logging.info(f"续写大纲：从第 {start_chapter_index + 1} 章开始，目标总章数 {target_chapters}，需要生成 {num_to_generate} 章。")
            if num_to_generate <= 0:
                logging.info("当前大纲章节数已达到或超过目标，无需生成新的大纲章节。")
                return
        else:
            logging.info(f"生成全新大纲：共 {target_chapters} 章。")
            self.chapter_outlines = [] # 如果不是续写，清空现有大纲

        # --- 上下文准备 ---
        context = f"小说基本信息：\n类型：{novel_type}\n主题：{theme}\n风格：{style}\n"
        # 可以考虑加入更多全局信息，例如主角设定、世界观等

        if continue_from_existing and self.chapter_outlines:
            context += "\n[已有大纲结尾部分]\n"
            # 包含最后几章（最多5章）的大纲作为上下文
            context_start_index = max(0, start_chapter_index - 5)
            for i in range(context_start_index, start_chapter_index):
                outline = self.chapter_outlines[i]
                context += f"第{outline.chapter_number}章 {outline.title}: 关键剧情点: {', '.join(outline.key_points)}; 涉及角色: {', '.join(outline.characters)};\n"
            logging.info("已添加已有大纲结尾部分到上下文。")

        # --- 分批生成循环 ---
        generated_count = 0
        total_batches = math.ceil(num_to_generate / batch_size)
        for batch_num in range(total_batches):
            current_batch_size = min(batch_size, num_to_generate - generated_count)
            current_start_chapter_num = start_chapter_index + generated_count + 1 # 章节号从1开始
            logging.info(f"--- 开始生成批次 {batch_num + 1}/{total_batches} (章节 {current_start_chapter_num} - {current_start_chapter_num + current_batch_size - 1}) ---")

            # --- 构建提示词 ---
            prompt = f"""{context}

请严格按照要求，基于以上小说信息和已有大纲（如果是续写），创作后续的小说大纲。

任务要求：
1.  生成从第 {current_start_chapter_num} 章开始的，共 {current_batch_size} 个章节的大纲。
2.  确保情节连贯，与已有大纲结尾部分自然衔接（如果是续写）。推动主线发展，引入新的冲突和看点。
3.  每章大纲必须包含以下字段：章节号 (chapter_number, 整数)，标题 (title, 字符串)，关键剧情点列表 (key_points, 字符串列表)，涉及角色列表 (characters, 字符串列表)，场景列表 (settings, 字符串列表)，核心冲突列表 (conflicts, 字符串列表)。
4.  严格按照以下 JSON 格式返回一个包含 {current_batch_size} 个章节大纲对象的列表。不要在 JSON 列表前后添加任何其他文字、解释或代码标记 (如 ```json ... ```)。

```json
[
  {{
    "chapter_number": {current_start_chapter_num},
    "title": "...",
    "key_points": ["...", "..."],
    "characters": ["...", "..."],
    "settings": ["...", "..."],
    "conflicts": ["...", "..."]
  }},
  // ... (如果 current_batch_size > 1, 继续添加后续章节对象)
]
```
"""
            try:
                # --- 调用 AI 模型 ---
                logging.debug(f"发送给 AI 的提示词 (部分):\n{prompt[:500]}...")
                response = self.outline_model.generate(prompt)
                logging.debug(f"从 AI 收到的原始响应 (部分):\n{response[:500]}...")

                # --- 解析响应 ---
                try:
                    # 尝试清理响应，去除可能的代码块标记和首尾空白
                    response = response.strip()
                    if response.startswith("```json"):
                        response = response[7:]
                    if response.endswith("```"):
                        response = response[:-3]
                    response = response.strip()

                    new_outlines_data = json.loads(response)
                    if not isinstance(new_outlines_data, list):
                        raise ValueError("AI 返回的不是 JSON 列表")

                    # --- 验证并添加大纲 ---
                    batch_added_count = 0
                    for i, outline_data in enumerate(new_outlines_data):
                        expected_chapter_num = current_start_chapter_num + i
                        # 基本结构验证
                        required_keys = ["chapter_number", "title", "key_points", "characters", "settings", "conflicts"]
                        if not isinstance(outline_data, dict) or not all(k in outline_data for k in required_keys):
                            logging.warning(f"批次 {batch_num + 1} 中第 {i+1} 个大纲数据结构不完整或格式错误，跳过: {outline_data}")
                            continue

                        # 章节号验证和修正
                        if not isinstance(outline_data["chapter_number"], int) or outline_data["chapter_number"] != expected_chapter_num:
                            logging.warning(f"批次 {batch_num + 1} 中第 {i+1} 个大纲章节号错误或类型错误 (应为 {expected_chapter_num}，实际为 {outline_data.get('chapter_number')})，尝试修正...")
                            outline_data["chapter_number"] = expected_chapter_num

                        # 列表字段验证和修正
                        list_keys = ["key_points", "characters", "settings", "conflicts"]
                        for key in list_keys:
                            if not isinstance(outline_data[key], list):
                                logging.warning(f"章节 {expected_chapter_num} 大纲的 '{key}' 字段不是列表 (实际类型: {type(outline_data[key])})，尝试修正...")
                                # 简单处理：如果是字符串，放入列表中；否则设为空列表
                                outline_data[key] = [outline_data[key]] if isinstance(outline_data[key], str) else []

                        # 标题验证
                        if not isinstance(outline_data["title"], str) or not outline_data["title"]:
                             logging.warning(f"章节 {expected_chapter_num} 大纲标题无效，使用默认标题。")
                             outline_data["title"] = f"第 {expected_chapter_num} 章（标题生成失败）"


                        try:
                            new_outline = ChapterOutline(**outline_data)
                            self.chapter_outlines.append(new_outline)
                            batch_added_count += 1
                        except Exception as e:
                            logging.error(f"根据解析数据创建 ChapterOutline 对象失败 (章节 {expected_chapter_num}): {e} 数据: {outline_data}")

                    logging.info(f"批次 {batch_num + 1}: 成功解析并添加了 {batch_added_count}/{current_batch_size} 个大纲章节。")
                    generated_count += batch_added_count

                    # 如果该批次未能成功添加任何章节，可能需要停止
                    if batch_added_count == 0:
                         logging.error(f"批次 {batch_num + 1} 未能成功添加任何章节，停止后续大纲生成。请检查 AI 响应或提示词。")
                         break # 停止生成

                except json.JSONDecodeError as e:
                    logging.error(f"批次 {batch_num + 1}: 解析AI返回的大纲JSON失败: {e}\n原始响应 (部分): {response[:500]}...")
                    # 可以选择跳过此批次或停止，这里选择停止
                    break
                except ValueError as e:
                    logging.error(f"批次 {batch_num + 1}: AI返回的数据格式或内容错误: {e}\n原始响应 (部分): {response[:500]}...")
                    # 停止
                    break

            except Exception as e:
                logging.error(f"批次 {batch_num + 1}: 调用AI生成大纲时发生意外错误: {str(e)}")
                # 停止
                break # 发生其他错误也停止

        # --- 保存最终结果 ---
        final_chapter_count = len(self.chapter_outlines)
        logging.info(f"大纲生成/续写完成。当前总章节数: {final_chapter_count} (目标: {target_chapters})")
        if final_chapter_count > start_chapter_index or not continue_from_existing: # 只有在大纲确实被修改或全新生成时才保存
            logging.info("正在保存更新后的大纲及进度...")
            try:
                self._save_progress() # _save_progress 会保存大纲和角色等
                logging.info("大纲及进度保存完成。")
            except Exception as e:
                logging.error(f"保存大纲或进度时出错: {e}")
        else:
            logging.info("大纲未发生变化，无需保存。") 