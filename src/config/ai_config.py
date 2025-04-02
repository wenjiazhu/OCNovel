import os
from typing import Dict, Any
from dotenv import load_dotenv

class AIConfig:
    """AI模型配置管理类"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # Gemini 配置
        self.gemini_config = {
            "api_key": os.getenv("GEMINI_API_KEY", ""),
            "models": {
                "outline": {
                    "name": "gemini-2.0-flash-thinking-exp-01-21",
                    "temperature": 0.8
                },
                "content": {
                    "name": "gemini-2.0-flash-thinking-exp-01-21",
                    "temperature": 0.7
                }
            }
        }
        
        # OpenAI 配置
        self.openai_config = {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "base_url": os.getenv("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            "models": {
                "embedding": {
                    "name": "Pro/BAAI/bge-m3",
                    "temperature": 0.7,
                    "dimension": 1024
                }
            }
        }
        
        # 验证配置
        self._validate_config()
    
    def _validate_config(self):
        """验证配置是否有效"""
        # 验证 Gemini 配置
        if not self.gemini_config["api_key"]:
            raise ValueError("未设置 GEMINI_API_KEY 环境变量")
            
        # 验证 OpenAI 配置
        if not self.openai_config["api_key"]:
            raise ValueError("未设置 OPENAI_API_KEY 环境变量")
            
        if not self.openai_config["base_url"]:
            raise ValueError("未设置 OPENAI_API_BASE 环境变量")
    
    def get_gemini_config(self, model_type: str = "content") -> Dict[str, Any]:
        """获取 Gemini 模型配置"""
        if model_type not in self.gemini_config["models"]:
            raise ValueError(f"不支持的 Gemini 模型类型: {model_type}")
            
        return {
            "type": "gemini",
            "api_key": self.gemini_config["api_key"],
            "model_name": self.gemini_config["models"][model_type]["name"],
            "temperature": self.gemini_config["models"][model_type]["temperature"]
        }
    
    def get_openai_config(self, model_type: str = "embedding") -> Dict[str, Any]:
        """获取 OpenAI 模型配置"""
        if model_type not in self.openai_config["models"]:
            raise ValueError(f"不支持的 OpenAI 模型类型: {model_type}")
            
        return {
            "type": "openai",
            "api_key": self.openai_config["api_key"],
            "base_url": self.openai_config["base_url"],
            "model_name": self.openai_config["models"][model_type]["name"],
            "temperature": self.openai_config["models"][model_type]["temperature"],
            "dimension": self.openai_config["models"][model_type].get("dimension", 1024)
        }
    
    def get_model_config(self, model_type: str) -> Dict[str, Any]:
        """获取指定类型的模型配置"""
        if model_type.startswith("gemini"):
            return self.get_gemini_config(model_type.split("_")[1])
        elif model_type.startswith("openai"):
            return self.get_openai_config(model_type.split("_")[1])
        else:
            raise ValueError(f"不支持的模型类型: {model_type}") 