from typing import Dict, List, Optional
import dataclasses # 导入 dataclasses 以便类型提示
import json

# 如果 ChapterOutline 只在此处用作类型提示，可以简化或使用 Dict
# from .novel_generator import ChapterOutline # 或者定义一个类似的结构

# 为了解耦，我们这里使用 Dict 作为 outline 的类型提示
# @dataclasses.dataclass
# class SimpleChapterOutline:
#     chapter_number: int
#     title: str
#     key_points: List[str]
#     characters: List[str]
#     settings: List[str]
#     conflicts: List[str]


def get_outline_prompt(
    novel_type: str,
    theme: str,
    style: str,
    current_start_chapter_num: int,
    current_batch_size: int,
    existing_context: str = "",
    extra_prompt: Optional[str] = None
) -> str:
    """生成用于创建小说大纲的提示词。"""
    extra_requirements = f"\n[额外要求]\n{extra_prompt}\n" if extra_prompt else ""

    prompt = f"""{existing_context}

你具有极强的逆向思维，熟知起点中文网、番茄中文网、七猫小说网、晋江文学城的风格与爽文套路，经常提出打破他人认知的故事创意。你的思考过程应该是原始的、有机的和自然的，捕捉真实的人类思维流程，更像是一个意识流。请严格按照要求，基于以上小说信息和已有大纲（如果是续写或替换），创作后续的小说大纲。

任务要求：
1.  生成从第 {current_start_chapter_num} 章开始的，共 {current_batch_size} 个章节的大纲。
2.  确保情节连贯，与已有上下文自然衔接。推动主线发展，引入新的冲突和看点。{extra_requirements}
3.  每章设计一个小高潮(如反转\打脸\冲突解决\悬念揭晓等)，每3章设计一个大高潮(达成目标\境界突破\战胜强敌等)。
4.  每章大纲必须包含以下字段：章节号 (chapter_number, 整数，必须与请求的章节号对应)，标题 (title, 字符串)，关键剧情点列表 (key_points, 字符串列表)，涉及角色列表 (characters, 字符串列表)，场景列表 (settings, 字符串列表)，核心冲突列表 (conflicts, 字符串列表)。
5.  严格按照以下 JSON 格式返回一个包含 {current_batch_size} 个章节大纲对象的列表。不要在 JSON 列表前后添加任何其他文字、解释或代码标记 (如 ```json ... ```)。JSON 列表必须直接开始于 '[' 结束于 ']'。

```json
[
  {{
    "chapter_number": {current_start_chapter_num},
    "title": "...",
    "key_points": ["...", "..."],
    "characters": ["...", "..."],
    "settings": ["...", "..."],
    "conflicts": ["...", "..."]
  }},
  // ... (如果 current_batch_size > 1, 继续添加后续章节对象，确保 chapter_number 连续递增)
]
```
"""
    return prompt


def get_chapter_prompt(
    outline: Dict, 
    references: Dict,
    extra_prompt: str = "",
    context_info: str = ""
) -> str:
    """生成用于创建章节内容的提示词。"""

    novel_number = outline.get('chapter_number', '未知')
    chapter_title = outline.get('title', '未知')
    key_points = ', '.join(outline.get('key_points', []))
    characters = ', '.join(outline.get('characters', []))
    settings = ', '.join(outline.get('settings', []))
    conflicts = ', '.join(outline.get('conflicts', []))
    
    # 添加系统角色设定
    system_prompt = """你具有极强的逆向思维，熟知起点中文网、番茄中文网、七猫小说网、晋江文学城的风格与爽文套路，经常提出打破他人认知的故事创意。你的思考过程应该是原始的、有机的和自然的，捕捉真实的人类思维流程，更像是一个意识流。"""
    
    # 根据章节号确定使用哪个提示词模板
    if novel_number == 1:
        # 第一章使用 first_chapter_draft_prompt
        base_prompt = f"""
{system_prompt}

即将创作：第 {novel_number} 章《{chapter_title}》
本章定位：开篇章节
核心作用：引入主角和世界观
悬念密度：中等
伏笔操作：埋设初始伏笔
认知颠覆：★☆☆☆☆
本章简述：{key_points}

可用元素：
- 核心人物：{characters}
- 关键场景：{settings}
- 核心冲突：{conflicts}

[参考信息]
情节参考：
{chr(10).join(references['plot_references'])}

角色参考：
{chr(10).join(references['character_references'])}

场景参考：
{chr(10).join(references['setting_references'])}

完成第 {novel_number} 章的正文，至少设计下方2个或以上具有动态张力的场景：
1. 对话场景：
   - 潜台词冲突（表面谈论A，实际博弈B）
   - 权力关系变化（通过非对称对话长度体现）

2. 动作场景：
   - 环境交互细节（至少3个感官描写）
   - 节奏控制（短句加速+比喻减速）
   - 动作揭示人物隐藏特质

3. 心理场景：
   - 认知失调的具体表现（行为矛盾）
   - 隐喻系统的运用（连接世界观符号）
   - 决策前的价值天平描写

4. 环境场景：
   - 空间透视变化（宏观→微观→异常焦点）
   - 非常规感官组合（如"听见阳光的重量"）
   - 动态环境反映心理（环境与人物心理对应）

[写作风格]
请专注于情节推进、人物刻画和场景描写，确保内容引人入胜，尽量使文字的AIGC值低于50%。
尽量减少乃至避免以下内容：主角的内心OS、配角的心理描写、作者的评论或议论。
步步为营的成长线、伏笔与填坑（如"神秘小瓶的隐藏作用"）、多视角冲突（如"门派内斗""跨界追杀"）。
简练白描文风、重复句式强化节奏（如"法宝祭出，金光一闪"）、画面感强的场景描写（如"竹海如刃，火焚天地"）。


[格式要求]
1.仅返回章节正文文本；
2.不使用分章节小标题；
3.长短句交错，一句一段；
4.不要使用markdown格式;
5.过滤*号、#号、空格等非常规文本字符。
"""
    else:
        # 后续章节使用标准提示词
        base_prompt = f"""
{system_prompt}

请根据以下章节大纲和参考信息，创作小说章节内容。

[章节大纲]
章节号: {novel_number}
标题: {chapter_title}
关键剧情点: {key_points}
涉及角色: {characters}
场景设定: {settings}
核心冲突: {conflicts}

[参考信息]
情节参考：
{chr(10).join(references['plot_references'])}

角色参考：
{chr(10).join(references['character_references'])}

场景参考：
{chr(10).join(references['setting_references'])}

[写作风格]
请专注于情节推进、人物刻画和场景描写，确保内容引人入胜，尽量使文字的AIGC值低于50%。
尽量减少乃至避免以下内容：主角的内心OS、配角的心理描写、作者的评论或议论。
步步为营的成长线、伏笔与填坑（如"神秘小瓶的隐藏作用"）、多视角冲突（如"门派内斗""跨界追杀"）。
简练白描文风、重复句式强化节奏（如"法宝祭出，金光一闪"）、画面感强的场景描写（如"竹海如刃，火焚天地"）

[格式要求]
1.仅返回章节正文文本；
2.不使用分章节小标题；
3.长短句交错，一句一段；
4.不要使用markdown格式。
"""

    # 添加额外要求
    if extra_prompt:
        base_prompt += f"\n\n[额外要求]\n{extra_prompt}"

    # 添加上下文信息
    if context_info:
        base_prompt += f"\n\n[上下文信息]\n{context_info}"

    # 添加连贯性要求
    base_prompt += f"""

[连贯性要求]
1. 请确保本章情节与上一章摘要中描述的情节有明确的连接
2. 章节开头应自然承接上一章的结尾，避免跳跃感
3. 章节结尾应为下一章大纲中的情节埋下伏笔
4. 确保人物情感和行为的连续性，避免角色表现前后矛盾
5. 时间线和场景转换要清晰流畅
"""
    return base_prompt


def get_summary_prompt(
    chapter_content: str
) -> str:
    """生成用于创建章节摘要的提示词。"""
    prompt = f"""
请为以下章节内容生成一个200字以内的摘要，要求：
1. 直接描述主要情节发展，不要使用"本章讲述了"等描述性文字
2. 突出关键人物的重要行动
3. 说明对整体剧情的影响
4. 字数控制在200字以内
5. 使用简洁的叙述语言，避免修饰性词语

章节内容：
{chapter_content[:4000]}... (内容过长已截断)
"""
    return prompt

# 注意：关于"章节回顾提示词"，在您提供的代码中没有找到明确对应的生成逻辑。
# 如果您需要这个功能，请提供更多信息，我可以为您添加相应的函数。 

# =============== 4. 角色状态更新提示词 ===================
def get_character_update_prompt(
    chapter_text: str,
    old_state: str
) -> str:
    """生成用于更新角色状态的提示词。"""
    return f"""
以下是新完成的章节文本：
{chapter_text}

这是当前的角色状态文档：
{old_state}

请严格按照以下规则更新主要角色状态：

1. 状态更新规则：
   - 必须基于章节文本中的具体描写
   - 禁止添加章节中未提及的内容
   - 保持原有格式，仅更新变化的部分
   - 删除过时或错误的信息

2. 内容验证：
   - 每个状态更新必须有文本依据
   - 保持人物性格和行为的一致性
   - 确保能力描述与实际表现相符
   - 关系网络必须反映最新互动

3. 格式要求：
   - 保持原有的树形结构
   - 使用统一的缩进和符号
   - 每个属性必须用【名称: 描述】格式
   - 状态必须包含身体和心理两个维度

4. 更新优先级：
   - 当前章节明确提到的变化优先
   - 与当前章节冲突的信息必须删除
   - 未提及的信息保持原样
   - 模糊的信息需要进一步确认

请直接返回更新后的角色状态文本，不要解释任何内容。
"""

# =============== 5. 角色导入提示词 ===================
def get_character_import_prompt(content: str) -> str:
    """生成用于导入角色信息的提示词。"""
    return f"""
根据以下文本内容，分析出所有角色及其属性信息，严格按照以下格式要求：

<<角色状态格式要求>>
1. 必须包含以下五个分类（按顺序）：
   ● 物品 ● 能力 ● 状态 ● 主要角色间关系网 ● 触发或加深的事件
2. 每个属性条目必须用【名称: 描述】格式
   例：├──青衫: 一件破损的青色长袍，带有暗红色污渍
3. 状态必须包含：
   ● 身体状态: [当前身体状况]
   ● 心理状态: [当前心理状况]
4. 关系网格式：
   ● [角色名称]: [关系类型，如"竞争对手"/"盟友"]
5. 触发事件格式：
   ● [事件名称]: [简要描述及影响]

<<示例>>
李员外:
├──物品:
│  ├──青衫: 一件破损的青色长袍，带有暗红色污渍
│  └──寒铁长剑: 剑身有裂痕，刻有「青云」符文
├──能力:
│  ├──精神感知: 能感知半径30米内的生命体
│  └──剑气压制: 通过目光释放精神威压
├──状态:
│  ├──身体状态: 右臂有未愈合的刀伤
│  └──心理状态: 对苏明远的实力感到忌惮
├──主要角色间关系网:
│  ├──苏明远: 竞争对手，十年前的同僚
│  └──林婉儿: 暗中培养的继承人
├──触发或加深的事件:
│  ├──兵器库遇袭: 丢失三把传家宝剑，影响战力
│  └──匿名威胁信: 信纸带有檀香味，暗示内部泄密
│

请严格按上述格式分析以下内容：
<<待分析小说文本开始>>
{content}
<<待分析小说文本结束>>
"""

# =============== 6. 前文摘要更新提示词 ===================
def get_global_summary_prompt(
    chapter_text: str,
    global_summary: str = ""
) -> str:
    """生成用于更新全局摘要的提示词。"""
    return f"""
以下是新完成的章节文本：
{chapter_text}

这是当前的前文摘要（可为空）：
{global_summary}

请根据本章新增内容，更新前文摘要。
要求：
- 保留既有重要信息，同时融入新剧情要点
- 以简洁、连贯的语言描述全书进展
- 客观描绘，不展开联想或解释
- 总字数控制在2000字以内

仅返回前文摘要文本，不要解释任何内容。
"""

# =============== 7. 核心种子设定提示词 ===================
def get_core_seed_prompt(
    topic: str,
    genre: str,
    number_of_chapters: int,
    word_number: int
) -> str:
    """生成用于创建核心种子设定的提示词。"""
    return f"""
作为专业作家，请用"雪花写作法"第一步构建故事核心：
主题：{topic}
类型：{genre}
篇幅：约{number_of_chapters}章（每章{word_number}字）

请用单句公式概括故事本质，例如：
"当[主角]遭遇[核心事件]，必须[关键行动]，否则[灾难后果]；与此同时，[隐藏的更大危机]正在发酵。"

要求：
1. 必须包含显性冲突与潜在危机
2. 体现人物核心驱动力
3. 暗示世界观关键矛盾
4. 使用25-100字精准表达

仅返回故事核心文本，不要解释任何内容。
"""

# =============== 8. 当前章节摘要生成提示词 ===================
def get_recent_chapters_summary_prompt(
    combined_text: str,
    novel_number: int,
    chapter_title: str,
    chapter_role: str,
    chapter_purpose: str,
    suspense_level: str,
    foreshadowing: str,
    plot_twist_level: str,
    chapter_summary: str,
    next_chapter_number: int,
    next_chapter_title: str,
    next_chapter_role: str,
    next_chapter_purpose: str,
    next_chapter_suspense_level: str,
    next_chapter_foreshadowing: str,
    next_chapter_plot_twist_level: str,
    next_chapter_summary: str
) -> str:
    """生成用于创建当前章节摘要的提示词。"""
    return f"""
作为一名专业的小说编辑和知识管理专家，正在基于已完成的前三章内容和本章信息生成当前章节的精准摘要。请严格遵循以下工作流程：
前三章内容：
{combined_text}

当前章节信息：
第{novel_number}章《{chapter_title}》：
├── 本章定位：{chapter_role}
├── 核心作用：{chapter_purpose}
├── 悬念密度：{suspense_level}
├── 伏笔操作：{foreshadowing}
├── 认知颠覆：{plot_twist_level}
└── 本章简述：{chapter_summary}

下一章信息：
第{next_chapter_number}章《{next_chapter_title}》：
├── 本章定位：{next_chapter_role}
├── 核心作用：{next_chapter_purpose}
├── 悬念密度：{next_chapter_suspense_level}
├── 伏笔操作：{next_chapter_foreshadowing}
├── 认知颠覆：{next_chapter_plot_twist_level}
└── 本章简述：{next_chapter_summary}

**上下文分析阶段**：
1. 回顾前三章核心内容：
   - 第一章核心要素：[章节标题]→[核心冲突/理论]→[关键人物/概念]
   - 第二章发展路径：[已建立的人物关系]→[技术/情节进展]→[遗留伏笔]
   - 第三章转折点：[新出现的变量]→[世界观扩展]→[待解决问题]
2. 提取延续性要素：
   - 必继承要素：列出前3章中必须延续的3个核心设定
   - 可调整要素：识别2个允许适度变化的辅助设定

**当前章节摘要生成规则**：
1. 内容架构：
   - 继承权重：70%内容需与前3章形成逻辑递进
   - 创新空间：30%内容可引入新要素，但需标注创新类型（如：技术突破/人物黑化）
2. 结构控制：
   - 采用"承继→发展→铺垫"三段式结构
   - 每段含1个前文呼应点+1个新进展
3. 预警机制：
   - 若检测到与前3章设定冲突，用[!]标记并说明
   - 对开放式发展路径，提供2种合理演化方向

现在请你基于目前故事的进展，完成以下两件事：
用最多800字，写一个简洁明了的「当前章节摘要」；

请按如下格式输出（不需要额外解释）：
当前章节摘要: <这里写当前章节摘要>
"""

# =============== 9. 章节一致性检查提示词 ===================
def get_consistency_check_prompt(
    chapter_content: str,
    chapter_outline: Dict,
    previous_summary: str = "",
    global_summary: str = "",
    character_info: str = ""
) -> str:
    """生成用于检查章节一致性的提示词"""
    return f"""
作为小说一致性检查专家，请基于以下信息评估章节内容的一致性，并提供详细报告：

[全局信息]
前文摘要：
{global_summary if global_summary else "（无前文摘要）"}

[上一章摘要]
{previous_summary if previous_summary else "（无上一章摘要）"}

[当前章节大纲]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}
场景设定：{', '.join(chapter_outline.get('settings', []))}
核心冲突：{', '.join(chapter_outline.get('conflicts', []))}

[角色信息]
{character_info if character_info else "（无角色信息）"}

[待检查章节内容]
{chapter_content}

===== 一致性检查标准 =====
请从以下五个维度进行评估，各占20分，总分100分：

1. 主题一致性：章节内容是否符合大纲设定的主题和核心冲突
2. 情节连贯性：与上一章是否有合理的承接，情节发展是否自然
3. 角色一致性：人物言行是否符合角色设定，性格表现是否连贯
4. 世界观一致性：是否符合已建立的世界设定、规则和环境
5. 逻辑完整性：情节中是否存在明显漏洞、不合理、断层或自相矛盾之处

===== 输出格式 =====
[总体评分]: <0-100分>

[主题一致性评分]: <0-20分>
[主题一致性分析]:
<分析内容>

[情节连贯性评分]: <0-20分>
[情节连贯性分析]:
<分析内容>

[角色一致性评分]: <0-20分>
[角色一致性分析]:
<分析内容>

[世界观一致性评分]: <0-20分>
[世界观一致性分析]:
<分析内容>

[逻辑完整性评分]: <0-20分>
[逻辑完整性分析]:
<分析内容>

[总体建议]:
<如有需要修改的地方，请提供具体的修改建议>

[修改必要性]: <"需要修改"或"无需修改">
"""

# =============== 10. 章节修正提示词 ===================
def get_chapter_revision_prompt(
    original_content: str,
    consistency_report: str,
    chapter_outline: Dict,
    previous_summary: str = "",
    global_summary: str = ""
) -> str:
    """生成用于修正章节内容的提示词"""
    return f"""
作为专业小说修改专家，请基于一致性检查报告，对小说章节进行必要的修改：

[一致性检查报告]
{consistency_report}

[原章节内容]
{original_content}

[章节大纲要求]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}
场景设定：{', '.join(chapter_outline.get('settings', []))}
核心冲突：{', '.join(chapter_outline.get('conflicts', []))}

[上下文信息]
前文摘要：{global_summary if global_summary else "（无前文摘要）"}
上一章摘要：{previous_summary if previous_summary else "（无上一章摘要）"}

===== 修改要求 =====
1. 专注于修复一致性检查报告中指出的问题
2. 保持原文风格和叙事方式
3. 确保与前文的连贯性
4. 保持修改后的文本长度与原文相近
5. 确保修改符合章节大纲的要求

请直接提供修改后的完整章节内容，不要解释修改内容或加入额外的文本。
"""

# =============== 11. 知识库检索提示词 ===================
def get_knowledge_search_prompt(
    chapter_number: int,
    chapter_title: str,
    characters_involved: List[str],
    key_items: List[str],
    scene_location: str,
    chapter_role: str,
    chapter_purpose: str,
    foreshadowing: str,
    short_summary: str,
    user_guidance: str = "",
    time_constraint: str = ""
) -> str:
    """生成用于知识库检索的提示词"""
    return f"""请基于以下当前写作需求，生成合适的知识库检索关键词：
    
章节元数据：
- 准备创作：第{chapter_number}章
- 章节主题：{chapter_title}
- 核心人物：{', '.join(characters_involved)}
- 关键道具：{', '.join(key_items)}
- 场景位置：{scene_location}
    
写作目标：
- 本章定位：{chapter_role}
- 核心作用：{chapter_purpose}
- 伏笔操作：{foreshadowing}
    
当前摘要：
{short_summary}
    
- 用户指导：
{user_guidance}
    
- 核心人物(可能未指定)：{', '.join(characters_involved)}
- 关键道具(可能未指定)：{', '.join(key_items)}
- 空间坐标(可能未指定)：{scene_location}
- 时间压力(可能未指定)：{time_constraint}
    
生成规则：
    
    
1.关键词组合逻辑：
-类型1：[实体]+[属性]（如"量子计算机 故障日志"）
-类型2：[事件]+[后果]（如"实验室爆炸 辐射泄漏"）
-类型3：[地点]+[特征]（如"地下城 氧气循环系统"）
    
2.优先级：
-首选用户指导中明确提及的术语
-次选当前章节涉及的核心道具/地点
-最后补充可能关联的扩展概念
    
3.过滤机制：
-排除抽象程度高于"中级"的概念
-排除与前3章重复率超60%的词汇
    
请生成3-5组检索词，按优先级降序排列。
格式：每组用"·"连接2-3个关键词，每组占一行
    
示例：
科技公司·数据泄露
地下实验室·基因编辑·禁忌实验
"""


# =============== 12. 知识库内容过滤提示词 ===================
def get_knowledge_filter_prompt(
    retrieved_texts: List[str],
    chapter_info: Dict
) -> str:
    """生成用于过滤知识库内容的提示词"""
    return f"""对知识库内容进行三级过滤：
    
待过滤内容：
{chr(10).join(retrieved_texts)}
    
当前叙事需求：
{json.dumps(chapter_info, ensure_ascii=False, indent=2)}
    
过滤流程：
    
    
冲突检测：
    
删除与已有摘要重复度＞40%的内容
    
标记存在世界观矛盾的内容（使用▲前缀）
    
价值评估：
    
关键价值点（❗标记）：
· 提供新的角色关系可能性
· 包含可转化的隐喻素材
· 存在至少2个可延伸的细节锚点
    
次级价值点（·标记）：
· 补充环境细节
· 提供技术/流程描述
    
结构重组：
    
按"情节燃料/人物维度/世界碎片/叙事技法"分类
    
为每个分类添加适用场景提示（如"可用于XX类型伏笔"）
    
输出格式：
[分类名称]→[适用场景]
❗/· [内容片段] （▲冲突提示）
...
    
示例：
[情节燃料]→可用于时间压力类悬念
❗ 地下氧气系统剩余23%储量（可制造生存危机）
▲ 与第三章提到的"永久生态循环系统"存在设定冲突
"""

def get_logic_check_prompt(
    chapter_content: str,
    chapter_outline: Dict
) -> str:
    """生成用于检查章节逻辑严密性的提示词"""
    return f"""请检查以下章节内容的逻辑严密性：

[章节大纲]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}
场景设定：{', '.join(chapter_outline.get('settings', []))}
核心冲突：{', '.join(chapter_outline.get('conflicts', []))}

[章节内容]
{chapter_content}

===== 逻辑检查标准 =====
请从以下维度评估章节内容的逻辑严密性：

1. 因果关系
   - 事件发生是否有合理的因果关联
   - 人物行为是否有合理的动机
   - 情节转折是否有充分的铺垫

2. 时间线
   - 事件发生顺序是否合理
   - 时间跨度是否合理
   - 是否存在时间线矛盾

3. 空间逻辑
   - 场景转换是否合理
   - 人物位置关系是否合理
   - 是否存在空间矛盾

4. 能力设定
   - 人物能力表现是否合理
   - 是否违反已设定的能力规则
   - 能力提升是否有合理依据

5. 世界观
   - 是否符合已建立的世界规则
   - 是否存在世界观矛盾
   - 新设定是否与已有设定冲突

===== 输出格式 =====
[总体评分]: <0-100分>

[因果关系评分]: <0-20分>
[因果关系分析]:
<分析内容>

[时间线评分]: <0-20分>
[时间线分析]:
<分析内容>

[空间逻辑评分]: <0-20分>
[空间逻辑分析]:
<分析内容>

[能力设定评分]: <0-20分>
[能力设定分析]:
<分析内容>

[世界观评分]: <0-20分>
[世界观分析]:
<分析内容>

[逻辑问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个逻辑问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">
""" 