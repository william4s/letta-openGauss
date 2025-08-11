# Letta RAG系统安全审计机制

## 🔒 概述

为Letta RAG系统设计的企业级安全审计机制，提供全方位的用户行为监控、风险评估和合规性保障。特别适用于金融、医疗等对安全要求严格的应用场景。

## 🎯 核心功能

### ✅ 已实现功能

1. **用户行为审计**
   - 会话管理（登录/登出）
   - 操作追踪和记录
   - 查询内容监控
   - 文档访问日志

2. **安全风险评估**
   - 实时风险评分（0-100分）
   - 敏感数据自动检测
   - 异常行为识别
   - 高风险事件告警

3. **数据完整性保障**
   - 数据哈希校验
   - 操作时间戳记录
   - 审计日志防篡改

4. **合规性支持**
   - GDPR合规框架
   - HIPAA医疗合规
   - 数据生命周期管理
   - 审计报告生成

## 📁 文件结构

```
letta/examples/
├── security_audit.py              # 核心审计模块
├── audited_rag_system.py          # 带审计功能的RAG系统
├── web_audit_demo.py              # Web应用集成示例
├── audit_report_generator.py      # 审计报告生成工具
├── audit_config.yaml              # 配置文件
├── SECURITY_AUDIT_GUIDE.md        # 详细使用指南
├── README_SECURITY_AUDIT.md       # 本文件
└── logs/                           # 审计日志目录
    ├── security_audit.log          # 主审计日志
    ├── high_risk_events.log        # 高风险事件日志
    └── audit_database.db           # 审计数据库(可选)
```

## 🚀 快速开始

### 1. 基本使用

```python
from audited_rag_system import AuditedQuickRAG

# 创建带审计功能的RAG系统
rag = AuditedQuickRAG(
    user_id="user123",
    session_id="session_abc", 
    ip_address="192.168.1.100"
)

# 构建RAG系统（自动记录审计日志）
success = rag.build_rag_system("./document.pdf")

# 进行问答（自动记录查询和响应）
answer = rag.ask_question("这个产品的风险是什么？")

# 查看审计报告
report = rag.auditor.generate_audit_report(hours=24)
```

### 2. Web应用集成

```bash
# 启动Web演示应用
cd letta/examples
python web_audit_demo.py

# 访问 http://127.0.0.1:5000
# 使用任意用户ID和密码登录
```

### 3. 生成审计报告

```bash
# 生成HTML格式报告
python audit_report_generator.py --hours 24 --format html

# 生成合规性报告
python audit_report_generator.py --compliance gdpr
```

## 📊 审计事件类型

| 事件类型 | 描述 | 风险等级 |
|---------|------|---------|
| `USER_SESSION_START` | 用户登录/会话开始 | 低 |
| `USER_SESSION_END` | 用户登出/会话结束 | 低 |
| `DOCUMENT_UPLOAD` | 文档上传 | 中 |
| `DOCUMENT_ACCESS` | 文档访问/处理 | 中 |
| `QUERY_EXECUTION` | 查询执行 | 低-中 |
| `RAG_SEARCH` | RAG检索操作 | 低-高* |
| `AGENT_CREATION` | 智能体创建 | 中 |
| `AGENT_MESSAGE` | 智能体交互 | 低 |
| `DATA_EMBEDDING` | 向量化处理 | 中-高* |
| `SENSITIVE_DATA_ACCESS` | 敏感数据访问 | 高 |
| `SYSTEM_ERROR` | 系统错误 | 中-高 |

*风险等级根据内容动态调整

## ⚠️ 风险评分机制

### 风险等级划分
- **低风险 (0-39分)**: 正常操作，如普通查询、文档访问
- **中风险 (40-69分)**: 需要关注，如系统错误、重复操作  
- **高风险 (70-100分)**: 需要立即处理，如敏感数据访问、异常行为

### 风险因子
- **基础分数**: 根据操作类型确定
- **敏感数据**: +30分
- **高风险模式**: +25分（批量操作、权限提升等）
- **操作失败**: +20分
- **重复操作**: +15分

## 🔍 敏感数据检测

自动检测以下敏感信息：

**中文敏感词**
- 密码、身份证、银行卡、信用卡、手机号、邮箱
- 账号、账户、密钥、医疗记录、病历、诊断、处方

**英文敏感词**  
- password, ssn, bank_card, credit_card, phone, email
- account, pin, key, secret, token, medical, diagnosis

## 📈 审计日志格式

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

## 📋 审计报告示例

### 基本统计信息
- **报告期间**: 最近24小时
- **总事件数**: 150
- **活跃用户数**: 5  
- **系统健康**: 正常
- **高风险事件**: 3

### 风险分布
- **高风险**: 3 事件
- **中风险**: 25 事件
- **低风险**: 122 事件

### 用户行为分析
| 用户ID | 总事件 | 风险事件 | 平均风险评分 |
|--------|--------|----------|-------------|
| user123 | 45 | 2 | 25.3 |
| admin | 30 | 1 | 18.7 |

## 🛡️ 安全最佳实践

### 1. 部署安全
```bash
# 设置日志文件权限
chmod 640 logs/security_audit.log
chown letta:letta logs/security_audit.log

# 创建日志轮转配置
sudo vim /etc/logrotate.d/letta-audit
```

### 2. 配置优化
```yaml
# audit_config.yaml
audit_config:
  logging:
    enable_console: false  # 生产环境关闭控制台输出
    max_file_size: 100     # 限制日志文件大小
  
  retention:
    audit_logs_days: 90    # 审计日志保留90天
    sensitive_data_days: 30 # 敏感数据日志保留30天
```

### 3. 监控告警
```python
# 自定义高风险事件处理
def handle_high_risk_event(event):
    if event.risk_score >= 80:
        # 发送邮件告警
        send_alert_email(event)
        
        # 记录到安全事件数据库
        save_to_security_db(event)
        
        # 可选：临时限制用户权限
        # restrict_user_access(event.user_id)
```

## 🔧 高级配置

### 自定义敏感词
```python
from security_audit import get_auditor

auditor = get_auditor()
auditor.sensitive_keywords.extend([
    "公司机密", "内部文档", "confidential", "proprietary"
])
```

### 集成外部系统
```python
# 集成SIEM系统
def export_to_siem():
    report = auditor.generate_audit_report(hours=1)
    siem_client.send_events(report['high_risk_events'])

# 集成消息队列
def send_to_queue(event):
    if event.risk_score >= 70:
        message_queue.send('high_risk_events', event)
```

## 🧪 测试验证

### 功能测试
```bash
# 1. 基本功能测试
python audited_rag_system.py

# 2. Web应用测试  
python web_audit_demo.py

# 3. 敏感数据检测测试
# 输入包含敏感词的查询，验证风险评分提升

# 4. 报告生成测试
python audit_report_generator.py --hours 1
```

### 性能测试
```python
# 测试审计对性能的影响
import time

# 无审计版本
start_time = time.time()
# ... 执行操作
no_audit_time = time.time() - start_time

# 有审计版本  
start_time = time.time()
# ... 执行相同操作
with_audit_time = time.time() - start_time

performance_impact = (with_audit_time - no_audit_time) / no_audit_time * 100
print(f"审计性能影响: {performance_impact:.2f}%")
```

## 📞 故障排除

### 常见问题

1. **日志文件权限错误**
   ```bash
   sudo chown letta:letta logs/
   sudo chmod 755 logs/
   ```

2. **审计日志过大**
   ```bash
   # 配置日志轮转
   logrotate -f /etc/logrotate.d/letta-audit
   ```

3. **高风险误报**
   ```python
   # 调整敏感词库
   auditor.sensitive_keywords.remove("常见词")
   
   # 调整风险阈值
   auditor.high_risk_threshold = 80
   ```

### 调试模式
```python
import logging
logging.getLogger("SecurityAudit").setLevel(logging.DEBUG)

# 查看详细审计日志
tail -f logs/security_audit.log | grep DEBUG
```

## 🔄 版本更新

### v1.0 功能列表
- [x] 基础审计框架
- [x] 用户行为追踪
- [x] 风险评分系统
- [x] 敏感数据检测
- [x] 审计报告生成
- [x] Web应用集成
- [x] 配置文件支持

### 后续规划
- [ ] 机器学习异常检测
- [ ] 实时流式处理
- [ ] 分布式审计支持
- [ ] 更多合规框架支持
- [ ] 可视化监控面板

## 📚 相关文档

- [详细使用指南](SECURITY_AUDIT_GUIDE.md)
- [配置文件说明](audit_config.yaml)
- [Web集成示例](web_audit_demo.py)
- [报告生成工具](audit_report_generator.py)

## 🤝 贡献指南

1. Fork项目仓库
2. 创建功能分支
3. 提交代码更改
4. 创建Pull Request

## 📄 许可证

本项目采用与Letta主项目相同的许可证。

---

**注意**: 本安全审计机制为企业级功能，在生产环境部署前请进行充分测试，并根据具体的合规要求进行配置调整。
