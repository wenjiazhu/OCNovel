#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import argparse
from typing import List, Dict
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.generators.novel_generator import NovelGenerator
from src.config import load_config
from src.models import load_model

def update_chapter_summaries(chapter_nums: List[int], output_dir: str, config_file: str) -> None:
    """
    更新指定章节的摘要
    
    Args:
        chapter_nums: 需要更新摘要的章节号列表
        output_dir: 输出目录路径
        config_file: 配置文件路径
    """
    try:
        # 加载配置
        config = load_config(config_file)
        
        # 初始化模型
        content_model = load_model(config['content_model'])
        outline_model = load_model(config['outline_model'])
        knowledge_base = None  # 这里可以根据需要加载知识库
        
        # 初始化 NovelGenerator
        generator = NovelGenerator(config, outline_model, content_model, knowledge_base)
        
        # 加载现有摘要
        summary_file = os.path.join(output_dir, "summary.json")
        summaries = {}
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                summaries = json.load(f)
        
        # 对每个指定的章节进行更新
        for chapter_num in sorted(chapter_nums):
            try:
                # 构建章节文件名
                chapter_files = [
                    f for f in os.listdir(output_dir) 
                    if f.startswith(f"第{chapter_num}章") or f.startswith(f"第{chapter_num} 章")
                ]
                
                if not chapter_files:
                    logging.warning(f"未找到第 {chapter_num} 章的文件，跳过更新")
                    continue
                
                chapter_file = os.path.join(output_dir, chapter_files[0])
                
                # 读取章节内容
                with open(chapter_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 调用 NovelGenerator 的 _update_summary 方法更新摘要
                generator._update_summary(chapter_num, content)
                logging.info(f"已成功更新第 {chapter_num} 章的摘要")
                
            except Exception as e:
                logging.error(f"更新第 {chapter_num} 章摘要时出错: {str(e)}")
                continue
        
        logging.info("所有指定章节的摘要更新完成")
        
    except Exception as e:
        logging.error(f"更新摘要过程中发生错误: {str(e)}")
        raise

def main():
    parser = argparse.ArgumentParser(description="更新指定章节的摘要")
    parser.add_argument("chapter_nums", type=int, nargs="+", help="需要更新摘要的章节号，可以指定多个，用空格分隔")
    parser.add_argument("--output_dir", type=str, default="data/output", help="输出目录路径")
    parser.add_argument("--config", type=str, default="config/config.json", help="配置文件路径")
    parser.add_argument("--log_level", type=str, default="INFO", help="日志级别")
    
    args = parser.parse_args()
    
    # 设置日志级别
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        update_chapter_summaries(args.chapter_nums, args.output_dir, args.config)
    except Exception as e:
        logging.error(f"程序执行出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 