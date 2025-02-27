from typing import Dict, List, Optional
import networkx as nx
from pydantic import BaseModel
from ..config import settings

class PowerSystem(BaseModel):
    level: int
    stage: int
    name: str
    description: str
    requirements: List[str]
    limitations: List[str]

class Faction(BaseModel):
    name: str
    type: str  # 庙堂/江湖/异族
    core_demands: List[str]
    hidden_motives: List[str]
    power_level: float
    territories: List[str]
    relationships: Dict[str, float]  # 与其他势力的关系值

class GeographicLocation(BaseModel):
    name: str
    element: str  # 五行属性
    landmarks: List[Dict[str, str]]
    resources: List[str]
    defense_level: int
    transport_nodes: List[str]

class WorldBuilder:
    def __init__(self):
        self.power_system = {}
        self.factions = {}
        self.locations = {}
        self.relationship_graph = nx.Graph()
        
    def generate_power_system(self) -> Dict[str, PowerSystem]:
        """生成九阶三段力量体系"""
        power_levels = []
        stages = ["凡境", "玄境", "天境"]
        
        for stage in range(settings.POWER_SYSTEM_STAGES):
            for level in range(settings.POWER_SYSTEM_LEVELS // 3):
                power_name = f"{stages[stage]}·第{level + 1}重"
                power_system = PowerSystem(
                    level=level + 1 + stage * 3,
                    stage=stage + 1,
                    name=power_name,
                    description=f"{stages[stage]}境界第{level + 1}重修为",
                    requirements=[f"需要{level}年修炼"],
                    limitations=[f"每重突破概率降低{level * 10}%"]
                )
                self.power_system[power_name] = power_system
                
        return self.power_system
    
    def create_faction_matrix(self) -> Dict[str, Faction]:
        """创建势力矩阵"""
        faction_types = ["庙堂", "江湖", "异族"]
        
        for type_ in faction_types:
            faction = Faction(
                name=f"{type_}主势力",
                type=type_,
                core_demands=[f"{type_}核心诉求"],
                hidden_motives=[f"{type_}隐藏动机"],
                power_level=0.8,
                territories=[f"{type_}领地"],
                relationships={}
            )
            self.factions[faction.name] = faction
            self.relationship_graph.add_node(faction.name)
        
        # 建立势力关系
        for f1 in self.factions.values():
            for f2 in self.factions.values():
                if f1.name != f2.name:
                    relationship_value = 0.5  # 默认中立
                    self.relationship_graph.add_edge(f1.name, f2.name, weight=relationship_value)
                    f1.relationships[f2.name] = relationship_value
                    
        return self.factions
    
    def build_geographic_system(self) -> Dict[str, GeographicLocation]:
        """构建五行地理体系"""
        elements = ["金", "木", "水", "火", "土"]
        
        for element in elements:
            location = GeographicLocation(
                name=f"{element}之境",
                element=element,
                landmarks=[{"name": f"{element}之殿", "defense": "9"}],
                resources=[f"{element}属性资源"],
                defense_level=9,
                transport_nodes=[f"{element}之门"]
            )
            self.locations[location.name] = location
            
        return self.locations
    
    def generate_world_setting(self, theme: str) -> Dict:
        """生成完整世界观设定"""
        return {
            "theme": theme,
            "power_system": self.generate_power_system(),
            "factions": self.create_faction_matrix(),
            "geography": self.build_geographic_system(),
            "relationships": nx.to_dict_of_dicts(self.relationship_graph)
        } 