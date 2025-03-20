from abc import ABC, abstractmethod
import numpy as np
from typing import Optional, Dict, Any

class BaseModel(ABC):
    """AI模型基础接口类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key", "")
        self.model_name = config.get("model_name", "")
        
    @abstractmethod
    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文本"""
        pass
        
    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        """获取文本嵌入向量"""
        pass
        
    def _validate_config(self) -> bool:
        """验证配置是否有效"""
        if not self.api_key:
            raise ValueError("API key is required")
        if not self.model_name:
            raise ValueError("Model name is required")
        return True 