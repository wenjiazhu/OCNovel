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

5. 避免重复与独创性：
   - **绝不能重复现有章节（特别是 `[上下文信息]` 中提供的内容）的标题、关键情节、核心冲突或主要事件。**
   - **每一章都必须有独特的、推进剧情的新内容，即使主题相似，也要有新的角度和发展。**
   - 充分利用 `[上下文信息]` 来理解故事的当前状态，并在此基础上进行创新和扩展，而非简单的变体或重复。

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
    
    # 格式化关键情节点
    key_points_list = outline.get('key_points', [])
    key_points_display = chr(10).join([f"- {point}" for point in key_points_list])
    
    # 其他信息
    characters = ', '.join(outline.get('characters', []))
    settings = ', '.join(outline.get('settings', []))
    conflicts = ', '.join(outline.get('conflicts', []))
    
    base_prompt = f"""你是专业小说创作AI，请基于以下信息生成章节内容：

[章节信息]
章节号: {novel_number}
标题: {chapter_title}
关键情节点:
{key_points_display}

[核心元素]
人物: {characters}
场景: {settings}
冲突: {conflicts}

[写作要求]
1. 场景设计：对话场景注重潜台词冲突，动作场景注重环境交互，心理场景注重认知失调
2. 叙事技巧：使用感官描写，建立情感契约，暗示深层主题，交替紧张与释放
3. 情感表达：识别普世共鸣点，创造情感升华时刻
4. 创新要求：颠覆读者预期但保持内在逻辑，制造"原来如此"时刻

[输出要求]
1. 仅返回章节正文文本，不使用分章节小标题
2. 长短句交错，增强语言节奏感
3. 仅使用简体中文和中文标点符号
4. 避免陈词滥调

[质量检查]
1. 是否触及人性的核心？
2. 是否创造了独特的阅读体验？
3. 是否有未探索的叙事维度？"""

    # 添加额外要求
    if extra_prompt:
        base_prompt += f"\n[额外要求]\n{extra_prompt}"

    # 添加上下文信息（限制长度）
    if context_info:
        # 限制上下文信息长度，避免过长
        max_context_length = 2000
        if len(context_info) > max_context_length:
            context_info = context_info[-max_context_length:] + "...(前文已省略)"
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
    
    # 安全处理列表字段，确保能处理字典和字符串混合的情况
    def safe_join_list(items, default=""):
        """安全地连接列表，处理字典和字符串混合的情况"""
        if not items:
            return default
        result = []
        for item in items:
            if isinstance(item, dict):
                # 如果是字典，提取名称和简介
                name = item.get("名称", "")
                desc = item.get("简介", item.get("说明", ""))
                if name and desc:
                    result.append(f"{name}: {desc}")
                elif name:
                    result.append(name)
                elif desc:
                    result.append(desc)
            elif isinstance(item, str):
                result.append(item)
            else:
                result.append(str(item))
        return ", ".join(result) if result else default
    
    return f"""请检查章节内容的一致性：

[同步信息]
世界观：{safe_join_list(world_info.get('世界背景', []))} | {safe_join_list(world_info.get('阵营势力', []))} | {safe_join_list(world_info.get('重要规则', []))}
人物：{chr(10).join([f"- {char.get('role_type', '未知')}: {char.get('personality', '')}" for char in character_info.get('人物信息', [])])}
剧情：{plot_info.get('主线梗概', '')} | 冲突：{safe_join_list(plot_info.get('进行中冲突', []))} | 伏笔：{safe_join_list(plot_info.get('悬念伏笔', []))}

[章节大纲]
{chapter_outline.get('chapter_number', '未知')}章《{chapter_outline.get('title', '未知')}》
关键点：{', '.join(chapter_outline.get('key_points', []))}
角色：{', '.join(chapter_outline.get('characters', []))}
场景：{', '.join(chapter_outline.get('settings', []))}
冲突：{', '.join(chapter_outline.get('conflicts', []))}

[上一章摘要]
{previous_summary if previous_summary else "（无）"}

[章节内容]
{chapter_content}

===== 一致性检查 =====
请从以下维度评估（总分100分）：
1. 世界观一致性（25分）：是否符合已建立的世界设定和规则
2. 人物一致性（25分）：人物行为是否符合其设定和当前状态
3. 剧情连贯性（25分）：与主线梗概的契合度，对已有伏笔的处理
4. 逻辑合理性（25分）：事件发展是否合理，因果关系是否清晰

===== 输出格式 =====
[总体评分]: <0-100分>

[世界观一致性]: <0-25分>
[人物一致性]: <0-25分>
[剧情连贯性]: <0-25分>
[逻辑合理性]: <0-25分>

[问题清单]:
1. <具体问题>
2. <具体问题>
...

[修改建议]:
1. <具体建议>
2. <具体建议>
...

[修改必要性]: <"需要修改"或"无需修改">"""

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
    prompt = f"""请检查章节内容的逻辑严密性：

[章节大纲]
{chapter_outline.get('chapter_number', '未知')}章《{chapter_outline.get('title', '未知')}》
关键点：{', '.join(chapter_outline.get('key_points', []))}
角色：{', '.join(chapter_outline.get('characters', []))}
场景：{', '.join(chapter_outline.get('settings', []))}
冲突：{', '.join(chapter_outline.get('conflicts', []))}"""

    # 添加同步信息部分（如果提供）
    if sync_info:
        prompt += f"""

[同步信息]
{sync_info}"""

    prompt += f"""

[章节内容]
{chapter_content}

===== 逻辑检查 =====
请从以下维度评估（总分100分）：
1. 因果关系（25分）：事件发生是否有合理的因果关联，人物行为是否有合理的动机
2. 时间线（25分）：事件发生顺序是否合理，是否存在时间线矛盾
3. 空间逻辑（25分）：场景转换是否合理，人物位置关系是否合理
4. 世界观（25分）：是否符合已建立的世界规则，是否存在世界观矛盾

===== 输出格式 =====
[总体评分]: <0-100分>

[因果关系]: <0-25分>
[时间线]: <0-25分>
[空间逻辑]: <0-25分>
[世界观]: <0-25分>

[逻辑问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个逻辑问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">"""
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
    
    return f"""请检查章节内容的写作风格：

[风格指南]
语气：{tone} | 视角：{pov} | 叙事：{narrative_style} | 语言：{language_style}

[章节内容]
{chapter_content}

===== 风格检查 =====
请从以下维度评估（总分100分）：
1. 语气一致性（25分）：是否保持指定的语气基调，情感表达是否恰当
2. 视角把控（25分）：是否严格遵守视角限制，视角切换是否自然
3. 叙事手法（25分）：是否符合指定的叙事风格，叙事节奏是否合适
4. 语言特色（25分）：是否符合指定的语言风格，用词是否准确规范

===== 输出格式 =====
[总体评分]: <0-100分>

[语气一致性]: <0-25分>
[视角把控]: <0-25分>
[叙事手法]: <0-25分>
[语言特色]: <0-25分>

[风格问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个风格问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">"""

def get_emotion_check_prompt(
    chapter_content: str,
    chapter_outline: Dict
) -> str:
    """生成用于检查章节情感表达的提示词"""
    return f"""请检查章节内容的情感表达：

[章节大纲]
{chapter_outline.get('chapter_number', '未知')}章《{chapter_outline.get('title', '未知')}》
情感基调：{chapter_outline.get('emotion', '未知')}
关键点：{', '.join(chapter_outline.get('key_points', []))}
角色：{', '.join(chapter_outline.get('characters', []))}

[章节内容]
{chapter_content}

===== 情感检查 =====
请从以下维度评估（总分100分）：
1. 情感基调（25分）：是否符合章节预设基调，情感变化是否自然
2. 人物情感（25分）：情感表达是否符合人物性格，情感反应是否合理
3. 情感互动（25分）：人物间情感交流是否自然，情感冲突是否鲜明
4. 读者共鸣（25分）：是否容易引起情感共鸣，是否有感情真实性

===== 输出格式 =====
[总体评分]: <0-100分>

[情感基调]: <0-25分>
[人物情感]: <0-25分>
[情感互动]: <0-25分>
[读者共鸣]: <0-25分>

[情感问题列表]:
1. <问题描述>
2. <问题描述>
...

[修改建议]:
<针对每个情感问题的具体修改建议>

[修改必要性]: <"需要修改"或"无需修改">""" 