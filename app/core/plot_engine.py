from typing import Dict, List, Optional
from pydantic import BaseModel
import numpy as np
from ..config import settings

class PlotPoint(BaseModel):
    """情节点类"""
    id: str
    type: str  # 启/承/转/合/破
    description: str
    tension: float
    characters: List[str]
    location: str
    timeline: int
    foreshadowing: List[str]
    callbacks: List[str]

class StoryLine(BaseModel):
    """故事线类"""
    id: str
    name: str
    plot_points: List[PlotPoint]
    main_character: str
    supporting_characters: List[str]
    conflict_value: float
    current_tension: float

class PlotEngine:
    def __init__(self):
        self.story_lines: Dict[str, StoryLine] = {}
        self.global_timeline: int = 0
        self.foreshadowing_pool: Dict[str, List[str]] = {}
        self.tension_history: List[float] = []
        
    def calculate_tension(self, plot_point: PlotPoint) -> float:
        """计算情节张力值"""
        base_tension = 0.5
        character_factor = len(plot_point.characters) * 0.1
        foreshadowing_factor = len(plot_point.foreshadowing) * 0.05
        callback_factor = len(plot_point.callbacks) * 0.08
        
        tension = base_tension + character_factor + foreshadowing_factor + callback_factor
        return min(max(tension, settings.TENSION_RANGE["min"]), settings.TENSION_RANGE["max"])
    
    def apply_snowflake_algorithm(self, story_line: StoryLine) -> List[PlotPoint]:
        """应用改良版雪花算法生成情节"""
        plot_points = []
        character_count = 1 + len(story_line.supporting_characters)
        motivation_strength = story_line.conflict_value
        environment_resistance = 1.0
        
        progress = character_count ** motivation_strength / environment_resistance
        num_points = int(progress * 10)  # 每条线默认10个关键节点
        
        plot_types = ["启", "承", "转", "合", "破"] * 2
        
        for i in range(num_points):
            plot_point = PlotPoint(
                id=f"{story_line.id}_point_{i}",
                type=plot_types[i % 5],
                description=f"{plot_types[i % 5]}阶段情节",
                tension=self.calculate_tension(PlotPoint(
                    id="temp",
                    type=plot_types[i % 5],
                    description="",
                    tension=0.0,
                    characters=[story_line.main_character],
                    location="默认地点",
                    timeline=self.global_timeline + i,
                    foreshadowing=[],
                    callbacks=[]
                )),
                characters=[story_line.main_character],
                location="默认地点",
                timeline=self.global_timeline + i,
                foreshadowing=[],
                callbacks=[]
            )
            plot_points.append(plot_point)
            
        return plot_points
    
    def create_story_line(self, name: str, main_character: str, 
                         supporting_characters: List[str], conflict_value: float) -> StoryLine:
        """创建新的故事线"""
        story_line = StoryLine(
            id=f"line_{len(self.story_lines)}",
            name=name,
            plot_points=[],
            main_character=main_character,
            supporting_characters=supporting_characters,
            conflict_value=conflict_value,
            current_tension=0.5
        )
        
        story_line.plot_points = self.apply_snowflake_algorithm(story_line)
        self.story_lines[story_line.id] = story_line
        return story_line
    
    def add_foreshadowing(self, plot_point: PlotPoint, foreshadowing: str):
        """添加伏笔"""
        self.foreshadowing_pool[foreshadowing] = []
        plot_point.foreshadowing.append(foreshadowing)
    
    def callback_foreshadowing(self, plot_point: PlotPoint, foreshadowing: str):
        """回收伏笔"""
        if foreshadowing in self.foreshadowing_pool:
            plot_point.callbacks.append(foreshadowing)
            self.foreshadowing_pool[foreshadowing].append(plot_point.id)
    
    def check_plot_consistency(self) -> Dict[str, List[str]]:
        """检查情节一致性"""
        issues = {
            "unresolved_foreshadowing": [],
            "tension_anomalies": [],
            "timeline_conflicts": []
        }
        
        # 检查未回收的伏笔
        for foreshadowing, callbacks in self.foreshadowing_pool.items():
            if not callbacks:
                issues["unresolved_foreshadowing"].append(foreshadowing)
        
        # 检查张力曲线异常
        for line in self.story_lines.values():
            tensions = [p.tension for p in line.plot_points]
            if np.std(tensions) > settings.EMOTION_STD_THRESHOLD:
                issues["tension_anomalies"].append(f"故事线 {line.name} 张力波动过大")
        
        # 检查时间线冲突
        all_points = []
        for line in self.story_lines.values():
            all_points.extend(line.plot_points)
        
        timeline_dict = {}
        for point in all_points:
            if point.timeline in timeline_dict:
                issues["timeline_conflicts"].append(
                    f"时间点 {point.timeline} 存在冲突: {timeline_dict[point.timeline]} 和 {point.id}"
                )
            timeline_dict[point.timeline] = point.id
        
        return issues 