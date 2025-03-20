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
            
    def generate_outline(self, novel_type: str, theme: str, style: str):
        """生成小说大纲"""
        prompt = self._create_outline_prompt(novel_type, theme, style)
        outline_text = self.outline_model.generate(prompt)
        self.chapter_outlines = self._parse_outline(outline_text)
        
        # 保存大纲
        self._save_progress()
        
        return self.chapter_outlines
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate_chapter(self, chapter_idx: int) -> str:
        """生成章节内容"""
        outline = self.chapter_outlines[chapter_idx]
        
        # 收集参考材料
        reference_materials = self._gather_reference_materials(outline)
        
        # 生成章节
        chapter_prompt = self._create_chapter_prompt(outline, reference_materials)
        chapter_content = self.content_model.generate(chapter_prompt)
        
        # 验证和修正
        if not self._validate_chapter(chapter_content, chapter_idx):
            raise ValueError("Chapter validation failed")
            
        # 更新角色状态
        self._update_character_states(chapter_content, outline)
        
        return chapter_content
        
    def generate_novel(self):
        """生成完整小说"""
        try:
            for chapter_idx in range(self.current_chapter, len(self.chapter_outlines)):
                logging.info(f"Generating chapter {chapter_idx + 1}")
                
                # 生成章节
                chapter_content = self.generate_chapter(chapter_idx)
                
                # 保存章节
                self._save_chapter(chapter_idx + 1, chapter_content)
                
                # 更新进度
                self.current_chapter = chapter_idx + 1
                self._save_progress()
                
        except Exception as e:
            logging.error(f"Error during novel generation: {str(e)}")
            raise
            
    def _create_outline_prompt(self, novel_type: str, theme: str, style: str) -> str:
        """创建大纲生成提示词"""
        return f"""
        请使用雪花创作法生成一部小说的详细大纲：
        
        [基本信息]
        类型：{novel_type}
        主题：{theme}
        风格：{style}
        目标字数：{self.config['target_length']}
        
        [创作要求]
        1. 使用三幕式结构
        2. 每个章节包含：
           - 章节标题
           - 关键剧情点
           - 涉及角色
           - 场景设定
           - 核心冲突
        3. 确保情节递进合理
        4. 角色弧光完整
        5. 世界观设定统一
        
        请生成详细大纲。
        """
        
    def _parse_outline(self, outline_text: str) -> List[ChapterOutline]:
        """解析大纲文本"""
        chapters = []
        current_chapter = None
        lines = outline_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 新章节开始
            if line.startswith('第') and ('章' in line or '回' in line):
                # 保存前一章节
                if current_chapter:
                    chapters.append(ChapterOutline(**current_chapter))
                
                # 初始化新章节
                chapter_num = len(chapters) + 1
                title = line.split('：')[-1] if '：' in line else line
                current_chapter = {
                    'chapter_number': chapter_num,
                    'title': title,
                    'key_points': [],
                    'characters': [],
                    'settings': [],
                    'conflicts': []
                }
            elif current_chapter:
                # 解析章节内容
                if line.startswith('- 关键剧情'):
                    current_chapter['key_points'].extend(
                        [p.strip() for p in line.split('：')[1].split('；') if p.strip()]
                    )
                elif line.startswith('- 涉及角色'):
                    current_chapter['characters'].extend(
                        [c.strip() for c in line.split('：')[1].split('、') if c.strip()]
                    )
                elif line.startswith('- 场景设定'):
                    current_chapter['settings'].extend(
                        [s.strip() for s in line.split('：')[1].split('；') if s.strip()]
                    )
                elif line.startswith('- 核心冲突'):
                    current_chapter['conflicts'].extend(
                        [c.strip() for c in line.split('：')[1].split('；') if c.strip()]
                    )
        
        # 添加最后一章
        if current_chapter:
            chapters.append(ChapterOutline(**current_chapter))
            
        return chapters
        
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
        请基于以下信息创作小说章节：
        
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
        
        [写作要求]
        1. 保持与参考材料风格一致
        2. 确保人物性格连贯
        3. 场景描写细致生动
        4. 情节发展符合逻辑
        5. 字数控制在{self.config['chapter_length']}字左右
        
        请创作本章节内容。
        """
        
    def _validate_chapter(self, content: str, chapter_idx: int) -> bool:
        """验证章节内容"""
        # 检查字数
        if not self._check_length(content):
            return False
            
        # 检查逻辑连贯性
        if not self._check_logic(content, chapter_idx):
            return False
            
        # 检查人物表现
        if not self._check_characters(content):
            return False
            
        # 检查重复内容
        if not self._check_duplicates(content):
            return False
            
        return True
        
    def _check_length(self, content: str) -> bool:
        """检查章节字数"""
        target_length = self.config['chapter_length']
        actual_length = len(content)
        return 0.8 * target_length <= actual_length <= 1.2 * target_length
        
    def _check_logic(self, content: str, chapter_idx: int) -> bool:
        """检查逻辑连贯性"""
        prompt = f"""
        请分析以下内容的逻辑连贯性：
        
        {content}
        
        检查要点：
        1. 情节发展是否合理
        2. 人物行为是否符合动机
        3. 是否存在逻辑漏洞
        4. 与前文是否连贯
        
        如果发现问题，请指出；如果没有问题，请回复"通过"。
        """
        
        response = self.content_model.generate(prompt)
        return response.strip() == "通过"
        
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
                
                如果符合设定请回复"通过"，否则指出问题。
                """
                
                response = self.content_model.generate(prompt)
                if response.strip() != "通过":
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