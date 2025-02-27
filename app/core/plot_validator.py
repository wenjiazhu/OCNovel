from typing import Dict, List, Optional
from pydantic import BaseModel
import networkx as nx
from .plot_engine import PlotPoint, StoryLine
from .character_graph import Character
from ..config import settings

class ValidationRule(BaseModel):
    """验证规则类"""
    id: str
    name: str
    description: str
    severity: int  # 1-5，5最严重
    check_function: str  # 对应的检查函数名

class ValidationIssue(BaseModel):
    """验证问题类"""
    rule_id: str
    severity: int
    location: str  # 问题发生的位置（情节点ID等）
    description: str
    suggested_fix: Optional[str]

class PlotValidator:
    def __init__(self):
        self.rules: Dict[str, ValidationRule] = self._initialize_rules()
        self.validation_history: List[Dict[str, List[ValidationIssue]]] = []
        
    def _initialize_rules(self) -> Dict[str, ValidationRule]:
        """初始化验证规则"""
        rules = {
            "logic_consistency": ValidationRule(
                id="rule_001",
                name="逻辑一致性",
                description="检查情节逻辑链是否连贯",
                severity=5,
                check_function="check_logic_consistency"
            ),
            "character_consistency": ValidationRule(
                id="rule_002",
                name="角色一致性",
                description="检查角色行为是否符合设定",
                severity=4,
                check_function="check_character_consistency"
            ),
            "world_rules": ValidationRule(
                id="rule_003",
                name="世界规则",
                description="检查是否违反世界设定规则",
                severity=5,
                check_function="check_world_rules"
            ),
            "plot_pace": ValidationRule(
                id="rule_004",
                name="情节节奏",
                description="检查情节发展节奏是否合适",
                severity=3,
                check_function="check_plot_pace"
            ),
            "emotion_coherence": ValidationRule(
                id="rule_005",
                name="情感连贯性",
                description="检查情感发展是否自然",
                severity=4,
                check_function="check_emotion_coherence"
            )
        }
        return rules
    
    def check_logic_consistency(self, story_lines: Dict[str, StoryLine]) -> List[ValidationIssue]:
        """检查逻辑一致性"""
        issues = []
        
        for line_id, line in story_lines.items():
            # 构建情节因果图
            causal_graph = nx.DiGraph()
            
            for i, point in enumerate(line.plot_points):
                causal_graph.add_node(point.id)
                if i > 0:
                    causal_graph.add_edge(line.plot_points[i-1].id, point.id)
            
            # 检查因果链深度
            for node in causal_graph.nodes():
                paths = list(nx.single_source_shortest_path_length(causal_graph, node))
                if max(paths.values()) < settings.LOGIC_CHECK_DEPTH:
                    issues.append(
                        ValidationIssue(
                            rule_id="rule_001",
                            severity=5,
                            location=node,
                            description=f"情节点 {node} 的因果链深度不足",
                            suggested_fix="增加相关联的情节点或加强因果关联"
                        )
                    )
        
        return issues
    
    def check_character_consistency(self, 
                                  story_lines: Dict[str, StoryLine],
                                  characters: Dict[str, Character]) -> List[ValidationIssue]:
        """检查角色一致性"""
        issues = []
        
        for line_id, line in story_lines.items():
            for point in line.plot_points:
                for char_id in point.characters:
                    if char_id in characters:
                        char = characters[char_id]
                        
                        # 检查行为是否符合性格特征
                        if "勇气" in char.traits:
                            courage = char.traits["勇气"].value
                            if "战斗" in point.description.lower() and courage < 0.4:
                                issues.append(
                                    ValidationIssue(
                                        rule_id="rule_002",
                                        severity=4,
                                        location=point.id,
                                        description=f"角色 {char.name} 的勇气值过低，不适合参与战斗场景",
                                        suggested_fix="调整场景或增加角色勇气值的成长铺垫"
                                    )
                                )
        
        return issues
    
    def check_world_rules(self, 
                         story_lines: Dict[str, StoryLine],
                         world_settings: Dict) -> List[ValidationIssue]:
        """检查世界规则"""
        issues = []
        
        power_system = world_settings.get("power_system", {})
        geography = world_settings.get("geography", {})
        
        for line_id, line in story_lines.items():
            for point in line.plot_points:
                # 检查力量体系规则
                if "战斗" in point.description.lower():
                    for char_id in point.characters:
                        char_power = point.characters[char_id].get("power_level", "")
                        if char_power not in power_system:
                            issues.append(
                                ValidationIssue(
                                    rule_id="rule_003",
                                    severity=5,
                                    location=point.id,
                                    description=f"角色 {char_id} 的力量等级 {char_power} 不在世界设定范围内",
                                    suggested_fix="调整角色力量等级或修改世界设定"
                                )
                            )
                
                # 检查地理规则
                if point.location not in geography:
                    issues.append(
                        ValidationIssue(
                            rule_id="rule_003",
                            severity=5,
                            location=point.id,
                            description=f"场景位置 {point.location} 不在世界地理设定中",
                            suggested_fix="添加新的地理位置或修改场景位置"
                        )
                    )
        
        return issues
    
    def check_plot_pace(self, story_lines: Dict[str, StoryLine]) -> List[ValidationIssue]:
        """检查情节节奏"""
        issues = []
        
        for line_id, line in story_lines.items():
            tension_values = [point.tension for point in line.plot_points]
            
            # 检查张力波动
            for i in range(1, len(tension_values)):
                change = abs(tension_values[i] - tension_values[i-1])
                if change > 0.3:  # 张力变化过大
                    issues.append(
                        ValidationIssue(
                            rule_id="rule_004",
                            severity=3,
                            location=line.plot_points[i].id,
                            description=f"情节张力变化过大 ({change:.2f})",
                            suggested_fix="添加过渡情节或调整张力值"
                        )
                    )
        
        return issues
    
    def check_emotion_coherence(self, 
                              story_lines: Dict[str, StoryLine],
                              characters: Dict[str, Character]) -> List[ValidationIssue]:
        """检查情感连贯性"""
        issues = []
        
        for line_id, line in story_lines.items():
            for i, point in enumerate(line.plot_points):
                if i > 0:
                    prev_point = line.plot_points[i-1]
                    
                    # 检查角色情感变化
                    for char_id in point.characters:
                        if char_id in prev_point.characters and char_id in characters:
                            char = characters[char_id]
                            
                            # 检查情感变化是否过大
                            if (char_id in prev_point.relationships and 
                                char_id in point.relationships):
                                emotion_change = abs(
                                    point.relationships[char_id] - 
                                    prev_point.relationships[char_id]
                                )
                                if emotion_change > 0.5:  # 情感变化过大
                                    issues.append(
                                        ValidationIssue(
                                            rule_id="rule_005",
                                            severity=4,
                                            location=point.id,
                                            description=f"角色 {char.name} 的情感变化过大 ({emotion_change:.2f})",
                                            suggested_fix="添加情感铺垫或调整情感变化幅度"
                                        )
                                    )
        
        return issues
    
    def validate_plot(self, 
                     story_lines: Dict[str, StoryLine],
                     characters: Dict[str, Character],
                     world_settings: Dict) -> Dict[str, List[ValidationIssue]]:
        """执行完整的情节验证"""
        validation_results = {}
        
        # 执行所有验证规则
        validation_results["logic_consistency"] = self.check_logic_consistency(story_lines)
        validation_results["character_consistency"] = self.check_character_consistency(
            story_lines, characters
        )
        validation_results["world_rules"] = self.check_world_rules(story_lines, world_settings)
        validation_results["plot_pace"] = self.check_plot_pace(story_lines)
        validation_results["emotion_coherence"] = self.check_emotion_coherence(
            story_lines, characters
        )
        
        # 记录验证历史
        self.validation_history.append(validation_results)
        
        return validation_results
    
    def get_validation_summary(self, validation_results: Dict[str, List[ValidationIssue]]) -> Dict:
        """生成验证结果摘要"""
        summary = {
            "total_issues": 0,
            "severity_distribution": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "critical_issues": [],
            "suggested_fixes": []
        }
        
        for rule_issues in validation_results.values():
            summary["total_issues"] += len(rule_issues)
            
            for issue in rule_issues:
                summary["severity_distribution"][issue.severity] += 1
                
                if issue.severity >= 4:
                    summary["critical_issues"].append({
                        "location": issue.location,
                        "description": issue.description
                    })
                
                if issue.suggested_fix:
                    summary["suggested_fixes"].append({
                        "location": issue.location,
                        "fix": issue.suggested_fix
                    })
        
        return summary 