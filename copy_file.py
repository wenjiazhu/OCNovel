import shutil
import os

source = "data/output3/processed_chapters/第1章_灵胎初醒，都市夜骑惊变 (1119).txt"
dest = "chapters"

if not os.path.exists(dest):
    os.makedirs(dest)

shutil.copy2(source, dest)
print(f"文件已复制到 {dest} 目录") 