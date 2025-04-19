import os
import json
import logging
import time
from typing import List, Tuple, Optional
from ..common.data_structures import ChapterOutline
from ..common.utils import load_json_file, save_json_file, validate_directory

class OutlineGenerator:
    def __init__(self, config, outline_model, knowledge_base):
        self.config = config
        self.outline_model = outline_model
        self.knowledge_base = knowledge_base
        self.output_dir = config.output_config["output_dir"]
        self.chapter_outlines = []
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)
        # 加载现有大纲
        self._load_outline()

    def _load_outline(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        outline_data = load_json_file(outline_file, default_value=[])
        
        if outline_data:
            # 处理可能的旧格式（包含元数据）和新格式（仅含章节列表）
            chapters_list = outline_data.get("chapters", outline_data) if isinstance(outline_data, dict) else outline_data
            if isinstance(chapters_list, list):
                self.chapter_outlines = [ChapterOutline(**chapter) for chapter in chapters_list]
                logging.info(f"从文件加载了 {len(self.chapter_outlines)} 章大纲")
            else:
                logging.error("大纲文件格式无法识别")
                self.chapter_outlines = []

    def _save_outline(self) -> bool:
        """保存大纲到文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        try:
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
            
            return save_json_file(outline_file, outline_data)
        except Exception as e:
            logging.error(f"保存大纲文件时出错: {str(e)}")
            return False

    def generate_outline(self, novel_type: str, theme: str, style: str, 
                        mode: str = 'replace', replace_range: Tuple[int, int] = None, 
                        extra_prompt: str = None) -> bool:
        """生成指定范围的章节大纲"""
        try:
            if mode != 'replace' or not replace_range:
                logging.error("不支持的生成模式或缺少必要参数")
                return False

            start_chapter, end_chapter = replace_range
            if start_chapter < 1 or end_chapter < start_chapter:
                logging.error("无效的章节范围")
                return False

            total_chapters = end_chapter - start_chapter + 1
            batch_size = 50  # 每批次生成50章
            successful_outlines = []

            num_batches = (total_chapters + batch_size - 1) // batch_size
            for batch_idx in range(num_batches):
                if not self._generate_batch(batch_idx, batch_size, start_chapter, end_chapter,
                                         novel_type, theme, style, extra_prompt, successful_outlines):
                    return False

            logging.info(f"所有批次的大纲生成完成，共生成 {len(successful_outlines)} 章")
            return True

        except Exception as e:
            logging.error(f"生成大纲时发生错误：{str(e)}")
            return False

    def _generate_batch(self, batch_idx: int, batch_size: int, start_chapter: int, 
                       end_chapter: int, novel_type: str, theme: str, style: str,
                       extra_prompt: str, successful_outlines: List[ChapterOutline]) -> bool:
        """生成一个批次的大纲"""
        batch_start = start_chapter + (batch_idx * batch_size)
        batch_end = min(batch_start + batch_size - 1, end_chapter)
        current_batch_size = batch_end - batch_start + 1

        logging.info(f"开始生成第 {batch_start} 到 {batch_end} 章的大纲（共 {current_batch_size} 章）")

        # 获取当前批次的上下文
        existing_context = self._get_context_for_batch(batch_start, successful_outlines)
        
        # 生成大纲
        prompt = self._create_outline_prompt(
            novel_type=novel_type,
            theme=theme,
            style=style,
            current_start_chapter_num=batch_start,
            current_batch_size=current_batch_size,
            existing_context=existing_context,
            extra_prompt=extra_prompt
        )

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.outline_model.generate(prompt)
                logging.debug(f"模型原始响应: {response}")  # 添加日志记录
                try:
                    outline_data = json.loads(response)
                except json.JSONDecodeError as e:
                    logging.error(f"解析模型响应失败: {e}\n响应内容: {response}")
                    raise
                if not isinstance(outline_data, list) or len(outline_data) != current_batch_size:
                    logging.error(f"生成的大纲格式不正确（第 {attempt + 1} 次尝试）")
                    continue

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
                
                if self._save_outline():
                    successful_outlines.extend(new_outlines)
                    logging.info(f"成功生成并保存第 {batch_start} 到 {batch_end} 章的大纲")
                    return True

            except Exception as e:
                logging.error(f"处理大纲数据时出错（第 {attempt + 1} 次尝试）：{str(e)}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30
                    logging.info(f"等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)

        logging.error(f"在处理第 {batch_start} 到 {batch_end} 章的大纲时失败")
        return False

    def _get_context_for_batch(self, batch_start: int, existing_outlines: List[ChapterOutline]) -> str:
        """获取批次的上下文信息"""
        context_parts = []
        
        # 获取前一章的大纲信息
        if batch_start > 1 and existing_outlines:
            prev_outline = existing_outlines[-1]
            context_parts.append(f"前一章大纲：\n{prev_outline.title}\n关键点：{', '.join(prev_outline.key_points)}")

        # 获取相关的知识库内容
        if existing_outlines:
            query_text = " ".join([o.title for o in existing_outlines[-3:]])  # 使用最近3章的标题
            relevant_knowledge = self.knowledge_base.search(query_text)
            if relevant_knowledge:
                context_parts.append("相关参考内容：\n" + "\n".join(relevant_knowledge))

        return "\n\n".join(context_parts)

    def _create_outline_prompt(self, novel_type: str, theme: str, style: str,
                             current_start_chapter_num: int, current_batch_size: int,
                             existing_context: str, extra_prompt: str = None) -> str:
        """创建大纲生成的提示词"""
        prompt = f"""请为一部{novel_type}小说生成从第{current_start_chapter_num}章开始的{current_batch_size}章的详细大纲。
主题：{theme}
写作风格：{style}

要求：
1. 每章大纲包含：章节标题、关键情节点、出场角色、场景设定、主要冲突
2. 保持情节连贯性和人物发展的合理性
3. 符合{novel_type}的特点和{theme}的主题

现有上下文信息：
{existing_context}

"""
        if extra_prompt:
            prompt += f"\n额外要求：\n{extra_prompt}"
            
        return prompt

if __name__ == "__main__":
    import argparse
    from ..config.config import Config
    from ..models import OutlineModel, KnowledgeBase
    
    parser = argparse.ArgumentParser(description='生成小说大纲')
    parser.add_argument('--config', type=str, required=True, help='配置文件路径')
    parser.add_argument('--novel-type', type=str, required=True, help='小说类型')
    parser.add_argument('--theme', type=str, required=True, help='主题')
    parser.add_argument('--style', type=str, required=True, help='写作风格')
    parser.add_argument('--start', type=int, required=True, help='起始章节')
    parser.add_argument('--end', type=int, required=True, help='结束章节')
    parser.add_argument('--extra-prompt', type=str, help='额外提示词')
    
    args = parser.parse_args()
    
    # 加载配置
    config = Config(args.config)
    
    # 初始化模型和知识库
    outline_model = OutlineModel()
    knowledge_base = KnowledgeBase()
    
    # 创建大纲生成器
    generator = OutlineGenerator(config, outline_model, knowledge_base)
    
    # 生成大纲
    success = generator.generate_outline(
        novel_type=args.novel_type,
        theme=args.theme,
        style=args.style,
        mode='replace',
        replace_range=(args.start, args.end),
        extra_prompt=args.extra_prompt
    )
    
    if success:
        print("大纲生成成功！")
    else:
        print("大纲生成失败，请查看日志文件了解详细信息。") 