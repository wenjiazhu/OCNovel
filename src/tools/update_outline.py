import argparse
import sys
import os
import logging

# 动态添加项目根目录到 Python 路径
# 假设 tools 目录位于 src 目录下，src 位于项目根目录下
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 现在可以安全地导入项目模块
try:
    from src.config.config import Config
    # 假设你的模型导入路径如下，如果不同请修改
    from src.models import OutlineModel, ContentModel, EmbeddingModel
    from src.knowledge_base.knowledge_base import KnowledgeBase
    from src.generators.novel_generator import NovelGenerator
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(f"Project root added to sys.path: {project_root}")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

def setup_logging(log_level_str="WARNING"):
    """配置基本的日志记录到控制台"""
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)]) # 明确指定输出到 stdout
    # 减少第三方库的日志干扰
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # 可以根据需要添加其他库

def main():
    parser = argparse.ArgumentParser(description="手动更新指定范围的小说章节大纲")
    parser.add_argument("--start", type=int, required=True, help="起始章节号 (包含, 从 1 开始)")
    parser.add_argument("--end", type=int, required=True, help="结束章节号 (包含, 从 1 开始)")
    parser.add_argument("--prompt", type=str, default=None, help="用于指导大纲生成的额外提示词")
    parser.add_argument("--config", type=str, default="config.json", help="配置文件路径 (相对于项目根目录)")
    parser.add_argument("--log-level", type=str, default="INFO", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help="日志级别")

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__) # 获取当前模块的 logger

    # 检查参数
    if args.start <= 0 or args.end < args.start:
        logger.error("输入的章节范围无效。起始章节必须大于0，结束章节必须大于等于起始章节。")
        sys.exit(1)

    config_path = os.path.join(project_root, args.config)
    logger.info(f"项目根目录: {project_root}")
    logger.info(f"配置文件路径: {config_path}")

    try:
        # 加载配置
        if not os.path.exists(config_path):
             raise FileNotFoundError(f"配置文件未找到: {config_path}")
        config = Config(config_path)
        logger.info("配置加载成功。")

        # ---- 初始化模型 ----
        # 这里需要根据你的实际模型配置和初始化方式进行调整
        try:
            outline_model_config = config.get_model_config("outline_model")
            content_model_config = config.get_model_config("content_model")
            outline_model = OutlineModel(outline_model_config)
            content_model = ContentModel(content_model_config)
            logger.info("模型初始化成功。")
        except KeyError as e:
             logger.error(f"模型配置错误：缺少键 {e} in models_config 或模型配置名称错误 (例如 'outline_model', 'content_model')")
             sys.exit(1)
        except Exception as e:
             logger.error(f"初始化模型时出错: {e}", exc_info=True)
             sys.exit(1)

        # ---- 初始化知识库 (可选，根据 NovelGenerator 需求) ----
        knowledge_base = None
        if hasattr(config, 'knowledge_base_config'):
            try:
                embedding_model = EmbeddingModel(config.get_model_config("embedding_model"))
                knowledge_base = KnowledgeBase(config.knowledge_base_config, embedding_model)
                logger.info("知识库初始化成功。")
            except KeyError as e:
                 logger.error(f"模型配置错误：缺少键 {e} in models_config 或模型配置名称错误 (例如 'outline_model', 'content_model')")
                 sys.exit(1)
            except Exception as kb_err:
                 logger.warning(f"初始化 KnowledgeBase 时出错: {kb_err}。将不使用知识库功能。")
        else:
            logger.warning("配置文件中缺少 'knowledge_base_config'，将不使用知识库功能。")


        # ---- 初始化 NovelGenerator ----
        try:
            novel_generator = NovelGenerator(config, outline_model, content_model, knowledge_base)
            logger.info("NovelGenerator 初始化完成。")
            logger.info(f"当前加载的大纲总章数: {len(novel_generator.chapter_outlines)}")
        except Exception as e:
             logger.error(f"初始化 NovelGenerator 时出错: {e}", exc_info=True)
             sys.exit(1)

        # 检查现有大纲长度是否足够覆盖替换范围
        current_outline_length = len(novel_generator.chapter_outlines)
        if args.end > current_outline_length:
            logger.error(f"指定的结束章节 {args.end} 超出当前大纲总数 {current_outline_length}。无法执行替换。")
            sys.exit(1)

        # 获取小说基本信息
        novel_type = config.novel_config.get("type", "未知类型")
        theme = config.novel_config.get("theme", "未知主题")
        style = config.novel_config.get("style", "未知风格")

        # ---- 调用更新方法 ----
        logger.info(f"准备更新章节 {args.start} 到 {args.end} 的大纲...")
        if args.prompt:
            logger.info(f"使用额外提示词: '{args.prompt[:100]}{'...' if len(args.prompt)>100 else ''}'")

        try:
            # --- 调用修改后的 generate_outline ---
            novel_generator.generate_outline(
                novel_type=novel_type,
                theme=theme,
                style=style,
                mode='replace',
                replace_range=(args.start, args.end),
                extra_prompt=args.prompt
                # batch_size 可以考虑也作为参数传入，或使用 config 中的值
            )
            # --- 结束调用 ---
            logger.info("大纲更新操作执行完毕。请查看日志了解详细结果。")

        except Exception as e:
             logger.error(f"调用 generate_outline 时发生错误: {e}", exc_info=True)
             sys.exit(1)

    except FileNotFoundError as e:
        logger.error(f"文件未找到错误: {e}")
        sys.exit(1)
    except KeyError as e:
         logger.error(f"配置错误：缺少必要的键 {e}")
         sys.exit(1)
    except Exception as e:
        logger.error(f"执行过程中发生未预料的错误: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 