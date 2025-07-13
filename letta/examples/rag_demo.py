#!/usr/bin/env python3
"""
RAG系统快速演示脚本
演示完整的PDF处理、向量化、检索和问答流程
"""

import os
import sys
import json
import requests
import PyPDF2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import psycopg2
from typing import List, Dict, Tuple
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RAGDemo:
    """RAG系统演示类"""
    
    def __init__(self):
        """初始化配置"""
        self.embedding_url = "http://localhost:8283/v1/embeddings"
        self.embedding_model = "bge-m3"
        self.chunk_size = 500
        self.overlap = 50
        self.top_k = 3
        
        # 数据库配置
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'postgres',
            'user': 'gaussdb',
            'password': 'Enmo@123'
        }
        
        # 存储向量和文档块
        self.chunks = []
        self.embeddings = []
    
    def check_services(self) -> bool:
        """检查必要服务是否运行"""
        logger.info("检查服务状态...")
        
        # 检查embedding服务
        try:
            response = requests.get(f"http://localhost:8283/v1/models", timeout=5)
            if response.status_code == 200:
                logger.info("✓ Embedding服务正常")
            else:
                logger.error("✗ Embedding服务异常")
                return False
        except Exception as e:
            logger.error(f"✗ Embedding服务连接失败: {e}")
            return False
        
        # 检查数据库连接
        try:
            conn = psycopg2.connect(**self.db_config)
            conn.close()
            logger.info("✓ OpenGauss数据库连接正常")
        except Exception as e:
            logger.error(f"✗ 数据库连接失败: {e}")
            return False
        
        return True
    
    def extract_pdf_text(self, pdf_path: str) -> str:
        """从PDF提取文本"""
        logger.info(f"正在提取PDF文本: {pdf_path}")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(reader.pages):
                    page_text = page.extract_text()
                    text += page_text + "\n"
                    logger.info(f"已处理第 {page_num + 1} 页")
        except Exception as e:
            logger.error(f"PDF解析失败: {e}")
            raise
        
        logger.info(f"PDF文本提取完成，总长度: {len(text)} 字符")
        return text
    
    def chunk_text(self, text: str) -> List[str]:
        """将文本分割成重叠的块"""
        logger.info(f"正在分割文本，块大小: {self.chunk_size}, 重叠: {self.overlap}")
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            # 避免在单词中间截断
            if end < len(text) and text[end] != ' ':
                last_space = chunk.rfind(' ')
                if last_space > start + self.chunk_size // 2:
                    chunk = chunk[:last_space]
                    end = start + last_space
            
            chunks.append(chunk.strip())
            start = end - self.overlap
        
        # 过滤空块和过短的块
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        logger.info(f"文本分割完成，共 {len(chunks)} 个块")
        return chunks
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取文本向量"""
        logger.info(f"正在生成 {len(texts)} 个文本块的向量...")
        
        headers = {"Content-Type": "application/json"}
        data = {
            "input": texts,
            "model": self.embedding_model
        }
        
        try:
            response = requests.post(self.embedding_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            embeddings = [item["embedding"] for item in result["data"]]
            logger.info(f"向量生成完成，维度: {len(embeddings[0])}")
            return embeddings
            
        except Exception as e:
            logger.error(f"向量生成失败: {e}")
            raise
    
    def store_to_database(self, chunks: List[str], embeddings: List[List[float]]) -> None:
        """将文档块和向量存储到数据库"""
        logger.info("正在存储向量到数据库...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 创建表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 清空现有数据（演示用）
            cursor.execute("DELETE FROM rag_documents")
            
            # 插入新数据
            for chunk, embedding in zip(chunks, embeddings):
                cursor.execute(
                    "INSERT INTO rag_documents (content, embedding) VALUES (%s, %s)",
                    (chunk, json.dumps(embedding))
                )
            
            conn.commit()
            logger.info(f"已存储 {len(chunks)} 个文档块到数据库")
            
        except Exception as e:
            logger.error(f"数据库存储失败: {e}")
            raise
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
    
    def retrieve_similar(self, query: str) -> List[Dict]:
        """检索相似文档块"""
        logger.info(f"正在检索相似文档: {query}")
        
        # 获取查询向量
        query_embedding = self.get_embeddings([query])[0]
        
        # 计算相似度
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        
        # 获取最相似的块
        top_indices = np.argsort(similarities)[-self.top_k:][::-1]
        
        results = []
        for idx in top_indices:
            results.append({
                'content': self.chunks[idx],
                'similarity': float(similarities[idx]),
                'index': int(idx)
            })
            
        logger.info(f"检索到 {len(results)} 个相关文档块")
        return results
    
    def generate_answer(self, question: str, context_chunks: List[str]) -> str:
        """生成答案（简化版，使用基于规则的回答）"""
        logger.info("正在生成答案...")
        
        # 合并上下文
        context = "\n\n".join(context_chunks)
        
        # 简化的答案生成（在实际应用中应该调用LLM）
        answer = f"""基于文档内容，我找到了以下相关信息来回答您的问题：

问题：{question}

相关内容：
{context}

总结：基于以上文档内容，可以看出文档包含了关于您问题的相关信息。建议您查看完整的相关段落以获得更详细的信息。

注意：这是基于文档检索的回答，如需更准确的答案，请结合完整文档内容进行理解。"""

        return answer
    
    def process_document(self, pdf_path: str) -> None:
        """处理PDF文档并构建向量索引"""
        logger.info(f"开始处理文档: {pdf_path}")
        
        # 1. 提取文本
        text = self.extract_pdf_text(pdf_path)
        
        # 2. 分割文本
        self.chunks = self.chunk_text(text)
        
        # 3. 生成向量
        self.embeddings = self.get_embeddings(self.chunks)
        
        # 4. 存储到数据库
        self.store_to_database(self.chunks, self.embeddings)
        
        logger.info("文档处理完成！")
    
    def ask(self, question: str) -> str:
        """基于文档内容回答问题"""
        if not self.chunks or not self.embeddings:
            return "请先处理文档再进行问答。"
        
        # 检索相似文档块
        similar_docs = self.retrieve_similar(question)
        
        # 提取文本内容
        context_chunks = [doc['content'] for doc in similar_docs]
        
        # 生成答案
        answer = self.generate_answer(question, context_chunks)
        
        # 添加相似度信息
        similarity_info = "\n\n相关度评分：\n"
        for i, doc in enumerate(similar_docs):
            similarity_info += f"{i+1}. 相似度: {doc['similarity']:.3f}\n"
        
        return answer + similarity_info
    
    def run_demo(self, pdf_path: str = None) -> None:
        """运行完整演示"""
        print("=" * 60)
        print("RAG系统演示")
        print("=" * 60)
        
        # 检查服务
        if not self.check_services():
            print("❌ 服务检查失败，请确保所有服务正常运行")
            return
        
        # 使用默认PDF或用户指定的PDF
        if pdf_path is None:
            pdf_path = "/home/shiwc24/ospp/letta-openGauss/letta/examples/jr.pdf"
        
        if not os.path.exists(pdf_path):
            print(f"❌ PDF文件不存在: {pdf_path}")
            return
        
        try:
            # 处理文档
            print("\n📚 开始处理PDF文档...")
            self.process_document(pdf_path)
            print("✅ 文档处理完成！")
            
            # 演示问答
            print("\n🤖 开始问答演示...")
            
            demo_questions = [
                "这个文档主要讲的是什么？",
                "文档中提到了哪些重要概念？",
                "有什么具体的案例或例子吗？"
            ]
            
            for i, question in enumerate(demo_questions, 1):
                print(f"\n问题 {i}: {question}")
                print("-" * 40)
                answer = self.ask(question)
                print(answer)
                print("-" * 40)
            
            # 交互式问答
            print("\n💬 进入交互式问答模式（输入 'quit' 退出）:")
            while True:
                question = input("\n请输入您的问题: ").strip()
                if question.lower() in ['quit', 'exit', 'q', '退出']:
                    break
                if question:
                    answer = self.ask(question)
                    print("\n回答:")
                    print(answer)
            
            print("\n✅ 演示完成！")
            
        except Exception as e:
            logger.error(f"演示过程中发生错误: {e}")
            print(f"❌ 演示失败: {e}")

def main():
    """主函数"""
    print("RAG系统快速演示脚本")
    print("确保以下服务正在运行：")
    print("1. OpenGauss数据库 (端口5432)")
    print("2. BGE-M3 Embedding服务 (端口8283)")
    print()
    
    # 创建演示实例
    demo = RAGDemo()
    
    # 检查命令行参数
    pdf_path = None
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    
    # 运行演示
    demo.run_demo(pdf_path)

if __name__ == "__main__":
    main()
