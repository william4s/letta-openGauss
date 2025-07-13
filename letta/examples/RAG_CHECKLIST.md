# RAG系统构建检查清单

## 🚀 快速开始检查清单

### ✅ 环境准备
- [ ] Python 3.8+ 已安装
- [ ] 必要Python包已安装:
  ```bash
  pip install letta-client pypdf requests psycopg2-binary
  ```

### ✅ 服务检查
- [ ] **Letta服务器**运行正常
  ```bash
  curl http://localhost:8283/health
  ```
- [ ] **BGE-M3 Embedding服务**运行正常
  ```bash
  curl http://127.0.0.1:8003/v1/models
  ```
- [ ] **Qwen3 LLM**通过Letta可访问

### ✅ 数据准备
- [ ] 目标文档已准备 (PDF/TXT格式)
- [ ] 文档内容清晰可读
- [ ] 文档大小适中 (建议<10MB)

### ✅ 配置检查
- [ ] OpenGauss环境变量已设置 (可选)
  ```bash
  export OPENGAUSS_HOST=localhost
  export OPENGAUSS_PORT=5432
  export OPENGAUSS_DATABASE=letta
  export OPENGAUSS_USERNAME=postgres
  export OPENGAUSS_PASSWORD=your_password
  ```

## 🔍 验证步骤

### 1. 环境验证
```bash
cd letta/examples
python jr_config_check.py
```
应该看到大部分检查通过。

### 2. Embedding测试
```bash
python debug_embedding.py
```
应该看到BGE-M3模型正常调用。

### 3. 完整RAG测试
```bash
python direct_embedding_rag.py
```
或
```bash
python quick_rag_template.py
```

## 📋 构建步骤

### 方法一：使用现成的脚本 (推荐)

```bash
# 使用已验证的完整RAG系统
python direct_embedding_rag.py

# 或使用简化的快速模板
python quick_rag_template.py
```

### 方法二：自定义构建

1. **创建RAG类**
   ```python
   from quick_rag_template import QuickRAG
   rag = QuickRAG()
   ```

2. **构建系统**
   ```python
   success = rag.build_rag_system("./your_document.pdf")
   ```

3. **开始问答**
   ```python
   answer = rag.ask_question("您的问题")
   ```

## 🎯 核心组件

### 文本处理流程
```
PDF文档 → 文本提取 → 智能分块 → 向量化 → 存储
```

### 问答流程
```
用户问题 → 问题向量化 → 相似度搜索 → 上下文构建 → LLM生成回答
```

### 关键配置
- **分块大小**: 300字符 (可调整)
- **向量维度**: 1024 (BGE-M3固定)
- **检索数量**: top_k=3 (可调整)
- **模型配置**: 
  - LLM: `openai/qwen3`
  - Embedding: `bge/bge-m3`

## 🔧 故障排除

### 常见问题

#### 1. "Mistral API key required"
**问题**: PDF上传失败，要求Mistral API key
**解决**: 使用我们的绕过方案，直接提取PDF文本进行处理

#### 2. Embedding调用失败
**检查**:
```bash
curl -X POST http://127.0.0.1:8003/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"bge-m3","input":["测试"]}'
```

#### 3. 向量维度不匹配
**检查**: 确保所有embedding都使用相同的模型和配置

#### 4. 内存不足
**解决**: 
- 减小分块数量
- 分批处理大文档
- 启用embedding缓存

### 性能优化

#### 1. 启用缓存
```python
rag = QuickRAG()
rag.enable_embedding_cache = True
```

#### 2. 调整分块策略
```python
# 更小的块，更精确的检索
chunks = rag.step2_chunk_text(text, chunk_size=200)

# 更大的块，更多上下文
chunks = rag.step2_chunk_text(text, chunk_size=500)
```

#### 3. 优化检索参数
```python
# 检索更多候选
results = rag.search_similar_chunks(query, top_k=5)

# 调整相似度阈值
filtered_results = [r for r in results if r['similarity'] > 0.6]
```

## 📊 预期结果

### 性能指标 (基于jr.pdf测试)
- **文档处理**: ~10秒 (7页PDF)
- **向量生成**: ~15秒 (33个文档块)
- **查询响应**: ~2秒 (包含检索+生成)
- **检索精度**: 0.65-0.75 (余弦相似度)

### 质量评估
- ✅ 能准确回答文档相关问题
- ✅ 引用具体文档内容
- ✅ 保持回答与文档一致性
- ✅ 处理中文文档效果良好

## 🔗 文件说明

### 核心文件
- `direct_embedding_rag.py` - 完整的生产级RAG系统
- `quick_rag_template.py` - 简化的快速入门模板
- `jr_config_check.py` - 环境配置检查
- `debug_embedding.py` - Embedding调试工具

### 文档文件
- `RAG_BUILD_GUIDE.md` - 完整构建指南
- `JR_RAG_README.md` - JR.PDF项目说明
- 本文件 - 快速检查清单

## 💡 最佳实践

1. **文档准备**: 确保文档内容清晰、结构化
2. **分块策略**: 根据文档类型调整分块大小
3. **向量质量**: 使用统一的embedding模型
4. **检索优化**: 结合向量搜索和关键词匹配
5. **系统监控**: 记录性能指标和错误日志
6. **缓存策略**: 对频繁查询启用缓存
7. **增量更新**: 支持文档的增量添加和更新

## 🎉 成功验证

如果您看到以下输出，说明RAG系统工作正常：

```
✅ PDF文本提取成功: 7页, 9603字符
✅ 分块完成: 33个块, 平均258.6字符  
✅ Embedding生成成功: 33个向量, 维度1024
✅ 智能体创建成功: AdmirableTeapot
✅ RAG系统构建完成!
   🎯 Embedding模型已被正确调用!
```

现在您就有了一个完全工作的RAG系统！
