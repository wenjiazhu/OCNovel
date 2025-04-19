import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import logging
from typing import Optional, Tuple
from src.config.config import Config
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.knowledge_base.knowledge_base import KnowledgeBase
from src.generators.outline.outline_generator import OutlineGenerator
from src.generators.content.content_generator import ContentGenerator
from src.generators.finalizer.finalizer import NovelFinalizer
from src.generators.common.utils import setup_logging

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

def create_model(model_config: dict):
    """创建AI模型实例"""
    logging.info(f"正在创建模型: {model_config['type']} - {model_config['model_name']}")
    if model_config["type"] == "gemini":
        return GeminiModel(model_config)
    elif model_config["type"] == "openai":
        return OpenAIModel(model_config)
    else:
        raise ValueError(f"不支持的模型类型: {model_config['type']}")

def main():
    # 初始化工作目录
    init_workspace()
    
    parser = argparse.ArgumentParser(description='小说生成工具')
    parser.add_argument('--config', type=str, default="config.json", help='配置文件路径')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 大纲生成命令
    outline_parser = subparsers.add_parser('outline', help='生成小说大纲')
    outline_parser.add_argument('--start', type=int, required=True, help='起始章节')
    outline_parser.add_argument('--end', type=int, required=True, help='结束章节')
    outline_parser.add_argument('--novel-type', type=str, help='小说类型（可选，默认使用配置文件中的设置）')
    outline_parser.add_argument('--theme', type=str, help='主题（可选，默认使用配置文件中的设置）')
    outline_parser.add_argument('--style', type=str, help='写作风格（可选，默认使用配置文件中的设置）')
    outline_parser.add_argument('--extra-prompt', type=str, help='额外提示词')
    
    # 内容生成命令
    content_parser = subparsers.add_parser('content', help='生成章节内容')
    content_parser.add_argument('--start-chapter', type=int, help='起始章节号')
    content_parser.add_argument('--target-chapter', type=int, help='指定要重新生成的章节号')
    content_parser.add_argument('--extra-prompt', type=str, help='额外提示词')
    
    # 定稿处理命令
    finalize_parser = subparsers.add_parser('finalize', help='处理章节定稿')
    finalize_parser.add_argument('--chapter', type=int, required=True, help='要处理的章节号')
    
    # 自动生成命令（包含完整流程）
    auto_parser = subparsers.add_parser('auto', help='自动执行完整生成流程')
    auto_parser.add_argument('--extra-prompt', type=str, help='额外提示词')
    
    args = parser.parse_args()
    
    try:
        # 加载配置
        config = Config(args.config)
        
        # 设置日志
        setup_logging(config.log_config["log_dir"])
        logging.info(f"配置 {args.config} 加载完成")
        
        # 创建模型实例
        logging.info("正在初始化AI模型...")
        content_model = create_model(config.model_config["content_model"])
        outline_model = content_model
        embedding_model = create_model(config.model_config["embedding_model"])
        logging.info("AI模型初始化完成")
        
        # 创建知识库
        logging.info("正在初始化知识库...")
        knowledge_base = KnowledgeBase(
            config.knowledge_base_config,
            embedding_model
        )
        logging.info("知识库初始化完成")
        
        # 命令处理
        if args.command == 'outline':
            logging.info("--- 执行大纲生成任务 ---")
            generator = OutlineGenerator(config, outline_model, knowledge_base)
            
            # 使用命令行参数或配置文件中的设置
            novel_type = args.novel_type or config.novel_config.get("type")
            theme = args.theme or config.novel_config.get("theme")
            style = args.style or config.novel_config.get("style")
            
            success = generator.generate_outline(
                novel_type=novel_type,
                theme=theme,
                style=style,
                mode='replace',
                replace_range=(args.start, args.end),
                extra_prompt=args.extra_prompt
            )
            print("大纲生成成功！" if success else "大纲生成失败，请查看日志文件了解详细信息。")
            
        elif args.command == 'content':
            logging.info("--- 执行内容生成任务 ---")
            generator = ContentGenerator(config, content_model, knowledge_base)
            
            # 处理起始章节和目标章节逻辑
            if args.target_chapter is not None:
                logging.info(f"指定重新生成章节: {args.target_chapter}")
                update_sync_info = False  # 目标章节不更新同步信息
            else:
                update_sync_info = True   # 起始章节需要更新同步信息
                # 如果指定了起始章节，则设置当前章节索引
                if args.start_chapter is not None:
                    logging.info(f"指定起始章节: {args.start_chapter}")
                    generator.current_chapter = args.start_chapter - 1
            
            # 调用内容生成方法
            success = generator.generate_content(
                target_chapter=args.target_chapter,
                external_prompt=args.extra_prompt,
                update_sync_info=update_sync_info
            )
            print("内容生成成功！" if success else "内容生成失败，请查看日志文件了解详细信息。")
            
        elif args.command == 'finalize':
            logging.info("--- 执行章节定稿任务 ---")
            finalizer = NovelFinalizer(config, content_model, knowledge_base)
            success = finalizer.finalize_chapter(args.chapter)
            print("章节定稿处理成功！" if success else "章节定稿处理失败，请查看日志文件了解详细信息。")
            
        elif args.command == 'auto':
            logging.info("--- 执行自动生成流程 ---")
            # 自动流程需要实例化所有生成器
            outline_generator = OutlineGenerator(config, outline_model, knowledge_base)
            content_generator = ContentGenerator(config, content_model, knowledge_base)
            finalizer = NovelFinalizer(config, content_model, knowledge_base)
            
            # 从progress.json获取当前章节进度
            progress_file = os.path.join(config.output_config["output_dir"], "progress.json")
            if os.path.exists(progress_file):
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)
                    start_chapter = progress_data.get("current_chapter", 0) + 1
            else:
                start_chapter = 1
            
            # 从config.json获取目标章节数
            end_chapter = config.novel_config.get("target_chapters")
            if not end_chapter:
                logging.error("配置文件中未找到目标章节数设置")
                return
            
            logging.info(f"自动生成范围：第 {start_chapter} 章到第 {end_chapter} 章")
            
            # 1. 检查并生成大纲
            logging.info("步骤 1: 检查大纲状态...")
            current_outline_count = len(outline_generator.chapter_outlines)
            
            if current_outline_count < end_chapter:
                # 只生成缺失的章节大纲
                logging.info(f"当前大纲章节数 ({current_outline_count}) 小于目标章节数 ({end_chapter})，将生成缺失的章节大纲...")
                outline_success = outline_generator.generate_outline(
                    novel_type=config.novel_config.get("type"),
                    theme=config.novel_config.get("theme"),
                    style=config.novel_config.get("style"),
                    mode='replace',
                    replace_range=(current_outline_count + 1, end_chapter),
                    extra_prompt=args.extra_prompt
                )
                if not outline_success:
                    print("大纲生成失败，停止流程。")
                    return
                print("缺失章节大纲生成成功！")
            else:
                logging.info(f"大纲章节数充足（当前：{current_outline_count}，目标：{end_chapter}），无需生成新大纲。")
                outline_success = True
            
            # 2. 生成内容
            logging.info("步骤 2: 生成内容...")
            content_generator.current_chapter = start_chapter - 1  # 从当前进度的下一章开始
            content_success = content_generator.generate_content(update_sync_info=True)
            if not content_success:
                print("内容生成失败，停止流程。")
                return
            print("内容生成成功！")
            
            # 3. 处理定稿
            logging.info("步骤 3: 处理定稿...")
            finalize_success = True
            for chapter_num in range(start_chapter, end_chapter + 1):
                logging.info(f"处理第 {chapter_num} 章定稿...")
                if not finalizer.finalize_chapter(chapter_num):
                    print(f"第 {chapter_num} 章定稿处理失败。")
                    finalize_success = False
                    break
            if finalize_success:
                print("自动生成流程全部完成！")
            else:
                print("自动生成流程中断，请查看日志文件了解详细信息。")
            
        else:
            parser.print_help()
            
    except FileNotFoundError as e:
        logging.error(f"文件未找到错误: {str(e)}。请检查配置文件路径和配置文件中引用的路径是否正确。", exc_info=True)
    except KeyError as e:
        logging.error(f"配置项缺失错误: 键 '{str(e)}' 在配置文件中未找到。请检查 config.json 文件。", exc_info=True)
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 