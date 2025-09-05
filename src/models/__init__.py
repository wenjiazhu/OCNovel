import logging
import json
import numpy as np
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from .base_model import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed

class OutlineModel(BaseModel):
    """大纲生成模型"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        # 获取实际的模型实例
        if config["type"] == "gemini":
            from .gemini_model import GeminiModel
            self.model = GeminiModel(config)
        elif config["type"] == "openai":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)
        elif config["type"] == "volcengine":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)  # 火山引擎复用OpenAI兼容实现
        else:
            raise ValueError(f"不支持的模型类型: {config['type']}")
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成章节大纲"""
        logging.info(f"使用模型 {self.model_name} 生成大纲")
        try:
            return self.model.generate(prompt, max_tokens)
        except Exception as e:
            logging.error(f"生成大纲时出错: {str(e)}")
            raise
        
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        return self.model.embed(text)

class ContentModel(BaseModel):
    """内容生成模型"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        # 获取实际的模型实例
        if config["type"] == "gemini":
            from .gemini_model import GeminiModel
            self.model = GeminiModel(config)
        elif config["type"] == "openai":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)
        elif config["type"] == "volcengine":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)  # 火山引擎复用OpenAI兼容实现
        else:
            raise ValueError(f"不支持的模型类型: {config['type']}")
        
    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成章节内容"""
        logging.info(f"使用模型 {self.model_name} 生成内容")
        try:
            return self.model.generate(prompt, max_tokens)
        except Exception as e:
            logging.error(f"生成内容时出错: {str(e)}")
            raise
        
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        return self.model.embed(text)

class EmbeddingModel(BaseModel):
    """文本嵌入模型"""
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._validate_config()
        # 获取实际的模型实例
        if config["type"] == "gemini":
            from .gemini_model import GeminiModel
            self.model = GeminiModel(config)
        elif config["type"] == "openai":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)
        elif config["type"] == "volcengine":
            from .openai_model import OpenAIModel
            self.model = OpenAIModel(config)  # 火山引擎复用OpenAI兼容实现
        else:
            raise ValueError(f"不支持的模型类型: {config['type']}")
        
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本（不支持）"""
        raise NotImplementedError("EmbeddingModel不支持文本生成")
        
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        logging.info(f"使用模型 {self.model_name} 生成文本嵌入")
        return self.model.embed(text)

# 导出所有模型类
__all__ = ['BaseModel', 'OutlineModel', 'ContentModel', 'EmbeddingModel'] 