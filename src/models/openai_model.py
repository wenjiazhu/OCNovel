from openai import OpenAI
import numpy as np
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed
from .base_model import BaseModel
import logging
import json

class OpenAIModel(BaseModel):
    """OpenAI模型实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config.get("base_url", "https://api.siliconflow.cn/v1"),
            timeout=60
        )
        logging.info(f"OpenAI model initialized with base URL: {config.get('base_url', 'https://api.siliconflow.cn/v1')}")
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"OpenAI generation error: {str(e)}")
            
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        try:
            logging.info(f"Generating embedding for text of length {len(text)}")
            logging.info(f"Using model: Pro/BAAI/bge-m3")
            
            # 打印请求信息
            request_data = {
                "model": "Pro/BAAI/bge-m3",
                "input": text[:100] + "..." if len(text) > 100 else text  # 只打印前100个字符
            }
            logging.info(f"Request data: {json.dumps(request_data, ensure_ascii=False)}")
            
            try:
                response = self.client.embeddings.create(
                    model="Pro/BAAI/bge-m3",
                    input=text
                )
                
                # 打印响应信息
                if hasattr(response, 'data') and len(response.data) > 0:
                    embedding = np.array(response.data[0].embedding)
                    logging.info(f"Successfully generated embedding with dimension {len(embedding)}")
                    return embedding
                else:
                    logging.error("Response data is empty or invalid")
                    logging.error(f"Response: {response}")
                    return None
                    
            except Exception as api_error:
                logging.error(f"API call failed: {str(api_error)}")
                if hasattr(api_error, 'response'):
                    logging.error(f"Response status: {api_error.response.status_code}")
                    logging.error(f"Response body: {api_error.response.text}")
                raise
                
        except Exception as e:
            logging.error(f"OpenAI embedding error: {str(e)}")
            raise 