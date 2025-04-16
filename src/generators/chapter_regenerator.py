import os
import argparse
import logging
import json
import hashlib
import sys
from typing import Dict, Optional, List, Set
import glob

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config.config import Config
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.knowledge_base.knowledge_base import KnowledgeBase
from src.generators.novel_generator import NovelGenerator

def setup_logging(config: Dict):
    """设置日志"""
    os.makedirs(config["log_dir"], exist_ok=True)
    
    # 设置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(config["log_level"])
    
    # 设置文件处理器
    file_handler = logging.FileHandler(
        os.path.join(config["log_dir"], "chapter_regeneration.log"),
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(config["log_format"]))
    root_logger.addHandler(file_handler)
    
    # 设置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(config["log_format"]))
    root_logger.addHandler(console_handler)

def create_model(model_config: Dict):
    """创建AI模型实例"""
    logging.info(f"正在创建模型: {model_config['type']} - {model_config['model_name']}")
    if model_config["type"] == "gemini":
        return GeminiModel(model_config)
    elif model_config["type"] == "openai":
        return OpenAIModel(model_config)
    else:
        raise ValueError(f"不支持的模型类型: {model_config['type']}")

def get_imported_files() -> Set[str]:
    """获取已导入文件的记录"""
    cache_file = "data/cache/imported_files.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            imported_files = json.load(f)
            # 过滤掉无效的条目
            return {f for f in imported_files if ':' in f}  # 只保留格式为 "path:md5" 的条目
    return set()

def main():
    parser = argparse.ArgumentParser(description="章节重新生成工具")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    parser.add_argument("--chapter", type=int, required=True, help="要重新生成的章节号")
    parser.add_argument("--prompt", type=str, help="重新生成章节时的额外提示词")
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = Config()
        
        # 设置日志
        setup_logging(config.log_config)
        logging.info("配置加载完成")
        
        # 创建模型实例
        logging.info("正在初始化AI模型...")
        outline_model = create_model(config.model_config["outline_model"])
        content_model = create_model(config.model_config["content_model"])
        embedding_model = create_model(config.model_config["embedding_model"])
        logging.info("AI模型初始化完成")
        
        # 检查参考小说文件
        reference_files = config.knowledge_base_config["reference_files"]
        logging.info(f"正在检查参考小说文件: {reference_files}")
        
        # 获取已导入文件的记录
        imported_files = get_imported_files()
        
        # 检查是否有新文件需要导入
        new_files = []
        for file in reference_files:
            file_hash = hashlib.md5(open(file, 'rb').read()).hexdigest()
            file_key = f"{file}:{file_hash}"
            if file_key not in imported_files:
                new_files.append(file)
        
        if not new_files and imported_files:
            logging.info("所有文件都已导入，从缓存加载知识库")
            # 创建知识库并从缓存加载
            knowledge_base = KnowledgeBase(
                config.knowledge_base_config,
                embedding_model
            )
            # 加载第一个参考文件的缓存
            first_file = reference_files[0]
            if os.path.exists(first_file):
                with open(first_file, 'r', encoding='utf-8') as f:
                    first_text = f.read()
                    knowledge_base.build(first_text)  # 这会触发从缓存加载
        else:
            # 创建知识库
            logging.info("正在构建知识库...")
            knowledge_base = KnowledgeBase(
                config.knowledge_base_config,
                embedding_model
            )
            
            # 导入参考小说
            all_reference_text = ""
            for file in new_files:
                with open(file, 'r', encoding='utf-8') as f:
                    reference_text = f.read()
                    all_reference_text += reference_text + "\n"
                    logging.info(f"已导入参考文件: {file}, 长度: {len(reference_text)}")
                file_hash = hashlib.md5(open(file, 'rb').read()).hexdigest()
                imported_files.add(f"{file}:{file_hash}")
            
            if all_reference_text:
                knowledge_base.build(
                    all_reference_text, 
                    force_rebuild=config.generator_config.get("force_rebuild_kb", False)
                )
                logging.info("知识库构建完成")
                
                # 保存已导入文件记录
                os.makedirs(config.knowledge_base_config["cache_dir"], exist_ok=True)
                with open("data/cache/imported_files.json", 'w', encoding='utf-8') as f:
                    json.dump(list(imported_files), f, ensure_ascii=False, indent=2)
                logging.info("已更新导入文件记录")
        
        # 创建小说生成器
        generator = NovelGenerator(
            config,
            outline_model,
            content_model,
            knowledge_base
        )
        
        # 设置目标章节和外部提示词
        generator.target_chapter = args.chapter
        generator.external_prompt = args.prompt
        
        # 强制设置当前章节为目标章节的索引，覆盖从 progress.json 加载的值
        logging.info(f"强制设置开始章节为: {args.chapter}")
        if args.prompt:
             logging.info(f"使用外部提示词: {args.prompt}")
        generator.current_chapter = args.chapter - 1

        # 调用generate_novel方法
        generator.generate_novel()
        # 检查生成器最终的 current_chapter 是否等于 target_chapter 来确认是否真的生成了
        if generator.current_chapter == args.chapter:
             logging.info(f"第 {args.chapter} 章重新生成完成")
        else:
             logging.warning(f"第 {args.chapter} 章可能未生成，生成器停止在章节 {generator.current_chapter + 1}")

    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main() 