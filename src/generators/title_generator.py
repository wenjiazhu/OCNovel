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
        # 预处理摘要部分，避免在f-string表达式中使用反斜杠
        summary_section = ""
        if summaries:
            summary_section = "【已有章节摘要】\n" + "\n".join(summaries)
        
        prompt = f"""
        请为一部小说创作一段200字以内的故事梗概，这段梗概将用于小说的宣传推广。
        
        【小说信息】
        类型：{novel_type}
        主题：{theme}
        可选标题：{', '.join(titles.values())}
        
        {summary_section}
        
        【要求】
        1. 梗概必须控制在200字以内
        2. 需要突出小说的核心冲突和主要卖点
        3. 语言要生动有吸引力，能吸引读者点击阅读
        4. 适当埋下悬念，引发读者的好奇心
        5. 不要剧透小说的关键转折和结局
        6. 要符合{novel_type}类小说的读者口味
        7. 必须全部使用中文，不能包含任何英文单词或短语
        8. 如果需要使用外来词，请使用对应的中文翻译
        
        请直接输出梗概文字，不要添加其他说明或标题。
        """
        
        try:
            summary = self.model.generate(prompt)
            # 确保不超过200字
            if len(summary) > 200:
                prompt_trim = f"""
                请将以下梗概缩减到200字以内，保持核心内容和吸引力：
                
                {summary}
                
                请确保使用纯中文，不包含任何英文单词。
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
        # 使用所有标题生成封面提示词
        title_list = list(titles.values())
        platforms = list(titles.keys())
        
        prompt = f"""
        请为以下小说标题生成封面设计提示词，用于AI绘图生成小说封面。
        
        【小说信息】
        类型：{novel_type}
        梗概：{summary}
        标题：
        {chr(10).join([f"{i+1}. {title}" for i, title in enumerate(title_list)])}
        
        【要求】
        1. 为每个标题生成一组适合的封面设计提示词
        2. 提示词必须全部使用中文，不包含任何英文单词
        3. 提示词应包含以下要素：
           - 主要人物（性别、外观、服装等）
           - 场景氛围
           - 色调风格
           - 构图要点（适合2:3的竖版比例）
        4. 提示词要能反映出小说的类型和氛围
        5. 关键细节要与标题内涵相匹配
        6. 每组提示词需要简洁明了
        
        请按照以下格式输出结果：
        标题1：【提示词】
        标题2：【提示词】
        标题3：【提示词】
        标题4：【提示词】
        标题5：【提示词】
        """
        
        try:
            response = self.model.generate(prompt)
            cover_prompts = {}
            
            # 解析响应并匹配标题与平台
            lines = response.strip().split('\n')
            for i, line in enumerate(lines):
                if ':' in line or '：' in line:
                    parts = line.replace('：', ':').split(':', 1)
                    prompt_text = parts[1].strip()
                    
                    # 清理可能的多余字符
                    for char in ['【', '】']:
                        prompt_text = prompt_text.replace(char, '')
                    
                    # 按照顺序匹配平台
                    if i < len(platforms):
                        platform = platforms[i]
                        cover_prompts[platform] = prompt_text
            
            # 确保所有平台都有封面提示词
            for platform in platforms:
                if platform not in cover_prompts:
                    cover_prompts[platform] = f"年轻男子、修仙服饰、{titles[platform]}、2:3竖版构图、幻彩光效"
            
            return cover_prompts
        except Exception as e:
            logging.error(f"生成封面提示词时出错: {str(e)}")
            return {platform: f"年轻男子、修仙服饰、{title}、2:3竖版构图、幻彩光效" 
                   for platform, title in titles.items()}
                   
    def save_to_file(self, titles: Dict[str, str], summary: str, 
                     cover_prompts: Dict[str, str], cover_images: Dict[str, str] = None) -> str:
        """
        保存生成的内容到文件
        
        Args:
            titles: 生成的标题
            summary: 故事梗概
            cover_prompts: 封面提示词
            cover_images: 封面图片路径
            
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
        
        if cover_images:
            data["cover_images"] = cover_images
        
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
                
                # 添加封面图片链接（如果有）
                if cover_images and platform in cover_images:
                    image_path = cover_images[platform]
                    # 获取相对路径，方便在Markdown中显示
                    rel_path = os.path.relpath(image_path, self.output_dir)
                    f.write(f"![{platform}封面]({rel_path})\n\n")
                
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
        
        # 4. 生成封面图片
        cover_images = self.generate_cover_images(cover_prompts)
        logging.info(f"已生成{len(cover_images)}个封面图片")
        
        # 5. 保存到文件
        saved_file = self.save_to_file(titles, summary, cover_prompts, cover_images)
        logging.info(f"已保存到文件：{saved_file}")
        
        return {
            "titles": titles,
            "summary": summary,
            "cover_prompts": cover_prompts,
            "cover_images": cover_images,
            "saved_file": saved_file
        }

    def generate_cover_images(self, cover_prompts: Dict[str, str], output_dir: str = None) -> Dict[str, str]:
        """
        根据提示词生成封面图片，使用谷歌Gemini API
        
        Args:
            cover_prompts: 封面提示词
            output_dir: 输出目录，默认为self.output_dir下的covers子目录
            
        Returns:
            Dict[str, str]: 平台名称到图片路径的映射
        """
        import requests
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO
        import time
        import base64
        
        if output_dir is None:
            output_dir = os.path.join(self.output_dir, "covers")
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 用于存储生成的图片路径
        image_paths = {}
        
        try:
            # 为每个平台生成封面图片
            for platform, prompt in cover_prompts.items():
                try:
                    logging.info(f"正在为 {platform} 生成封面图片...")
                    
                    # 使用谷歌Gemini API生成图片
                    api_key = os.environ.get("GEMINI_API_KEY")
                    if not api_key:
                        logging.warning("未设置GEMINI_API_KEY环境变量，无法调用Gemini API")
                        raise ValueError("请设置GEMINI_API_KEY环境变量")
                    
                    # Gemini图像生成API端点
                    api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent"
                    
                    # 构建请求数据
                    request_data = {
                        "contents": [
                            {
                                "parts": [
                                    {
                                        "text": prompt + "，高清，精细，精美，小说封面，2:3比例"
                                    }
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.4,
                            "topK": 32,
                            "topP": 1,
                            "candidateCount": 1,
                        },
                        "safetySettings": [
                            {
                                "category": "HARM_CATEGORY_HARASSMENT",
                                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                            },
                            {
                                "category": "HARM_CATEGORY_HATE_SPEECH",
                                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                            },
                            {
                                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                            },
                            {
                                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                            }
                        ]
                    }
                    
                    # 发送API请求
                    response = requests.post(
                        f"{api_url}?key={api_key}",
                        json=request_data,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        # 从响应中提取图像数据
                        if "candidates" in response_data and len(response_data["candidates"]) > 0:
                            for candidate in response_data["candidates"]:
                                if "content" in candidate and "parts" in candidate["content"]:
                                    for part in candidate["content"]["parts"]:
                                        if "inlineData" in part and "data" in part["inlineData"]:
                                            # 获取base64编码的图像数据
                                            image_data = part["inlineData"]["data"]
                                            # 解码base64数据
                                            img_data = base64.b64decode(image_data)
                                            img = Image.open(BytesIO(img_data))
                                            
                                            # 保存图片
                                            clean_platform_name = platform.replace(" ", "_").replace("：", "_").replace(":", "_")
                                            image_filename = f"cover_{timestamp}_{clean_platform_name}.png"
                                            image_path = os.path.join(output_dir, image_filename)
                                            img.save(image_path)
                                            
                                            image_paths[platform] = image_path
                                            logging.info(f"已成功生成 {platform} 的封面图片: {image_path}")
                                            break
                        else:
                            raise ValueError(f"API返回数据中没有找到图像: {response_data}")
                    else:
                        logging.error(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
                        raise ValueError(f"API请求失败: {response.text}")
                    
                    # 避免API限制
                    time.sleep(2)
                
                except Exception as e:
                    logging.error(f"为 {platform} 生成封面图片时出错: {str(e)}")
                    # 创建一个错误图片
                    img = Image.new('RGB', (768, 1152), color=(255, 0, 0))
                    d = ImageDraw.Draw(img)
                    try:
                        font = ImageFont.truetype("arial.ttf", 36)
                    except IOError:
                        font = ImageFont.load_default()
                    d.text((384, 576), f"生成失败: {platform}", fill=(255, 255, 255), anchor="mm", font=font)
                    d.text((384, 650), str(e)[:50], fill=(255, 255, 255), anchor="mm", font=font)
                    
                    clean_platform_name = platform.replace(" ", "_").replace("：", "_").replace(":", "_")
                    image_filename = f"error_{timestamp}_{clean_platform_name}.png"
                    image_path = os.path.join(output_dir, image_filename)
                    img.save(image_path)
                    
                    image_paths[platform] = image_path
            
            return image_paths
                
        except Exception as e:
            logging.error(f"生成封面图片时出错: {str(e)}")
            return {} 