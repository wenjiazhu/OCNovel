from auto_publish import read_chapters_from_files

chapters = read_chapters_from_files("chapters")
for chapter in chapters:
    print("标题:", chapter["title"])
    print("内容前100个字符:", chapter["content"][:100])
    print("-" * 50) 