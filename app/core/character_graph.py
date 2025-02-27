from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
import networkx as nx
import numpy as np
from ..config import settings

class CharacterTrait(BaseModel):
    """角色特征类"""
    name: str
    value: float  # 0-1之间的值
    description: str
    evolution_rate: float  # 特征随时间演变速率

class Character(BaseModel):
    """角色类"""
    id: str
    name: str
    age: int
    gender: str
    faction: str
    power_level: str
    traits: Dict[str, CharacterTrait]
    relationships: Dict[str, float]  # 与其他角色的关系值
    story_involvement: List[str]  # 参与的故事线ID
    background: str
    goals: List[str]
    fears: List[str]

class CharacterGraph:
    def __init__(self):
        self.characters: Dict[str, Character] = {}
        self.relationship_graph = nx.Graph()
        self.trait_evolution_history: Dict[str, List[Tuple[int, Dict[str, float]]]] = {}
        
    def create_character(self, name: str, age: int, gender: str, 
                        faction: str, power_level: str) -> Character:
        """创建新角色"""
        character_id = f"char_{len(self.characters)}"
        
        # 生成基础性格特征
        base_traits = {
            "勇气": CharacterTrait(
                name="勇气",
                value=np.random.uniform(0.3, 0.9),
                description="面对危险的勇气值",
                evolution_rate=0.01
            ),
            "智慧": CharacterTrait(
                name="智慧",
                value=np.random.uniform(0.4, 0.8),
                description="解决问题的智慧值",
                evolution_rate=0.005
            ),
            "忠诚": CharacterTrait(
                name="忠诚",
                value=np.random.uniform(0.5, 1.0),
                description="对信仰/组织的忠诚度",
                evolution_rate=0.008
            ),
            "野心": CharacterTrait(
                name="野心",
                value=np.random.uniform(0.2, 0.7),
                description="追求目标的野心值",
                evolution_rate=0.015
            )
        }
        
        character = Character(
            id=character_id,
            name=name,
            age=age,
            gender=gender,
            faction=faction,
            power_level=power_level,
            traits=base_traits,
            relationships={},
            story_involvement=[],
            background=f"{name}的背景故事",
            goals=[f"{name}的目标"],
            fears=[f"{name}的恐惧"]
        )
        
        self.characters[character_id] = character
        self.relationship_graph.add_node(character_id)
        self.trait_evolution_history[character_id] = []
        
        return character
    
    def establish_relationship(self, char1_id: str, char2_id: str, 
                             relationship_type: str, initial_value: float):
        """建立角色关系"""
        if char1_id in self.characters and char2_id in self.characters:
            self.relationship_graph.add_edge(char1_id, char2_id, 
                                          type=relationship_type, 
                                          weight=initial_value)
            
            self.characters[char1_id].relationships[char2_id] = initial_value
            self.characters[char2_id].relationships[char1_id] = initial_value
    
    def evolve_traits(self, character_id: str, timeline: int):
        """演化角色特征"""
        if character_id in self.characters:
            character = self.characters[character_id]
            current_traits = {}
            
            for trait_name, trait in character.traits.items():
                # 基于演化率计算新的特征值
                evolution = trait.evolution_rate * np.random.normal(0, 0.1)
                new_value = max(0, min(1, trait.value + evolution))
                
                character.traits[trait_name].value = new_value
                current_traits[trait_name] = new_value
            
            # 记录特征演化历史
            self.trait_evolution_history[character_id].append((timeline, current_traits))
    
    def update_relationship(self, char1_id: str, char2_id: str, 
                          event_impact: float, event_description: str):
        """更新角色关系"""
        if char1_id in self.characters and char2_id in self.characters:
            current_value = self.relationship_graph[char1_id][char2_id]["weight"]
            new_value = max(0, min(1, current_value + event_impact))
            
            self.relationship_graph[char1_id][char2_id]["weight"] = new_value
            self.characters[char1_id].relationships[char2_id] = new_value
            self.characters[char2_id].relationships[char1_id] = new_value
    
    def analyze_character_network(self) -> Dict:
        """分析角色关系网络"""
        analysis = {
            "central_characters": [],
            "isolated_characters": [],
            "relationship_clusters": [],
            "potential_conflicts": []
        }
        
        # 计算中心性
        centrality = nx.degree_centrality(self.relationship_graph)
        for char_id, score in sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:3]:
            analysis["central_characters"].append({
                "character": self.characters[char_id].name,
                "centrality_score": score
            })
        
        # 寻找孤立角色
        for char_id in self.characters:
            if self.relationship_graph.degree(char_id) == 0:
                analysis["isolated_characters"].append(self.characters[char_id].name)
        
        # 寻找角色群集
        communities = nx.community.greedy_modularity_communities(self.relationship_graph)
        for i, community in enumerate(communities):
            cluster = []
            for char_id in community:
                cluster.append(self.characters[char_id].name)
            analysis["relationship_clusters"].append({
                "cluster_id": i,
                "members": cluster
            })
        
        # 分析潜在冲突
        for char1_id in self.characters:
            for char2_id in self.characters:
                if char1_id != char2_id:
                    char1 = self.characters[char1_id]
                    char2 = self.characters[char2_id]
                    
                    # 检查阵营冲突
                    if (char1.faction != char2.faction and 
                        char1_id in char2.relationships and 
                        char2.relationships[char1_id] < 0.3):
                        analysis["potential_conflicts"].append({
                            "characters": [char1.name, char2.name],
                            "reason": "阵营对立",
                            "intensity": 1 - char2.relationships[char1_id]
                        })
        
        return analysis 