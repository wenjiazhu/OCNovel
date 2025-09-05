# OCNovel - AI小说生成系统

一个基于Python的AI小说自动生成系统，支持东方玄幻、仙侠、武侠等多种类型的小说创作。系统采用模块化设计，集成了多种AI模型接口，提供从大纲生成到章节内容创作的全流程自动化。

## 项目结构

```
OCNovel/
├── main.py                    # 主程序入口
├── config.json.example        # 配置文件模板
├── config.json               # 配置文件（基于模板生成）
├── requirements.txt          # Python依赖包列表
├── .env.example              # 环境变量模板
├── .env                      # 环境变量配置
├── README.md                 # 项目说明文档
├── .gitignore               # Git忽略配置
│
├── src/                      # 源代码目录
│   ├── config/               # 配置管理模块
│   │   ├── ai_config.py      # AI模型配置管理
│   │   └── config.py         # 通用配置管理
│   │
│   ├── generators/           # 内容生成器模块
│   │   ├── common/           # 通用数据结构和工具
│   │   │   ├── data_structures.py  # 数据结构定义
│   │   │   └── utils.py      # 通用工具函数
│   │   │
│   │   ├── content/          # 章节内容生成
│   │   │   ├── content_generator.py    # 内容生成器
│   │   │   ├── consistency_checker.py # 一致性检查器
│   │   │   └── validators.py          # 内容验证器
│   │   │
│   │   ├── outline/          # 大纲生成
│   │   │   └── outline_generator.py   # 大纲生成器
│   │   │
│   │   ├── finalizer/        # 内容最终化处理
│   │   │   └── finalizer.py           # 内容最终化器
│   │   │
│   │   ├── models.py         # 生成模型定义
│   │   ├── prompts.py        # 提示词模板
│   │   ├── title_generator.py        # 标题生成器
│   │   └── humanization_prompts.py  # 人性化提示词
│   │
│   ├── models/               # AI模型接口
│   │   ├── base_model.py     # 基础模型抽象类
│   │   ├── gemini_model.py   # Google Gemini模型接口
│   │   └── openai_model.py   # OpenAI模型接口
│   │
│   ├── knowledge_base/       # 知识库模块
│   │   └── knowledge_base.py # 知识库管理
│   │
│   └── tools/                # 工具和辅助功能
│       ├── generate_config.py       # 配置生成工具
│       └── generate_marketing.py     # 营销内容生成
│
└── data/                     # 数据目录
    ├── cache/                # 缓存数据存储
    ├── logs/                 # 日志文件存储
    ├── output/               # 生成内容输出目录
    ├── marketing/            # 营销内容存储
    ├── reference/            # 参考资料存储
    └── style_sources/        # 风格源文件存储
```

## 核心模块功能

### 1. 配置管理模块 (`src/config/`)
- **config.py**: 统一的配置管理类，支持环境变量加载和敏感信息过滤
- **ai_config.py**: AI模型配置管理，支持多模型切换和配置

### 2. 内容生成模块 (`src/generators/`)
- **outline_generator.py**: 小说大纲生成器，支持章节结构规划
- **content_generator.py**: 章节内容生成器，集成一致性检查和验证
- **consistency_checker.py**: 内容一致性检查，确保情节连贯
- **validators.py**: 内容验证器，检查逻辑和重复内容
- **finalizer.py**: 内容最终化处理，优化输出质量

### 3. AI模型接口 (`src/models/`)
- **base_model.py**: 基础模型抽象类，定义统一接口
- **gemini_model.py**: Google Gemini模型接口实现
- **openai_model.py**: OpenAI模型接口实现
- 支持多模型切换和备用模型机制

### 4. 知识库模块 (`src/knowledge_base/`)
- **knowledge_base.py**: 知识库管理，支持参考文件加载和缓存
- 支持文本分块和语义搜索功能

### 环境配置
- Python 3.9+
- 支持的AI模型API密钥（OpenAI、Gemini、VolcEngine等）
- 配置文件 `config.json`（基于 `config.json.example` 生成）
- 环境变量文件 `.env`（包含API密钥等敏感信息）

## 基础使用示例

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置设置
复制配置文件模板并修改：
```bash
cp config.json.example config.json
cp .env.example .env
```

编辑 `config.json` 配置小说参数：
```json
{
    "novel_config": {
        "type": "东方玄幻",
        "theme": "凡人流、成长、冒险",
        "title": "牧神记",
        "target_chapters": 100,
        "chapter_length": 2500
    }
}
```

编辑 `.env` 配置API密钥：
```bash
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
VOLCENGINE_ACCESS_KEY=your_volcengine_key
VOLCENGINE_SECRET_KEY=your_volcengine_secret
```

### 3. 运行小说生成
```bash
# 生成小说大纲（第1-10章）
python main.py outline --start 1 --end 10

# 生成指定章节内容（重新生成第5章）
python main.py content --target-chapter 5

# 生成章节内容（从第3章开始继续）
python main.py content --start-chapter 3

# 处理章节定稿（处理第8章）
python main.py finalize --chapter 8

# 自动执行完整流程（大纲+内容+定稿）
python main.py auto

# 强制重新生成所有大纲后执行完整流程
python main.py auto --force-outline

# 仿写文本（基于风格范文）
python main.py imitate --style-source data/style_sources/范文.txt --input-file data/input/原始文本.txt --output-file data/output/仿写结果.txt

# 使用额外提示词
python main.py outline --start 1 --end 5 --extra-prompt "增加悬疑元素"
python main.py content --extra-prompt "增加人物对话"
python main.py auto --extra-prompt "保持轻松幽默风格"
```

## 配置说明

### 主要配置项
- **knowledge_base_config**: 知识库配置（分块大小、重叠、缓存目录）
- **log_config**: 日志配置（目录、级别、格式）
- **novel_config**: 小说配置（类型、主题、风格、标题、目标章节数）
- **generation_config**: 生成配置（重试次数、批量大小、模型选择）
- **output_config**: 输出配置（格式、编码、保存选项）
- **imitation_config**: 风格模仿配置（启用状态、风格源文件）

### 支持的小说类型
- 东方玄幻
- 仙侠修真  
- 武侠江湖
- 都市异能
- 历史架空
- 科幻奇幻

## 开发说明

### 架构设计原则
1. **分层架构**: 表示层、业务逻辑层、服务层、数据层分离
2. **模块化设计**: 各功能模块独立，便于扩展和维护
3. **统一接口**: AI模型统一接口设计，支持多模型切换
4. **错误处理**: 完善的错误处理和重试机制
5. **配置管理**: 统一的配置管理和环境变量支持