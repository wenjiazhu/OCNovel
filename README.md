# OCNovel - AI 小说生成工具

OCNovel 是一个基于大语言模型的智能小说生成工具，能够根据参考小说和用户设定的主题、风格等参数，自动生成完整的长篇小说。

## 功能特点

- 🤖 支持多种 AI 模型（Gemini、OpenAI）
- 📚 智能知识库系统，支持参考小说导入和分析
- 📝 自动生成小说大纲和章节内容
- 💡 支持手动更新和优化小说大纲
- 🔄 支持手动更新已生成章节的摘要信息
- 👥 智能角色管理系统 (待实现)
- 🎯 支持章节重新生成和内容优化 (通过 `content --target-chapter`)
- ✨ 章节内容自动定稿与优化 (集成在 `content` 和 `auto` 流程中)
- 📂 基于小说标题的专属输出目录管理和配置快照
- ⚙️ 自动工作目录初始化
- 📄 首次运行时可交互生成基础配置文件
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

5. 准备配置文件 (`config.json`)：
   - 你可以手动复制 `config.json.example` 并重命名为 `config.json`，然后根据需要修改。
   - **首次运行** `main.py` 时，如果 `config.json` 不存在，程序会提示你输入小说主题，并自动调用 `src/tools/generate_config.py` 生成一个基础的 `config.json` 文件。

## 使用方法

### 1. 主程序运行 (main.py)

```bash
python main.py [--config <配置文件路径>] [command] [options]
```
- `--config`：可选，指定配置文件的路径，默认为 `config.json`。

支持以下子命令：

#### (1) 自动生成完整小说流程 (`auto`)
```bash
python main.py auto [--extra-prompt "额外提示词"]
```
- **功能**：自动执行完整的小说生成流程。从 `summary.json` (位于输出目录) 读取进度，检查并生成缺失的大纲，然后从上次进度开始生成章节内容并自动定稿，直至达到 `config.json` 中设定的 `target_chapters`。
- **参数**：
  - `--extra-prompt`：可选，用于指导生成的额外提示词，会传递给大纲和内容生成阶段。

#### (2) 单独生成大纲 (`outline`)
```bash
python main.py outline \
    --start <起始章节> \
    --end <结束章节> \
    [--novel-type <小说类型>] \
    [--theme <主题>] \
    [--style <写作风格>] \
    [--extra-prompt "额外提示词"]
```
- **功能**：生成或更新指定章节范围的小说大纲 (`outline.json`)。
- **参数**：
  - `--start`：必需，起始章节号（从 1 开始）。
  - `--end`：必需，结束章节号（包含）。
  - `--novel-type`：可选，小说类型（如未提供，使用配置文件中的设置）。
  - `--theme`：可选，主题（如未提供，使用配置文件中的设置）。
  - `--style`：可选，写作风格（如未提供，使用配置文件中的设置）。
  - `--extra-prompt`：可选，用于指导大纲生成的额外提示词。

#### (3) 生成章节内容 (`content`)
```bash
python main.py content \
    [--start-chapter <起始章节>] \
    [--target-chapter <指定章节>] \
    [--extra-prompt "额外提示词"]
```
- **功能**：生成或重新生成章节内容。默认从上次中断的章节（记录在 `progress.json`）开始生成，直至大纲结束。生成过程中会自动调用定稿逻辑。
- **参数**：
  - `--start-chapter`：可选，指定从哪一章开始生成。如果指定，将覆盖 `progress.json` 中的记录。
  - `--target-chapter`：可选，指定仅重新生成某一个章节。优先级高于 `--start-chapter`。
  - `--extra-prompt`：可选，用于指导内容生成的额外提示词。

#### (4) 手动章节定稿处理 (`finalize`)
```bash
python main.py finalize --chapter <章节号>
```
- **功能**：对指定章节进行手动的定稿处理（通常已集成到 `content` 和 `auto` 流程中，此命令主要用于特殊情况或调试）。
- **参数**：
  - `--chapter`：必需，需要定稿的章节号（从 1 开始）。

### 2. 生成营销内容

```bash
python src/tools/generate_marketing.py --keywords "关键词1" "关键词2" --characters "角色1" "角色2"
```
*(此工具的功能和用法请参考其内部实现或相关文档)*

### 3. 整理章节内容

```bash
python src/tools/process_novel.py <输入目录> <输出目录> -e <结束章节号> [-s <起始章节号>] [--split-sentences]
```
*(此工具的功能和用法请参考其内部实现或相关文档)*

## 项目结构

```
OCNovel/
├── data/                 # 数据目录 (自动创建)
│   ├── cache/           # 知识库、模型缓存等
│   ├── logs/            # 日志文件
│   ├── output/          # 生成输出根目录
│   │   ├──  <novel_title>/ # 基于小说标题的专属输出目录
│   │   │   └── config_snapshot.json # 本次运行的配置快照
│   │   ├── content_kb/  # 章节知识库
│   │   ├── outline.json # 生成的小说大纲
│   │   ├── summary.json # 各章节摘要信息
│   │   └── sync_info.json # 同步信息
│   └── reference/       # 参考小说存放处
├── src/                 # 源代码
│   ├── config/          # 配置管理
│   │   ├── ai_config.py     # AI Config类，加载和管理LLM配置
│   │   └── config.py     # Config类，加载和管理配置
│   ├── generators/      # 生成器模块
│   │   ├── common/       # 通用工具 (如 utils.py)
│   │   ├── content/      # 章节内容生成
│   │   │   └── content_generator.py
│   │   ├── finalizer/    # 章节定稿处理
│   │   │   └── finalizer.py
│   │   └── outline/      # 大纲生成
│   │       └── outline_generator.py
│   ├── knowledge_base/  # 知识库管理
│   │   └── knowledge_base.py
│   ├── models/          # AI模型接口
│   │   ├── base_model.py # 基础模型类
│   │   ├── gemini_model.py
│   │   └── openai_model.py
│   └── tools/           # 辅助工具脚本
│       ├── generate_config.py    # 自动生成配置文件脚本
│       ├── generate_marketing.py # 营销内容生成
│       └── process_novel.py      # 章节内容整理
├── tests/               # 测试文件
├── .env                 # 环境变量 (API Keys等)
├── config.json          # 主配置文件
├── config.json.example   # 配置文件示例
├── main.py              # 主程序入口
├── requirements.txt     # Python依赖列表
└── README.md           # 项目说明
```

## 配置说明 (`config.json`)

配置文件是指导小说生成的核心。如果 `config.json` 不存在，首次运行 `main.py` 时会尝试自动生成。

主要配置项分为以下部分：

### 1. 小说配置 (`novel_config`)

定义小说的基本信息和写作指南。

```json
{
  "title": "我的第一部AI小说",    // 小说标题，【重要】用于创建专属输出目录 data/output/<novel_title>/
  "type": "玄幻",               // 小说类型: 如 玄幻, 都市, 科幻
  "theme": "成长与冒险",          // 小说主题: 如 成长, 复仇, 探索
  "style": "轻松幽默",           // 写作风格: 如 热血, 轻松, 悬疑
  "target_chapters": 100,     // 目标生成章节数
  "chapter_length": 2000,     // 每章目标字数 (AI会尽量靠近此目标)
  "writing_guide": {          // 详细的写作指南，包含世界观、角色、情节结构、风格等方面的详细设定
    // ... 详细配置见 config.json.example ...
  },
  "extra_guidance": {         // 额外的写作指导，包括具体写作风格、内容规则、章节结构和情节修正等
    // ... 详细配置见 config.json.example ...
  }
}
```
**注意**: `title` 字段非常重要，它决定了你的小说内容（大纲、章节、摘要等）存储在 `data/output/` 下的哪个子目录。

### 2. 知识库配置 (`knowledge_base_config`)

控制知识库的行为。

```json
{
  "reference_dir": "data/reference", // 参考资料目录
  "cache_dir": "data/cache/kb_cache",// 知识库缓存目录
  "chunk_size": 1000,              // 文本分块大小
  "chunk_overlap": 100,            // 文本分块重叠大小
  "force_rebuild": false           // 是否强制重新构建知识库，即使缓存存在
}
```

### 3. 生成配置 (`generation_config`)

控制小说生成过程的行为。

```json
{
  "max_retries": 3,          // 单个任务（如生成章节）失败时的最大重试次数
  "retry_delay": 10,         // 重试之间的延迟时间（秒）
  // "force_rebuild_kb" 已移至 knowledge_base_config
  "validation": {            // 内容验证选项 (部分可能未完全实现)
    "check_logic": true,
    "check_consistency": true,
    "check_duplicates": true
  }
}
```

### 5. 输出配置 (`output_config`)

控制生成结果的保存方式。

```json
{
  "output_dir": "data/output",     // 【重要】生成文件的根目录，实际输出会在 data/output/<novel_title>/ 下
  "format": "txt",                 // 章节内容输出文件格式 (目前主要影响 process_novel.py)
  "encoding": "utf-8",             // 输出文件编码
  "save_outline": true,            // 是否保存生成的小说大纲 (outline.json)
  "save_summary": true,            // 是否保存章节摘要 (summary.json)
  "save_progress": true            // 是否保存生成进度 (progress.json)
  // "save_character_states": true // 角色状态保存 (待实现)
}
```
**注意**: 实际的章节文本文件、大纲、摘要等会保存在由 `output_dir` 和 `novel_config.title` 决定的专属目录中，例如 `data/output/我的第一部AI小说/`。同时，每次运行时使用的配置文件快照也会保存到该目录 (`config_snapshot.json`)。

### 6. 日志配置 (`log_config`)

控制日志记录。

```json
{
    "log_dir": "data/logs",    // 日志文件存放目录
    "log_level": "INFO",     // 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    "log_to_console": true   // 是否同时输出日志到控制台
}
```

---

*后面的 "番茄小说网自动发布工具" 部分保持不变，因为它似乎是一个独立的脚本功能。*