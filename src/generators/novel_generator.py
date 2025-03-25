import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_fixed
import dataclasses

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
            
    def _create_outline_prompt(self, novel_type: str, theme: str, style: str, start_chapter: int = 1, existing_chapters: List[ChapterOutline] = None, target_chapters: int = None, plot_references: str = "") -> str:
        """创建大纲生成提示词"""
        if target_chapters is None:
            target_chapters = self.config['target_length'] // self.config['chapter_length']

        # 构建现有章节的概要
        existing_summary = ""
        if existing_chapters:
            existing_summary = "\n现有章节概要：\n"
            for chapter in existing_chapters:
                existing_summary += f"""
                第{chapter.chapter_number}章：{chapter.title}
                - 关键剧情：{' '.join(chapter.key_points)}
                - 涉及角色：{' '.join(chapter.characters)}
                - 场景设定：{' '.join(chapter.settings)}
                - 核心冲突：{' '.join(chapter.conflicts)}
                """

        # 获取情节参考材料
        reference_materials = self._gather_reference_materials(ChapterOutline(chapter_number=start_chapter, title="", key_points=[theme, novel_type], characters=[], settings=[], conflicts=[])) # 使用主题和类型作为关键词
        plot_references = self._format_references(reference_materials['plot_references'])

        if plot_references:
            existing_summary += f"""

        [情节参考]
        {plot_references}
        """

        return f"""
        请使用雪花创作法{f'续写第{start_chapter}章到第{target_chapters}章的' if start_chapter > 1 else '生成'}小说大纲。
        请严格按照以下格式输出：

        [基本信息]
        类型：{novel_type}
        主题：{theme}
        风格：{style}
        目标总字数：{self.config['target_length']}
        每章字数：{self.config['chapter_length']}
        当前起始章节：第{start_chapter}章
        目标结束章节：第{target_chapters}章

        {existing_summary}

        [创作要求]
        1. 使用三幕式结构
        2. 每个章节必须包含以下要素（请严格按照此格式）：
           第N章：章节标题
           - 关键剧情：剧情点1；剧情点2；剧情点3
           - 涉及角色：角色1、角色2、角色3
           - 场景设定：场景1；场景2；场景3
           - 核心冲突：冲突1；冲突2；冲突3

        3. 确保情节递进合理，与前面章节**和已生成大纲**保持连贯，**避免剧情重复**
        4. 角色弧光完整
        5. 世界观设定统一
        6. 每章字数控制在{self.config['chapter_length']}字左右
        7. 需要生成从第{start_chapter}章到第{target_chapters}章的大纲

        请生成这些章节的详细大纲，每个章节都必须包含上述所有要素。
        请确保输出格式严格遵循上述示例，每个章节都要有完整的四个要素。
        **请务必参考已有的章节大纲，避免生成重复或矛盾的剧情。**
        **生成的大纲情节需要紧密围绕小说主题和风格展开。**
        **请务必仔细分析 [情节参考] 中的内容，并将其融入到你生成的大纲情节中，确保新生成的大纲情节与参考情节有一定的关联性和相似性。**
        """

    def generate_outline(self, novel_type: str, theme: str, style: str, continue_from_existing: bool = False, batch_size: int = 20):
        """生成小说大纲"""
        if continue_from_existing and self.chapter_outlines:
            # 获取现有章节数和目标章节数
            existing_count = len(self.chapter_outlines)
            target_chapters = self.config['target_length'] // self.config['chapter_length']
            remaining_chapters = target_chapters - existing_count
            
            if remaining_chapters <= 0:
                logging.info("已达到目标章节数，无需继续生成")
                return self.chapter_outlines
            
            logging.info(f"需要继续生成 {remaining_chapters} 章")
            
            # 分批生成剩余章节
            while len(self.chapter_outlines) < target_chapters:
                current_count = len(self.chapter_outlines)
                next_batch = min(batch_size, target_chapters - current_count)
                logging.info(f"正在生成第 {current_count + 1} 到第 {current_count + next_batch} 章的大纲")
                
                # 创建续写提示,  传递情节参考
                prompt = self._create_outline_prompt(
                    novel_type,
                    theme,
                    style,
                    start_chapter=current_count + 1,
                    existing_chapters=self.chapter_outlines[-3:],  # 只传递最后3章作为上下文
                    target_chapters=current_count + next_batch,
                    plot_references=self._format_references(self._gather_reference_materials(ChapterOutline(chapter_number=current_count + 1, title="", key_points=[theme, novel_type], characters=[], settings=[], conflicts=[]))['plot_references'])
                )
                
                try:
                    outline_text = self.outline_model.generate(prompt)
                    if not outline_text or outline_text.strip() == "":
                        raise ValueError("模型返回的大纲文本为空")
                    
                    logging.info("成功生成大纲文本，开始解析...")
                    logging.debug(f"模型返回的大纲文本：\n{outline_text}")
                    
                    # 解析新章节并添加到现有大纲后面
                    new_chapters = self._parse_outline(outline_text)
                    # 调整新章节的编号
                    start_num = len(self.chapter_outlines) + 1
                    for i, chapter in enumerate(new_chapters):
                        chapter.chapter_number = start_num + i
                    self.chapter_outlines.extend(new_chapters)
                    
                    # 保存当前进度
                    self._save_progress()
                    
                    logging.info(f"成功添加 {len(new_chapters)} 个章节，当前总章节数：{len(self.chapter_outlines)}")
                    
                except Exception as e:
                    logging.error(f"生成批次大纲时出错: {str(e)}")
                    # 继续下一批次
                    continue
                
        else:
            # 创建全新大纲提示
            prompt = self._create_outline_prompt(novel_type, theme, style)
            
            try:
                outline_text = self.outline_model.generate(prompt)
                if not outline_text or outline_text.strip() == "":
                    raise ValueError("模型返回的大纲文本为空")
                
                logging.info("成功生成大纲文本，开始解析...")
                logging.debug(f"模型返回的大纲文本：\n{outline_text}")
                
                # 完全替换现有大纲
                self.chapter_outlines = self._parse_outline(outline_text)
                
            except Exception as e:
                logging.error(f"生成大纲时出错: {str(e)}")
                raise
            
        if not self.chapter_outlines:
            raise ValueError("解析后的大纲为空")
        
        # 保存大纲
        self._save_progress()
        
        return self.chapter_outlines
        
    def _parse_outline(self, outline_text: str) -> List[ChapterOutline]:
        """解析大纲文本"""
        chapters = []
        current_chapter = None
        lines = outline_text.strip().split('\n')
        
        # 记录原始文本以便调试
        logging.debug(f"开始解析大纲文本：\n{outline_text}")
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 跳过基本信息和创作要求部分
            if '[基本信息]' in line or '[创作要求]' in line:
                continue
                
            # 新章节开始
            if ('第' in line and ('章' in line or '回' in line)) or line.startswith('第') or '章：' in line:
                # 保存前一章节
                if current_chapter:
                    if self._validate_chapter_outline(current_chapter):
                        chapters.append(ChapterOutline(**current_chapter))
                    else:
                        logging.warning(f"章节 {current_chapter['chapter_number']} 数据不完整，将被跳过")
                
                try:
                    # 解析章节号和标题
                    chapter_num = len(chapters) + 1
                    if '：' in line:
                        title = line.split('：')[-1].strip()
                    elif '章' in line:
                        title = line.split('章')[-1].strip()
                    else:
                        title = line.strip()
                    
                    # 初始化新章节
                    current_chapter = {
                        'chapter_number': chapter_num,
                        'title': title,
                        'key_points': [],
                        'characters': [],
                        'settings': [],
                        'conflicts': []
                    }
                    logging.debug(f"开始解析第{chapter_num}章：{title}")
                except Exception as e:
                    logging.error(f"解析章节标题时出错：{line}")
                    logging.error(str(e))
                    continue
                
            elif current_chapter:
                try:
                    # 解析章节内容
                    if '关键剧情' in line:
                        points = line.split('：')[1].split('；')
                        current_chapter['key_points'] = [p.strip() for p in points if p.strip()]
                        logging.debug(f"解析到关键剧情：{current_chapter['key_points']}")
                    elif '涉及角色' in line:
                        chars = line.split('：')[1].split('、')
                        current_chapter['characters'] = [c.strip() for c in chars if c.strip()]
                        logging.debug(f"解析到涉及角色：{current_chapter['characters']}")
                    elif '场景设定' in line:
                        settings = line.split('：')[1].split('；')
                        current_chapter['settings'] = [s.strip() for s in settings if s.strip()]
                        logging.debug(f"解析到场景设定：{current_chapter['settings']}")
                    elif '核心冲突' in line:
                        conflicts = line.split('：')[1].split('；')
                        current_chapter['conflicts'] = [c.strip() for c in conflicts if c.strip()]
                        logging.debug(f"解析到核心冲突：{current_chapter['conflicts']}")
                except Exception as e:
                    logging.error(f"解析章节内容时出错：{line}")
                    logging.error(str(e))
                    continue
        
        # 添加最后一章
        if current_chapter:
            if self._validate_chapter_outline(current_chapter):
                chapters.append(ChapterOutline(**current_chapter))
            else:
                logging.warning("最后一章数据不完整，将被跳过")
        
        if not chapters:
            logging.error("未能解析出任何有效章节，原始文本：")
            logging.error(outline_text)
            raise ValueError("未能解析出任何有效章节")
        
        logging.info(f"成功解析出 {len(chapters)} 个章节")
        return chapters
        
    def _validate_chapter_outline(self, chapter: Dict) -> bool:
        """验证章节大纲数据的完整性"""
        required_fields = ['chapter_number', 'title', 'key_points', 'characters', 'settings', 'conflicts']
        
        # 检查所有必需字段是否存在且不为空
        for field in required_fields:
            if field not in chapter or not chapter[field]:
                logging.warning(f"章节 {chapter.get('chapter_number', '未知')} 缺少必需字段：{field}")
                return False
                
        # 检查列表字段是否至少包含一个有效元素
        list_fields = ['key_points', 'characters', 'settings', 'conflicts']
        for field in list_fields:
            if not any(item.strip() for item in chapter[field]):
                logging.warning(f"章节 {chapter['chapter_number']} 的 {field} 字段没有有效内容")
                return False
                
        return True
        
    def _gather_reference_materials(self, outline: ChapterOutline) -> Dict:
        """收集参考材料"""
        materials = {
            "plot_references": [],
            "character_references": [],
            "setting_references": []
        }
        
        # 搜索情节相关内容
        plot_query = " ".join(outline.key_points)
        plot_results = self.knowledge_base.search(plot_query, k=5)  # 增加搜索结果数量
        materials["plot_references"] = [
            {
                "content": chunk.content,
                "context": self.knowledge_base.get_context(chunk),
                "source": chunk.metadata.get("source", "未知来源")  # 添加来源信息
            }
            for chunk, _ in plot_results
        ]
        
        # 搜索角色相关内容
        for character in outline.characters:
            char_results = self.knowledge_base.search(character, k=3)  # 增加每个角色的搜索结果数量
            materials["character_references"].extend([
                {
                    "character": character,
                    "content": chunk.content,
                    "context": self.knowledge_base.get_context(chunk),
                    "source": chunk.metadata.get("source", "未知来源")  # 添加来源信息
                }
                for chunk, _ in char_results
            ])
            
        # 搜索场景相关内容
        for setting in outline.settings:
            setting_results = self.knowledge_base.search(setting, k=3)  # 增加每个场景的搜索结果数量
            materials["setting_references"].extend([
                {
                    "setting": setting,
                    "content": chunk.content,
                    "context": self.knowledge_base.get_context(chunk),
                    "source": chunk.metadata.get("source", "未知来源")  # 添加来源信息
                }
                for chunk, _ in setting_results
            ])
            
        return materials
        
    def _create_chapter_prompt(self, outline: ChapterOutline, references: Dict, review_result: Optional[str] = None) -> str:
        """创建章节生成提示词"""
        # 获取上一章和下一章的信息
        prev_chapter = None
        next_chapter = None
        chapter_idx = outline.chapter_number - 1
        
        if chapter_idx > 0:
            prev_chapter = self.chapter_outlines[chapter_idx - 1]
            
        if chapter_idx < len(self.chapter_outlines) - 1:
            next_chapter = self.chapter_outlines[chapter_idx + 1]
        
        # 构建上下文信息
        context_info = ""
        if prev_chapter:
            context_info += f"""
            [上一章信息]
            章节号：{prev_chapter.chapter_number}
            标题：{prev_chapter.title}
            关键剧情：{' '.join(prev_chapter.key_points)}
            结尾冲突：{' '.join(prev_chapter.conflicts)}
            """
            
        if next_chapter:
            context_info += f"""
            [下一章信息]
            章节号：{next_chapter.chapter_number}
            标题：{next_chapter.title}
            关键剧情：{' '.join(next_chapter.key_points)}
            开头设定：{' '.join(next_chapter.settings)}
            """
        
        prompt_content = f"""
        请基于以下信息创作小说章节，要求：
        1. 字数必须严格控制在{self.config['chapter_length']}个汉字左右（允许±20%的误差）
        2. 字数统计只计算中文字符，不包括标点符号和英文字符
        3. 内容必须完整，包含开头、发展、高潮和结尾，但结尾不要进行总结性陈述或议论
        4. 情节必须符合逻辑，人物行为要有合理动机
        5. 场景描写要细致生动，**运用更具创意和想象力的语言，避免使用过于公式化和重复的表达**
        6. 人物性格要符合设定，**注重描写人物的内心活动和情感变化，使人物形象更加丰满**
        7. 必须与上一章结尾自然衔接
        8. 必须为下一章埋下伏笔或留下悬念
        9. 多描写，少议论，**尝试运用比喻、拟人等修辞手法，使描写更加生动形象**
        10. 多对话，少叙述，**对话要自然流畅，符合人物身份和性格**
        11. 增强人物形象描写、对话描写（双人对话、三人对话），减少非必要的环境描写
        12. **请分析参考材料中不同作品的语言风格，选择最适合当前情节的表达方式。注意保持风格的一致性，避免不同风格的混杂。**
        13. 仅输出章节正文，不使用markdown格式。
        {context_info}
        
        [本章信息]
        章节号：{outline.chapter_number}
        标题：{outline.title}
        
        [关键要素]
        主要情节：{outline.key_points}
        涉及角色：{outline.characters}
        场景设定：{outline.settings}
        核心冲突：{outline.conflicts}
        
        [参考材料]
        情节参考：
        {self._format_references(references['plot_references'])}
        
        角色参考：
        {self._format_references(references['character_references'])}
        
        场景参考：
        {self._format_references(references['setting_references'])}
        
        请严格按照要求创作本章节内容，特别注意：
        1. 开头要自然承接上一章结尾的剧情
        2. 结尾要为下一章埋下伏笔或制造悬念
        3. 保持情节的连贯性和人物性格的一致性
        4. 分析每个参考材料的来源，选择最适合当前情节的写作风格
        5. 在保持风格一致的前提下，可以借鉴不同参考材料的优秀表达方式
        """
        
        # 判断 review_result 是否存在且不是 "内容正常"，如果是，则添加到 prompt_content 中
        if review_result and review_result.strip() != "内容正常":
            prompt_content += f"""

            [前文回顾与改进建议]
            {review_result}
            请在创作本章节时，参考以上回顾与建议，进行改进。
            """

        return prompt_content
        
    def _validate_chapter(self, content: str, chapter_idx: int) -> bool:
        """验证章节内容"""
        validation_passed = True
        logging.info(f"开始验证第 {chapter_idx + 1} 章内容...")
        
        # 检查字数
        if not self._check_length(content):
            logging.warning(f"章节 {chapter_idx + 1} 字数不符合要求，但将继续生成")
            validation_passed = False
            
        # 检查逻辑连贯性
        if not self._check_logic(content, chapter_idx):
            logging.warning(f"章节 {chapter_idx + 1} 逻辑验证失败，但将继续生成")
            validation_passed = False
            
        # 检查人物表现
        if not self._check_characters(content):
            logging.warning(f"章节 {chapter_idx + 1} 人物表现不符合设定，但将继续生成")
            validation_passed = False
            
        # 检查重复内容
        if not self._check_duplicates(content):
            logging.warning(f"章节 {chapter_idx + 1} 存在重复内容，但将继续生成")
            validation_passed = False
        
        if not validation_passed:
            logging.warning(f"章节 {chapter_idx + 1} 验证未完全通过，但仍然继续生成")
        else:
            logging.info(f"章节 {chapter_idx + 1} 验证全部通过")
            
        # 始终返回True，不中断生成流程
        return True
        
    def _count_chinese_chars(self, text: str) -> int:
        """计算文本中的中文字符数量"""
        return sum(1 for char in text if '\u4e00' <= char <= '\u9fff')

    def _check_length(self, content: str) -> bool:
        """检查章节字数"""
        target_length = self.config['chapter_length']
        actual_length = self._count_chinese_chars(content)
        
        # 计算与目标字数的偏差百分比
        deviation = abs(actual_length - target_length) / target_length * 100
        
        # 记录详细的字数信息
        logging.info(f"字数检查 - 目标：{target_length}，实际：{actual_length}，偏差：{deviation:.1f}%")
        
        # 如果偏差超过50%，返回False
        if deviation > 50:
            logging.warning(f"字数偏差过大 - 目标：{target_length}，实际：{actual_length}，偏差：{deviation:.1f}%")
            return False
        
        return True
        
    def _check_logic(self, content: str, chapter_idx: int) -> bool:
        """检查逻辑连贯性"""
        # 获取当前章节大纲
        outline = self.chapter_outlines[chapter_idx]
        
        prompt = f"""
        请分析以下内容的逻辑连贯性。

        章节大纲：
        - 标题：{outline.title}
        - 关键剧情：{' '.join(outline.key_points)}
        - 涉及角色：{' '.join(outline.characters)}
        - 场景设定：{' '.join(outline.settings)}
        - 核心冲突：{' '.join(outline.conflicts)}

        内容：
        {content[:2000]}...（内容过长已省略）

        请逐项检查：
        1. 内容是否完整覆盖了大纲中的关键剧情点？
        2. 角色的行为是否符合其设定和动机？
        3. 场景描写是否符合设定？
        4. 核心冲突是否得到了合理展现？
        5. 情节发展是否自然流畅？

        对每一项进行评分（1-5分），3分及以上为及格。
        如果所有项目都及格，回复"通过"；
        如果总分达到13分及以上但有1-2项不及格，回复"基本通过"；
        否则指出具体问题。
        """
        
        try:
            response = self.content_model.generate(prompt)
            logging.debug(f"逻辑检查结果：{response}")
            
            # 检查响应中是否包含"通过"或"基本通过"
            response = response.strip()
            if "通过" in response:
                logging.info(f"章节 {chapter_idx + 1} 逻辑检查通过")
                return True
            
            # 记录具体问题
            logging.warning(f"章节 {chapter_idx + 1} 逻辑问题：{response}")
            
            # 如果问题不严重，也允许通过
            if "问题不严重" in response or "整体较好" in response or "基本符合" in response:
                logging.info(f"章节 {chapter_idx + 1} 逻辑问题不严重，允许通过")
                return True
                
            return False
        except Exception as e:
            logging.error(f"章节 {chapter_idx + 1} 逻辑检查过程出错: {str(e)}")
            # 出错时默认通过，避免生成中断
            return True
        
    def _check_characters(self, content: str) -> bool:
        """检查人物表现是否符合设定"""
        # 限制检查的角色数量，避免过多调用API
        check_success = True
        characters_to_check = {name: char for name, char in self.characters.items() 
                            if name in content[:2000]}  # 只检查前2000字中出现的角色
        
        # 如果没有已知角色，直接返回通过
        if not characters_to_check:
            logging.info("没有已知角色需要检查，直接通过")
            return True
            
        # 限制检查的角色数量为最多3个
        if len(characters_to_check) > 3:
            logging.info(f"角色数量过多 ({len(characters_to_check)}个)，只检查前3个")
            characters_to_check = dict(list(characters_to_check.items())[:3])
            
        for name, character in characters_to_check.items():
            try:
                prompt = f"""
                简要分析角色 {name} 在以下内容中的表现是否符合人物设定：
                
                角色设定：
                - 性格：{character.temperament}
                - 目标：{character.goals[0] if character.goals else "未知"}
                - 发展阶段：{character.development_stage}
                
                内容（节选）：
                {content[:1500]}...（内容过长已省略）
                
                如果基本符合设定请回复"通过"或"基本通过"，否则指出主要问题。简明扼要回答即可。
                """
                
                response = self.content_model.generate(prompt)
                logging.debug(f"角色 {name} 检查结果：{response}")
                
                if "通过" in response or "符合" in response:
                    logging.info(f"角色 {name} 表现检查通过")
                else:
                    logging.warning(f"角色 {name} 表现检查不通过: {response}")
                    check_success = False
            except Exception as e:
                logging.error(f"检查角色 {name} 表现时出错: {str(e)}")
                # 出错时不影响整体结果
                continue
                    
        return check_success
        
    def _check_duplicates(self, content: str) -> bool:
        """检查重复内容"""
        # 实现重复内容检查逻辑
        return True
        
    def _update_character_states(self, content: str, outline: ChapterOutline):
        """更新角色状态"""
        logging.info(f"开始更新角色状态，当前角色库状态: {self.characters}")
        
        for name in outline.characters:
            logging.info(f"开始更新角色: {name} 的状态")
            
            # 如果角色不存在，则创建新角色
            if name not in self.characters:
                logging.info(f"发现新角色 {name}，正在创建...")
                # 分析角色在当前章节中的表现，生成初始属性
                prompt = f"""
                请分析以下内容中角色 {name} 的特征，并按照JSON格式返回角色属性：
                
                章节内容：
                {content}
                
                请分析并返回以下属性（JSON格式）：
                {{
                    "role": "主角/配角/反派",
                    "personality": {{"特征1": 0.8, "特征2": 0.6}},
                    "goals": ["目标1", "目标2"],
                    "relationships": {{"其他角色名": "关系描述"}},
                    "development_stage": "发展阶段",
                    "alignment": "正派/反派/中立",
                    "realm": "境界",
                    "level": "等级(数字)",
                    "cultivation_method": "功法",
                    "magic_treasure": ["法宝1", "法宝2"],
                    "temperament": "性格特征",
                    "ability": ["能力1", "能力2"],
                    "stamina": "体力值(数字)",
                    "sect": "门派",
                    "position": "职务"
                }}
                """
                
                try:
                    analysis = self.content_model.generate(prompt)
                    logging.debug(f"模型返回的角色分析原始结果: {analysis}")
                    
                    # 尝试从返回内容中提取JSON部分
                    json_start = analysis.find('{')
                    json_end = analysis.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        # 提取JSON部分
                        json_str = analysis[json_start:json_end]
                        try:
                            char_data = json.loads(json_str)
                            # 确保必需字段存在
                            required_fields = ["role", "personality", "goals", "relationships", "development_stage"]
                            missing_fields = [field for field in required_fields if field not in char_data]
                            
                            if missing_fields:
                                logging.warning(f"角色 {name} 数据缺少必需字段: {missing_fields}")
                                # 为缺失字段提供默认值
                                if "role" not in char_data:
                                    char_data["role"] = "配角"
                                if "personality" not in char_data:
                                    char_data["personality"] = {"平和": 0.5}
                                if "goals" not in char_data:
                                    char_data["goals"] = ["暂无明确目标"]
                                if "relationships" not in char_data:
                                    char_data["relationships"] = {}
                                if "development_stage" not in char_data:
                                    char_data["development_stage"] = "初次登场"
                            
                            # 确保数值类型字段正确
                            if "level" in char_data and not isinstance(char_data["level"], int):
                                try:
                                    char_data["level"] = int(char_data["level"])
                                except:
                                    char_data["level"] = 1
                            
                            if "stamina" in char_data and not isinstance(char_data["stamina"], int):
                                try:
                                    char_data["stamina"] = int(char_data["stamina"])
                                except:
                                    char_data["stamina"] = 100
                            
                            # 创建新的Character实例
                            self.characters[name] = Character(
                                name=name,
                                **char_data
                            )
                            logging.info(f"成功创建新角色 {name}: {char_data}")
                        except json.JSONDecodeError as je:
                            logging.error(f"解析角色 {name} 的JSON数据失败: {je}")
                            # 创建一个基本角色
                            self._create_basic_character(name)
                    else:
                        logging.warning(f"无法从模型输出中找到有效的JSON数据: {analysis}")
                        # 创建一个基本角色
                        self._create_basic_character(name)
                except Exception as e:
                    logging.error(f"创建角色 {name} 时出错: {str(e)}")
                    # 创建一个基本角色
                    self._create_basic_character(name)
                    continue
            
            # 更新现有角色状态
            character = self.characters[name]
            prompt = f"""
            请详细分析角色 {name} 在本章节内容中的发展变化，并结构化输出分析结果。

            章节内容：
            {content}

            角色 {name} 的原有状态：
            - 性格：{character.temperament}，详细性格特征：{character.personality}
            - 目标：{character.goals}
            - 发展阶段：{character.development_stage}
            - 现有关系：{character.relationships}
            - 境界：{character.realm}
            - 等级：{character.level}
            - 功法：{character.cultivation_method}
            - 法宝：{character.magic_treasure}
            - 能力：{character.ability}
            - 门派：{character.sect}
            - 职务：{character.position}

            请分析角色在本章的变化，并按照以下JSON格式返回：
            {{
                "性格变化": "变化描述或'无'",
                "目标更新": "新目标或'无'",
                "关系变化": "新关系或'无'",
                "发展阶段调整": "新阶段或'无'",
                "境界提升": "新境界或'无'",
                "新能力/法宝": "新能力或法宝列表或'无'",
                "门派/职务变化": "新门派职务或'无'"
            }}
            """
            
            try:
                analysis_result = self.content_model.generate(prompt)
                analysis = self._parse_character_analysis(analysis_result)
                self._update_character(name, analysis)
                logging.info(f"成功更新角色 {name} 的状态")
            except Exception as e:
                logging.error(f"更新角色 {name} 状态时出错: {str(e)}")
                continue
        
        # 保存更新后的角色库
        self._save_characters()

    def _update_character(self, name: str, analysis: Dict):
        """根据分析更新角色信息"""
        if not analysis:
            logging.warning(f"未能解析角色 {name} 的状态分析结果")
            return

        character = self.characters[name]
        
        # 更新性格
        if "性格变化" in analysis and analysis["性格变化"] and analysis["性格变化"] != "无":
            character.temperament = analysis["性格变化"]
            # 更新性格特征权重
            new_personality = {}
            for trait, weight in character.personality.items():
                if trait in analysis["性格变化"].lower():
                    weight = min(1.0, weight + 0.1)  # 增强相关特征
                new_personality[trait] = weight
            character.personality = new_personality
            logging.info(f"角色 {name} 性格更新为：{character.temperament}, 特征权重：{character.personality}")

        # 更新目标
        if "目标更新" in analysis and analysis["目标更新"] and analysis["目标更新"] != "无":
            if analysis["目标更新"] not in character.goals:
                character.goals.append(analysis["目标更新"])
            logging.info(f"角色 {name} 目标更新为：{character.goals}")

        # 更新关系
        if "关系变化" in analysis and analysis["关系变化"] and analysis["关系变化"] != "无":
            # 清理和标准化关系描述
            relation_text = analysis["关系变化"]
            
            # 移除不相关的文本
            if "期待" in relation_text:
                relation_text = relation_text.split("期待")[0].strip()
            
            # 标准化角色名称
            def standardize_name(name: str) -> str:
                # 移除常见的后缀
                suffixes = ["的", "了", "着", "过", "吗", "呢", "啊", "吧", "呀", "哦", "哈", "么"]
                for suffix in suffixes:
                    if name.endswith(suffix):
                        name = name[:-len(suffix)]
                return name.strip()
            
            # 处理关系描述
            relations = {}
            # 分割多个关系描述
            relation_parts = [part.strip() for part in relation_text.split("，") if part.strip()]
            
            for part in relation_parts:
                # 跳过不包含角色名的部分
                if not any(char in part for char in self.characters.keys()):
                    continue
                    
                # 尝试提取角色名和关系
                for other_name in self.characters.keys():
                    if other_name in part:
                        # 标准化角色名
                        std_name = standardize_name(other_name)
                        if std_name:
                            # 提取关系描述
                            relation = part.replace(other_name, "").strip()
                            if relation:
                                relations[std_name] = relation
                                break
            
            # 更新角色关系
            for other_name, relation in relations.items():
                # 如果关系描述合理，则更新
                if len(relation) > 2 and not any(x in relation for x in ["期待", "**", "：", "："]):
                    character.relationships[other_name] = relation
                    logging.info(f"角色 {name} 与 {other_name} 的关系更新为：{relation}")

        # 更新发展阶段
        if "发展阶段调整" in analysis and analysis["发展阶段调整"] and analysis["发展阶段调整"] != "无":
            character.development_stage = analysis["发展阶段调整"]
            logging.info(f"角色 {name} 发展阶段更新为：{character.development_stage}")

        # 更新境界和等级
        if "境界提升" in analysis and analysis["境界提升"] and analysis["境界提升"] != "无":
            old_realm = character.realm
            character.realm = analysis["境界提升"]
            # 境界提升时增加等级
            if old_realm != character.realm:
                character.level += 1
            logging.info(f"角色 {name} 境界提升至：{character.realm}，等级：{character.level}")

        # 更新能力和法宝
        if "新能力/法宝" in analysis and analysis["新能力/法宝"] and analysis["新能力/法宝"] != "无":
            new_items = [item.strip() for item in analysis["新能力/法宝"].split("、")]
            for item in new_items:
                if "法宝" in item or "宝物" in item:
                    if item not in character.magic_treasure:
                        character.magic_treasure.append(item)
                else:
                    if item not in character.ability:
                        character.ability.append(item)
            logging.info(f"角色 {name} 获得新能力/法宝：能力 {character.ability}，法宝 {character.magic_treasure}")

        # 更新门派和职务
        if "门派/职务变化" in analysis and analysis["门派/职务变化"] and analysis["门派/职务变化"] != "无":
            changes = analysis["门派/职务变化"].split("，")
            for change in changes:
                if "门派" in change:
                    character.sect = change.split("门派")[1].strip()
                if "职务" in change:
                    character.position = change.split("职务")[1].strip()
            logging.info(f"角色 {name} 门派/职务更新为：门派 {character.sect}，职务 {character.position}")

    def _parse_character_analysis(self, analysis_text: str) -> Dict:
        """解析角色状态分析结果"""
        analysis = {}
        try:
            # 尝试从返回内容中提取JSON部分
            json_start = analysis_text.find('{')
            json_end = analysis_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                # 提取JSON部分
                json_str = analysis_text[json_start:json_end]
                analysis = json.loads(json_str) # 尝试解析 JSON 格式
                logging.debug(f"成功解析 JSON 格式的角色分析结果: {analysis}")
            else:
                raise json.JSONDecodeError("未找到JSON格式数据", analysis_text, 0)
        except json.JSONDecodeError:
            logging.warning("模型返回的分析结果不是 JSON 格式，尝试文本行解析。")
            # 回退到文本行解析
            lines = analysis_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 检查常见的分隔符
                for separator in [':', '：', '-', '=']:
                    if separator in line:
                        parts = line.split(separator, 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        # 转换键名称
                        key_map = {
                            "性格变化": "性格变化",
                            "性格": "性格变化",
                            "目标更新": "目标更新",
                            "目标": "目标更新",
                            "关系变化": "关系变化",
                            "关系": "关系变化",
                            "发展阶段调整": "发展阶段调整",
                            "发展阶段": "发展阶段调整",
                            "境界提升": "境界提升",
                            "境界": "境界提升",
                            "新能力/法宝": "新能力/法宝",
                            "能力/法宝": "新能力/法宝",
                            "法宝": "新能力/法宝",
                            "能力": "新能力/法宝",
                            "门派/职务变化": "门派/职务变化",
                            "门派职务": "门派/职务变化",
                            "门派": "门派/职务变化",
                            "职务": "门派/职务变化"
                        }
                        
                        # 标准化键名
                        for std_key, mapped_key in key_map.items():
                            if std_key in key.lower():
                                key = mapped_key
                                break
                                
                        # 过滤无效值
                        if value.lower() in ["无", "none", "null", "nil", "没有变化", "没有", "没有改变"]:
                            value = "无"
                            
                        analysis[key] = value
                        break
                        
            logging.debug(f"文本行解析的角色分析结果: {analysis}")
            
            # 如果解析结果为空，添加默认值
            if not analysis:
                logging.warning("文本解析未能提取有效信息，使用默认值")
                analysis = {
                    "性格变化": "无",
                    "目标更新": "无", 
                    "关系变化": "无",
                    "发展阶段调整": "无",
                    "境界提升": "无",
                    "新能力/法宝": "无",
                    "门派/职务变化": "无"
                }
                
        return analysis

    def _save_chapter(self, chapter_num: int, content: str, skip_character_update: bool = False):
        """保存章节文件"""
        try:
            outline = self.chapter_outlines[chapter_num - 1]
            # 清理标题中的非法字符
            clean_title = "".join(c for c in outline.title if c.isalnum() or c in " -_")
            filename = f"第{chapter_num}章_{clean_title}.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 写入章节内容
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入章节标题
                f.write(f"第{chapter_num}章 {outline.title}\n\n")
                # 写入正文
                f.write(content)
                
            logging.info(f"已保存章节：{filename}")
            
            # 如果不跳过角色更新，则更新角色状态
            if not skip_character_update:
                try:
                    self._update_character_states(content, outline)
                except Exception as e:
                    logging.error(f"更新角色状态时出错: {str(e)}")
            
            # 生成并保存章节摘要（不管是否跳过角色更新）
            try:
                self._generate_and_save_summary(chapter_num, content)
            except Exception as e:
                logging.error(f"生成章节摘要失败: {str(e)}")
                
        except Exception as e:
            logging.error(f"保存章节 {chapter_num} 时出错: {str(e)}")
            # 尝试基本保存，确保内容不丢失
            try:
                backup_filepath = os.path.join(self.output_dir, f"第{chapter_num}章_备份.txt")
                with open(backup_filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                logging.info(f"已保存备份章节：{backup_filepath}")
            except Exception as backup_e:
                logging.error(f"保存备份章节也失败: {str(backup_e)}")

    def _generate_and_save_summary(self, chapter_num: int, content: str):
        """生成章节摘要并保存到summary.json"""
        summary_file = os.path.join(self.output_dir, "summary.json")
        
        # 生成摘要
        prompt = f"""
        请为以下章节内容生成一个200字以内的摘要，要求：
        1. 突出本章的主要情节发展
        2. 包含关键人物的重要行动
        3. 说明本章对整体剧情的影响
        4. 仅返回摘要正文，字数控制在200字以内
        
        章节内容：
        {content}
        """
        
        summary = self.content_model.generate(prompt)
        
        # 读取现有摘要
        summaries = {}
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                summaries = json.load(f)
        
        # 更新摘要
        summaries[str(chapter_num)] = summary
        
        # 保存摘要
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, ensure_ascii=False, indent=2)
            
        logging.info(f"已保存第{chapter_num}章摘要")
        
        # 每5章进行一次回顾
        if chapter_num % 5 == 0:
            self._review_summaries(chapter_num)
            
    def _review_summaries(self, current_chapter: int):
        """回顾前文摘要，检查剧情连贯性和主题一致性"""
        summary_file = os.path.join(self.output_dir, "summary.json")
        if not os.path.exists(summary_file):
            return
            
        # 读取所有摘要
        with open(summary_file, 'r', encoding='utf-8') as f:
            summaries = json.load(f)
            
        # 获取最近5章的摘要
        recent_summaries = []
        for i in range(max(1, current_chapter - 4), current_chapter + 1):
            if str(i) in summaries:
                recent_summaries.append(f"第{i}章：{summaries[str(i)]}")
                
        # 生成回顾提示
        prompt = f"""
        请分析最近5章的内容摘要，检查是否存在以下问题：
        1. 剧情是否重复
        2. 情节是否偏离主题
        3. 人物行为是否前后矛盾
        4. 故事节奏是否合理
        
        最近5章摘要：
        {' '.join(recent_summaries)}
        
        如果发现问题，请指出具体问题并提供改进建议。
        如果内容正常，请回复"内容正常"。
        """
        
        review_result = self.content_model.generate(prompt)
        logging.info(f"第{current_chapter}章回顾结果：{review_result}")
        
        # 如果发现问题，记录到日志
        if review_result.strip() != "内容正常":
            logging.warning(f"第{current_chapter}章回顾发现问题：{review_result}")
        
        return review_result
        
    def _format_references(self, references: List[Dict]) -> str:
        """格式化参考材料"""
        formatted = []
        for ref in references:
            source_info = f"[来源：{ref.get('source', '未知来源')}]"
            if "character" in ref:
                formatted.append(f"{source_info}\n角色：{ref['character']}\n内容：{ref['content']}")
            elif "setting" in ref:
                formatted.append(f"{source_info}\n场景：{ref['setting']}\n内容：{ref['content']}")
            else:
                formatted.append(f"{source_info}\n内容：{ref['content']}")
        return "\n\n".join(formatted)

    def _adjust_content_length(self, content: str, target_length: int) -> str:
        """调整内容长度"""
        current_length = self._count_chinese_chars(content)
        if current_length < 0.8 * target_length:
            logging.info(f"字数不足，需要扩充 - 目标：{target_length}，实际：{current_length}")
            # 内容太短，需要扩充
            prompt = f"""
            请在保持原有情节和风格的基础上，扩充以下内容，使其达到约{target_length}个汉字：
            
            {content}
            
            要求：
            1. 保持原有情节不变
            2. 增加细节描写和内心活动
            3. 扩充对话和场景
            4. 保持风格一致
            5. 注意：字数统计只计算中文字符，不包括标点符号和英文字符
            """
            return self.content_model.generate(prompt)
        elif current_length > 1.6 * target_length:
            logging.warning(f"字数超出，需要精简 - 目标：{target_length}，实际：{current_length}")
            return content # 直接返回原始内容，不再缩写
        else:
            logging.info(f"字数符合要求，无需调整 - 目标：{target_length}，实际：{current_length}")
            return content

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
        
        # 构建上下文信息
        context_info = ""
        if prev_content:
            context_info += f"""
            [上一章内容]
            {prev_content[:2000]}...（内容过长已省略）
            """
            
        if next_content:
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
                    # 生成章节
                    chapter_content = self.generate_chapter(chapter_idx)
                    
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