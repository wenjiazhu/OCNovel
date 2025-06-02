from openai import OpenAI
import numpy as np
import time
import logging
import os
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embedding():
    """测试硅基流动的Pro/BAAI/bge-m3 embedding模型"""
    try:
        # 加载环境变量
        load_dotenv()
        api_key = os.getenv("OPENAI_EMBEDDING_API_KEY")
        api_base = os.getenv("OPENAI_EMBEDDING_API_BASE")
        
        if not api_key or not api_base:
            raise ValueError("未找到API密钥或基础URL")
        
        # 创建OpenAI客户端
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        # 准备测试文本
        texts = [
            "修真之路，漫漫求索",
            "灵气复苏，万物有灵",
            "丹道至尊，法力无边"
        ]
        
        # 记录开始时间
        start_time = time.time()
        
        # 生成embeddings
        logger.info("正在生成embeddings...")
        response = client.embeddings.create(
            model="Pro/BAAI/bge-m3",
            input=texts
        )
        
        # 提取embeddings
        embeddings = np.array([data.embedding for data in response.data])
        
        # 验证结果
        logger.info(f"\n处理时间: {time.time() - start_time:.2f}秒")
        logger.info(f"嵌入维度: {embeddings.shape}")
        logger.info(f"第一个文本的embedding前5个值: {embeddings[0][:5]}")
        
        # 计算相似度示例
        logger.info("\n计算文本相似度:")
        similarity_01 = np.dot(embeddings[0], embeddings[1]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]))
        similarity_02 = np.dot(embeddings[0], embeddings[2]) / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[2]))
        
        logger.info(f"文本1和文本2的相似度: {similarity_01:.4f}")
        logger.info(f"文本1和文本3的相似度: {similarity_02:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("开始测试硅基流动的Pro/BAAI/bge-m3模型...")
    success = test_embedding()
    logger.info(f"\n测试结果: {'✓ 成功' if success else '✗ 失败'}") 