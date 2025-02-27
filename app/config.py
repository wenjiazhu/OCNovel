from pydantic_settings import BaseSettings
from typing import Dict, List
import os

class Settings(BaseSettings):
    # API配置
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # 数据库配置
    VECTOR_DB_PATH: str = "data/vector_store"
    KNOWLEDGE_GRAPH_PATH: str = "data/knowledge_graph"
    
    # 模型配置
    DEFAULT_MODEL: str = "gpt-4"
    BACKUP_MODEL: str = "gemini-pro"
    
    # 世界观配置
    POWER_SYSTEM_LEVELS: int = 9
    POWER_SYSTEM_STAGES: int = 3
    MIN_CONFLICT_VALUE: float = 0.7
    
    # 情节配置
    STORY_LINES_COUNT: int = 3
    TENSION_RANGE: Dict[str, float] = {
        "min": 0.65,
        "max": 0.8
    }
    
    # 审核配置
    LOGIC_CHECK_DEPTH: int = 3
    EMOTION_STD_THRESHOLD: float = 0.15
    INNOVATION_DENSITY: int = 2  # 每万字创新点数量
    
    # 记忆配置
    MEMORY_DECAY_RATE: float = 0.1
    CONTEXT_WINDOW: int = 8192
    
    class Config:
        env_file = ".env"

settings = Settings() 