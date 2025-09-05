import os
from typing import Dict, Any
from dotenv import load_dotenv

class AIConfig:
    """AI模型配置管理类"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()

        # OpenAI 配置（提前定义）
        self.openai_config = {
            "retry_delay": float(os.getenv("OPENAI_RETRY_DELAY", "10")),  # 默认 10 秒
            "models": {
                "embedding": {
                    "name": "Qwen/Qwen3-Embedding-0.6B",
                    "temperature": 0.7,
                    "dimension": 1024,
                    "api_key": os.getenv("OPENAI_EMBEDDING_API_KEY", ""),
                    "base_url": os.getenv("OPENAI_EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1"),
                    "timeout": int(os.getenv("OPENAI_EMBEDDING_TIMEOUT", "60"))
                },
                "outline": {
                    "name": "deepgeminipro",  # 使用本地服务器支持的模型
                    "temperature": 1.0,
                    "api_key": os.getenv("OPENAI_OUTLINE_API_KEY", ""),
                    "base_url": os.getenv("OPENAI_OUTLINE_API_BASE", "https://api.siliconflow.cn/v1"),
                    "timeout": int(os.getenv("OPENAI_OUTLINE_TIMEOUT", "120"))
                },
                "content": {
                    "name": "deepgeminiflash",  # 使用deepclaude接口的模型
                    "temperature": 0.7,
                    "api_key": os.getenv("OPENAI_CONTENT_API_KEY", ""),
                    "base_url": os.getenv("OPENAI_CONTENT_API_BASE", "https://api.siliconflow.cn/v1"),
                    "timeout": int(os.getenv("OPENAI_CONTENT_TIMEOUT", "180"))  # 内容生成需要更长时间
                },
                "reranker": {
                    "name": os.getenv("OPENAI_RERANKER_MODEL", "Qwen/Qwen3-Reranker-0.6B"),
                    "api_key": os.getenv("OPENAI_EMBEDDING_API_KEY", ""),
                    "base_url": os.getenv("OPENAI_EMBEDDING_API_BASE", "https://api.siliconflow.cn/v1"),
                    "use_fp16": os.getenv("OPENAI_RERANKER_USE_FP16", "True") == "True",
                    "timeout": int(os.getenv("OPENAI_EMBEDDING_TIMEOUT", "60"))
                }
            }
        }
        # Gemini 配置
        self.gemini_config = {
            "api_key": os.getenv("GEMINI_API_KEY", ""),
            "retry_delay": float(os.getenv("GEMINI_RETRY_DELAY", "30")),  # 默认 30 秒
            "max_retries": int(os.getenv("GEMINI_MAX_RETRIES", "5")),  # 默认 5 次
            "max_input_length": int(os.getenv("GEMINI_MAX_INPUT_LENGTH", "500000")),  # 默认 500000 字符
            "timeout": int(os.getenv("GEMINI_TIMEOUT", "60")),  # 默认 60 秒
            # 备用模型配置
            "fallback": {
                "enabled": os.getenv("GEMINI_FALLBACK_ENABLED", "True") == "True",  # 默认启用备用模型
                "api_key": os.getenv("OPENAI_EMBEDDING_API_KEY", ""),  # 使用embedding的API key作为备用
                "base_url": os.getenv("GEMINI_FALLBACK_BASE_URL", "https://api.siliconflow.cn/v1"),
                "timeout": int(os.getenv("GEMINI_FALLBACK_TIMEOUT", "120")),  # 备用API使用更长的超时时间
                "models": {
                    "flash": "moonshotai/Kimi-K2-Instruct",  # flash模型的备用
                    "pro": "Qwen/Qwen3-235B-A22B-Thinking-2507",  # pro模型的备用
                    "default": "deepseek-ai/DeepSeek-V3.1"  # 默认备用模型
                }
            },
            "models": {
                "outline": {
                    "name": "gemini-2.5-pro",
                    "temperature": 1.0
                },
                "content": {
                    "name": "gemini-2.5-flash",
                    "temperature": 0.7
                }
            }
        }
        # 火山引擎DeepSeek-V3.1配置
        self.volcengine_config = {
            "api_key": os.getenv("VOLCENGINE_API_KEY", ""),
            "api_endpoint": os.getenv("VOLCENGINE_API_ENDPOINT", 
                                     "https://ark.cn-beijing.volces.com/api/v3"),
            "thinking_enabled": os.getenv("VOLCENGINE_THINKING_ENABLED", "true").lower() == "true",
            "timeout": int(os.getenv("VOLCENGINE_TIMEOUT", "120")),
            "max_tokens": int(os.getenv("VOLCENGINE_MAX_TOKENS", "8192")),
            "retry_delay": float(os.getenv("VOLCENGINE_RETRY_DELAY", "15")),
            "max_retries": int(os.getenv("VOLCENGINE_MAX_RETRIES", "3")),
            # 模型配置
            "models": {
                "outline": {
                    "name": os.getenv("VOLCENGINE_OUTLINE_MODEL_ID", "deepseek-v3-1-250821"),
                    "temperature": float(os.getenv("VOLCENGINE_OUTLINE_TEMPERATURE", "1.0"))
                },
                "content": {
                    "name": os.getenv("VOLCENGINE_CONTENT_MODEL_ID", "deepseek-v3-1-250821"),
                    "temperature": float(os.getenv("VOLCENGINE_CONTENT_TEMPERATURE", "0.7"))
                }
            },
            # 备用模型配置
            "fallback": {
                "enabled": os.getenv("VOLCENGINE_FALLBACK_ENABLED", "true").lower() == "true",
                "provider": "openai",  # 备用到OpenAI兼容模型
                "model_name": "deepseek-ai/DeepSeek-V3.1",
                "api_key": os.getenv("OPENAI_EMBEDDING_API_KEY", ""),  # 使用嵌入模型的API密钥作为备用
                "base_url": "https://api.siliconflow.cn/v1"  # 使用硅基流动的API地址
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
        for model_type, model_config in self.openai_config["models"].items():
            if not model_config["api_key"]:
                raise ValueError(f"未设置 OPENAI_{model_type.upper()}_API_KEY 环境变量")
            if not model_config["base_url"]:
                raise ValueError(f"未设置 OPENAI_{model_type.upper()}_API_BASE 环境变量")
                
        # 验证火山引擎配置（仅在api_key存在时验证）
        if self.volcengine_config["api_key"]:
            if not self.volcengine_config["api_endpoint"]:
                raise ValueError("火山引擎API Key已设置但缺少API端点配置")
            # 验证模型配置
            for model_type in ["outline", "content"]:
                if not self.volcengine_config["models"][model_type]["name"]:
                    raise ValueError(f"火山引擎{model_type}模型配置缺少模型ID")
    
    def get_gemini_config(self, model_type: str = "content") -> Dict[str, Any]:
        """获取 Gemini 模型配置"""
        if model_type not in self.gemini_config["models"]:
            raise ValueError(f"不支持的 Gemini 模型类型: {model_type}")
            
        config = {
            "type": "gemini",
            "api_key": self.gemini_config["api_key"],
            "model_name": self.gemini_config["models"][model_type]["name"],
            "temperature": self.gemini_config["models"][model_type]["temperature"],
            "retry_delay": self.gemini_config["retry_delay"],
            "max_retries": self.gemini_config["max_retries"],
            "max_input_length": self.gemini_config["max_input_length"],
            "timeout": self.gemini_config["timeout"]
        }
        
        # 添加备用模型配置
        if self.gemini_config["fallback"]["enabled"]:
            config.update({
                "fallback_enabled": True,
                "fallback_api_key": self.gemini_config["fallback"]["api_key"],
                "fallback_base_url": self.gemini_config["fallback"]["base_url"],
                "fallback_timeout": self.gemini_config["fallback"]["timeout"],
                "fallback_models": self.gemini_config["fallback"]["models"]
            })
        else:
            config["fallback_enabled"] = False
            
        return config
    
    def get_volcengine_config(self, model_type: str = "content") -> Dict[str, Any]:
        """获取火山引擎模型配置"""
        if not self.volcengine_config["api_key"]:
            raise ValueError("未设置 VOLCENGINE_API_KEY 环境变量")
            
        if model_type not in self.volcengine_config["models"]:
            raise ValueError(f"不支持的火山引擎模型类型: {model_type}")
            
        model_config = self.volcengine_config["models"][model_type]
        
        config = {
            "type": "volcengine",
            "api_key": self.volcengine_config["api_key"],
            "base_url": self.volcengine_config["api_endpoint"],
            "model_name": model_config["name"],
            "thinking_enabled": self.volcengine_config["thinking_enabled"],
            "temperature": model_config["temperature"],
            "max_tokens": self.volcengine_config["max_tokens"],
            "timeout": self.volcengine_config["timeout"],
            "retry_delay": self.volcengine_config["retry_delay"],
            "max_retries": self.volcengine_config["max_retries"]
        }
        
        # 添加备用模型配置
        if self.volcengine_config["fallback"]["enabled"]:
            config.update({
                "fallback_enabled": True,
                "fallback_api_key": self.volcengine_config["fallback"]["api_key"],
                "fallback_base_url": self.volcengine_config["fallback"]["base_url"],
                "fallback_model_name": self.volcengine_config["fallback"]["model_name"]
            })
        else:
            config["fallback_enabled"] = False
            
        return config
    
    def get_openai_config(self, model_type: str = "embedding") -> Dict[str, Any]:
        """获取 OpenAI 模型配置"""
        if model_type not in self.openai_config["models"]:
            raise ValueError(f"不支持的 OpenAI 模型类型: {model_type}")
        model_config = self.openai_config["models"][model_type]
        # 针对reranker类型，返回专用字段
        if model_type == "reranker":
            return {
                "type": "openai",
                "api_key": model_config["api_key"],
                "base_url": model_config["base_url"],
                "model_name": model_config["name"],
                "use_fp16": model_config.get("use_fp16", True),
                "retry_delay": self.openai_config["retry_delay"],
                "timeout": model_config.get("timeout", 60)
            }
        return {
            "type": "openai",
            "api_key": model_config["api_key"],
            "base_url": model_config["base_url"],
            "model_name": model_config["name"],
            "temperature": model_config["temperature"],
            "dimension": model_config.get("dimension", 1024),
            "retry_delay": self.openai_config["retry_delay"],
            "timeout": model_config.get("timeout", 60)
        }
    
    def get_model_config(self, model_type: str) -> Dict[str, Any]:
        """获取指定类型的模型配置"""
        if model_type.startswith("gemini"):
            return self.get_gemini_config(model_type.split("_")[1])
        elif model_type.startswith("openai"):
            return self.get_openai_config(model_type.split("_")[1])
        else:
            raise ValueError(f"不支持的模型类型: {model_type}")

    def get_model_config_by_purpose(self, model_purpose: str) -> Dict[str, Any]:
        """根据用途获取模型配置"""
        # 这个方法需要外部传入config和ai_config实例
        # 暂时保留但标记为需要重构
        raise NotImplementedError("此方法需要重构，请使用get_gemini_config或get_openai_config方法")