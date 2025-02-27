import pytest
from app.core.world_builder import WorldBuilder
from app.core.plot_engine import PlotEngine
from app.core.character_graph import CharacterGraph
from app.core.plot_validator import PlotValidator
from app.core.style_transfer import StyleTransfer

def test_world_builder():
    builder = WorldBuilder()
    world_setting = builder.generate_world_setting("修真")
    
    assert "power_system" in world_setting
    assert "factions" in world_setting
    assert "geography" in world_setting
    assert len(world_setting["power_system"]) > 0

def test_plot_engine():
    engine = PlotEngine()
    story_line = engine.create_story_line(
        name="主线",
        main_character="张三",
        supporting_characters=["李四", "王五"],
        conflict_value=0.8
    )
    
    assert story_line.name == "主线"
    assert story_line.main_character == "张三"
    assert len(story_line.plot_points) > 0
    assert story_line.conflict_value == 0.8

def test_character_graph():
    graph = CharacterGraph()
    char1 = graph.create_character(
        name="张三",
        age=20,
        gender="男",
        faction="正派",
        power_level="凡境·第1重"
    )
    
    char2 = graph.create_character(
        name="李四",
        age=25,
        gender="男",
        faction="反派",
        power_level="凡境·第2重"
    )
    
    graph.establish_relationship(char1.id, char2.id, "敌对", 0.2)
    
    assert char1.name == "张三"
    assert char2.name == "李四"
    assert char1.id in graph.characters
    assert char2.id in graph.characters
    assert char2.id in char1.relationships

def test_plot_validator():
    engine = PlotEngine()
    graph = CharacterGraph()
    builder = WorldBuilder()
    validator = PlotValidator()
    
    # 创建测试数据
    story_line = engine.create_story_line(
        name="测试线",
        main_character="测试角色",
        supporting_characters=[],
        conflict_value=0.7
    )
    
    char = graph.create_character(
        name="测试角色",
        age=20,
        gender="男",
        faction="正派",
        power_level="凡境·第1重"
    )
    
    world_setting = builder.generate_world_setting("测试")
    
    # 执行验证
    validation_results = validator.validate_plot(
        {story_line.id: story_line},
        {char.id: char},
        world_setting
    )
    
    assert isinstance(validation_results, dict)
    assert "logic_consistency" in validation_results
    assert "character_consistency" in validation_results

def test_style_transfer():
    transfer = StyleTransfer()
    
    test_text = "他走进房间，看到了一本书。"
    
    # 测试风格分析
    style_scores = transfer.analyze_style(test_text)
    assert isinstance(style_scores, dict)
    assert len(style_scores) > 0
    
    # 测试风格建议
    suggestions = transfer.suggest_style_improvements(test_text)
    assert isinstance(suggestions, list)
    
    # 测试风格迁移
    try:
        converted_text = transfer.transfer_style(test_text, "epic")
        assert isinstance(converted_text, str)
        assert len(converted_text) > 0
    except Exception as e:
        # 如果没有设置API密钥，这里会失败
        assert "API key" in str(e) 