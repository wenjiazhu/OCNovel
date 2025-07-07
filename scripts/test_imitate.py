import os
import sys
import subprocess
import tempfile
import shutil

# 获取 main.py 路径
MAIN_PY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))

# 测试用风格源内容和原始文本
STYLE_TEXT = """
青山隐隐水迢迢，秋尽江南草未凋。
二十四桥明月夜，玉人何处教吹箫。
"""
ORIGINAL_TEXT = """
小明走进了教室，阳光洒在他的脸上。他微笑着和同学们打招呼，心情格外愉快。
"""

def test_imitate():
    print("[仿写功能测试] 开始...")
    temp_dir = tempfile.mkdtemp()
    try:
        style_file = os.path.join(temp_dir, "style.txt")
        input_file = os.path.join(temp_dir, "input.txt")
        output_file = os.path.join(temp_dir, "output.txt")

        # 写入测试内容
        with open(style_file, 'w', encoding='utf-8') as f:
            f.write(STYLE_TEXT)
        with open(input_file, 'w', encoding='utf-8') as f:
            f.write(ORIGINAL_TEXT)

        # 构造命令
        cmd = [
            sys.executable, MAIN_PY_PATH, 'imitate',
            '--style-source', style_file,
            '--input-file', input_file,
            '--output-file', output_file
        ]
        print(f"运行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("[stdout]\n", result.stdout)
        print("[stderr]\n", result.stderr)

        # 检查输出文件
        if not os.path.exists(output_file):
            print("[失败] 未生成仿写输出文件！")
            return False
        with open(output_file, 'r', encoding='utf-8') as f:
            imitated = f.read().strip()
        if not imitated:
            print("[失败] 仿写输出内容为空！")
            return False
        if imitated == ORIGINAL_TEXT.strip():
            print("[失败] 仿写输出与原文完全一致，未发生风格迁移！")
            return False
        print("[成功] 仿写功能测试通过！\n仿写结果：\n", imitated)
        return True
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    ok = test_imitate()
    sys.exit(0 if ok else 1) 