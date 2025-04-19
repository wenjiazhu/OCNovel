import os
import sys
import json
import logging
from src.config.config import Config
from src.models.gemini_model import GeminiModel
from src.models.openai_model import OpenAIModel
from src.knowledge_base.knowledge_base import KnowledgeBase
from src.generators.content.content_generator import ContentGenerator
from src.generators.common.utils import setup_logging

def main():
    """测试同步信息更新功能"""
    # 设置日志
    log_dir = os.path.join("data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    setup_logging(log_dir)
    
    # 加载配置
    config = Config("config.json")
    
    # 创建模型实例
    logging.info("正在初始化AI模型...")
    content_model = None
    if config.model_config["content_model"]["type"] == "gemini":
        content_model = GeminiModel(config.model_config["content_model"])
    elif config.model_config["content_model"]["type"] == "openai":
        content_model = OpenAIModel(config.model_config["content_model"])
    else:
        raise ValueError(f"不支持的模型类型: {config.model_config['content_model']['type']}")
    
    embedding_model = None
    if config.model_config["embedding_model"]["type"] == "gemini":
        embedding_model = GeminiModel(config.model_config["embedding_model"])
    elif config.model_config["embedding_model"]["type"] == "openai":
        embedding_model = OpenAIModel(config.model_config["embedding_model"])
    else:
        raise ValueError(f"不支持的模型类型: {config.model_config['embedding_model']['type']}")
        
    logging.info("AI模型初始化完成")
    
    # 创建知识库
    logging.info("正在初始化知识库...")
    knowledge_base = KnowledgeBase(
        config.knowledge_base_config,
        embedding_model
    )
    logging.info("知识库初始化完成")
    
    # 创建ContentGenerator实例
    generator = ContentGenerator(config, content_model, knowledge_base)
    
    # 模拟完成第20章
    generator.current_chapter = 20
    
    # 测试更新缓存
    logging.info("测试：开始更新缓存...")
    generator._check_and_update_cache(20)
    
    # 检查同步信息文件是否存在
    sync_info_file = generator.sync_info_file
    if os.path.exists(sync_info_file):
        logging.info(f"测试成功：同步信息文件已生成 {sync_info_file}")
        with open(sync_info_file, 'r', encoding='utf-8') as f:
            sync_info = json.load(f)
            logging.info(f"同步信息文件内容预览：{str(sync_info)[:200]}...")
    else:
        logging.error(f"测试失败：同步信息文件未生成 {sync_info_file}")
        
        # 检查是否有调试文件
        debug_file = os.path.join(os.path.dirname(sync_info_file), "sync_info_raw.txt")
        if os.path.exists(debug_file):
            logging.info(f"找到调试文件：{debug_file}")
            with open(debug_file, 'r', encoding='utf-8') as f:
                content = f.read()
                logging.info(f"调试文件内容预览：{content[:200]}...")
        else:
            logging.error(f"未找到调试文件：{debug_file}")

if __name__ == "__main__":
    main() 