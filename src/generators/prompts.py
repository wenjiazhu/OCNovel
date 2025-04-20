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
    extra_prompt: Optional[str] = None
) -> str:
    """生成用于创建小说大纲的提示词，应用知识库内容过滤"""
    extra_requirements = f"{chr(10)}[额外要求]{chr(10)}{extra_prompt}{chr(10)}" if extra_prompt else ""

    # 获取额外指导内容
    extra_guidance = config.novel_config.get("extra_guidance", {})
    writing_style = extra_guidance.get("writing_style", {})
    content_rules = extra_guidance.get("content_rules", {})
    chapter_structure = extra_guidance.get("chapter_structure", {})
    plot_corrections = extra_guidance.get("plot_corrections", {})

    # 格式化额外指导内容
    extra_guidance_text = f"""
[写作风格指导]
节奏控制：{writing_style.get('pacing', '')}
描写要求：{writing_style.get('description', '')}
对话设计：{writing_style.get('dialogue', '')}
动作描写：{writing_style.get('action', '')}

[内容规则]
必须包含：
{chr(10).join(['- ' + rule for rule in content_rules.get('must_include', [])])}

必须避免：
{chr(10).join(['- ' + rule for rule in content_rules.get('must_avoid', [])])}

[章节结构]
开篇方式：{chapter_structure.get('opening', '')}
发展过程：{chapter_structure.get('development', '')}
高潮设计：{chapter_structure.get('climax', '')}
结尾处理：{chapter_structure.get('ending', '')}

[剧情修正要求]
{chr(10).join([f"【{correction['title']}】{chr(10)}{correction['description']}" for correction in plot_corrections.values()])}
"""

    # 从知识库中获取参考文件内容
    reference_files = config.novel_config.get("knowledge_base_config", {}).get("reference_files", [])
    reference_content = ""
    raw_references = []  # 存储原始参考内容，用于过滤

    for file_path in reference_files:
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logging.warning(f"参考文件不存在: {file_path}")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                raw_references.append(f"[参考文件: {os.path.basename(file_path)}]\n{content[:1000]}...")
        except UnicodeDecodeError:
            # 尝试其他编码
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
                    raw_references.append(f"[参考文件: {os.path.basename(file_path)}]\n{content[:1000]}...")
            except Exception as e:
                logging.warning(f"读取参考文件 {file_path} 时出错（尝试GBK编码后）: {str(e)}")
        except Exception as e:
            logging.warning(f"读取参考文件 {file_path} 时出错: {str(e)}")

    # 应用知识库内容过滤
    if raw_references:
        chapter_info = {
            "novel_type": novel_type,
            "theme": theme,
            "current_chapters": f"{current_start_chapter_num}-{current_start_chapter_num + current_batch_size - 1}"
        }
        filter_prompt = get_knowledge_filter_prompt(raw_references, chapter_info)
        # 假设通过模型生成过滤后的内容（实际需调用模型）
        filtered_content = f"（已过滤知识库内容）\n{filter_prompt}"  # 实际替换为模型调用
        reference_content = filtered_content
    else:
        reference_content = f"{chr(10)}[知识库参考内容]{chr(10)}暂无参考内容，将仅基于设定生成大纲。{chr(10)}"

    prompt = f"""{existing_context}

你是一个专业的小说大纲生成助手。你的任务是生成符合JSON格式的小说大纲。你必须严格按照要求的格式输出，不能添加任何额外的文字或解释。

[小说设定]
类型: {novel_type}
主题: {theme}
风格: {style}

[世界观设定]
{config.novel_config.get("writing_guide", {}).get("world_building", {}).get("magic_system", "")}
{config.novel_config.get("writing_guide", {}).get("world_building", {}).get("social_system", "")}
{config.novel_config.get("writing_guide", {}).get("world_building", {}).get("background", "")}

[角色设定]
主角: {config.novel_config.get("writing_guide", {}).get("character_guide", {}).get("protagonist", {}).get("background", "")}
配角: {', '.join([role.get("role_type", "") for role in config.novel_config.get("writing_guide", {}).get("character_guide", {}).get("supporting_roles", [])])}
反派: {', '.join([role.get("role_type", "") for role in config.novel_config.get("writing_guide", {}).get("character_guide", {}).get("antagonists", [])])}

[知识库参考内容]
{reference_content}

[任务要求]
1. 生成从第 {current_start_chapter_num} 章开始的，共 {current_batch_size} 个章节的大纲。重要：必须生成本批次要求的全部大纲，不得省略或截断。
2. 确保情节连贯，与已有上下文自然衔接。推动主线发展，引入新的冲突和看点。{extra_requirements}
3. 每章设计一个小高潮(如反转/打脸/冲突解决/悬念揭晓等)，每3章设计一个大高潮(达成目标/境界突破/战胜强敌等)。
4. 模仿知识库中同类型小说的桥段/套路/剧情梗等进行剧情设计，注意保持单个事件(开始-发展-结尾)的完整性。
5. 基于人物设定塑造人物成长经历，剧情发展不得偏离主题和设定。
6. 重要：大纲的所有文本内容（如 title, key_points, characters, settings, conflicts）必须仅使用简体中文，不允许包含任何其他语言的文字，尤其是严禁出现俄文词语或字符。

[输出格式要求]
1. 你必须直接输出一个JSON数组，数组中包含 {current_batch_size} 个章节对象
2. 不要添加任何其他文字说明、注释或代码标记
3. 每个章节对象必须包含以下字段：
   - chapter_number (整数): 章节号，从 {current_start_chapter_num} 开始递增，到 {current_start_chapter_num + current_batch_size - 1} 为止
   - title (字符串): 章节标题
   - key_points (字符串数组): 关键剧情点列表，至少2个
   - characters (字符串数组): 涉及角色列表，至少1个
   - settings (字符串数组): 场景列表，至少1个
   - conflicts (字符串数组): 核心冲突列表，至少1个
4. 所有字符串必须使用双引号，不能使用单引号
5. 数组和对象的最后一个元素后不要加逗号
6. 确保生成的是有效的JSON格式，可以被 JSON.parse() 解析

示例格式：
[
  {{
    "chapter_number": {current_start_chapter_num},
    "title": "第一个高潮",
    "key_points": [
      "主角发现神秘法宝",
      "与反派首次交手",
      "觉醒特殊能力"
    ],
    "characters": [
      "陆沉",
      "神秘老者"
    ],
    "settings": [
      "荒古遗迹"
    ],
    "conflicts": [
      "争夺法宝"
    ]
  }},
  {{
    "chapter_number": {current_start_chapter_num + 1},
    "title": "逃亡之路",
    "key_points": [
      "被追杀",
      "寻找庇护",
      "结识盟友"
    ],
    "characters": [
      "陆沉",
      "神秘老者",
      "盟友"
    ],
    "settings": [
      "深山老林"
    ],
    "conflicts": [
      "躲避追杀"
    ]
  }}
]

请直接生成符合上述格式的JSON数组，不要添加任何其他内容。确保输出的是有效的JSON格式。"""
    return prompt


def get_chapter_prompt(
    outline: Dict, 
    references: Dict,
    extra_prompt: str = "",
    context_info: str = ""
) -> str:
    """生成用于创建章节内容的提示词，根据章节号选择模板并应用知识库内容过滤。"""
    # 获取基本信息
    novel_number = outline.get('chapter_number', 0)
    is_first_chapter = novel_number == 1
    chapter_title = outline.get('title', '未知')
    
    # 处理关键情节点 - 改为分行展示以增强可读性和重要性
    key_points_list = outline.get('key_points', [])
    key_points_display = chr(10).join([f"- {point}" for point in key_points_list])
    
    # 其他信息
    characters = ', '.join(outline.get('characters', []))
    settings = ', '.join(outline.get('settings', []))
    conflicts = ', '.join(outline.get('conflicts', []))
    
    # 获取额外指导内容
    extra_guidance = config.novel_config.get("extra_guidance", {})
    writing_style = extra_guidance.get("writing_style", {})
    content_rules = extra_guidance.get("content_rules", {})
    chapter_structure = extra_guidance.get("chapter_structure", {})

    # 从 config.json 中获取 novel_config 的内容
    novel_type = config.novel_config.get("type", "玄幻")
    theme = config.novel_config.get("theme", "逆袭")
    style = config.novel_config.get("style", "严肃")

    # 格式化额外指导内容
    extra_guidance_text = f"""
[写作风格指导]
节奏控制：{writing_style.get('pacing', '')}
描写要求：{writing_style.get('description', '')}
对话设计：{writing_style.get('dialogue', '')}
动作描写：{writing_style.get('action', '')}

[内容规则]
必须包含：
{chr(10).join(['- ' + rule for rule in content_rules.get('must_include', [])])}

必须避免：
{chr(10).join(['- ' + rule for rule in content_rules.get('must_avoid', [])])}

[章节结构]
开篇方式：{chapter_structure.get('opening', '')}
发展过程：{chapter_structure.get('development', '')}
高潮设计：{chapter_structure.get('climax', '')}
结尾处理：{chapter_structure.get('ending', '')}
"""
    
    # 添加系统角色设定
    system_prompt = """你具有极强的逆向思维，熟知起点中文网、番茄中文网、七猫小说网、晋江文学城的风格与爽文套路，经常提出打破他人认知的故事创意。你的思考过程应该是原始的、有机的和自然的，捕捉真实的人类思维流程，更像是一个意识流。"""
    
    # 处理知识库参考内容 - 应用知识库内容过滤
    reference_files = config.novel_config.get("knowledge_base_config", {}).get("reference_files", [])
    raw_references = []

    # 读取参考文件内容
    for file_path in reference_files:
        try:
            if not os.path.exists(file_path):
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                raw_references.append(f"[参考文件: {os.path.basename(file_path)}]\n{content[:1000]}...")
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='gbk') as f:
                    content = f.read()
                    raw_references.append(f"[参考文件: {os.path.basename(file_path)}]\n{content[:1000]}...")
            except Exception as e:
                logging.warning(f"读取参考文件 {file_path} 时出错（尝试GBK编码后）: {str(e)}")
        except Exception as e:
            logging.warning(f"读取参考文件 {file_path} 时出错: {str(e)}")

    # 应用知识库内容过滤
    filtered_reference_content = ""
    if raw_references:
        chapter_info = {
            "chapter_number": novel_number,
            "title": chapter_title,
            "key_points": key_points_list,
            "characters": outline.get('characters', []),
            "is_first_chapter": is_first_chapter
        }
        
        # 获取过滤提示词
        filter_prompt = get_knowledge_filter_prompt(raw_references, chapter_info)
        
        # 实际应用中需要调用模型生成过滤后的内容
        # filtered_content = content_model.generate(filter_prompt)
        # 临时使用，实际使用时替换为模型调用结果
        filtered_reference_content = f"[过滤后的知识库参考内容]\n{filter_prompt}"
    else:
        filtered_reference_content = "\n[知识库参考内容]\n暂无参考内容，将仅基于设定生成章节。\n"
    
    # 获取下一章大纲信息（如果存在）
    next_chapter_info = ""
    try:
        # 假设可以通过以下方式获取下一章大纲
        # 实际实现中需要从chapter_outlines中获取下一章信息
        next_chapter_num = novel_number + 1
        
        # 这里应该根据实际项目结构获取chapter_outlines
        # 可以从配置或其他地方获取
        # 以下是示例代码，实际使用时需要根据项目结构调整
        from src.generators.common.utils import load_json_file
        outline_file = os.path.join(config.output_config["output_dir"], "outline.json")
        outlines_data = load_json_file(outline_file, default_value=[])
        
        # 获取下一章大纲（如果存在）
        next_chapter_outline = None
        for ch in outlines_data:
            if isinstance(ch, dict) and ch.get('chapter_number') == next_chapter_num:
                next_chapter_outline = ch
                break

        if next_chapter_outline:
            next_chapter_title = next_chapter_outline.get('title', f'第{next_chapter_num}章')
            next_chapter_key_points = chr(10).join([f"- {point}" for point in next_chapter_outline.get('key_points', [])])
            next_chapter_characters = ', '.join(next_chapter_outline.get('characters', []))
            next_chapter_settings = ', '.join(next_chapter_outline.get('settings', []))
            next_chapter_conflicts = ', '.join(next_chapter_outline.get('conflicts', []))
            
            next_chapter_info = f"""
[下一章大纲]
章节号: {next_chapter_num}
标题: {next_chapter_title}
关键情节点: 
{next_chapter_key_points}
涉及角色: {next_chapter_characters}
场景设定: {next_chapter_settings}
核心冲突: {next_chapter_conflicts}
"""
        else:
            next_chapter_info = "\n[下一章信息]\n暂无下一章大纲信息。\n"
    except Exception as e:
        logging.warning(f"获取下一章大纲信息时出错: {str(e)}")
        next_chapter_info = "\n[下一章信息]\n获取下一章大纲信息时出错。\n"
    
    # 根据章节号选择提示词模板
    if is_first_chapter:
        # 第一章使用 first_chapter_draft_prompt
        base_prompt = f"""
{system_prompt}

即将创作：第 {novel_number} 章《{chapter_title}》
本章定位：开篇章节
核心作用：引入主角和世界观
悬念密度：中等
伏笔操作：埋设初始伏笔
认知颠覆：★☆☆☆☆

[小说设定]
类型: {novel_type}
主题: {theme}
风格: {style}

{extra_guidance_text}

【重要】本章必须包含的关键情节点：
{key_points_display}

可用元素：
- 核心人物：{characters}
- 关键场景：{settings}
- 核心冲突：{conflicts}

{next_chapter_info}

[知识库参考内容]
{filtered_reference_content}

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
步步为营的成长线（人物境界只能单向提升、从低到高）、伏笔与填坑（如"神秘法宝的隐藏作用"）、多视角冲突（如"门派内斗""跨界追杀"）。
简练白描文风、重复句式强化节奏（如"法宝祭出，金光一闪"）、画面感强的场景描写（如"竹海如刃，火焚天地"）、高中生都能看懂的语句。
"""
    else:
        # 后续章节使用标准提示词
        base_prompt = f"""
{system_prompt}

请根据以下章节大纲和参考信息，创作小说章节内容。

[章节大纲]
章节号: {novel_number}
标题: {chapter_title}

[小说设定]
类型: {novel_type}
主题: {theme}
风格: {style}

{extra_guidance_text}

【重要】本章必须包含的关键情节点：
{key_points_display}

涉及角色: {characters}
场景设定: {settings}
核心冲突: {conflicts}

{next_chapter_info}

[知识库参考内容]
{filtered_reference_content}

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
步步为营的成长线（人物境界只能单向提升、从低到高）、伏笔与填坑（如"神秘法宝的隐藏作用"）、多视角冲突（如"门派内斗""跨界追杀"）。
简练白描文风、重复句式强化节奏（如"法宝祭出，金光一闪"）、画面感强的场景描写（如"竹海如刃，火焚天地"）、高中生都能看懂的语句。
"""

    # 添加格式要求（两种模板都需要）
    base_prompt += f"""
[格式要求]
1. 仅返回章节正文文本；
2. 不使用分章节小标题；
3. 长短句交错，增强语言节奏感；
4. 不要使用markdown格式;
5. 仅输出简体中文和中文标点符号，不要使用*号、#号、空格等非常规文本字符；
6. 避免在章节结尾使用 '...才刚刚开始' 或类似的陈词滥调。
"""

    # 添加额外要求
    if extra_prompt:
        base_prompt += f"{chr(10)}{chr(10)}[额外要求]{chr(10)}{extra_prompt}"

    # 添加上下文信息
    if context_info:
        base_prompt += f"{chr(10)}{chr(10)}[上下文信息]{chr(10)}{context_info}"

    # 添加连贯性要求（非第一章才需要）
    if not is_first_chapter:
        base_prompt += f"""
[连贯性要求]
1. 请确保本章情节与上一章摘要中描述的情节有明确的连接
2. 章节开头应自然承接上一章的结尾，避免跳跃感
3. 章节结尾应为下一章大纲中的情节埋下伏笔，为下一章做自然过渡
4. 确保人物情感和行为的连续性，避免角色表现前后矛盾
5. 时间线和场景转换要清晰流畅
"""
    # 即使是第一章，也需要为下一章做铺垫
    else:
        base_prompt += f"""
[下一章铺垫]
1. 在章节结尾为下一章大纲中的情节埋下伏笔
2. 为下一章的场景和人物做自然过渡
3. 留下一定的悬念引导读者继续阅读
"""

    # 最终检查部分（两种模板都需要）
    base_prompt += f"""
[重要·最终检查]
1. 检查你的章节内容是否明确包含了所有关键情节点
2. 检查所有指定的角色是否都出现在了章节中
3. 检查你描述的场景是否与场景设定一致
4. 确保核心冲突被合理地展开和刻画
5. 确保章节结尾与下一章大纲的开头能够自然衔接
"""
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
{chr(10).join([f"   - {char['名称']}: {char['身份']} - {char['当前状态']}" for char in character_info.get('人物信息', [])])}

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