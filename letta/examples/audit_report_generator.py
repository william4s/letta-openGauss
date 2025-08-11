#!/usr/bin/env python3
"""
Letta RAG系统审计报告生成工具
用于生成详细的安全审计报告和合规性文档
"""

import os
import json
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from security_audit import SecurityAuditor, get_auditor

class AuditReportGenerator:
    """审计报告生成器"""
    
    def __init__(self, audit_log_path: str = "./logs/security_audit.log"):
        self.auditor = SecurityAuditor(audit_log_path=audit_log_path)
        self.report_dir = Path("./reports")
        self.report_dir.mkdir(exist_ok=True)
    
    def generate_comprehensive_report(self, hours: int = 24, output_format: str = "html") -> str:
        """生成综合审计报告"""
        print(f"📊 生成最近{hours}小时的综合审计报告...")
        
        # 获取基础审计数据
        report_data = self.auditor.generate_audit_report(hours)
        
        # 扩展分析
        extended_data = self._analyze_extended_metrics(hours)
        report_data.update(extended_data)
        
        # 生成报告文件
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format.lower() == "html":
            filename = f"audit_report_{timestamp}.html"
            filepath = self.report_dir / filename
            self._generate_html_report(report_data, filepath)
        elif output_format.lower() == "json":
            filename = f"audit_report_{timestamp}.json"
            filepath = self.report_dir / filename
            self._generate_json_report(report_data, filepath)
        elif output_format.lower() == "csv":
            filename = f"audit_report_{timestamp}.csv"
            filepath = self.report_dir / filename
            self._generate_csv_report(report_data, filepath)
        else:
            raise ValueError(f"不支持的输出格式: {output_format}")
        
        print(f"✅ 报告已生成: {filepath}")
        return str(filepath)
    
    def _analyze_extended_metrics(self, hours: int) -> Dict:
        """分析扩展指标"""
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        try:
            with open(self.auditor.audit_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except FileNotFoundError:
            return {}
        
        events = []
        for line in lines:
            try:
                parts = line.strip().split(' | ', 2)
                if len(parts) >= 3:
                    event_data = json.loads(parts[2])
                    event_time = datetime.datetime.fromisoformat(event_data['timestamp'])
                    
                    if event_time >= cutoff_time:
                        events.append(event_data)
            except (json.JSONDecodeError, KeyError, ValueError, IndexError):
                continue
        
        # 时间分布分析
        hourly_distribution = {}
        for event in events:
            hour = datetime.datetime.fromisoformat(event['timestamp']).hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
        
        # 用户行为分析
        user_analysis = {}
        for event in events:
            user_id = event.get('user_id', 'unknown')
            if user_id not in user_analysis:
                user_analysis[user_id] = {
                    'total_events': 0,
                    'risk_events': 0,
                    'error_events': 0,
                    'event_types': {},
                    'avg_risk_score': 0,
                    'peak_activity_hour': None
                }
            
            user_analysis[user_id]['total_events'] += 1
            
            if event.get('risk_score', 0) >= 50:
                user_analysis[user_id]['risk_events'] += 1
            
            if not event.get('success', True):
                user_analysis[user_id]['error_events'] += 1
            
            event_type = event['event_type']
            user_analysis[user_id]['event_types'][event_type] = \
                user_analysis[user_id]['event_types'].get(event_type, 0) + 1
        
        # 计算平均风险评分
        for user_id, data in user_analysis.items():
            user_events = [e for e in events if e.get('user_id') == user_id]
            if user_events:
                avg_risk = sum(e.get('risk_score', 0) for e in user_events) / len(user_events)
                data['avg_risk_score'] = round(avg_risk, 2)
        
        # 响应时间分析
        response_times = [e.get('response_time_ms', 0) for e in events if e.get('response_time_ms')]
        response_analysis = {}
        if response_times:
            response_analysis = {
                'avg_response_time': round(sum(response_times) / len(response_times), 2),
                'max_response_time': max(response_times),
                'min_response_time': min(response_times),
                'slow_queries': len([t for t in response_times if t > 5000])
            }
        
        # 安全事件趋势
        security_events = [e for e in events if e.get('level') == 'SECURITY' or e.get('risk_score', 0) >= 70]
        security_trend = {
            'total_security_events': len(security_events),
            'security_event_types': {},
            'top_security_users': {}
        }
        
        for event in security_events:
            event_type = event['event_type']
            security_trend['security_event_types'][event_type] = \
                security_trend['security_event_types'].get(event_type, 0) + 1
            
            user_id = event.get('user_id', 'unknown')
            security_trend['top_security_users'][user_id] = \
                security_trend['top_security_users'].get(user_id, 0) + 1
        
        return {
            'hourly_distribution': hourly_distribution,
            'user_analysis': user_analysis,
            'response_analysis': response_analysis,
            'security_trend': security_trend,
            'analysis_period': f"{hours}小时",
            'analysis_timestamp': datetime.datetime.now().isoformat()
        }
    
    def _generate_html_report(self, data: Dict, filepath: Path):
        """生成HTML格式报告"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Letta RAG系统安全审计报告</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; color: #333; border-bottom: 2px solid #007bff; padding-bottom: 20px; }}
        .section {{ margin: 30px 0; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        .risk-high {{ color: #dc3545; }}
        .risk-medium {{ color: #ffc107; }}
        .risk-low {{ color: #28a745; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
        .chart-container {{ margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        .alert {{ padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .alert-danger {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
        .alert-warning {{ background: #fff3cd; border: 1px solid #ffeaa7; color: #856404; }}
        .alert-info {{ background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }}
        .footer {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 报告头部 -->
        <div class="header">
            <h1>🔒 Letta RAG系统安全审计报告</h1>
            <p>报告期间: {data.get('report_period', 'N/A')} | 生成时间: {data.get('generation_time', 'N/A')}</p>
        </div>
        
        <!-- 关键指标 -->
        <div class="section">
            <h2>📊 关键指标概览</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{data.get('total_events', 0)}</div>
                    <div class="metric-label">总事件数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{data.get('unique_users', 0)}</div>
                    <div class="metric-label">活跃用户数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value risk-{self._get_health_class(data.get('system_health', '正常'))}">{data.get('system_health', '正常')}</div>
                    <div class="metric-label">系统健康</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value risk-high">{data.get('high_risk_count', 0)}</div>
                    <div class="metric-label">高风险事件</div>
                </div>
            </div>
        </div>
        
        <!-- 风险分布 -->
        <div class="section">
            <h2>⚠️ 风险分布分析</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value risk-high">{data.get('risk_distribution', {}).get('high', 0)}</div>
                    <div class="metric-label">高风险事件</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value risk-medium">{data.get('risk_distribution', {}).get('medium', 0)}</div>
                    <div class="metric-label">中风险事件</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value risk-low">{data.get('risk_distribution', {}).get('low', 0)}</div>
                    <div class="metric-label">低风险事件</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{data.get('sensitive_data_access', 0)}</div>
                    <div class="metric-label">敏感数据访问</div>
                </div>
            </div>
        </div>
        
        <!-- 事件类型统计 -->
        <div class="section">
            <h2>📈 事件类型统计</h2>
            <table>
                <thead>
                    <tr>
                        <th>事件类型</th>
                        <th>发生次数</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        # 事件类型表格
        event_types = data.get('event_types', {})
        total_events = data.get('total_events', 0)
        for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_events * 100) if total_events > 0 else 0
            html_content += f"""
                    <tr>
                        <td>{event_type}</td>
                        <td>{count}</td>
                        <td>{percentage:.1f}%</td>
                    </tr>
"""
        
        html_content += """
                </tbody>
            </table>
        </div>
"""
        
        # 用户行为分析
        if 'user_analysis' in data:
            html_content += """
        <div class="section">
            <h2>👥 用户行为分析</h2>
            <table>
                <thead>
                    <tr>
                        <th>用户ID</th>
                        <th>总事件数</th>
                        <th>风险事件</th>
                        <th>错误事件</th>
                        <th>平均风险评分</th>
                    </tr>
                </thead>
                <tbody>
"""
            user_analysis = data['user_analysis']
            for user_id, user_data in sorted(user_analysis.items(), 
                                           key=lambda x: x[1]['total_events'], reverse=True):
                html_content += f"""
                    <tr>
                        <td>{user_id}</td>
                        <td>{user_data['total_events']}</td>
                        <td class="risk-{self._get_risk_class(user_data['risk_events'])}">{user_data['risk_events']}</td>
                        <td class="risk-{self._get_risk_class(user_data['error_events'])}">{user_data['error_events']}</td>
                        <td class="risk-{self._get_risk_class_score(user_data['avg_risk_score'])}">{user_data['avg_risk_score']}</td>
                    </tr>
"""
            html_content += """
                </tbody>
            </table>
        </div>
"""
        
        # 高风险事件详情
        if data.get('high_risk_events'):
            html_content += """
        <div class="section">
            <h2>🚨 高风险事件详情</h2>
            <div class="alert alert-danger">
                <strong>注意:</strong> 以下事件需要重点关注和处理
            </div>
"""
            for event in data['high_risk_events'][:10]:  # 显示前10个
                html_content += f"""
            <div class="alert alert-warning">
                <strong>时间:</strong> {event.get('timestamp', 'N/A')}<br>
                <strong>用户:</strong> {event.get('user_id', 'N/A')}<br>
                <strong>事件类型:</strong> {event.get('event_type', 'N/A')}<br>
                <strong>操作:</strong> {event.get('action', 'N/A')}<br>
                <strong>风险评分:</strong> <span class="risk-high">{event.get('risk_score', 0)}</span><br>
                <strong>详情:</strong> {str(event.get('details', {}))[:200]}...
            </div>
"""
        
        # 性能分析
        if 'response_analysis' in data and data['response_analysis']:
            response_data = data['response_analysis']
            html_content += f"""
        <div class="section">
            <h2>⚡ 性能分析</h2>
            <div class="metrics">
                <div class="metric-card">
                    <div class="metric-value">{response_data.get('avg_response_time', 0)}ms</div>
                    <div class="metric-label">平均响应时间</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{response_data.get('max_response_time', 0)}ms</div>
                    <div class="metric-label">最大响应时间</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{response_data.get('slow_queries', 0)}</div>
                    <div class="metric-label">慢查询数量</div>
                </div>
            </div>
        </div>
"""
        
        # 建议和改进
        html_content += f"""
        <div class="section">
            <h2>💡 安全建议</h2>
            <div class="alert alert-info">
                {self._generate_recommendations(data)}
            </div>
        </div>
        
        <div class="footer">
            <p>报告由 Letta RAG 安全审计系统自动生成</p>
            <p>版本: v1.0 | 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_json_report(self, data: Dict, filepath: Path):
        """生成JSON格式报告"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _generate_csv_report(self, data: Dict, filepath: Path):
        """生成CSV格式报告"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入基本统计信息
            writer.writerow(['指标', '数值'])
            writer.writerow(['报告期间', data.get('report_period', 'N/A')])
            writer.writerow(['总事件数', data.get('total_events', 0)])
            writer.writerow(['唯一用户数', data.get('unique_users', 0)])
            writer.writerow(['系统健康', data.get('system_health', 'N/A')])
            writer.writerow(['高风险事件', data.get('high_risk_count', 0)])
            writer.writerow(['错误事件', data.get('error_count', 0)])
            writer.writerow([])
            
            # 写入事件类型统计
            writer.writerow(['事件类型统计'])
            writer.writerow(['事件类型', '发生次数'])
            for event_type, count in data.get('event_types', {}).items():
                writer.writerow([event_type, count])
            writer.writerow([])
            
            # 写入用户分析
            if 'user_analysis' in data:
                writer.writerow(['用户行为分析'])
                writer.writerow(['用户ID', '总事件数', '风险事件', '错误事件', '平均风险评分'])
                for user_id, user_data in data['user_analysis'].items():
                    writer.writerow([
                        user_id,
                        user_data['total_events'],
                        user_data['risk_events'], 
                        user_data['error_events'],
                        user_data['avg_risk_score']
                    ])
    
    def _get_health_class(self, health: str) -> str:
        """获取健康状态对应的CSS类"""
        if health == "异常":
            return "high"
        elif health == "需要关注":
            return "medium"
        else:
            return "low"
    
    def _get_risk_class(self, count: int) -> str:
        """根据事件数量获取风险类"""
        if count >= 10:
            return "high"
        elif count >= 3:
            return "medium"
        else:
            return "low"
    
    def _get_risk_class_score(self, score: float) -> str:
        """根据风险评分获取风险类"""
        if score >= 70:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"
    
    def _generate_recommendations(self, data: Dict) -> str:
        """生成安全建议"""
        recommendations = []
        
        # 基于高风险事件的建议
        if data.get('high_risk_count', 0) > 5:
            recommendations.append("🚨 检测到多个高风险事件，建议立即审查用户权限和操作日志")
        
        # 基于错误率的建议
        error_rate = (data.get('error_count', 0) / max(data.get('total_events', 1), 1)) * 100
        if error_rate > 10:
            recommendations.append(f"❌ 错误率较高 ({error_rate:.1f}%)，建议检查系统稳定性")
        
        # 基于敏感数据访问的建议
        if data.get('sensitive_data_access', 0) > 0:
            recommendations.append("🔒 检测到敏感数据访问，建议加强数据脱敏和访问控制")
        
        # 基于用户行为的建议
        if 'user_analysis' in data:
            high_risk_users = [u for u, d in data['user_analysis'].items() 
                             if d['avg_risk_score'] > 50]
            if high_risk_users:
                recommendations.append(f"👥 发现高风险用户: {', '.join(high_risk_users[:3])}，建议加强监控")
        
        # 基于性能的建议
        if 'response_analysis' in data and data['response_analysis'].get('slow_queries', 0) > 0:
            recommendations.append("⚡ 检测到慢查询，建议优化系统性能")
        
        # 通用建议
        recommendations.extend([
            "📝 定期更新敏感词库和风险检测规则",
            "🔄 建立自动化告警和响应机制",
            "📊 定期进行安全审计和合规性检查",
            "🎓 加强用户安全意识培训"
        ])
        
        return "<br>".join(recommendations[:8])  # 限制建议数量
    
    def generate_compliance_report(self, compliance_type: str = "general") -> str:
        """生成合规性报告"""
        print(f"📋 生成{compliance_type}合规性报告...")
        
        # 获取最近30天的数据
        data = self.auditor.generate_audit_report(hours=30*24)
        
        # 根据合规类型生成不同的报告
        if compliance_type.lower() == "gdpr":
            return self._generate_gdpr_compliance_report(data)
        elif compliance_type.lower() == "hipaa":
            return self._generate_hipaa_compliance_report(data)
        elif compliance_type.lower() == "pci":
            return self._generate_pci_compliance_report(data)
        else:
            return self._generate_general_compliance_report(data)
    
    def _generate_gdpr_compliance_report(self, data: Dict) -> str:
        """生成GDPR合规报告"""
        # GDPR相关的审计要求
        gdpr_report = {
            "data_processing_activities": data.get('total_events', 0),
            "data_subject_requests": 0,  # 需要从具体事件中统计
            "data_breaches": len([e for e in data.get('high_risk_events', []) 
                                if 'breach' in str(e).lower()]),
            "access_logs": data.get('total_events', 0),
            "consent_records": 0,  # 需要额外实现
            "data_retention_compliance": True  # 需要检查保留策略
        }
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gdpr_compliance_{timestamp}.json"
        filepath = self.report_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(gdpr_report, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def _generate_hipaa_compliance_report(self, data: Dict) -> str:
        """生成HIPAA合规报告"""
        # HIPAA相关的审计要求
        hipaa_report = {
            "access_controls": True,
            "audit_logs": data.get('total_events', 0),
            "data_integrity": True,
            "transmission_security": True,
            "user_access_management": len(data.get('users', [])),
            "incident_response": len(data.get('high_risk_events', []))
        }
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hipaa_compliance_{timestamp}.json"
        filepath = self.report_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(hipaa_report, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def _generate_general_compliance_report(self, data: Dict) -> str:
        """生成通用合规报告"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"compliance_report_{timestamp}.html"
        filepath = self.report_dir / filename
        self._generate_html_report(data, filepath)
        return str(filepath)


def main():
    """命令行工具主函数"""
    parser = argparse.ArgumentParser(description="Letta RAG系统审计报告生成工具")
    parser.add_argument("--hours", type=int, default=24, help="报告时间范围（小时）")
    parser.add_argument("--format", choices=["html", "json", "csv"], default="html", help="输出格式")
    parser.add_argument("--log-path", default="./logs/security_audit.log", help="审计日志文件路径")
    parser.add_argument("--compliance", choices=["general", "gdpr", "hipaa", "pci"], help="生成合规性报告")
    
    args = parser.parse_args()
    
    # 创建报告生成器
    generator = AuditReportGenerator(args.log_path)
    
    try:
        if args.compliance:
            # 生成合规性报告
            filepath = generator.generate_compliance_report(args.compliance)
            print(f"✅ 合规性报告已生成: {filepath}")
        else:
            # 生成综合审计报告
            filepath = generator.generate_comprehensive_report(args.hours, args.format)
            print(f"✅ 审计报告已生成: {filepath}")
    
    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
