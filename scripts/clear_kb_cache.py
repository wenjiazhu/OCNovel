#!/usr/bin/env python3
"""
清理知识库缓存脚本

用于解决FAISS索引维度不匹配的问题。
当嵌入模型配置发生变化时，需要清理旧的缓存文件。
"""

import os
import shutil
import logging
from pathlib import Path

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

def clear_kb_cache(cache_dir: str = "data/cache"):
    """
    清理知识库缓存文件
    
    Args:
        cache_dir: 缓存目录路径
    """
    cache_path = Path(cache_dir)
    
    if not cache_path.exists():
        logging.info(f"缓存目录 {cache_dir} 不存在，无需清理")
        return
    
    # 查找所有知识库缓存文件
    kb_files = list(cache_path.glob("kb_*.pkl"))
    temp_files = list(cache_path.glob("kb_*.pkl.temp_*"))
    
    if not kb_files and not temp_files:
        logging.info("未找到知识库缓存文件")
        return
    
    logging.info(f"找到 {len(kb_files)} 个知识库缓存文件和 {len(temp_files)} 个临时文件")
    
    # 删除缓存文件
    deleted_count = 0
    for file_path in kb_files + temp_files:
        try:
            file_path.unlink()
            logging.info(f"已删除: {file_path.name}")
            deleted_count += 1
        except Exception as e:
            logging.error(f"删除 {file_path.name} 失败: {e}")
    
    logging.info(f"清理完成，共删除 {deleted_count} 个文件")
    
    # 清理content_kb目录
    content_kb_dir = cache_path / "content_kb"
    if content_kb_dir.exists():
        try:
            shutil.rmtree(content_kb_dir)
            logging.info("已清理 content_kb 目录")
        except Exception as e:
            logging.error(f"清理 content_kb 目录失败: {e}")

def main():
    """主函数"""
    setup_logging()
    
    print("=== 知识库缓存清理工具 ===")
    print("此工具将清理所有知识库缓存文件，解决FAISS索引维度不匹配问题。")
    print("清理后，下次运行程序时将重新构建知识库。")
    print()
    
    # 检查缓存目录
    cache_dir = "data/cache"
    if not os.path.exists(cache_dir):
        print(f"缓存目录 {cache_dir} 不存在，无需清理")
        return
    
    # 显示将要删除的文件
    cache_path = Path(cache_dir)
    kb_files = list(cache_path.glob("kb_*.pkl"))
    temp_files = list(cache_path.glob("kb_*.pkl.temp_*"))
    
    if not kb_files and not temp_files:
        print("未找到需要清理的知识库缓存文件")
        return
    
    print("将要删除以下文件:")
    for file_path in kb_files + temp_files:
        print(f"  - {file_path.name}")
    print()
    
    # 确认操作
    confirm = input("确认删除这些文件吗？(y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("操作已取消")
        return
    
    # 执行清理
    clear_kb_cache(cache_dir)
    print("\n清理完成！下次运行程序时将重新构建知识库。")

if __name__ == "__main__":
    main() 