import os
import argparse
import logging
from typing import Dict
from src.config.config import Config
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.knowledge_base.knowledge_base import KnowledgeBase
from src.generators.novel_generator import NovelGenerator

def setup_logging(config: Config):
    """设置日志"""
    os.makedirs(config.log_config["log_dir"], exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(config.log_config["log_dir"], "novel_generation.log"),
        level=config.log_config["log_level"],
        format=config.log_config["log_format"]
    )

def create_model(model_config: Dict):
    """创建AI模型实例"""
    if model_config["type"] == "gemini":
        return GeminiModel(model_config)
    elif model_config["type"] == "openai":
        return OpenAIModel(model_config)
    else:
        raise ValueError(f"不支持的模型类型: {model_config['type']}")

def main():
    parser = argparse.ArgumentParser(description="长篇网文仿写工具")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    args = parser.parse_args()
    
    try:
        # 询问用户是否继续上次的生成
        continue_last = input("是否继续上次的生成？(Y/n) ").strip().lower()
        continue_generation = continue_last != 'n'
        
        # 加载配置
        config = Config()
        setup_logging(config)
        logging.info("配置加载完成")
        
        # 创建模型实例
        logging.info("正在初始化AI模型...")
        outline_model = create_model(config.model_config["outline_model"])
        content_model = create_model(config.model_config["content_model"])
        embedding_model = create_model(config.model_config["embedding_model"])
        logging.info("AI模型初始化完成")
        
        # 检查参考小说文件
        reference_file = config.knowledge_base_config["reference_file"]
        if not os.path.exists(reference_file):
            raise FileNotFoundError(f"参考小说文件不存在: {reference_file}")
            
        # 创建知识库
        logging.info("正在构建知识库...")
        knowledge_base = KnowledgeBase(
            config.knowledge_base_config,
            embedding_model
        )
        
        # 导入参考小说
        with open(reference_file, 'r', encoding='utf-8') as f:
            reference_text = f.read()
        knowledge_base.build(
            reference_text, 
            force_rebuild=config.generation_config.get("force_rebuild_kb", False)
        )
        logging.info("知识库构建完成")
        
        # 创建小说生成器
        generator = NovelGenerator(
            config.generator_config,
            outline_model,
            content_model,
            knowledge_base
        )
        
        if not continue_generation:
            # 生成新的大纲
            logging.info("正在生成小说大纲...")
            generator.generate_outline(
                config.novel_config["type"],
                config.novel_config["theme"],
                config.novel_config["style"]
            )
            logging.info("大纲生成完成")
        
        # 生成小说
        logging.info("开始生成小说...")
        generator.generate_novel()
        logging.info("小说生成完成")
        
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
        raise

def init_workspace():
    """初始化工作目录"""
    # 创建必要的目录
    dirs = [
        "data/cache",
        "data/output",
        "data/logs",
        "data/reference"
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        
    # 创建.gitkeep文件
    for dir_path in dirs:
        gitkeep_file = os.path.join(dir_path, ".gitkeep")
        if not os.path.exists(gitkeep_file):
            with open(gitkeep_file, 'w') as f:
                pass

if __name__ == "__main__":
    # 初始化工作目录
    init_workspace()
    # 运行主程序
    main() 