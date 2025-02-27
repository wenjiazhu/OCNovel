from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import uvicorn

from app.core.world_builder import WorldBuilder
from app.core.plot_engine import PlotEngine
from app.core.character_graph import CharacterGraph
from app.core.plot_validator import PlotValidator
from app.core.style_transfer import StyleTransfer

app = FastAPI(
    title="NovelForge",
    description="AI网文生成系统",
    version="1.0.0"
)

class WorldSettingRequest(BaseModel):
    theme: str
    
class StoryLineRequest(BaseModel):
    name: str
    main_character: str
    supporting_characters: List[str]
    conflict_value: float

class CharacterRequest(BaseModel):
    name: str
    age: int
    gender: str
    faction: str
    power_level: str

class StyleTransferRequest(BaseModel):
    text: str
    target_style_id: str

# 初始化核心组件
world_builder = WorldBuilder()
plot_engine = PlotEngine()
character_graph = CharacterGraph()
plot_validator = PlotValidator()
style_transfer = StyleTransfer()

@app.post("/world-setting")
async def generate_world_setting(request: WorldSettingRequest):
    """生成世界观设定"""
    try:
        world_setting = world_builder.generate_world_setting(request.theme)
        return {"status": "success", "data": world_setting}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/story-line")
async def create_story_line(request: StoryLineRequest):
    """创建故事线"""
    try:
        story_line = plot_engine.create_story_line(
            name=request.name,
            main_character=request.main_character,
            supporting_characters=request.supporting_characters,
            conflict_value=request.conflict_value
        )
        return {"status": "success", "data": story_line}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/character")
async def create_character(request: CharacterRequest):
    """创建角色"""
    try:
        character = character_graph.create_character(
            name=request.name,
            age=request.age,
            gender=request.gender,
            faction=request.faction,
            power_level=request.power_level
        )
        return {"status": "success", "data": character}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/validate-plot")
async def validate_plot():
    """验证情节"""
    try:
        validation_results = plot_validator.validate_plot(
            plot_engine.story_lines,
            character_graph.characters,
            world_builder.generate_world_setting("")
        )
        summary = plot_validator.get_validation_summary(validation_results)
        return {
            "status": "success",
            "data": {
                "validation_results": validation_results,
                "summary": summary
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transfer-style")
async def transfer_style(request: StyleTransferRequest):
    """转换写作风格"""
    try:
        result = style_transfer.transfer_style(
            text=request.text,
            target_style_id=request.target_style_id
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze-style")
async def analyze_style(text: str):
    """分析文本风格"""
    try:
        style_analysis = style_transfer.analyze_style(text)
        suggestions = style_transfer.suggest_style_improvements(text)
        return {
            "status": "success",
            "data": {
                "style_analysis": style_analysis,
                "suggestions": suggestions
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/character-network")
async def analyze_character_network():
    """分析角色关系网络"""
    try:
        network_analysis = character_graph.analyze_character_network()
        return {"status": "success", "data": network_analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
