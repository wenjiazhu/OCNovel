#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gemini模型配置验证脚本
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_gemini_config():
    """测试Gemini模型配置"""
    print("🔧 Gemini模型配置验证")
    print("=" * 50)
    
    try:
        from src.config.config import Config
        from src.models.gemini_model import GeminiModel
        
        # 加载配置
        print("1. 加载配置...")
        config = Config("config.json")
        print("✓ 配置加载成功")
        
        # 检查content_model配置
        print("\n2. 检查content_model配置...")
        content_config = config.model_config["content_model"]
        print(f"  模型类型: {content_config.get('type')}")
        print(f"  模型名称: {content_config.get('model_name')}")
        print(f"  最大重试次数: {content_config.get('max_retries')}")
        print(f"  上下文长度: {content_config.get('max_input_length')} tokens")
        print(f"  超时时间: {content_config.get('timeout')} 秒")
        print(f"  重试延迟: {content_config.get('retry_delay')} 秒")
        
        # 检查outline_model配置
        print("\n3. 检查outline_model配置...")
        outline_config = config.model_config["outline_model"]
        print(f"  模型类型: {outline_config.get('type')}")
        print(f"  模型名称: {outline_config.get('model_name')}")
        print(f"  最大重试次数: {outline_config.get('max_retries')}")
        print(f"  上下文长度: {outline_config.get('max_input_length')} tokens")
        print(f"  超时时间: {outline_config.get('timeout')} 秒")
        print(f"  重试延迟: {outline_config.get('retry_delay')} 秒")
        
        # 创建模型实例并验证配置
        print("\n4. 创建模型实例并验证配置...")
        content_model = GeminiModel(content_config)
        outline_model = GeminiModel(outline_config)
        
        print(f"  Content模型实例:")
        print(f"    最大重试次数: {content_model.max_retries}")
        print(f"    上下文长度: {content_model.max_input_length}")
        print(f"    超时时间: {content_model.timeout}")
        
        print(f"  Outline模型实例:")
        print(f"    最大重试次数: {outline_model.max_retries}")
        print(f"    上下文长度: {outline_model.max_input_length}")
        print(f"    超时时间: {outline_model.timeout}")
        
        # 验证配置是否符合要求
        print("\n5. 验证配置要求...")
        content_ok = (
            content_model.max_retries == 3 and
            content_model.max_input_length == 60000
        )
        outline_ok = (
            outline_model.max_retries == 3 and
            outline_model.max_input_length == 60000
        )
        
        if content_ok:
            print("✓ Content模型配置符合要求")
        else:
            print("✗ Content模型配置不符合要求")
            
        if outline_ok:
            print("✓ Outline模型配置符合要求")
        else:
            print("✗ Outline模型配置不符合要求")
        
        return content_ok and outline_ok
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    success = test_gemini_config()
    
    if success:
        print("\n✅ Gemini模型配置验证成功！")
        print("💡 配置修改已生效：")
        print("   - 重试次数: 5次 → 3次")
        print("   - 上下文长度: 500000字符 → 60000 tokens")
    else:
        print("\n❌ Gemini模型配置验证失败")
        print("💡 请检查配置文件")

if __name__ == "__main__":
    main() 