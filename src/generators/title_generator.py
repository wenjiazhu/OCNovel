import os
import json
import logging
import datetime
from typing import Dict, List, Optional

class TitleGenerator:
    """小说标题、梗概和封面提示词生成器"""
    
    def __init__(self, model, output_dir: str = "data/marketing"):
        """
        初始化生成器
        
        Args:
            model: AI模型实例（支持generate方法）
            output_dir: 输出目录
        """
        self.model = model
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_titles(self, novel_type: str, theme: str, keywords: List[str], 
                         character_names: List[str], existing_outline: Optional[str] = None) -> Dict[str, str]:
        """
        生成符合各平台风格的小说标题
        
        Args:
            novel_type: 小说类型
            theme: 小说主题
            keywords: 关键词列表
            character_names: 主要角色名列表
            existing_outline: 已有的小说大纲或摘要
            
        Returns:
            Dict[str, str]: 平台名称到标题的映射
        """
        platforms = ["番茄小说", "七猫小说", "起点中文网", "书旗小说", "掌阅"]
        platform_styles = {
            "番茄小说": "吸引眼球、有悬念、通常包含数字",
            "七猫小说": "有仙侠/玄幻色彩、略带文艺气息",
            "起点中文网": "有气势、展现成长、争霸、逆袭等主题",
            "书旗小说": "简洁有力、能体现小说主要矛盾",
            "掌阅": "注重人物关系、情感冲突、容易记忆"
        }
        
        prompt = f"""
        请帮我为一部小说生成5个不同风格的标题，每个标题对应一个不同的阅读平台风格。
        
        【小说信息】
        类型：{novel_type}
        主题：{theme}
        关键词：{', '.join(keywords)}
        主要角色：{', '.join(character_names)}
        {'大纲摘要：' + existing_outline if existing_outline else ''}
        
        【要求】
        1. 每个标题必须在15个汉字以内
        2. 标题要有吸引力，符合该平台的风格特点
        3. 标题要体现小说的核心卖点和情感
        4. 避免过于俗套或老套的表达
        5. 标题要与小说类型、主题相符
        
        【不同平台的风格特点】
        {chr(10).join([f"- {platform}: {style}" for platform, style in platform_styles.items()])}
        
        请按照以下格式输出结果（仅输出标题，不要解释）：
        番茄小说：【标题】
        七猫小说：【标题】
        起点中文网：【标题】
        书旗小说：【标题】
        掌阅：【标题】
        """
        
        try:
            response = self.model.generate(prompt)
            titles = {}
            
            for line in response.strip().split('\n'):
                if ':' in line or '：' in line:
                    parts = line.replace('：', ':').split(':', 1)
                    platform = parts[0].strip()
                    title = parts[1].strip()
                    
                    # 清理可能的多余字符
                    for char in ['【', '】', '"', '"']:
                        title = title.replace(char, '')
                    
                    titles[platform] = title
            
            return titles
        except Exception as e:
            logging.error(f"生成标题时出错: {str(e)}")
            return {platform: f"未能生成{platform}标题" for platform in platforms}
            
    def generate_summary(self, novel_type: str, theme: str, titles: Dict[str, str], 
                          summaries: List[str] = None) -> str:
        """
        生成200字以内的故事梗概
        
        Args:
            novel_type: 小说类型
            theme: 小说主题
            titles: 生成的标题
            summaries: 已有的章节摘要列表
            
        Returns:
            str: 生成的故事梗概
        """
        prompt = f"""
        请为一部小说创作一段200字以内的故事梗概，这段梗概将用于小说的宣传推广。
        
        【小说信息】
        类型：{novel_type}
        主题：{theme}
        可选标题：{', '.join(titles.values())}
        
        {'【已有章节摘要】\n' + '\n'.join(summaries) if summaries else ''}
        
        【要求】
        1. 梗概必须控制在200字以内
        2. 需要突出小说的核心冲突和主要卖点
        3. 语言要生动有吸引力，能吸引读者点击阅读
        4. 适当埋下悬念，引发读者的好奇心
        5. 不要剧透小说的关键转折和结局
        6. 要符合{novel_type}类小说的读者口味
        
        请直接输出梗概文字，不要添加其他说明或标题。
        """
        
        try:
            summary = self.model.generate(prompt)
            # 确保不超过200字
            if len(summary) > 200:
                prompt_trim = f"""
                请将以下梗概缩减到200字以内，保持核心内容和吸引力：
                
                {summary}
                """
                summary = self.model.generate(prompt_trim)
                
            return summary.strip()
        except Exception as e:
            logging.error(f"生成梗概时出错: {str(e)}")
            return "未能生成小说梗概"
            
    def generate_cover_prompts(self, novel_type: str, titles: Dict[str, str], 
                                 summary: str) -> Dict[str, str]:
        """
        生成封面提示词
        
        Args:
            novel_type: 小说类型
            titles: 生成的标题
            summary: 故事梗概
            
        Returns:
            Dict[str, str]: 标题到封面提示词的映射
        """
        # 提取待生成封面的标题
        title_list = list(titles.values())[:3]  # 只为前三个标题生成封面提示词
        
        prompt = f"""
        请为以下小说标题生成封面设计提示词，用于AI绘图生成小说封面。
        
        【小说信息】
        类型：{novel_type}
        梗概：{summary}
        标题：{', '.join(title_list)}
        
        【要求】
        1. 为每个标题生成一组适合的封面设计提示词
        2. 提示词应包含以下要素：
           - 主要人物（性别、外观、服装等）
           - 场景氛围
           - 色调风格
           - 构图要点
        3. 提示词要能反映出小说的类型和氛围
        4. 关键细节要与标题内涵相匹配
        5. 每组提示词需要简洁明了
        
        请按照以下格式输出结果：
        标题1：【提示词】
        标题2：【提示词】
        标题3：【提示词】
        """
        
        try:
            response = self.model.generate(prompt)
            cover_prompts = {}
            
            # 将生成的每个标题的提示词匹配到原始标题
            current_idx = 0
            for line in response.strip().split('\n'):
                if ':' in line or '：' in line:
                    if current_idx < len(title_list):
                        # 找到对应的原始平台和标题
                        for platform, title in titles.items():
                            if title == title_list[current_idx]:
                                parts = line.replace('：', ':').split(':', 1)
                                prompt_text = parts[1].strip()
                                
                                # 清理可能的多余字符
                                for char in ['【', '】']:
                                    prompt_text = prompt_text.replace(char, '')
                                    
                                cover_prompts[platform] = prompt_text
                                current_idx += 1
                                break
            
            return cover_prompts
        except Exception as e:
            logging.error(f"生成封面提示词时出错: {str(e)}")
            return {platform: f"未能生成{title}的封面提示词" 
                   for platform, title in titles.items() if platform in list(titles.keys())[:3]}
                   
    def save_to_file(self, titles: Dict[str, str], summary: str, 
                     cover_prompts: Dict[str, str]) -> str:
        """
        保存生成的内容到文件
        
        Args:
            titles: 生成的标题
            summary: 故事梗概
            cover_prompts: 封面提示词
            
        Returns:
            str: 保存的文件路径
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.output_dir, f"novel_marketing_{timestamp}.json")
        
        data = {
            "timestamp": timestamp,
            "titles": titles,
            "summary": summary,
            "cover_prompts": cover_prompts
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 同时保存一个Markdown版本，方便阅读
        md_filename = os.path.join(self.output_dir, f"novel_marketing_{timestamp}.md")
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write("# 小说营销材料\n\n")
            f.write(f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 标题方案\n\n")
            for platform, title in titles.items():
                f.write(f"- **{platform}**: {title}\n")
            
            f.write("\n## 故事梗概\n\n")
            f.write(f"{summary}\n\n")
            
            f.write("## 封面提示词\n\n")
            for platform, prompt in cover_prompts.items():
                title = titles.get(platform, "")
                f.write(f"### {platform}（{title}）\n")
                f.write(f"{prompt}\n\n")
                
        return filename
        
    def one_click_generate(self, novel_config: Dict, chapter_summaries: List[str] = None) -> Dict:
        """
        一键生成所有营销内容
        
        Args:
            novel_config: 小说配置信息
            chapter_summaries: 章节摘要列表
            
        Returns:
            Dict: 生成的所有内容
        """
        # 提取小说信息
        novel_type = novel_config.get("type", "玄幻")
        theme = novel_config.get("theme", "修真逆袭")
        keywords = novel_config.get("keywords", [])
        character_names = novel_config.get("main_characters", [])
        
        # 如果没有提供关键词，从主题中提取
        if not keywords:
            keywords = theme.split()
            
        # 如果没有提供角色名，使用默认值
        if not character_names:
            character_names = ["主角", "对手", "师傅"]
            
        # 提取大纲摘要
        existing_outline = novel_config.get("outline_summary", "")
        
        # 1. 生成标题
        titles = self.generate_titles(novel_type, theme, keywords, character_names, existing_outline)
        logging.info(f"已生成{len(titles)}个标题")
        
        # 2. 生成梗概
        summary = self.generate_summary(novel_type, theme, titles, chapter_summaries)
        logging.info(f"已生成故事梗概，长度：{len(summary)}字")
        
        # 3. 生成封面提示词
        cover_prompts = self.generate_cover_prompts(novel_type, titles, summary)
        logging.info(f"已生成{len(cover_prompts)}个封面提示词")
        
        # 4. 保存到文件
        saved_file = self.save_to_file(titles, summary, cover_prompts)
        logging.info(f"已保存到文件：{saved_file}")
        
        return {
            "titles": titles,
            "summary": summary,
            "cover_prompts": cover_prompts,
            "saved_file": saved_file
        } 