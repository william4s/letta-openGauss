# OpenGauss 数据库初始化功能

本文档描述了在 Letta 项目启动时增加的 OpenGauss 数据库初始化功能，该功能类似于 SQLite 的初始化方式。

## 功能概述

### 自动数据库初始化

在项目启动时，如果启用了 OpenGauss（`ENABLE_OPENGAUSS=true`），系统会自动执行以下初始化步骤：

1. **数据库创建**: 检查目标数据库是否存在，如果不存在则自动创建
2. **扩展启用**: 尝试启用必要的 PostgreSQL 扩展（vector、uuid-ossp）
3. **表结构创建**: 运行 Alembic 迁移创建所有必要的表结构

### 与 SQLite 的对比

| 特性 | SQLite | OpenGauss |
|------|--------|-----------|
| 数据库文件 | 自动创建 | 自动创建数据库 |
| 表结构 | `Base.metadata.create_all()` | Alembic 迁移 |
| 扩展支持 | 无 | 自动启用向量扩展 |
| 错误处理 | 包装异常 | 详细日志记录 |

## 实现细节

### 核心函数

#### `ensure_opengauss_database_exists()`
- 连接到默认的 `postgres` 数据库
- 检查目标数据库是否存在
- 如果不存在，创建目标数据库
- 连接到目标数据库并启用必要的扩展

#### `run_alembic_migrations_for_opengauss()`
- 运行 `alembic upgrade head` 命令
- 创建所有必要的表结构
- 处理迁移错误和警告

#### `initialize_opengauss_database()`
- 协调整个初始化流程
- 提供统一的错误处理和日志记录

### 集成点

修改了 `DatabaseRegistry` 类的以下方法：

#### `initialize_sync()`
```python
# 在创建 PostgreSQL 引擎前检查 OpenGauss 配置
if settings.enable_opengauss:
    if not initialize_opengauss_database():
        raise RuntimeError("OpenGauss database initialization failed")
```

#### `initialize_async()`
```python
# 避免重复初始化，只在同步未初始化时执行
if settings.enable_opengauss and not self._initialized.get("sync"):
    if not initialize_opengauss_database():
        raise RuntimeError("OpenGauss database initialization failed")
```

## 配置要求

### 环境变量

```bash
# 启用 OpenGauss
ENABLE_OPENGAUSS=true

# 连接配置
OPENGAUSS_HOST=localhost
OPENGAUSS_PORT=5432
OPENGAUSS_DATABASE=letta
OPENGAUSS_USERNAME=opengauss
OPENGAUSS_PASSWORD=your_password

# PostgreSQL URI（必须）
LETTA_PG_URI=postgresql://opengauss:your_password@localhost:5432/letta
```

### 依赖项

```bash
pip install psycopg2-binary  # PostgreSQL 驱动
```

## 使用方法

### 自动初始化

当项目启动时（如运行服务器或使用数据库功能），初始化会自动执行：

```python
from letta.server.db import db_registry

# 这会自动触发初始化
with db_registry.session() as session:
    # 数据库已经准备就绪
    pass
```

### 手动测试

使用提供的测试脚本：

```bash
python letta/examples/test_opengauss_initialization.py
```

## 错误处理

### 常见错误和解决方案

1. **连接失败**
   - 检查 OpenGauss 服务是否运行
   - 验证连接参数

2. **权限不足**
   - 确保用户有创建数据库的权限
   - 检查表创建权限

3. **迁移失败**
   - 手动运行 `alembic upgrade head`
   - 检查项目根目录和 alembic.ini 文件

## 兼容性

### 向后兼容
- 不影响现有的 SQLite 功能
- 可以在 SQLite 和 OpenGauss 之间切换
- 保持现有 API 不变

### 部署兼容
- Docker 环境支持
- 开发环境支持
- 生产环境支持

## 监控和日志

### 日志级别
- `INFO`: 正常初始化步骤
- `WARNING`: 可选功能失败（如扩展）
- `ERROR`: 严重错误需要处理

### 日志示例
```
INFO - OpenGauss is enabled, initializing database...
INFO - Database 'letta' already exists
INFO - ✓ Vector extension enabled
INFO - ✓ Alembic migrations completed successfully
INFO - ✓ OpenGauss database 'letta' is ready for use
```

## 测试

### 自动化测试
- 数据库创建测试
- 扩展启用测试
- 迁移执行测试
- 连接验证测试

### 手动测试
- 全新数据库初始化
- 现有数据库检查
- 错误场景处理

## 性能考虑

### 初始化性能
- 数据库创建: 一次性操作
- 迁移执行: 依赖表数量
- 扩展启用: 快速操作

### 运行时性能
- 无额外开销
- 与普通 PostgreSQL 性能相同
- 向量操作优化（如果支持向量扩展）
