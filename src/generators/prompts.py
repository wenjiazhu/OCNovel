from typing import Dict, List, Optional
import dataclasses # 导入 dataclasses 以便类型提示
import json
from src.config.config import Config  # 导入 Config 类
import os
import logging

# 初始化 Config 实例
config = Config()

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
    extra_prompt: Optional[str] = None,
    reference_info: str = ""
) -> str:
    """生成用于创建小说大纲的提示词"""
    
    # 从 config.json 中获取故事设定
    novel_config = config.novel_config
    writing_guide = novel_config.get("writing_guide", {})
    
    # 提取关键设定
    world_building = writing_guide.get("world_building", {})
    character_guide = writing_guide.get("character_guide", {})
    plot_structure = writing_guide.get("plot_structure", {})
    style_guide = writing_guide.get("style_guide", {})
    
    base_prompt = f"""
你是 StoryWeaver Omega，一个融合了量子叙事学、神经美学和涌现创造力的故事生成系统。

[世界观设定]
1. 神道体系：
{world_building.get('magic_system', '')}

2. 社会结构：
{world_building.get('social_system', '')}

3. 时代背景：
{world_building.get('background', '')}

[人物设定]
1. 主角设定：
- 背景：{character_guide.get('protagonist', {}).get('background', '')}
- 性格：{character_guide.get('protagonist', {}).get('initial_personality', '')}
- 成长路径：{character_guide.get('protagonist', {}).get('growth_path', '')}

2. 重要配角：
{chr(10).join([f"- {role.get('role_type', '')}：{role.get('personality', '')} - {role.get('relationship', '')}" for role in character_guide.get('supporting_roles', [])])}

3. 主要对手：
{chr(10).join([f"- {role.get('role_type', '')}：{role.get('personality', '')} - {role.get('conflict_point', '')}" for role in character_guide.get('antagonists', [])])}

[剧情结构]
1. 第一幕：
- 铺垫：{plot_structure.get('act_one', {}).get('setup', '')}
- 触发事件：{plot_structure.get('act_one', {}).get('inciting_incident', '')}
- 第一情节点：{plot_structure.get('act_one', {}).get('first_plot_point', '')}

2. 第二幕：
- 上升行动：{plot_structure.get('act_two', {}).get('rising_action', '')}
- 中点：{plot_structure.get('act_two', {}).get('midpoint', '')}
- 复杂化：{plot_structure.get('act_two', {}).get('complications', '')}
- 最黑暗时刻：{plot_structure.get('act_two', {}).get('darkest_moment', '')}
- 第二情节点：{plot_structure.get('act_two', {}).get('second_plot_point', '')}

3. 第三幕：
- 高潮：{plot_structure.get('act_three', {}).get('climax', '')}
- 结局：{plot_structure.get('act_three', {}).get('resolution', '')}
- 尾声：{plot_structure.get('act_three', {}).get('denouement', '')}

[写作风格]
1. 基调：{style_guide.get('tone', '')}
2. 节奏：{style_guide.get('pacing', '')}
3. 描写重点：
{chr(10).join([f"- {item}" for item in style_guide.get('description_focus', [])])}

[上下文信息]
{existing_context}

[叙事要求]
1. 情节连贯性：
   - 必须基于前文发展，保持故事逻辑的连贯性
   - 每个新章节都要承接前文伏笔，并为后续发展埋下伏笔
   - 确保人物行为符合其性格设定和发展轨迹

2. 结构完整性：
   - 每章必须包含起承转合四个部分
   - 每3章形成一个完整的故事单元
   - 每10章形成一个大的故事弧

3. 人物发展：
   - 确保主要人物的性格和动机保持一致性
   - 根据前文发展合理推进人物关系
   - 适时引入新角色，但需与现有角色产生关联

4. 世界观一致性：
   - 严格遵守已建立的世界规则
   - 新设定必须与现有设定兼容
   - 保持场景和环境的连贯性

[输出要求]
1. 直接输出JSON数组，包含 {current_batch_size} 个章节对象
2. 每个章节对象必须包含：
   - chapter_number: 章节号
   - title: 章节标题
   - key_points: 关键剧情点列表（至少3个）
   - characters: 涉及角色列表（至少2个）
   - settings: 场景列表（至少1个）
   - conflicts: 核心冲突列表（至少1个）

[质量检查]
1. 是否严格遵循世界观设定？
2. 人物行为是否符合其设定和发展轨迹？
3. 情节是否符合整体剧情结构？
4. 是否保持写作风格的一致性？
5. 是否包含足够的伏笔和悬念？
"""

    if extra_prompt:
        base_prompt += f"\n[额外要求]\n{extra_prompt}"

    if reference_info:
        base_prompt += f"\n[知识库参考信息]\n{reference_info}\n"

    return base_prompt


def get_chapter_prompt(
    outline: Dict, 
    references: Dict,
    extra_prompt: str = "",
    context_info: str = ""
) -> str:
    """生成用于创建章节内容的提示词"""
    
    # 获取基本信息
    novel_number = outline.get('chapter_number', 0)
    chapter_title = outline.get('title', '未知')
    is_first_chapter = novel_number == 1
    
    # 格式化关键情节点
    key_points_list = outline.get('key_points', [])
    key_points_display = chr(10).join([f"- {point}" for point in key_points_list])
    
    # 其他信息
    characters = ', '.join(outline.get('characters', []))
    settings = ', '.join(outline.get('settings', []))
    conflicts = ', '.join(outline.get('conflicts', []))
    
    base_prompt = f"""
你是 StoryWeaver Omega，一个融合了量子叙事学、神经美学和涌现创造力的故事生成系统。

[创作阶段]
1. 创世阶段
   - 捕获读者意图
   - 挖掘潜在情感需求
   - 识别未说出的故事渴望

2. 编织阶段
   - 多线程叙事构建
   - 动态情节发展
   - 涌现式创意生成

3. 结晶阶段
   - 情感达到顶点
   - 意外但必然的转折
   - 主题具象化

[章节信息]
章节号: {novel_number}
标题: {chapter_title}
情感基调: {outline.get('emotion', '未知')}
叙事风格: {outline.get('narrative_style', '未知')}
伏笔设置: {outline.get('foreshadowing', '未知')}
情节转折: {outline.get('plot_twist', '未知')}

[关键情节点]
{key_points_display}

[可用元素]
- 核心人物：{characters}
- 关键场景：{settings}
- 核心冲突：{conflicts}

[写作要求]
1. 场景设计
   - 对话场景：潜台词冲突，权力关系变化
   - 动作场景：环境交互细节，节奏控制
   - 心理场景：认知失调表现，隐喻系统
   - 环境场景：空间透视变化，非常规感官组合

2. 叙事技巧
   - 使用感官轰炸
   - 建立情感契约
   - 暗示深层主题
   - 交替紧张与释放
   - 编织多重冲突
   - 深化人物弧线

3. 情感表达
   - 扫描人类情感光谱
   - 识别普世共鸣点
   - 植入情感病毒（正向）
   - 创造cathartic moments

4. 创新要求
   - 颠覆读者预期
   - 保持内在逻辑
   - 制造"原来如此"时刻
   - 平衡熟悉与陌生

[输出要求]
1. 仅返回章节正文文本
2. 不使用分章节小标题
3. 长短句交错，增强语言节奏感
4. 仅使用简体中文和中文标点符号
5. 避免陈词滥调

[质量检查]
1. 是否触及人性的核心？
2. 是否创造了独特的阅读体验？
3. 是否有未探索的叙事维度？
4. 如何让这个故事成为读者的一部分？
"""

    # 添加额外要求
    if extra_prompt:
        base_prompt += f"\n[额外要求]\n{extra_prompt}"

    # 添加上下文信息
    if context_info:
        base_prompt += f"\n[上下文信息]\n{context_info}"

    return base_prompt


def get_summary_prompt(
    chapter_content: str
) -> str:
    """生成用于创建章节摘要的提示词。"""
    prompt = f"""请为以下章节内容生成一个简洁的摘要。

章节内容：
{chapter_content[:4000]}... (内容过长已截断)

[输出要求]
1.  **严格要求：只返回摘要正文本身。**
2.  不要包含任何前缀，例如 "本章摘要："、"章节摘要：" 、"内容摘要：" 或类似文字。
3.  在返回的内容不必包含章节号或章节标题。
4.  摘要应直接描述主要情节发展、关键人物行动和对剧情的影响。
5.  字数控制在 200 字以内。
6.  语言简洁，避免不必要的修饰。

请直接输出摘要文本。"""
    return prompt

# =============== 6. 前文摘要更新提示词 ===================
def get_sync_info_prompt(
    story_content: str,
    existing_sync_info: str = "",
    current_chapter: int = 0
) -> str:
    """生成用于创建/更新同步信息的提示词
    
    Args:
        story_content: 新增的故事内容
        existing_sync_info: 现有的同步信息（JSON字符串）
        current_chapter: 当前更新的章节号
    """
    return f"""根据故事进展更新相关信息，具体要求：
1. 合理细化使得相关信息逻辑完整，但不扩展不存在的设定
2. 精简表达，去除一切不必要的修饰，确保信息有效的同时使用最少tokens
3. 只保留对后续故事发展有参考价值的内容
4. 必须仅返回标准的JSON格式，不要添加任何前后缀、说明或标记

现有同步信息：
{existing_sync_info}

故事内容：
{story_content}

你必须严格按以下JSON格式输出，不要添加任何文字说明或其他标记：
{{
    "世界观": {{
        "世界背景": [],
        "阵营势力": [],
        "重要规则": [],
        "关键场所": []
    }},
    "人物设定": {{
        "人物信息": [
            {{
                "名称": "",
                "身份": "",
                "特点": "",
                "发展历程": "",
                "当前状态": ""
            }}
        ],
        "人物关系": []
    }},
    "剧情发展": {{
        "主线梗概": "",
        "重要事件": [],
        "悬念伏笔": [],
        "已解决冲突": [],
        "进行中冲突": []
    }},
    "前情提要": [],
    "当前章节": {current_chapter},
    "最后更新时间": ""
}}"""

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

[上下文分析阶段]：
1. 回顾前三章核心内容：
   - 第一章核心要素：[章节标题]→[核心冲突/理论]→[关键人物/概念]
   - 第二章发展路径：[已建立的人物关系]→[技术/情节进展]→[遗留伏笔]
   - 第三章转折点：[新出现的变量]→[世界观扩展]→[待解决问题]
2. 提取延续性要素：
   - 必继承要素：列出前3章中必须延续的3个核心设定
   - 可调整要素：识别2个允许适度变化的辅助设定

[当前章节摘要生成规则]：
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
    sync_info: Dict,
    previous_summary: str = "",
    character_info: str = "",
    previous_scene: str = ""
) -> str:
    """生成用于检查章节一致性的提示词"""
    # 从同步信息中提取相关内容
    world_info = sync_info.get("世界观", {})
    character_info = sync_info.get("人物设定", {})
    plot_info = sync_info.get("剧情发展", {})
    
    return f"""作为小说一致性检查专家，请基于以下信息评估章节内容的一致性，并提供详细报告：

[同步信息]
1. 世界观设定：
   - 世界背景：{', '.join(world_info.get('世界背景', []))}
   - 阵营势力：{', '.join(world_info.get('阵营势力', []))}
   - 重要规则：{', '.join(world_info.get('重要规则', []))}
   - 关键场所：{', '.join(world_info.get('关键场所', []))}

2. 人物设定：
{chr(10).join([f"   - {char.get('role_type', '未知角色')}: {char.get('personality', '')} - {char.get('relationship', '')}" for char in character_info.get('人物信息', [])])}

3. 剧情发展：
   - 主线梗概：{plot_info.get('主线梗概', '')}
   - 进行中冲突：{', '.join(plot_info.get('进行中冲突', []))}
   - 悬念伏笔：{', '.join(plot_info.get('悬念伏笔', []))}

[当前章节大纲]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}
场景设定：{', '.join(chapter_outline.get('settings', []))}
核心冲突：{', '.join(chapter_outline.get('conflicts', []))}

[上一章摘要]
{previous_summary if previous_summary else "（无上一章摘要）"}

[待检查章节内容]
{chapter_content}

===== 一致性检查标准 =====
请从以下八个维度进行评估，各占不同分值，总分100分：

1. 世界观一致性（15分）：
   - 是否符合已建立的世界设定和规则
   - 新增设定是否与现有世界观冲突
   - 场景描写是否符合世界背景

2. 人物一致性（15分）：
   - 人物行为是否符合其设定和当前状态
   - 人物关系发展是否合理
   - 新角色是否与已有角色体系协调

3. 剧情连贯性（15分）：
   - 与主线梗概的契合度
   - 与进行中冲突的呼应
   - 对已有伏笔的处理

4. 情节逻辑性（10分）：
   - 事件发展是否合理
   - 因果关系是否清晰
   - 时间线是否连贯

5. 冲突展现（10分）：
   - 是否合理展现核心冲突
   - 冲突发展是否符合逻辑
   - 冲突解决方式是否恰当

6. 设定延续性（10分）：
   - 对已有设定的运用
   - 新设定的合理性
   - 设定间的协调性

7. 细节准确性（15分）：
   - 场景描写的准确性
   - 专业知识的准确性
   - 前后细节的一致性

8. 节奏把控（10分）：
   - 情节节奏是否合适
   - 是否符合章节定位
   - 与整体节奏的协调性

===== 输出格式 =====
[总体评分]: <0-100分>

[世界观一致性评分]: <0-15分>
[世界观分析]:
<分析内容>

[人物一致性评分]: <0-15分>
[人物分析]:
<分析内容>

[剧情连贯性评分]: <0-15分>
[剧情分析]:
<分析内容>

[情节逻辑性评分]: <0-10分>
[情节分析]:
<分析内容>

[冲突展现评分]: <0-10分>
[冲突分析]:
<分析内容>

[设定延续性评分]: <0-10分>
[设定分析]:
<分析内容>

[细节准确性评分]: <0-15分>
[细节分析]:
<分析内容>

[节奏把控评分]: <0-10分>
[节奏分析]:
<分析内容>

[问题清单]:
1. <具体问题描述>
2. <具体问题描述>
...

[修改建议]:
1. <具体修改建议>
2. <具体修改建议>
...

[修改必要性]: <"需要修改"或"无需修改">

[优先级]: <"高"/"中"/"低">
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
    """生成用于知识库检索的提示词，过滤低相关性内容"""
    # 生成关键词组合逻辑
    keywords = []
    
    # 1. 优先使用用户指导中的术语
    if user_guidance:
        keywords.extend(user_guidance.split())
    
    # 2. 添加章节核心要素
    keywords.extend([f"章节{chapter_number}", chapter_title])
    keywords.extend(characters_involved)
    keywords.extend(key_items)
    keywords.extend([scene_location])
    
    # 3. 补充扩展概念（如伏笔、章节作用等）
    keywords.extend([chapter_role, chapter_purpose, foreshadowing])
    
    # 去重并过滤抽象词汇
    keywords = list(set([k for k in keywords if k and len(k) > 1]))
    
    # 生成检索词组合
    search_terms = []
    for i in range(0, len(keywords), 2):
        group = keywords[i:i+2]
        if group:
            search_terms.append(".".join(group))
    
    return "\n".join(search_terms[:5])  # 返回最多5组检索词


# =============== 12. 知识库内容过滤提示词 ===================
def get_knowledge_filter_prompt(
    retrieved_texts: List[str],
    chapter_info: Dict
) -> str:
    """生成用于过滤知识库内容的提示词，增强过滤逻辑"""
    return f"""
请根据当前章节需求过滤知识库内容，严格按以下规则执行：

[当前章节需求]
{json.dumps(chapter_info, ensure_ascii=False, indent=2)}

[待过滤内容]
{chr(10).join([f"--- 片段 {i+1} ---{chr(10)}{text[:200]}..." for i, text in enumerate(retrieved_texts)])}

===== 过滤规则 =====
1. **冲突检测**：
   - 删除与已有世界观/角色设定矛盾的内容（标记为 ▲CONFLICT）。
   - 删除重复度＞40%的内容（标记为 ▲DUPLICATE）。

2. **价值评估**：
   - 标记高价值内容（❗）：
     - 提供新角色关系或剧情转折可能性的内容。
     - 包含可扩展的细节（如场景描写、技术设定）。
   - 标记低价值内容（·）：
     - 泛泛而谈的描述或无具体情节的内容。

3. **分类输出**：
   - 按以下分类整理内容，并标注适用场景：
     - 情节燃料：推动主线或支线发展的内容。
     - 人物维度：深化角色形象或关系的内容。
     - 世界碎片：补充世界观细节的内容。

[输出格式]
[分类名称]→[适用场景]
❗/· [内容片段]（▲冲突提示）
...

示例：
[情节燃料]→可用于第{chapter_info.get('chapter_number', 'N')}章高潮
❗ "主角发现密室中的古老地图，暗示下个副本位置"（▲与第三章地图描述冲突）
· "村民谈论最近的异常天气"（可作背景铺垫）
"""

def get_logic_check_prompt(
    chapter_content: str,
    chapter_outline: Dict,
    sync_info: Optional[str] = None
) -> str:
    """生成用于检查章节逻辑严密性的提示词"""
    prompt = f"""请检查以下章节内容的逻辑严密性：

[章节大纲]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}
场景设定：{', '.join(chapter_outline.get('settings', []))}
核心冲突：{', '.join(chapter_outline.get('conflicts', []))}"""

    # 添加同步信息部分（如果提供）
    if sync_info:
        prompt += f"""

[同步信息]
{sync_info}"""

    prompt += f"""

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
    return prompt

def get_style_check_prompt(
    chapter_content: str,
    novel_config: Dict
) -> str:
    """生成用于检查章节写作风格的提示词"""
    writing_guide = novel_config.get("writing_guide", {})
    style_guide = writing_guide.get("style_guide", {})
    
    # 获取风格指南
    tone = style_guide.get("tone", "")
    pov = style_guide.get("pov", "")
    narrative_style = style_guide.get("narrative_style", "")
    language_style = style_guide.get("language_style", "")
    
    return f"""请检查以下章节内容的写作风格：

[风格指南]
语气基调：{tone}
叙述视角：{pov}
叙事风格：{narrative_style}
语言风格：{language_style}

[章节内容]
{chapter_content}

===== 风格检查维度 =====

1. 语气一致性
   - 是否保持指定的语气基调
   - 情感表达是否恰当
   - 是否存在语气突兀转变

2. 视角把控
   - 是否严格遵守视角限制
   - 视角切换是否自然
   - 是否出现视角混乱

3. 叙事手法
   - 是否符合指定的叙事风格
   - 叙事节奏是否合适
   - 场景描写是否生动

4. 语言特色
   - 是否符合指定的语言风格
   - 用词是否准确规范
   - 句式是否多样流畅

5. 细节处理
   - 环境描写是否细致
   - 人物刻画是否生动
   - 情节铺陈是否到位

===== 输出格式 =====
[总体评分]: <0-100分>

[语气一致性评分]: <0-20分>
[语气分析]:
<分析内容>

[视角把控评分]: <0-20分>
[视角分析]:
<分析内容>

[叙事手法评分]: <0-20分>
[叙事分析]:
<分析内容>

[语言特色评分]: <0-20分>
[语言分析]:
<分析内容>

[细节处理评分]: <0-20分>
[细节分析]:
<分析内容>

[风格问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个风格问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">
"""

def get_emotion_check_prompt(
    chapter_content: str,
    chapter_outline: Dict
) -> str:
    """生成用于检查章节情感表达的提示词"""
    return f"""请检查以下章节内容的情感表达：

[章节大纲]
章节号：{chapter_outline.get('chapter_number', '未知')}
标题：{chapter_outline.get('title', '未知')}
情感基调：{chapter_outline.get('emotion', '未知')}
关键剧情点：{', '.join(chapter_outline.get('key_points', []))}
涉及角色：{', '.join(chapter_outline.get('characters', []))}

[章节内容]
{chapter_content}

===== 情感检查维度 =====

1. 情感基调
   - 是否符合章节预设基调
   - 情感变化是否自然
   - 是否有突兀的情绪波动

2. 人物情感
   - 情感表达是否符合人物性格
   - 情感反应是否合理
   - 内心活动描写是否到位

3. 情感互动
   - 人物间情感交流是否自然
   - 情感冲突是否鲜明
   - 群体情绪是否传染

4. 场景情感
   - 环境氛围营造是否到位
   - 场景与情感是否呼应
   - 是否有画面感

5. 读者共鸣
   - 是否容易引起情感共鸣
   - 是否有感情真实性
   - 是否有情感升华

===== 输出格式 =====
[总体评分]: <0-100分>

[情感基调评分]: <0-20分>
[基调分析]:
<分析内容>

[人物情感评分]: <0-20分>
[人物情感分析]:
<分析内容>

[情感互动评分]: <0-20分>
[互动分析]:
<分析内容>

[场景情感评分]: <0-20分>
[场景分析]:
<分析内容>

[读者共鸣评分]: <0-20分>
[共鸣分析]:
<分析内容>

[情感问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个情感问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">
""" 