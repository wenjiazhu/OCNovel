import google.generativeai as genai
import numpy as np
import time
import logging
import os
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .base_model import BaseModel

class GeminiModel(BaseModel):
    """Gemini模型实现，支持官方和OpenAI兼容API分流"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        self.model_name = config.get('model_name', 'gemini-2.5-flash')
        self.temperature = config.get('temperature', 0.7)
        self.timeout = config.get('timeout', 60)
        self.retry_delay = config.get('retry_delay', 30)
        self.max_retries = config.get('max_retries', 5)
        self.max_input_length = config.get('max_input_length', 500000)
        self.api_key = config.get('api_key', None)
        self.base_url = config.get('base_url', None)
        self.is_gemini_official = self.model_name in ["gemini-2.5-pro", "gemini-2.5-flash"]
        
        # 备用模型配置
        self._setup_fallback_config()

        # 初始化模型客户端
        if self.is_gemini_official:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            # OpenAI兼容API客户端
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout
                )
            except ImportError:
                self.openai_client = None
                logging.error("OpenAI库未安装，无法使用OpenAI兼容API模型")

    def _setup_fallback_config(self):
        """设置备用模型配置"""
        fallback_enabled = self.config.get("fallback_enabled", True)
        if not fallback_enabled:
            self.fallback_api_key = ""
            self.fallback_base_url = ""
            self.fallback_model_name = ""
            logging.info("Gemini模型备用功能已禁用")
            return
        self.fallback_base_url = self.config.get("fallback_base_url", "https://api.siliconflow.cn/v1")
        self.fallback_api_key = self.config.get("fallback_api_key", os.getenv("OPENAI_EMBEDDING_API_KEY", ""))
        fallback_models = self.config.get("fallback_models", {
            "flash": "deepseek-ai/DeepSeek-R1",
            "pro": "Qwen/Qwen3-235B-A22B", 
            "default": "deepseek-ai/DeepSeek-R1"
        })
        if "flash" in self.model_name.lower():
            self.fallback_model_name = fallback_models.get("flash", fallback_models["default"])
        elif "pro" in self.model_name.lower():
            self.fallback_model_name = fallback_models.get("pro", fallback_models["default"])
        else:
            self.fallback_model_name = fallback_models["default"]
        logging.info(f"Gemini模型备用配置: {self.fallback_model_name}")

    def _truncate_prompt(self, prompt: str) -> str:
        if len(prompt) <= self.max_input_length:
            return prompt
        logging.warning(f"提示词长度 ({len(prompt)}) 超过限制 ({self.max_input_length})，将进行截断")
        keep_start = int(self.max_input_length * 0.7)
        keep_end = int(self.max_input_length * 0.2)
        truncated = prompt[:keep_start] + "\n\n[内容过长，已截断中间部分...]\n\n" + prompt[-keep_end:]
        logging.info(f"截断后长度: {len(truncated)}")
        return truncated

    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本，支持官方Gemini和OpenAI兼容API分流"""
        last_exception = None
        prompt = self._truncate_prompt(prompt)
        if self.is_gemini_official:
            # 官方Gemini模型调用
            for attempt in range(self.max_retries):
                try:
                    logging.info(f"Gemini模型调用 (尝试 {attempt + 1}/{self.max_retries})")
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
                    if "500" in error_msg or "internal error" in error_msg.lower():
                        delay = self.retry_delay * (attempt + 1) * 2
                    else:
                        delay = self.retry_delay * (attempt + 1)
                    if attempt < self.max_retries - 1:
                        logging.info(f"等待 {delay} 秒后重试...")
                        time.sleep(delay)
                    else:
                        logging.error(f"所有重试都失败了，最后一次错误: {str(e)}")
            # 官方模型失败后尝试 fallback
            if self.fallback_api_key:
                logging.warning("Gemini模型失败，尝试使用备用模型...")
                try:
                    from openai import OpenAI
                    fallback_client = OpenAI(
                        api_key=self.fallback_api_key,
                        base_url=self.fallback_base_url,
                        timeout=self.config.get("fallback_timeout", 180)
                    )
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
            raise Exception(f"All models failed. Last error: {str(last_exception)}")
        else:
            # OpenAI兼容API模型直接调用
            if not self.openai_client:
                raise Exception("OpenAI兼容API客户端未初始化，无法调用自定义模型")
            try:
                logging.info(f"直接调用OpenAI兼容API模型: {self.model_name}")
                response = self.openai_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=self.temperature
                )
                content = response.choices[0].message.content
                if content:
                    logging.info(f"OpenAI兼容API模型调用成功，返回内容长度: {len(content)}")
                    return content
                else:
                    raise Exception("OpenAI兼容API模型返回空响应")
            except Exception as e:
                logging.error(f"OpenAI兼容API模型调用失败: {str(e)}")
                raise

    def embed(self, text: str) -> np.ndarray:
        raise NotImplementedError("Embedding is not supported in Gemini model yet") 