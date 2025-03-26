# OCNovel - AI 小说生成工具

OCNovel 是一个基于大语言模型的智能小说生成工具，能够根据参考小说和用户设定的主题、风格等参数，自动生成完整的长篇小说。

## 功能特点

- 🤖 支持多种 AI 模型（Gemini、OpenAI）
- 📚 智能知识库系统，支持参考小说导入和分析
- 📝 自动生成小说大纲和章节内容
- 👥 智能角色管理系统
- 🎯 支持章节重新生成和内容优化
- 📊 完整的日志记录系统
- 🎨 支持生成营销内容（标题、封面等）

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

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并添加以下内容：
```
# Gemini API配置
GEMINI_API_KEY=你的Gemini API密钥

# OpenAI API配置
OPENAI_API_KEY=你的OpenAI API密钥
OPENAI_API_BASE=你的OpenAI API基础URL（可选）
```

4. 配置项目：
编辑 `config.json` 文件，设置：
- 小说类型、主题和风格
- 目标长度和章节长度
- 参考小说文件路径
- 其他生成参数

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
python src/tools/chapter_regenerator.py --chapter <章节号> --prompt "额外提示词"
```

### 3. 生成营销内容

```bash
python src/tools/generate_marketing.py --keywords "关键词1" "关键词2" --characters "角色1" "角色2"
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
│   ├── generators/    # 生成器
│   ├── knowledge_base/# 知识库
│   ├── models/        # AI模型
│   └── tools/         # 工具脚本
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
  "log_level": "DEBUG",                                // 日志级别：DEBUG/INFO/WARNING/ERROR
  "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"  // 日志格式
}
```

#### 2.3 小说配置 (novel_config)

定义要生成的小说基本信息和写作指南。

##### 2.3.1 基本信息
```json
{
  "type": "玄幻",                                      // 小说类型：如玄幻、武侠、都市等
  "theme": "修真逆袭",                                 // 小说主题：如修真逆袭、都市重生等
  "style": "热血",                                     // 写作风格：如热血、轻松、严肃等
  "target_length": 1000000,                            // 目标总字数
  "chapter_length": 2500,                              // 每章字数
  "reference_files": ["data/reference/my_novel.txt"]   // 参考小说文件列表
}
```

##### 2.3.2 写作指南 (writing_guide)

###### 世界观设定 (world_building)
```json
{
  "magic_system": "以灵气修炼为主，分为天地玄黄四个大境界",  // 修炼体系说明
  "social_system": "修真门派为主，世俗王朝为辅",            // 社会体系说明
  "background": "末法时代，灵气复苏"                       // 时代背景说明
}
```

###### 人物设定 (character_guide)
```json
{
  "protagonist": {                                      // 主角设定
    "background": "普通散修",                           // 背景设定
    "initial_personality": "坚韧、重情、智慧",           // 初始性格特点
    "growth_path": "逆境成长"                           // 成长路线
  },
  "supporting_roles": [                                 // 配角设定列表
    {
      "role_type": "师尊",                              // 角色类型
      "personality": "深沉智慧",                         // 性格特点
      "relationship": "亦师亦父"                         // 与主角关系
    }
  ],
  "antagonists": [                                      // 反派设定列表
    {
      "role_type": "宿敌",
      "personality": "阴狠毒辣",
      "conflict_point": "夺宝之争"                      // 冲突点
    }
  ]
}
```

###### 情节结构 (plot_structure)
```json
{
  "act_one": {                                          // 第一幕：开篇
    "setup": "主角发现自身特殊体质",                     // 开场设定
    "inciting_incident": "获得上古传承",                 // 引子事件
    "first_plot_point": "被迫离开家乡"                   // 第一个转折点
  },
  "act_two": {                                          // 第二幕：发展
    "rising_action": "加入门派，逐步成长",               // 上升情节
    "midpoint": "身世之谜揭开",                          // 中点转折
    "complications": "与宿敌的多次对抗"                  // 复杂化情节
  },
  "act_three": {                                        // 第三幕：结局
    "climax": "终极决战",                               // 高潮
    "resolution": "飞升成仙"                            // 结局
  }
}
```

###### 写作风格指南 (style_guide)
```json
{
  "tone": "热血激昂中带有智慧思考",                      // 整体基调
  "pacing": "快节奏，重要场景适当放慢",                  // 节奏控制
  "description_focus": [                                // 重点描写方向列表
    "修炼场景要细致",
    "战斗场景要激烈",
    "情感描写要真挚",
    "人物对话要生动",
    "语言风格要诙谐"
  ]
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