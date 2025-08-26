#!/usr/bin/env python3
"""
Letta服务器审计API路由
提供审计数据查询和报告生成功能
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from letta.server.audit_system import get_audit_system, AuditEventType, AuditLevel
from letta.server.audit_report_generator import LettaAuditReportGenerator
from letta.log import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditStatsResponse(BaseModel):
    """审计统计响应模型"""
    total_events: int
    high_risk_events: int
    medium_risk_events: int
    low_risk_events: int
    failed_events: int
    avg_risk_score: float
    uptime_hours: float
    financial_events: int = 0
    compliance_violations: int = 0


class AuditEventResponse(BaseModel):
    """审计事件响应模型"""
    id: str
    timestamp: str
    event_type: str
    level: str
    user_id: Optional[str]
    action: str
    success: bool
    risk_score: int
    financial_category: Optional[str] = None
    compliance_flags: List[str] = []


@router.get("/stats", response_model=AuditStatsResponse)
async def get_audit_stats():
    """获取审计统计信息"""
    try:
        audit_system = get_audit_system()
        stats = audit_system.get_real_time_stats()
        
        # 从数据库获取更详细的统计
        report_data = audit_system.generate_audit_report(hours=24)
        
        return AuditStatsResponse(
            total_events=stats.get("total_events", 0),
            high_risk_events=stats.get("high_risk_events", 0),
            medium_risk_events=report_data.get("summary", {}).get("medium_risk_events", 0),
            low_risk_events=report_data.get("summary", {}).get("low_risk_events", 0),
            failed_events=0,  # 可以从统计中获取
            avg_risk_score=0.0,  # 可以从统计中计算
            uptime_hours=stats.get("uptime_hours", 0),
            financial_events=stats.get("financial_events", 0),
            compliance_violations=stats.get("compliance_violations", 0)
        )
    except Exception as e:
        logger.error(f"获取审计统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取审计统计失败: {str(e)}")


@router.get("/report")
async def generate_audit_report(
    hours: int = Query(24, description="报告时间范围(小时)"),
    format: str = Query("html", description="输出格式(html/json)"),
    include_financial: bool = Query(True, description="包含金融分析")
):
    """生成审计报告"""
    try:
        if format not in ["html", "json", "csv"]:
            raise HTTPException(status_code=400, detail="不支持的格式，支持: html, json, csv")
        
        # 使用审计数据库路径
        db_path = "./logs/letta_audit.db"
        if not os.path.exists(db_path):
            raise HTTPException(status_code=404, detail="审计数据库不存在")
        
        generator = LettaAuditReportGenerator(db_path)
        report_path = generator.generate_comprehensive_report(
            hours=hours, 
            output_format=format,
            include_financial_analysis=include_financial
        )
        
        if format == "html":
            return FileResponse(
                report_path, 
                media_type="text/html",
                filename=f"letta_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            )
        else:
            return FileResponse(
                report_path,
                media_type="application/octet-stream",
                filename=os.path.basename(report_path)
            )
            
    except Exception as e:
        logger.error(f"生成审计报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成审计报告失败: {str(e)}")


@router.get("/compliance")
async def generate_compliance_report(
    hours: int = Query(24, description="报告时间范围(小时)")
):
    """生成合规性报告"""
    try:
        db_path = "./logs/letta_audit.db"
        if not os.path.exists(db_path):
            raise HTTPException(status_code=404, detail="审计数据库不存在")
        
        generator = LettaAuditReportGenerator(db_path)
        report_path = generator.generate_compliance_report(hours=hours)
        
        return FileResponse(
            report_path,
            media_type="text/html",
            filename=f"letta_compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
        
    except Exception as e:
        logger.error(f"生成合规报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成合规报告失败: {str(e)}")


@router.get("/events")
async def get_audit_events(
    limit: int = Query(50, description="返回事件数量限制"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    risk_level: Optional[str] = Query(None, description="风险等级过滤(high/medium/low)"),
    user_id: Optional[str] = Query(None, description="用户ID过滤"),
    hours: int = Query(24, description="时间范围(小时)")
):
    """获取审计事件列表"""
    try:
        audit_system = get_audit_system()
        
        # 简单实现 - 可以扩展为更复杂的查询
        if not audit_system.db_conn:
            raise HTTPException(status_code=500, detail="审计数据库不可用")
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 构建查询条件
        conditions = ["timestamp >= ?"]
        params = [cutoff_time.isoformat()]
        
        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        
        if risk_level:
            if risk_level == "high":
                conditions.append("risk_score >= 70")
            elif risk_level == "medium":
                conditions.append("risk_score >= 40 AND risk_score < 70")
            elif risk_level == "low":
                conditions.append("risk_score < 40")
        
        query = f"""
            SELECT id, timestamp, event_type, level, user_id, action, success, 
                   risk_score, financial_category, compliance_flags
            FROM audit_events 
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC 
            LIMIT ?
        """
        params.append(limit)
        
        with audit_system.db_lock:
            cursor = audit_system.db_conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
        
        events = []
        for row in rows:
            events.append(AuditEventResponse(
                id=row[0],
                timestamp=row[1],
                event_type=row[2],
                level=row[3],
                user_id=row[4],
                action=row[5],
                success=bool(row[6]),
                risk_score=row[7],
                financial_category=row[8],
                compliance_flags=eval(row[9]) if row[9] and row[9] != '[]' else []
            ))
        
        return events
        
    except Exception as e:
        logger.error(f"获取审计事件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取审计事件失败: {str(e)}")


@router.get("/dashboard", response_class=HTMLResponse)
async def audit_dashboard():
    """审计仪表板页面"""
    dashboard_html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Letta服务器审计仪表板</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f7fa; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-left: 4px solid #3498db; }
        .stat-card.high-risk { border-left-color: #e74c3c; }
        .stat-card.medium-risk { border-left-color: #f39c12; }
        .stat-card.low-risk { border-left-color: #27ae60; }
        .stat-value { font-size: 2.5em; font-weight: bold; color: #2c3e50; margin: 0; }
        .stat-label { color: #7f8c8d; margin: 10px 0 0 0; font-weight: 600; }
        .actions { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .btn { display: inline-block; padding: 12px 24px; margin: 5px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; font-weight: 600; }
        .btn:hover { background: #2980b9; }
        .btn.danger { background: #e74c3c; }
        .btn.warning { background: #f39c12; }
        .btn.success { background: #27ae60; }
        .loading { text-align: center; color: #7f8c8d; margin: 20px 0; }
        .refresh { float: right; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Letta服务器审计仪表板</h1>
            <p>实时监控金融文档RAG系统的安全性和合规性</p>
            <button class="btn refresh" onclick="loadStats()">🔄 刷新数据</button>
        </div>
        
        <div class="stats-grid" id="stats-grid">
            <div class="loading">正在加载统计数据...</div>
        </div>
        
        <div class="actions">
            <h3>📊 报告生成</h3>
            <a href="/audit/report?format=html&hours=24" class="btn" target="_blank">📈 生成24小时审计报告 (HTML)</a>
            <a href="/audit/report?format=json&hours=24" class="btn" target="_blank">📄 生成24小时审计报告 (JSON)</a>
            <a href="/audit/compliance?hours=24" class="btn warning" target="_blank">⚖️ 生成合规性报告</a>
            <a href="/audit/events?limit=100" class="btn success" target="_blank">📋 查看最近事件 (API)</a>
        </div>
        
        <div class="actions">
            <h3>⚙️ 快速操作</h3>
            <a href="/audit/report?format=html&hours=1" class="btn" target="_blank">🕐 最近1小时报告</a>
            <a href="/audit/report?format=html&hours=168" class="btn" target="_blank">📅 最近7天报告</a>
            <a href="/audit/events?risk_level=high&hours=24" class="btn danger" target="_blank">🚨 高风险事件</a>
        </div>
    </div>
    
    <script>
        async function loadStats() {
            try {
                const response = await fetch('/audit/stats');
                const stats = await response.json();
                
                const statsGrid = document.getElementById('stats-grid');
                statsGrid.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_events}</div>
                        <div class="stat-label">总事件数</div>
                    </div>
                    <div class="stat-card high-risk">
                        <div class="stat-value">${stats.high_risk_events}</div>
                        <div class="stat-label">高风险事件</div>
                    </div>
                    <div class="stat-card medium-risk">
                        <div class="stat-value">${stats.medium_risk_events}</div>
                        <div class="stat-label">中风险事件</div>
                    </div>
                    <div class="stat-card low-risk">
                        <div class="stat-value">${stats.low_risk_events}</div>
                        <div class="stat-label">低风险事件</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.financial_events}</div>
                        <div class="stat-label">金融相关事件</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.compliance_violations}</div>
                        <div class="stat-label">合规违规</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.uptime_hours.toFixed(1)}h</div>
                        <div class="stat-label">运行时长</div>
                    </div>
                `;
                
                // 如果有高风险事件，添加警告
                if (stats.high_risk_events > 0) {
                    const warning = document.createElement('div');
                    warning.style.cssText = 'background: #ffebee; color: #c62828; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f44336;';
                    warning.innerHTML = `<strong>⚠️ 安全警告:</strong> 检测到 ${stats.high_risk_events} 个高风险事件，建议立即查看详情！`;
                    statsGrid.parentNode.insertBefore(warning, statsGrid.nextSibling);
                }
                
            } catch (error) {
                document.getElementById('stats-grid').innerHTML = 
                    '<div style="color: #e74c3c; text-align: center;">加载统计数据失败: ' + error.message + '</div>';
            }
        }
        
        // 页面加载时自动加载统计数据
        loadStats();
        
        // 每30秒自动刷新
        setInterval(loadStats, 30000);
    </script>
</body>
</html>
    """
    return dashboard_html


@router.post("/event")
async def log_audit_event(
    event_type: str,
    action: str,
    level: str = "INFO",
    user_id: Optional[str] = None,
    details: Optional[Dict] = None
):
    """手动记录审计事件 (用于测试)"""
    try:
        from letta.server.audit_system import log_server_event, AuditEventType, AuditLevel
        
        # 验证参数
        try:
            event_type_enum = AuditEventType(event_type)
            level_enum = AuditLevel(level)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"无效的参数: {str(e)}")
        
        event = log_server_event(
            event_type=event_type_enum,
            level=level_enum,
            action=action,
            user_id=user_id,
            details=details or {}
        )
        
        return {"message": "审计事件已记录", "event_id": event.id}
        
    except Exception as e:
        logger.error(f"记录审计事件失败: {e}")
        raise HTTPException(status_code=500, detail=f"记录审计事件失败: {str(e)}")
