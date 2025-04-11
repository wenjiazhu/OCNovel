# OCNovel - AI 小说生成工具

OCNovel 是一个基于大语言模型的智能小说生成工具，能够根据参考小说和用户设定的主题、风格等参数，自动生成完整的长篇小说。

## 功能特点

- 🤖 支持多种 AI 模型（Gemini、OpenAI）
- 📚 智能知识库系统，支持参考小说导入和分析
- 📝 自动生成小说大纲和章节内容
- 👥 智能角色管理系统
- 🎯 支持章节重新生成和内容优化
- 📊 完整的日志记录系统
- 🎨 支持生成营销内容（标题、封面提示词等）
- 🔄 支持多轮对话和内容迭代优化
- 📈 可视化数据分析和进度追踪

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

##### 2.3.2 写作指南 (`writing_guide`)

用于详细指导 AI 的创作方向。

###### 世界观设定 (`world_building`)
```json
{
  "magic_system": "示例力量体系或核心设定", // 定义世界的力量规则、科技水平等
  "social_system": "示例社会结构或势力划分", // 描述世界的主要组织、国家、种族等
  "background": "示例时代背景或世界起源"   // 设定故事发生的宏观背景
}
```

###### 人物设定 (`character_guide`)
```json
{
  "protagonist": { // 主角设定
    "background": "示例主角背景故事",
    "initial_personality": "示例主角初始性格",
    "growth_path": "示例主角成长或转变路径"
  },
  "supporting_roles": [ // 重要配角列表
    {
      "role_type": "示例配角类型 (例如: 导师, 挚友, 竞争对手)", // 配角的类型或定位
      "personality": "示例配角性格",
      "relationship": "示例配角与主角的关系"
    }
    // 可添加更多配角...
  ],
  "antagonists": [ // 主要反派列表
    {
      "role_type": "示例反派类型 (例如: 宿敌, 幕后黑手, 理念冲突者)", // 反派的类型或定位
      "personality": "示例反派性格",
      "conflict_point": "示例反派与主角的核心冲突"
    }
    // 可添加更多反派...
  ]
}
```

###### 情节结构 (`plot_structure`)
这部分定义了故事的大致走向，可以参考经典的三幕剧结构或其他结构。
```json
{
  "act_one": { // 第一幕：开端
    "setup": "示例开篇设定和背景介绍",
    "inciting_incident": "示例激励事件，故事的起点",
    "first_plot_point": "示例第一主要情节转折点"
  },
  "act_two": { // 第二幕：发展
    "rising_action": "示例上升情节，主角应对挑战",
    "midpoint": "示例中点事件，重要的转折或揭示",
    "complications": "示例情节复杂化，困难加剧",
    "darkest_moment": "示例主角面临的最低谷或最大危机",
    "second_plot_point": "示例第二主要情节转折点，导向结局"
  },
  "act_three": { // 第三幕：结局
    "climax": "示例高潮，最终对决或问题解决",
    "resolution": "示例结局，事件的最终结果",
    "denouement": "示例尾声，展示结局后的状态"
  }
}
```

###### 写作风格指南 (`style_guide`)
```json
{
  "tone": "示例整体基调 (例如: 轻松幽默, 严肃深刻)", // 小说的整体情感色彩
  "pacing": "示例节奏控制 (例如: 快节奏, 张弛有度)", // 故事进展的速度
  "description_focus": [ // 描写侧重点列表
    "示例描写侧重点1 (例如: 动作场面)", // AI应侧重描写的方面
    "示例描写侧重点2 (例如: 内心活动)",
    "示例描写侧重点3 (例如: 环境氛围)"
    // 可添加更多侧重点...
  ]
}
```

##### 2.3.3 额外指导 (`extra_guidance`) (可选)

提供更具体、细化的写作规则，进一步约束或引导 AI 的生成。

```json
{
  "writing_style": { // 细化的写作风格要求
    "pacing": "示例章节节奏 (例如: 每章一个小高潮)",
    "description": "示例描写风格 (例如: 简洁, 华丽)",
    "dialogue": "示例对话风格 (例如: 生活化, 富含信息)",
    "action": "示例动作场景风格 (例如: 强调速度, 强调策略)"
  },
  "content_rules": { // 内容规则
    "must_include": [ // 每章或整体必须包含的特定元素
      "示例必须包含的元素1",
      "示例必须包含的元素2"
     ],
    "must_avoid": [ // 需要避免的情节或设定
      "示例必须避免的内容1",
      "示例必须避免的内容2"
     ]
  },
  "chapter_structure": { // 章节结构建议
    "opening": "示例章节开头方式 (例如: 以悬念开始)",
    "development": "示例章节情节推进方式",
    "climax": "示例章节高潮设置方式",
    "ending": "示例章节结尾方式 (例如: 留下钩子)"
  },
  "plot_corrections": { // 针对常见网文套路的修正或创新点 (可选)
    "example_correction_1": {
      "title": "示例修正点标题1", // 修正点的简要概括
      "description": "示例修正点描述1，说明如何避免某个套路或进行创新" // 具体描述
    },
    "example_correction_2": {
      "title": "示例修正点标题2",
      "description": "示例修正点描述2"
    }
    // 可添加更多修正点...
  }
}
```

#### 2.4 生成配置 (generation_config)

控制小说生成过程的配置项。

```json
{
  "max_retries": 3,                                     // 生成失败时的最大重试次数
  "retry_delay": 10,                                    // 重试间隔时间（秒）
  "force_rebuild_kb": false,                            // 是否强制重建知识库
  "validation": {                                       // 内容验证选项
    "check_logic": true,                                // 检查逻辑连贯性
    "check_consistency": true,                          // 检查前后一致性
    "check_duplicates": true                            // 检查重复内容
  }
}
```

#### 2.5 输出配置 (output_config)

控制生成结果的保存配置项。

```json
{
  "format": "txt",                                      // 输出文件格式
  "encoding": "utf-8",                                  // 文件编码
  "save_outline": true,                                 // 是否保存大纲
  "save_character_states": true,                        // 是否保存角色状态
  "output_dir": "data/output"                           // 输出目录
}
```

## 注意事项

1. 首次运行时会自动创建必要的目录结构
2. 确保参考小说文件存在且格式正确
3. 生成过程中可以随时中断，下次运行时会询问是否继续
4. 建议定期备份生成的内容
5. 请妥善保管 `.env` 文件中的 API 密钥，不要将其提交到版本控制系统

## 常见问题

1. API 密钥配置问题
   - 检查 `.env` 文件是否正确配置
   - 确认 API 密钥是否有效
   - 确保环境变量已正确加载

2. 知识库构建失败
   - 检查参考文件是否存在
   - 确认文件编码为 UTF-8
   - 验证知识库配置参数是否合理

3. 生成内容质量不理想
   - 调整 `config.json` 中的生成参数
   - 提供更多优质的参考小说
   - 检查写作指南的详细程度

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。 