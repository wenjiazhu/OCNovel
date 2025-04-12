# OCNovel - AI 小说生成工具

OCNovel 是一个基于大语言模型的智能小说生成工具，能够根据参考小说和用户设定的主题、风格等参数，自动生成完整的长篇小说。

## 功能特点

- 🤖 支持多种 AI 模型（Gemini、OpenAI）
- 📚 智能知识库系统，支持参考小说导入和分析
- 📝 自动生成小说大纲和章节内容
- 💡 支持手动更新和优化小说大纲
- 🔄 支持手动更新已生成章节的摘要信息
- 👥 智能角色管理系统
- 🎯 支持章节重新生成和内容优化
- 📊 完整的日志记录系统
- 🎨 支持生成营销内容（标题、封面提示词等）

## 系统要求

- Python 3.9+
- 足够的磁盘空间用于存储知识库和生成内容
- API 密钥（Gemini 和/或 OpenAI）

## 安装说明

1. 克隆项目到本地：
```bash
git clone https://github.com/yourusername/OCNovel.git
cd OCNovel
```

2. 创建并激活虚拟环境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 配置环境变量：
创建 `.env` 文件并添加以下内容：
```
# Gemini API配置
GEMINI_API_KEY=你的Gemini API密钥

# OpenAI API配置
OPENAI_API_KEY=你的OpenAI API密钥
OPENAI_API_BASE=你的OpenAI API基础URL（可选）
```

## 使用方法

### 1. 生成新小说

```bash
python main.py
```

程序会：
- 检查并构建知识库
- 生成小说大纲
- 逐章节生成内容
- 保存生成结果

### 2. 重新生成特定章节

```bash
python src/generators/chapter_regenerator.py --chapter <章节号> --prompt "额外提示词"
```

### 3. 生成营销内容

```bash
python src/tools/generate_marketing.py --keywords "关键词1" "关键词2" --characters "角色1" "角色2"
```

### 4. 手动更新小说大纲

如果你需要手动更新小说的大纲，可以使用 `src/tools/update_outline.py` 脚本。这允许你指定章节范围和额外的提示词来重新生成大纲。

```bash
python src/tools/update_outline.py --start <起始章节号> --end <结束章节号> [--prompt "额外提示词"] [--config <配置文件路径>] [--log-level <日志级别>]
```

**参数说明:**

- `--start <起始章节号>`:  起始章节号 (包含)，从 1 开始。**必需参数**。
- `--end <结束章节号>`:  结束章节号 (包含)，从 1 开始。**必需参数**。
- `--prompt "额外提示词"`:  *(可选)* 用于指导大纲生成的额外提示词。如果需要更精细地控制大纲生成，可以添加此参数。
- `--config <配置文件路径>`:  *(可选)* 配置文件路径，默认为 `config.json`。如果你的配置文件不在项目根目录或者文件名不同，可以使用此参数指定。
- `--log-level <日志级别>`:  *(可选)* 日志级别，默认为 `INFO`。可以选择 `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` 等。

**示例:**

更新第 10 章到第 20 章的大纲，并添加额外提示词 "增加主角的冒险元素":

```bash
python src/tools/update_outline.py --start 10 --end 20 --prompt "增加主角的冒险元素"
```

### 5. 手动更新章节摘要

如果你希望更新已生成章节的摘要信息，可以使用 `src/tools/update_summary.py` 脚本。这在你修改了章节内容后，希望更新摘要以保持信息同步时非常有用。

```bash
python src/tools/update_summary.py <章节号1> [<章节号2> ...] [--output_dir <输出目录路径>] [--config <配置文件路径>] [--log-level <日志级别>]
```

**参数说明:**

- `<章节号1> [<章节号2> ...]`:  需要更新摘要的章节号，可以指定一个或多个，用空格分隔。**必需参数**。
- `--output_dir <输出目录路径>`:  *(可选)* 输出目录路径，默认为 `data/output`。如果你的小说章节输出目录不是默认路径，可以使用此参数指定。
- `--config <配置文件路径>`:  *(可选)* 配置文件路径，默认为 `config.json`。
- `--log-level <日志级别>`:  *(可选)* 日志级别，默认为 `INFO`。

**示例:**

更新第 5 章和第 8 章的摘要:

```bash
python src/tools/update_summary.py 5 8
```

更新第 12 章的摘要，并指定输出目录为 `output` 文件夹:

```bash
python src/tools/update_summary.py 12 --output_dir output
```

### 6. 整理章节内容 (process_novel.py)

如果你有原始的、未处理的小说章节文件（例如，繁体中文、标点不规范），可以使用 `src/tools/process_novel.py` 脚本进行批量整理。该脚本可以完成以下任务：

-   将繁体中文转换为简体中文。
-   将常见的半角标点符号转换为全角中文标点。
-   移除文本中的所有空格。
-   （可选）将每个句子拆分成单独的段落。
-   统计每个章节正文的汉字数量，并将其添加到输出文件名末尾的括号中。

```bash
python src/tools/process_novel.py <输入目录> <输出目录> -e <结束章节号> [-s <起始章节号>] [--split-sentences]
```

**参数说明:**

-   `<输入目录>`: 包含原始章节文件的目录路径。章节文件命名应符合格式 `第{数字}章_任意字符.txt` (例如 `第1章_初遇.txt`)。**必需参数**。
-   `<输出目录>`: 保存处理后章节文件的目录路径。脚本会自动创建此目录（如果不存在）。**必需参数**。
-   `-e <结束章节号>` 或 `--end <结束章节号>`: 需要处理的结束章节号（包含）。**必需参数**。
-   `-s <起始章节号>` 或 `--start <起始章节号>`: *(可选)* 需要处理的起始章节号（包含），默认为 `1`。
-   `--split-sentences`: *(可选)* 是否将每个句子拆分为一个段落。如果指定此参数，则启用该功能。

**示例:**

处理位于 `data/raw_chapters` 目录下的第 1 章到第 50 章，将结果保存到 `data/processed_chapters`，并启用句子分段：

```bash
python src/tools/process_novel.py data/raw_chapters data/processed_chapters -s 1 -e 50 --split-sentences
```

处理位于 `input` 目录下所有章节号小于等于 100 的章节（从默认第 1 章开始），保存到 `output` 目录，不进行句子分段：

```bash
python src/tools/process_novel.py input output -e 100
```

## 项目结构

```
OCNovel/
├── data/               # 数据目录
│   ├── cache/         # 缓存文件
│   ├── logs/          # 日志文件
│   ├── output/        # 生成输出
│   └── reference/     # 参考小说
├── src/               # 源代码
│   ├── config/        # 配置相关
│   │   ├── ai_config.py    # AI模型配置
│   │   └── config.py       # 主配置管理
│   ├── generators/    # 生成器
│   │   ├── novel_generator.py      # 小说生成器
│   │   ├── chapter_regenerator.py  # 章节重生成器
│   │   ├── title_generator.py      # 标题生成器
│   │   ├── consistency_checker.py  # 一致性检查器
│   │   ├── prompts.py             # 提示词定义
│   │   ├── models.py              # 生成器模型
│   │   └── validators.py          # 内容验证器
│   ├── knowledge_base/# 知识库
│   │   └── knowledge_base.py      # 知识库管理
│   ├── models/        # AI模型
│   │   ├── base_model.py          # 基础模型类
│   │   ├── gemini_model.py        # Gemini模型
│   │   └── openai_model.py        # OpenAI模型
│   └── tools/         # 工具脚本
│       └── generate_marketing.py   # 营销内容生成
├── tests/             # 测试文件
├── config.json        # 主配置文件
├── requirements.txt   # 依赖列表
└── README.md         # 项目说明
```

## 配置说明

主要配置项分为两部分：

### 1. AI 模型配置（.env 文件）

在项目根目录创建 `.env` 文件，配置 AI 模型相关参数：

```
# Gemini API配置
GEMINI_API_KEY=你的Gemini API密钥

# OpenAI API配置
OPENAI_API_KEY=你的OpenAI API密钥
OPENAI_API_BASE=你的OpenAI API基础URL（可选）
```

### 2. 项目配置（config.json）

编辑 `config.json` 文件，设置项目相关参数。详细配置说明如下：

#### 2.1 知识库配置 (knowledge_base_config)

用于管理和处理参考小说的配置项。

```json
{
  "reference_files": ["data/reference/my_novel.txt"],  // 参考小说文件路径列表，支持多个文件
  "chunk_size": 1000,                                  // 文本分块大小，用于将长文本分割成小块进行处理
  "chunk_overlap": 200,                                // 分块重叠大小，确保上下文连贯性
  "cache_dir": "data/cache"                            // 知识库缓存目录，用于存储处理后的文本块
}
```

#### 2.2 日志配置 (log_config)

用于记录系统运行状态的配置项。

```json
{
  "log_dir": "data/logs",                              // 日志文件存储目录
  "log_level": "INFO",                                // 日志级别：DEBUG/INFO/WARNING/ERROR
  "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  // 日志格式
}
```

#### 2.3 小说配置 (`novel_config`)

定义要生成的小说基本信息和写作指南，这是指导 AI 创作的核心部分。

##### 2.3.1 基本信息
```json
{
  "type": "示例类型",         // 小说类型: 如 玄幻, 都市, 科幻
  "theme": "示例主题",        // 小说主题: 如 成长, 复仇, 探索
  "style": "示例风格",        // 写作风格: 如 热血, 轻松, 悬疑
  "target_chapters": 100,   // 目标生成章节数
  "chapter_length": 2000    // 每章目标字数 (AI会尽量靠近此目标)
}
```