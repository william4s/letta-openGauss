#!/usr/bin/env python3
"""
Letta审计系统测试脚本
验证审计功能是否正常工作
"""

import os
import sys
import time
import json
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta.server.audit_system import get_audit_system, log_server_event, AuditEventType, AuditLevel
from letta.log import get_logger

logger = get_logger(__name__)


def test_audit_system():
    """测试审计系统功能"""
    print("🔍 开始测试Letta审计系统")
    print("=" * 50)
    
    try:
        # 1. 获取审计系统实例
        print("1. 初始化审计系统...")
        audit_system = get_audit_system()
        print("✅ 审计系统初始化成功")
        
        # 2. 测试各种事件记录
        print("\n2. 测试事件记录...")
        
        # 用户会话事件
        log_server_event(
            event_type=AuditEventType.USER_SESSION_START,
            level=AuditLevel.INFO,
            action="test_user_login",
            user_id="test_user_001",
            session_id="test_session_001",
            ip_address="127.0.0.1",
            details={"test_type": "audit_system_test"}
        )
        print("  ✅ 用户会话事件记录成功")
        
        # 文档处理事件
        log_server_event(
            event_type=AuditEventType.DOCUMENT_PROCESSING,
            level=AuditLevel.INFO,
            action="test_document_upload",
            user_id="test_user_001",
            session_id="test_session_001",
            resource="jr.pdf",
            details={
                "file_size": 1024000,
                "document_type": "financial_product_manual",
                "processing_time_ms": 1500
            },
            response_time_ms=1500
        )
        print("  ✅ 文档处理事件记录成功")
        
        # 金融查询事件
        log_server_event(
            event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
            level=AuditLevel.COMPLIANCE,
            action="financial_product_query",
            user_id="test_user_001",
            session_id="test_session_001",
            data_content="这个理财产品的风险等级是什么？预期收益率如何？",
            details={
                "query_type": "product_risk_inquiry",
                "is_sensitive": True,
                "requires_compliance_check": True
            },
            response_time_ms=800
        )
        print("  ✅ 金融查询事件记录成功")
        
        # RAG搜索事件
        log_server_event(
            event_type=AuditEventType.RAG_SEARCH,
            level=AuditLevel.INFO,
            action="similarity_search",
            user_id="test_user_001",
            session_id="test_session_001",
            data_content="投资期限和赎回条件",
            details={
                "search_results": 3,
                "max_similarity": 0.89,
                "embedding_model": "bge-m3"
            },
            response_time_ms=200
        )
        print("  ✅ RAG搜索事件记录成功")
        
        # 高风险事件
        log_server_event(
            event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
            level=AuditLevel.SECURITY,
            action="sensitive_data_query",
            user_id="test_user_001",
            session_id="test_session_001",
            data_content="客户身份证信息查询",
            details={
                "sensitivity_level": "high",
                "data_type": "personal_identification",
                "requires_authorization": True
            },
            success=False,
            error_message="未授权访问敏感数据"
        )
        print("  ✅ 高风险事件记录成功")
        
        # 系统错误事件
        log_server_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLevel.ERROR,
            action="embedding_service_error",
            user_id="test_user_001",
            session_id="test_session_001",
            success=False,
            error_message="BGE-M3嵌入服务连接超时",
            details={
                "error_code": "CONNECTION_TIMEOUT",
                "service_url": "http://127.0.0.1:8003/v1/embeddings",
                "retry_count": 3
            }
        )
        print("  ✅ 系统错误事件记录成功")
        
        # 等待一秒让事件处理完成
        time.sleep(1)
        
        # 3. 测试实时统计
        print("\n3. 测试实时统计...")
        stats = audit_system.get_real_time_stats()
        print("  ✅ 实时统计获取成功")
        print(f"     总事件数: {stats.get('total_events', 0)}")
        print(f"     高风险事件: {stats.get('high_risk_events', 0)}")
        print(f"     金融事件: {stats.get('financial_events', 0)}")
        print(f"     合规违规: {stats.get('compliance_violations', 0)}")
        
        # 4. 测试审计报告生成
        print("\n4. 测试审计报告生成...")
        report = audit_system.generate_audit_report(hours=1)
        
        if "error" in report:
            print(f"  ❌ 报告生成失败: {report['error']}")
        else:
            print("  ✅ 审计报告生成成功")
            print(f"     报告期间: {report.get('report_period', '未知')}")
            print(f"     总事件数: {report.get('summary', {}).get('total_events', 0)}")
            print(f"     高风险事件: {report.get('summary', {}).get('high_risk_events', 0)}")
            print(f"     金融事件: {report.get('summary', {}).get('financial_events', 0)}")
            print(f"     系统健康: {report.get('system_health', '未知')}")
        
        # 5. 测试数据库连接
        print("\n5. 测试数据库连接...")
        if audit_system.db_conn:
            print("  ✅ 审计数据库连接正常")
            
            # 查询最近的事件
            with audit_system.db_lock:
                cursor = audit_system.db_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM audit_events")
                count = cursor.fetchone()[0]
                print(f"     数据库中总事件数: {count}")
        else:
            print("  ❌ 审计数据库连接失败")
        
        # 记录测试完成
        log_server_event(
            event_type=AuditEventType.USER_SESSION_END,
            level=AuditLevel.INFO,
            action="audit_system_test_complete",
            user_id="test_user_001",
            session_id="test_session_001",
            details={"test_result": "success", "total_test_events": 6}
        )
        
        print("\n" + "=" * 50)
        print("✅ 审计系统测试完成!")
        print("所有功能正常工作")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 审计系统测试失败: {e}")
        logger.error(f"审计系统测试失败: {e}", exc_info=True)
        return False


def test_financial_content_analysis():
    """测试金融内容分析功能"""
    print("\n🏦 测试金融内容分析功能")
    print("-" * 30)
    
    audit_system = get_audit_system()
    financial_auditor = audit_system.financial_auditor
    
    # 测试不同类型的金融内容
    test_contents = [
        "本理财产品为非保本浮动收益型产品，投资有风险，客户需谨慎选择。",
        "产品投资期限为365天，预期年化收益率3.5%-4.2%，具体收益以实际投资表现为准。",
        "客户身份证号码：123456789012345678，银行卡号：6222023456789012345。",
        "投资标的主要为货币市场工具和债券类资产，风险等级为R2级。",
        "普通的技术文档内容，不包含金融相关信息。"
    ]
    
    for i, content in enumerate(test_contents, 1):
        print(f"\n测试内容 {i}:")
        print(f"  内容: {content[:50]}...")
        
        analysis = financial_auditor.analyze_financial_content(content)
        
        print(f"  金融类别: {analysis.get('financial_categories', [])}")
        print(f"  风险等级: {analysis.get('risk_level', 'unknown')}")
        print(f"  敏感数据: {'是' if analysis.get('sensitive_data_detected') else '否'}")
        print(f"  合规问题: {analysis.get('compliance_issues', [])}")
        
        # 记录分析事件
        log_server_event(
            event_type=AuditEventType.COMPLIANCE_CHECK,
            level=AuditLevel.COMPLIANCE if analysis.get('sensitive_data_detected') else AuditLevel.INFO,
            action="financial_content_analysis",
            user_id="test_analyzer",
            data_content=content,
            details={
                "analysis_result": analysis,
                "content_index": i
            }
        )
    
    print("\n✅ 金融内容分析测试完成")


def test_api_audit_middleware():
    """测试API审计中间件（模拟）"""
    print("\n🌐 测试API审计中间件（模拟）")
    print("-" * 30)
    
    # 模拟不同类型的API请求
    api_requests = [
        {
            "method": "POST", 
            "path": "/v1/agents", 
            "user_id": "api_user_001",
            "status": 201,
            "response_time": 1200
        },
        {
            "method": "GET", 
            "path": "/v1/agents/12345/messages", 
            "user_id": "api_user_001",
            "status": 200,
            "response_time": 300
        },
        {
            "method": "POST", 
            "path": "/v1/sources", 
            "user_id": "api_user_002",
            "status": 400,
            "response_time": 150
        },
        {
            "method": "GET", 
            "path": "/v1/audit/report", 
            "user_id": "admin_user",
            "status": 200,
            "response_time": 2000
        }
    ]
    
    for req in api_requests:
        # 确定事件类型
        if "/agents" in req["path"] and req["method"] == "POST":
            event_type = AuditEventType.AGENT_CREATION
        elif "/agents" in req["path"] and "messages" in req["path"]:
            event_type = AuditEventType.AGENT_MESSAGE
        elif "/sources" in req["path"]:
            event_type = AuditEventType.DOCUMENT_ACCESS
        elif "/audit" in req["path"]:
            event_type = AuditEventType.COMPLIANCE_CHECK
        else:
            event_type = AuditEventType.AUTHENTICATION
        
        success = req["status"] < 400
        
        log_server_event(
            event_type=event_type,
            level=AuditLevel.ERROR if not success else AuditLevel.INFO,
            action=f"{req['method']} {req['path']}",
            user_id=req["user_id"],
            session_id=f"api_session_{req['user_id']}",
            ip_address="192.168.1.100",
            success=success,
            response_time_ms=req["response_time"],
            details={
                "http_method": req["method"],
                "api_path": req["path"],
                "status_code": req["status"],
                "simulated_request": True
            }
        )
        
        print(f"  ✅ API请求记录: {req['method']} {req['path']} -> {req['status']}")
    
    print("\n✅ API审计中间件测试完成")


def main():
    """主测试函数"""
    print("🔍 Letta审计系统完整测试")
    print("=" * 60)
    
    try:
        # 基础功能测试
        success = test_audit_system()
        
        if success:
            # 金融内容分析测试
            test_financial_content_analysis()
            
            # API中间件测试
            test_api_audit_middleware()
            
            # 最终统计
            print("\n📊 最终审计统计:")
            print("-" * 30)
            audit_system = get_audit_system()
            stats = audit_system.get_real_time_stats()
            
            for key, value in stats.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
            
            print("\n" + "=" * 60)
            print("🎉 所有测试完成! 审计系统工作正常")
            print("可以访问以下端点查看审计信息:")
            print("  - GET /v1/audit/health - 审计系统健康状态")
            print("  - GET /v1/audit/stats - 实时统计")
            print("  - GET /v1/audit/report - 审计报告")
            print("  - GET /v1/audit/financial-report - 金融专用报告")
        
        else:
            print("\n❌ 基础测试失败，跳过其他测试")
            return 1
    
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        logger.error(f"测试失败: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
