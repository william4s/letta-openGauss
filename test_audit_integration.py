#!/usr/bin/env python3
"""
Letta服务器审计系统测试脚本
"""

import sys
import time
import requests
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta.server.audit_system import get_audit_system, log_server_event, AuditEventType, AuditLevel


def test_audit_system():
    """测试审计系统功能"""
    print("🔍 测试Letta服务器审计系统")
    print("=" * 50)
    
    # 获取审计系统实例
    audit_system = get_audit_system()
    print(f"✅ 审计系统已初始化")
    
    # 测试1: 记录基本事件
    print("\\n📝 测试1: 记录基本审计事件")
    event = log_server_event(
        event_type=AuditEventType.USER_SESSION_START,
        level=AuditLevel.INFO,
        action="test_session_start",
        user_id="test_user",
        session_id="test_session_123",
        details={"test": "basic_event"}
    )
    print(f"   事件ID: {event.id}")
    print(f"   风险分数: {event.risk_score}")
    
    # 测试2: 记录金融相关事件
    print("\\n💰 测试2: 记录金融文档访问事件")
    financial_event = log_server_event(
        event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
        level=AuditLevel.SECURITY,
        action="access_financial_document",
        user_id="test_user",
        session_id="test_session_123",
        resource="jr.pdf",
        data_content="这是一个人民币理财产品说明书，包含产品风险等级、预期收益率等信息",
        details={"document_type": "financial_product_description"}
    )
    print(f"   事件ID: {financial_event.id}")
    print(f"   风险分数: {financial_event.risk_score}")
    print(f"   金融类别: {financial_event.financial_category}")
    
    # 测试3: 记录RAG查询事件
    print("\\n❓ 测试3: 记录RAG查询事件")
    query_event = log_server_event(
        event_type=AuditEventType.RAG_QUERY,
        level=AuditLevel.INFO,
        action="user_question",
        user_id="test_user",
        session_id="test_session_123",
        data_content="这个理财产品的风险等级是什么？投资期限多长？",
        response_time_ms=150,
        details={"query_type": "product_risk_inquiry"}
    )
    print(f"   事件ID: {query_event.id}")
    print(f"   风险分数: {query_event.risk_score}")
    print(f"   响应时间: {query_event.response_time_ms}ms")
    
    # 测试4: 记录错误事件
    print("\\n❌ 测试4: 记录错误事件")
    error_event = log_server_event(
        event_type=AuditEventType.SYSTEM_ERROR,
        level=AuditLevel.ERROR,
        action="test_error",
        user_id="test_user",
        session_id="test_session_123",
        success=False,
        error_message="测试错误消息",
        details={"error_type": "test_error"}
    )
    print(f"   事件ID: {error_event.id}")
    print(f"   风险分数: {error_event.risk_score}")
    
    # 等待一秒让事件被处理
    time.sleep(1)
    
    # 测试5: 生成审计报告
    print("\\n📊 测试5: 生成审计报告")
    report = audit_system.generate_audit_report(hours=1)
    print(f"   总事件数: {report.get('summary', {}).get('total_events', 0)}")
    print(f"   高风险事件: {report.get('summary', {}).get('high_risk_events', 0)}")
    print(f"   金融事件: {report.get('summary', {}).get('financial_events', 0)}")
    
    # 测试6: 获取实时统计
    print("\\n📈 测试6: 获取实时统计")
    stats = audit_system.get_real_time_stats()
    print(f"   总事件数: {stats.get('total_events', 0)}")
    print(f"   高风险事件: {stats.get('high_risk_events', 0)}")
    print(f"   运行时长: {stats.get('uptime_hours', 0):.2f}小时")
    
    print("\\n✅ 审计系统测试完成")


def test_audit_api():
    """测试审计API端点 (需要服务器运行)"""
    print("\\n🌐 测试审计API端点")
    print("=" * 30)
    
    base_url = "http://localhost:8283/v1"
    
    try:
        # 测试获取审计统计
        print("📊 测试获取审计统计...")
        response = requests.get(f"{base_url}/audit/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✅ 成功获取统计: 总事件 {stats.get('total_events', 0)}")
        else:
            print(f"   ❌ 获取统计失败: {response.status_code}")
    
    except requests.exceptions.ConnectionError:
        print("   ⚠️ 无法连接到Letta服务器，请确保服务器正在运行")
        print("   提示: 运行 'letta server' 启动服务器")
    
    except Exception as e:
        print(f"   ❌ API测试失败: {e}")


def main():
    """主测试函数"""
    print("🧪 Letta服务器审计系统测试")
    print("=" * 60)
    
    # 测试审计系统核心功能
    test_audit_system()
    
    # 测试API端点 (如果服务器在运行)
    test_audit_api()
    
    print("\\n🎉 测试完成！")
    print("\\n💡 提示:")
    print("1. 启动Letta服务器: letta server")
    print("2. 访问审计仪表板: http://localhost:8283/v1/audit/dashboard")
    print("3. 运行增强版RAG: python letta/examples/audited_quick_rag.py")


if __name__ == "__main__":
    main()
