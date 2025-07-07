import sys
import os
import json
import shutil
import subprocess
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

    # 仿写命令
    imitate_parser = subparsers.add_parser('imitate', help='根据指定的风格范文仿写文本')
    imitate_parser.add_argument('--style-source', type=str, required=True, help='作为风格参考的源文件路径')
    imitate_parser.add_argument('--input-file', type=str, required=True, help='需要进行仿写的原始文本文件路径')
    imitate_parser.add_argument('--output-file', type=str, required=True, help='仿写结果的输出文件路径')
    imitate_parser.add_argument('--extra-prompt', type=str, help='额外的仿写要求')
    
    args = parser.parse_args()
    
    # --- 检查并可能生成默认配置文件 ---
    config_path = args.config
    if config_path == "config.json" and not os.path.exists(config_path):
        print(f"默认配置文件 '{config_path}' 不存在。")
        try:
            user_theme = input("请输入您的小说主题以生成新的配置文件: ")
            if not user_theme:
                print("未输入主题，无法生成配置文件。程序退出。")
                sys.exit(1)

            # 获取 generate_config.py 脚本的绝对路径
            script_dir = os.path.dirname(os.path.abspath(__file__))
            generate_script_path = os.path.join(script_dir, "src", "tools", "generate_config.py")

            if not os.path.exists(generate_script_path):
                print(f"错误: 配置文件生成脚本 '{generate_script_path}' 未找到。程序退出。")
                sys.exit(1)

            print(f"正在调用脚本 '{os.path.basename(generate_script_path)}' 生成配置文件 '{config_path}'...")
            # 使用 sys.executable 确保使用当前环境的 Python 解释器
            # 将主题通过 stdin 传递给脚本
            process = subprocess.run(
                [sys.executable, generate_script_path],
                input=user_theme,
                text=True,
                capture_output=True,
                check=False # 手动检查返回码
            )

            # 打印脚本的输出 (stdout 和 stderr) 以便调试
            print("\n--- 配置文件生成脚本输出 ---")
            if process.stdout:
                print(process.stdout.strip())
            if process.stderr:
                print(f"错误输出:\n{process.stderr.strip()}")
            print("--- 脚本输出结束 ---\n")


            if process.returncode != 0:
                print(f"自动生成配置文件失败。请检查上述错误信息。程序退出。")
                sys.exit(1)
            elif not os.path.exists(config_path):
                 print(f"脚本执行成功，但配置文件 '{config_path}' 仍然不存在。请检查脚本逻辑。程序退出。")
                 sys.exit(1)
            else:
                print(f"配置文件 '{config_path}' 已成功生成。")
                # 继续执行程序，将使用新生成的配置文件

        except Exception as e:
            print(f"尝试生成配置文件时发生意外错误: {e}")
            sys.exit(1)

    elif not os.path.exists(config_path):
         print(f"错误: 指定的配置文件 '{config_path}' 未找到。程序退出。")
         sys.exit(1)


    # 后续代码保持不变，加载配置等
    try:
        # 加载配置 (现在确保 config_path 存在，无论是原有的还是新生成的)
        config = Config(config_path)
        
        # 设置日志
        setup_logging(config.log_config["log_dir"])
        logging.info(f"配置 {config_path} 加载完成") # 使用 config_path 而非 args.config
        
        # --- 获取小说标题并创建专属备份目录 ---
        novel_title = config.novel_config.get("title")
        if not novel_title:
            logging.error("配置文件 'novel_config' 中缺少 'title' 键，无法创建专属输出目录。")
            novel_title = "default_novel"
            logging.warning(f"将使用默认小说标题: {novel_title}")

        safe_novel_title = novel_title

        base_output_dir = config.output_config.get("output_dir", "data/output")
        novel_output_dir = os.path.join(base_output_dir, safe_novel_title)
        os.makedirs(novel_output_dir, exist_ok=True)
        logging.info(f"小说专属输出目录已创建/确认存在: {novel_output_dir}")

        # 复制配置文件快照
        config_snapshot_path = os.path.join(novel_output_dir, "config_snapshot.json")
        try:
            # 复制加载时使用的 config_path
            shutil.copy2(config_path, config_snapshot_path)
            logging.info(f"配置文件快照已保存至: {config_snapshot_path}")
        except Exception as e:
            logging.error(f"复制配置文件快照失败: {e}", exc_info=True)
        
        # 创建模型实例
        logging.info("正在初始化AI模型...")
        content_model = create_model(config.model_config["content_model"])
        outline_model = create_model(config.model_config["outline_model"])
        embedding_model = create_model(config.model_config["embedding_model"])
        logging.info("AI模型初始化完成")
        
        # 创建知识库
        logging.info("正在初始化知识库...")
        knowledge_base = KnowledgeBase(
            config.knowledge_base_config,
            embedding_model
        )
        logging.info("知识库初始化完成")
        
        # --- 实例化 Finalizer ---
        # Instantiate Finalizer early as ContentGenerator might need it
        finalizer = NovelFinalizer(config, content_model, knowledge_base)
        logging.info("NovelFinalizer 初始化完成")
        
        # 命令处理
        if args.command == 'outline':
            logging.info("--- 执行大纲生成任务 ---")
            generator = OutlineGenerator(config, outline_model, knowledge_base, content_model)
            
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
            # Pass finalizer instance to ContentGenerator
            generator = ContentGenerator(config, content_model, knowledge_base, finalizer=finalizer)
            
            # 处理起始章节和目标章节逻辑
            target_chapter_to_generate = None
            if args.target_chapter is not None:
                logging.info(f"指定重新生成章节: {args.target_chapter}")
                target_chapter_to_generate = args.target_chapter
            else:
                # 如果指定了起始章节，则设置当前章节索引
                if args.start_chapter is not None:
                    # Validate start_chapter against loaded outline length if possible?
                    # For now, trust the input or let ContentGenerator handle invalid index later.
                    if args.start_chapter > 0 :
                       logging.info(f"指定起始章节: {args.start_chapter}")
                       generator.current_chapter = args.start_chapter - 1
                       # Save the potentially updated starting point?
                       # generator._save_progress() # Optional: save if you want '--start-chapter' to persist
                    else:
                       logging.warning(f"指定的起始章节 ({args.start_chapter}) 无效，将从上次进度开始。")
                else:
                    # No target, no start chapter -> generate remaining from current progress
                    logging.info(f"未指定目标或起始章节，将从进度文件记录的下一章 ({generator.current_chapter + 1}) 开始生成。")
            
            # 调用内容生成方法 (removed update_sync_info)
            success = generator.generate_content(
                target_chapter=target_chapter_to_generate,
                external_prompt=args.extra_prompt
            )
            print("内容生成成功！" if success else "内容生成失败，请查看日志文件了解详细信息。")
            
        elif args.command == 'finalize':
            # Finalize command remains for manually finalizing a chapter if needed
            logging.info("--- 执行章节定稿任务 ---")
            # Finalizer is already instantiated
            success = finalizer.finalize_chapter(args.chapter)
            print("章节定稿处理成功！" if success else "章节定稿处理失败，请查看日志文件了解详细信息。")
            
        elif args.command == 'auto':
            # 重新初始化日志系统，并清理旧日志
            setup_logging(config.log_config["log_dir"], clear_logs=True)
            logging.info("--- 执行自动生成流程 ---")
            # 自动流程需要实例化所有生成器
            outline_generator = OutlineGenerator(config, outline_model, knowledge_base, content_model)
            # Pass finalizer instance to ContentGenerator
            content_generator = ContentGenerator(config, content_model, knowledge_base, finalizer=finalizer)
            # finalizer is already instantiated
            
            # 从 summary.json 获取当前章节进度
            summary_file = os.path.join(base_output_dir, "summary.json")
            start_chapter_index = 0  # Default to 0 (start from chapter 1)
            if os.path.exists(summary_file):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                        # 获取最大的章节号作为当前进度
                        chapter_numbers = [int(k) for k in summary_data.keys() if k.isdigit()]
                        start_chapter_index = max(chapter_numbers) if chapter_numbers else 0
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logging.warning(f"读取或解析摘要文件 {summary_file} 失败: {e}. 将从头开始。")
                    start_chapter_index = 0  # Reset on error
            
            content_generator.current_chapter = start_chapter_index # Set generator's start point
            actual_start_chapter_num = start_chapter_index + 1
            
            # 从config.json获取目标章节数
            end_chapter = config.novel_config.get("target_chapters")
            if not end_chapter or not isinstance(end_chapter, int) or end_chapter <= 0:
                logging.error("配置文件中未找到有效的目标章节数设置 (target_chapters)")
                return
            
            logging.info(f"自动生成范围：从第 {actual_start_chapter_num} 章开始，目标共 {end_chapter} 章")
            
            # 1. 检查并生成大纲
            logging.info("步骤 1: 检查并生成大纲...")
            outline_generator._load_outline() # Ensure outline is loaded
            current_outline_count = len(outline_generator.chapter_outlines)

            if current_outline_count < end_chapter:
                logging.info(f"当前大纲章节数 ({current_outline_count}) 小于目标章节数 ({end_chapter})，将生成缺失的大纲...")
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
                # Reload outline in content_generator after modification
                # content_generator._load_outline() # Moved outside
            else:
                logging.info(f"大纲章节数充足（当前：{current_outline_count}，目标：{end_chapter}），无需生成新大纲。")

            # Ensure content_generator always loads the outline before proceeding
            content_generator._load_outline()

            # Check if start chapter is already beyond target
            if actual_start_chapter_num > end_chapter:
                 logging.info(f"起始章节 ({actual_start_chapter_num}) 已超过目标章节 ({end_chapter})，无需生成内容。")
                 content_success = True # Nothing to do, considered success
            else:
                 # 2. 生成内容 (ContentGenerator now handles finalization internally)
                 logging.info(f"步骤 2: 生成内容 (包含定稿)，从第 {actual_start_chapter_num} 章开始...")
                 # The generate_content call will handle chapters from generator.current_chapter up to the end of the outline
                 # We rely on the loaded outline length to determine the end point.
                 # We need to ensure the outline actually covers up to end_chapter
                 # Now that content_generator._load_outline() is guaranteed to run, this check should be correct
                 if len(content_generator.chapter_outlines) < end_chapter:
                      logging.error(f"错误：大纲加载后章节数 ({len(content_generator.chapter_outlines)}) 仍小于目标章节数 ({end_chapter})。")
                      return

                 # Call generate_content without target_chapter to process remaining chapters from current_chapter
                 content_success = content_generator.generate_content(
                      external_prompt=args.extra_prompt
                      # Removed update_sync_info
                 )

                 if not content_success:
                     print("内容生成或定稿过程中失败，停止流程。")
                     return
                 print("内容生成及定稿成功！")

            print("自动生成流程全部完成！")

        elif args.command == 'imitate':
            logging.info("--- 执行仿写任务 ---")
            try:
                # 1. 读取输入文件
                logging.info(f"读取风格源文件: {args.style_source}")
                with open(args.style_source, 'r', encoding='utf-8') as f:
                    style_text = f.read()

                logging.info(f"读取原始文本文件: {args.input_file}")
                with open(args.input_file, 'r', encoding='utf-8') as f:
                    input_text = f.read()

                # 2. 初始化模型（改为 imitation_model 配置）
                logging.info("初始化AI模型...")
                imitation_model_config = config.get_imitation_model()
                if imitation_model_config["type"] == "gemini":
                    imitation_model = GeminiModel(imitation_model_config)
                elif imitation_model_config["type"] == "openai":
                    imitation_model = OpenAIModel(imitation_model_config)
                else:
                    raise ValueError(f"不支持的模型类型: {imitation_model_config['type']}")

                # 3. 创建一个临时的、基于风格范文的知识库
                logging.info("为风格范文动态构建临时知识库...")
                # 创建一个临时的知识库配置，指向一个专用的仿写缓存目录
                imitate_kb_config = config.knowledge_base_config.copy()
                imitate_kb_config["cache_dir"] = os.path.join(config.knowledge_base_config["cache_dir"], "imitation_cache")
                style_kb = KnowledgeBase(imitate_kb_config, embedding_model)
                style_kb.build(style_text, force_rebuild=False)
                logging.info("临时知识库构建完成。")

                # 4. 从风格知识库中检索与原始文本最相关的片段作为范例
                logging.info("从风格知识库中检索最相关的风格范例...")
                style_examples = style_kb.search(input_text, k=5)

                # 5. 导入并使用新的仿写提示词
                from src.generators.prompts import get_imitation_prompt
                prompt = get_imitation_prompt(
                    original_text=input_text,
                    style_examples=style_examples,
                    extra_prompt=args.extra_prompt
                )

                # 6. 调用模型生成仿写内容前，打印实际模型名
                logging.info(f"仿写实际调用模型: {imitation_model_config.get('model_name', imitation_model_config)}")
                logging.info("调用AI模型进行仿写...")
                imitated_content = imitation_model.generate(prompt)

                # 7. 保存结果
                logging.info(f"仿写完成，保存结果到: {args.output_file}")
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(imitated_content)
                print(f"仿写成功！结果已保存至 {args.output_file}")

            except FileNotFoundError as e:
                logging.error(f"文件未找到: {e}", exc_info=True)
                print(f"错误：文件未找到 - {e}")
            except Exception as e:
                logging.error(f"执行仿写任务时出错: {e}", exc_info=True)
                print(f"错误：执行仿写任务失败，请查看日志。")
            
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