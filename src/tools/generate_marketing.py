import os
import sys
import argparse
import json
import logging

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.config import Config
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.generators.title_generator import TitleGenerator

def setup_logging():
    """设置日志"""
    # 获取项目根目录
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 定义日志目录路径
    log_dir = os.path.join(base_dir, "data", "logs")
    # 确保日志目录存在
    os.makedirs(log_dir, exist_ok=True)
    # 定义日志文件完整路径
    log_file_path = os.path.join(log_dir, "marketing_generation.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            # 使用完整的日志文件路径
            logging.FileHandler(log_file_path, encoding='utf-8')
        ]
    )

def create_model(model_config):
    """创建AI模型实例"""
    logging.info(f"正在创建模型: {model_config['type']} - {model_config['model_name']}")
    if model_config["type"] == "gemini":
        return GeminiModel(model_config)
    elif model_config["type"] == "openai":
        return OpenAIModel(model_config)
    elif model_config["type"] == "volcengine":
        return OpenAIModel(model_config)  # 火山引擎复用OpenAI兼容实现
    else:
        raise ValueError(f"不支持的模型类型: {model_config['type']}")

def load_chapter_summaries(summary_file):
    """加载章节摘要"""
    if not os.path.exists(summary_file):
        logging.warning(f"摘要文件不存在: {summary_file}")
        return []
        
    try:
        with open(summary_file, 'r', encoding='utf-8') as f:
            summaries = json.load(f)
            return list(summaries.values())
    except Exception as e:
        logging.error(f"加载摘要文件时出错: {str(e)}")
        return []

def main():
    parser = argparse.ArgumentParser(description="小说营销内容生成工具")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--output_dir", default="data/marketing", help="输出目录")
    parser.add_argument("--summary_file", help="章节摘要文件路径")
    parser.add_argument("--keywords", nargs="+", help="额外的关键词")
    parser.add_argument("--characters", nargs="+", help="主要角色名")
    args = parser.parse_args()
    
    try:
        setup_logging()
        logging.info("开始生成小说营销内容...")
        
        # 加载配置
        config = Config()  # 不传递参数
        logging.info("配置加载完成")
        
        # 创建内容生成模型
        content_model = create_model(config.model_config["content_model"])
        logging.info("AI模型初始化完成")
        
        # 创建标题生成器
        generator = TitleGenerator(content_model, args.output_dir)
        
        # 加载章节摘要
        chapter_summaries = []
        if args.summary_file:
            chapter_summaries = load_chapter_summaries(args.summary_file)
            logging.info(f"已加载 {len(chapter_summaries)} 条章节摘要")
        elif hasattr(config, 'output_config') and 'output_dir' in config.output_config:
            summary_file = os.path.join(config.output_config['output_dir'], "summary.json")
            if os.path.exists(summary_file):
                chapter_summaries = load_chapter_summaries(summary_file)
                logging.info(f"已从默认位置加载 {len(chapter_summaries)} 条章节摘要")
        
        # 准备小说配置
        novel_config = {
            "type": config.novel_config.get("type", "玄幻"),
            "theme": config.novel_config.get("theme", "修真逆袭"),
            "keywords": args.keywords or config.novel_config.get("keywords", []),
            "main_characters": args.characters or config.novel_config.get("main_characters", [])
        }
        
        # 一键生成所有营销内容
        result = generator.one_click_generate(novel_config, chapter_summaries)
        
        logging.info("营销内容生成完成！")
        logging.info(f"结果已保存到：{result['saved_file']}")
        
        # 打印生成的内容摘要
        print("\n===== 生成的营销内容摘要 =====")
        print("\n【标题方案】")
        for platform, title in result["titles"].items():
            print(f"{platform}: {title}")
            
        print("\n【故事梗概】")
        print(result["summary"])
        
        print("\n【封面提示词】")
        for platform, prompt in result["cover_prompts"].items():
            print(f"{platform}: {prompt}")
        
        if "cover_images" in result and result["cover_images"]:
            print("\n【封面图片】")
            for platform, image_path in result["cover_images"].items():
                print(f"{platform}: {image_path}")
        
        print("\n【已保存到】")
        print(result["saved_file"])
        
    except Exception as e:
        logging.error(f"生成营销内容时出错: {str(e)}")
        raise

if __name__ == "__main__":
    main() 