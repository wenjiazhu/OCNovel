# OCNovel - AI 小说生成工具

OCNovel 是一个基于大语言模型的智能小说生成工具，能够根据参考小说和用户设定的主题、风格等参数，自动生成完整的长篇小说。

## 功能特点

- 🤖 支持多种 AI 模型（Gemini、OpenAI）
  - Gemini模型：使用 `gemini-2.5-flash`（内容生成）和 `gemini-2.5-pro`（大纲生成）
  - OpenAI模型：支持自定义API端点，兼容多种模型
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

> 主要依赖说明：
> - openai：用于调用 OpenAI API（嵌入/内容/大纲模型）
> - google-generativeai：用于调用 Gemini API（支持 gemini-2.5-flash、gemini-2.5-pro 等模型）
> - chromadb、faiss-cpu：知识库向量化与检索
> - jieba：中文分词
> - FlagEmbedding：中文语义重排序
> - python-dotenv：环境变量加载
> - tenacity：自动重试机制
> - numpy：向量与数值处理
> - pytest：单元测试
> - pydantic：类型校验
> - opencc：繁简转换（章节整理工具用）

4. 配置环境变量：
创建 `.env` 文件并添加以下内容：
```
# Gemini API配置
GEMINI_API_KEY=你的Gemini API密钥

# 嵌入模型配置（用于知识库向量化等）
OPENAI_EMBEDDING_API_KEY=你的OpenAI嵌入模型API密钥
OPENAI_EMBEDDING_API_BASE=你的OpenAI嵌入模型API基础URL

# 大纲模型配置（用于生成小说大纲）
OPENAI_OUTLINE_API_KEY=你的OpenAI大纲模型API密钥
OPENAI_OUTLINE_API_BASE=你的OpenAI大纲模型API基础URL

# 内容模型配置（用于生成章节内容）
OPENAI_CONTENT_API_KEY=你的OpenAI内容模型API密钥
OPENAI_CONTENT_API_BASE=你的OpenAI内容模型API基础URL
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

## 故障排除

### Gemini API 调用失败

如果遇到 "404 models/gemini-2.5-flash-preview is not found" 错误：

1. **问题原因**：模型名称已更新，旧版本模型名称不再可用
2. **解决方案**：项目已自动使用正确的模型名称：
   - 内容生成：`gemini-2.5-flash`
   - 大纲生成：`gemini-2.5-pro`

### 其他常见问题

1. **API密钥错误**：确保在 `.env` 文件中正确设置了所有必需的API密钥
2. **网络连接问题**：如果使用代理，确保代理设置正确
3. **模型超时**：可以调整配置文件中的 `timeout` 参数

## 配置说明 (`config.json`)

配置文件是指导小说生成的核心。如果 `config.json` 不存在，首次运行 `main.py` 时会尝试自动调用 `src/tools/generate_config.py` 生成一个基础文件。

主要配置项分为以下部分：

### 1. AI 模型配置（.env 文件）

在项目根目录创建 `.env` 文件，配置 AI 模型相关参数：

```
# Gemini API配置
GEMINI_API_KEY=你的Gemini API密钥

# 嵌入模型配置（用于知识库向量化等）
OPENAI_EMBEDDING_API_KEY=你的OpenAI嵌入模型API密钥
OPENAI_EMBEDDING_API_BASE=你的OpenAI嵌入模型API基础URL

# 大纲模型配置（用于生成小说大纲）
OPENAI_OUTLINE_API_KEY=你的OpenAI大纲模型API密钥
OPENAI_OUTLINE_API_BASE=你的OpenAI大纲模型API基础URL

# 内容模型配置（用于生成章节内容）
OPENAI_CONTENT_API_KEY=你的OpenAI内容模型API密钥
OPENAI_CONTENT_API_BASE=你的OpenAI内容模型API基础URL
```

- `GEMINI_API_KEY`：用于 Gemini LLM 的 API 密钥。
- `OPENAI_EMBEDDING_API_KEY`/`OPENAI_EMBEDDING_API_BASE`：用于知识库嵌入模型（如文本向量化）。
- `OPENAI_OUTLINE_API_KEY`/`OPENAI_OUTLINE_API_BASE`：用于生成小说大纲的 LLM。
- `OPENAI_CONTENT_API_KEY`/`OPENAI_CONTENT_API_BASE`：用于生成章节内容的 LLM。

如不需要某项功能，可留空对应配置。

### 2. 项目配置（config.json）

将`config.json.example`的文件名改为`config.json`，编辑 `config.json` 文件，设置项目相关参数。详细配置说明如下：

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
  "max_retries": 3,          // 单个任务（如生成章节）失败时的最大重试次数
  "retry_delay": 10,         // 重试之间的延迟时间（秒）
  "force_rebuild_kb": false, // 是否强制重新构建知识库，即使缓存存在
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
  "format": "txt",               // 输出文件格式 (目前主要影响 process_novel.py)
  "encoding": "utf-8",           // 输出文件编码
  "save_outline": true,          // 是否保存生成的小说大纲 (outline.json)
  "save_character_states": false, // 是否保存角色状态信息 (待移除)
  "output_dir": "data/output"    // 生成文件的根目录，实际输出会在 data/output/<novel_title>/ 下
}
```

## 故障排除

### FAISS索引维度不匹配错误

如果遇到以下错误：
```
AssertionError: assert d == self.d
```

这是因为知识库的嵌入模型配置发生了变化，导致新生成的查询向量维度与缓存中的索引维度不匹配。

**解决方案：**

1. **自动解决（推荐）**：
   - 程序已内置自动检测和修复机制
   - 当检测到维度不匹配时，会自动重新构建知识库
   - 只需重新运行程序即可

2. **手动清理缓存**：
   ```bash
   python scripts/clear_kb_cache.py
   ```
   此脚本会清理所有知识库缓存文件，下次运行时会重新构建知识库。

3. **直接删除缓存目录**：
   ```bash
   rm -rf data/cache/*
   ```

**预防措施：**
- 避免频繁更改嵌入模型配置
- 如需更改模型配置，建议先清理缓存再运行程序