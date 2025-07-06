from openai import OpenAI
import numpy as np
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential
from .base_model import BaseModel
import logging
import json
import time
import os

class OpenAIModel(BaseModel):
    """OpenAI模型实现"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        
        # 增加超时时间，特别是对于本地服务器
        timeout = config.get("timeout", 120)  # 默认120秒
        base_url = config.get("base_url", "https://api.siliconflow.cn/v1")
        
        # 备用API配置
        self.fallback_base_url = "https://api.siliconflow.cn/v1"
        self.fallback_api_key = os.getenv("OPENAI_EMBEDDING_API_KEY", "")  # 使用embedding的API key作为备用
        # 根据当前模型类型选择备用模型
        if "deepgeminiflash" in self.model_name:
            self.fallback_model_name = "deepseek-ai/DeepSeek-R1"  # 使用DeepSeek-R1作为deepgeminiflash的备用
        elif "deepgeminipro" in self.model_name:
            self.fallback_model_name = "Qwen/Qwen3-235B-A22B"  # 使用Qwen作为deepgeminipro的备用
        else:
            self.fallback_model_name = "deepseek-ai/DeepSeek-R1"  # 默认备用模型
        
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=base_url,
            timeout=timeout
        )
        logging.info(f"OpenAI model initialized with base URL: {base_url}, timeout: {timeout}s")
        
    def _create_fallback_client(self):
        """创建备用客户端"""
        if self.fallback_api_key:
            logging.warning(f"切换到备用API: {self.fallback_base_url}, 模型: {self.fallback_model_name}")
            return OpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
                timeout=180  # 备用API使用更长的超时时间
            )
        return None
        
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        try:
            logging.info(f"开始生成文本，模型: {self.model_name}, 提示词长度: {len(prompt)}")
            
            # 如果提示词太长，进行截断
            max_prompt_length = 65536  # 设置最大提示词长度
            if len(prompt) > max_prompt_length:
                logging.warning(f"提示词过长 ({len(prompt)} 字符)，截断到 {max_prompt_length} 字符")
                prompt = prompt[:max_prompt_length]
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise Exception("模型返回空内容")
                
            logging.info(f"文本生成成功，返回内容长度: {len(content)}")
            return content
            
        except Exception as e:
            logging.error(f"OpenAI generation error: {str(e)}")
            
            # 如果是连接错误且配置了备用API，尝试使用备用API
            if ("timeout" in str(e).lower() or "connection" in str(e).lower()) and self.fallback_api_key:
                logging.warning("检测到连接错误，尝试使用备用API...")
                fallback_client = self._create_fallback_client()
                if fallback_client:
                    try:
                        response = fallback_client.chat.completions.create(
                            model=self.fallback_model_name,  # 使用备用模型名称
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens,
                            temperature=0.7
                        )
                        content = response.choices[0].message.content
                        if content is None:
                            raise Exception("备用模型返回空内容")
                            
                        logging.info(f"使用备用API生成成功，返回内容长度: {len(content)}")
                        return content
                    except Exception as fallback_error:
                        logging.error(f"备用API也失败了: {str(fallback_error)}")
            
            if "timeout" in str(e).lower() or "connection" in str(e).lower():
                logging.warning("检测到超时或连接错误，将重试...")
                time.sleep(5)  # 等待5秒后重试
            raise Exception(f"OpenAI generation error: {str(e)}")
            
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        try:
            logging.info(f"Generating embedding for text of length {len(text)}")
            logging.info(f"Using model: {self.model_name}")
            
            # 打印请求信息
            request_data = {
                "model": self.model_name,
                "input": text[:100] + "..." if len(text) > 100 else text  # 只打印前100个字符
            }
            logging.info(f"Request data: {json.dumps(request_data, ensure_ascii=False)}")
            
            try:
                response = self.client.embeddings.create(
                    model=self.model_name,
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
                    raise Exception("Embedding response is empty or invalid")
                    
            except Exception as api_error:
                logging.error(f"API call failed: {str(api_error)}")
                # 检查是否有response属性（OpenAI API错误通常有）
                if hasattr(api_error, 'response') and api_error.response is not None:
                    logging.error(f"Response status: {api_error.response.status_code}")
                    logging.error(f"Response body: {api_error.response.text}")
                raise
                
        except Exception as e:
            logging.error(f"OpenAI embedding error: {str(e)}")
            raise 