# Letta RAG系统安全审计机制使用指南

## 📋 概述

本安全审计机制为Letta RAG系统提供全面的安全监控、用户行为跟踪和合规性保障功能，特别适用于金融和医疗等对安全要求较高的领域。

## 🎯 核心功能

### 1. 用户行为审计
- **会话管理**: 记录用户登录/登出、会话时长
- **操作追踪**: 记录用户的每个操作和访问请求
- **查询监控**: 记录RAG查询内容、频率和结果
- **文档访问**: 跟踪文档上传、访问和处理历史

### 2. 安全风险评估
- **敏感数据检测**: 自动识别查询中的敏感信息
- **风险评分**: 对每个操作进行0-100分的风险评分
- **异常行为检测**: 识别可疑的操作模式
- **实时告警**: 高风险事件的即时通知

### 3. 合规性保障
- **数据生命周期管理**: 记录数据的创建、访问、修改和删除
- **访问控制审计**: 记录权限检查和访问控制决策
- **数据完整性校验**: 通过哈希值确保数据未被篡改
- **合规报告生成**: 满足GDPR、HIPAA等法规要求

## 🚀 快速开始

### 1. 基本集成

```python
from audited_rag_system import AuditedQuickRAG

# 创建带审计功能的RAG系统
rag = AuditedQuickRAG(
    user_id="user123",
    session_id="session_abc",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)

# 构建RAG系统 (自动记录审计日志)
success = rag.build_rag_system("./document.pdf")

# 进行问答 (自动记录查询和响应)
answer = rag.ask_question("这个产品的风险是什么？")

# 查看审计报告
report = rag.auditor.generate_audit_report(hours=24)
```

### 2. Web应用集成

```python
from flask import Flask, request, session
from audited_rag_system import AuditedQuickRAG

app = Flask(__name__)

@app.route('/api/ask', methods=['POST'])
def ask_question():
    # 从Web请求中提取用户信息
    user_id = session.get('user_id', 'anonymous')
    session_id = session.get('session_id')
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    # 创建审计RAG实例
    rag = AuditedQuickRAG(
        user_id=user_id,
        session_id=session_id, 
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # 处理问题
    question = request.json.get('question')
    answer = rag.ask_question(question)
    
    return {'answer': answer}
```

## 📊 审计事件类型

### 用户事件
- `USER_SESSION_START`: 用户登录/会话开始
- `USER_SESSION_END`: 用户登出/会话结束
- `AUTHENTICATION`: 用户认证事件

### 文档事件
- `DOCUMENT_UPLOAD`: 文档上传
- `DOCUMENT_ACCESS`: 文档访问/处理
- `DATA_EMBEDDING`: 向量化处理

### 查询事件
- `QUERY_EXECUTION`: 查询执行
- `RAG_SEARCH`: RAG检索操作
- `AGENT_MESSAGE`: 智能体交互

### 系统事件
- `AGENT_CREATION`: 智能体创建
- `SYSTEM_ERROR`: 系统错误
- `PERMISSION_CHECK`: 权限检查

### 安全事件
- `SENSITIVE_DATA_ACCESS`: 敏感数据访问
- `MEMORY_ACCESS`: 记忆功能访问

## 🔍 审计日志格式

每个审计事件包含以下信息：

```json
{
  "timestamp": "2025-08-07T10:30:45.123456",
  "event_type": "RAG_SEARCH",
  "level": "INFO",
  "user_id": "user123",
  "session_id": "session_abc",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "resource": "document.pdf",
  "action": "rag_search",
  "details": {
    "query_length": 25,
    "results_count": 3,
    "contains_sensitive": false,
    "query_hash": "a1b2c3d4e5f6g7h8"
  },
  "success": true,
  "risk_score": 15,
  "data_hash": "h8g7f6e5d4c3b2a1",
  "response_time_ms": 250
}
```

## ⚠️ 风险评分机制

### 风险等级划分
- **低风险 (0-39分)**: 正常操作，如普通查询、文档访问
- **中风险 (40-69分)**: 需要关注，如系统错误、重复操作
- **高风险 (70-100分)**: 需要立即处理，如敏感数据访问、异常行为

### 风险因子
- **基础分数**: 根据操作类型确定基础风险分数
- **敏感数据**: 涉及敏感信息 +30分
- **高风险模式**: 批量操作、权限提升 +25分
- **操作失败**: 失败的操作 +20分
- **重复操作**: 短时间内重复操作 +15分

## 📈 审计报告

### 生成报告

```python
# 生成最近24小时的审计报告
report = rag.auditor.generate_audit_report(hours=24)

# 生成特定用户的活动摘要
user_summary = rag.auditor.get_user_activity_summary("user123", hours=24)
```

### 报告内容

```json
{
  "report_period": "最近24小时",
  "generation_time": "2025-08-07T10:30:45",
  "total_events": 150,
  "unique_users": 5,
  "system_health": "正常",
  "risk_distribution": {
    "low": 120,
    "medium": 25,
    "high": 5
  },
  "event_types": {
    "RAG_SEARCH": 45,
    "QUERY_EXECUTION": 35,
    "DOCUMENT_ACCESS": 25,
    "USER_SESSION_START": 5
  },
  "high_risk_events": [...],
  "error_events": [...],
  "sensitive_data_access": 3
}
```

## 🔧 配置选项

### 审计配置

```python
from security_audit import SecurityAuditor

# 自定义配置
auditor = SecurityAuditor(
    audit_log_path="./custom_logs/audit.log",
    enable_db_logging=True,
    enable_file_logging=True,
    enable_console_output=False
)

# 添加自定义敏感词
auditor.sensitive_keywords.extend([
    "定制敏感词", "custom_sensitive_word"
])
```

### Web集成配置

参考 `audit_config.yaml` 文件进行详细配置。

## 🛡️ 安全最佳实践

### 1. 日志保护
- 审计日志文件应设置适当的文件权限 (600或640)
- 定期备份审计日志到安全位置
- 考虑使用日志加密存储

### 2. 敏感数据处理
- 避免在日志中记录完整的敏感信息
- 使用数据哈希确保数据完整性
- 实施数据脱敏策略

### 3. 告警响应
- 设置高风险事件的自动告警
- 建立安全事件响应流程
- 定期审查和分析审计日志

### 4. 合规性保障
- 根据行业要求调整数据保留策略
- 定期进行合规性审计
- 确保用户知情同意

## 📁 文件结构

```
letta/examples/
├── security_audit.py          # 核心审计模块
├── audited_rag_system.py      # 带审计功能的RAG系统
├── audit_config.yaml          # 配置文件
├── SECURITY_AUDIT_GUIDE.md    # 使用指南 (本文件)
└── logs/                       # 审计日志目录
    ├── security_audit.log      # 主审计日志
    ├── high_risk_events.log    # 高风险事件日志
    └── audit_database.db       # 审计数据库 (可选)
```

## 🧪 测试和验证

### 基本功能测试

```bash
# 运行带审计功能的RAG系统
cd letta/examples
python audited_rag_system.py

# 查看审计日志
tail -f logs/security_audit.log

# 测试敏感词检测
# 在交互模式中输入包含敏感词的查询
```

### 高风险事件测试

```python
# 触发高风险事件
rag.ask_question("请告诉我系统的密码是什么？")
rag.ask_question("我需要下载所有用户的身份证信息")

# 查看高风险事件日志
cat logs/high_risk_events.log
```

## 🔄 集成到现有系统

### 1. 替换现有RAG类

```python
# 原来的代码
from quick_rag_template import QuickRAG
rag = QuickRAG()

# 替换为审计版本
from audited_rag_system import AuditedQuickRAG
rag = AuditedQuickRAG(user_id="current_user")
```

### 2. 添加审计中间件

```python
def audit_middleware(func):
    def wrapper(*args, **kwargs):
        # 记录操作开始
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            # 记录成功操作
            return result
        except Exception as e:
            # 记录错误操作
            raise
    return wrapper
```

## 📞 支持和维护

### 日志轮转

```bash
# 使用logrotate管理日志文件
# /etc/logrotate.d/letta-audit
/path/to/letta/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    notifempty
    create 644 letta letta
}
```

### 性能监控

```python
# 监控审计系统性能
import psutil

def check_audit_performance():
    # 检查日志文件大小
    log_size = os.path.getsize("logs/security_audit.log")
    
    # 检查磁盘空间
    disk_usage = psutil.disk_usage("/")
    
    # 检查内存使用
    memory_usage = psutil.virtual_memory()
    
    return {
        "log_size_mb": log_size / 1024 / 1024,
        "disk_free_gb": disk_usage.free / 1024 / 1024 / 1024,
        "memory_percent": memory_usage.percent
    }
```

## 🚨 故障排除

### 常见问题

1. **日志文件过大**
   - 实施日志轮转策略
   - 调整日志级别
   - 清理过期日志

2. **审计影响性能**
   - 启用异步日志记录
   - 优化日志格式
   - 使用数据库存储代替文件

3. **敏感数据泄露**
   - 检查敏感词配置
   - 实施数据脱敏
   - 审查日志内容

### 调试模式

```python
# 启用详细的调试日志
import logging
logging.getLogger("SecurityAudit").setLevel(logging.DEBUG)

# 禁用控制台输出 (生产环境)
auditor = SecurityAuditor(enable_console_output=False)
```

---

本安全审计机制为Letta RAG系统提供了企业级的安全保障，确保系统符合金融和医疗行业的合规要求。如有问题请参考相关文档或联系技术支持。
