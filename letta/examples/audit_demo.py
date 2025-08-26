#!/usr/bin/env python3
"""
Letta RAG审计系统演示
展示如何在Quick RAG系统中使用审计功能
"""

import sys
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta.server.audit_system import get_audit_system, log_server_event, AuditEventType, AuditLevel


def demo_audit_usage():
    """演示审计系统的使用"""
    print("🔍 Letta RAG审计系统演示")
    print("=" * 50)
    
    # 1. 获取审计系统实例
    audit_system = get_audit_system()
    print("✅ 审计系统已初始化")
    
    # 2. 模拟用户启动RAG会话
    print("\n📱 用户启动RAG会话...")
    log_server_event(
        event_type=AuditEventType.USER_SESSION_START,
        level=AuditLevel.INFO,
        action="start_rag_session",
        user_id="demo_user",
        session_id="demo_session_001",
        ip_address="192.168.1.100",
        details={
            "client_type": "web_browser",
            "document": "jr.pdf"  # 人民币理财产品说明书
        }
    )
    
    # 3. 模拟文档处理
    print("📄 处理金融文档...")
    log_server_event(
        event_type=AuditEventType.DOCUMENT_PROCESSING,
        level=AuditLevel.INFO,
        action="process_financial_document",
        user_id="demo_user",
        session_id="demo_session_001",
        resource="jr.pdf",
        details={
            "document_type": "理财产品说明书",
            "pages": 15,
            "processing_method": "pdf_extraction"
        },
        response_time_ms=2500
    )
    
    # 4. 模拟用户查询理财产品信息
    print("💰 用户查询理财产品信息...")
    log_server_event(
        event_type=AuditEventType.PRODUCT_INFO_QUERY,
        level=AuditLevel.INFO,
        action="query_product_details",
        user_id="demo_user",
        session_id="demo_session_001",
        data_content="这个理财产品的风险等级是什么？投资期限多长？",
        details={
            "query_category": "产品风险和期限",
            "rag_chunks_found": 3,
            "confidence_score": 0.87
        },
        response_time_ms=1200
    )
    
    # 5. 模拟查询收益相关信息
    print("📊 用户查询收益信息...")
    log_server_event(
        event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
        level=AuditLevel.COMPLIANCE,
        action="query_investment_returns",
        user_id="demo_user",
        session_id="demo_session_001",
        data_content="预期年化收益率是多少？有没有保本承诺？",
        details={
            "query_category": "收益率和保本情况",
            "contains_risk_terms": True,
            "requires_risk_disclosure": True
        },
        response_time_ms=950
    )
    
    # 6. 模拟高风险查询（敏感信息）
    print("⚠️ 检测到敏感信息查询...")
    log_server_event(
        event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
        level=AuditLevel.SECURITY,
        action="sensitive_data_query",
        user_id="demo_user",
        session_id="demo_session_001",
        data_content="客户身份证信息和银行卡号",
        details={
            "data_sensitivity": "high",
            "contains_personal_info": True,
            "authorization_required": True
        },
        success=False,
        error_message="未授权访问敏感客户信息"
    )
    
    # 7. 模拟合规性检查
    print("⚖️ 执行合规性检查...")
    log_server_event(
        event_type=AuditEventType.COMPLIANCE_CHECK,
        level=AuditLevel.COMPLIANCE,
        action="financial_compliance_audit",
        user_id="system",
        session_id="demo_session_001",
        details={
            "check_type": "financial_document_compliance",
            "missing_disclosures": ["风险提示", "费用说明"],
            "compliance_score": 75
        }
    )
    
    # 8. 获取实时统计
    print("\n📊 获取实时统计...")
    stats = audit_system.get_real_time_stats()
    print(f"   总事件数: {stats['total_events']}")
    print(f"   高风险事件: {stats['high_risk_events']}")
    print(f"   金融事件: {stats['financial_events']}")
    print(f"   合规违规: {stats['compliance_violations']}")
    
    # 9. 生成审计报告
    print("\n📋 生成审计报告...")
    try:
        from letta.server.audit_report_generator import LettaAuditReportGenerator
        
        generator = LettaAuditReportGenerator()
        report_path = generator.generate_comprehensive_report(
            hours=1,  # 最近1小时
            output_format="html",
            include_financial_analysis=True
        )
        print(f"   ✅ 报告已生成: {report_path}")
        
        # 生成合规性报告
        compliance_report = generator.generate_compliance_report(hours=1)
        print(f"   ✅ 合规报告已生成: {compliance_report}")
        
    except Exception as e:
        print(f"   ❌ 报告生成失败: {e}")
    
    # 10. 结束会话
    print("\n👋 结束RAG会话...")
    log_server_event(
        event_type=AuditEventType.USER_SESSION_END,
        level=AuditLevel.INFO,
        action="end_rag_session",
        user_id="demo_user",
        session_id="demo_session_001",
        details={
            "session_duration_minutes": 15,
            "total_queries": 4,
            "documents_accessed": 1
        }
    )
    
    print("\n" + "=" * 50)
    print("🎉 审计系统演示完成！")
    print("\n📁 查看生成的文件:")
    print("   - 审计日志: ./logs/letta_server_audit.log")
    print("   - 审计数据库: ./logs/letta_audit.db")
    print("   - 高风险事件: ./logs/high_risk_events.log")
    print("   - 审计报告: ./reports/")
    
    print("\n🌐 API端点:")
    print("   - 实时统计: GET http://localhost:8283/v1/audit/stats")
    print("   - 审计报告: GET http://localhost:8283/v1/audit/report")
    print("   - 系统健康: GET http://localhost:8283/v1/audit/health")


if __name__ == "__main__":
    demo_audit_usage()
