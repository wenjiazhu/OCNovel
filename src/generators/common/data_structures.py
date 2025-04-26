from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class ChapterOutline:
    """章节大纲数据结构"""
    chapter_number: int
    title: str
    key_points: List[str]
    characters: List[str]
    settings: List[str]
    conflicts: List[str]

@dataclass
class NovelOutline:
    """小说大纲数据结构"""
    title: str
    chapters: List[ChapterOutline]

@dataclass
class Character:
    """角色数据结构"""
    name: str
    role: str  # 主角、配角、反派等
    personality: Dict[str, float]  # 性格特征权重
    goals: List[str]
    relationships: Dict[str, str]
    development_stage: str  # 当前发展阶段
    alignment: str = "中立"  # 阵营：正派、反派、中立等，默认为中立
    realm: str = "凡人"      # 境界，例如：凡人、炼气、筑基、金丹等，默认为凡人
    level: int = 1          # 等级，默认为1
    cultivation_method: str = "无" # 功法，默认为无
    magic_treasure: List[str] = field(default_factory=list) # 法宝列表，默认为空列
    temperament: str = "平和"    # 性情，默认为平和
    ability: List[str] = field(default_factory=list)      # 能力列表，默认为空列
    stamina: int = 100        # 体力值，默认为100
    sect: str = "无门无派"      # 门派，默认为无门无派
    position: str = "普通弟子"    # 职务，默认为普通弟子
    emotions_history: List[str] = field(default_factory=list)  # 情绪历史记录
    states_history: List[str] = field(default_factory=list)    # 状态历史记录
    descriptions_history: List[str] = field(default_factory=list)  # 描述历史记录 