# RAG系统使用文档

## 目录
1. [概述](#概述)
2. [系统架构](#系统架构)
3. [环境准备](#环境准备)
4. [快速开始](#快速开始)
5. [详细使用说明](#详细使用说明)
6. [API参考](#api参考)
7. [常见问题](#常见问题)
8. [进阶配置](#进阶配置)

## 概述

本RAG（Retrieval-Augmented Generation）系统基于Letta和OpenGauss构建，支持PDF文档的向量化处理、语义检索和智能问答。系统使用BGE-M3作为embedding模型，Qwen3作为生成模型。

### 核心功能
- PDF文档自动解析和分块
- 文本向量化存储
- 语义相似度检索
- 上下文增强生成
- 支持中英文问答

## 系统架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   PDF文档   │ -> │  文本分块器  │ -> │ Embedding   │
└─────────────┘    └──────────────┘    │   模型      │
                                       │ (BGE-M3)    │
                                       └─────────────┘
                                              │
                                              ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   用户问题  │ -> │  相似度检索  │ <- │  向量数据库 │
└─────────────┘    └──────────────┘    │ (OpenGauss) │
       │                  │            └─────────────┘
       │                  ▼
       │           ┌─────────────┐
       └---------> │ LLM生成答案 │
                   │  (Qwen3)    │
                   └─────────────┘
```

## 环境准备

### 1. 系统要求
- Python 3.8+
- Docker (用于OpenGauss数据库)
- 至少4GB可用内存

### 2. 服务启动

#### 启动OpenGauss数据库
```bash
# 使用Docker启动OpenGauss
docker run --name opengauss \
  -e GS_PASSWORD=Enmo@123 \
  -p 5432:5432 \
  -d enmotech/opengauss:latest
```

#### 启动Embedding服务
```bash
# 启动BGE-M3 embedding服务
python -m letta.server.server --host 0.0.0.0 --port 8283 --backend letta
```

#### 启动LLM服务
```bash
# 启动Qwen3服务（需要配置API密钥）
export OPENAI_API_KEY="your_api_key"
```

### 3. 安装依赖
```bash
pip install -r requirements_opengauss.txt
pip install PyPDF2 numpy scikit-learn
```

## 快速开始

### 1. 环境检查
运行环境检查脚本，确保所有服务正常：

```bash
python jr_config_check.py
```

### 2. 简单示例
使用模板脚本快速体验RAG功能：

```python
from quick_rag_template import SimpleRAGSystem

# 初始化RAG系统
rag = SimpleRAGSystem()

# 处理PDF文档
rag.process_pdf("/path/to/your/document.pdf")

# 进行问答
answer = rag.ask("你的问题")
print(answer)
```

### 3. 完整示例
参考 `direct_embedding_rag.py` 的完整实现：

```bash
python direct_embedding_rag.py
```

## 详细使用说明

### 1. 文档处理

#### PDF文档解析
```python
import PyPDF2
from io import StringIO

def extract_text_from_pdf(pdf_path):
    """从PDF提取文本"""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text
```

#### 文本分块
```python
def chunk_text(text, chunk_size=500, overlap=50):
    """将文本分割成重叠的块"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks
```

### 2. 向量化处理

#### 调用Embedding服务
```python
import requests
import json

def get_embeddings(texts):
    """获取文本的向量表示"""
    url = "http://localhost:8283/v1/embeddings"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "input": texts if isinstance(texts, list) else [texts],
        "model": "bge-m3"
    }
    
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    embeddings = [item["embedding"] for item in result["data"]]
    return embeddings[0] if len(embeddings) == 1 else embeddings
```

### 3. 向量存储

#### 存储到OpenGauss
```python
import psycopg2
import json

def store_vectors(chunks, embeddings):
    """将向量存储到OpenGauss"""
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="postgres",
        user="gaussdb",
        password="Enmo@123"
    )
    
    cursor = conn.cursor()
    
    # 创建向量表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_vectors (
            id SERIAL PRIMARY KEY,
            content TEXT,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 插入向量数据
    for chunk, embedding in zip(chunks, embeddings):
        cursor.execute(
            "INSERT INTO document_vectors (content, embedding) VALUES (%s, %s)",
            (chunk, json.dumps(embedding))
        )
    
    conn.commit()
    cursor.close()
    conn.close()
```

### 4. 相似度检索

#### 计算余弦相似度
```python
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def find_similar_chunks(query_embedding, stored_embeddings, chunks, top_k=3):
    """查找最相似的文本块"""
    similarities = cosine_similarity([query_embedding], stored_embeddings)[0]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        results.append({
            'chunk': chunks[idx],
            'similarity': similarities[idx]
        })
    
    return results
```

### 5. 答案生成

#### 调用LLM服务
```python
import openai

def generate_answer(question, context_chunks):
    """基于检索到的上下文生成答案"""
    context = "\n".join(context_chunks)
    
    prompt = f"""基于以下上下文信息回答问题：

上下文：
{context}

问题：{question}

请基于上下文信息给出准确、详细的回答。如果上下文中没有相关信息，请明确说明。
"""
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )
    
    return response.choices[0].message.content
```

## API参考

### RAGSystem类

#### 主要方法

```python
class RAGSystem:
    def __init__(self, embedding_url, llm_config, db_config):
        """初始化RAG系统"""
        pass
    
    def process_document(self, file_path):
        """处理文档并存储向量"""
        pass
    
    def ask(self, question, top_k=3):
        """基于文档内容回答问题"""
        pass
    
    def add_document(self, content):
        """添加新文档到知识库"""
        pass
    
    def search(self, query, limit=10):
        """搜索相关文档片段"""
        pass
```

#### 配置参数

```python
# Embedding服务配置
embedding_config = {
    "url": "http://localhost:8283/v1/embeddings",
    "model": "bge-m3"
}

# LLM配置
llm_config = {
    "api_key": "your_openai_api_key",
    "model": "gpt-3.5-turbo",
    "temperature": 0.7
}

# 数据库配置
db_config = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "gaussdb",
    "password": "Enmo@123"
}
```

## 常见问题

### Q1: Embedding服务无法连接
**A:** 检查服务是否正常启动：
```bash
curl http://localhost:8283/v1/models
```

### Q2: 数据库连接失败
**A:** 确认OpenGauss容器正在运行：
```bash
docker ps | grep opengauss
```

### Q3: PDF解析失败
**A:** 确保PDF文件可读且格式正确：
```python
# 测试PDF文件
import PyPDF2
with open("your_file.pdf", "rb") as f:
    reader = PyPDF2.PdfReader(f)
    print(f"页数: {len(reader.pages)}")
```

### Q4: 向量维度不匹配
**A:** BGE-M3模型输出1024维向量，确保数据库表结构正确。

### Q5: 回答质量不佳
**A:** 尝试以下优化：
- 调整文本分块大小
- 增加检索的文档数量
- 优化prompt模板
- 调整LLM参数

## 进阶配置

### 1. 自定义分块策略
```python
def semantic_chunking(text, max_chunk_size=500):
    """基于语义的智能分块"""
    # 按段落分割
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk + para) <= max_chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks
```

### 2. 向量数据库优化
```sql
-- 创建向量索引
CREATE INDEX idx_embedding_cosine ON document_vectors USING ivfflat (embedding vector_cosine_ops);

-- 分区表
CREATE TABLE document_vectors_partitioned (
    id SERIAL,
    content TEXT,
    embedding VECTOR(1024),
    doc_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY RANGE (created_at);
```

### 3. 缓存机制
```python
import redis
import json

class EmbeddingCache:
    def __init__(self, redis_host='localhost', redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port)
    
    def get_embedding(self, text):
        key = f"embedding:{hash(text)}"
        cached = self.redis_client.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    def set_embedding(self, text, embedding):
        key = f"embedding:{hash(text)}"
        self.redis_client.setex(key, 3600, json.dumps(embedding))
```

### 4. 批量处理
```python
def batch_process_documents(file_paths, batch_size=10):
    """批量处理多个文档"""
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i+batch_size]
        
        # 并行处理批次
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_single_document, path) 
                      for path in batch]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    print(f"处理完成: {result}")
                except Exception as e:
                    print(f"处理失败: {e}")
```

### 5. 监控和日志
```python
import logging
import time
from functools import wraps

def log_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        logging.info(f"{func.__name__} 执行时间: {end_time - start_time:.2f}秒")
        return result
    return wrapper

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rag_system.log'),
        logging.StreamHandler()
    ]
)
```

## 最佳实践

1. **文档预处理**: 清理文本、去除无关内容
2. **分块策略**: 根据文档类型选择合适的分块方法
3. **向量存储**: 使用适当的索引提高检索速度
4. **缓存机制**: 缓存常用查询和计算结果
5. **监控告警**: 监控系统性能和服务可用性
6. **版本管理**: 对模型和数据进行版本控制
7. **安全考虑**: 加密敏感数据，控制访问权限

## 总结

本RAG系统提供了完整的文档处理、向量化、检索和生成功能。通过合理配置和优化，可以构建高效、准确的智能问答系统。

如需更多帮助，请参考项目源代码和相关文档。
