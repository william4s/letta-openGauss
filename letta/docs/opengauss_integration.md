# OpenGauss 向量数据库集成

本文档介绍如何在 Letta 项目中配置和使用 OpenGauss 作为向量数据库。

## 安装和配置

### 1. 安装依赖

```bash
# 安装 PostgreSQL 驱动 (推荐)
pip install psycopg2-binary

# 或者安装 OpenGauss 专用驱动
pip install py-opengauss
```

### 2. 配置环境变量

创建 `.env` 文件或设置以下环境变量：

```bash
# 启用 OpenGauss
ENABLE_OPENGAUSS=true

# OpenGauss 连接配置
OPENGAUSS_HOST=localhost
OPENGAUSS_PORT=5432
OPENGAUSS_DATABASE=letta
OPENGAUSS_USERNAME=postgres
OPENGAUSS_PASSWORD=your_password

# 可选配置
OPENGAUSS_TABLE_NAME=passage_embeddings
OPENGAUSS_SSL_MODE=prefer
```

### 3. 准备 OpenGauss 数据库

确保 OpenGauss 数据库已经启动并且可以连接。数据库和表结构会自动创建。

## 使用方法

### 1. 基本使用

```python
from letta.schemas.embedding_config import OpenGaussConfig
from letta.services.passage_manager import PassageManager

# 创建 OpenGauss 配置
opengauss_config = OpenGaussConfig(
    host="localhost",
    port=5432,
    database="letta",
    username="postgres",
    password="your_password"
)

# 初始化 PassageManager
passage_manager = PassageManager(opengauss_config=opengauss_config)
```

### 2. 自动配置

如果设置了环境变量，PassageManager 会自动从设置中读取配置：

```python
# 这会自动使用环境变量中的配置
passage_manager = PassageManager()
```

### 3. 服务器配置

Letta 服务器会自动检测 OpenGauss 配置并使用向量存储：

```python
# 服务器启动时会自动初始化 OpenGauss（如果配置了）
from letta.server.server import SyncServer

server = SyncServer()
# PassageManager 会自动配置 OpenGauss 向量存储
```

## 特性

### 1. 向量存储

- **自动同步**: 当创建新的 passage 时，embedding 会自动同步到 OpenGauss
- **批量操作**: 支持批量存储和查询向量
- **元数据支持**: 每个向量都可以存储相关的元数据

### 2. 向量搜索

- **余弦相似度**: 使用余弦相似度进行向量搜索
- **过滤支持**: 支持按 agent_id 或 source_id 过滤
- **性能优化**: 使用索引和优化的 SQL 查询

### 3. 数据管理

- **自动清理**: 删除 passage 时会自动清理向量数据
- **统计信息**: 提供向量存储的统计信息
- **错误处理**: 完善的错误处理和日志记录

## 数据库表结构

OpenGauss 会自动创建以下表结构：

```sql
CREATE TABLE passage_embeddings (
    id SERIAL PRIMARY KEY,
    passage_id VARCHAR(255) UNIQUE NOT NULL,
    embedding FLOAT[] NOT NULL,
    embedding_dim INTEGER NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_passage_embeddings_passage_id ON passage_embeddings(passage_id);
CREATE INDEX idx_passage_embeddings_embedding_dim ON passage_embeddings(embedding_dim);
```

## 性能优化

### 1. 连接池

考虑使用连接池来提高性能：

```python
# 在生产环境中，可以考虑使用 pgbouncer 或其他连接池
opengauss_config = OpenGaussConfig(
    host="localhost",
    port=5432,
    database="letta",
    username="postgres",
    password="your_password"
)
```

### 2. 索引优化

根据查询模式创建适当的索引：

```sql
-- 为特定维度的向量创建索引
CREATE INDEX idx_embeddings_1536 ON passage_embeddings(embedding_dim) WHERE embedding_dim = 1536;

-- 为元数据查询创建索引
CREATE INDEX idx_metadata_agent_id ON passage_embeddings USING GIN ((metadata->>'agent_id'));
```

### 3. 批量操作

使用批量操作来提高吞吐量：

```python
# 批量存储向量
embeddings_data = [
    (passage_id, embedding, metadata)
    for passage_id, embedding, metadata in data
]
passage_manager.vector_store.batch_store_embeddings(embeddings_data)
```

## 故障排除

### 1. 连接问题

```python
# 检查连接
try:
    passage_manager = PassageManager(opengauss_config=opengauss_config)
    if passage_manager.vector_store:
        print("✓ OpenGauss connected successfully")
    else:
        print("✗ Failed to connect to OpenGauss")
except Exception as e:
    print(f"Connection error: {e}")
```

### 2. 权限问题

确保数据库用户有适当的权限：

```sql
-- 授予必要的权限
GRANT CREATE, SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO your_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

### 3. 性能问题

监控查询性能：

```python
# 获取统计信息
stats = passage_manager.vector_store.get_stats()
print(f"Total embeddings: {stats['total_embeddings']}")
print(f"Distinct dimensions: {stats['distinct_dimensions']}")
```

## 兼容性

- **向后兼容**: 保持与现有 SQLite 存储的完全兼容
- **平滑切换**: 可以在 SQLite 和 OpenGauss 之间轻松切换
- **数据迁移**: 支持从 SQLite 迁移到 OpenGauss

## 配置选项

| 选项 | 默认值 | 描述 |
|------|--------|------|
| `ENABLE_OPENGAUSS` | `false` | 是否启用 OpenGauss |
| `OPENGAUSS_HOST` | `localhost` | 数据库主机 |
| `OPENGAUSS_PORT` | `5432` | 数据库端口 |
| `OPENGAUSS_DATABASE` | `letta` | 数据库名称 |
| `OPENGAUSS_USERNAME` | `postgres` | 用户名 |
| `OPENGAUSS_PASSWORD` | 必须设置 | 密码 |
| `OPENGAUSS_TABLE_NAME` | `passage_embeddings` | 表名 |
| `OPENGAUSS_SSL_MODE` | `prefer` | SSL 模式 |
