# JR.PDF 向量化处理和RAG系统

这是一个专门针对 `letta/examples/jr.pdf` 文件的向量化处理和检索增强生成（RAG）系统。

## 功能特性

- 🔄 **自动向量化**: 自动将 JR.PDF 文档进行文本提取和向量化
- 🧠 **智能问答**: 基于 Qwen3 模型的智能文档问答
- 🔍 **语义搜索**: 使用 BGE-M3 嵌入模型进行高精度语义搜索  
- 💾 **向量存储**: 向量数据自动存储到 OpenGauss 向量数据库
- 🛠️ **专用工具**: 文档搜索、摘要生成、要点提取等专用工具

## 模型配置

- **LLM模型**: `openai/qwen3`
- **嵌入模型**: `bge/bge-m3`
- **向量数据库**: OpenGauss

## 文件说明

### 主要文件

1. **`jr_rag_system.py`** - 完整的RAG系统实现
   - 向量化处理
   - RAG智能体创建
   - 交互式问答
   - 工具集成

2. **`quick_jr_test.py`** - 快速测试脚本
   - 简化的测试流程
   - 基本功能验证

3. **`jr_config_check.py`** - 环境配置检查
   - 系统环境验证
   - 配置完整性检查

## 使用方法

### 1. 环境检查

首先检查系统环境是否配置正确：

```bash
cd letta/examples
python jr_config_check.py
```

如果检查失败，查看设置说明：

```bash
python jr_config_check.py --setup
```

### 2. 快速测试

运行快速测试验证基本功能：

```bash
python quick_jr_test.py
```

### 3. 完整RAG系统

运行完整的RAG系统：

```bash
python jr_rag_system.py
```

## 系统要求

### 必需组件

1. **Letta服务器** - 需要运行在 `http://localhost:8283`
2. **JR.PDF文件** - 必须存在于 `letta/examples/jr.pdf`
3. **OpenGauss数据库** - 用于向量存储

### 环境变量

```bash
export OPENGAUSS_HOST=localhost
export OPENGAUSS_PORT=5432
export OPENGAUSS_DATABASE=letta
export OPENGAUSS_USERNAME=postgres
export OPENGAUSS_PASSWORD=your_password
```

## 工作流程

### 1. 向量化处理流程

```
PDF文档 → 文本提取 → 分块处理 → BGE-M3嵌入 → OpenGauss存储
```

### 2. RAG查询流程

```
用户问题 → 问题嵌入 → 向量检索 → 上下文构建 → Qwen3生成 → 回答输出
```

## 使用示例

### 基本问答

```python
from jr_rag_system import JRPDFRagSystem

# 创建RAG系统
rag = JRPDFRagSystem()

# 设置系统（包含向量化）
rag.setup()

# 提问
answer = rag.ask_question("JR.PDF文档的主要内容是什么？")
print(answer)

# 清理资源
rag.cleanup()
```

### 交互式模式

```python
# 进入交互式问答
rag.interactive_chat()
```

## 常见问题

### Q: 向量化失败怎么办？
A: 检查以下几点：
- PDF文件是否存在且可读
- Letta服务器是否正常运行
- 网络连接是否正常
- 模型服务是否可用

### Q: 无法连接到数据库？
A: 确认：
- OpenGauss服务正在运行
- 环境变量配置正确
- 数据库权限设置正确

### Q: 问答质量不理想？
A: 尝试：
- 重新进行向量化处理
- 调整问题的表述方式
- 检查文档内容是否完整

## 技术架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   JR.PDF    │───▶│  文本提取    │───▶│   分块处理   │
└─────────────┘    └──────────────┘    └─────────────┘
                                              │
┌─────────────┐    ┌──────────────┐          ▼
│ OpenGauss   │◀───│   向量存储    │    ┌─────────────┐
│  向量数据库  │    └──────────────┘    │  BGE-M3嵌入 │
└─────────────┘                       └─────────────┘
      ▲                                       │
      │                                       ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Qwen3     │◀───│   上下文构建  │◀───│   向量检索   │
│   回答生成   │    └──────────────┘    └─────────────┘
└─────────────┘                              ▲
                                             │
                              ┌──────────────┴──────────────┐
                              │        用户问题嵌入          │
                              └─────────────────────────────┘
```

## 扩展开发

如需自定义功能，可以：

1. **添加新工具** - 在 `create_rag_tools()` 方法中添加
2. **修改提示词** - 在 `create_rag_agent()` 中调整记忆块
3. **调整模型** - 修改模型参数配置
4. **增强搜索** - 改进向量检索逻辑

## 许可证

遵循 Letta 项目的许可证条款。
