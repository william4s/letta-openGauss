#!/usr/bin/env python3
"""
Letta RAG系统安全审计机制
记录用户行为、文档访问、系统操作等审计日志
"""

import os
import json
import hashlib
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging


class AuditLevel(Enum):
    """审计级别"""
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    SECURITY = "SECURITY"


class AuditEventType(Enum):
    """审计事件类型"""
    USER_SESSION_START = "USER_SESSION_START"
    USER_SESSION_END = "USER_SESSION_END"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_ACCESS = "DOCUMENT_ACCESS"
    QUERY_EXECUTION = "QUERY_EXECUTION"
    RAG_SEARCH = "RAG_SEARCH"
    AGENT_CREATION = "AGENT_CREATION"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    DATA_EMBEDDING = "DATA_EMBEDDING"
    MEMORY_ACCESS = "MEMORY_ACCESS"
    SENSITIVE_DATA_ACCESS = "SENSITIVE_DATA_ACCESS"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    AUTHENTICATION = "AUTHENTICATION"
    PERMISSION_CHECK = "PERMISSION_CHECK"


@dataclass
class AuditEvent:
    """审计事件数据结构"""
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
    data_hash: Optional[str] = None
    response_time_ms: Optional[int] = None


class SecurityAuditor:
    """安全审计器"""
    
    def __init__(self, 
                 audit_log_path: str = "./logs/security_audit.log",
                 enable_db_logging: bool = True,
                 enable_file_logging: bool = True,
                 enable_console_output: bool = True):
        self.audit_log_path = Path(audit_log_path)
        self.enable_db_logging = enable_db_logging
        self.enable_file_logging = enable_file_logging
        self.enable_console_output = enable_console_output
        
        # 创建日志目录
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 设置日志记录器
        self._setup_logger()
        
        # 敏感词检测列表
        self.sensitive_keywords = [
            "密码", "身份证", "银行卡", "信用卡", "手机号", "邮箱", "社会保障号",
            "password", "id_card", "bank_card", "credit_card", "phone", "email", "ssn",
            "账号", "账户", "pin", "密钥", "key", "secret", "token",
            "医疗记录", "病历", "诊断", "处方", "medical", "diagnosis", "prescription"
        ]
        
        # 高风险操作模式
        self.high_risk_patterns = [
            "批量下载", "数据导出", "权限提升", "系统配置",
            "bulk_download", "data_export", "privilege_escalation", "system_config"
        ]
    
    def _setup_logger(self):
        """设置日志记录器"""
        self.logger = logging.getLogger("SecurityAudit")
        self.logger.setLevel(logging.INFO)
        
        # 清除现有的处理器
        self.logger.handlers.clear()
        
        if self.enable_file_logging:
            # 文件处理器
            file_handler = logging.FileHandler(self.audit_log_path, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)
        
        if self.enable_console_output:
            # 控制台处理器（用于开发调试）
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('🔍 AUDIT | %(levelname)s | %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def _calculate_data_hash(self, data: str) -> str:
        """计算数据哈希值用于完整性校验"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    
    def _detect_sensitive_data(self, text: str) -> bool:
        """检测敏感数据"""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.sensitive_keywords)
    
    def _detect_high_risk_pattern(self, action: str, details: Dict) -> bool:
        """检测高风险操作模式"""
        action_lower = action.lower()
        details_str = str(details).lower()
        
        return any(pattern in action_lower or pattern in details_str 
                  for pattern in self.high_risk_patterns)
    
    def _calculate_risk_score(self, event_type: AuditEventType, action: str, details: Dict, success: bool) -> int:
        """计算风险评分 (0-100)"""
        base_scores = {
            AuditEventType.USER_SESSION_START: 10,
            AuditEventType.DOCUMENT_UPLOAD: 30,
            AuditEventType.DOCUMENT_ACCESS: 20,
            AuditEventType.QUERY_EXECUTION: 15,
            AuditEventType.RAG_SEARCH: 15,
            AuditEventType.AGENT_MESSAGE: 10,
            AuditEventType.SENSITIVE_DATA_ACCESS: 80,
            AuditEventType.SYSTEM_ERROR: 40,
            AuditEventType.AUTHENTICATION: 25,
            AuditEventType.PERMISSION_CHECK: 20
        }
        
        score = base_scores.get(event_type, 10)
        
        # 根据详细信息调整分数
        if self._detect_sensitive_data(str(details)):
            score += 30
        
        if self._detect_high_risk_pattern(action, details):
            score += 25
        
        if not success:
            score += 20
        
        if details.get('failed_attempts', 0) > 0:
            score += 20
        
        # 多次重复操作
        if details.get('repeated_operations', 0) > 5:
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
                  response_time_ms: Optional[int] = None):
        """记录审计事件"""
        
        if details is None:
            details = {}
        
        # 创建审计事件
        event = AuditEvent(
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
            risk_score=self._calculate_risk_score(event_type, action, details, success),
            data_hash=self._calculate_data_hash(data_content) if data_content else None,
            response_time_ms=response_time_ms
        )
        
        # 记录到日志
        log_message = self._format_log_message(event)
        
        if level == AuditLevel.ERROR or level == AuditLevel.SECURITY:
            self.logger.error(log_message)
        elif level == AuditLevel.WARN:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
        
        # 如果是高风险事件，额外处理
        if event.risk_score >= 70:
            self._handle_high_risk_event(event)
        
        return event
    
    def _format_log_message(self, event: AuditEvent) -> str:
        """格式化日志消息"""
        return json.dumps(asdict(event), ensure_ascii=False, separators=(',', ':'))
    
    def _handle_high_risk_event(self, event: AuditEvent):
        """处理高风险事件"""
        alert_msg = f"🚨 HIGH RISK EVENT: {event.event_type} | User: {event.user_id} | Risk Score: {event.risk_score}"
        print(alert_msg)
        
        # 写入高风险事件专门的日志
        high_risk_log = self.audit_log_path.parent / "high_risk_events.log"
        with open(high_risk_log, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now().isoformat()} | {alert_msg}\n")
        
        # 这里可以添加：
        # 1. 发送告警通知
        # 2. 临时锁定用户
        # 3. 记录到安全事件数据库
        # 4. 自动化响应措施
    
    def log_user_session(self, user_id: str, action: str, session_id: str = None, ip_address: str = None):
        """记录用户会话"""
        self.log_event(
            event_type=AuditEventType.USER_SESSION_START if action == "login" else AuditEventType.USER_SESSION_END,
            level=AuditLevel.INFO,
            action=action,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            details={"session_action": action}
        )
    
    def log_document_operation(self, user_id: str, document_name: str, operation: str, 
                             session_id: str = None, file_size: int = None):
        """记录文档操作"""
        self.log_event(
            event_type=AuditEventType.DOCUMENT_UPLOAD if operation == "upload" else AuditEventType.DOCUMENT_ACCESS,
            level=AuditLevel.INFO,
            action=f"document_{operation}",
            user_id=user_id,
            session_id=session_id,
            resource=document_name,
            details={
                "operation": operation, 
                "document": document_name,
                "file_size": file_size
            }
        )
    
    def log_rag_search(self, user_id: str, query: str, results_count: int, 
                      session_id: str = None, response_time_ms: int = None):
        """记录RAG搜索"""
        is_sensitive = self._detect_sensitive_data(query)
        level = AuditLevel.SECURITY if is_sensitive else AuditLevel.INFO
        
        self.log_event(
            event_type=AuditEventType.RAG_SEARCH,
            level=level,
            action="rag_search",
            user_id=user_id,
            session_id=session_id,
            details={
                "query_length": len(query),
                "results_count": results_count,
                "contains_sensitive": is_sensitive,
                "query_hash": self._calculate_data_hash(query)
            },
            data_content=query,
            response_time_ms=response_time_ms
        )
    
    def log_agent_interaction(self, user_id: str, agent_id: str, message_type: str, 
                            content_length: int, session_id: str = None):
        """记录智能体交互"""
        self.log_event(
            event_type=AuditEventType.AGENT_MESSAGE,
            level=AuditLevel.INFO,
            action=f"agent_{message_type}",
            user_id=user_id,
            session_id=session_id,
            resource=agent_id,
            details={
                "agent_id": agent_id,
                "message_type": message_type,
                "content_length": content_length
            }
        )
    
    def log_embedding_generation(self, user_id: str, text_chunks: List[str], session_id: str = None):
        """记录向量生成"""
        total_chars = sum(len(chunk) for chunk in text_chunks)
        has_sensitive = any(self._detect_sensitive_data(chunk) for chunk in text_chunks)
        
        self.log_event(
            event_type=AuditEventType.DATA_EMBEDDING,
            level=AuditLevel.SECURITY if has_sensitive else AuditLevel.INFO,
            action="generate_embeddings",
            user_id=user_id,
            session_id=session_id,
            details={
                "chunks_count": len(text_chunks),
                "total_characters": total_chars,
                "contains_sensitive": has_sensitive
            }
        )
    
    def log_system_error(self, user_id: str, error_type: str, error_message: str, 
                        session_id: str = None, context: Dict = None):
        """记录系统错误"""
        self.log_event(
            event_type=AuditEventType.SYSTEM_ERROR,
            level=AuditLevel.ERROR,
            action="system_error",
            user_id=user_id,
            session_id=session_id,
            details={
                "error_type": error_type,
                "error_message": error_message[:500],  # 限制错误消息长度
                "context": context or {}
            },
            success=False
        )
    
    def generate_audit_report(self, hours: int = 24) -> Dict:
        """生成审计报告"""
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        try:
            with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {"error": "审计日志文件不存在"}
        
        events = []
        for line in lines:
            try:
                # 解析日志行格式: timestamp | level | json_data
                parts = line.strip().split(' | ', 2)
                if len(parts) >= 3:
                    event_data = json.loads(parts[2])
                    event_time = datetime.datetime.fromisoformat(event_data['timestamp'])
                    
                    if event_time >= cutoff_time:
                        events.append(event_data)
            except (json.JSONDecodeError, KeyError, ValueError, IndexError):
                continue
        
        # 统计分析
        report = {
            "report_period": f"最近{hours}小时",
            "generation_time": datetime.datetime.now().isoformat(),
            "total_events": len(events),
            "event_types": {},
            "risk_distribution": {"low": 0, "medium": 0, "high": 0},
            "users": set(),
            "high_risk_events": [],
            "error_events": [],
            "sensitive_data_access": 0,
            "system_health": "正常"
        }
        
        error_count = 0
        high_risk_count = 0
        
        for event in events:
            # 事件类型统计
            event_type = event['event_type']
            report["event_types"][event_type] = report["event_types"].get(event_type, 0) + 1
            
            # 风险分布
            risk_score = event.get('risk_score', 0)
            if risk_score >= 70:
                report["risk_distribution"]["high"] += 1
                report["high_risk_events"].append(event)
                high_risk_count += 1
            elif risk_score >= 40:
                report["risk_distribution"]["medium"] += 1
            else:
                report["risk_distribution"]["low"] += 1
            
            # 错误事件
            if not event.get('success', True) or event.get('level') == 'ERROR':
                report["error_events"].append(event)
                error_count += 1
            
            # 敏感数据访问
            if event.get('details', {}).get('contains_sensitive', False):
                report["sensitive_data_access"] += 1
            
            # 用户统计
            if event.get('user_id'):
                report["users"].add(event['user_id'])
        
        # 系统健康评估
        if error_count > 10 or high_risk_count > 5:
            report["system_health"] = "需要关注"
        if error_count > 50 or high_risk_count > 20:
            report["system_health"] = "异常"
        
        report["unique_users"] = len(report["users"])
        report["users"] = list(report["users"])
        report["error_count"] = error_count
        report["high_risk_count"] = high_risk_count
        
        return report
    
    def get_user_activity_summary(self, user_id: str, hours: int = 24) -> Dict:
        """获取特定用户的活动摘要"""
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        try:
            with open(self.audit_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {"error": "审计日志文件不存在"}
        
        user_events = []
        for line in lines:
            try:
                parts = line.strip().split(' | ', 2)
                if len(parts) >= 3:
                    event_data = json.loads(parts[2])
                    event_time = datetime.datetime.fromisoformat(event_data['timestamp'])
                    
                    if (event_time >= cutoff_time and 
                        event_data.get('user_id') == user_id):
                        user_events.append(event_data)
            except (json.JSONDecodeError, KeyError, ValueError, IndexError):
                continue
        
        if not user_events:
            return {"message": f"用户 {user_id} 在最近{hours}小时内无活动记录"}
        
        summary = {
            "user_id": user_id,
            "period": f"最近{hours}小时",
            "total_activities": len(user_events),
            "activity_types": {},
            "risk_events": [],
            "documents_accessed": set(),
            "queries_count": 0,
            "last_activity": user_events[-1]['timestamp'] if user_events else None
        }
        
        for event in user_events:
            event_type = event['event_type']
            summary["activity_types"][event_type] = summary["activity_types"].get(event_type, 0) + 1
            
            if event.get('risk_score', 0) >= 50:
                summary["risk_events"].append(event)
            
            if event_type in ['DOCUMENT_ACCESS', 'DOCUMENT_UPLOAD']:
                if event.get('resource'):
                    summary["documents_accessed"].add(event['resource'])
            
            if event_type in ['QUERY_EXECUTION', 'RAG_SEARCH']:
                summary["queries_count"] += 1
        
        summary["documents_accessed"] = list(summary["documents_accessed"])
        summary["unique_documents"] = len(summary["documents_accessed"])
        
        return summary


# 全局审计器实例
_global_auditor = None

def get_auditor() -> SecurityAuditor:
    """获取全局审计器实例"""
    global _global_auditor
    if _global_auditor is None:
        _global_auditor = SecurityAuditor()
    return _global_auditor


def log_event(*args, **kwargs):
    """快捷函数：记录审计事件"""
    return get_auditor().log_event(*args, **kwargs)


def generate_audit_report(hours: int = 24) -> Dict:
    """快捷函数：生成审计报告"""
    return get_auditor().generate_audit_report(hours)
