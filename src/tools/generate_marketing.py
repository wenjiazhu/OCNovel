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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("marketing_generation.log", encoding='utf-8')
        ]
    )

def create_model(model_config):
    """创建AI模型实例"""
    logging.info(f"正在创建模型: {model_config['type']} - {model_config['model_name']}")
    if model_config["type"] == "gemini":
        return GeminiModel(model_config)
    elif model_config["type"] == "openai":
        return OpenAIModel(model_config)
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
        config = Config(args.config)
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
        elif hasattr(config, 'generator_config') and 'output_dir' in config.generator_config:
            summary_file = os.path.join(config.generator_config['output_dir'], "summary.json")
            if os.path.exists(summary_file):
                chapter_summaries = load_chapter_summaries(summary_file)
                logging.info(f"已从默认位置加载 {len(chapter_summaries)} 条章节摘要")
        
        # 准备小说配置
        novel_config = {
            "type": config.generator_config.get("novel_config", {}).get("type", "玄幻"),
            "theme": config.generator_config.get("novel_config", {}).get("theme", "修真逆袭"),
            "keywords": args.keywords or config.generator_config.get("novel_config", {}).get("keywords", []),
            "main_characters": args.characters or config.generator_config.get("novel_config", {}).get("main_characters", [])
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
        
        print("\n【已保存到】")
        print(result["saved_file"])
        
    except Exception as e:
        logging.error(f"生成营销内容时出错: {str(e)}")
        raise

if __name__ == "__main__":
    main() 