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

            batch_size = 10 # 减少批次大小，降低单次请求失败的影响，更容易调试
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
        existing_context = self._get_context_for_batch(batch_start_num) # 修改：不再传入 successful_outlines_in_run
        
        # 使用导入的 get_outline_prompt 生成提示词
        prompt = get_outline_prompt( # 直接调用导入的函数
            novel_type=novel_type,
            theme=theme,
            style=style,
            current_start_chapter_num=batch_start_num,
            current_batch_size=current_batch_size,
            existing_context=existing_context,
            extra_prompt=extra_prompt
        )
        logging.debug(f"为章节 {batch_start_num}-{batch_end_num} 生成的提示词:\n{prompt[:500]}...") # 记录部分提示词

        max_retries = self.config.generation_config.get("max_retries", 3)
        retry_delay = self.config.generation_config.get("retry_delay", 10)

        for attempt in range(max_retries):
            logging.info(f"章节 {batch_start_num}-{batch_end_num}，尝试 {attempt + 1}/{max_retries}")
            try:
                response = self.outline_model.generate(prompt)
                logging.debug(f"模型原始响应 (尝试 {attempt + 1}):\n{response}") # 添加日志记录
                
                # 尝试清理响应，移除可能的 ```json ... ``` 或前后缀文本
                json_start = response.find('[')
                json_end = response.rfind(']') + 1
                if json_start == -1 or json_end == 0:
                    json_start = response.find('{') # 有些模型可能会返回单个对象而非列表
                    json_end = response.rfind('}') + 1

                if json_start != -1 and json_end > json_start:
                    json_string = response[json_start:json_end]
                    logging.debug(f"提取到的 JSON 字符串:\n{json_string}")
                else:
                    json_string = response # 如果找不到 JSON 括号，尝试直接解析
                    logging.warning("未在响应中找到 '[' 或 '{'，将尝试直接解析完整响应。")

                try:
                    # 解析 JSON
                    outline_data = json.loads(json_string)
                except json.JSONDecodeError as e:
                    logging.error(f"解析模型响应失败 (尝试 {attempt + 1}): {e}\n处理后的字符串: {json_string[:500]}...")
                    # 如果失败，记录完整原始响应以便分析
                    error_log_path = os.path.join(self.output_dir, f"outline_error_response_{batch_start_num}-{batch_end_num}_attempt_{attempt+1}.txt")
                    with open(error_log_path, 'w', encoding='utf-8') as f_err:
                        f_err.write(response)
                    logging.info(f"已将失败的原始响应保存到: {error_log_path}")
                    # 根据错误决定是否继续重试
                    if attempt < max_retries - 1:
                         time.sleep(retry_delay * (attempt + 1)) # 增加等待时间
                         continue
                    else:
                         return False # 重试次数耗尽

                # 验证解析结果
                if not isinstance(outline_data, list):
                    # 兼容返回单个对象的情况
                    if isinstance(outline_data, dict) and current_batch_size == 1:
                         outline_data = [outline_data]
                    else:
                        logging.error(f"生成的大纲格式不正确，期望列表但得到 {type(outline_data)} (尝试 {attempt + 1})")
                        if attempt < max_retries - 1:
                             time.sleep(retry_delay)
                             continue
                        else:
                             return False

                if len(outline_data) != current_batch_size:
                     logging.error(f"生成的大纲数量 ({len(outline_data)}) 与要求 ({current_batch_size}) 不符 (尝试 {attempt + 1})")
                     if attempt < max_retries - 1:
                         time.sleep(retry_delay)
                         continue
                     else:
                         return False

                # 验证通过，处理大纲数据
                new_outlines_batch = []
                valid_count = 0
                for i, chapter_data in enumerate(outline_data):
                    expected_chapter_num = batch_start_num + i
                    # 验证单个章节数据的类型和必要字段
                    if not isinstance(chapter_data, dict):
                        logging.warning(f"批次内第 {i+1} 个章节数据不是字典: {chapter_data}")
                        new_outlines_batch.append(None) # 添加占位符
                        continue
                    
                    actual_chapter_num = chapter_data.get('chapter_number')
                    if actual_chapter_num != expected_chapter_num:
                         logging.warning(f"章节号不匹配：期望 {expected_chapter_num}，实际 {actual_chapter_num}。将使用期望值。")
                         # chapter_data['chapter_number'] = expected_chapter_num # 可以强制修正，但需谨慎

                    try:
                        new_outline = ChapterOutline(
                            chapter_number=expected_chapter_num, # 使用期望值
                            title=chapter_data.get('title', f'第{expected_chapter_num}章'),
                            key_points=chapter_data.get('key_points', []),
                            characters=chapter_data.get('characters', []),
                            settings=chapter_data.get('settings', []),
                            conflicts=chapter_data.get('conflicts', [])
                        )
                        new_outlines_batch.append(new_outline)
                        valid_count += 1
                    except Exception as e:
                         logging.error(f"根据章节数据创建 ChapterOutline 对象时出错 (章节 {expected_chapter_num}): {e} - 数据: {chapter_data}", exc_info=True)
                         new_outlines_batch.append(None) # 添加占位符


                logging.info(f"批次解析完成，成功转换 {valid_count}/{current_batch_size} 个章节大纲。")

                # 替换指定范围的章节 (使用索引)
                start_index = batch_start_num - 1
                end_index = batch_end_num # Python 切片不包含 end_index
                
                # 确保列表足够长
                if end_index > len(self.chapter_outlines):
                     self.chapter_outlines.extend([None] * (end_index - len(self.chapter_outlines)))

                self.chapter_outlines[start_index:end_index] = new_outlines_batch
                
                # 将本次批次成功生成的有效大纲添加到运行记录中
                successful_outlines_in_run.extend([o for o in new_outlines_batch if isinstance(o, ChapterOutline)])
                logging.info(f"成功处理第 {batch_start_num} 到 {batch_end_num} 章的大纲")
                return True # 当前批次成功

            except Exception as e:
                logging.error(f"处理大纲数据或调用模型时发生未预期错误 (尝试 {attempt + 1})：{str(e)}", exc_info=True) # 添加 exc_info
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1)) # 指数退避
                else:
                    logging.error(f"章节 {batch_start_num}-{batch_end_num} 重试次数耗尽，生成失败。")
                    return False # 重试次数耗尽

        logging.error(f"处理第 {batch_start_num} 到 {batch_end_num} 章的大纲时，所有尝试均失败。")
        return False # 所有尝试都失败了

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
                # 解析并更新同步信息
                updated_sync_info = json.loads(new_sync_info)
                updated_sync_info["最后更新时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.sync_info = updated_sync_info
                return self._save_sync_info()
            except json.JSONDecodeError as e:
                logging.error(f"解析更新后的同步信息失败: {str(e)}")
                return False

        except Exception as e:
            logging.error(f"更新同步信息时出错: {str(e)}", exc_info=True)
            return False

    def _get_context_for_batch(self, batch_start_num: int) -> str:
        """获取批次的上下文信息"""
        context_parts = []
        
        # 添加同步信息到上下文
        if self.sync_info:
            context_parts.append("[全局信息]")
            # 添加主线梗概
            if self.sync_info.get("剧情发展", {}).get("主线梗概"):
                context_parts.append(f"主线发展：{self.sync_info['剧情发展']['主线梗概']}")
            
            # 添加最近的前情提要
            if self.sync_info.get("前情提要"):
                recent_summary = self.sync_info["前情提要"][-3:]  # 最近3条
                context_parts.append("最近剧情：\n" + "\n".join(recent_summary))
            
            # 添加进行中的冲突
            if self.sync_info.get("剧情发展", {}).get("进行中冲突"):
                context_parts.append("当前冲突：\n- " + "\n- ".join(self.sync_info["剧情发展"]["进行中冲突"]))
        
        # 获取前 N 章的大纲信息 (例如前3章)
        context_chapters_count = 3
        start_index = max(0, batch_start_num - 1 - context_chapters_count)
        end_index = max(0, batch_start_num - 1)

        previous_outlines_text = []
        if end_index > start_index:
             previous_outlines = [o for o in self.chapter_outlines[start_index:end_index] if isinstance(o, ChapterOutline)] # 只使用有效的大纲
             if previous_outlines:
                 context_parts.append(f"[前 {len(previous_outlines)} 章大纲概要]")
                 for prev_outline in previous_outlines:
                    previous_outlines_text.append(f"第 {prev_outline.chapter_number} 章: {prev_outline.title}\n  关键点: {', '.join(prev_outline.key_points[:2])}...") # 限制长度
                 context_parts.append("\n".join(previous_outlines_text))
             else:
                 context_parts.append("[前文大纲]\n（无有效的前文章节大纲可供参考）")
        elif batch_start_num == 1:
            context_parts.append("[前文大纲]\n（这是第一批生成的大纲，无前文）")
        else:
             context_parts.append("[前文大纲]\n（未找到有效的前文章节大纲）")

        # 获取相关的知识库内容 (如果需要，但 get_outline_prompt 已包含此逻辑)
        # query_text = " ".join(previous_outlines_text) # 可以基于概要查询
        # if query_text:
        #     relevant_knowledge = self.knowledge_base.search(query_text, top_k=3) # 限制数量
        #     if relevant_knowledge:
        #         context_parts.append("\n[相关参考内容]\n" + "\n".join([f"- {r[:150]}..." for r in relevant_knowledge])) # 限制长度

        return "\n\n".join(context_parts)

if __name__ == "__main__":
    import argparse
    # 假设 Config, OutlineModel, KnowledgeBase 可以正确导入或用 Mock 替代
    try:
        from ..config.config import Config
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
    import re # For mock model parsing


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