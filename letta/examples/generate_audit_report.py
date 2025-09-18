#!/usr/bin/env python3
"""
RAG审计报告生成器
基于SQLite审计数据库生成详细的审计报告
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path


class RAGAuditReportGenerator:
    """RAG审计报告生成器"""
    
    def __init__(self, db_path: str = "./logs/rag_audit.db"):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"审计数据库不存在: {db_path}")
    
    def get_db_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def get_basic_statistics(self) -> dict:
        """获取基础统计信息"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # 总对话数
        cursor.execute("SELECT COUNT(*) FROM rag_audit_logs WHERE event_type = 'CONVERSATION'")
        stats['total_conversations'] = cursor.fetchone()[0]
        
        # 风险级别分布
        cursor.execute("""
            SELECT risk_level, COUNT(*) 
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION' 
            GROUP BY risk_level
        """)
        risk_distribution = dict(cursor.fetchall())
        stats['risk_distribution'] = risk_distribution
        
        # 活跃用户数
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) 
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION'
        """)
        stats['active_users'] = cursor.fetchone()[0]
        
        # 平均敏感度分数
        cursor.execute("""
            SELECT AVG(sensitive_score) 
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION'
        """)
        avg_score = cursor.fetchone()[0]
        stats['avg_sensitivity_score'] = round(avg_score, 2) if avg_score else 0
        
        # 平均响应时间
        cursor.execute("""
            SELECT AVG(response_time_ms) 
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION' AND response_time_ms IS NOT NULL
        """)
        avg_time = cursor.fetchone()[0]
        stats['avg_response_time_ms'] = round(avg_time, 2) if avg_time else 0
        
        conn.close()
        return stats
    
    def get_high_risk_events(self) -> list:
        """获取高风险事件"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, user_id, session_id, 
                   substr(user_question, 1, 100) as question_preview,
                   substr(llm_response, 1, 100) as response_preview,
                   sensitive_score, keywords_detected, ip_address
            FROM rag_audit_logs 
            WHERE risk_level = 'HIGH' 
               OR event_type = 'HIGH_RISK_DETECTED'
            ORDER BY timestamp DESC
        """)
        
        events = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'user_id': row[1],
                'session_id': row[2],
                'question_preview': row[3],
                'response_preview': row[4],
                'sensitive_score': row[5],
                'keywords_detected': row[6],
                'ip_address': row[7]
            }
            for row in events
        ]
    
    def get_user_activity_analysis(self) -> list:
        """获取用户活动分析"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(*) as total_questions,
                AVG(sensitive_score) as avg_sensitivity,
                MAX(sensitive_score) as max_sensitivity,
                COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high_risk_count,
                COUNT(CASE WHEN risk_level = 'MEDIUM' THEN 1 END) as medium_risk_count,
                datetime(MAX(timestamp)) as last_activity
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION'
            GROUP BY user_id
            ORDER BY avg_sensitivity DESC, total_questions DESC
        """)
        
        users = cursor.fetchall()
        conn.close()
        
        return [
            {
                'user_id': row[0],
                'total_questions': row[1],
                'avg_sensitivity': round(row[2], 2) if row[2] else 0,
                'max_sensitivity': row[3],
                'high_risk_count': row[4],
                'medium_risk_count': row[5],
                'last_activity': row[6]
            }
            for row in users
        ]
    
    def get_sensitive_keywords_analysis(self) -> list:
        """获取敏感关键词分析"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT keywords_detected, COUNT(*) as count
            FROM rag_audit_logs 
            WHERE keywords_detected IS NOT NULL 
              AND keywords_detected != '' 
              AND keywords_detected != '[]'
            GROUP BY keywords_detected
            ORDER BY count DESC
            LIMIT 20
        """)
        
        keywords = cursor.fetchall()
        conn.close()
        
        # 解析JSON关键词
        keyword_stats = {}
        for row in keywords:
            try:
                kw_list = json.loads(row[0])
                for kw in kw_list:
                    if kw in keyword_stats:
                        keyword_stats[kw] += row[1]
                    else:
                        keyword_stats[kw] = row[1]
            except:
                continue
        
        return sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)[:15]
    
    def get_time_series_analysis(self, days: int = 7) -> list:
        """获取时间序列分析"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                date(timestamp) as date,
                COUNT(*) as total_conversations,
                AVG(response_time_ms) as avg_response_time,
                AVG(sensitive_score) as avg_sensitivity,
                COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high_risk_count
            FROM rag_audit_logs 
            WHERE event_type = 'CONVERSATION' 
              AND timestamp >= datetime('now', '-{} days')
            GROUP BY date(timestamp)
            ORDER BY date DESC
        """.format(days))
        
        data = cursor.fetchall()
        conn.close()
        
        return [
            {
                'date': row[0],
                'total_conversations': row[1],
                'avg_response_time': round(row[2], 2) if row[2] else 0,
                'avg_sensitivity': round(row[3], 2) if row[3] else 0,
                'high_risk_count': row[4]
            }
            for row in data
        ]
    
    def generate_comprehensive_report(self) -> str:
        """生成综合审计报告"""
        # 获取所有数据
        stats = self.get_basic_statistics()
        high_risk_events = self.get_high_risk_events()
        user_analysis = self.get_user_activity_analysis()
        keyword_analysis = self.get_sensitive_keywords_analysis()
        time_analysis = self.get_time_series_analysis()
        
        # 生成报告
        report = f"""# RAG系统综合审计报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据库**: {self.db_path}

## 📊 总体统计

- **总对话数**: {stats['total_conversations']}
- **活跃用户数**: {stats['active_users']}
- **平均敏感度分数**: {stats['avg_sensitivity_score']}
- **平均响应时间**: {stats['avg_response_time_ms']}ms

### 风险级别分布

"""
        
        # 风险分布
        for risk_level, count in stats['risk_distribution'].items():
            percentage = (count / stats['total_conversations'] * 100) if stats['total_conversations'] > 0 else 0
            icon = "🟢" if risk_level == "LOW" else "🟡" if risk_level == "MEDIUM" else "🔴"
            report += f"- {icon} **{risk_level}**: {count} 次 ({percentage:.1f}%)\n"
        
        # 高风险事件
        report += f"""
## 🚨 高风险事件 ({len(high_risk_events)} 项)

"""
        
        if high_risk_events:
            for i, event in enumerate(high_risk_events[:10], 1):  # 只显示前10个
                report += f"""### 事件 #{i}
- **时间**: {event['timestamp']}
- **用户**: {event['user_id']}
- **敏感度分数**: {event['sensitive_score']}
- **检测关键词**: {event['keywords_detected']}
- **问题预览**: {event['question_preview']}...
- **IP地址**: {event['ip_address'] or 'N/A'}

"""
        else:
            report += "✅ 暂无高风险事件\n"
        
        # 用户活动分析
        report += f"""
## 👤 用户活动分析

"""
        
        for user in user_analysis[:10]:  # 只显示前10个用户
            risk_icon = "🔴" if user['high_risk_count'] > 0 else "🟡" if user['medium_risk_count'] > 0 else "🟢"
            report += f"""### {risk_icon} 用户: {user['user_id']}
- **总问题数**: {user['total_questions']}
- **平均敏感度**: {user['avg_sensitivity']}
- **最高敏感度**: {user['max_sensitivity']}
- **高风险对话**: {user['high_risk_count']} 次
- **中风险对话**: {user['medium_risk_count']} 次
- **最后活动**: {user['last_activity']}

"""
        
        # 敏感关键词分析
        report += f"""
## 🔍 敏感关键词检测统计

"""
        
        for keyword, count in keyword_analysis[:15]:
            report += f"- **{keyword}**: {count} 次\n"
        
        # 时间序列分析
        report += f"""
## 📈 时间趋势分析 (最近7天)

"""
        
        for day_data in time_analysis:
            report += f"""### {day_data['date']}
- **对话数**: {day_data['total_conversations']}
- **平均响应时间**: {day_data['avg_response_time']}ms
- **平均敏感度**: {day_data['avg_sensitivity']}
- **高风险事件**: {day_data['high_risk_count']}

"""
        
        report += f"""
## 🛡️ 安全建议

基于审计分析，提出以下安全建议：

"""
        
        # 基于数据生成建议
        if stats['avg_sensitivity_score'] > 2:
            report += "⚠️  **高敏感度警告**: 系统整体敏感度偏高，建议加强内容过滤\n"
        
        if len(high_risk_events) > 0:
            report += "🚨 **高风险事件关注**: 发现高风险事件，建议详细审查相关用户行为\n"
        
        high_risk_users = [u for u in user_analysis if u['high_risk_count'] > 0]
        if high_risk_users:
            report += f"👤 **重点用户监控**: {len(high_risk_users)} 名用户有高风险行为，建议重点关注\n"
        
        if stats['avg_response_time_ms'] > 5000:
            report += "⏱️  **性能优化**: 平均响应时间较长，建议优化系统性能\n"
        
        report += """
✅ **系统运行正常**: 审计机制工作正常，持续监控中

---

*此报告由RAG审计系统自动生成*
"""
        
        return report


def main():
    """主函数 - 生成审计报告"""
    db_path = "./logs/rag_audit.db"
    
    if not os.path.exists(db_path):
        print(f"❌ 审计数据库不存在: {db_path}")
        print("请先运行RAG系统以生成审计数据")
        return
    
    try:
        generator = RAGAuditReportGenerator(db_path)
        report = generator.generate_comprehensive_report()
        
        # 保存报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"./logs/comprehensive_audit_report_{timestamp}.md"
        
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 综合审计报告已生成: {report_path}")
        
        # 显示简要统计
        stats = generator.get_basic_statistics()
        print("\n📊 审计数据概览:")
        print(f"   总对话数: {stats['total_conversations']}")
        print(f"   活跃用户: {stats['active_users']}")
        print(f"   平均敏感度: {stats['avg_sensitivity_score']}")
        print(f"   风险分布: {stats['risk_distribution']}")
        
    except Exception as e:
        print(f"❌ 生成报告时出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()