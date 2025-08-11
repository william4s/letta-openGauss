#!/usr/bin/env python3
"""
Letta RAG安全审计功能测试脚本
用于验证审计机制的各项功能是否正常工作
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

from security_audit import SecurityAuditor, AuditEventType, AuditLevel
from audited_rag_system import AuditedQuickRAG


class AuditSystemTester:
    """审计系统测试器"""
    
    def __init__(self):
        self.test_results = []
        self.auditor = SecurityAuditor(
            audit_log_path="./logs/test_audit.log",
            enable_console_output=True
        )
        
        # 创建测试目录
        os.makedirs("./logs", exist_ok=True)
        print("🧪 初始化审计系统测试器")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("🚀 开始Letta RAG安全审计功能测试")
        print("=" * 60)
        
        # 基础功能测试
        self.test_basic_audit_logging()
        self.test_risk_scoring()
        self.test_sensitive_data_detection()
        self.test_event_types()
        
        # 高级功能测试
        self.test_audit_report_generation()
        self.test_user_session_tracking()
        
        # RAG集成测试
        self.test_rag_integration()
        
        # 性能测试
        self.test_performance_impact()
        
        # 输出测试结果
        self.print_test_summary()
    
    def test_basic_audit_logging(self):
        """测试基础审计日志功能"""
        print("\n📝 测试1: 基础审计日志功能")
        
        try:
            # 记录测试事件
            event = self.auditor.log_event(
                event_type=AuditEventType.USER_SESSION_START,
                level=AuditLevel.INFO,
                action="test_login",
                user_id="test_user",
                session_id="test_session",
                ip_address="127.0.0.1",
                details={"test": True}
            )
            
            # 验证事件是否正确记录
            assert event.event_type == "USER_SESSION_START"
            assert event.user_id == "test_user"
            assert event.success == True
            
            self.test_results.append(("基础审计日志", "✅ 通过"))
            print("   ✅ 基础审计日志功能正常")
            
        except Exception as e:
            self.test_results.append(("基础审计日志", f"❌ 失败: {e}"))
            print(f"   ❌ 基础审计日志测试失败: {e}")
    
    def test_risk_scoring(self):
        """测试风险评分机制"""
        print("\n⚠️ 测试2: 风险评分机制")
        
        try:
            # 测试低风险事件
            low_risk_event = self.auditor.log_event(
                event_type=AuditEventType.USER_SESSION_START,
                level=AuditLevel.INFO,
                action="normal_login",
                user_id="test_user",
                details={"normal": True}
            )
            
            # 测试高风险事件
            high_risk_event = self.auditor.log_event(
                event_type=AuditEventType.SENSITIVE_DATA_ACCESS,
                level=AuditLevel.SECURITY,
                action="access_sensitive",
                user_id="test_user",
                details={"contains_password": True},
                data_content="这里包含密码信息"
            )
            
            # 验证风险评分
            assert low_risk_event.risk_score < 40, f"低风险事件评分异常: {low_risk_event.risk_score}"
            assert high_risk_event.risk_score >= 70, f"高风险事件评分异常: {high_risk_event.risk_score}"
            
            self.test_results.append(("风险评分机制", "✅ 通过"))
            print(f"   ✅ 低风险评分: {low_risk_event.risk_score}, 高风险评分: {high_risk_event.risk_score}")
            
        except Exception as e:
            self.test_results.append(("风险评分机制", f"❌ 失败: {e}"))
            print(f"   ❌ 风险评分测试失败: {e}")
    
    def test_sensitive_data_detection(self):
        """测试敏感数据检测"""
        print("\n🔍 测试3: 敏感数据检测")
        
        try:
            # 测试敏感词检测
            test_cases = [
                ("这是普通文本", False),
                ("用户密码是123456", True),
                ("请提供您的身份证号码", True),
                ("This contains password information", True),
                ("Normal query about products", False)
            ]
            
            correct_detections = 0
            for text, expected_sensitive in test_cases:
                is_sensitive = self.auditor._detect_sensitive_data(text)
                if is_sensitive == expected_sensitive:
                    correct_detections += 1
                print(f"   文本: '{text}' -> 敏感: {is_sensitive} ({'✅' if is_sensitive == expected_sensitive else '❌'})")
            
            accuracy = correct_detections / len(test_cases)
            assert accuracy >= 0.8, f"敏感数据检测准确率过低: {accuracy}"
            
            self.test_results.append(("敏感数据检测", f"✅ 通过 (准确率: {accuracy:.1%})"))
            print(f"   ✅ 敏感数据检测准确率: {accuracy:.1%}")
            
        except Exception as e:
            self.test_results.append(("敏感数据检测", f"❌ 失败: {e}"))
            print(f"   ❌ 敏感数据检测测试失败: {e}")
    
    def test_event_types(self):
        """测试各种事件类型"""
        print("\n📊 测试4: 事件类型覆盖")
        
        try:
            event_types_to_test = [
                AuditEventType.DOCUMENT_UPLOAD,
                AuditEventType.QUERY_EXECUTION,
                AuditEventType.RAG_SEARCH,
                AuditEventType.AGENT_CREATION,
                AuditEventType.SYSTEM_ERROR
            ]
            
            events_logged = 0
            for event_type in event_types_to_test:
                try:
                    self.auditor.log_event(
                        event_type=event_type,
                        level=AuditLevel.INFO,
                        action=f"test_{event_type.value.lower()}",
                        user_id="test_user",
                        details={"test_event": True}
                    )
                    events_logged += 1
                    print(f"   ✅ {event_type.value}")
                except Exception as e:
                    print(f"   ❌ {event_type.value}: {e}")
            
            coverage = events_logged / len(event_types_to_test)
            assert coverage >= 0.8, f"事件类型覆盖率过低: {coverage}"
            
            self.test_results.append(("事件类型覆盖", f"✅ 通过 ({events_logged}/{len(event_types_to_test)})"))
            
        except Exception as e:
            self.test_results.append(("事件类型覆盖", f"❌ 失败: {e}"))
            print(f"   ❌ 事件类型测试失败: {e}")
    
    def test_audit_report_generation(self):
        """测试审计报告生成"""
        print("\n📈 测试5: 审计报告生成")
        
        try:
            # 生成一些测试事件
            for i in range(5):
                self.auditor.log_event(
                    event_type=AuditEventType.QUERY_EXECUTION,
                    level=AuditLevel.INFO,
                    action=f"test_query_{i}",
                    user_id=f"user_{i % 2}",
                    details={"query_id": i}
                )
            
            # 生成审计报告
            report = self.auditor.generate_audit_report(hours=0.1)  # 最近6分钟
            
            # 验证报告内容
            assert "total_events" in report
            assert "event_types" in report
            assert "users" in report
            assert report["total_events"] > 0
            
            self.test_results.append(("审计报告生成", "✅ 通过"))
            print(f"   ✅ 生成报告包含{report['total_events']}个事件")
            
        except Exception as e:
            self.test_results.append(("审计报告生成", f"❌ 失败: {e}"))
            print(f"   ❌ 审计报告生成测试失败: {e}")
    
    def test_user_session_tracking(self):
        """测试用户会话跟踪"""
        print("\n👤 测试6: 用户会话跟踪")
        
        try:
            test_user = "session_test_user"
            
            # 模拟用户会话
            self.auditor.log_user_session(test_user, "login", "test_session_123", "192.168.1.100")
            
            # 模拟一些用户活动
            self.auditor.log_event(
                event_type=AuditEventType.QUERY_EXECUTION,
                level=AuditLevel.INFO,
                action="user_query",
                user_id=test_user,
                session_id="test_session_123"
            )
            
            self.auditor.log_user_session(test_user, "logout", "test_session_123", "192.168.1.100")
            
            # 获取用户活动摘要
            summary = self.auditor.get_user_activity_summary(test_user, hours=0.1)
            
            assert "user_id" in summary
            assert summary["user_id"] == test_user
            assert summary["total_activities"] >= 2
            
            self.test_results.append(("用户会话跟踪", "✅ 通过"))
            print(f"   ✅ 用户{test_user}的活动记录: {summary['total_activities']}个事件")
            
        except Exception as e:
            self.test_results.append(("用户会话跟踪", f"❌ 失败: {e}"))
            print(f"   ❌ 用户会话跟踪测试失败: {e}")
    
    def test_rag_integration(self):
        """测试RAG系统集成"""
        print("\n🤖 测试7: RAG系统集成")
        
        try:
            # 创建带审计的RAG实例
            rag = AuditedQuickRAG(
                user_id="rag_test_user",
                session_id="rag_test_session"
            )
            
            # 测试文本分块（不需要实际文件）
            test_text = "这是一个测试文档。它包含多个句子。用于测试文本分块功能。"
            chunks = rag.step2_chunk_text(test_text, chunk_size=20)
            
            assert len(chunks) > 0, "文本分块失败"
            
            # 验证审计日志是否记录了RAG操作
            recent_report = rag.auditor.generate_audit_report(hours=0.1)
            rag_events = [e for e in recent_report.get('event_types', {}).keys() 
                         if 'DOCUMENT' in e or 'SESSION' in e]
            
            assert len(rag_events) > 0, "RAG操作未被审计记录"
            
            self.test_results.append(("RAG系统集成", "✅ 通过"))
            print(f"   ✅ RAG集成正常，生成{len(chunks)}个文本块")
            
        except Exception as e:
            self.test_results.append(("RAG系统集成", f"❌ 失败: {e}"))
            print(f"   ❌ RAG系统集成测试失败: {e}")
    
    def test_performance_impact(self):
        """测试性能影响"""
        print("\n⚡ 测试8: 性能影响评估")
        
        try:
            # 测试审计日志记录的性能
            num_operations = 100
            
            # 无审计版本（模拟）
            start_time = time.time()
            for i in range(num_operations):
                # 模拟一些计算操作
                _ = sum(range(100))
            no_audit_time = time.time() - start_time
            
            # 有审计版本
            start_time = time.time()
            for i in range(num_operations):
                # 同样的计算操作 + 审计日志
                _ = sum(range(100))
                self.auditor.log_event(
                    event_type=AuditEventType.QUERY_EXECUTION,
                    level=AuditLevel.INFO,
                    action=f"perf_test_{i}",
                    user_id="perf_test_user",
                    details={"iteration": i}
                )
            with_audit_time = time.time() - start_time
            
            # 计算性能影响
            if no_audit_time > 0:
                performance_impact = (with_audit_time - no_audit_time) / no_audit_time * 100
            else:
                performance_impact = 0
            
            # 性能影响应该在合理范围内（<50%）
            assert performance_impact < 50, f"性能影响过大: {performance_impact:.2f}%"
            
            self.test_results.append(("性能影响评估", f"✅ 通过 (影响: {performance_impact:.1f}%)"))
            print(f"   ✅ 审计对性能影响: {performance_impact:.1f}%")
            
        except Exception as e:
            self.test_results.append(("性能影响评估", f"❌ 失败: {e}"))
            print(f"   ❌ 性能影响测试失败: {e}")
    
    def print_test_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("📋 测试结果摘要")
        print("=" * 60)
        
        passed_tests = 0
        total_tests = len(self.test_results)
        
        for test_name, result in self.test_results:
            print(f"{result} {test_name}")
            if result.startswith("✅"):
                passed_tests += 1
        
        success_rate = passed_tests / total_tests * 100
        print(f"\n📊 测试通过率: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("🎉 审计系统测试基本通过！")
        elif success_rate >= 60:
            print("⚠️ 审计系统部分功能需要调整")
        else:
            print("❌ 审计系统存在重大问题，需要修复")
        
        # 生成测试报告文件
        self.generate_test_report()
    
    def generate_test_report(self):
        """生成测试报告文件"""
        try:
            test_report = {
                "test_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_tests": len(self.test_results),
                "passed_tests": len([r for r in self.test_results if r[1].startswith("✅")]),
                "test_results": dict(self.test_results),
                "system_info": {
                    "python_version": sys.version,
                    "platform": sys.platform
                }
            }
            
            report_file = Path("./logs/audit_test_report.json")
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(test_report, f, ensure_ascii=False, indent=2)
            
            print(f"\n📄 详细测试报告已保存: {report_file}")
            
        except Exception as e:
            print(f"⚠️ 保存测试报告失败: {e}")


def main():
    """主函数"""
    print("🔒 Letta RAG安全审计功能测试工具")
    
    # 检查依赖
    try:
        from security_audit import SecurityAuditor
        from audited_rag_system import AuditedQuickRAG
    except ImportError as e:
        print(f"❌ 导入模块失败: {e}")
        print("请确保在正确的目录中运行此测试脚本")
        return 1
    
    # 运行测试
    tester = AuditSystemTester()
    tester.run_all_tests()
    
    return 0


if __name__ == "__main__":
    exit(main())
