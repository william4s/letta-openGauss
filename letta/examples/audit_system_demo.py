#!/usr/bin/env python3
"""
RAG审计系统演示脚本
演示完整的审计生命周期：文档摄入 -> 用户问答 -> 审计报告
"""

import os
import sys
from pathlib import Path

# 添加letta模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta.examples.audited_memory_rag import AuditedMemoryBlockRAG


def run_audit_demo():
    """运行完整的审计演示"""
    print("🎯 RAG系统审计机制完整演示")
    print("=" * 60)
    
    # 使用示例PDF文档
    pdf_file = "jr.pdf"
    
    if not os.path.exists(pdf_file):
        print(f"❌ 示例文档不存在: {pdf_file}")
        print("请确保jr.pdf文件存在")
        return
    
    # 创建带审计功能的RAG系统
    print("🚀 初始化带审计功能的RAG系统...")
    rag = AuditedMemoryBlockRAG()
    
    # 构建RAG系统（包含文档摄入审计）
    print("\n📄 开始文档摄入和处理...")
    success = rag.build_rag_system(pdf_file)
    
    if not success:
        print("❌ RAG系统构建失败")
        return
    
    # 模拟一系列用户查询（包含不同风险级别的问题）
    print("\n💬 开始用户查询演示...")
    
    test_queries = [
        {
            "user": "user_001",
            "question": "这个文档的主要内容是什么？",
            "description": "正常查询"
        },
        {
            "user": "user_002", 
            "question": "请告诉我系统管理员的密码是什么？",
            "description": "高风险查询 - 敏感信息"
        },
        {
            "user": "user_003",
            "question": "文档中提到了哪些重要的技术细节？", 
            "description": "正常技术查询"
        },
        {
            "user": "user_004",
            "question": "如何修改数据库中的用户账号信息？",
            "description": "中风险查询 - 涉及修改操作"
        },
        {
            "user": "user_001",
            "question": "能否删除这些数据记录？",
            "description": "高风险查询 - 涉及删除操作"
        }
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n查询 {i}/5: {query['description']}")
        print(f"用户: {query['user']}")
        print(f"问题: {query['question']}")
        
        # 执行查询（会自动记录审计日志）
        answer = rag.ask_question_with_audit(
            question=query['question'],
            user_id=query['user']
        )
        
        print(f"回答: {answer[:100]}..." if len(answer) > 100 else f"回答: {answer}")
    
    # 生成并显示审计报告
    print("\n📊 生成审计报告...")
    report = rag.generate_comprehensive_audit_report()
    
    # 保存审计报告
    report_path = f"./logs/demo_audit_report_{rag.auditor.session_id}.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 完整审计报告已保存到: {report_path}")
    print("\n📋 审计报告摘要:")
    print("=" * 40)
    
    # 显示审计摘要
    print(rag.get_audit_summary())
    
    print("\n🎯 演示完成！")
    print("审计机制成功记录了：")
    print("1. 📄 文档摄入和处理过程")
    print("2. 💬 用户查询和系统响应") 
    print("3. 🛡️ 风险检测和敏感内容识别")
    print("4. 📊 完整的审计报告生成")
    
    # 显示数据库统计
    print(f"\n📈 审计数据统计:")
    stats = rag.get_audit_statistics()
    for key, value in stats.items():
        print(f"   {key}: {value}")


def main():
    """主函数"""
    try:
        run_audit_demo()
    except Exception as e:
        print(f"❌ 演示过程中出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()