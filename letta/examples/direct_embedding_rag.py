#!/usr/bin/env python3
"""
直接调用embedding模型进行向量化处理
绕过文件上传限制，直接进行向量化
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
from typing import List, Dict

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate


class DirectEmbeddingRAG:
    """直接调用embedding的RAG系统"""
    
    def __init__(self):
        self.client = Letta(base_url="http://localhost:8283")
        self.embedding_url = "http://127.0.0.1:8003/v1/embeddings"
        self.source = None
        self.agent = None
        self.text_chunks = []
        self.chunk_embeddings = []
    
    def extract_pdf_text(self):
        """提取PDF文本"""
        pdf_path = "./jr.pdf"
        
        try:
            import pypdf
            
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                full_text = ""
                
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    full_text += f"\\n--- 第 {page_num + 1} 页 ---\\n{text}"
                
                print(f"✅ PDF文本提取成功")
                print(f"   页数: {len(reader.pages)}")
                print(f"   文本长度: {len(full_text)} 字符")
                
                return full_text
                
        except Exception as e:
            print(f"❌ PDF文本提取失败: {e}")
            return None
    
    def chunk_text(self, text: str, chunk_size: int = 300) -> List[str]:
        """将文本分块"""
        if not text:
            return []
        
        # 简单的分块策略：按句号分割，然后合并到指定长度
        sentences = text.split('。')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # 如果当前块加上新句子不超过限制，就添加
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + "。"
            else:
                # 保存当前块，开始新块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "。"
        
        # 添加最后一块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        print(f"✅ 文本分块完成")
        print(f"   总块数: {len(chunks)}")
        print(f"   平均长度: {sum(len(c) for c in chunks) / len(chunks):.1f} 字符")
        
        return chunks
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """获取文本的embedding向量"""
        print(f"🔄 调用BGE-M3生成embedding向量...")
        
        try:
            response = requests.post(
                self.embedding_url,
                json={
                    "model": "bge-m3",
                    "input": texts
                },
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                embeddings = [item['embedding'] for item in data['data']]
                
                print(f"✅ Embedding生成成功!")
                print(f"   处理文本数: {len(texts)}")
                print(f"   向量维度: {len(embeddings[0]) if embeddings else 0}")
                print(f"   向量示例: {embeddings[0][:5] if embeddings else 'N/A'}")
                
                return embeddings
            else:
                print(f"❌ Embedding调用失败: {response.status_code}")
                print(f"   响应: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Embedding调用出错: {e}")
            return []
    
    def create_manual_source(self):
        """创建手动管理的文档源"""
        try:
            source_name = f"manual_jr_rag_{int(time.time())}"
            self.source = self.client.sources.create(
                name=source_name,
                embedding="bge/bge-m3",
            )
            
            print(f"✅ 手动文档源创建成功")
            print(f"   ID: {self.source.id}")
            print(f"   名称: {self.source.name}")
            
            return self.source
            
        except Exception as e:
            print(f"❌ 创建文档源失败: {e}")
            return None
    
    def store_embeddings_manually(self):
        """手动存储embedding向量到向量数据库"""
        print("🔄 手动存储embedding向量...")
        
        if not self.text_chunks or not self.chunk_embeddings:
            print("❌ 没有文本块或embedding向量")
            return False
        
        try:
            # 这里我们模拟向量存储
            # 在实际应用中，这应该直接插入到OpenGauss向量数据库
            
            stored_count = 0
            for i, (chunk, embedding) in enumerate(zip(self.text_chunks, self.chunk_embeddings)):
                # 模拟存储过程
                passage_id = f"passage_{self.source.id}_{i}"
                
                # 这里应该是实际的数据库插入操作
                # INSERT INTO passage_embeddings (passage_id, embedding, metadata, ...)
                
                stored_count += 1
                
                if i < 3:  # 只显示前3个
                    print(f"   存储块 {i+1}: {chunk[:50]}... (向量维度: {len(embedding)})")
            
            print(f"✅ 模拟存储完成: {stored_count} 个向量")
            return True
            
        except Exception as e:
            print(f"❌ 存储embedding失败: {e}")
            return False
    
    def similarity_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """执行相似度搜索"""
        print(f"🔍 执行相似度搜索: {query}")
        
        try:
            # 1. 获取查询的embedding
            query_embeddings = self.get_embeddings([query])
            if not query_embeddings:
                return []
            
            query_embedding = query_embeddings[0]
            
            # 2. 计算与所有文档块的相似度
            similarities = []
            for i, chunk_embedding in enumerate(self.chunk_embeddings):
                # 计算余弦相似度
                similarity = self.cosine_similarity(query_embedding, chunk_embedding)
                similarities.append({
                    'index': i,
                    'text': self.text_chunks[i],
                    'similarity': similarity
                })
            
            # 3. 按相似度排序并返回top_k
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            results = similarities[:top_k]
            
            print(f"✅ 搜索完成，返回 {len(results)} 个结果")
            for i, result in enumerate(results):
                print(f"   结果 {i+1} (相似度: {result['similarity']:.4f}): {result['text'][:100]}...")
            
            return results
            
        except Exception as e:
            print(f"❌ 相似度搜索失败: {e}")
            return []
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        import math
        
        # 计算点积
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # 计算向量的模长
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        # 避免除零
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def create_rag_agent(self):
        """创建RAG智能体"""
        print("🤖 创建RAG智能体...")
        
        try:
            memory_blocks = [
                CreateBlock(
                    value=(
                        "你是一个专业的JR理财产品文档问答助手。"
                        "你可以基于已向量化的理财产品说明书回答用户问题，"
                        "提供准确的投资建议和风险提示。"
                    ),
                    label="system_instruction",
                ),
                CreateBlock(
                    value=(
                        f"当前已加载JR理财产品说明书，共 {len(self.text_chunks)} 个文档片段。"
                        "可以回答关于产品特性、风险等级、投资期限等问题。"
                    ),
                    label="document_status",
                ),
            ]
            
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",
                embedding="bge/bge-m3",
            )
            
            print(f"✅ RAG智能体创建成功: {self.agent.name}")
            
            # 将文档源附加到智能体（如果可能的话）
            if self.source:
                try:
                    self.client.agents.sources.attach(
                        agent_id=self.agent.id,
                        source_id=self.source.id
                    )
                    print("✅ 文档源已附加到智能体")
                except Exception as e:
                    print(f"⚠️ 附加文档源失败: {e}")
            
            return self.agent
            
        except Exception as e:
            print(f"❌ 创建RAG智能体失败: {e}")
            return None
    
    def ask_question_with_rag(self, question: str) -> str:
        """使用RAG回答问题"""
        print(f"❓ 用户问题: {question}")
        
        # 1. 检索相关文档
        relevant_docs = self.similarity_search(question, top_k=3)
        
        if not relevant_docs:
            return "抱歉，没有找到相关的文档内容。"
        
        # 2. 构建增强的prompt
        context = "\\n\\n".join([doc['text'] for doc in relevant_docs])
        enhanced_question = f"""基于以下文档内容回答问题：

文档内容：
{context}

问题：{question}

请基于上述文档内容给出准确的回答。"""
        
        # 3. 调用智能体
        try:
            if self.agent:
                response = self.client.agents.messages.create(
                    agent_id=self.agent.id,
                    messages=[
                        MessageCreate(
                            role="user",
                            content=enhanced_question,
                        ),
                    ],
                )
                
                # 提取回答
                for msg in response.messages:
                    if msg.message_type == "assistant_message":
                        print(f"🤖 智能体回答: {msg.content}")
                        return msg.content
                
            return "智能体响应异常"
            
        except Exception as e:
            print(f"❌ 问答过程出错: {e}")
            return f"处理问题时出错: {e}"
    
    def setup_complete_rag(self):
        """完整的RAG系统设置"""
        print("🚀 设置完整的JR.PDF RAG系统")
        print("=" * 60)
        
        # 1. 提取PDF文本
        print("\\n📄 步骤1: 提取PDF文本")
        full_text = self.extract_pdf_text()
        if not full_text:
            return False
        
        # 2. 文本分块
        print("\\n✂️ 步骤2: 文本分块")
        self.text_chunks = self.chunk_text(full_text)
        if not self.text_chunks:
            return False
        
        # 3. 生成embedding向量
        print("\\n🧠 步骤3: 生成embedding向量")
        self.chunk_embeddings = self.get_embeddings(self.text_chunks)
        if not self.chunk_embeddings:
            return False
        
        # 4. 创建文档源
        print("\\n📁 步骤4: 创建文档源")
        source = self.create_manual_source()
        if not source:
            return False
        
        # 5. 存储向量（模拟）
        print("\\n💾 步骤5: 存储向量")
        storage_success = self.store_embeddings_manually()
        
        # 6. 创建RAG智能体
        print("\\n🤖 步骤6: 创建RAG智能体")
        agent = self.create_rag_agent()
        
        print("\\n" + "=" * 60)
        if all([full_text, self.text_chunks, self.chunk_embeddings, source, agent]):
            print("✅ JR.PDF RAG系统设置完成!")
            print(f"   文档片段: {len(self.text_chunks)} 个")
            print(f"   向量维度: {len(self.chunk_embeddings[0]) if self.chunk_embeddings else 0}")
            print(f"   智能体: {agent.name}")
            print("   🎯 Embedding模型已被正确调用!")
            return True
        else:
            print("❌ RAG系统设置失败")
            return False
    
    def interactive_demo(self):
        """交互式演示"""
        print("\\n💬 进入JR理财产品问答演示")
        print("=" * 50)
        
        # 预设问题
        demo_questions = [
            "这个理财产品的风险等级是什么？",
            "投资期限多长？",
            "有哪些风险提示？",
            "产品的收益如何？"
        ]
        
        print("🎯 预设问题演示:")
        for i, question in enumerate(demo_questions, 1):
            print(f"\\n--- 演示 {i} ---")
            answer = self.ask_question_with_rag(question)
            print(f"答案: {answer}")
            
            if i < len(demo_questions):
                input("\\n按回车键继续...")
        
        print("\\n" + "=" * 50)
        print("🔍 自由问答 (输入 'quit' 退出):")
        
        while True:
            try:
                question = input("\\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 演示结束!")
                    break
                
                if not question:
                    continue
                
                answer = self.ask_question_with_rag(question)
                print(f"🤖 回答: {answer}")
                
            except KeyboardInterrupt:
                print("\\n👋 演示结束!")
                break


def main():
    """主函数"""
    rag_system = DirectEmbeddingRAG()
    
    try:
        # 设置完整的RAG系统
        success = rag_system.setup_complete_rag()
        
        if success:
            # 运行交互式演示
            rag_system.interactive_demo()
        else:
            print("❌ 系统设置失败，无法进行演示")
    
    except Exception as e:
        print(f"❌ 系统运行出错: {e}")
    
    finally:
        print("\\n🧹 清理资源...")


if __name__ == "__main__":
    main()
