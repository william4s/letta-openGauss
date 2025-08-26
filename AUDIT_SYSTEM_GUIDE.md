# Letta服务器审计系统使用文档

## 概述

Letta审计系统是为金融文档RAG系统专门设计的安全审计和合规监控解决方案。系统能够实时监控用户行为、文档访问、系统操作等，并自动生成详细的审计报告。

## 功能特性

### ✅ 核心功能
- **实时审计监控**: 自动记录所有用户操作和系统事件
- **金融内容分析**: 智能识别金融关键词和敏感信息
- **风险评分**: 基于多维度算法计算每个事件的风险级别(0-100)
- **合规性检查**: 自动检测金融文档的合规性问题
- **审计报告生成**: 支持HTML、JSON、CSV格式的详细报告
- **实时统计**: 提供系统健康状态和关键指标的实时监控

### 🔍 专门针对金融场景
- **理财产品说明书审计**: 专门针对人民币理财产品等金融文档
- **敏感数据检测**: 自动识别身份证、银行卡等敏感信息
- **合规违规监控**: 检测缺失的风险揭示、费用说明等合规要求
- **高风险事件告警**: 自动标记和处理高风险操作

## 安装和配置

### 1. 系统依赖
审计系统已集成到Letta服务器中，无需额外安装。

### 2. 启动审计系统
当Letta服务器启动时，审计系统会自动初始化：

```bash
letta server
```

系统启动后会看到：
```
🔍 Letta服务器审计系统已启动
```

### 3. 配置选项
审计系统支持以下配置（可在代码中修改）：

```python
from letta.server.audit_system import ServerAuditSystem

audit_system = ServerAuditSystem(
    audit_log_path="./logs/letta_server_audit.log",  # 审计日志文件路径
    audit_db_path="./logs/letta_audit.db",           # 审计数据库路径
    enable_real_time_monitoring=True                  # 启用实时监控
)
```

## API接口

### 1. 审计系统健康状态
```http
GET /v1/audit/health
```

**响应示例：**
```json
{
  "status": "healthy",
  "audit_system_active": true,
  "database_connected": true,
  "uptime_hours": 2.5
}
```

### 2. 实时统计信息
```http
GET /v1/audit/stats
```

**响应示例：**
```json
{
  "total_events": 156,
  "high_risk_events": 3,
  "financial_events": 45,
  "compliance_violations": 2,
  "uptime_hours": 2.5
}
```

### 3. 生成审计报告
```http
GET /v1/audit/report?hours=24&format=html
```

**查询参数：**
- `hours`: 报告时间范围（小时），默认24
- `format`: 输出格式（html/json/csv），默认html

### 4. 金融专用报告
```http
GET /v1/audit/financial-report?hours=24
```

**响应包含：**
- 金融文档访问统计
- 理财产品查询分析
- 风险相关查询统计
- 合规违规详情

### 5. 合规性报告
```http
GET /v1/audit/compliance-report?hours=24
```

## 在代码中使用审计系统

### 1. 记录审计事件

```python
from letta.server.audit_system import log_server_event, AuditEventType, AuditLevel

# 记录用户登录
log_server_event(
    event_type=AuditEventType.USER_SESSION_START,
    level=AuditLevel.INFO,
    action="user_login",
    user_id="user123",
    session_id="session456",
    ip_address="192.168.1.100",
    details={"login_method": "password"}
)

# 记录金融文档访问
log_server_event(
    event_type=AuditEventType.FINANCIAL_DATA_ACCESS,
    level=AuditLevel.COMPLIANCE,
    action="product_info_query",
    user_id="user123",
    resource="jr.pdf",
    data_content="理财产品风险等级查询",
    details={
        "product_type": "理财产品",
        "query_category": "风险信息"
    }
)
```

### 2. 使用装饰器自动审计

```python
from letta.server.audit_system import audit_api_call, AuditEventType

@audit_api_call(AuditEventType.AGENT_MESSAGE, "create_agent")
def create_agent(request):
    # 函数逻辑
    return agent
```

### 3. 获取审计系统实例

```python
from letta.server.audit_system import get_audit_system

audit_system = get_audit_system()

# 生成报告
report = audit_system.generate_audit_report(hours=24)

# 获取实时统计
stats = audit_system.get_real_time_stats()
```

## 事件类型说明

### 用户会话事件
- `USER_SESSION_START`: 用户会话开始
- `USER_SESSION_END`: 用户会话结束
- `AUTHENTICATION`: 用户认证

### 文档操作事件
- `DOCUMENT_UPLOAD`: 文档上传
- `DOCUMENT_ACCESS`: 文档访问
- `DOCUMENT_PROCESSING`: 文档处理

### RAG操作事件
- `RAG_QUERY`: RAG查询
- `RAG_SEARCH`: 相似性搜索
- `RAG_RESPONSE`: RAG响应

### 金融特定事件
- `FINANCIAL_DATA_ACCESS`: 金融数据访问
- `RISK_ASSESSMENT_QUERY`: 风险评估查询
- `PRODUCT_INFO_QUERY`: 产品信息查询
- `COMPLIANCE_CHECK`: 合规性检查

### 系统事件
- `SYSTEM_ERROR`: 系统错误
- `AGENT_CREATION`: 智能体创建
- `AGENT_MESSAGE`: 智能体消息

## 风险评分说明

系统为每个事件计算风险分数（0-100分）：

- **0-39分**: 低风险（绿色）
- **40-69分**: 中风险（黄色）
- **70-100分**: 高风险（红色）

### 风险评分因素：
1. **事件类型基础分数**
2. **金融内容敏感性**
3. **操作成功/失败状态**
4. **重复操作频率**
5. **合规性问题**

## 金融内容分析

系统能够自动分析金融文档内容：

### 识别的金融类别：
- `product_info`: 产品信息
- `risk_terms`: 风险相关
- `compliance`: 合规条款
- `sensitive_data`: 敏感数据
- `amount_terms`: 金额条款

### 合规性检查项：
- `missing_risk_disclosure`: 缺失风险揭示
- `missing_product_description`: 缺失产品说明
- `missing_fee_structure`: 缺失费用结构
- `missing_redemption_terms`: 缺失赎回条款

## 报告和日志

### 1. 审计日志文件
- **位置**: `./logs/letta_server_audit.log`
- **格式**: 结构化JSON格式
- **内容**: 所有审计事件的详细记录

### 2. 审计数据库
- **位置**: `./logs/letta_audit.db`
- **类型**: SQLite数据库
- **表结构**: 包含所有审计事件字段

### 3. HTML报告
生成的HTML报告包含：
- 概览统计图表
- 事件类型分布
- 用户活动分析
- 高风险事件详情
- 合规违规记录
- 系统健康状态

## 实际使用场景

### 1. 启动Letta服务器

```bash
# 启动服务器（审计系统自动启动）
letta server

# 查看审计日志
tail -f ./logs/letta_server_audit.log
```

### 2. 使用Quick RAG系统

```bash
# 运行集成审计的RAG系统
python letta/examples/audited_quick_rag.py
```

### 3. 查看审计报告

```bash
# 生成审计报告
python letta/server/audit_report_generator.py --hours 24 --format html

# 生成合规性报告
python letta/server/audit_report_generator.py --compliance --hours 24
```

### 4. 通过API访问

```bash
# 获取实时统计
curl http://localhost:8283/v1/audit/stats

# 生成审计报告
curl "http://localhost:8283/v1/audit/report?hours=24&format=json"

# 检查系统健康
curl http://localhost:8283/v1/audit/health
```

## 监控和告警

### 高风险事件自动处理
- 风险分数≥70的事件会自动触发告警
- 告警信息记录到专门的高风险事件日志
- 控制台显示实时告警信息

### 合规违规监控
- 自动检测金融文档的合规性问题
- 标记缺失的必要披露信息
- 生成专门的合规性报告

## 最佳实践

### 1. 定期监控
- 建议每日查看审计报告
- 重点关注高风险事件和合规违规
- 监控系统健康状态

### 2. 数据保护
- 定期备份审计日志和数据库
- 确保审计数据的完整性
- 保护敏感信息不被泄露

### 3. 性能优化
- 定期清理旧的审计数据
- 监控审计系统的性能影响
- 根据需要调整监控级别

## 故障排除

### 常见问题

1. **审计系统未启动**
   - 检查日志中是否有"🔍 Letta服务器审计系统已启动"
   - 确认审计数据库文件权限

2. **报告生成失败**
   - 检查数据库连接
   - 确认报告输出目录权限

3. **高风险事件过多**
   - 检查风险评分配置
   - 分析事件模式调整阈值

### 日志位置
- 审计日志: `./logs/letta_server_audit.log`
- 高风险事件: `./logs/high_risk_events.log`
- 审计数据库: `./logs/letta_audit.db`
- 审计报告: `./reports/`

## 总结

Letta审计系统为金融文档RAG应用提供了完整的安全审计解决方案。通过实时监控、智能分析和自动报告，帮助确保系统的安全性和合规性。系统已完全集成到Letta服务器中，开箱即用，为金融场景下的文档问答系统提供了强有力的安全保障。
