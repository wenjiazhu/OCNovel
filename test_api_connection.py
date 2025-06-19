#!/usr/bin/env python3
"""
API连接测试脚本
用于测试本地和在线API的连接状态
"""

import os
import sys
import logging
from dotenv import load_dotenv

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config.ai_config import AIConfig
from src.models.openai_model import OpenAIModel

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_api_connection():
    """测试API连接"""
    try:
        # 加载环境变量
        load_dotenv()
        
        # 初始化AI配置
        ai_config = AIConfig()
        
        # 测试内容生成模型配置
        content_config = ai_config.get_openai_config("content")
        logger.info(f"内容生成模型配置: {content_config}")
        
        # 创建模型实例
        model = OpenAIModel(content_config)
        
        # 测试简单生成
        test_prompt = "请写一个简短的测试段落，不超过50字。"
        logger.info("开始测试API连接...")
        
        response = model.generate(test_prompt)
        logger.info(f"API测试成功！响应: {response}")
        
        return True
        
    except Exception as e:
        logger.error(f"API测试失败: {str(e)}")
        return False

def test_local_api():
    """测试本地API服务器"""
    try:
        import requests
        
        # 测试本地API服务器
        local_url = "http://192.168.31.240:8000/v1/models"
        logger.info(f"测试本地API: {local_url}")
        
        response = requests.get(local_url, timeout=10)
        logger.info(f"本地API响应状态: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("本地API服务器正常")
            return True
        else:
            logger.warning(f"本地API服务器异常，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"本地API测试失败: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("开始API连接测试...")
    
    # 测试本地API
    local_ok = test_local_api()
    
    # 测试完整API连接
    api_ok = test_api_connection()
    
    if local_ok and api_ok:
        logger.info("✅ 所有API连接测试通过")
        return True
    elif api_ok:
        logger.warning("⚠️ 本地API不可用，但备用API正常")
        return True
    else:
        logger.error("❌ API连接测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 