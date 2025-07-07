#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备用模型使用示例

这个示例展示了如何使用OCNovel的备用模型功能。
当主模型（如Gemini）不可用时，系统会自动切换到备用模型。
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from config.ai_config import AIConfig
from models.gemini_model import GeminiModel
from models.openai_model import OpenAIModel

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def example_gemini_fallback():
    """Gemini模型备用功能示例"""
    logger.info("=== Gemini模型备用功能示例 ===")
    
    try:
        # 加载环境变量
        load_dotenv()
        
        # 创建AI配置
        ai_config = AIConfig()
        
        # 获取Gemini配置（包含备用模型设置）
        gemini_config = ai_config.get_gemini_config("content")
        
        # 创建Gemini模型实例
        gemini_model = GeminiModel(gemini_config)
        
        # 测试提示词
        prompt = "请写一个简短的玄幻小说开头，100字左右。"
        
        logger.info("开始生成内容...")
        logger.info(f"主模型: {gemini_model.model_name}")
        logger.info(f"备用模型: {gemini_model.fallback_model_name}")
        
        # 生成内容（如果主模型失败，会自动切换到备用模型）
        response = gemini_model.generate(prompt, max_tokens=300)
        
        logger.info("✓ 内容生成成功！")
        logger.info(f"生成内容: {response}")
        
    except Exception as e:
        logger.error(f"示例执行失败: {str(e)}")

def example_openai_fallback():
    """OpenAI模型备用功能示例"""
    logger.info("\n=== OpenAI模型备用功能示例 ===")
    
    try:
        # 加载环境变量
        load_dotenv()
        
        # 创建AI配置
        ai_config = AIConfig()
        
        # 获取OpenAI配置
        openai_config = ai_config.get_openai_config("content")
        
        # 创建OpenAI模型实例
        openai_model = OpenAIModel(openai_config)
        
        # 测试提示词
        prompt = "请写一个简短的科幻小说开头，100字左右。"
        
        logger.info("开始生成内容...")
        logger.info(f"主模型: {openai_model.model_name}")
        logger.info(f"备用模型: {openai_model.fallback_model_name}")
        
        # 生成内容（如果主模型失败，会自动切换到备用模型）
        response = openai_model.generate(prompt, max_tokens=300)
        
        logger.info("✓ 内容生成成功！")
        logger.info(f"生成内容: {response}")
        
    except Exception as e:
        logger.error(f"示例执行失败: {str(e)}")

def main():
    """主函数"""
    logger.info("开始备用模型功能示例...")
    
    # 运行Gemini示例
    example_gemini_fallback()
    
    # 运行OpenAI示例
    example_openai_fallback()
    
    logger.info("\n示例完成！")

if __name__ == "__main__":
    main() 