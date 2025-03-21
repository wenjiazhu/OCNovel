import os
import json
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_fixed

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
    
class NovelGenerator:
    def __init__(self, config: Dict, outline_model, content_model, knowledge_base):
        self.config = config
        self.outline_model = outline_model
        self.content_model = content_model
        self.knowledge_base = knowledge_base
        self.characters: Dict[str, Character] = {}
        self.chapter_outlines: List[ChapterOutline] = []
        self.current_chapter = 0
        
        # 从配置中获取输出目录
        self.output_dir = config.get("output_dir", "data/output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        self._setup_logging()
        self._load_progress()
        
    def _setup_logging(self):
        """设置日志"""
        log_file = os.path.join(self.output_dir, "generation.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
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

        3. 确保情节递进合理，与前面章节保持连贯
        4. 角色弧光完整
        5. 世界观设定统一
        6. 每章字数控制在{self.config['chapter_length']}字左右
        7. 需要生成从第{start_chapter}章到第{target_chapters}章的大纲

        请生成这些章节的详细大纲，每个章节都必须包含上述所有要素。
        请确保输出格式严格遵循上述示例，每个章节都要有完整的四个要素。
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
        
    def _create_chapter_prompt(self, outline: ChapterOutline, references: Dict) -> str:
        """创建章节生成提示词"""
        return f"""
        请基于以下信息创作小说章节，要求：
        1. 字数必须严格控制在{self.config['chapter_length']}字左右（允许±20%的误差）
        2. 内容必须完整，包含开头、发展、高潮和结尾
        3. 情节必须符合逻辑，人物行为要有合理动机
        4. 场景描写要细致生动
        5. 人物性格要符合设定
        
        [章节信息]
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
        
        请严格按照要求创作本章节内容。
        """
        
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
        
    def _check_length(self, content: str) -> bool:
        """检查章节字数"""
        target_length = self.config['chapter_length']
        actual_length = len(content)
        
        # 计算与目标字数的偏差百分比
        deviation = abs(actual_length - target_length) / target_length * 100
        
        # 记录详细的字数信息
        logging.info(f"字数检查 - 目标：{target_length}，实际：{actual_length}，偏差：{deviation:.1f}%")
        
        # 如果偏差超过30%，返回False
        if deviation > 30:
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
        for name in outline.characters:
            if name in self.characters:
                character = self.characters[name]
                
                # 分析角色在本章的发展
                prompt = f"""
                分析角色 {name} 在本章的发展变化：
                
                原有状态：
                - 性格：{character.personality}
                - 目标：{character.goals}
                - 发展阶段：{character.development_stage}
                
                本章内容：
                {content}
                
                请提供：
                1. 性格变化
                2. 目标更新
                3. 发展阶段调整
                """
                
                analysis = self.content_model.generate(prompt)
                self._update_character(name, analysis)
                
    def _update_character(self, name: str, analysis: str):
        """根据分析更新角色信息"""
        # 实现角色信息更新逻辑
        pass
        
    def _save_chapter(self, chapter_num: int, content: str):
        """保存章节文件"""
        outline = self.chapter_outlines[chapter_num - 1]
        filename = f"第{chapter_num}章_{outline.title}.txt"
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
        current_length = len(content)
        if current_length < 0.7 * target_length:
            # 内容太短，需要扩充
            prompt = f"""
            请在保持原有情节和风格的基础上，扩充以下内容，使其达到约{target_length}字：
            
            {content}
            
            要求：
            1. 保持原有情节不变
            2. 增加细节描写和内心活动
            3. 扩充对话和场景
            4. 保持风格一致
            """
            return self.content_model.generate(prompt)
        elif current_length > 1.3 * target_length:
            # 内容太长，需要精简
            prompt = f"""
            请在保持原有情节和风格的基础上，将以下内容精简到约{target_length}字：
            
            {content}
            
            要求：
            1. 保持主要情节不变
            2. 删除不必要的细节
            3. 保持关键对话和场景
            4. 保持风格一致
            """
            return self.content_model.generate(prompt)
        else:
            return content

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate_chapter(self, chapter_idx: int) -> str:
        """生成章节内容"""
        outline = self.chapter_outlines[chapter_idx]
        
        # 收集参考材料
        reference_materials = self._gather_reference_materials(outline)
        
        # 生成章节
        chapter_prompt = self._create_chapter_prompt(outline, reference_materials)
        chapter_content = self.content_model.generate(chapter_prompt)
        
        # 调整内容长度
        target_length = self.config['chapter_length']
        chapter_content = self._adjust_content_length(chapter_content, target_length)
        
        # 验证和修正
        if not self._validate_chapter(chapter_content, chapter_idx):
            raise ValueError("Chapter validation failed")
        
        # 更新角色状态
        self._update_character_states(chapter_content, outline)
        
        return chapter_content
    
    def generate_novel(self):
        """生成完整小说"""
        try:
            target_chapters = self.config['target_length'] // self.config['chapter_length']
            
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