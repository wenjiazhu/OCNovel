import json
import os
import sys
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# 导入您项目中的 AIConfig
# 假设脚本在 src/tools/ 目录下，需要调整路径以正确导入
# 如果从项目根目录运行，需要将 src 添加到 sys.path 或使用相对导入
try:
    # 尝试相对导入（如果脚本在 src/tools/ 并且从 src/ 运行）
    from ..config.ai_config import AIConfig
except (ImportError, ValueError):
    # 如果相对导入失败，尝试添加到 sys.path（假设从项目根目录运行）
    # 获取项目根目录（假设此脚本位于 src/tools/）
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    try:
         from src.config.ai_config import AIConfig
    except ImportError as e:
        print(f"错误: 无法导入 AIConfig。请确保 PYTHONPATH 设置正确或从项目根目录运行。 {e}")
        sys.exit(1)


# --- LLM Configuration (Now fetched from AIConfig) ---
# LLM_MODEL variable is no longer needed here

# --- Safety Settings for Gemini ---
# 您可以根据需要调整这些安全设置
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


def construct_llm_prompt(theme, config_structure_json):
    """构建用于填充 novel_config 的 LLM 提示词 (保持不变)"""
    try:
        config_structure = json.loads(config_structure_json)
        if 'theme' in config_structure:
            config_structure['theme'] = theme
        else:
            print("警告: novel_config 结构中未找到 'theme' 字段，可能导致 LLM 理解偏差。")
        formatted_structure_json = json.dumps(config_structure, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        print("错误: 提供的 config_structure_json 不是有效的 JSON。")
        formatted_structure_json = config_structure_json

    prompt = f"""
您是一个富有创造力的小说设定助手。
根据以下提供的小说【主题】:
"{theme}"

请详细填充下面的 JSON 结构中的 `novel_config` 部分。请将所有 "示例" 值、描述性文字（如 "示例力量体系或核心设定"）替换为与【主题】紧密相关、具体且有创意的设定。
请确保输出是一个【完整且有效】的 JSON 对象，该对象代表填充后的 `novel_config` 的【值】（即，不包含最外层的 "novel_config": {{...}}，只输出大括号内的内容）。
不要添加任何额外的解释或注释，只返回纯粹的 JSON 对象值。
请严格使用双引号包裹所有的键和字符串值，确保输出是标准的 JSON 格式。

模板结构如下:
```json
{formatted_structure_json}
```

请严格按照上述 JSON 结构进行填充，并确保所有 "示例" 或占位符文本都被替换。返回填充后的 JSON 对象值。
"""
    return prompt

def call_llm_to_fill_config(theme, novel_config_template):
    """调用配置好的 Gemini 模型填充 novel_config"""
    try:
        # 1. 初始化 AIConfig
        ai_config = AIConfig()

        # 2. 获取 Gemini Outline 模型配置
        gemini_outline_config = ai_config.get_gemini_config("outline")
        api_key = gemini_outline_config.get("api_key")
        model_name = gemini_outline_config.get("model_name")
        temperature = gemini_outline_config.get("temperature", 1.0) # 使用配置的 temperature

        if not api_key:
            print("错误: 从 AIConfig 获取的 GEMINI_API_KEY 为空。")
            return None
        if not model_name:
             print("错误: 从 AIConfig 获取的 Gemini outline 模型名称为空。")
             return None

        # 3. 配置 Gemini 客户端
        genai.configure(api_key=api_key)

        # 4. 准备模型和生成配置
        generation_config = genai.GenerationConfig(
            temperature=temperature,
            # response_mime_type="application/json" # Gemini Flash 可能不支持强制 JSON 输出，依赖提示词
        )
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            safety_settings=SAFETY_SETTINGS # 应用安全设置
        )

        # 5. 构建提示
        try:
            template_json = json.dumps(novel_config_template, ensure_ascii=False, indent=2)
        except TypeError:
            print("错误: novel_config_template 无法序列化为 JSON。")
            return None
        prompt = construct_llm_prompt(theme, template_json)
        print(f"\n正在调用 Gemini模型 ({model_name}) 生成详细配置，请稍候...")
        # print("\n--- Prompt ---")
        # print(prompt)
        # print("--- End Prompt ---")


        # 6. 调用 Gemini API
        response = model.generate_content(prompt)

        # 7. 处理和解析响应
        try:
            # 检查是否有候选内容以及内容部分
            if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                 # 检查是否因为安全或其他原因被阻止
                 if response.prompt_feedback.block_reason:
                     print(f"错误: Gemini 请求被阻止，原因: {response.prompt_feedback.block_reason}")
                     if response.prompt_feedback.safety_ratings:
                         print("安全评分详情:")
                         for rating in response.prompt_feedback.safety_ratings:
                             print(f"- {rating.category}: {rating.probability}")
                 else:
                     print("错误: Gemini 返回的响应无效或为空。")
                     print("原始响应:", response)
                 return None

            # 提取文本内容
            generated_text = response.text
            # print("\n--- Raw LLM Response ---")
            # print(generated_text)
            # print("--- End Raw LLM Response ---")

            # 尝试去除可能的 Markdown 代码块标记
            if generated_text.strip().startswith("```json"):
                generated_text = generated_text.strip()[7:]
            if generated_text.strip().endswith("```"):
                generated_text = generated_text.strip()[:-3]
            generated_text = generated_text.strip() # 去除首尾空白

            # 解析 JSON
            filled_novel_config = json.loads(generated_text)

            if not isinstance(filled_novel_config, dict):
                print("错误: LLM 返回的不是有效的 JSON 对象。")
                print("解析后内容:", filled_novel_config)
                return None

            # 确保主题被正确保留或填充
            if 'theme' not in filled_novel_config or not filled_novel_config['theme']:
                 print("警告: LLM 返回的配置缺少 'theme'，将使用用户输入的主题。")
                 filled_novel_config['theme'] = theme
            elif filled_novel_config['theme'] != theme:
                 print(f"提示: LLM 修改了主题，已修正为用户输入的主题: '{theme}'")
                 filled_novel_config['theme'] = theme

            print("LLM 配置生成成功并已解析。")
            return filled_novel_config

        except json.JSONDecodeError as e:
            print(f"错误: 解析 LLM 返回内容失败，不是有效的 JSON: {e}")
            print("原始返回文本:", generated_text) # 打印清理后的文本
            return None
        except AttributeError as e:
             print(f"错误: 处理 Gemini 响应时出错: {e}. 可能响应结构不符合预期。")
             print("原始响应:", response)
             return None
        except google_exceptions.GoogleAPIError as e:
             print(f"错误: 调用 Gemini API 时发生 Google API 错误: {e}")
             return None
        except Exception as e:
             print(f"解析或处理 LLM 响应时发生未知错误: {e}")
             print("原始响应:", response)
             return None


    except ValueError as e: # 来自 AIConfig 的错误
        print(f"错误: AI 配置无效: {e}")
    except ImportError:
         # AIConfig 导入失败的错误已在模块级别处理
         pass
    except Exception as e:
        print(f"调用 LLM 或处理配置时发生未知错误: {e}")

    return None


def generate_config_from_theme(theme_input, template_path="config.json.example", output_path="config.json"):
    """
    根据模板和用户输入的主题生成 config.json 文件，并使用配置的 Gemini 模型填充 novel_config。
    """
    try:
        # 修正模板和输出路径，使其相对于脚本位置或项目根目录更可靠
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(script_dir)) # 退两层到项目根目录

        # 如果模板路径是相对的，则假定它相对于项目根目录
        if not os.path.isabs(template_path):
            template_path = os.path.join(project_root, template_path)

        # 如果输出路径是相对的，则假定它相对于项目根目录
        if not os.path.isabs(output_path):
            output_path = os.path.join(project_root, output_path)


        if not os.path.exists(template_path):
            print(f"错误: 模板文件 '{template_path}' 未找到。")
            return

        with open(template_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        if 'novel_config' not in config_data or not isinstance(config_data['novel_config'], dict):
            print(f"错误: 模板文件 '{template_path}' 中未找到有效的 'novel_config' 部分或其格式不正确。")
            config_data['novel_config'] = {"theme": theme_input, "type": "待填充", "style": "待填充"}
            print("已创建基本的 novel_config 结构。")


        novel_config_template = config_data.get('novel_config', {})
        novel_config_template['theme'] = theme_input


        # 调用 LLM 填充 novel_config
        filled_novel_config = call_llm_to_fill_config(theme_input, novel_config_template)

        if filled_novel_config:
            config_data['novel_config'] = filled_novel_config
            print(f"\n使用 LLM 生成的内容更新了 'novel_config'。")
        else:
            print("\n未能从 LLM 获取有效的配置。将仅更新主题，其余保留模板值。")
            config_data['novel_config']['theme'] = theme_input


        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        print(f"\n成功生成配置文件 '{output_path}'。")
        if filled_novel_config:
             print("请检查生成的 novel_config 内容是否符合预期，并根据需要进行调整。")
        print(f"文件中的其他顶级配置项（如路径）仍来自模板 '{template_path}'，")
        print(f"请手动编辑 '{output_path}' 以设置实际值。")

    except json.JSONDecodeError:
        print(f"错误: 模板文件 '{template_path}' 包含无效的 JSON。")
    except IOError as e:
        print(f"错误: 读写文件时发生错误: {e}")
    except Exception as e:
        print(f"生成配置文件时发生未知错误: {e}")

if __name__ == "__main__":
    # 相对于项目根目录定位文件更稳健
    project_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_template_file = os.path.join(project_root_dir, "config.json.example")
    default_output_file = os.path.join(project_root_dir, "config.json")

    # 检查模板文件是否存在
    if not os.path.exists(default_template_file):
         print(f"错误: 模板文件 '{default_template_file}' 未找到。")
         print("请确保 'config.json.example' 文件位于项目根目录下。")
         sys.exit(1)

    # 检查 .env 文件是否存在并包含 GEMINI_API_KEY (由 AIConfig 内部处理，这里仅作提示)
    env_path = os.path.join(project_root_dir, ".env")
    if not os.path.exists(env_path):
        print("警告: 未找到 .env 文件。请确保已创建 .env 文件并设置了所需的 API 密钥（如 GEMINI_API_KEY）。")
    else:
        # 简单检查下 .env 是否包含 GEMINI_API_KEY
        with open(env_path, 'r') as f:
            if 'GEMINI_API_KEY' not in f.read():
                 print("警告: .env 文件中似乎缺少 'GEMINI_API_KEY'。请确保已正确设置。")


    print(f"将使用模板 '{os.path.basename(default_template_file)}' 和 AIConfig 中的 Gemini 模型生成 '{os.path.basename(default_output_file)}'。")
    user_theme = input("请输入您的小说主题: ")

    if user_theme:
        # 传递绝对路径给函数
        generate_config_from_theme(user_theme, default_template_file, default_output_file)
    else:
        print("未输入主题，操作已取消。")
