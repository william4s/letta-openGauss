#!/usr/bin/env python3
"""
Letta Server集成审计系统
专门针对金融文档RAG系统的审计和合规监控
"""

import os
import json
import hashlib
import datetime
import asyncio
import uuid
import time
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor

from letta.log import get_logger

logger = get_logger(__name__)


class AuditLevel(Enum):
    """审计级别"""
    INFO = "INFO"
    WARN = "WARN" 
    ERROR = "ERROR"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"  # 合规性
    FINANCE = "FINANCE"        # 金融专用


class AuditEventType(Enum):
    """审计事件类型"""
    # 用户会话
    USER_SESSION_START = "USER_SESSION_START"
    USER_SESSION_END = "USER_SESSION_END"
    
    # 文档操作
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_ACCESS = "DOCUMENT_ACCESS"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    
    # RAG操作
    RAG_QUERY = "RAG_QUERY"
    RAG_SEARCH = "RAG_SEARCH"
    RAG_RESPONSE = "RAG_RESPONSE"
    
    # 智能体操作
    AGENT_CREATION = "AGENT_CREATION"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    AGENT_MEMORY_ACCESS = "AGENT_MEMORY_ACCESS"
    
    # 金融特定事件
    FINANCIAL_DATA_ACCESS = "FINANCIAL_DATA_ACCESS"
    RISK_ASSESSMENT_QUERY = "RISK_ASSESSMENT_QUERY"
    PRODUCT_INFO_QUERY = "PRODUCT_INFO_QUERY"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    
    # 系统事件
    SYSTEM_ERROR = "SYSTEM_ERROR"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION_CHECK = "PERMISSION_CHECK"
    EMBEDDING_GENERATION = "EMBEDDING_GENERATION"


@dataclass
class AuditEvent:
    """审计事件数据结构"""
    id: str
    timestamp: str
    event_type: str
    level: str
    user_id: Optional[str]
    session_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: str
    details: Dict[str, Any]
    success: bool
    risk_score: int = 0
    compliance_flags: List[str] = None
    financial_category: Optional[str] = None
    data_hash: Optional[str] = None
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None


class FinancialDocumentAuditor:
    """金融文档专用审计器"""
    
    def __init__(self):
        # 金融关键词检测
        self.financial_keywords = {
            "product_info": ["产品", "收益", "期限", "风险", "投资", "理财", "基金", "债券"],
            "risk_terms": ["风险", "损失", "波动", "不确定", "风险等级", "风险承受"],
            "compliance": ["合规", "监管", "法规", "条款", "披露", "说明书"],
            "sensitive_data": ["身份证", "银行卡", "账户", "密码", "个人信息", "客户资料"],
            "amount_terms": ["金额", "收益", "费用", "手续费", "管理费", "赎回费"]
        }
        
        # 合规性检查规则
        self.compliance_rules = {
            "risk_disclosure": ["风险提示", "风险揭示", "投资风险"],
            "product_description": ["产品说明", "投资标的", "投资策略"],
            "fee_structure": ["费用结构", "收费标准", "费用说明"],
            "redemption_terms": ["赎回条件", "赎回费用", "赎回流程"]
        }
    
    def analyze_financial_content(self, content: str) -> Dict[str, Any]:
        """分析金融内容"""
        analysis = {
            "financial_categories": [],
            "risk_level": "low",
            "compliance_issues": [],
            "sensitive_data_detected": False,
            "requires_disclosure": False
        }
        
        content_lower = content.lower()
        
        # 检测金融类别
        for category, keywords in self.financial_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                analysis["financial_categories"].append(category)
        
        # 风险等级评估
        risk_keywords = len([k for k in self.financial_keywords["risk_terms"] if k in content_lower])
        if risk_keywords >= 3:
            analysis["risk_level"] = "high"
        elif risk_keywords >= 1:
            analysis["risk_level"] = "medium"
        
        # 敏感数据检测
        if any(keyword in content_lower for keyword in self.financial_keywords["sensitive_data"]):
            analysis["sensitive_data_detected"] = True
        
        # 合规性检查
        for rule, terms in self.compliance_rules.items():
            if not any(term in content_lower for term in terms):
                analysis["compliance_issues"].append(f"missing_{rule}")
        
        analysis["requires_disclosure"] = bool(analysis["compliance_issues"])
        
        return analysis


class ServerAuditSystem:
    """Letta服务器集成审计系统"""
    
    def __init__(self, 
                 audit_log_path: str = "./logs/letta_server_audit.log",
                 audit_db_path: str = "./logs/letta_audit.db",
                 enable_real_time_monitoring: bool = True):
        
        self.audit_log_path = Path(audit_log_path)
        self.audit_db_path = Path(audit_db_path)
        self.enable_real_time_monitoring = enable_real_time_monitoring
        
        # 创建日志目录
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化组件
        self.financial_auditor = FinancialDocumentAuditor()
        self._setup_logger()
        self._setup_database()
        
        # 线程池用于异步审计处理
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # 实时监控状态
        self.monitoring_stats = {
            "total_events": 0,
            "high_risk_events": 0,
            "financial_events": 0,
            "compliance_violations": 0,
            "session_start_time": datetime.datetime.now()
        }
        
        logger.info("🔍 Letta服务器审计系统已启动")
    
    def _setup_logger(self):
        """设置审计日志记录器"""
        self.logger = logging.getLogger("LettaServerAudit")
        self.logger.setLevel(logging.INFO)
        self.logger.handlers.clear()
        
        # 只添加文件处理器，不添加控制台处理器
        file_handler = logging.FileHandler(self.audit_log_path, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 设置logger不传播到父logger，避免重复输出
        self.logger.propagate = False
    
    def _setup_database(self):
        """设置SQLite审计数据库"""
        try:
            self.db_conn = sqlite3.connect(str(self.audit_db_path), check_same_thread=False)
            self.db_lock = threading.Lock()
            
            # 创建审计事件表
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_events (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        level TEXT NOT NULL,
                        user_id TEXT,
                        session_id TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        resource TEXT,
                        action TEXT NOT NULL,
                        details TEXT,
                        success BOOLEAN,
                        risk_score INTEGER,
                        compliance_flags TEXT,
                        financial_category TEXT,
                        data_hash TEXT,
                        response_time_ms INTEGER,
                        error_message TEXT
                    )
                """)
                
                # 创建索引
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON audit_events(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_risk_score ON audit_events(risk_score)")
                
                self.db_conn.commit()
                
        except Exception as e:
            logger.error(f"审计数据库初始化失败: {e}")
            self.db_conn = None
    
    def _calculate_data_hash(self, data: str) -> str:
        """计算数据哈希值"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    
    def _generate_unique_event_id(self) -> str:
        """生成唯一的事件ID"""
        import uuid
        import time
        # 使用时间戳 + UUID 确保唯一性
        timestamp = str(int(time.time() * 1000000))  # 微秒时间戳
        unique_part = str(uuid.uuid4().hex)[:8]
        return f"{timestamp}_{unique_part}"
    
    def _calculate_risk_score(self, event_type: AuditEventType, action: str, 
                            details: Dict, success: bool, financial_analysis: Dict = None) -> int:
        """计算风险评分 (0-100)"""
        base_scores = {
            AuditEventType.USER_SESSION_START: 10,
            AuditEventType.DOCUMENT_UPLOAD: 30,
            AuditEventType.DOCUMENT_ACCESS: 25,
            AuditEventType.RAG_QUERY: 20,
            AuditEventType.RAG_SEARCH: 15,
            AuditEventType.AGENT_MESSAGE: 15,
            AuditEventType.FINANCIAL_DATA_ACCESS: 50,
            AuditEventType.RISK_ASSESSMENT_QUERY: 40,
            AuditEventType.PRODUCT_INFO_QUERY: 30,
            AuditEventType.COMPLIANCE_CHECK: 35,
            AuditEventType.SYSTEM_ERROR: 60,
            AuditEventType.AUTHENTICATION: 25
        }
        
        score = base_scores.get(event_type, 15)
        
        # 基于金融分析调整分数
        if financial_analysis:
            if financial_analysis.get("sensitive_data_detected"):
                score += 30
            if financial_analysis.get("risk_level") == "high":
                score += 25
            elif financial_analysis.get("risk_level") == "medium":
                score += 15
            if financial_analysis.get("compliance_issues"):
                score += 20
        
        # 其他调整因素
        if not success:
            score += 25
        if details.get("failed_attempts", 0) > 2:
            score += 20
        if details.get("bulk_operation"):
            score += 15
        
        return min(score, 100)
    
    def log_event(self,
                  event_type: AuditEventType,
                  level: AuditLevel,
                  action: str,
                  user_id: Optional[str] = None,
                  session_id: Optional[str] = None,
                  ip_address: Optional[str] = None,
                  user_agent: Optional[str] = None,
                  resource: Optional[str] = None,
                  details: Optional[Dict] = None,
                  success: bool = True,
                  data_content: Optional[str] = None,
                  response_time_ms: Optional[int] = None,
                  error_message: Optional[str] = None):
        """记录审计事件"""
        
        if details is None:
            details = {}
        
        # 金融内容分析
        financial_analysis = None
        financial_category = None
        if data_content and event_type in [
            AuditEventType.RAG_QUERY, 
            AuditEventType.FINANCIAL_DATA_ACCESS,
            AuditEventType.PRODUCT_INFO_QUERY,
            AuditEventType.RISK_ASSESSMENT_QUERY
        ]:
            financial_analysis = self.financial_auditor.analyze_financial_content(data_content)
            financial_category = ",".join(financial_analysis.get("financial_categories", []))
        
        # 创建审计事件
        event_id = self._generate_unique_event_id()
        
        event = AuditEvent(
            id=event_id,
            timestamp=datetime.datetime.now().isoformat(),
            event_type=event_type.value,
            level=level.value,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            resource=resource,
            action=action,
            details=details,
            success=success,
            risk_score=self._calculate_risk_score(event_type, action, details, success, financial_analysis),
            compliance_flags=financial_analysis.get("compliance_issues", []) if financial_analysis else [],
            financial_category=financial_category,
            data_hash=self._calculate_data_hash(data_content) if data_content else None,
            response_time_ms=response_time_ms,
            error_message=error_message
        )
        
        # 异步记录
        self.executor.submit(self._record_event, event)
        
        # 更新统计
        self._update_monitoring_stats(event)
        
        return event
    
    def _record_event(self, event: AuditEvent):
        """记录事件到日志和数据库"""
        try:
            # 记录到文件日志
            log_message = json.dumps(asdict(event), ensure_ascii=False, separators=(',', ':'))
            
            # 记录到审计文件
            if event.level in ["ERROR", "SECURITY", "COMPLIANCE"]:
                self.logger.error(log_message)
            elif event.level == "WARN":
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)
            
            # 只有重要事件才在主服务器日志中显示
            main_logger = logging.getLogger(__name__)
            if event.level in ["ERROR", "SECURITY", "COMPLIANCE"]:
                main_logger.error(f"🚨 审计安全事件: {event.event_type} - 用户: {event.user_id} - 风险分数: {event.risk_score}")
            elif event.risk_score >= 70:  # 只有极高风险事件才显示在控制台
                main_logger.warning(f"⚠️ 高风险审计事件: {event.event_type} (风险分数: {event.risk_score})")
            elif event.level == "WARN":
                main_logger.debug(f"📋 审计警告: {event.event_type}")  # 使用debug级别，默认不显示
            
            # 记录到数据库 - 添加重试机制
            if self.db_conn:
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with self.db_lock:
                            cursor = self.db_conn.cursor()
                            cursor.execute("""
                                INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                event.id, event.timestamp, event.event_type, event.level,
                                event.user_id, event.session_id, event.ip_address, event.user_agent,
                                event.resource, event.action, json.dumps(event.details),
                                event.success, event.risk_score, 
                                json.dumps(event.compliance_flags) if event.compliance_flags else None,
                                event.financial_category, event.data_hash, 
                                event.response_time_ms, event.error_message
                            ))
                            self.db_conn.commit()
                            break  # 成功则跳出重试循环
                    except sqlite3.IntegrityError as e:
                        if "UNIQUE constraint failed" in str(e) and attempt < max_retries - 1:
                            # 如果是ID冲突，重新生成ID并重试
                            event.id = self._generate_unique_event_id()
                            continue
                        else:
                            # 其他完整性错误或已达到最大重试次数
                            logger.error(f"数据库完整性错误: {e}")
                            break
                    except Exception as e:
                        logger.error(f"数据库操作失败 (尝试 {attempt + 1}): {e}")
                        if attempt == max_retries - 1:
                            break
                        import time
                        time.sleep(0.01)  # 短暂等待后重试
            
            # 高风险事件处理
            if event.risk_score >= 70:
                self._handle_high_risk_event(event)
                
        except Exception as e:
            logger.error(f"记录审计事件失败: {e}")
    
    def _update_monitoring_stats(self, event: AuditEvent):
        """更新监控统计"""
        self.monitoring_stats["total_events"] += 1
        
        if event.risk_score >= 70:
            self.monitoring_stats["high_risk_events"] += 1
        
        if event.financial_category:
            self.monitoring_stats["financial_events"] += 1
        
        if event.compliance_flags:
            self.monitoring_stats["compliance_violations"] += 1
    
    def _handle_high_risk_event(self, event: AuditEvent):
        """处理高风险事件"""
        alert_msg = f"🚨 HIGH RISK: {event.event_type} | User: {event.user_id} | Score: {event.risk_score}"
        print(alert_msg)
        
        # 记录高风险事件到专门日志
        high_risk_log = self.audit_log_path.parent / "high_risk_events.log"
        try:
            with open(high_risk_log, 'a', encoding='utf-8') as f:
                f.write(f"{event.timestamp} | {alert_msg} | Details: {json.dumps(event.details)}\n")
        except Exception as e:
            logger.error(f"记录高风险事件失败: {e}")
    
    def generate_audit_report(self, hours: int = 24) -> Dict:
        """生成审计报告"""
        if not self.db_conn:
            return {"error": "审计数据库不可用"}
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                
                # 基础统计
                cursor.execute("""
                    SELECT COUNT(*) FROM audit_events 
                    WHERE timestamp >= ?
                """, (cutoff_time.isoformat(),))
                total_events = cursor.fetchone()[0]
                
                # 风险分布
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN risk_score >= 70 THEN 1 ELSE 0 END) as high_risk,
                        SUM(CASE WHEN risk_score >= 40 AND risk_score < 70 THEN 1 ELSE 0 END) as medium_risk,
                        SUM(CASE WHEN risk_score < 40 THEN 1 ELSE 0 END) as low_risk
                    FROM audit_events 
                    WHERE timestamp >= ?
                """, (cutoff_time.isoformat(),))
                risk_stats = cursor.fetchone()
                
                # 事件类型统计
                cursor.execute("""
                    SELECT event_type, COUNT(*) 
                    FROM audit_events 
                    WHERE timestamp >= ?
                    GROUP BY event_type
                """, (cutoff_time.isoformat(),))
                event_types = dict(cursor.fetchall())
                
                # 金融相关事件
                cursor.execute("""
                    SELECT COUNT(*) FROM audit_events 
                    WHERE timestamp >= ? AND financial_category IS NOT NULL
                """, (cutoff_time.isoformat(),))
                financial_events = cursor.fetchone()[0]
                
                # 合规违规
                cursor.execute("""
                    SELECT COUNT(*) FROM audit_events 
                    WHERE timestamp >= ? AND compliance_flags IS NOT NULL AND compliance_flags != '[]'
                """, (cutoff_time.isoformat(),))
                compliance_violations = cursor.fetchone()[0]
                
                report = {
                    "report_period": f"最近{hours}小时",
                    "generation_time": datetime.datetime.now().isoformat(),
                    "summary": {
                        "total_events": total_events,
                        "high_risk_events": risk_stats[0] if risk_stats else 0,
                        "medium_risk_events": risk_stats[1] if risk_stats else 0,
                        "low_risk_events": risk_stats[2] if risk_stats else 0,
                        "financial_events": financial_events,
                        "compliance_violations": compliance_violations
                    },
                    "event_types": event_types,
                    "monitoring_stats": self.monitoring_stats,
                    "system_health": self._assess_system_health(risk_stats[0] if risk_stats else 0, total_events)
                }
                
                return report
                
        except Exception as e:
            logger.error(f"生成审计报告失败: {e}")
            return {"error": f"生成报告失败: {str(e)}"}
    
    def _assess_system_health(self, high_risk_count: int, total_events: int) -> str:
        """评估系统健康状态"""
        if total_events == 0:
            return "正常"
        
        risk_ratio = high_risk_count / total_events
        
        if risk_ratio >= 0.1:
            return "高风险"
        elif risk_ratio >= 0.05:
            return "中等风险"
        else:
            return "正常"
    
    def get_real_time_stats(self) -> Dict:
        """获取实时统计信息"""
        return {
            **self.monitoring_stats,
            "uptime_hours": (datetime.datetime.now() - self.monitoring_stats["session_start_time"]).total_seconds() / 3600
        }
    
    def close(self):
        """关闭审计系统"""
        if self.db_conn:
            self.db_conn.close()
        self.executor.shutdown(wait=True)
        logger.info("🔍 审计系统已关闭")


# 全局审计系统实例
_audit_system: Optional[ServerAuditSystem] = None


def get_audit_system() -> ServerAuditSystem:
    """获取全局审计系统实例"""
    global _audit_system
    if _audit_system is None:
        _audit_system = ServerAuditSystem()
    return _audit_system


def log_server_event(event_type: AuditEventType, 
                    level: AuditLevel,
                    action: str,
                    **kwargs):
    """便捷的服务器事件记录函数"""
    audit_system = get_audit_system()
    return audit_system.log_event(event_type, level, action, **kwargs)


# 装饰器用于自动审计函数调用
def audit_api_call(event_type: AuditEventType, action: str = None):
    """API调用审计装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.datetime.now()
            success = True
            error_msg = None
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                response_time = int((datetime.datetime.now() - start_time).total_seconds() * 1000)
                
                log_server_event(
                    event_type=event_type,
                    level=AuditLevel.ERROR if not success else AuditLevel.INFO,
                    action=action or func.__name__,
                    success=success,
                    response_time_ms=response_time,
                    error_message=error_msg,
                    details={
                        "function": func.__name__,
                        "args_count": len(args),
                        "kwargs_count": len(kwargs)
                    }
                )
        
        return wrapper
    return decorator
