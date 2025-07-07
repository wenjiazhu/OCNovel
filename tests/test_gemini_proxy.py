import google.generativeai as genai
import os
from dotenv import load_dotenv

def test_gemini():
    """测试Gemini模型基本功能"""
    try:
        # 加载环境变量
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            print("错误：未找到Gemini API密钥")
            return False
            
        # 设置代理
        os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"
        os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
        
        # 配置Gemini
        genai.configure(api_key=api_key)
        
        # 创建模型实例
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 测试生成
        prompt = """
        你是一个专业的玄幻小说写作助手。请用一句话描述修真世界的灵气复苏场景。
        """
        
        print("\n正在测试文本生成...")
        response = model.generate_content(prompt)
        print(f"生成结果: {response.text}")
        
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("开始测试Gemini模型...")
    success = test_gemini()
    print(f"\n测试结果: {'✓ 成功' if success else '✗ 失败'}") 