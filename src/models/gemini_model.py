import google.generativeai as genai
import numpy as np
import time
import logging
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .base_model import BaseModel

class GeminiModel(BaseModel):
    """Gemini模型实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        genai.configure(api_key=self.api_key)
        # 如果配置中没有指定模型名称，使用默认的 'gemini-2.5-flash'
        self.model_name = config.get('model_name', 'gemini-2.5-flash')
        # 获取温度参数，默认为0.7
        self.temperature = config.get('temperature', 0.7)
        # 获取超时参数，默认为60秒
        self.timeout = config.get('timeout', 60)
        # 获取重试延迟参数，默认为30秒
        self.retry_delay = config.get('retry_delay', 30)
        self.model = genai.GenerativeModel(self.model_name)
        
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本，使用改进的重试机制"""
        max_retries = 5  # 增加重试次数
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                logging.info(f"Gemini模型调用 (尝试 {attempt + 1}/{max_retries})")
                
                generation_config = {
                    "temperature": self.temperature
                }
                if max_tokens:
                    generation_config["max_output_tokens"] = max_tokens
                    
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options={"timeout": self.timeout}
                )
                
                if response and response.text:
                    logging.info(f"Gemini模型调用成功")
                    return response.text
                else:
                    raise Exception("模型返回空响应")
                    
            except Exception as e:
                last_exception = e
                logging.error(f"Gemini模型调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
                
                if attempt < max_retries - 1:
                    # 使用递增延迟
                    delay = self.retry_delay * (attempt + 1)
                    logging.info(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    logging.error(f"所有重试都失败了，最后一次错误: {str(e)}")
        
        # 如果所有重试都失败，抛出最后一个异常
        raise Exception(f"Gemini generation failed after {max_retries} attempts. Last error: {str(last_exception)}")
            
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        # 注意：目前Gemini API可能不直接支持文本嵌入
        # 这里可以选择使用其他模型来处理嵌入，或等待Gemini支持
        raise NotImplementedError("Embedding is not supported in Gemini model yet") 