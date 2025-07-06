import google.generativeai as genai
import numpy as np
import time
import logging
import os
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
        # 获取最大重试次数，默认为5次
        self.max_retries = config.get('max_retries', 5)
        # 获取最大输入长度，默认为500000字符
        self.max_input_length = config.get('max_input_length', 500000)
        self.model = genai.GenerativeModel(self.model_name)
        
        # 备用模型配置
        self._setup_fallback_config()
        
    def _setup_fallback_config(self):
        """设置备用模型配置"""
        # 从配置中获取备用模型设置
        fallback_enabled = self.config.get("fallback_enabled", True)
        if not fallback_enabled:
            self.fallback_api_key = ""
            self.fallback_base_url = ""
            self.fallback_model_name = ""
            logging.info("Gemini模型备用功能已禁用")
            return
            
        # 备用API配置 - 使用OpenAI兼容的API
        self.fallback_base_url = self.config.get("fallback_base_url", "https://api.siliconflow.cn/v1")
        self.fallback_api_key = self.config.get("fallback_api_key", os.getenv("OPENAI_EMBEDDING_API_KEY", ""))
        
        # 从配置中获取备用模型映射
        fallback_models = self.config.get("fallback_models", {
            "flash": "deepseek-ai/DeepSeek-R1",
            "pro": "Qwen/Qwen3-235B-A22B", 
            "default": "deepseek-ai/DeepSeek-R1"
        })
        
        # 根据当前Gemini模型类型选择备用模型
        if "flash" in self.model_name.lower():
            self.fallback_model_name = fallback_models.get("flash", fallback_models["default"])
        elif "pro" in self.model_name.lower():
            self.fallback_model_name = fallback_models.get("pro", fallback_models["default"])
        else:
            self.fallback_model_name = fallback_models["default"]
            
        logging.info(f"Gemini模型备用配置: {self.fallback_model_name}")
        
    def _create_fallback_client(self):
        """创建备用客户端（OpenAI兼容）"""
        if not self.fallback_api_key:
            return None
            
        try:
            from openai import OpenAI
            fallback_timeout = self.config.get("fallback_timeout", 180)
            logging.warning(f"切换到备用API: {self.fallback_base_url}, 模型: {self.fallback_model_name}")
            return OpenAI(
                api_key=self.fallback_api_key,
                base_url=self.fallback_base_url,
                timeout=fallback_timeout
            )
        except ImportError:
            logging.error("OpenAI库未安装，无法使用备用模型")
            return None
        
    def _truncate_prompt(self, prompt: str) -> str:
        """截断过长的提示词"""
        if len(prompt) <= self.max_input_length:
            return prompt
            
        logging.warning(f"提示词长度 ({len(prompt)}) 超过限制 ({self.max_input_length})，将进行截断")
        
        # 保留开头和结尾的重要信息
        keep_start = int(self.max_input_length * 0.7)  # 保留70%的开头
        keep_end = int(self.max_input_length * 0.2)    # 保留20%的结尾
        
        truncated = prompt[:keep_start] + "\n\n[内容过长，已截断中间部分...]\n\n" + prompt[-keep_end:]
        
        logging.info(f"截断后长度: {len(truncated)}")
        return truncated
        
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本，使用改进的重试机制和备用模型"""
        last_exception = None
        
        # 检查并截断过长的提示词
        prompt = self._truncate_prompt(prompt)
        
        # 首先尝试使用Gemini模型
        for attempt in range(self.max_retries):
            try:
                logging.info(f"Gemini模型调用 (尝试 {attempt + 1}/{self.max_retries})")
                
                # 创建生成配置
                generation_config = {"temperature": self.temperature}
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
                error_msg = str(e)
                logging.error(f"Gemini模型调用失败 (尝试 {attempt + 1}/{self.max_retries}): {error_msg}")
                
                # 特殊处理500错误
                if "500" in error_msg or "internal error" in error_msg.lower():
                    logging.warning("检测到500内部错误，将使用更长的延迟时间")
                    delay = self.retry_delay * (attempt + 1) * 2  # 500错误使用更长的延迟
                else:
                    delay = self.retry_delay * (attempt + 1)
                
                if attempt < self.max_retries - 1:
                    logging.info(f"等待 {delay} 秒后重试...")
                    time.sleep(delay)
                else:
                    logging.error(f"所有重试都失败了，最后一次错误: {str(e)}")
        
        # 如果Gemini模型所有重试都失败，尝试使用备用模型
        if self.fallback_api_key:
            logging.warning("Gemini模型失败，尝试使用备用模型...")
            fallback_client = self._create_fallback_client()
            if fallback_client:
                try:
                    logging.info(f"使用备用模型: {self.fallback_model_name}")
                    response = fallback_client.chat.completions.create(
                        model=self.fallback_model_name,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=self.temperature
                    )
                    
                    content = response.choices[0].message.content
                    if content:
                        logging.info(f"备用模型调用成功，返回内容长度: {len(content)}")
                        return content
                    else:
                        raise Exception("备用模型返回空响应")
                        
                except Exception as fallback_error:
                    logging.error(f"备用模型也失败了: {str(fallback_error)}")
                    last_exception = fallback_error
        
        # 如果所有模型都失败，抛出最后一个异常
        raise Exception(f"All models failed. Last error: {str(last_exception)}")
            
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        # 注意：目前Gemini API可能不直接支持文本嵌入
        # 这里可以选择使用其他模型来处理嵌入，或等待Gemini支持
        raise NotImplementedError("Embedding is not supported in Gemini model yet") 