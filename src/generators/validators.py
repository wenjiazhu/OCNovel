class LogicValidator:
    def check_logic(
        self, 
        content: str, 
        outline: Dict,
        sync_info: Dict  # 新增参数
    ) -> Tuple[str, bool]:
        """检查章节内容的逻辑性"""
        prompt = f"""请检查以下章节内容的逻辑性，特别关注与同步信息的一致性：

[同步信息]
- 世界观: {sync_info.get('世界观', {}).get('世界背景', '')}
- 进行中冲突: {', '.join(sync_info.get('剧情发展', {}).get('进行中冲突', []))}
- 人物状态: {', '.join([f"{c['名称']}({c['当前状态']})" for c in sync_info.get('人物设定', {}).get('人物信息', [])])}

[章节大纲]
{json.dumps(outline, indent=2, ensure_ascii=False)}

[章节内容]
{content}

请从以下方面检查逻辑性：
1. 是否符合同步信息中的世界观设定
2. 是否合理处理进行中冲突
3. 人物行为是否符合其当前状态
4. 时间线和因果关系是否合理

返回格式：
[总体评价]: <评价>
[具体问题]: <问题列表>
[需要修改]: <是/否>
"""
        # ... 其余逻辑不变 ... 