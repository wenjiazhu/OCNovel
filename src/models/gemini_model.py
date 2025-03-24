import google.generativeai as genai
import numpy as np
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed
from .base_model import BaseModel

class GeminiModel(BaseModel):
    """Gemini模型实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        genai.configure(api_key=self.api_key)
        # 如果配置中没有指定模型名称，使用默认的 'gemini-2.0-flash'
        self.model_name = config.get('model_name', 'gemini-2.0-flash')
        # 获取温度参数，默认为0.7
        self.temperature = config.get('temperature', 0.7)
        self.model = genai.GenerativeModel(self.model_name)
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        try:
            generation_config = {
                "temperature": self.temperature
            }
            if max_tokens:
                generation_config["max_output_tokens"] = max_tokens
                
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation error: {str(e)}, prompt: {prompt}")
            
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        # 注意：目前Gemini API可能不直接支持文本嵌入
        # 这里可以选择使用其他模型来处理嵌入，或等待Gemini支持
        raise NotImplementedError("Embedding is not supported in Gemini model yet") 