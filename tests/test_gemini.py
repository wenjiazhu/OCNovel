import google.generativeai as genai
import time
import logging
import os
from dotenv import load_dotenv

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gemini():
    """测试Gemini模型"""
    try:
        # 加载环境变量
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("未找到Gemini API密钥")
        
        # 配置Gemini
        genai.configure(api_key=api_key)
        
        # 创建模型实例
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # 准备测试提示词
        prompt = """
        你是一个专业的玄幻小说写作助手。请根据以下要求写一段话：
        
        背景：修真世界，灵气复苏
        主题：修炼突破
        风格：热血激昂
        字数：100字左右
        
        请生成内容。
        """
        
        # 记录开始时间
        start_time = time.time()
        
        # 生成内容
        logger.info("正在生成内容...")
        response = model.generate_content(prompt)
        
        # 验证结果
        logger.info(f"\n处理时间: {time.time() - start_time:.2f}秒")
        logger.info("\n生成的内容:")
        logger.info(response.text)
        
        # 测试流式生成
        logger.info("\n测试流式生成...")
        start_time = time.time()
        response = model.generate_content(prompt, stream=True)
        
        logger.info("流式输出内容:")
        full_response = ""
        for chunk in response:
            if chunk.text:
                logger.info(chunk.text)
                full_response += chunk.text
        
        logger.info(f"\n流式生成处理时间: {time.time() - start_time:.2f}秒")
        
        # 测试对话能力
        logger.info("\n测试对话能力...")
        chat = model.start_chat(history=[])
        response = chat.send_message("你是一个专业的玄幻小说写作助手，请简单介绍一下你自己。")
        logger.info(f"助手回复: {response.text}")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("开始测试Gemini模型...")
    success = test_gemini()
    logger.info(f"\n测试结果: {'✓ 成功' if success else '✗ 失败'}") 