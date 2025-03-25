import os
import argparse
import logging
import json
import hashlib
import sys
from typing import Dict
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
        imported_files_record = os.path.join(config.knowledge_base_config["cache_dir"], "imported_files.json")
        imported_files = set()
        if os.path.exists(imported_files_record):
            with open(imported_files_record, 'r', encoding='utf-8') as f:
                imported_files = set(json.load(f))
                logging.info(f"已导入的文件记录: {imported_files}")
        
        # 过滤出需要导入的文件
        files_to_import = []
        for file_path in reference_files:
            if not os.path.exists(file_path):
                logging.warning(f"参考小说文件不存在，将跳过: {file_path}")
                continue
                
            file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
            file_record = f"{file_path}:{file_hash}"
            
            if file_record in imported_files and not config.generator_config.get("force_rebuild_kb", False):
                logging.info(f"文件已导入，将跳过: {file_path}")
                continue
                
            files_to_import.append((file_path, file_record))
        
        if not files_to_import and imported_files:
            logging.info("所有文件都已导入，无需重新构建知识库")
            # 创建知识库但不重新构建
            knowledge_base = KnowledgeBase(
                config.knowledge_base_config,
                embedding_model
            )
        else:
            # 创建知识库
            logging.info("正在构建知识库...")
            knowledge_base = KnowledgeBase(
                config.knowledge_base_config,
                embedding_model
            )
            
            # 导入参考小说
            all_reference_text = ""
            for file_path, file_record in files_to_import:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reference_text = f.read()
                    all_reference_text += reference_text + "\n"
                    logging.info(f"已导入参考文件: {file_path}, 长度: {len(reference_text)}")
                imported_files.add(file_record)
            
            if all_reference_text:
                knowledge_base.build(
                    all_reference_text, 
                    force_rebuild=config.generator_config.get("force_rebuild_kb", False)
                )
                logging.info("知识库构建完成")
                
                # 保存已导入文件记录
                os.makedirs(config.knowledge_base_config["cache_dir"], exist_ok=True)
                with open(imported_files_record, 'w', encoding='utf-8') as f:
                    json.dump(list(imported_files), f, ensure_ascii=False, indent=2)
                logging.info("已更新导入文件记录")
        
        # 创建小说生成器
        generator = NovelGenerator(
            config.generator_config,
            outline_model,
            content_model,
            knowledge_base
        )
        
        # 重新生成指定章节
        chapter_num = args.chapter
        extra_prompt = args.prompt if args.prompt else ""
        logging.info(f"正在重新生成第 {chapter_num} 章，额外提示词: {extra_prompt}")
        
        try:
            # 读取原章节内容
            output_dir = config.generator_config.get("output_dir", "data/output")
            
            # 定义多种可能的章节文件名格式
            possible_chapter_files = [
                os.path.join(output_dir, f"第{chapter_num}章.txt"),
                os.path.join(output_dir, f"第{chapter_num} 章.txt"),
                os.path.join(output_dir, f"第{chapter_num}章_*.txt")  # 通配符匹配带标题的文件
            ]
            
            chapter_file = ""
            original_content = ""
            
            # 尝试找到并读取章节文件
            for file_pattern in possible_chapter_files:
                if '*' in file_pattern:
                    # 处理带通配符的文件名
                    matching_files = glob.glob(file_pattern)
                    if matching_files:
                        chapter_file = matching_files[0]
                        break
                elif os.path.exists(file_pattern):
                    chapter_file = file_pattern
                    break
            
            if chapter_file and os.path.exists(chapter_file):
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                logging.info(f"已读取原第 {chapter_num} 章内容: {chapter_file}")
            else:
                logging.warning(f"未找到第 {chapter_num} 章原始文件，将创建新章节")
            
            # 读取前后章节内容
            prev_content = ""
            next_content = ""
            if chapter_num > 1:
                prev_file = os.path.join(output_dir, f"第{chapter_num-1}章.txt")
                if os.path.exists(prev_file):
                    with open(prev_file, 'r', encoding='utf-8') as f:
                        prev_content = f.read()
                    logging.info(f"已读取第 {chapter_num-1} 章内容")
            
            next_file = os.path.join(output_dir, f"第{chapter_num+1}章.txt")
            if os.path.exists(next_file):
                with open(next_file, 'r', encoding='utf-8') as f:
                    next_content = f.read()
                logging.info(f"已读取第 {chapter_num+1} 章内容")
            
            # 使用NovelGenerator中的方法重新生成章节
            generator.generate_chapter(chapter_num - 1, extra_prompt, original_content, prev_content, next_content)
            logging.info(f"第 {chapter_num} 章重新生成完成")
            
            # 更新章节摘要
            summary_file = os.path.join(output_dir, "summary.json")
            if os.path.exists(summary_file):
                with open(summary_file, 'r', encoding='utf-8') as f:
                    summaries = json.load(f)
                
                # 查找重新生成的章节文件
                new_chapter_files = [
                    f for f in os.listdir(output_dir) 
                    if f.startswith(f"第{chapter_num}章") or f.startswith(f"第{chapter_num} 章")
                ]
                
                if new_chapter_files:
                    new_chapter_file = os.path.join(output_dir, new_chapter_files[0])
                    logging.info(f"找到重新生成的章节文件: {new_chapter_files[0]}")
                    
                    # 读取重新生成后的章节内容
                    with open(new_chapter_file, 'r', encoding='utf-8') as f:
                        new_chapter_content = f.read()
                    
                    # 使用新生成的内容来创建摘要
                    prompt = f"""
                    请为以下章节内容生成一个200字以内的摘要，要求：
                    1. 突出本章的主要情节发展
                    2. 包含关键人物的重要行动
                    3. 说明本章对整体剧情的影响
                    4. 仅返回摘要正文，字数控制在200字以内
                    
                    章节内容：
                    {new_chapter_content}
                    """
                    
                    new_summary = content_model.generate(prompt)
                    summaries[str(chapter_num)] = new_summary
                    
                    # 保存更新后的摘要
                    with open(summary_file, 'w', encoding='utf-8') as f:
                        json.dump(summaries, f, ensure_ascii=False, indent=2)
                    logging.info(f"已更新第 {chapter_num} 章摘要")
                else:
                    logging.warning(f"无法找到重新生成的第 {chapter_num} 章文件，无法更新摘要")
            
        except Exception as e:
            logging.error(f"重新生成第 {chapter_num} 章时出错: {str(e)}")
            raise
        
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
        raise

if __name__ == "__main__":
    main() 