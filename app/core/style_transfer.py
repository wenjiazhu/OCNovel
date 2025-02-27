from typing import Dict, List, Optional
from pydantic import BaseModel
import numpy as np
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from ..config import settings

class StyleTemplate(BaseModel):
    """风格模板类"""
    id: str
    name: str
    description: str
    keywords: List[str]
    sentence_patterns: List[str]
    tone: str
    example_text: str

class StyleTransfer:
    def __init__(self):
        self.style_templates: Dict[str, StyleTemplate] = self._initialize_templates()
        self.llm = OpenAI(api_key=settings.OPENAI_API_KEY)
        
    def _initialize_templates(self) -> Dict[str, StyleTemplate]:
        """初始化风格模板"""
        templates = {
            "epic": StyleTemplate(
                id="style_001",
                name="史诗",
                description="宏大磅礴，气势恢宏的写作风格",
                keywords=["浩瀚", "壮阔", "恢宏", "震撼", "磅礴"],
                sentence_patterns=[
                    "在那{形容词}的{地点}，{主语}{动词}着...",
                    "{时间}，{主语}如同{比喻}般{动词}..."
                ],
                tone="庄重",
                example_text="浩瀚星空之下，古老的战鼓声震撼着每个人的灵魂..."
            ),
            "romantic": StyleTemplate(
                id="style_002",
                name="浪漫",
                description="细腻温情，富有诗意的写作风格",
                keywords=["温柔", "细腻", "柔美", "婉约", "深情"],
                sentence_patterns=[
                    "{主语}轻轻地{动词}，仿佛{比喻}...",
                    "在{形容词}的{地点}，{主语}感受着{名词}..."
                ],
                tone="温柔",
                example_text="月光如水般轻柔地流淌，她的目光中闪烁着星辰般的光芒..."
            ),
            "thriller": StyleTemplate(
                id="style_003",
                name="惊悚",
                description="紧张刺激，悬疑迭起的写作风格",
                keywords=["阴森", "诡异", "恐怖", "紧张", "黑暗"],
                sentence_patterns=[
                    "突然，{主语}{动词}，{状语}...",
                    "在{形容词}的{地点}，{主语}感觉到{形容词}的{名词}..."
                ],
                tone="紧张",
                example_text="黑暗中，一阵诡异的脚步声渐渐逼近，空气仿佛凝固了..."
            )
        }
        return templates
    
    def _create_style_prompt(self, style: StyleTemplate, text: str) -> str:
        """创建风格转换提示"""
        prompt = PromptTemplate(
            input_variables=["style_description", "keywords", "tone", "example", "text"],
            template="""
            请将以下文本转换为指定的写作风格：
            
            目标风格描述：{style_description}
            关键词：{keywords}
            语气：{tone}
            风格示例：{example}
            
            原文：
            {text}
            
            请保持原文的核心内容不变，但使用上述风格重写。
            """
        )
        
        return prompt.format(
            style_description=style.description,
            keywords=", ".join(style.keywords),
            tone=style.tone,
            example=style.example_text,
            text=text
        )
    
    def transfer_style(self, text: str, target_style_id: str) -> str:
        """执行风格迁移"""
        if target_style_id not in self.style_templates:
            raise ValueError(f"未找到目标风格模板：{target_style_id}")
        
        style = self.style_templates[target_style_id]
        prompt = self._create_style_prompt(style, text)
        
        chain = LLMChain(llm=self.llm, prompt=PromptTemplate.from_template(prompt))
        result = chain.run(text=text)
        
        return result
    
    def analyze_style(self, text: str) -> Dict[str, float]:
        """分析文本当前风格"""
        style_scores = {}
        
        for style_id, template in self.style_templates.items():
            score = 0
            # 关键词匹配度
            for keyword in template.keywords:
                if keyword in text:
                    score += 0.2
            
            # 句式匹配度
            for pattern in template.sentence_patterns:
                if any(p in text for p in pattern.split("{")):
                    score += 0.3
            
            # 语气匹配度
            if template.tone in text:
                score += 0.5
                
            style_scores[template.name] = min(1.0, score)
        
        return style_scores
    
    def suggest_style_improvements(self, text: str) -> List[Dict[str, str]]:
        """提供风格改进建议"""
        current_style = self.analyze_style(text)
        suggestions = []
        
        for style_name, score in current_style.items():
            if score < 0.5:
                template = next(t for t in self.style_templates.values() if t.name == style_name)
                suggestions.append({
                    "style": style_name,
                    "current_score": score,
                    "suggestion": f"建议增加以下关键词的使用：{', '.join(template.keywords[:3])}",
                    "example": template.example_text
                })
        
        return suggestions
    
    def batch_transfer_style(self, texts: List[str], target_style_id: str) -> List[str]:
        """批量处理风格迁移"""
        results = []
        for text in texts:
            try:
                converted_text = self.transfer_style(text, target_style_id)
                results.append(converted_text)
            except Exception as e:
                results.append(f"处理失败：{str(e)}")
        return results 