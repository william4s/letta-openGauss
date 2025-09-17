#!/usr/bin/env python3
"""
综合审计仪表板 - 整合服务器端审计和对话审计
同时显示API操作审计和用户对话审计数据
"""

import os
import json
import sqlite3
import requests
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio

from flask import Flask, render_template, jsonify, request, send_file
from flask_cors import CORS
import plotly.graph_objs as go
import plotly.utils
import pandas as pd

# 添加letta模块路径
import sys
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

try:
    from letta.server.audit_system import get_audit_system, AuditEventType, AuditLevel
    from letta.server.audit_report_generator import LettaAuditReportGenerator
except ImportError:
    print("警告：无法导入服务器端审计模块，将使用REST API方式")
    get_audit_system = None


@dataclass
class ComprehensiveAuditConfig:
    """综合审计仪表板配置"""
    letta_server_url: str = "http://localhost:8283"
    server_audit_db_path: str = "./logs/letta_audit.db"
    rag_audit_db_path: str = "./logs/rag_audit.db"
    refresh_interval: int = 30  # 秒
    max_events_display: int = 100
    enable_real_time: bool = True


class RAGAuditReader:
    """RAG审计数据读取器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_conversation_stats(self, hours: int = 24) -> dict:
        """获取对话统计"""
        if not os.path.exists(self.db_path):
            return {
                "total_conversations": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "avg_sensitivity": 0.0,
                "unique_users": 0
            }
        
        since_time = (datetime.datetime.now().timestamp() - hours * 3600)
        since_iso = datetime.datetime.fromtimestamp(since_time).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high_risk,
                COUNT(CASE WHEN risk_level = 'MEDIUM' THEN 1 END) as medium_risk,
                COUNT(CASE WHEN risk_level = 'LOW' THEN 1 END) as low_risk,
                AVG(sensitive_score) as avg_sensitivity,
                COUNT(DISTINCT user_id) as unique_users
            FROM rag_audit_logs 
            WHERE timestamp > ?
        """, (since_iso,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "total_conversations": result[0] or 0,
            "high_risk": result[1] or 0,
            "medium_risk": result[2] or 0,
            "low_risk": result[3] or 0,
            "avg_sensitivity": round(result[4] or 0, 2),
            "unique_users": result[5] or 0
        }
    
    def get_recent_conversations(self, limit: int = 50, hours: int = 24) -> List[dict]:
        """获取最近对话记录"""
        if not os.path.exists(self.db_path):
            return []
        
        since_time = (datetime.datetime.now().timestamp() - hours * 3600)
        since_iso = datetime.datetime.fromtimestamp(since_time).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                timestamp, session_id, user_id, user_question,
                llm_response, sensitive_score, risk_level,
                keywords_detected, response_time_ms
            FROM rag_audit_logs 
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (since_iso, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        conversations = []
        for row in results:
            conversations.append({
                "timestamp": row[0],
                "session_id": row[1],
                "user_id": row[2],
                "user_question": row[3][:100] + "..." if len(row[3]) > 100 else row[3],
                "llm_response": row[4][:150] + "..." if len(row[4]) > 150 else row[4],
                "sensitive_score": row[5],
                "risk_level": row[6],
                "keywords_detected": json.loads(row[7]) if row[7] else [],
                "response_time_ms": row[8]
            })
        
        return conversations
    
    def get_risk_distribution(self, hours: int = 24) -> dict:
        """获取风险分布"""
        if not os.path.exists(self.db_path):
            return {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        
        since_time = (datetime.datetime.now().timestamp() - hours * 3600)
        since_iso = datetime.datetime.fromtimestamp(since_time).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT risk_level, COUNT(*) as count
            FROM rag_audit_logs 
            WHERE timestamp > ?
            GROUP BY risk_level
        """, (since_iso,))
        
        results = cursor.fetchall()
        conn.close()
        
        distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for row in results:
            distribution[row[0]] = row[1]
        
        return distribution


class ComprehensiveAuditDashboard:
    """综合审计系统仪表板"""
    
    def __init__(self, config: ComprehensiveAuditConfig = None):
        self.config = config or ComprehensiveAuditConfig()
        self.app = Flask(__name__)
        CORS(self.app)
        
        # 尝试直接连接服务器端审计系统
        self.audit_system = None
        if get_audit_system:
            try:
                self.audit_system = get_audit_system()
                print("✅ 直接连接到服务器端审计系统")
            except Exception as e:
                print(f"⚠️ 无法直接连接服务器端审计系统，将使用REST API: {e}")
        
        # RAG审计数据读取器
        self.rag_audit_reader = RAGAuditReader(self.config.rag_audit_db_path)
        print(f"📊 RAG审计数据库: {self.config.rag_audit_db_path}")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置Flask路由"""
        
        @self.app.route('/')
        def dashboard():
            """主仪表板页面"""
            return render_template('comprehensive_audit_dashboard.html')
        
        @self.app.route('/api/server_stats')
        def get_server_stats():
            """获取服务器端审计统计信息"""
            try:
                if self.audit_system:
                    # 直接从审计系统获取
                    stats = self.audit_system.get_real_time_stats()
                else:
                    # 通过REST API获取
                    response = requests.get(
                        f"{self.config.letta_server_url}/v1/audit/stats",
                        timeout=10
                    )
                    if response.status_code == 200:
                        stats = response.json()
                    else:
                        stats = {}
                
                # 统一格式化统计数据
                formatted_stats = {
                    "total_events": stats.get("total_events", 0),
                    "high_risk_events": stats.get("high_risk_events", 0),
                    "medium_risk_events": stats.get("medium_risk_events", 0),
                    "low_risk_events": stats.get("low_risk_events", 0),
                    "failed_events": stats.get("failed_events", 0),
                    "avg_risk_score": stats.get("avg_risk_score", 0.0),
                    "uptime_hours": stats.get("uptime_hours", 0.0),
                    "financial_events": stats.get("financial_events", 0),
                    "compliance_violations": stats.get("compliance_violations", 0),
                    "last_update": datetime.datetime.now().isoformat()
                }
                
                return jsonify(formatted_stats)
                
            except Exception as e:
                return jsonify({"error": f"获取服务器审计统计失败: {str(e)}"}), 500
        
        @self.app.route('/api/conversation_stats')
        def get_conversation_stats():
            """获取对话审计统计信息"""
            try:
                hours = request.args.get('hours', 24, type=int)
                stats = self.rag_audit_reader.get_conversation_stats(hours)
                stats["last_update"] = datetime.datetime.now().isoformat()
                return jsonify(stats)
            except Exception as e:
                return jsonify({"error": f"获取对话审计统计失败: {str(e)}"}), 500
        
        @self.app.route('/api/server_events')
        def get_server_events():
            """获取服务器端审计事件"""
            try:
                limit = request.args.get('limit', 50, type=int)
                
                if self.audit_system and hasattr(self.audit_system, 'get_events'):
                    events = self.audit_system.get_events(limit=limit)
                else:
                    # 通过REST API获取
                    response = requests.get(
                        f"{self.config.letta_server_url}/v1/audit/events",
                        params={'limit': limit},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        events = response.json()
                    else:
                        events = []
                
                # 格式化事件数据
                formatted_events = []
                for event in events:
                    formatted_events.append({
                        "timestamp": event.get("timestamp", ""),
                        "event_type": event.get("event_type", "UNKNOWN"),
                        "level": event.get("level", "INFO"),
                        "action": event.get("action", ""),
                        "user_id": event.get("user_id", "system"),
                        "details": str(event.get("details", {}))[:100] + "..." if len(str(event.get("details", {}))) > 100 else str(event.get("details", {})),
                        "risk_score": event.get("risk_score", 0)
                    })
                
                return jsonify(formatted_events)
                
            except Exception as e:
                return jsonify({"error": f"获取服务器事件失败: {str(e)}"}), 500
        
        @self.app.route('/api/conversations')
        def get_conversations():
            """获取对话审计记录"""
            try:
                limit = request.args.get('limit', 50, type=int)
                hours = request.args.get('hours', 24, type=int)
                conversations = self.rag_audit_reader.get_recent_conversations(limit, hours)
                return jsonify(conversations)
            except Exception as e:
                return jsonify({"error": f"获取对话记录失败: {str(e)}"}), 500
        
        @self.app.route('/api/charts/risk_comparison')
        def get_risk_comparison_chart():
            """获取风险分布对比图表"""
            try:
                hours = request.args.get('hours', 24, type=int)
                
                # 服务器端风险分布
                server_stats = {}
                if self.audit_system:
                    server_stats = self.audit_system.get_real_time_stats()
                
                # RAG对话风险分布
                rag_stats = self.rag_audit_reader.get_risk_distribution(hours)
                
                # 创建对比图表
                fig = go.Figure()
                
                # 服务器端数据
                fig.add_trace(go.Bar(
                    name='服务器审计',
                    x=['高风险', '中风险', '低风险'],
                    y=[
                        server_stats.get('high_risk_events', 0),
                        server_stats.get('medium_risk_events', 0),
                        server_stats.get('low_risk_events', 0)
                    ],
                    marker_color='rgba(158,202,225,0.8)',
                    text=[
                        server_stats.get('high_risk_events', 0),
                        server_stats.get('medium_risk_events', 0),
                        server_stats.get('low_risk_events', 0)
                    ],
                    textposition='auto',
                ))
                
                # RAG对话数据
                fig.add_trace(go.Bar(
                    name='对话审计',
                    x=['高风险', '中风险', '低风险'],
                    y=[rag_stats['HIGH'], rag_stats['MEDIUM'], rag_stats['LOW']],
                    marker_color='rgba(58,200,225,0.8)',
                    text=[rag_stats['HIGH'], rag_stats['MEDIUM'], rag_stats['LOW']],
                    textposition='auto',
                ))
                
                fig.update_layout(
                    title=f'风险分布对比 (最近{hours}小时)',
                    xaxis_title='风险级别',
                    yaxis_title='事件数量',
                    barmode='group',
                    showlegend=True,
                    height=400
                )
                
                graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
                return jsonify({"chart": graphJSON})
                
            except Exception as e:
                return jsonify({"error": f"生成风险对比图表失败: {str(e)}"}), 500
        
        @self.app.route('/api/charts/conversation_timeline')
        def get_conversation_timeline():
            """获取对话时间线图表"""
            try:
                hours = request.args.get('hours', 24, type=int)
                conversations = self.rag_audit_reader.get_recent_conversations(100, hours)
                
                if not conversations:
                    return jsonify({"chart": json.dumps({}, cls=plotly.utils.PlotlyJSONEncoder)})
                
                # 按小时统计
                df = pd.DataFrame(conversations)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp'].dt.floor('H')
                
                hourly_counts = df.groupby(['hour', 'risk_level']).size().unstack(fill_value=0)
                
                fig = go.Figure()
                
                colors = {'HIGH': 'red', 'MEDIUM': 'orange', 'LOW': 'green'}
                
                for risk_level in ['HIGH', 'MEDIUM', 'LOW']:
                    if risk_level in hourly_counts.columns:
                        fig.add_trace(go.Scatter(
                            x=hourly_counts.index,
                            y=hourly_counts[risk_level],
                            mode='lines+markers',
                            name=f'{risk_level}风险',
                            line=dict(color=colors[risk_level]),
                            fill='tonexty' if risk_level != 'HIGH' else 'tozeroy'
                        ))
                
                fig.update_layout(
                    title=f'对话风险时间线 (最近{hours}小时)',
                    xaxis_title='时间',
                    yaxis_title='对话数量',
                    hovermode='x unified',
                    height=400
                )
                
                graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
                return jsonify({"chart": graphJSON})
                
            except Exception as e:
                return jsonify({"error": f"生成对话时间线失败: {str(e)}"}), 500
    
    def create_dashboard_template(self):
        """创建仪表板HTML模板"""
        template_dir = Path(self.app.template_folder or 'templates')
        template_dir.mkdir(exist_ok=True)
        
        template_content = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Letta综合审计仪表板</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        .metric-card { min-height: 120px; }
        .risk-high { border-left: 4px solid #dc3545; }
        .risk-medium { border-left: 4px solid #fd7e14; }
        .risk-low { border-left: 4px solid #20c997; }
        .event-row { border-bottom: 1px solid #eee; padding: 10px 0; }
        .conversation-item { border-left: 3px solid #007bff; padding: 10px; margin: 5px 0; background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container-fluid">
        <nav class="navbar navbar-dark bg-dark mb-4">
            <div class="container-fluid">
                <span class="navbar-brand mb-0 h1">🛡️ Letta综合审计仪表板</span>
                <span class="navbar-text" id="lastUpdate">最后更新: --</span>
            </div>
        </nav>

        <!-- 总览统计 -->
        <div class="row mb-4">
            <div class="col-md-6">
                <h4>🖥️ 服务器审计统计</h4>
                <div class="row" id="serverStats">
                    <!-- 服务器统计卡片 -->
                </div>
            </div>
            <div class="col-md-6">
                <h4>💬 对话审计统计</h4>
                <div class="row" id="conversationStats">
                    <!-- 对话统计卡片 -->
                </div>
            </div>
        </div>

        <!-- 图表区域 -->
        <div class="row mb-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">📊 风险分布对比</div>
                    <div class="card-body">
                        <div id="riskComparisonChart" style="height: 400px;"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">📈 对话风险时间线</div>
                    <div class="card-body">
                        <div id="conversationTimelineChart" style="height: 400px;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 事件列表 -->
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">🔍 最近服务器事件</div>
                    <div class="card-body">
                        <div id="serverEvents" style="max-height: 400px; overflow-y: auto;">
                            <!-- 服务器事件列表 -->
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">💭 最近对话记录</div>
                    <div class="card-body">
                        <div id="conversations" style="max-height: 400px; overflow-y: auto;">
                            <!-- 对话记录列表 -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 更新服务器统计
        function updateServerStats() {
            fetch('/api/server_stats')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('serverStats');
                    container.innerHTML = `
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-primary">${data.total_events || 0}</h5>
                                    <p class="card-text">总事件数</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card risk-high">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-danger">${data.high_risk_events || 0}</h5>
                                    <p class="card-text">高风险事件</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-info">${data.financial_events || 0}</h5>
                                    <p class="card-text">金融事件</p>
                                </div>
                            </div>
                        </div>
                    `;
                });
        }

        // 更新对话统计
        function updateConversationStats() {
            fetch('/api/conversation_stats')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('conversationStats');
                    container.innerHTML = `
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-success">${data.total_conversations || 0}</h5>
                                    <p class="card-text">总对话数</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card risk-high">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-danger">${data.high_risk || 0}</h5>
                                    <p class="card-text">高风险对话</p>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4 mb-2">
                            <div class="card metric-card">
                                <div class="card-body text-center">
                                    <h5 class="card-title text-warning">${data.avg_sensitivity || 0}</h5>
                                    <p class="card-text">平均敏感度</p>
                                </div>
                            </div>
                        </div>
                    `;
                });
        }

        // 更新图表
        function updateCharts() {
            // 风险对比图表
            fetch('/api/charts/risk_comparison')
                .then(response => response.json())
                .then(data => {
                    if (data.chart) {
                        Plotly.newPlot('riskComparisonChart', JSON.parse(data.chart).data, JSON.parse(data.chart).layout);
                    }
                });

            // 对话时间线图表
            fetch('/api/charts/conversation_timeline')
                .then(response => response.json())
                .then(data => {
                    if (data.chart) {
                        Plotly.newPlot('conversationTimelineChart', JSON.parse(data.chart).data, JSON.parse(data.chart).layout);
                    }
                });
        }

        // 更新事件列表
        function updateEvents() {
            // 服务器事件
            fetch('/api/server_events?limit=20')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('serverEvents');
                    if (Array.isArray(data)) {
                        container.innerHTML = data.map(event => `
                            <div class="event-row">
                                <strong>${event.event_type}</strong> 
                                <span class="badge bg-${event.level === 'ERROR' ? 'danger' : event.level === 'WARNING' ? 'warning' : 'info'}">${event.level}</span>
                                <br>
                                <small class="text-muted">${new Date(event.timestamp).toLocaleString()}</small>
                                <br>
                                <small>${event.action}: ${event.details}</small>
                            </div>
                        `).join('');
                    }
                });

            // 对话记录
            fetch('/api/conversations?limit=20')
                .then(response => response.json())
                .then(data => {
                    const container = document.getElementById('conversations');
                    if (Array.isArray(data)) {
                        container.innerHTML = data.map(conv => `
                            <div class="conversation-item">
                                <div class="d-flex justify-content-between">
                                    <strong>${conv.user_id}</strong>
                                    <span class="badge bg-${conv.risk_level === 'HIGH' ? 'danger' : conv.risk_level === 'MEDIUM' ? 'warning' : 'success'}">${conv.risk_level}</span>
                                </div>
                                <div class="mt-2">
                                    <div><strong>Q:</strong> ${conv.user_question}</div>
                                    <div class="mt-1"><strong>A:</strong> ${conv.llm_response}</div>
                                </div>
                                <small class="text-muted">${new Date(conv.timestamp).toLocaleString()}</small>
                            </div>
                        `).join('');
                    }
                });
        }

        // 初始化和定时刷新
        function updateAll() {
            updateServerStats();
            updateConversationStats();
            updateCharts();
            updateEvents();
            document.getElementById('lastUpdate').textContent = `最后更新: ${new Date().toLocaleTimeString()}`;
        }

        // 页面加载时更新
        updateAll();

        // 每30秒自动刷新
        setInterval(updateAll, 30000);
    </script>
</body>
</html>
        '''
        
        template_path = template_dir / 'comprehensive_audit_dashboard.html'
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        print(f"✅ 创建仪表板模板: {template_path}")
    
    def run(self, host="127.0.0.1", port=5002, debug=False):
        """启动仪表板"""
        self.create_dashboard_template()
        
        print(f"🚀 启动Letta综合审计系统仪表板")
        print(f"   📊 仪表板地址: http://{host}:{port}")
        print(f"   🔗 Letta服务器: {self.config.letta_server_url}")
        print(f"   🗄️ 服务器审计DB: {self.config.server_audit_db_path}")
        print(f"   💬 对话审计DB: {self.config.rag_audit_db_path}")
        print(f"   ⚡ 自动刷新: {self.config.refresh_interval}秒")
        
        # 测试连接
        print(f"\n🔍 测试连接:")
        audit_system_status = "直连成功" if self.audit_system else "使用REST API"
        print(f"  ✅ 服务器端审计系统: {audit_system_status}")
        
        rag_audit_status = "数据库存在" if os.path.exists(self.config.rag_audit_db_path) else "数据库不存在"
        print(f"  {'✅' if os.path.exists(self.config.rag_audit_db_path) else '⚠️'} RAG审计数据库: {rag_audit_status}")
        
        try:
            response = requests.get(f"{self.config.letta_server_url}/health", timeout=5)
            server_status = f"响应码 {response.status_code}"
        except:
            server_status = "连接失败"
        print(f"  {'✅' if '响应码 2' in server_status else '⚠️'} Letta服务器: {server_status}")
        
        print(f"\n{'='*60}")
        print("综合审计仪表板功能:")
        print("• 服务器端审计统计和事件监控")
        print("• 用户对话审计和风险评估")
        print("• 风险分布对比图表")
        print("• 对话时间线分析")
        print("• 实时事件和对话记录")
        print("• 敏感信息检测报告")
        print(f"{'='*60}")
        
        self.app.run(host=host, port=port, debug=debug)


def main():
    """主函数"""
    config = ComprehensiveAuditConfig()
    dashboard = ComprehensiveAuditDashboard(config)
    dashboard.run(debug=True)


if __name__ == "__main__":
    main()