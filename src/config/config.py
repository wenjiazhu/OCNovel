from typing import Dict
import os
import json
from dotenv import load_dotenv
from .ai_config import AIConfig

class Config:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_file = os.path.join(self.base_dir, "config.json")
        
        # 加载环境变量
        load_dotenv()
        
        # 加载配置文件
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            raise FileNotFoundError(f"配置文件 {self.config_file} 不存在")
            
        # 初始化 AI 配置
        self.ai_config = AIConfig()
            
        # AI模型配置
        self.model_config = {
            "outline_model": self.ai_config.get_model_config("gemini_outline"),
            "content_model": self.ai_config.get_model_config("gemini_content"),
            "embedding_model": self.ai_config.get_model_config("openai_embedding")
        }
        
        # 小说配置
        self.novel_config = config["novel_config"]
        self.novel_config["reference_files"] = [
            os.path.join(self.base_dir, file_path)
            for file_path in self.novel_config["reference_files"]
        ]
        
        # 知识库配置
        self.knowledge_base_config = config["knowledge_base_config"]
        self.knowledge_base_config["reference_files"] = [
            os.path.join(self.base_dir, file_path)
            for file_path in self.knowledge_base_config["reference_files"]
        ]
        
        # 生成器配置
        self.generator_config = {
            "target_length": self.novel_config["target_length"],
            "chapter_length": self.novel_config["chapter_length"],
            "output_dir": os.path.join(self.base_dir, "data", "output"),
            "max_retries": config["generation_config"]["max_retries"],
            "retry_delay": config["generation_config"]["retry_delay"],
            "validation": config["generation_config"]["validation"]
        }
        
        # 日志配置
        self.log_config = {
            "log_dir": os.path.join(self.base_dir, "data", "logs"),
            "log_level": "INFO",
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
        
        # 输出配置
        self.output_config = config["output_config"]
        self.output_config.update({
            "output_dir": os.path.join(self.base_dir, "data", "output")
        })
    
    def get_model_config(self, model_type: str) -> Dict:
        """获取指定类型的模型配置"""
        return self.model_config.get(model_type, {})
        
    def get_writing_guide(self) -> Dict:
        """获取写作指南"""
        return self.novel_config["writing_guide"]
        
    def save(self):
        """保存配置到文件"""
        config = {
            "ai_config": {
                "gemini_api_key": self.model_config["outline_model"]["api_key"],
                "openai_api_key": self.model_config["content_model"]["api_key"],
                "openai_api_base": self.model_config["content_model"]["base_url"]
            },
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