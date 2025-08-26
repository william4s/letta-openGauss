#!/usr/bin/env python3
"""
Letta服务器审计报告生成器
专门为金融文档RAG系统生成详细的审计报告和合规性分析
"""

import os
import json
import csv
import sqlite3
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import argparse

from letta.log import get_logger

logger = get_logger(__name__)


class LettaAuditReportGenerator:
    """Letta服务器审计报告生成器"""
    
    def __init__(self, audit_db_path: str = "./logs/letta_audit.db"):
        self.audit_db_path = Path(audit_db_path)
        self.report_dir = Path("./reports")
        self.report_dir.mkdir(exist_ok=True)
        
        if not self.audit_db_path.exists():
            raise FileNotFoundError(f"审计数据库不存在: {audit_db_path}")
    
    def generate_comprehensive_report(self, 
                                    hours: int = 24, 
                                    output_format: str = "html",
                                    include_financial_analysis: bool = True) -> str:
        """生成综合审计报告"""
        logger.info(f"📊 生成最近{hours}小时的Letta服务器审计报告...")
        
        # 收集数据
        report_data = self._collect_audit_data(hours)
        
        if include_financial_analysis:
            financial_data = self._analyze_financial_activities(hours)
            report_data["financial_analysis"] = financial_data
        
        # 生成报告
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format.lower() == "html":
            filename = f"letta_audit_report_{timestamp}.html"
            filepath = self.report_dir / filename
            self._generate_html_report(report_data, filepath)
        elif output_format.lower() == "json":
            filename = f"letta_audit_report_{timestamp}.json"
            filepath = self.report_dir / filename
            self._generate_json_report(report_data, filepath)
        elif output_format.lower() == "csv":
            filename = f"letta_audit_report_{timestamp}.csv"
            filepath = self.report_dir / filename
            self._generate_csv_report(report_data, filepath)
        else:
            raise ValueError(f"不支持的输出格式: {output_format}")
        
        logger.info(f"✅ 审计报告已生成: {filepath}")
        return str(filepath)
    
    def _collect_audit_data(self, hours: int) -> Dict:
        """收集审计数据"""
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        with sqlite3.connect(str(self.audit_db_path)) as conn:
            cursor = conn.cursor()
            
            # 基础统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_events,
                    SUM(CASE WHEN risk_score >= 70 THEN 1 ELSE 0 END) as high_risk,
                    SUM(CASE WHEN risk_score >= 40 AND risk_score < 70 THEN 1 ELSE 0 END) as medium_risk,
                    SUM(CASE WHEN risk_score < 40 THEN 1 ELSE 0 END) as low_risk,
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_events,
                    AVG(CAST(risk_score as FLOAT)) as avg_risk_score,
                    AVG(CAST(response_time_ms as FLOAT)) as avg_response_time
                FROM audit_events 
                WHERE timestamp >= ?
            """, (cutoff_time.isoformat(),))
            
            basic_stats = cursor.fetchone()
            
            # 事件类型分布
            cursor.execute("""
                SELECT event_type, COUNT(*), AVG(CAST(risk_score as FLOAT))
                FROM audit_events 
                WHERE timestamp >= ?
                GROUP BY event_type
                ORDER BY COUNT(*) DESC
            """, (cutoff_time.isoformat(),))
            
            event_types = cursor.fetchall()
            
            # 用户活动统计
            cursor.execute("""
                SELECT 
                    user_id,
                    COUNT(*) as event_count,
                    AVG(CAST(risk_score as FLOAT)) as avg_risk,
                    SUM(CASE WHEN risk_score >= 70 THEN 1 ELSE 0 END) as high_risk_count,
                    COUNT(DISTINCT session_id) as session_count
                FROM audit_events 
                WHERE timestamp >= ? AND user_id IS NOT NULL
                GROUP BY user_id
                ORDER BY event_count DESC
            """, (cutoff_time.isoformat(),))
            
            user_stats = cursor.fetchall()
            
            # 时间分布
            cursor.execute("""
                SELECT 
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as event_count,
                    AVG(CAST(risk_score as FLOAT)) as avg_risk
                FROM audit_events 
                WHERE timestamp >= ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY hour
            """, (cutoff_time.isoformat(),))
            
            hourly_distribution = cursor.fetchall()
            
            # 高风险事件详情
            cursor.execute("""
                SELECT id, timestamp, event_type, user_id, action, risk_score, details, error_message
                FROM audit_events 
                WHERE timestamp >= ? AND risk_score >= 70
                ORDER BY risk_score DESC, timestamp DESC
                LIMIT 20
            """, (cutoff_time.isoformat(),))
            
            high_risk_events = cursor.fetchall()
            
            # 合规违规事件
            cursor.execute("""
                SELECT id, timestamp, event_type, user_id, action, compliance_flags, financial_category
                FROM audit_events 
                WHERE timestamp >= ? AND compliance_flags IS NOT NULL 
                  AND compliance_flags != '[]' AND compliance_flags != 'null'
                ORDER BY timestamp DESC
                LIMIT 20
            """, (cutoff_time.isoformat(),))
            
            compliance_violations = cursor.fetchall()
            
            # 错误统计
            cursor.execute("""
                SELECT 
                    event_type,
                    COUNT(*) as error_count,
                    GROUP_CONCAT(DISTINCT error_message) as error_messages
                FROM audit_events 
                WHERE timestamp >= ? AND success = 0
                GROUP BY event_type
                ORDER BY error_count DESC
            """, (cutoff_time.isoformat(),))
            
            error_stats = cursor.fetchall()
        
        return {
            "report_period": f"最近{hours}小时",
            "generation_time": datetime.datetime.now().isoformat(),
            "basic_stats": {
                "total_events": basic_stats[0] or 0,
                "high_risk_events": basic_stats[1] or 0,
                "medium_risk_events": basic_stats[2] or 0,
                "low_risk_events": basic_stats[3] or 0,
                "failed_events": basic_stats[4] or 0,
                "avg_risk_score": round(basic_stats[5] or 0, 2),
                "avg_response_time": round(basic_stats[6] or 0, 2)
            },
            "event_types": [
                {"type": row[0], "count": row[1], "avg_risk": round(row[2] or 0, 2)}
                for row in event_types
            ],
            "user_stats": [
                {
                    "user_id": row[0], 
                    "event_count": row[1], 
                    "avg_risk": round(row[2] or 0, 2),
                    "high_risk_count": row[3] or 0,
                    "session_count": row[4] or 0
                }
                for row in user_stats
            ],
            "hourly_distribution": [
                {"hour": int(row[0]), "count": row[1], "avg_risk": round(row[2] or 0, 2)}
                for row in hourly_distribution
            ],
            "high_risk_events": [
                {
                    "id": row[0], "timestamp": row[1], "event_type": row[2],
                    "user_id": row[3], "action": row[4], "risk_score": row[5],
                    "details": json.loads(row[6]) if row[6] else {},
                    "error_message": row[7]
                }
                for row in high_risk_events
            ],
            "compliance_violations": [
                {
                    "id": row[0], "timestamp": row[1], "event_type": row[2],
                    "user_id": row[3], "action": row[4], 
                    "compliance_flags": json.loads(row[5]) if row[5] else [],
                    "financial_category": row[6]
                }
                for row in compliance_violations
            ],
            "error_stats": [
                {"event_type": row[0], "count": row[1], "messages": row[2]}
                for row in error_stats
            ]
        }
    
    def _analyze_financial_activities(self, hours: int) -> Dict:
        """分析金融相关活动"""
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        with sqlite3.connect(str(self.audit_db_path)) as conn:
            cursor = conn.cursor()
            
            # 金融文档访问统计
            cursor.execute("""
                SELECT 
                    financial_category,
                    COUNT(*) as access_count,
                    AVG(CAST(risk_score as FLOAT)) as avg_risk,
                    COUNT(DISTINCT user_id) as unique_users
                FROM audit_events 
                WHERE timestamp >= ? AND financial_category IS NOT NULL
                GROUP BY financial_category
                ORDER BY access_count DESC
            """, (cutoff_time.isoformat(),))
            
            financial_categories = cursor.fetchall()
            
            # RAG查询分析
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_queries,
                    AVG(CAST(response_time_ms as FLOAT)) as avg_response_time,
                    SUM(CASE WHEN financial_category IS NOT NULL THEN 1 ELSE 0 END) as financial_queries,
                    SUM(CASE WHEN risk_score >= 50 THEN 1 ELSE 0 END) as sensitive_queries
                FROM audit_events 
                WHERE timestamp >= ? AND event_type IN ('RAG_QUERY', 'RAG_SEARCH', 'PRODUCT_INFO_QUERY', 'RISK_ASSESSMENT_QUERY')
            """, (cutoff_time.isoformat(),))
            
            query_stats = cursor.fetchone()
            
            # 理财产品相关查询
            cursor.execute("""
                SELECT action, COUNT(*) as count, AVG(CAST(risk_score as FLOAT)) as avg_risk
                FROM audit_events 
                WHERE timestamp >= ? AND (
                    financial_category LIKE '%product_info%' OR
                    action LIKE '%product%' OR 
                    action LIKE '%理财%'
                )
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff_time.isoformat(),))
            
            product_queries = cursor.fetchall()
            
            # 风险相关查询
            cursor.execute("""
                SELECT action, COUNT(*) as count, AVG(CAST(risk_score as FLOAT)) as avg_risk
                FROM audit_events 
                WHERE timestamp >= ? AND (
                    financial_category LIKE '%risk%' OR
                    action LIKE '%risk%' OR 
                    action LIKE '%风险%'
                )
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
            """, (cutoff_time.isoformat(),))
            
            risk_queries = cursor.fetchall()
        
        return {
            "financial_categories": [
                {
                    "category": row[0], "count": row[1], 
                    "avg_risk": round(row[2] or 0, 2), "unique_users": row[3]
                }
                for row in financial_categories
            ],
            "query_statistics": {
                "total_queries": query_stats[0] or 0,
                "avg_response_time": round(query_stats[1] or 0, 2),
                "financial_queries": query_stats[2] or 0,
                "sensitive_queries": query_stats[3] or 0
            },
            "product_queries": [
                {"action": row[0], "count": row[1], "avg_risk": round(row[2] or 0, 2)}
                for row in product_queries
            ],
            "risk_queries": [
                {"action": row[0], "count": row[1], "avg_risk": round(row[2] or 0, 2)}
                for row in risk_queries
            ]
        }
    
    def _generate_html_report(self, data: Dict, filepath: Path):
        """生成HTML格式报告"""
        # 安全地获取数据，避免KeyError
        basic_stats = data.get('basic_stats', {})
        event_types = data.get('event_types', [])
        user_stats = data.get('user_stats', [])
        high_risk_events = data.get('high_risk_events', [])
        compliance_violations = data.get('compliance_violations', [])
        financial_analysis = data.get('financial_analysis', {})
        
        # 构建HTML内容
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Letta服务器审计报告</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background-color: #f5f7fa; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 2.5em; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 40px; }}
        .section h2 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; margin-bottom: 20px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #3498db; }}
        .stat-card.high-risk {{ border-left-color: #e74c3c; }}
        .stat-card.medium-risk {{ border-left-color: #f39c12; }}
        .stat-card.low-risk {{ border-left-color: #27ae60; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; margin: 0; }}
        .stat-label {{ color: #7f8c8d; margin: 5px 0 0 0; }}
        .table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        .table th, .table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .table th {{ background-color: #f1f3f4; font-weight: 600; }}
        .table tr:hover {{ background-color: #f8f9fa; }}
        .risk-high {{ color: #e74c3c; font-weight: bold; }}
        .risk-medium {{ color: #f39c12; font-weight: bold; }}
        .risk-low {{ color: #27ae60; }}
        .alert {{ padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .alert-danger {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .alert-warning {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
        .alert-info {{ background-color: #d1ecf1; color: #0c5460; border: 1px solid #b8daff; }}
        .financial-section {{ background: #fff8dc; border: 2px solid #daa520; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .compliance-violation {{ background: #ffe6e6; border-left: 4px solid #ff4444; padding: 15px; margin: 10px 0; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Letta服务器审计报告</h1>
            <p>金融文档RAG系统安全审计与合规监控</p>
            <p>报告期间: {data.get('report_period', '未知')} | 生成时间: {data.get('generation_time', '未知')[:19]}</p>
        </div>
        
        <div class="content">
            <!-- 概览统计 -->
            <div class="section">
                <h2>📊 概览统计</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{basic_stats.get('total_events', 0)}</div>
                        <div class="stat-label">总事件数</div>
                    </div>
                    <div class="stat-card high-risk">
                        <div class="stat-value">{basic_stats.get('high_risk_events', 0)}</div>
                        <div class="stat-label">高风险事件</div>
                    </div>
                    <div class="stat-card medium-risk">
                        <div class="stat-value">{basic_stats.get('medium_risk_events', 0)}</div>
                        <div class="stat-label">中风险事件</div>
                    </div>
                    <div class="stat-card low-risk">
                        <div class="stat-value">{basic_stats.get('low_risk_events', 0)}</div>
                        <div class="stat-label">低风险事件</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{basic_stats.get('failed_events', 0)}</div>
                        <div class="stat-label">失败事件</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{basic_stats.get('avg_risk_score', 0):.1f}</div>
                        <div class="stat-label">平均风险分数</div>
                    </div>
                </div>"""
        
        # 添加安全警告
        if basic_stats.get('high_risk_events', 0) > 0:
            html_content += f"""
                <div class="alert alert-danger">
                    <strong>⚠️ 安全警告:</strong> 检测到 {basic_stats.get('high_risk_events', 0)} 个高风险事件，需要立即关注！
                </div>"""
        
        # 事件类型分布
        html_content += """
            </div>
            
            <!-- 事件类型分布 -->
            <div class="section">
                <h2>📈 事件类型分布</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>事件类型</th>
                            <th>数量</th>
                            <th>平均风险分数</th>
                            <th>风险评级</th>
                        </tr>
                    </thead>
                    <tbody>"""
        
        for event in event_types:
            avg_risk = event.get('avg_risk', 0)
            risk_class = 'risk-high' if avg_risk >= 70 else 'risk-medium' if avg_risk >= 40 else 'risk-low'
            risk_label = '高风险' if avg_risk >= 70 else '中风险' if avg_risk >= 40 else '低风险'
            
            html_content += f"""
                        <tr>
                            <td>{event.get('type', '未知')}</td>
                            <td>{event.get('count', 0)}</td>
                            <td>{avg_risk:.1f}</td>
                            <td class="{risk_class}">{risk_label}</td>
                        </tr>"""
        
        html_content += """
                    </tbody>
                </table>
            </div>"""
        
        # 金融活动分析
        if financial_analysis:
            query_stats = financial_analysis.get('query_statistics', {})
            product_queries = financial_analysis.get('product_queries', [])
            
            html_content += f"""
            <!-- 金融活动分析 -->
            <div class="section financial-section">
                <h2>💰 金融活动分析</h2>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value">{query_stats.get('total_queries', 0)}</div>
                        <div class="stat-label">总查询数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{query_stats.get('financial_queries', 0)}</div>
                        <div class="stat-label">金融相关查询</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{query_stats.get('sensitive_queries', 0)}</div>
                        <div class="stat-label">敏感查询</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">{query_stats.get('avg_response_time', 0):.1f}ms</div>
                        <div class="stat-label">平均响应时间</div>
                    </div>
                </div>
                
                <h3>📋 理财产品查询统计</h3>
                <table class="table">
                    <thead>
                        <tr><th>查询类型</th><th>次数</th><th>平均风险分数</th></tr>
                    </thead>
                    <tbody>"""
            
            for query in product_queries:
                avg_risk = query.get('avg_risk', 0)
                risk_class = 'risk-high' if avg_risk >= 70 else 'risk-medium' if avg_risk >= 40 else 'risk-low'
                
                html_content += f"""
                        <tr>
                            <td>{query.get('action', '未知')}</td>
                            <td>{query.get('count', 0)}</td>
                            <td class="{risk_class}">{avg_risk:.1f}</td>
                        </tr>"""
            
            html_content += """
                    </tbody>
                </table>
            </div>"""
        
        # 用户活动统计
        html_content += """
            <!-- 用户活动统计 -->
            <div class="section">
                <h2>👥 用户活动统计</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>用户ID</th>
                            <th>事件数</th>
                            <th>平均风险</th>
                            <th>高风险事件</th>
                            <th>会话数</th>
                        </tr>
                    </thead>
                    <tbody>"""
        
        for user in user_stats:
            avg_risk = user.get('avg_risk', 0)
            risk_class = 'risk-high' if avg_risk >= 70 else 'risk-medium' if avg_risk >= 40 else 'risk-low'
            
            html_content += f"""
                        <tr>
                            <td>{user.get('user_id', '未知')}</td>
                            <td>{user.get('event_count', 0)}</td>
                            <td class="{risk_class}">{avg_risk:.1f}</td>
                            <td>{user.get('high_risk_count', 0)}</td>
                            <td>{user.get('session_count', 0)}</td>
                        </tr>"""
        
        html_content += """
                    </tbody>
                </table>
            </div>"""
        
        # 高风险事件详情
        if high_risk_events:
            html_content += """
            <!-- 高风险事件详情 -->
            <div class="section">
                <h2>🚨 高风险事件详情</h2>"""
            
            for event in high_risk_events:
                html_content += f"""
                <div class="alert alert-danger">
                    <strong>{event.get('event_type', '未知')}</strong> (风险分数: {event.get('risk_score', 0)})
                    <br>时间: {event.get('timestamp', '未知')}
                    <br>用户: {event.get('user_id', '未知')}
                    <br>操作: {event.get('action', '未知')}"""
                
                if event.get('error_message'):
                    html_content += f"<br>错误: {event.get('error_message')}"
                
                html_content += "</div>"
            
            html_content += "</div>"
        
        # 合规违规事件
        if compliance_violations:
            html_content += """
            <!-- 合规违规事件 -->
            <div class="section">
                <h2>⚖️ 合规违规事件</h2>"""
            
            for violation in compliance_violations:
                compliance_flags = violation.get('compliance_flags', [])
                flags_str = ', '.join(compliance_flags) if isinstance(compliance_flags, list) else str(compliance_flags)
                
                html_content += f"""
                <div class="compliance-violation">
                    <strong>{violation.get('event_type', '未知')}</strong>
                    <br>时间: {violation.get('timestamp', '未知')}
                    <br>用户: {violation.get('user_id', '未知')}
                    <br>违规项: {flags_str}"""
                
                if violation.get('financial_category'):
                    html_content += f"<br>金融类别: {violation.get('financial_category')}"
                
                html_content += "</div>"
            
            html_content += "</div>"
        
        # 系统健康状态
        total_events = basic_stats.get('total_events', 0)
        high_risk_count = basic_stats.get('high_risk_events', 0)
        
        if high_risk_count == 0:
            health_status = "success"
            health_message = "✅ 系统运行正常，未检测到高风险事件"
        elif high_risk_count < 5:
            health_status = "warning"
            health_message = "⚠️ 系统存在少量风险事件，建议关注"
        else:
            health_status = "danger"
            health_message = "🚨 系统存在较多高风险事件，需要立即处理"
        
        html_content += f"""
            <!-- 系统健康状态 -->
            <div class="section">
                <h2>🏥 系统健康状态</h2>
                <div class="alert alert-{health_status}">
                    {health_message}
                </div>
                
                <h3>📊 风险分布</h3>
                <div>"""
        
        if total_events > 0:
            high_pct = (high_risk_count * 100 / total_events)
            medium_pct = (basic_stats.get('medium_risk_events', 0) * 100 / total_events)
            low_pct = (basic_stats.get('low_risk_events', 0) * 100 / total_events)
            
            html_content += f"""
                    <div>高风险事件: {high_risk_count} ({high_pct:.1f}%)</div>
                    <div>中风险事件: {basic_stats.get('medium_risk_events', 0)} ({medium_pct:.1f}%)</div>
                    <div>低风险事件: {basic_stats.get('low_risk_events', 0)} ({low_pct:.1f}%)</div>"""
        
        html_content += """
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_json_report(self, data: Dict, filepath: Path):
        """生成JSON格式报告"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_csv_report(self, data: Dict, filepath: Path):
        """生成CSV格式报告"""
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # 基础统计
            writer.writerow(["基础统计"])
            writer.writerow(["指标", "数值"])
            for key, value in data["basic_stats"].items():
                writer.writerow([key, value])
            
            writer.writerow([])  # 空行
            
            # 事件类型统计
            writer.writerow(["事件类型统计"])
            writer.writerow(["事件类型", "数量", "平均风险分数"])
            for event in data["event_types"]:
                writer.writerow([event["type"], event["count"], event["avg_risk"]])
            
            writer.writerow([])  # 空行
            
            # 用户统计
            writer.writerow(["用户活动统计"])
            writer.writerow(["用户ID", "事件数", "平均风险", "高风险事件", "会话数"])
            for user in data["user_stats"]:
                writer.writerow([user["user_id"], user["event_count"], user["avg_risk"], 
                               user["high_risk_count"], user["session_count"]])
    
    def generate_compliance_report(self, hours: int = 24) -> str:
        """生成专门的合规性报告"""
        logger.info(f"📋 生成合规性报告...")
        
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        with sqlite3.connect(str(self.audit_db_path)) as conn:
            cursor = conn.cursor()
            
            # 合规相关统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_compliance_events,
                    SUM(CASE WHEN compliance_flags IS NOT NULL AND compliance_flags != '[]' THEN 1 ELSE 0 END) as violation_count,
                    COUNT(DISTINCT user_id) as users_with_violations
                FROM audit_events 
                WHERE timestamp >= ?
            """, (cutoff_time.isoformat(),))
            
            compliance_stats = cursor.fetchone()
            
            # 违规详情
            cursor.execute("""
                SELECT timestamp, event_type, user_id, action, compliance_flags, financial_category, details
                FROM audit_events 
                WHERE timestamp >= ? AND compliance_flags IS NOT NULL AND compliance_flags != '[]'
                ORDER BY timestamp DESC
            """, (cutoff_time.isoformat(),))
            
            violations = cursor.fetchall()
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"letta_compliance_report_{timestamp}.html"
        filepath = self.report_dir / filename
        
        # 生成合规报告HTML
        compliance_html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>Letta服务器合规性报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f7fa; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; text-align: center; margin-bottom: 30px; }}
        .violation {{ background: #fff5f5; border-left: 4px solid #e53e3e; padding: 15px; margin: 15px 0; border-radius: 4px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚖️ Letta服务器合规性报告</h1>
            <p>金融文档RAG系统合规监控 | 报告期间: 最近{hours}小时</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{compliance_stats[0] or 0}</div>
                <div>合规相关事件</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{compliance_stats[1] or 0}</div>
                <div>违规事件</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{compliance_stats[2] or 0}</div>
                <div>涉违规用户</div>
            </div>
        </div>
        
        <h2>违规事件详情</h2>
        """
        
        for violation in violations:
            compliance_flags = json.loads(violation[4]) if violation[4] else []
            details = json.loads(violation[6]) if violation[6] else {}
            
            compliance_html += f"""
        <div class="violation">
            <strong>{violation[1]}</strong> - {violation[0]}<br>
            用户: {violation[2] or "未知"}<br>
            操作: {violation[3]}<br>
            违规项: {', '.join(compliance_flags)}<br>
            金融类别: {violation[5] or "无"}<br>
        </div>
            """
        
        compliance_html += """
        </div>
    </body>
    </html>
        """
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(compliance_html)
        
        logger.info(f"✅ 合规性报告已生成: {filepath}")
        return str(filepath)


def main():
    """命令行工具"""
    parser = argparse.ArgumentParser(description="Letta服务器审计报告生成器")
    parser.add_argument("--hours", type=int, default=24, help="报告时间范围(小时)")
    parser.add_argument("--format", choices=["html", "json", "csv"], default="html", help="输出格式")
    parser.add_argument("--db-path", default="./logs/letta_audit.db", help="审计数据库路径")
    parser.add_argument("--compliance", action="store_true", help="生成合规性报告")
    
    args = parser.parse_args()
    
    try:
        generator = LettaAuditReportGenerator(args.db_path)
        
        if args.compliance:
            report_path = generator.generate_compliance_report(args.hours)
        else:
            report_path = generator.generate_comprehensive_report(args.hours, args.format)
        
        print(f"✅ 报告已生成: {report_path}")
        
    except Exception as e:
        print(f"❌ 生成报告失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
