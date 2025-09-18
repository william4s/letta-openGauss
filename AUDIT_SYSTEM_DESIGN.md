# RAG系统审计机制设计文档

## 概述

基于事件驱动的RAG系统审计机制，使用SQLite数据库记录从知识摄入到用户查询的完整生命周期，确保系统的可追溯性、安全性和合规性。

## 审计架构设计

### 1. 审计日志表结构（SQLite）

```sql
-- RAG系统主审计日志表
CREATE TABLE IF NOT EXISTS rag_audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT,
    user_id TEXT,
    event_type TEXT NOT NULL,
    source_identifier TEXT,
    status TEXT NOT NULL,
    user_question TEXT,
    llm_response TEXT,
    sensitive_score INTEGER DEFAULT 0,
    risk_level TEXT DEFAULT 'LOW',
    keywords_detected TEXT,
    response_time_ms INTEGER,
    document_chunks_used INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    metadata TEXT
);

-- 高风险事件表
CREATE TABLE IF NOT EXISTS high_risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    session_id TEXT,
    user_id TEXT,
    event_type TEXT,
    risk_description TEXT,
    content_hash TEXT,
    auto_blocked INTEGER,
    metadata TEXT
);

-- 系统操作审计表
CREATE TABLE IF NOT EXISTS system_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    operation_type TEXT,
    operator_id TEXT,
    target_resource TEXT,
    operation_details TEXT,
    success INTEGER,
    error_message TEXT
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON rag_audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON rag_audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_session_id ON rag_audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_risk_level ON rag_audit_logs(risk_level);
```

### 2. 核心审计事件类型

#### 2.1 知识库生命周期审计

| 事件类型 | 描述 | 记录字段 | 示例场景 |
|---------|------|---------|---------|
| `DOCUMENT_INGESTION` | 文档摄入 | source_identifier, metadata | PDF文档上传处理 |
| `DOCUMENT_PROCESSING` | 文档处理 | document_chunks_used, processing_time | 文档分块和向量化 |
| `MEMORY_BLOCK_CREATION` | Memory Block创建 | agent_id, block_count | 创建智能体记忆块 |
| `SYSTEM_STARTUP` | 系统启动 | system_config | RAG服务启动 |

#### 2.2 RAG查询流程审计

| 事件类型 | 描述 | 记录字段 | 示例场景 |
|---------|------|---------|---------|
| `USER_QUESTION` | 用户提问 | user_question, user_id, session_id | 用户提交问题 |
| `LLM_RESPONSE` | LLM回答 | llm_response, response_time_ms | LLM生成答案 |
| `CONVERSATION` | 完整对话 | 完整的问答对 | 问答交互完成 |
| `HIGH_RISK_DETECTED` | 高风险检测 | risk_description, sensitive_score | 检测到敏感内容 |

#### 2.3 安全审计

| 事件类型 | 描述 | 记录字段 | 示例场景 |
|---------|------|---------|---------|
| `SENSITIVE_CONTENT` | 敏感内容检测 | keywords_detected, sensitive_score | 检测敏感词汇 |
| `RISK_ASSESSMENT` | 风险评估 | risk_level, assessment_details | 评估对话风险 |
| `SECURITY_VIOLATION` | 安全违规 | violation_type, auto_blocked | 检测到安全威胁 |

### 3. 风险级别定义

- **LOW**: 敏感分数 0-1，正常对话
- **MEDIUM**: 敏感分数 2-4，包含部分敏感词汇
- **HIGH**: 敏感分数 5+，包含高风险内容或模式

## 审计实现架构

### 1. RAGAuditor类（SQLite版本）

```python
class RAGAuditor:
    """RAG系统专用审计器 - 基于SQLite"""
    
    def __init__(self, db_path: str = "./logs/rag_audit.db"):
        self.db_path = db_path
        self.init_database()
        
        # 敏感关键词列表
        self.sensitive_keywords = [
            "密码", "password", "身份证", "银行卡", "账号", 
            "个人信息", "隐私", "机密", "删除", "修改"
        ]
        
        # 风险模式正则表达式
        self.risk_patterns = [
            r".*如何.*绕过.*", r".*破解.*", r".*漏洞.*",
            r".*攻击.*", r".*黑客.*", r".*泄露.*"
        ]
    
    def log_conversation(self, user_question: str, llm_response: str, 
                        user_id: str = "anonymous", **kwargs):
        """记录完整对话到SQLite数据库"""
        
    def log_high_risk_event(self, event_type: str, description: str, 
                           content_hash: str, **kwargs):
        """记录高风险事件"""
        
    def calculate_sensitivity_score(self, text: str) -> tuple:
        """计算文本敏感度评分"""
```

### 2. AuditedMemoryBlockRAG类

```python
class AuditedMemoryBlockRAG:
    """带审计功能的Memory Blocks RAG系统"""
    
    def __init__(self, letta_url="http://localhost:8283"):
        self.auditor = RAGAuditor()
        self.client = Letta(base_url=letta_url)
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """PDF文本提取（带审计）"""
        # 记录文档摄入事件
        self.auditor.log_system_operation("DOCUMENT_INGESTION", 
                                         target_resource=pdf_path)
        
    def ask_question(self, question: str, user_id: str = "user") -> str:
        """问答处理（带完整审计）"""
        # 记录用户问题、LLM响应、风险评估
        response = self._process_question(question)
        self.auditor.log_conversation(question, response, user_id)
        return response
```

## 审计查询示例（SQLite）

### 1. 对话历史追踪

```sql
-- 查看最近的所有对话记录
SELECT 
    timestamp, 
    user_id,
    event_type,
    substr(user_question, 1, 50) || '...' as question_preview,
    substr(llm_response, 1, 50) || '...' as response_preview,
    risk_level,
    sensitive_score
FROM rag_audit_logs 
WHERE event_type = 'CONVERSATION'
ORDER BY timestamp DESC 
LIMIT 20;
```

### 2. 高风险事件监控

```sql
-- 查找高风险对话和安全事件
SELECT 
    timestamp,
    user_id,
    session_id,
    event_type,
    risk_level,
    sensitive_score,
    keywords_detected,
    ip_address
FROM rag_audit_logs 
WHERE risk_level = 'HIGH' 
   OR event_type IN ('HIGH_RISK_DETECTED', 'SECURITY_VIOLATION')
ORDER BY timestamp DESC;
```

### 3. 用户行为分析

```sql
-- 分析用户提问模式和敏感度
SELECT 
    user_id,
    COUNT(*) as total_questions,
    AVG(sensitive_score) as avg_sensitivity,
    MAX(sensitive_score) as max_sensitivity,
    COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high_risk_count,
    datetime(MAX(timestamp)) as last_activity
FROM rag_audit_logs 
WHERE event_type = 'CONVERSATION'
GROUP BY user_id
ORDER BY avg_sensitivity DESC, total_questions DESC;
```

### 4. 系统性能统计

```sql
-- 统计响应时间和成功率
SELECT 
    date(timestamp) as date,
    COUNT(*) as total_conversations,
    AVG(response_time_ms) as avg_response_time,
    AVG(document_chunks_used) as avg_chunks_used,
    COUNT(CASE WHEN risk_level = 'LOW' THEN 1 END) * 100.0 / COUNT(*) as safe_percentage
FROM rag_audit_logs 
WHERE event_type = 'CONVERSATION' 
  AND timestamp >= datetime('now', '-7 days')
GROUP BY date(timestamp)
ORDER BY date DESC;
```

### 5. 敏感词汇分析

```sql
-- 分析检测到的敏感关键词
SELECT 
    keywords_detected,
    COUNT(*) as occurrence_count,
    AVG(sensitive_score) as avg_score,
    COUNT(DISTINCT user_id) as affected_users
FROM rag_audit_logs 
WHERE keywords_detected IS NOT NULL 
  AND keywords_detected != ''
GROUP BY keywords_detected
ORDER BY occurrence_count DESC;
```

## 审计报告生成

### 自动生成的审计报告包含：

1. **会话概览**
   - 会话ID和时间范围
   - 事件总数和类型分布
   - 成功/失败统计

2. **事件时间线**
   - 按时间顺序列出所有事件
   - 每个事件的详细信息
   - 成功/失败状态指示

3. **数据流追踪**
   - 文档从摄入到存储的完整路径
   - 查询从接收到响应的处理流程
   - 相关哈希值用于数据完整性验证

### 示例审计报告格式

```markdown
# RAG系统审计报告

**会话ID**: a1b2c3d4
**生成时间**: 2024-03-15 14:30:25
**事件总数**: 15

## 事件时间线

### 14:25:10 - SYSTEM_STARTUP ✅
- **状态**: SUCCESS
- **源标识**: N/A
- **操作者**: system
- **详情**: {"letta_url": "http://localhost:8283", "db_config": {...}}

### 14:25:15 - INGESTION_START ⏳
- **状态**: PENDING
- **源标识**: document.pdf
- **操作者**: data_ingestion_service
- **详情**: {"file_hash": "abc123...", "file_size": 2048576}

### 14:25:18 - INGESTION_COMPLETE ✅
- **状态**: SUCCESS
- **源标识**: document.pdf
- **操作者**: data_ingestion_service
- **详情**: {"pages_extracted": 10, "total_characters": 50000}

...继续列出所有事件...
```

## 合规性和安全考虑

### 1. 数据隐私保护
- 查询文本仅存储哈希值，不存储明文
- 敏感信息识别和标记
- 用户身份信息匿名化处理

### 2. 数据完整性
- 使用SHA256哈希验证数据完整性
- 关键操作的前后状态记录
- 时间戳确保事件顺序的可追溯性

### 3. 审计日志安全
- 审计日志表的写入权限控制
- 日志记录的不可篡改性保证
- 定期备份和归档策略

### 4. 合规性检查
- 支持按时间范围生成合规报告
- 提供数据处理全生命周期追踪
- 满足GDPR等数据保护法规要求

## 使用示例

### 运行带审计功能的RAG系统

```bash
# 使用默认文档
python letta/examples/audited_memory_rag.py

# 指定PDF文档
python letta/examples/audited_memory_rag.py /path/to/document.pdf

# 系统会自动创建 ./logs/rag_audit.db SQLite数据库
# 并记录所有对话和操作事件
```

### 审计报告自动生成

系统会自动生成审计报告：
- 会话级别报告：每次运行后生成
- HTML报告：通过Web仪表板访问
- 高风险事件日志：实时记录到单独文件

### 数据库查询示例

```python
# 连接到SQLite审计数据库
import sqlite3

conn = sqlite3.connect('./logs/rag_audit.db')
cursor = conn.cursor()

# 查询最近的对话记录
cursor.execute("""
    SELECT timestamp, user_id, risk_level, sensitive_score 
    FROM rag_audit_logs 
    WHERE event_type = 'CONVERSATION' 
    ORDER BY timestamp DESC LIMIT 10
""")

for row in cursor.fetchall():
    print(f"时间: {row[0]}, 用户: {row[1]}, 风险: {row[2]}, 敏感度: {row[3]}")

conn.close()
```

### 审计仪表板

系统提供Web审计仪表板：
```bash
# 启动审计仪表板
python letta/examples/comprehensive_audit_dashboard.py

# 访问 http://localhost:8080 查看：
# - 实时对话监控
# - 风险事件统计
# - 用户行为分析
# - 系统性能指标
```

## 审计报告示例

### 自动生成的会话审计报告

```markdown
# RAG系统会话审计报告

**会话ID**: abc123def
**时间范围**: 2024-03-15 14:00:00 - 14:30:00
**总对话数**: 15
**高风险事件**: 2

## 对话统计

- **安全对话**: 13 (86.7%)
- **中风险对话**: 2 (13.3%)
- **高风险对话**: 0 (0%)

## 检测到的敏感词汇

1. "密码" - 2次
2. "个人信息" - 1次
3. "账号" - 1次

## 高风险事件详情

### 事件 #1: 2024-03-15 14:15:23
- **类型**: SENSITIVE_CONTENT
- **用户**: user_123
- **描述**: 检测到密码相关询问
- **处理**: 已记录，正常响应
```

这个基于SQLite的审计机制提供了完整的RAG系统可追溯性，具有以下优势：

1. **轻量级部署**：无需额外数据库服务，SQLite文件即可
2. **完整追踪**：记录从文档摄入到用户交互的全流程
3. **安全监控**：实时检测敏感内容和高风险行为
4. **性能监控**：统计响应时间和系统负载
5. **合规支持**：满足数据处理全生命周期审计要求