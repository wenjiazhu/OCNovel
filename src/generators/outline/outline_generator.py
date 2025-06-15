import os
import json
import logging
import time
from typing import List, Tuple, Optional
from ..common.data_structures import ChapterOutline
from ..common.utils import load_json_file, save_json_file, validate_directory
from ..prompts import get_outline_prompt, get_sync_info_prompt

class OutlineGenerator:
    def __init__(self, config, outline_model, knowledge_base):
        self.config = config
        self.outline_model = outline_model
        self.knowledge_base = knowledge_base
        self.output_dir = config.output_config["output_dir"]
        self.chapter_outlines = []
        
        # 同步信息相关
        self.sync_info_file = os.path.join(self.output_dir, "sync_info.json")
        self.sync_info = self._load_sync_info()
        
        # 验证并创建输出目录
        validate_directory(self.output_dir)
        # 加载现有大纲
        self._load_outline()

    def _merge_list_unique(self, target_list: list, source_list: list):
        """将 source_list 中的唯一元素添加到 target_list 中"""
        existing_elements = set(target_list)
        for item in source_list:
            if item not in existing_elements:
                target_list.append(item)
                existing_elements.add(item) # Add to set for efficiency
        
    def _load_outline(self):
        """加载大纲文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        outline_data = load_json_file(outline_file, default_value=[])
        
        if outline_data:
            # 处理可能的旧格式（包含元数据）和新格式（仅含章节列表）
            chapters_list = outline_data.get("chapters", outline_data) if isinstance(outline_data, dict) else outline_data
            if isinstance(chapters_list, list):
                # 增加对 ChapterOutline 字段的健壮性检查
                valid_chapters = []
                for idx, chapter_data in enumerate(chapters_list):
                    if isinstance(chapter_data, dict):
                        try:
                            # 尝试创建 ChapterOutline，捕获可能的 TypeError
                            valid_chapters.append(ChapterOutline(**chapter_data))
                        except TypeError as e:
                            logging.warning(f"加载大纲时，第 {idx+1} 个章节数据字段不匹配或类型错误: {e} - 数据: {chapter_data} - 已跳过")
                        except Exception as e:
                            logging.warning(f"加载大纲时，第 {idx+1} 个章节数据出现未知错误: {e} - 数据: {chapter_data} - 已跳过")
                    else:
                        logging.warning(f"加载大纲时，发现非字典类型的章节数据: {chapter_data} - 已跳过")
                self.chapter_outlines = valid_chapters
                logging.info(f"从文件加载了 {len(self.chapter_outlines)} 章有效大纲")
            else:
                logging.error("大纲文件格式无法识别，应为列表或包含 'chapters' 键的字典。")
                self.chapter_outlines = []
        else:
            logging.info("未找到大纲文件或文件为空。")
            self.chapter_outlines = []

    def _save_outline(self) -> bool:
        """保存大纲到文件"""
        outline_file = os.path.join(self.output_dir, "outline.json")
        try:
            # 修改：只收集有效的 ChapterOutline 对象
            outline_data = []
            for outline in self.chapter_outlines:
                # 增加检查，明确跳过 None 值，避免警告
                if outline is None:
                    continue
                
                if isinstance(outline, ChapterOutline):
                    # 将 ChapterOutline 对象转换为字典
                    outline_dict = {
                        "chapter_number": outline.chapter_number,
                        "title": outline.title,
                        "key_points": outline.key_points,
                        "characters": outline.characters,
                        "settings": outline.settings,
                        "conflicts": outline.conflicts
                    }
                    outline_data.append(outline_dict)
                else: # 如果不是 None 但也不是 ChapterOutline，才发出警告
                    logging.warning(f"尝试保存非 ChapterOutline 对象: {type(outline)} - {outline}")

            if not outline_data:
                logging.warning("没有有效的大纲数据可以保存。")
                # 根据需要决定是否保存空文件或返回False
                # return save_json_file(outline_file, []) # 保存空列表
                return False # 或者认为没有数据则保存失败

            return save_json_file(outline_file, outline_data)
        except Exception as e:
            logging.error(f"保存大纲文件时出错: {str(e)}", exc_info=True) # 添加 exc_info
            return False

    def generate_outline(self, novel_type: str, theme: str, style: str, 
                        mode: str = 'replace', replace_range: Tuple[int, int] = None, 
                        extra_prompt: Optional[str] = None) -> bool:
        """生成指定范围的章节大纲"""
        try:
            if mode != 'replace' or not replace_range:
                logging.error(f"不支持的生成模式 '{mode}' 或缺少章节范围 'replace_range'")
                return False

            start_chapter, end_chapter = replace_range
            if start_chapter < 1 or end_chapter < start_chapter:
                logging.error(f"无效的章节范围: start={start_chapter}, end={end_chapter}")
                return False

            total_chapters_to_generate = end_chapter - start_chapter + 1
            # 确保大纲列表至少有 end_chapter 的长度，如果不够则填充 None 或空 ChapterOutline
            # 这对于替换逻辑很重要
            if len(self.chapter_outlines) < end_chapter:
                self.chapter_outlines.extend([None] * (end_chapter - len(self.chapter_outlines)))
                logging.info(f"扩展大纲列表以容纳目标章节 {end_chapter}")

            batch_size = 100 # 修改为100章一个批次
            successful_outlines_in_run = [] # 存储本次运行成功生成的

            num_batches = (total_chapters_to_generate + batch_size - 1) // batch_size
            all_batches_successful = True # 跟踪所有批次是否都成功
            for batch_idx in range(num_batches):
                batch_start_num = start_chapter + (batch_idx * batch_size)
                # 确保批次结束不超过总的结束章节
                batch_end_num = min(batch_start_num + batch_size - 1, end_chapter)
                
                batch_success = self._generate_batch(batch_start_num, batch_end_num,
                                                    novel_type, theme, style, extra_prompt, successful_outlines_in_run)
                
                if batch_success:
                    logging.info(f"批次 {batch_idx + 1} (章节 {batch_start_num}-{batch_end_num}) 生成成功，正在保存当前大纲...")
                    if not self._save_outline():
                         logging.error(f"在批次 {batch_idx + 1} 后保存大纲失败。")
                         # 即使保存失败，也可能决定继续生成下一批次，或者停止
                         # all_batches_successful = False # 标记失败
                         # break # 如果希望保存失败时停止，则取消注释此行
                else:
                    logging.error(f"批次 {batch_idx + 1} (章节 {batch_start_num}-{batch_end_num}) 生成失败，终止大纲生成。")
                    # 保存部分成功的结果
                    self._save_outline() # 保留之前的保存逻辑，以防万一
                    all_batches_successful = False
                    break # 生成失败则停止

            logging.info(f"所有批次的大纲生成尝试完成，本次运行共生成 {len(successful_outlines_in_run)} 章")
            # 不再需要在此处调用 _save_outline()，因为每次成功后都已保存
            # return self._save_outline()
            return all_batches_successful # 返回整体是否成功

        except Exception as e:
            logging.error(f"生成大纲主流程发生未预期错误：{str(e)}", exc_info=True) # 添加 exc_info
            return False

    def _generate_batch(self, batch_start_num: int, batch_end_num: int, 
                       novel_type: str, theme: str, style: str,
                       extra_prompt: Optional[str], 
                       successful_outlines_in_run: List[ChapterOutline]) -> bool:
        """生成一个批次的大纲"""
        current_batch_size = batch_end_num - batch_start_num + 1
        logging.info(f"开始生成第 {batch_start_num} 到 {batch_end_num} 章的大纲（共 {current_batch_size} 章）")

        # 获取当前批次的上下文
        existing_context = self._get_context_for_batch(batch_start_num)
        
        # 获取前文大纲用于一致性检查
        previous_outlines = [o for o in self.chapter_outlines[:batch_start_num-1] if isinstance(o, ChapterOutline)]
        
        # 生成提示词
        prompt = get_outline_prompt(
            novel_type=novel_type,
            theme=theme,
            style=style,
            current_start_chapter_num=batch_start_num,
            current_batch_size=current_batch_size,
            existing_context=existing_context,
            extra_prompt=extra_prompt
        )

        max_retries = self.config.generation_config.get("max_retries", 3)
        retry_delay = self.config.generation_config.get("retry_delay", 20)
        batch_size = self.config.generation_config.get("batch_size", 5)  # 默认每批5章

        # 如果批次太大，尝试分批处理
        if current_batch_size > batch_size:
            logging.info(f"批次大小 ({current_batch_size}) 超过限制 ({batch_size})，将分批处理")
            success = True
            for sub_batch_start in range(batch_start_num, batch_end_num + 1, batch_size):
                sub_batch_end = min(sub_batch_start + batch_size - 1, batch_end_num)
                if not self._generate_batch(sub_batch_start, sub_batch_end, novel_type, theme, style, extra_prompt, successful_outlines_in_run):
                    success = False
                    break
            return success

        for attempt in range(max_retries):
            try:
                logging.info(f"尝试 {attempt + 1}/{max_retries} 生成大纲")
                
                # 调用模型生成内容
                response = self.outline_model.generate(prompt)
                if not response:
                    raise Exception("模型返回为空")

                # 解析响应
                outline_data = self._parse_model_response(response)
                if not outline_data:
                    raise Exception("解析模型响应失败")

                # 验证并处理大纲数据
                new_outlines_batch = []
                valid_count = 0
                
                for i, chapter_data in enumerate(outline_data):
                    expected_chapter_num = batch_start_num + i
                    try:
                        new_outline = ChapterOutline(
                            chapter_number=expected_chapter_num,
                            title=chapter_data.get('title', f'第{expected_chapter_num}章'),
                            key_points=chapter_data.get('key_points', []),
                            characters=chapter_data.get('characters', []),
                            settings=chapter_data.get('settings', []),
                            conflicts=chapter_data.get('conflicts', [])
                        )
                        
                        # 检查一致性
                        if self._check_outline_consistency(new_outline, previous_outlines):
                            new_outlines_batch.append(new_outline)
                            valid_count += 1
                            previous_outlines.append(new_outline)
                        else:
                            logging.warning(f"第 {expected_chapter_num} 章大纲未通过一致性检查")
                            new_outlines_batch.append(None)
                            
                    except Exception as e:
                        logging.error(f"处理章节 {expected_chapter_num} 大纲时出错: {str(e)}")
                        new_outlines_batch.append(None)
                
                if valid_count == current_batch_size:
                    # 更新大纲列表
                    start_index = batch_start_num - 1
                    end_index = batch_end_num
                    self.chapter_outlines[start_index:end_index] = new_outlines_batch
                    
                    # 更新同步信息
                    self._update_sync_info(batch_start_num, batch_end_num)
                    
                    # 保存成功生成的大纲
                    successful_outlines_in_run.extend([o for o in new_outlines_batch if isinstance(o, ChapterOutline)])
                    return True
                else:
                    logging.warning(f"批次生成的大纲中只有 {valid_count}/{current_batch_size} 个通过验证")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                    
            except Exception as e:
                logging.error(f"生成批次大纲时出错: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    # 保存当前进度
                    self._save_outline()
                    return False
        
        return False

    def _parse_model_response(self, response: str):
        """解析模型返回的 JSON 响应，兼容 markdown 包裹和多余前后缀"""
        import json
        import re
        try:
            # 去除 markdown 代码块包裹
            response = response.strip()
            if response.startswith('```'):
                response = re.sub(r'^```[a-zA-Z]*', '', response)
                response = response.strip('`\n')
            # 查找第一个 [ 和最后一个 ]
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start == -1 or json_end == 0:
                # 尝试查找 { ... }
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
            else:
                json_str = response
            try:
                return json.loads(json_str)
            except Exception as e:
                logging.error(f"_parse_model_response: JSON 解析失败: {e}\n原始内容: {json_str[:500]}...")
                return None
        except Exception as e:
            logging.error(f"_parse_model_response: 处理响应时出错: {e}")
            return None

    def _load_sync_info(self) -> dict:
        """加载同步信息文件"""
        try:
            if os.path.exists(self.sync_info_file):
                with open(self.sync_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {
                "世界观": {
                    "世界背景": [],
                    "阵营势力": [],
                    "重要规则": [],
                    "关键场所": []
                },
                "人物设定": {
                    "人物信息": [],
                    "人物关系": []
                },
                "剧情发展": {
                    "主线梗概": "",
                    "重要事件": [],
                    "悬念伏笔": [],
                    "已解决冲突": [],
                    "进行中冲突": []
                },
                "前情提要": [],
                "当前章节": 0,
                "最后更新时间": ""
            }
        except Exception as e:
            logging.error(f"加载同步信息文件时出错: {str(e)}", exc_info=True)
            return self._get_default_sync_info()

    def _save_sync_info(self) -> bool:
        """保存同步信息到文件"""
        try:
            with open(self.sync_info_file, 'w', encoding='utf-8') as f:
                json.dump(self.sync_info, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"保存同步信息文件时出错: {str(e)}", exc_info=True)
            return False

    def _update_sync_info(self, batch_start: int, batch_end: int) -> bool:
        """更新同步信息"""
        try:
            # 获取本批次的章节内容
            batch_outlines = []
            for chapter_num in range(batch_start, batch_end + 1):
                if chapter_num - 1 < len(self.chapter_outlines):
                    outline = self.chapter_outlines[chapter_num - 1]
                    if outline:
                        batch_outlines.append(outline)

            if not batch_outlines:
                logging.warning("没有找到需要更新的章节大纲")
                return False

            # 构建章节内容文本
            chapter_texts = []
            for outline in batch_outlines:
                chapter_text = f"第{outline.chapter_number}章 {outline.title}\n"
                chapter_text += f"关键情节：{', '.join(outline.key_points)}\n"
                chapter_text += f"涉及角色：{', '.join(outline.characters)}\n"
                chapter_text += f"场景：{', '.join(outline.settings)}\n"
                chapter_text += f"冲突：{', '.join(outline.conflicts)}"
                chapter_texts.append(chapter_text)

            # 生成更新提示词
            prompt = get_sync_info_prompt(
                "\n\n".join(chapter_texts),
                json.dumps(self.sync_info, ensure_ascii=False),
                batch_end
            )

            # 调用模型更新同步信息
            new_sync_info = self.outline_model.generate(prompt)
            
            try:
                # 1. 首先尝试直接解析
                updated_sync_info = json.loads(new_sync_info)
            except json.JSONDecodeError:
                # 2. 如果直接解析失败，尝试提取 JSON 部分
                json_start = new_sync_info.find('{')
                json_end = new_sync_info.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_content = new_sync_info[json_start:json_end]
                    try:
                        updated_sync_info = json.loads(json_content)
                    except json.JSONDecodeError as e:
                        logging.error(f"提取的 JSON 内容解析失败: {str(e)}")
                        # 保存原始输出以供调试
                        debug_file = os.path.join(os.path.dirname(self.sync_info_file), "sync_info_raw.txt")
                        with open(debug_file, 'w', encoding='utf-8') as f:
                            f.write(new_sync_info)
                        logging.info(f"已保存原始输出到 {debug_file} 以供调试")
                        return False
                else:
                    logging.error("无法在生成的内容中找到 JSON 格式数据")
                    return False
            
            # 3. 验证 JSON 结构
            required_keys = ["世界观", "人物设定", "剧情发展", "前情提要", "当前章节", "最后更新时间"]
            if not all(key in updated_sync_info for key in required_keys):
                logging.warning(f"模型返回的同步信息缺少一些必要顶层键: {[k for k in required_keys if k not in updated_sync_info]}")
            
            # 4. 合并新的同步信息到现有信息中
            
            # 世界观
            if "世界观" in updated_sync_info and isinstance(updated_sync_info["世界观"], dict):
                world_view_updates = updated_sync_info["世界观"]
                self.sync_info.setdefault("世界观", {}) # Ensure "世界观" exists in self.sync_info
                for key in ["世界背景", "阵营势力", "重要规则"]: # Exclude "关键场所" as it's handled in _check_outline_consistency
                    if key in world_view_updates and isinstance(world_view_updates[key], list):
                        self._merge_list_unique(self.sync_info["世界观"].setdefault(key, []), world_view_updates[key])

            # 人物设定
            if "人物设定" in updated_sync_info and isinstance(updated_sync_info["人物设定"], dict):
                character_updates = updated_sync_info["人物设定"]
                self.sync_info.setdefault("人物设定", {}) # Ensure "人物设定" exists
                # "人物信息" 已在 _check_outline_consistency 统一处理，此处不重复添加
                if "人物关系" in character_updates and isinstance(character_updates["人物关系"], list):
                    self._merge_list_unique(self.sync_info["人物设定"].setdefault("人物关系", []), character_updates["人物关系"])

            # 剧情发展、前情提要 不在章节大纲生成阶段更新，仅在生成章节内容时按照当前进度进行更新
            # if "剧情发展" in updated_sync_info and isinstance(updated_sync_info["剧情发展"], dict):
            #     plot_updates = updated_sync_info["剧情发展"]
            #     self.sync_info.setdefault("剧情发展", {}) # Ensure "剧情发展" exists
            #     # 主线梗概：如果模型返回了新的非空梗概，则更新（覆盖）
            #     if plot_updates.get("主线梗概"): # Check if it's not None or empty string
            #         self.sync_info["剧情发展"]["主线梗概"] = plot_updates["主线梗概"]
            #     
            #     for key in ["重要事件", "悬念伏笔", "已解决冲突", "进行中冲突"]:
            #         if key in plot_updates and isinstance(plot_updates[key], list):
            #             self._merge_list_unique(self.sync_info["剧情发展"].setdefault(key, []), plot_updates[key])
            
            # # 前情提要
            # if "前情提要" in updated_sync_info and isinstance(updated_sync_info["前情提要"], list):
            #     self._merge_list_unique(self.sync_info.setdefault("前情提要", []), updated_sync_info["前情提要"])

            # 当前章节和最后更新时间由内部逻辑设定，不依赖模型输出
            self.sync_info["当前章节"] = batch_end
            self.sync_info["最后更新时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            return self._save_sync_info()
            
        except Exception as e:
            logging.error(f"更新同步信息时出错: {str(e)}", exc_info=True)
            return False

    def _get_context_for_batch(self, batch_start_num: int) -> str:
        """获取批次的上下文信息"""
        context_parts = []
        
        # 1. 获取更全面的前文信息
        context_chapters_count = 10  # 增加到10章以提供更多上下文
        start_index = max(0, batch_start_num - 1 - context_chapters_count)
        end_index = max(0, batch_start_num - 1)
        
        # 2. 添加故事发展脉络
        if self.sync_info:
            context_parts.append("[故事发展脉络]")
            # 主线发展
            if self.sync_info.get("剧情发展", {}).get("主线梗概"):
                context_parts.append(f"主线发展：{self.sync_info['剧情发展']['主线梗概']}")
            
            # 重要事件时间线
            if self.sync_info.get("剧情发展", {}).get("重要事件"):
                context_parts.append("重要事件时间线：")
                for event in self.sync_info["剧情发展"]["重要事件"][-10:]:  # 增加到最近10个重要事件
                    context_parts.append(f"- {event}")
            
            # 进行中的冲突
            if self.sync_info.get("剧情发展", {}).get("进行中冲突"):
                context_parts.append("\n当前主要冲突：")
                for conflict in self.sync_info["剧情发展"]["进行中冲突"]:
                    context_parts.append(f"- {conflict}")
        
        # 3. 获取前文大纲的详细信息（只显示最近5章的详细信息）
        previous_outlines = [o for o in self.chapter_outlines[start_index:end_index] if isinstance(o, ChapterOutline)]
        if previous_outlines:
            context_parts.append(f"\n[前 {len(previous_outlines)} 章详细大纲]")
            # 只显示最近5章的详细信息
            recent_outlines = previous_outlines[-5:]
            for prev_outline in recent_outlines:
                context_parts.append(f"\n第 {prev_outline.chapter_number} 章: {prev_outline.title}")
                context_parts.append(f"关键点: {', '.join(prev_outline.key_points)}")
                context_parts.append(f"涉及角色: {', '.join(prev_outline.characters)}")
                context_parts.append(f"场景: {', '.join(prev_outline.settings)}")
                context_parts.append(f"冲突: {', '.join(prev_outline.conflicts)}")
        
            # 对于更早的章节，只显示标题和关键点
            if len(previous_outlines) > 5:
                context_parts.append("\n[更早章节概要]")
                for prev_outline in previous_outlines[:-5]:
                    context_parts.append(f"第 {prev_outline.chapter_number} 章: {prev_outline.title}")
                    context_parts.append(f"关键点: {', '.join(prev_outline.key_points[:2])}...")
        
        # 4. 添加人物关系网络
        if self.sync_info.get("人物设定", {}).get("人物关系"):
            context_parts.append("\n[关键人物关系]")
            for relation in self.sync_info["人物设定"]["人物关系"][-10:]:  # 增加到最近10个关系
                context_parts.append(f"- {relation}")
        
        # 5. 添加世界观关键信息
        if self.sync_info.get("世界观"):
            context_parts.append("\n[世界观关键信息]")
            for key, value in self.sync_info["世界观"].items():
                if value:  # 只添加非空信息
                    context_parts.append(f"{key}: {', '.join(value)}")
        
        return "\n\n".join(context_parts)

    def _check_outline_consistency(self, new_outline: ChapterOutline, previous_outlines: List[ChapterOutline]) -> bool:
        """检查新生成的大纲与已有大纲的一致性，仅添加新角色和新场景"""
        try:
            # 1. 检查与前文的关联
            if previous_outlines:
                last_outline = previous_outlines[-1]
                # 检查是否有角色延续
                character_overlap = set(new_outline.characters) & set(last_outline.characters)
                if not character_overlap:
                    logging.warning(f"第 {new_outline.chapter_number} 章与前一章没有共同角色")
                    # 允许通过，不强制返回 False
                # 检查场景延续性
                setting_overlap = set(new_outline.settings) & set(last_outline.settings)
                if not setting_overlap:
                    logging.warning(f"第 {new_outline.chapter_number} 章与前一章没有共同场景")
                    # 允许通过，不强制返回 False

            # 2. 检查与同步信息的一致性，仅添加新内容
            if self.sync_info:
                # 检查角色是否在人物设定中
                all_characters = set()
                char_info_list = self.sync_info.get("人物设定", {}).get("人物信息", [])
                for char_info in char_info_list:
                    all_characters.add(char_info.get("名称", ""))
                
                # 只添加新角色
                unknown_characters = set(new_outline.characters) - all_characters
                if unknown_characters:
                    for char_name in unknown_characters:
                        if char_name:
                            # 自动添加新角色，保持其他角色信息不变
                            new_char = {"名称": char_name, "身份": "", "特点": "", "发展历程": "", "当前状态": ""}
                            char_info_list.append(new_char)
                            logging.info(f"自动添加新角色到人物设定: {char_name}")
                    # 更新 sync_info 中的人物信息列表
                    self.sync_info["人物设定"]["人物信息"] = char_info_list
                    self._save_sync_info()

                # 检查场景是否在世界观中
                all_settings = set()
                setting_list = self.sync_info.get("世界观", {}).get("关键场所", [])
                for setting in setting_list:
                    all_settings.add(setting)
                
                # 只添加新场景
                unknown_settings = set(new_outline.settings) - all_settings
                if unknown_settings:
                    for setting_name in unknown_settings:
                        if setting_name:
                            setting_list.append(setting_name)
                            logging.info(f"自动添加新场景到世界观关键场所: {setting_name}")
                    # 更新 sync_info 中的场景列表
                    self.sync_info["世界观"]["关键场所"] = setting_list
                    self._save_sync_info()

            return True
        except Exception as e:
            logging.error(f"检查大纲一致性时出错: {str(e)}")
            return False

    def _get_knowledge_references(self, batch_start: int, batch_end: int, 
                                previous_outlines: List[ChapterOutline]) -> str:
        """从知识库获取相关参考信息"""
        try:
            # 构建搜索查询
            search_queries = []
            
            # 1. 基于前文大纲的关键信息
            for outline in previous_outlines[-5:]:  # 只使用最近5章
                search_queries.extend(outline.key_points)
                search_queries.extend(outline.characters)
                search_queries.extend(outline.settings)
            
            # 2. 基于同步信息的关键信息
            if self.sync_info:
                # 添加世界观相关查询
                world_building = self.sync_info.get("世界观", {})
                for key, values in world_building.items():
                    if values:
                        search_queries.extend(values)
                
                # 添加人物相关查询
                character_info = self.sync_info.get("人物设定", {}).get("人物信息", [])
                for char in character_info:
                    if isinstance(char, dict):
                        search_queries.append(char.get("名称", ""))
            
            # 3. 基于当前章节范围的查询
            search_queries.append(f"第{batch_start}章到第{batch_end}章")
            
            # 去重并过滤空值
            search_queries = list(set(q for q in search_queries if q))
            
            # 从知识库搜索相关信息
            reference_texts = []
            for query in search_queries:
                results = self.knowledge_base.search(query, top_k=3)
                if results:
                    reference_texts.extend(results)
            
            # 格式化参考信息
            if reference_texts:
                return "\n".join([f"- {text}" for text in reference_texts])
            return ""
            
        except Exception as e:
            logging.error(f"获取知识库参考信息时出错: {str(e)}")
            return ""

if __name__ == "__main__":
    import argparse
    import re # For mock model parsing
    # 假设 Config, OutlineModel, KnowledgeBase 可以正确导入或用 Mock 替代
    try:
        # Change to absolute import assuming script is run from project root
        # or src is in PYTHONPATH
        from src.config.config import Config
        # Mock or import actual models
        class MockModel:
             def generate(self, prompt):
                 logging.info("[MockModel] Generating outline...")
                 # 返回一个符合格式的 JSON 字符串（示例）
                 example_chapter_num = 1 # 需要从 prompt 中解析
                 match = re.search(r'生成从第 (\d+) 章开始', prompt)
                 if match:
                     example_chapter_num = int(match.group(1))
                 
                 match_size = re.search(r'共 (\d+) 个章节的大纲', prompt)
                 batch_size = 1
                 if match_size:
                     batch_size = int(match_size.group(1))

                 outlines = []
                 for i in range(batch_size):
                     num = example_chapter_num + i
                     outlines.append({
                         "chapter_number": num,
                         "title": f"模拟章节 {num}",
                         "key_points": [f"模拟关键点 {num}-1", f"模拟关键点 {num}-2"],
                         "characters": [f"角色A", f"角色B-{num}"],
                         "settings": [f"模拟场景 {num}"],
                         "conflicts": [f"模拟冲突 {num}"]
                     })
                 return json.dumps(outlines, ensure_ascii=False, indent=2)

        class MockKnowledgeBase:
             def search(self, query, top_k=5):
                 logging.info(f"[MockKB] Searching for: {query}")
                 return [f"知识库参考1 for '{query[:20]}...'", f"知识库参考2 for '{query[:20]}...'"]
             def build_from_files(self, files):
                 logging.info(f"[MockKB] Building from files: {files}")
                 self.is_built = True


        OutlineModel = MockModel
        KnowledgeBase = MockKnowledgeBase
        # Setup logging for testing
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    except ImportError as e:
        logging.error(f"无法导入必要的模块: {e}")
        exit(1)


    parser = argparse.ArgumentParser(description='生成小说大纲')
    parser.add_argument('--config', type=str, default='config.json', help='配置文件路径') # Default for testing
    # Make other args optional for simpler testing if needed, or provide defaults
    parser.add_argument('--novel-type', type=str, default='修真玄幻', help='小说类型')
    parser.add_argument('--theme', type=str, default='天庭权谋', help='主题')
    parser.add_argument('--style', type=str, default='热血悬疑', help='写作风格')
    parser.add_argument('--start', type=int, default=1, help='起始章节')
    parser.add_argument('--end', type=int, default=5, help='结束章节') # Small range for test
    parser.add_argument('--extra-prompt', type=str, help='额外提示词')
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = Config(args.config)
        # Ensure necessary keys exist for testing
        if "output_config" not in config or "output_dir" not in config.output_config:
             config.output_config = {"output_dir": "data/output_test"}
             os.makedirs(config.output_config["output_dir"], exist_ok=True)
        if "generation_config" not in config:
            config.generation_config = {"max_retries": 1, "retry_delay": 1} # Faster test retries
    except FileNotFoundError:
         logging.error(f"配置文件 {args.config} 未找到。")
         exit(1)
    except Exception as e:
         logging.error(f"加载配置文件 {args.config} 出错: {e}")
         exit(1)

    
    # 初始化模型和知识库 (使用 Mock)
    outline_model = OutlineModel()
    knowledge_base = KnowledgeBase()
    knowledge_base.build_from_files([]) # Simulate build
    
    # 创建大纲生成器
    try:
        generator = OutlineGenerator(config, outline_model, knowledge_base)
    except Exception as e:
         logging.error(f"创建 OutlineGenerator 实例失败: {e}", exc_info=True)
         exit(1)

    
    # 生成大纲
    logging.info("开始生成大纲 (测试模式)...")
    success = generator.generate_outline(
        novel_type=args.novel_type,
        theme=args.theme,
        style=args.style,
        mode='replace',
        replace_range=(args.start, args.end),
        extra_prompt=args.extra_prompt
    )
    
    if success:
        print(f"\n大纲生成成功！(测试范围: {args.start}-{args.end})")
        print(f"大纲文件保存在: {os.path.join(generator.output_dir, 'outline.json')}")
        # Optionally print the generated outline
        # generated_outline = load_json_file(os.path.join(generator.output_dir, 'outline.json'))
        # print("生成的大纲内容:")
        # print(json.dumps(generated_outline, ensure_ascii=False, indent=2))
    else:
        print("\n大纲生成失败，请查看上面的日志了解详细信息。") 