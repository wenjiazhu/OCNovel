import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import logging
import json
import hashlib
from typing import Dict
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
        os.path.join(config["log_dir"], "novel_generation.log"),
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
    parser = argparse.ArgumentParser(description="长篇网文仿写工具")
    parser.add_argument("--config", default="config.json", help="配置文件路径")
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = Config()
        
        # 设置日志
        setup_logging(config.log_config)
        logging.info("配置加载完成")
        
        # 询问用户是否继续上次的生成
        continue_last = input("是否继续上次的生成？(Y/n) ").strip().lower()
        continue_generation = continue_last != 'n'
        logging.info(f"用户选择{'继续' if continue_generation else '不继续'}上次的生成")
        
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
            
            # 确保知识库被初始化 - 加载一个示例文本
            try:
                knowledge_base.build("示例文本以初始化知识库", force_rebuild=False)
            except Exception as e:
                logging.warning(f"初始化知识库时出错: {e}，尝试读取参考文件")
                # 尝试读取第一个参考文件来初始化知识库
                for file_path in reference_files:
                    if os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            sample_text = f.read(1000)  # 只读取前1000个字符
                            knowledge_base.build(sample_text, force_rebuild=False)
                            logging.info("已使用参考文件样本初始化知识库")
                            break
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
            
            # 强制重新构建知识库（如果需要）
            knowledge_base.build(all_reference_text, force_rebuild=True)
            logging.info("知识库构建完成")
            
            # 保存已导入文件记录
            os.makedirs(config.knowledge_base_config["cache_dir"], exist_ok=True)
            with open(imported_files_record, 'w', encoding='utf-8') as f:
                json.dump(list(imported_files), f, ensure_ascii=False, indent=2)
            logging.info("已更新导入文件记录")
        
        # 创建小说生成器
        generator = NovelGenerator(
            config,
            outline_model,
            content_model,
            knowledge_base
        )
        
        if not continue_generation:
            # 生成角色动力学设定
            logging.info("正在生成角色动力学设定...")
            characters_data = generator.generate_character_dynamics()
            logging.info(f"已生成 {len(characters_data)} 个角色的设定")
            
            # 保存小说架构信息
            generator.save_novel_architecture(characters_data)
            logging.info("小说架构信息已保存")
            
            # 生成新的大纲
            logging.info("正在生成小说大纲...")
            generator.generate_outline(
                config.novel_config["type"],
                config.novel_config["theme"],
                config.novel_config["style"]
            )
            logging.info("大纲生成完成")
        else:
            # 检查是否有已存在的大纲
            outline_file = os.path.join(config.generator_config["output_dir"], "outline.json")
            if not os.path.exists(outline_file):
                logging.info("未找到已有大纲，正在生成新大纲...")
                # 生成角色动力学设定
                logging.info("正在生成角色动力学设定...")
                characters_data = generator.generate_character_dynamics()
                logging.info(f"已生成 {len(characters_data)} 个角色的设定")
                
                # 保存小说架构信息
                generator.save_novel_architecture(characters_data)
                logging.info("小说架构信息已保存")
            
                # 生成新的大纲                
                logging.info("正在生成小说大纲...")                # Call the correct method to generate the initial outline chapters
                generator.generate_outline(
                    config.novel_config["type"],
                    config.novel_config["theme"],
                    config.novel_config["style"]
                )
                logging.info("大纲生成完成")
            else:
                logging.info("已加载现有大纲")
                # 检查大纲章节数是否达到目标
                with open(outline_file, 'r', encoding='utf-8') as f:
                    outline_data = json.load(f)
                    current_chapters = len(outline_data)
                    target_chapters = config.novel_config["target_chapters"]
                    
                    if current_chapters < target_chapters:
                        logging.info(f"大纲未完成（当前 {current_chapters}/{target_chapters} 章），继续生成剩余章节...")
                        generator.generate_outline_chapters(
                            config.novel_config["type"],
                            config.novel_config["theme"],
                            config.novel_config["style"],
                            mode='replace',
                            replace_range=(current_chapters + 1, target_chapters)
                        )
                        logging.info("剩余大纲生成完成")
        
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