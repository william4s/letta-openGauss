#!/usr/bin/env python3
"""
Letta服务器日志分析工具
分析审计日志、性能指标和错误模式
"""

import re
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class LettaLogAnalyzer:
    """Letta服务器日志分析器"""
    
    def __init__(self, log_file: str):
        self.log_file = Path(log_file)
        self.audit_events = []
        self.api_calls = []
        self.errors = []
        self.database_issues = []
        self.performance_data = []
        
    def parse_log_file(self):
        """解析日志文件"""
        if not self.log_file.exists():
            raise FileNotFoundError(f"日志文件不存在: {self.log_file}")
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    # 解析审计事件
                    if '🔍 AUDIT |' in line or 'LettaServerAudit' in line:
                        self._parse_audit_event(line, line_num)
                    
                    # 解析API调用
                    elif '"GET ' in line or '"POST ' in line or '"PUT ' in line or '"DELETE ' in line:
                        self._parse_api_call(line, line_num)
                    
                    # 解析错误信息
                    elif 'ERROR' in line or 'UNIQUE constraint failed' in line or 'could not open extension' in line:
                        self._parse_error(line, line_num)
                    
                    # 解析数据库问题
                    elif any(keyword in line for keyword in ['OpenGauss', 'postgresql', 'database', 'extension']):
                        self._parse_database_issue(line, line_num)
                
                except Exception as e:
                    print(f"解析第{line_num}行时出错: {e}")
                    continue
    
    def _parse_audit_event(self, line: str, line_num: int):
        """解析审计事件"""
        try:
            # 提取JSON部分
            json_start = line.find('{"id":')
            if json_start != -1:
                json_str = line[json_start:]
                audit_data = json.loads(json_str)
                audit_data['line_number'] = line_num
                self.audit_events.append(audit_data)
        except json.JSONDecodeError:
            pass
    
    def _parse_api_call(self, line: str, line_num: int):
        """解析API调用"""
        # 匹配API调用模式: IP - "METHOD PATH" STATUS
        pattern = r'(\d+\.\d+\.\d+\.\d+):\d+ - "([A-Z]+) ([^"]+)" (\d+)'
        match = re.search(pattern, line)
        
        if match:
            ip, method, path, status = match.groups()
            
            # 提取响应时间（如果有）
            response_time = None
            time_match = re.search(r'(\d+)ms', line)
            if time_match:
                response_time = int(time_match.group(1))
            
            self.api_calls.append({
                'line_number': line_num,
                'ip': ip,
                'method': method,
                'path': path,
                'status': int(status),
                'response_time': response_time,
                'timestamp': self._extract_timestamp(line)
            })
    
    def _parse_error(self, line: str, line_num: int):
        """解析错误信息"""
        error_data = {
            'line_number': line_num,
            'timestamp': self._extract_timestamp(line),
            'content': line,
            'type': 'unknown'
        }
        
        # 分类错误类型
        if 'UNIQUE constraint failed' in line:
            error_data['type'] = 'database_constraint'
        elif 'could not open extension control file' in line:
            error_data['type'] = 'database_extension'
        elif 'ERROR' in line and 'audit' in line.lower():
            error_data['type'] = 'audit_system'
        elif 'HTTP' in line:
            error_data['type'] = 'http_error'
        
        self.errors.append(error_data)
    
    def _parse_database_issue(self, line: str, line_num: int):
        """解析数据库相关问题"""
        issue_data = {
            'line_number': line_num,
            'timestamp': self._extract_timestamp(line),
            'content': line,
            'severity': 'info'
        }
        
        # 判断严重程度
        if 'ERROR' in line:
            issue_data['severity'] = 'error'
        elif 'WARNING' in line:
            issue_data['severity'] = 'warning'
        elif 'could not' in line or 'failed' in line:
            issue_data['severity'] = 'error'
        
        self.database_issues.append(issue_data)
    
    def _extract_timestamp(self, line: str) -> Optional[str]:
        """从日志行中提取时间戳"""
        # 匹配ISO时间戳
        iso_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)'
        match = re.search(iso_pattern, line)
        if match:
            return match.group(1)
        
        # 匹配简单时间戳
        simple_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
        match = re.search(simple_pattern, line)
        if match:
            return match.group(1)
        
        return None
    
    def analyze_audit_events(self) -> Dict:
        """分析审计事件"""
        if not self.audit_events:
            return {"message": "未找到审计事件"}
        
        # 事件类型统计
        event_types = Counter(event.get('event_type', 'unknown') for event in self.audit_events)
        
        # 风险分析
        risk_scores = [event.get('risk_score', 0) for event in self.audit_events]
        high_risk_events = [e for e in self.audit_events if e.get('risk_score', 0) >= 70]
        
        # 用户活动统计
        user_activities = defaultdict(int)
        for event in self.audit_events:
            user_id = event.get('user_id', 'anonymous')
            user_activities[user_id] += 1
        
        # 性能统计
        response_times = [e.get('response_time_ms') for e in self.audit_events if e.get('response_time_ms')]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        return {
            'total_events': len(self.audit_events),
            'event_types': dict(event_types.most_common(10)),
            'risk_analysis': {
                'high_risk_count': len(high_risk_events),
                'avg_risk_score': sum(risk_scores) / len(risk_scores) if risk_scores else 0,
                'max_risk_score': max(risk_scores) if risk_scores else 0
            },
            'user_activities': dict(user_activities),
            'performance': {
                'avg_response_time': round(avg_response_time, 2),
                'total_responses': len(response_times),
                'slow_requests': len([t for t in response_times if t > 1000])  # > 1秒
            }
        }
    
    def analyze_api_calls(self) -> Dict:
        """分析API调用"""
        if not self.api_calls:
            return {"message": "未找到API调用记录"}
        
        # 端点统计
        endpoints = Counter(call['path'] for call in self.api_calls)
        
        # 状态码统计
        status_codes = Counter(call['status'] for call in self.api_calls)
        
        # 性能分析
        response_times = [call['response_time'] for call in self.api_calls if call['response_time']]
        
        # 错误分析
        error_calls = [call for call in self.api_calls if call['status'] >= 400]
        
        return {
            'total_calls': len(self.api_calls),
            'top_endpoints': dict(endpoints.most_common(10)),
            'status_codes': dict(status_codes),
            'performance': {
                'avg_response_time': round(sum(response_times) / len(response_times), 2) if response_times else 0,
                'slow_requests': len([t for t in response_times if t > 1000])
            },
            'errors': {
                'count': len(error_calls),
                'error_endpoints': Counter(call['path'] for call in error_calls)
            }
        }
    
    def analyze_errors(self) -> Dict:
        """分析错误"""
        if not self.errors:
            return {"message": "未发现错误"}
        
        # 错误类型统计
        error_types = Counter(error['type'] for error in self.errors)
        
        # 数据库相关错误
        db_errors = [e for e in self.errors if 'database' in e['type']]
        audit_errors = [e for e in self.errors if e['type'] == 'audit_system']
        
        return {
            'total_errors': len(self.errors),
            'error_types': dict(error_types),
            'database_errors': len(db_errors),
            'audit_errors': len(audit_errors),
            'top_errors': [
                {
                    'type': error['type'],
                    'line': error['line_number'],
                    'content': error['content'][:100] + '...' if len(error['content']) > 100 else error['content']
                }
                for error in self.errors[:10]
            ]
        }
    
    def analyze_database_issues(self) -> Dict:
        """分析数据库问题"""
        if not self.database_issues:
            return {"message": "未发现数据库问题"}
        
        # 严重程度统计
        severity_count = Counter(issue['severity'] for issue in self.database_issues)
        
        # 扩展相关问题
        extension_issues = [i for i in self.database_issues if 'extension' in i['content']]
        opengauss_issues = [i for i in self.database_issues if 'OpenGauss' in i['content']]
        
        return {
            'total_issues': len(self.database_issues),
            'severity_distribution': dict(severity_count),
            'extension_issues': len(extension_issues),
            'opengauss_issues': len(opengauss_issues),
            'critical_issues': [
                {
                    'severity': issue['severity'],
                    'line': issue['line_number'],
                    'content': issue['content'][:150] + '...' if len(issue['content']) > 150 else issue['content']
                }
                for issue in self.database_issues if issue['severity'] == 'error'
            ]
        }
    
    def generate_report(self, output_file: str):
        """生成分析报告"""
        audit_analysis = self.analyze_audit_events()
        api_analysis = self.analyze_api_calls()
        error_analysis = self.analyze_errors()
        db_analysis = self.analyze_database_issues()
        
        report = f"""# 📊 Letta服务器日志分析报告
{'='*50}

## 🚀 服务器基本信息
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **日志文件**: {self.log_file}
- **总日志行数**: {sum(1 for _ in open(self.log_file, encoding='utf-8', errors='ignore'))}

## 📋 审计事件总览
- **总审计事件数**: {audit_analysis.get('total_events', 0)}
- **事件类型分布**:
"""
        
        for event_type, count in audit_analysis.get('event_types', {}).items():
            report += f"  - {event_type}: {count}\n"
        
        report += f"""
## 🌐 API调用统计
- **总API调用次数**: {api_analysis.get('total_calls', 0)}
- **热门API端点** (前10):
"""
        
        for endpoint, count in api_analysis.get('top_endpoints', {}).items():
            report += f"  - {endpoint}: {count}次\n"
        
        report += f"""
## 👥 用户活动统计
"""
        for user, count in audit_analysis.get('user_activities', {}).items():
            report += f"- {user}: {count}次活动\n"
        
        report += f"""
## 🤖 智能体活动统计
- 智能体相关API调用: {len([c for c in self.api_calls if 'agent' in c.get('path', '')])}
- 消息相关调用: {len([c for c in self.api_calls if 'message' in c.get('path', '')])}

## ⚡ 性能指标
- **平均响应时间**: {audit_analysis.get('performance', {}).get('avg_response_time', 0)}ms
- **慢请求数量**: {audit_analysis.get('performance', {}).get('slow_requests', 0)}
- **API平均响应时间**: {api_analysis.get('performance', {}).get('avg_response_time', 0)}ms

## ❌ 错误分析
- **系统错误总数**: {error_analysis.get('total_errors', 0)}
- **数据库相关问题**: {db_analysis.get('total_issues', 0)}
- **审计系统错误**: {error_analysis.get('audit_errors', 0)}

### 🔍 关键错误详情:
"""
        
        for error in error_analysis.get('top_errors', [])[:5]:
            report += f"- **{error['type']}** (行{error['line']}): {error['content']}\n"
        
        report += f"""
## 🗄️ 数据库问题分析
- **总问题数**: {db_analysis.get('total_issues', 0)}
- **扩展相关问题**: {db_analysis.get('extension_issues', 0)}
- **OpenGauss相关问题**: {db_analysis.get('opengauss_issues', 0)}

### 🚨 严重问题:
"""
        
        for issue in db_analysis.get('critical_issues', [])[:5]:
            report += f"- **{issue['severity'].upper()}** (行{issue['line']}): {issue['content']}\n"
        
        report += f"""
## ⏰ 活动时间分布
"""
        # 简单的时间分布统计
        hourly_stats = defaultdict(int)
        for event in self.audit_events:
            timestamp = event.get('timestamp', '')
            if timestamp:
                try:
                    hour = datetime.fromisoformat(timestamp.replace('Z', '')).hour
                    hourly_stats[hour] += 1
                except:
                    pass
        
        for hour in sorted(hourly_stats.keys()):
            report += f"- **{hour:02d}:00**: {hourly_stats[hour]}\n"
        
        report += f"""
## 📝 总结和建议
### 系统健康状态
- **整体状态**: {'良好 ✅' if error_analysis.get('total_errors', 0) < 10 else '需要关注 ⚠️'}
- **错误率**: {(error_analysis.get('total_errors', 0) / max(audit_analysis.get('total_events', 1), 1) * 100):.2f}%

### 🔧 紧急修复建议
1. **数据库兼容性**: 解决OpenGauss与PostgreSQL vector类型的兼容问题
2. **审计系统**: 优化审计事件ID生成，避免冲突
3. **性能优化**: 关注慢请求，优化响应时间
4. **监控增强**: 添加更详细的用户会话跟踪

## 🔍 审计系统评估
### 审计覆盖度
✅ **已覆盖的方面**:
- API调用追踪
- 智能体活动监控
- 风险评分评估
- 响应时间监控

⚠️ **待改进的方面**:
- 具体对话内容分析
- 金融敏感数据检测
- 用户身份验证审计
- 合规性检查

### 🛠️ 建议的下一步操作
1. 运行数据库兼容性修复工具: `python fix_opengauss_compatibility.py`
2. 重启letta服务器并观察错误是否减少
3. 实施用户身份验证审计
4. 添加金融文档特定的合规性检查
"""
        
        # 保存报告
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 分析报告已生成: {output_path}")
        
        # 返回分析摘要
        return {
            'audit_events': audit_analysis.get('total_events', 0),
            'api_calls': api_analysis.get('total_calls', 0),
            'errors': error_analysis.get('total_errors', 0),
            'database_issues': db_analysis.get('total_issues', 0)
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Letta服务器日志分析工具")
    parser.add_argument("--log-file", required=True, help="日志文件路径")
    parser.add_argument("--output", default="./logs/audit_analysis_report.md", help="输出报告文件路径")
    
    args = parser.parse_args()
    
    try:
        analyzer = LettaLogAnalyzer(args.log_file)
        print("📄 解析日志文件...")
        analyzer.parse_log_file()
        
        print("📊 生成分析报告...")
        summary = analyzer.generate_report(args.output)
        
        print("\n" + "="*50)
        print("📈 分析摘要:")
        print(f"- 审计事件: {summary['audit_events']}")
        print(f"- API调用: {summary['api_calls']}")
        print(f"- 错误数量: {summary['errors']}")
        print(f"- 数据库问题: {summary['database_issues']}")
        print("="*50)
        
    except Exception as e:
        print(f"❌ 分析过程中发生错误: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())