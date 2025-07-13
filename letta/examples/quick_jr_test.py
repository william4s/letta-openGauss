#!/usr/bin/env python3
"""
JR.PDF 快速向量化测试脚本
用于快速测试 jr.pdf 的向量化处理和检索功能
"""

import os
import sys
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from jr_rag_system import JRPDFRagSystem


def quick_test():
    """快速测试JR PDF向量化和RAG功能"""
    print("🚀 JR.PDF 快速向量化测试")
    print("=" * 50)
    
    try:
        # 创建RAG系统
        rag = JRPDFRagSystem()
        
        # 设置系统
        print("📋 设置RAG系统...")
        rag.setup()
        
        # 测试问题
        test_questions = [
            "这份JR.PDF文档的主要内容是什么？",
            "请简要总结文档的关键信息",
        ]
        
        print("\n🧪 开始测试问答...")
        print("=" * 40)
        
        for i, question in enumerate(test_questions, 1):
            print(f"\n🔍 测试问题 {i}: {question}")
            print("-" * 30)
            
            try:
                answer = rag.ask_question(question)
                print(f"✅ 测试 {i} 完成")
            except Exception as e:
                print(f"❌ 测试 {i} 失败: {e}")
            
            print("-" * 30)
        
        print("\n✅ 快速测试完成!")
        
        # 询问是否进入交互模式
        interactive = input("\n是否进入交互问答模式? (y/n): ").strip().lower()
        if interactive == 'y' or interactive == 'yes':
            rag.interactive_chat()
        
        return rag
        
    except Exception as e:
        print(f"❌ 快速测试失败: {e}")
        return None


def vector_info():
    """显示向量化信息"""
    print("\n📊 向量化处理信息:")
    print("• 嵌入模型: bge/bge-m3")
    print("• 目标文件: jr.pdf")
    print("• 向量维度: 1024 (BGE-M3标准)")
    print("• 文本分块: 自动分割")
    print("• 存储后端: OpenGauss向量数据库")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--info":
        vector_info()
    else:
        rag_system = quick_test()
        if rag_system:
            # 清理资源
            try:
                rag_system.cleanup()
            except:
                pass
