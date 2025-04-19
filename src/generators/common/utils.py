import os
import json
import logging
import sys # 引入 sys 模块以访问 stdout
from logging.handlers import RotatingFileHandler # 推荐使用 RotatingFileHandler 以防日志文件过大
from typing import Dict, List, Optional, Any
from opencc import OpenCC

def setup_logging(log_dir: str, clear_logs: bool = False):
    """设置日志系统"""
    root_logger = logging.getLogger()
    # 检查是否已存在相同格式的处理器
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.formatter._fmt == '%(asctime)s - %(levelname)s - %(message)s':
            return  # 已存在，直接返回

    # 清理旧的日志文件
    log_file = os.path.join(log_dir, "generation.log")
    if clear_logs and os.path.exists(log_file):
        try:
            os.remove(log_file)
        except Exception as e:
            logging.error(f"清理日志文件失败: {e}")

    # 配置根日志记录器
    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # 添加文件处理器（唯一）
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 添加控制台处理器（唯一）
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info("日志系统初始化完成，将输出到文件和终端。")

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