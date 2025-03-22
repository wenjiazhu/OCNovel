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
            
    def _create_outline_prompt(self, novel_type: str, theme: str, style: str, start_chapter: int = 1, existing_chapters: List[ChapterOutline] = None, target_chapters: int = None) -> str:
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
                
                # 创建续写提示
                prompt = self._create_outline_prompt(
                    novel_type, 
                    theme, 
                    style,
                    start_chapter=current_count + 1,
                    existing_chapters=self.chapter_outlines[-3:],  # 只传递最后3章作为上下文
                    target_chapters=current_count + next_batch
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
        plot_results = self.knowledge_base.search(plot_query, k=3)
        materials["plot_references"] = [
            {
                "content": chunk.content,
                "context": self.knowledge_base.get_context(chunk)
            }
            for chunk, _ in plot_results
        ]
        
        # 搜索角色相关内容
        for character in outline.characters:
            char_results = self.knowledge_base.search(character, k=2)
            materials["character_references"].extend([
                {
                    "character": character,
                    "content": chunk.content,
                    "context": self.knowledge_base.get_context(chunk)
                }
                for chunk, _ in char_results
            ])
            
        # 搜索场景相关内容
        for setting in outline.settings:
            setting_results = self.knowledge_base.search(setting, k=2)
            materials["setting_references"].extend([
                {
                    "setting": setting,
                    "content": chunk.content,
                    "context": self.knowledge_base.get_context(chunk)
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
        2. 注意：字数统计只计算中文字符，不包括标点符号和英文字符
        3. 内容必须完整，包含开头、发展、高潮和结尾，但结尾不要进行总结性陈述或议论
        4. 情节必须符合逻辑，人物行为要有合理动机
        5. 场景描写要细致生动，**运用更具创意和想象力的语言，避免使用过于公式化和重复的表达**
        6. 人物性格要符合设定，**注重描写人物的内心活动和情感变化，使人物形象更加丰满**
        7. 必须与上一章结尾自然衔接
        8. 必须为下一章埋下伏笔或留下悬念
        9. 多描写，少议论，**尝试运用比喻、拟人等修辞手法，使描写更加生动形象**
        10. 多对话，少叙述，**对话要自然流畅，符合人物身份和性格**
        11. **请模仿人类写作的风格（如《牧神记》、《凡人修仙传》、《斗破苍穹》等作品的语言风格），避免明显的AI生成痕迹，例如：过度使用模板句式、逻辑跳跃、缺乏情感深度等**
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
        **12. 请分析上述 [参考材料] 的语言风格，并在创作正文时尝试模仿其风格。例如，如果参考材料的语言偏正式，则正文也使用正式的书面语；如果参考材料的语言比较口语化，则正文也采用相对轻松的口语风格。**
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
        # 检查字数
        if not self._check_length(content):
            logging.warning(f"章节 {chapter_idx + 1} 字数不符合要求")
            return False
            
        # 检查逻辑连贯性
        if not self._check_logic(content, chapter_idx):
            logging.warning(f"章节 {chapter_idx + 1} 逻辑验证失败")
            return False
            
        # 检查人物表现
        if not self._check_characters(content):
            logging.warning(f"章节 {chapter_idx + 1} 人物表现不符合设定")
            return False
            
        # 检查重复内容
        if not self._check_duplicates(content):
            logging.warning(f"章节 {chapter_idx + 1} 存在重复内容")
            return False
            
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
        {content}

        请逐项检查：
        1. 内容是否完整覆盖了大纲中的关键剧情点？
        2. 角色的行为是否符合其设定和动机？
        3. 场景描写是否符合设定？
        4. 核心冲突是否得到了合理展现？
        5. 情节发展是否自然流畅？

        对每一项进行评分（1-5分），3分及以上为及格。
        如果所有项目都及格，回复"通过"；
        如果总分达到15分及以上但有1-2项不及格，回复"基本通过"；
        否则指出具体问题。
        """
        
        response = self.content_model.generate(prompt)
        logging.debug(f"逻辑检查结果：{response}")
        
        # 检查响应中是否包含"通过"或"基本通过"
        response = response.strip()
        if "通过" in response:
            return True
        
        # 记录具体问题
        logging.warning(f"章节 {chapter_idx + 1} 逻辑问题：{response}")
        return False
        
    def _check_characters(self, content: str) -> bool:
        """检查人物表现是否符合设定"""
        for name, character in self.characters.items():
            if name in content:
                prompt = f"""
                请分析角色 {name} 在以下内容中的表现是否符合人物设定：
                
                角色设定：
                - 性格：{character.personality}
                - 目标：{character.goals}
                - 发展阶段：{character.development_stage}
                
                内容：
                {content}
                
                如果符合设定请回复"通过"，如果基本符合请回复"基本通过"，否则指出问题。
                """
                
                response = self.content_model.generate(prompt)
                logging.debug(f"角色 {name} 检查结果：{response}")
                if response.strip() not in ["通过", "基本通过"]:
                    return False
                    
        return True
        
    def _check_duplicates(self, content: str) -> bool:
        """检查重复内容"""
        # 实现重复内容检查逻辑
        return True
        
    def _update_character_states(self, content: str, outline: ChapterOutline):
        """更新角色状态"""
        logging.info(f"开始更新角色状态，当前角色库状态: {self.characters}") # 添加日志：角色状态更新开始时打印角色库状态
        for name in outline.characters:
            logging.info(f"开始更新角色: {name} 的状态，更新前状态: {self.characters.get(name)}") # 添加日志：开始更新角色状态前打印角色信息
            if name in self.characters:
                character = self.characters[name]

                prompt = f"""
                请详细分析角色 **{name}** 在本章节 **内容** 中的发展变化，并 **结构化** 输出分析结果。

                **章节内容：**
                {content}

                **角色 {name} 的原有状态：**
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

                **请分析角色在本章的行为、对话、心理活动等，判断角色在本章中在以下几个方面是否发生了变化：**

                1. **性格变化**:  角色在本章中是否展现出与原有性格不同的特点？例如，变得更加勇敢、冷静、冲动等。请总结性格变化，如果没有明显变化，请回答 "无明显变化"。
                2. **目标更新**:  角色在本章中是否产生了新的目标，或者原有目标是否发生了改变？例如，目标从 "提升修为" 变为 "为家族复仇"。请总结目标更新，如果没有目标更新，请回答 "无目标更新"。
                3. **关系变化**:  角色在本章中与哪些角色产生了新的关系，或者原有关系是否发生了改变（变得更亲密、更疏远、敌对等）？请总结关系变化，如果没有关系变化，请回答 "无关系变化"。
                4. **发展阶段调整**: 角色在本章中的经历是否导致其发展阶段发生变化？例如，从 "青年期" 进入 "中年期"，或者在心智、能力上更加成熟。请总结发展阶段调整，如果没有发展阶段调整，请回答 "无发展阶段调整"。
                5. **境界/等级提升**: 角色在本章中修为或能力是否有提升，境界或等级是否发生变化？请总结境界/等级提升情况，如果没有提升，请回答 "无境界/等级提升"。
                6. **新能力/法宝**: 角色在本章中是否获得了新的能力或法宝？请总结新能力/法宝，如果没有，请回答 "无新能力/法宝"。
                7. **门派/职务变化**: 角色在本章中是否加入了新的门派或者职务发生了变化？请总结门派/职务变化，如果没有，请回答 "无门派/职务变化"。

                **请务必按照以下 JSON 格式返回分析结果：**
                {
                  "性格变化": "...",
                  "目标更新": "...",
                  "关系变化": "...",
                  "发展阶段调整": "...",
                  "境界提升": "...",
                  "新能力/法宝": "...",
                  "门派/职务变化": "..."
                }
                **如果对应项无变化，请在 JSON 中对应的值设置为 "无"。**
                """

                analysis_result = self.content_model.generate(prompt)
                analysis = self._parse_character_analysis(analysis_result) # 解析分析结果
                self._update_character(name, analysis)
                
    def _update_character(self, name: str, analysis: str):
        """根据分析更新角色信息"""
        logging.info(f"开始根据分析结果更新角色: {name} 的信息，分析结果: {analysis}") # 添加日志：开始更新角色信息时打印分析结果
        if not analysis:
            logging.warning(f"未能解析角色 {name} 的状态分析结果")
            return

        character = self.characters[name]

        # 更新性格
        if "性格变化" in analysis and analysis["性格变化"] and analysis["性格变化"] != "无明显变化":
            character.temperament = analysis["性格变化"]
            logging.info(f"角色 {name} 性格更新为：{character.temperament}") # 添加日志：性格更新日志

        # 更新目标
        if "目标更新" in analysis and analysis["目标更新"] and analysis["目标更新"] != "无目标更新":
            character.goals.append(analysis["目标更新"]) #  示例：直接添加新的目标
            logging.info(f"角色 {name} 目标更新为：{character.goals}") # 添加日志：目标更新日志

        # 更新关系
        if "关系变化" in analysis and analysis["关系变化"] and analysis["关系变化"] != "无关系变化":
            relation_change = analysis["关系变化"]
            #  示例：假设关系变化描述包含了 "与[角色名]关系[变化类型]" 的信息
            #  例如 "与李四关系变得更亲密"
            #  解析 relation_change，提取角色名和变化类型，并更新 character.relationships
            logging.info(f"角色 {name} 关系更新为：{character.relationships}")

        # 更新发展阶段
        if "发展阶段调整" in analysis and analysis["发展阶段调整"] and analysis["发展阶段调整"] != "无发展阶段调整":
            character.development_stage = analysis["发展阶段调整"]
            logging.info(f"角色 {name} 发展阶段更新为：{character.development_stage}")

        # 更新境界/等级
        if "境界提升" in analysis and analysis["境界提升"] and analysis["境界提升"] != "无境界/等级提升":
            character.realm = analysis["境界提升"] #  示例：假设分析结果直接返回新的境界名称
            #  或者可以更细致地解析境界提升的描述，例如 "从炼气期提升到筑基期"
            logging.info(f"角色 {name} 境界提升至：{character.realm}")

        # 更新新能力/法宝
        if "新能力/法宝" in analysis and analysis["新能力/法宝"] and analysis["新能力/法宝"] != "无新能力/法宝":
            new_ability_treasure = analysis["新能力/法宝"]
            character.ability.extend([item.strip() for item in new_ability_treasure.split("、") if item.strip()]) # 示例：假设新能力/法宝以顿号分隔
            character.magic_treasure.extend([item.strip() for item in new_ability_treasure.split("、") if item.strip()]) # 同时添加到 ability 和 magic_treasure，根据实际情况调整
            logging.info(f"角色 {name} 获得新能力/法宝：{character.ability}, {character.magic_treasure}")

        # 更新门派/职务
        if "门派/职务变化" in analysis and analysis["门派/职务变化"] and analysis["门派/职务变化"] != "无门派/职务变化":
            character.sect = analysis["门派/职务变化"] # 示例：假设分析结果直接返回新的门派名称
            character.position = analysis["门派/职务变化"] #  同时更新门派和职务，根据实际情况调整
            logging.info(f"角色 {name} 门派/职务更新为：{character.sect}, {character.position}") # 添加日志：门派/职务更新日志

        #  ... 可以根据 JSON 分析结果中的其他字段，继续扩展角色属性的更新逻辑 ...

    def _parse_character_analysis(self, analysis_text: str) -> Dict:
        """解析角色状态分析结果"""
        analysis = {}
        try:
            analysis = json.loads(analysis_text) # 尝试解析 JSON 格式
            logging.debug(f"成功解析 JSON 格式的角色分析结果: {analysis}")
        except json.JSONDecodeError:
            logging.warning("模型返回的分析结果不是 JSON 格式，尝试文本行解析。")
            lines = analysis_text.strip().split('\n') # 回退到文本行解析
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    analysis[key.strip()] = value.strip()
            logging.debug(f"文本行解析的角色分析结果: {analysis}")
        return analysis

    def _save_chapter(self, chapter_num: int, content: str):
        """保存章节文件"""
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
        
        # 更新角色状态
        self._update_character_states(content, outline)
        
        # 生成并保存章节摘要
        try:
            self._generate_and_save_summary(chapter_num, content)
        except Exception as e:
            logging.error(f"生成章节摘要失败: {str(e)}")
        
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
            if "character" in ref:
                formatted.append(f"角色：{ref['character']}\n内容：{ref['content']}")
            elif "setting" in ref:
                formatted.append(f"场景：{ref['setting']}\n内容：{ref['content']}")
            else:
                formatted.append(f"内容：{ref['content']}")
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
    def generate_chapter(self, chapter_idx: int) -> str:
        """生成章节内容"""
        outline = self.chapter_outlines[chapter_idx]

        logging.info(f"开始生成第 {chapter_idx + 1} 章内容，当前角色库状态: {self.characters}") # 添加日志：章节生成开始时打印角色库状态

        # 收集参考材料
        reference_materials = self._gather_reference_materials(outline)

        # 生成章节
        review_result = None # 初始化 review_result 为 None
        if (chapter_idx + 1) % 5 == 0: # 判断是否是每5章一次的回顾章节
            review_result = self._review_summaries(chapter_idx + 1) # 获取回顾结果
        chapter_prompt = self._create_chapter_prompt(outline, reference_materials, review_result if (review_result and (chapter_idx + 1) <= self.current_chapter + 3) else None)
        chapter_content = self.content_model.generate(chapter_prompt)

        # 调整内容长度
        target_length = self.config['chapter_length']
        chapter_content = self._adjust_content_length(chapter_content, target_length)

        # 验证和修正
        if not self._validate_chapter(chapter_content, chapter_idx):
            raise ValueError("Chapter validation failed")

        # 更新角色状态
        self._update_character_states(chapter_content, outline)

        logging.info(f"第 {chapter_idx + 1} 章内容生成完成，角色状态更新完成。当前角色库状态: {self.characters}") # 添加日志：章节生成结束时打印角色库状态

        return chapter_content
    
    def generate_novel(self):
        """生成完整小说"""
        try:
            target_chapters = self.config['target_length'] // self.config['chapter_length']

            # 初始化角色库 (在生成小说前调用)
            self._initialize_characters()  # 添加：初始化角色

            # 如果大纲章节数不足，生成后续章节的大纲
            if len(self.chapter_outlines) < target_chapters:
                logging.info(f"当前大纲只有{len(self.chapter_outlines)}章，需要生成后续章节大纲以达到{target_chapters}章")
                # 从novel_config中获取小说信息
                novel_config = self.config.get('novel_config', {})
                self.generate_outline(
                    novel_config.get('type', '玄幻'),
                    novel_config.get('theme', '修真逆袭'),
                    novel_config.get('style', '热血'),
                    continue_from_existing=True  # 设置为续写模式
                )
            
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
                    
                except Exception as e:
                    logging.error(f"生成第 {chapter_idx + 1} 章时出错: {str(e)}")
                    # 保存当前进度
                    self._save_progress()
                    raise
                
            logging.info("小说生成完成")
            
        except Exception as e:
            logging.error(f"生成小说时出错: {str(e)}")
            raise 

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
        with open(self.characters_file, 'w', encoding='utf-8') as f:
            json.dump(characters_data, f, ensure_ascii=False, indent=2)
        logging.info("角色库保存完成。") # 添加日志：角色库保存完成 

    def _initialize_characters(self):
        """初始化角色库 (示例代码，需要您根据实际情况修改)"""
        logging.info("开始初始化角色库...")  # 添加日志

        # 创建一些示例角色
        self.characters = {
            "张三": Character(name="张三", role="主角", personality={"勇敢": 0.8, "正直": 0.7}, goals=["成为修真界的强者"], relationships={"李四": "朋友"}, development_stage="青年期", alignment="正派", realm="炼气期", level=5, cultivation_method="无", magic_treasure=["青云剑"], temperament="勇敢", ability=["剑术"], stamina=100, sect="无门无派", position="主角"),
            "李四": Character(name="李四", role="配角", personality={"聪明": 0.7, "狡猾": 0.5}, goals=["获得更多的修炼资源"], relationships={"张三": "朋友"}, development_stage="青年期", alignment="中立", realm="炼气期", level=5, cultivation_method="无", magic_treasure=["乾坤袋"], temperament="狡猾", ability=["储物"], stamina=100, sect="无门无派", position="配角"),
            "王五": Character(name="王五", role="反派", personality={"狡猾": 0.9, "残忍": 0.8}, goals=["统治整个修真界"], relationships={}, development_stage="中年期", alignment="反派", realm="金丹期", level=10, cultivation_method="无", magic_treasure=["血魔幡"], temperament="残忍", ability=["魔道"], stamina=150, sect="血魔宗", position="反派")
        }

        logging.info("角色库初始化完成。")  # 添加日志

        # 保存角色库
        self._save_characters() 