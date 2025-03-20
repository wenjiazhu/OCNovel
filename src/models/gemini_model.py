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
        self.model = genai.GenerativeModel(self.model_name)
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_tokens} if max_tokens else None
            )
            return response.text
        except Exception as e:
            raise Exception(f"Gemini generation error: {str(e)}")
            
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        # 注意：目前Gemini API可能不直接支持文本嵌入
        # 这里可以选择使用其他模型来处理嵌入，或等待Gemini支持
        raise NotImplementedError("Embedding is not supported in Gemini model yet") 