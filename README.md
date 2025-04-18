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

### 1. 主程序运行 (main.py)

```bash
python main.py [command] [options]
```

支持以下子命令：

#### (1) 生成完整小说流程
```bash
python main.py auto [--extra-prompt "额外提示词"]
```
- **功能**：自动执行完整的小说生成流程（大纲生成、内容生成、章节定稿）。
- **参数**：
  - `--extra-prompt`：可选，用于指导生成的额外提示词。

#### (2) 单独生成大纲
```bash
python main.py outline \
    --start <起始章节> \
    --end <结束章节> \
    [--novel-type <小说类型>] \
    [--theme <主题>] \
    [--style <写作风格>] \
    [--extra-prompt "额外提示词"]
```
- **功能**：生成或更新指定章节范围的小说大纲。
- **参数**：
  - `--start`：必需，起始章节号（从 1 开始）。
  - `--end`：必需，结束章节号（包含）。
  - `--novel-type`：可选，小说类型（如未提供，使用配置文件中的设置）。
  - `--theme`：可选，主题（如未提供，使用配置文件中的设置）。
  - `--style`：可选，写作风格（如未提供，使用配置文件中的设置）。
  - `--extra-prompt`：可选，额外提示词。

#### (3) 生成章节内容
```bash
python main.py content \
    [--start-chapter <起始章节>] \
    [--target-chapter <指定章节>] \
    [--extra-prompt "额外提示词"]
```
- **功能**：生成或重新生成章节内容。
- **参数**：
  - `--start-chapter`：可选，起始章节号（从 1 开始）。如未提供，从上次进度或默认章节开始。
  - `--target-chapter`：可选，指定重新生成的章节号（优先级高于 `--start-chapter`）。
  - `--extra-prompt`：可选，额外提示词。

#### (4) 章节定稿处理
```bash
python main.py finalize --chapter <章节号>
```
- **功能**：对指定章节进行定稿处理（如内容优化、格式检查等）。
- **参数**：
  - `--chapter`：必需，章节号（从 1 开始）。

### 2. 生成营销内容

```bash
python src/tools/generate_marketing.py --keywords "关键词1" "关键词2" --characters "角色1" "角色2"
```

### 3. 整理章节内容

```bash
python src/tools/process_novel.py <输入目录> <输出目录> -e <结束章节号> [-s <起始章节号>] [--split-sentences]
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
│       ├── process_novel.py        # 章节内容整理工具
│       ├── update_outline.py       # 大纲更新工具
│       ├── update_summary.py       # 章节摘要更新工具
│       └── generate_marketing.py   # 营销内容生成
├── tests/             # 测试文件
├── config.json        # 主配置文件
├── config.json.example # 配置文件示例
├── requirements.txt   # 依赖列表
└── README.md         # 项目说明
```

## 配置说明

主要配置项分为两部分：

### 1. 小说配置 (`novel_config`)

定义要生成的小说基本信息和写作指南，这是指导 AI 创作的核心部分。

```json
{
  "type": "示例类型",          // 小说类型: 如 玄幻, 都市, 科幻
  "theme": "示例主题",         // 小说主题: 如 成长, 复仇, 探索
  "style": "示例风格",         // 写作风格: 如 热血, 轻松, 悬疑
  "target_chapters": 100,    // 目标生成章节数
  "chapter_length": 2000,    // 每章目标字数 (AI会尽量靠近此目标)
  "writing_guide": {         // 详细的写作指南，包含世界观、角色、情节结构、风格等方面的详细设定
    // ... 详细配置见 config.json.example ...
  },
  "extra_guidance": {        // 额外的写作指导，包括具体写作风格、内容规则、章节结构和情节修正等
    // ... 详细配置见 config.json.example ...
  }
}
```
详细的 `writing_guide` 和 `extra_guidance` 配置项请参考 `config.json.example` 文件。

### 2. 生成配置 (`generation_config`)

控制小说生成过程的行为。

```json
{
  "max_retries": 3,          // 单个任务（如生成章节）失败时的最大重试次数
  "retry_delay": 10,         // 重试之间的延迟时间（秒）
  "force_rebuild_kb": false, // 是否强制重新构建知识库，即使缓存存在
  "validation": {            // 内容验证选项
    "check_logic": true,     // 是否检查生成内容的逻辑性
    "check_consistency": true, // 是否检查与前文的一致性
    "check_duplicates": true  // 是否检查重复内容
  }
}
```

### 3. 输出配置 (`output_config`)

控制生成结果的保存方式。

```json
{
  "format": "txt",               // 输出文件格式
  "encoding": "utf-8",           // 输出文件编码
  "save_outline": true,          // 是否保存生成的小说大纲
  "save_character_states": true, // 是否保存角色状态信息（如果实现）
  "output_dir": "<path/to/output>" // 生成文件的输出目录
}
```

# 番茄小说网自动发布工具

这是一个使用Playwright自动将章节发布到番茄小说网作家专区的Python脚本。

## 环境要求

- Python 3.7+
- Playwright

## 安装步骤

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 安装Playwright浏览器：
```bash
playwright install
```

## 使用方法

1. 准备章节文件：
   - 在项目根目录创建 `chapters` 文件夹
   - 将章节文件（.txt格式）放入该文件夹
   - 章节文件的第一行应为章节标题，之后为章节内容

2. 准备登录信息：
   - 手动登录番茄小说网
   - 使用浏览器开发者工具导出cookies为JSON格式
   - 将cookies保存为 `cookies.json` 文件放在项目根目录

3. 运行脚本：
```bash
python auto_publish.py
```

## 注意事项

- 章节文件会按文件名排序依次发布
- 每个章节发布后会有2秒延时，避免请求过快
- 发布过程中请勿关闭浏览器窗口
- 所有章节都会保存为草稿，需要手动审核后发布