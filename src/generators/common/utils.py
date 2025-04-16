import os
import json
import logging
from typing import Dict, List, Optional, Any
from opencc import OpenCC

def setup_logging(output_dir: str) -> None:
    """设置日志系统"""
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, "generation.log")
    
    try:
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        
        logging.info("日志系统初始化完成")
    except Exception as e:
        print(f"日志系统初始化失败: {e}")

def load_json_file(file_path: str, default_value: Any = None) -> Any:
    """加载JSON文件"""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"加载JSON文件 {file_path} 时出错: {str(e)}")
    return default_value

def save_json_file(file_path: str, data: Any) -> bool:
    """保存数据到JSON文件"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f"保存JSON文件 {file_path} 时出错: {str(e)}")
        return False

def clean_text(text: str) -> str:
    """清理文本内容"""
    # 创建繁简转换器
    t2s = OpenCC('t2s')
    # 转换为简体
    return t2s.convert(text.strip())

def validate_directory(directory: str) -> bool:
    """验证目录是否存在，不存在则创建"""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logging.error(f"创建目录 {directory} 时出错: {str(e)}")
        return False 