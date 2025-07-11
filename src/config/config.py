from typing import Dict, Any
import os
import json
import logging
from dotenv import load_dotenv
from .ai_config import AIConfig

class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置
        
        Args:
            config_file: 配置文件路径
        """
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_file = config_file
        
        # 加载环境变量
        load_dotenv()
        
        # 加载配置文件
        with open(self.config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
            
        # 初始化 AI 配置
        self.ai_config = AIConfig()
        
        # 从配置文件中读取 output_dir
        config_output_dir = self.config["output_config"].get("output_dir")
        
        # 优先使用config.json中的model_config，如果没有则使用AIConfig的默认配置
        if "model_config" in self.config:
            # 使用配置文件中的model_config
            self.model_config = self.config["model_config"].copy()
            logging.info("使用配置文件中的model_config")
        else:
            # 动态AI模型配置，根据config.json的model_selection字段
            self.model_config = {}
            model_selection = self.config["generation_config"].get("model_selection", {})
            # outline_model
            outline_sel = model_selection.get("outline", {"provider": "gemini", "model_type": "outline"})
            if outline_sel["provider"] == "openai":
                self.model_config["outline_model"] = self.ai_config.get_openai_config(outline_sel["model_type"])
            else:
                self.model_config["outline_model"] = self.ai_config.get_gemini_config(outline_sel["model_type"])
            # content_model
            content_sel = model_selection.get("content", {"provider": "gemini", "model_type": "content"})
            if content_sel["provider"] == "openai":
                self.model_config["content_model"] = self.ai_config.get_openai_config(content_sel["model_type"])
            else:
                self.model_config["content_model"] = self.ai_config.get_gemini_config(content_sel["model_type"])
            # embedding_model 只支持openai
            self.model_config["embedding_model"] = self.ai_config.get_openai_config("embedding")
            logging.info("使用AIConfig的默认model_config")
        
        # 小说配置
        self.novel_config = self.config["novel_config"]
        
        # 知识库配置
        self.knowledge_base_config = self.config["knowledge_base_config"]
        self.knowledge_base_config["reference_files"] = [
            os.path.join(self.base_dir, file_path)
            for file_path in self.knowledge_base_config["reference_files"]
        ]
        
        # 生成器配置
        self.generator_config = {
            "target_chapters": self.novel_config["target_chapters"],
            "chapter_length": self.novel_config["chapter_length"],
            "output_dir": config_output_dir if config_output_dir else os.path.join(self.base_dir, "data", "output"),
            "max_retries": self.config["generation_config"]["max_retries"],
            "retry_delay": self.config["generation_config"]["retry_delay"],
            "validation": self.config["generation_config"]["validation"]
        }
        
        # 日志配置
        self.log_config = {
            "log_dir": os.path.join(self.base_dir, "data", "logs"),
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
        
        # 输出配置
        self.output_config = self.config["output_config"]
        self.output_config.update({
            "output_dir": config_output_dir if config_output_dir else os.path.join(self.base_dir, "data", "output")
        })
        
        # 仿写配置
        self.imitation_config = self.config.get("imitation_config", {})

        # 启动时打印当前 model_config 便于调试
        logging.info(f"[调试] 当前 model_config: {self.model_config}")
    
    def get_model_config(self, model_type: str) -> Dict[str, Any]:
        """
        获取指定类型的模型配置
        
        Args:
            model_type: 模型类型（outline_model/content_model/embedding_model/imitation_model）
            
        Returns:
            Dict[str, Any]: 模型配置
        """
        if model_type in self.model_config:
            return self.model_config[model_type]
        raise ValueError(f"不支持的模型类型: {model_type}")
    
    def get_writing_guide(self) -> Dict:
        """获取写作指南"""
        return self.novel_config["writing_guide"]
        
    def save(self):
        """保存配置到文件"""
        config = {
            "novel_config": self.novel_config,
            "generation_config": {
                "max_retries": self.generator_config["max_retries"],
                "retry_delay": self.generator_config["retry_delay"],
                "validation": self.generator_config["validation"]
            },
            "output_config": self.output_config
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def __getattr__(self, name: str) -> Any:
        """获取配置项"""
        if name in self.config:
            return self.config[name]
        raise AttributeError(f"Config has no attribute '{name}'")

    def get_imitation_model(self) -> Dict[str, Any]:
        """
        获取仿写专用模型配置，优先级：
        1. model_config['imitation_model']
        2. ai_config.gemini_config['fallback']（补全必要字段）
        3. content_model
        """
        # 1. 优先使用 model_config['imitation_model']
        if "imitation_model" in self.model_config:
            logging.info(f"[仿写模型选择] 使用 model_config['imitation_model']: {self.model_config['imitation_model']}")
            return self.model_config["imitation_model"]
        # 2. 其次使用 ai_config.gemini_config['fallback']
        fallback = getattr(self.ai_config, "gemini_config", {}).get("fallback")
        if fallback and fallback.get("enabled", False):
            fallback_model_name = fallback.get("models", {}).get("default", "deepseek-ai/DeepSeek-R1")
            imitation_fallback_config = {
                "type": "gemini",
                "model_name": fallback_model_name,
                "api_key": fallback.get("api_key", ""),
                "base_url": fallback.get("base_url", "https://api.siliconflow.cn/v1"),
                "timeout": fallback.get("timeout", 180),
            }
            logging.info(f"[仿写模型选择] 使用 gemini_config['fallback']: {imitation_fallback_config}")
            return imitation_fallback_config
        # 3. 最后 fallback 到 content_model
        logging.info(f"[仿写模型选择] fallback 到 content_model: {self.model_config.get('content_model')}")
        return self.model_config.get("content_model") 