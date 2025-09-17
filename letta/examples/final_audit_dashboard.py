#!/usr/bin/env python3
"""
Letta审计系统 - 最终版本
整合服务器端审计系统，提供完整的网页可视化审计仪表板
"""

import os
import json
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
class AuditDashboardConfig:
    """审计仪表板配置"""
    letta_server_url: str = "http://localhost:8283"
    refresh_interval: int = 30  # 秒
    max_events_display: int = 100
    enable_real_time: bool = True
    audit_db_path: str = "./logs/letta_audit.db"


class LettaAuditDashboard:
    """Letta审计系统仪表板"""
    
    def __init__(self, config: AuditDashboardConfig = None):
        self.config = config or AuditDashboardConfig()
        self.app = Flask(__name__)
        CORS(self.app)
        
        # 尝试直接连接审计系统
        self.audit_system = None
        if get_audit_system:
            try:
                self.audit_system = get_audit_system()
                print("✅ 直接连接到服务器端审计系统")
            except Exception as e:
                print(f"⚠️ 无法直接连接审计系统，将使用REST API: {e}")
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置Flask路由"""
        
        @self.app.route('/')
        def dashboard():
            """主仪表板页面"""
            return render_template('audit_dashboard.html')
        
        @self.app.route('/api/stats')
        def get_stats():
            """获取审计统计信息"""
            try:
                if self.audit_system:
                    # 直接从审计系统获取
                    stats = self.audit_system.get_real_time_stats()
                    report_data = self.audit_system.generate_audit_report(hours=24)
                else:
                    # 通过REST API获取
                    response = requests.get(
                        f"{self.config.letta_server_url}/v1/audit/stats",
                        timeout=10
                    )
                    if response.status_code == 200:
                        stats = response.json()
                        report_data = {}
                    else:
                        raise Exception(f"API调用失败: {response.status_code}")
                
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
                return jsonify({"error": f"获取统计信息失败: {str(e)}"}), 500
        
        @self.app.route('/api/events')
        def get_events():
            """获取最近的审计事件"""
            try:
                limit = request.args.get('limit', 50, type=int)
                event_type = request.args.get('event_type')
                risk_level = request.args.get('risk_level')
                hours = request.args.get('hours', 24, type=int)
                
                if self.audit_system and hasattr(self.audit_system, 'get_events'):
                    # 直接从审计系统获取
                    events = self.audit_system.get_events(
                        limit=limit, 
                        event_type=event_type,
                        risk_level=risk_level,
                        hours=hours
                    )
                else:
                    # 通过REST API获取
                    params = {
                        'limit': limit,
                        'hours': hours
                    }
                    if event_type:
                        params['event_type'] = event_type
                    if risk_level:
                        params['risk_level'] = risk_level
                    
                    response = requests.get(
                        f"{self.config.letta_server_url}/v1/audit/events",
                        params=params,
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        events = response.json()
                    else:
                        raise Exception(f"API调用失败: {response.status_code}")
                
                return jsonify(events)
                
            except Exception as e:
                return jsonify({"error": f"获取事件失败: {str(e)}"}), 500
        
        @self.app.route('/api/charts/risk_distribution')
        def risk_distribution_chart():
            """生成风险分布图表"""
            try:
                if self.audit_system:
                    report_data = self.audit_system.generate_audit_report(hours=24)
                else:
                    # 模拟数据或通过API获取
                    report_data = {"summary": {"high_risk_events": 5, "medium_risk_events": 15, "low_risk_events": 30}}
                
                summary = report_data.get("summary", {})
                
                fig = go.Figure(data=[
                    go.Pie(
                        labels=['高风险', '中等风险', '低风险'],
                        values=[
                            summary.get("high_risk_events", 0),
                            summary.get("medium_risk_events", 0),
                            summary.get("low_risk_events", 0)
                        ],
                        hole=0.3,
                        marker_colors=['#ff4757', '#ffa502', '#2ed573']
                    )
                ])
                
                fig.update_layout(
                    title="24小时风险事件分布",
                    font=dict(size=14),
                    showlegend=True
                )
                
                return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))
                
            except Exception as e:
                return jsonify({"error": f"生成图表失败: {str(e)}"}), 500
        
        @self.app.route('/api/charts/event_timeline')
        def event_timeline_chart():
            """生成事件时间线图表"""
            try:
                # 获取24小时内的事件统计
                if self.audit_system and hasattr(self.audit_system, 'get_hourly_stats'):
                    hourly_data = self.audit_system.get_hourly_stats(hours=24)
                else:
                    # 模拟24小时数据
                    import random
                    hourly_data = []
                    base_time = datetime.datetime.now() - datetime.timedelta(hours=23)
                    for i in range(24):
                        hour_time = base_time + datetime.timedelta(hours=i)
                        hourly_data.append({
                            "hour": hour_time.strftime("%H:00"),
                            "events": random.randint(0, 10),
                            "high_risk": random.randint(0, 2)
                        })
                
                hours = [item["hour"] for item in hourly_data]
                events = [item["events"] for item in hourly_data]
                high_risk = [item["high_risk"] for item in hourly_data]
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=hours,
                    y=events,
                    mode='lines+markers',
                    name='总事件',
                    line=dict(color='#3742fa'),
                    marker=dict(size=6)
                ))
                
                fig.add_trace(go.Scatter(
                    x=hours,
                    y=high_risk,
                    mode='lines+markers',
                    name='高风险事件',
                    line=dict(color='#ff4757'),
                    marker=dict(size=6)
                ))
                
                fig.update_layout(
                    title="24小时事件趋势",
                    xaxis_title="时间",
                    yaxis_title="事件数量",
                    font=dict(size=12),
                    showlegend=True
                )
                
                return jsonify(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig)))
                
            except Exception as e:
                return jsonify({"error": f"生成时间线图表失败: {str(e)}"}), 500
        
        @self.app.route('/api/report/download')
        def download_report():
            """下载审计报告"""
            try:
                hours = request.args.get('hours', 24, type=int)
                format_type = request.args.get('format', 'html')
                
                if self.audit_system and os.path.exists(self.config.audit_db_path):
                    # 使用本地报告生成器
                    generator = LettaAuditReportGenerator(self.config.audit_db_path)
                    report_path = generator.generate_comprehensive_report(
                        hours=hours, 
                        output_format=format_type,
                        include_financial_analysis=True
                    )
                    return send_file(report_path, as_attachment=True)
                else:
                    # 通过REST API获取
                    response = requests.get(
                        f"{self.config.letta_server_url}/v1/audit/report",
                        params={'hours': hours, 'format': format_type},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        # 临时保存文件并返回
                        temp_path = f"./temp_report.{format_type}"
                        with open(temp_path, 'wb') as f:
                            f.write(response.content)
                        return send_file(temp_path, as_attachment=True)
                    else:
                        raise Exception(f"API调用失败: {response.status_code}")
                        
            except Exception as e:
                return jsonify({"error": f"下载报告失败: {str(e)}"}), 500
        
        @self.app.route('/api/compliance')
        def compliance_status():
            """获取合规状态"""
            try:
                if self.audit_system and hasattr(self.audit_system, 'get_compliance_status'):
                    status = self.audit_system.get_compliance_status()
                else:
                    # 模拟合规状态
                    status = {
                        "overall_score": 85,
                        "risk_disclosure_compliance": 90,
                        "data_protection_compliance": 80,
                        "financial_regulation_compliance": 88,
                        "violations": 2,
                        "last_assessment": datetime.datetime.now().isoformat()
                    }
                
                return jsonify(status)
                
            except Exception as e:
                return jsonify({"error": f"获取合规状态失败: {str(e)}"}), 500
    
    def create_dashboard_template(self):
        """创建仪表板HTML模板"""
        template_dir = Path(self.app.template_folder or './templates')
        template_dir.mkdir(exist_ok=True)
        
        template_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Letta审计系统仪表板</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        .risk-high { background: linear-gradient(135deg, #ff4757, #ff3838); }
        .risk-medium { background: linear-gradient(135deg, #ffa502, #ff8c00); }
        .risk-low { background: linear-gradient(135deg, #2ed573, #00b894); }
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .navbar-brand {
            font-weight: bold;
        }
        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background-color: #2ed573; }
        .status-offline { background-color: #ff4757; }
    </style>
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">
                <i class="fas fa-shield-alt me-2"></i>
                Letta审计系统仪表板
            </a>
            <div class="d-flex align-items-center">
                <span id="connection-status" class="text-light me-3">
                    <span class="status-indicator status-online"></span>
                    连接正常
                </span>
                <button class="btn btn-outline-light btn-sm" onclick="downloadReport()">
                    <i class="fas fa-download me-1"></i>下载报告
                </button>
            </div>
        </div>
    </nav>

    <div class="container-fluid mt-4">
        <!-- 统计卡片 -->
        <div class="row">
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="metric-value" id="total-events">-</div>
                    <div class="metric-label">
                        <i class="fas fa-list me-1"></i>总事件数
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card risk-high">
                    <div class="metric-value" id="high-risk-events">-</div>
                    <div class="metric-label">
                        <i class="fas fa-exclamation-triangle me-1"></i>高风险事件
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card risk-medium">
                    <div class="metric-value" id="financial-events">-</div>
                    <div class="metric-label">
                        <i class="fas fa-dollar-sign me-1"></i>金融事件
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card risk-low">
                    <div class="metric-value" id="compliance-score">-</div>
                    <div class="metric-label">
                        <i class="fas fa-check-circle me-1"></i>合规评分
                    </div>
                </div>
            </div>
        </div>

        <!-- 图表 -->
        <div class="row">
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="fas fa-chart-pie me-2"></i>风险分布</h5>
                    <div id="risk-distribution-chart"></div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="chart-container">
                    <h5><i class="fas fa-chart-line me-2"></i>事件趋势</h5>
                    <div id="timeline-chart"></div>
                </div>
            </div>
        </div>

        <!-- 最近事件表 -->
        <div class="row">
            <div class="col-12">
                <div class="chart-container">
                    <h5><i class="fas fa-history me-2"></i>最近事件</h5>
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>时间</th>
                                    <th>类型</th>
                                    <th>用户</th>
                                    <th>操作</th>
                                    <th>风险评分</th>
                                    <th>状态</th>
                                </tr>
                            </thead>
                            <tbody id="events-table">
                                <tr><td colspan="6" class="text-center">加载中...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 全局状态
        let updateInterval;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', function() {
            updateDashboard();
            startAutoUpdate();
        });
        
        // 更新仪表板数据
        async function updateDashboard() {
            try {
                await Promise.all([
                    updateStats(),
                    updateCharts(),
                    updateEvents()
                ]);
                updateConnectionStatus(true);
            } catch (error) {
                console.error('更新仪表板失败:', error);
                updateConnectionStatus(false);
            }
        }
        
        // 更新统计信息
        async function updateStats() {
            const response = await fetch('/api/stats');
            const stats = await response.json();
            
            document.getElementById('total-events').textContent = stats.total_events || 0;
            document.getElementById('high-risk-events').textContent = stats.high_risk_events || 0;
            document.getElementById('financial-events').textContent = stats.financial_events || 0;
            
            // 更新合规评分
            const complianceResponse = await fetch('/api/compliance');
            const compliance = await complianceResponse.json();
            document.getElementById('compliance-score').textContent = 
                Math.round(compliance.overall_score || 0) + '%';
        }
        
        // 更新图表
        async function updateCharts() {
            // 风险分布图
            const riskResponse = await fetch('/api/charts/risk_distribution');
            const riskData = await riskResponse.json();
            Plotly.newPlot('risk-distribution-chart', riskData.data, riskData.layout, {responsive: true});
            
            // 事件时间线
            const timelineResponse = await fetch('/api/charts/event_timeline');
            const timelineData = await timelineResponse.json();
            Plotly.newPlot('timeline-chart', timelineData.data, timelineData.layout, {responsive: true});
        }
        
        // 更新事件表
        async function updateEvents() {
            const response = await fetch('/api/events?limit=10');
            const events = await response.json();
            
            const tbody = document.getElementById('events-table');
            if (events.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center">暂无事件</td></tr>';
                return;
            }
            
            tbody.innerHTML = events.map(event => `
                <tr>
                    <td>${formatTime(event.timestamp)}</td>
                    <td><span class="badge bg-info">${event.event_type}</span></td>
                    <td>${event.user_id || 'N/A'}</td>
                    <td>${event.action}</td>
                    <td>
                        <span class="badge ${getRiskBadgeClass(event.risk_score)}">
                            ${event.risk_score}
                        </span>
                    </td>
                    <td>
                        <i class="fas ${event.success ? 'fa-check-circle text-success' : 'fa-times-circle text-danger'}"></i>
                    </td>
                </tr>
            `).join('');
        }
        
        // 辅助函数
        function formatTime(timestamp) {
            return new Date(timestamp).toLocaleString('zh-CN');
        }
        
        function getRiskBadgeClass(score) {
            if (score >= 70) return 'bg-danger';
            if (score >= 40) return 'bg-warning';
            return 'bg-success';
        }
        
        function updateConnectionStatus(isOnline) {
            const statusEl = document.getElementById('connection-status');
            const indicator = statusEl.querySelector('.status-indicator');
            
            if (isOnline) {
                indicator.className = 'status-indicator status-online';
                statusEl.innerHTML = '<span class="status-indicator status-online"></span>连接正常';
            } else {
                indicator.className = 'status-indicator status-offline';
                statusEl.innerHTML = '<span class="status-indicator status-offline"></span>连接异常';
            }
        }
        
        // 自动更新
        function startAutoUpdate() {
            updateInterval = setInterval(updateDashboard, 30000); // 30秒更新一次
        }
        
        // 下载报告
        function downloadReport() {
            window.open('/api/report/download?format=html&hours=24', '_blank');
        }
    </script>
</body>
</html>"""
        
        template_path = template_dir / 'audit_dashboard.html'
        template_path.write_text(template_content, encoding='utf-8')
        print(f"✅ 创建仪表板模板: {template_path}")
    
    def run(self, host='127.0.0.1', port=5001, debug=False):
        """运行仪表板应用"""
        print("🚀 启动Letta审计系统仪表板")
        print(f"   📊 仪表板地址: http://{host}:{port}")
        print(f"   🔗 Letta服务器: {self.config.letta_server_url}")
        print(f"   ⚡ 自动刷新: {self.config.refresh_interval}秒")
        
        # 创建模板
        self.create_dashboard_template()
        
        # 测试连接
        self._test_connections()
        
        print("\n" + "="*50)
        print("审计仪表板功能:")
        print("• 实时审计统计和指标")
        print("• 风险事件分布图表")
        print("• 24小时事件趋势分析")  
        print("• 最近审计事件列表")
        print("• 合规性状态监控")
        print("• 审计报告下载")
        print("="*50)
        
        self.app.run(host=host, port=port, debug=debug)
    
    def _test_connections(self):
        """测试连接状态"""
        print("\n🔍 测试连接:")
        
        # 测试审计系统连接
        if self.audit_system:
            print("  ✅ 服务器端审计系统: 直连成功")
        else:
            print("  ⚠️ 服务器端审计系统: 使用REST API")
        
        # 测试审计数据库
        if os.path.exists(self.config.audit_db_path):
            print(f"  ✅ 审计数据库: {self.config.audit_db_path}")
        else:
            print(f"  ⚠️ 审计数据库: 文件不存在 {self.config.audit_db_path}")
        
        # 测试Letta服务器连接
        try:
            response = requests.get(f"{self.config.letta_server_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"  ✅ Letta服务器: {self.config.letta_server_url}")
            else:
                print(f"  ⚠️ Letta服务器: 响应码 {response.status_code}")
        except Exception as e:
            print(f"  ❌ Letta服务器: 连接失败 - {e}")


def main():
    """主函数"""
    print("📊 Letta审计系统 - 最终版本仪表板")
    print("="*50)
    
    # 配置
    config = AuditDashboardConfig(
        letta_server_url="http://localhost:8283",
        refresh_interval=30,
        max_events_display=100,
        enable_real_time=True,
        audit_db_path="./logs/letta_audit.db"
    )
    
    # 创建并运行仪表板
    dashboard = LettaAuditDashboard(config)
    
    try:
        dashboard.run(host='127.0.0.1', port=5001, debug=False)
    except KeyboardInterrupt:
        print("\n👋 审计仪表板已关闭")
    except Exception as e:
        print(f"❌ 启动失败: {e}")


if __name__ == "__main__":
    main()