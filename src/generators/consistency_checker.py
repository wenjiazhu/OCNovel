def ensure_chapter_consistency(
    self,
    chapter_content: str,
    chapter_outline: Dict,
    sync_info: Dict,  # 新增参数
    chapter_idx: int,
    characters: Optional[List[Dict]] = None
) -> str:
    """确保章节内容的一致性"""
    # 获取上一章摘要
    previous_summary = self._get_previous_summary(chapter_idx)
    
    # 构建验证提示词（使用更新后的get_consistency_check_prompt）
    prompt = get_consistency_check_prompt(
        chapter_content=chapter_content,
        chapter_outline=chapter_outline,
        sync_info=sync_info,  # 新增参数
        previous_summary=previous_summary
    )
    
    # 调用模型进行验证
    validation_result = self.model.generate(prompt)
    # ... 其余验证逻辑不变 ... 