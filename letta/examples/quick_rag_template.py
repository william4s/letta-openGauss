#!/usr/bin/env python3
"""
RAG系统快速入门模板
基于验证的direct_embedding_rag.py简化而来
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate


class QuickRAG:
    """快速RAG系统模板"""
    
    def __init__(self, letta_url="http://localhost:8283", embedding_url="http://127.0.0.1:8003/v1/embeddings"):
        self.client = Letta(base_url=letta_url)
        self.embedding_url = embedding_url
        self.text_chunks = []
        self.chunk_embeddings = []
        self.agent = None
        
    def step1_extract_text(self, file_path: str) -> str:
        """步骤1: 提取文档文本"""
        print("📄 步骤1: 提取文档文本")
        
        if file_path.endswith('.pdf'):
            return self._extract_pdf_text(file_path)
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"不支持的文件格式: {file_path}")
    
    def _extract_pdf_text(self, pdf_path: str) -> str:
        """提取PDF文本"""
        try:
            import pypdf
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                print(f"✅ PDF提取成功: {len(reader.pages)}页, {len(text)}字符")
                return text
        except ImportError:
            print("❌ 需要安装pypdf: pip install pypdf")
            return ""
        except Exception as e:
            print(f"❌ PDF提取失败: {e}")
            return ""
    
    def step2_chunk_text(self, text: str, chunk_size: int = 300) -> List[str]:
        """步骤2: 文本分块"""
        print("✂️ 步骤2: 文本分块")
        
        sentences = text.split('。')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + "。"
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        self.text_chunks = chunks
        print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c) for c in chunks)/len(chunks):.1f}字符")
        return chunks
    
    def step3_generate_embeddings(self) -> List[List[float]]:
        """步骤3: 生成embedding向量"""
        print("🧠 步骤3: 生成embedding向量")
        
        try:
            response = requests.post(
                self.embedding_url,
                json={
                    "model": "bge-m3",
                    "input": self.text_chunks
                },
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                embeddings = [item['embedding'] for item in data['data']]
                self.chunk_embeddings = embeddings
                print(f"✅ Embedding生成成功: {len(embeddings)}个向量, 维度{len(embeddings[0])}")
                return embeddings
            else:
                print(f"❌ Embedding调用失败: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ Embedding生成出错: {e}")
            return []
    
    def step4_create_agent(self) -> None:
        """步骤4: 创建RAG智能体"""
        print("🤖 步骤4: 创建RAG智能体")
        
        try:
            memory_blocks = [
                CreateBlock(
                    value="你是一个专业的文档问答助手，基于提供的文档内容准确回答问题。",
                    label="system_instruction",
                ),
                CreateBlock(
                    value=f"当前已加载文档，共{len(self.text_chunks)}个片段，可以回答相关问题。",
                    label="document_status",
                ),
            ]
            
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # Qwen3模型
                embedding="bge/bge-m3",      # BGE-M3嵌入
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            
        except Exception as e:
            print(f"❌ 创建智能体失败: {e}")
    
    def search_similar_chunks(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索相似文档块"""
        if not self.chunk_embeddings:
            return []
        
        # 获取查询的embedding
        try:
            response = requests.post(
                self.embedding_url,
                json={"model": "bge-m3", "input": [query]},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                return []
            
            query_embedding = response.json()['data'][0]['embedding']
            
        except Exception as e:
            print(f"查询embedding失败: {e}")
            return []
        
        # 计算相似度
        similarities = []
        for i, chunk_embedding in enumerate(self.chunk_embeddings):
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)
            similarities.append({
                'index': i,
                'text': self.text_chunks[i],
                'similarity': similarity
            })
        
        # 排序并返回top_k
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:top_k]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def ask_question(self, question: str) -> str:
        """RAG问答"""
        print(f"❓ 问题: {question}")
        
        # 1. 检索相关文档
        relevant_docs = self.search_similar_chunks(question, top_k=3)
        
        if not relevant_docs:
            return "抱歉，没有找到相关的文档内容。"
        
        print(f"🔍 找到{len(relevant_docs)}个相关片段")
        
        # 2. 构建增强的prompt
        context = "\\n\\n".join([doc['text'] for doc in relevant_docs])
        enhanced_question = f"""基于以下文档内容回答问题：

文档内容：
{context}

问题：{question}

请基于上述文档内容给出准确的回答。"""
        
        # 3. 调用智能体
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=enhanced_question)],
            )
            
            # 提取回答
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    print(f"🤖 回答: {msg.content}")
                    return msg.content
            
            return "智能体没有返回有效回答"
            
        except Exception as e:
            print(f"❌ 问答过程出错: {e}")
            return f"处理问题时出错: {e}"
    
    def build_rag_system(self, file_path: str) -> bool:
        """构建完整的RAG系统"""
        print("🚀 开始构建RAG系统")
        print("=" * 50)
        
        try:
            # 步骤1-4
            text = self.step1_extract_text(file_path)
            if not text:
                return False
            
            chunks = self.step2_chunk_text(text)
            if not chunks:
                return False
            
            embeddings = self.step3_generate_embeddings()
            if not embeddings:
                return False
            
            self.step4_create_agent()
            if not self.agent:
                return False
            
            print("\\n" + "=" * 50)
            print("✅ RAG系统构建完成!")
            print(f"   文档: {Path(file_path).name}")
            print(f"   文本块: {len(self.text_chunks)}个")
            print(f"   向量维度: {len(self.chunk_embeddings[0])}")
            print(f"   智能体: {self.agent.name}")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统构建失败: {e}")
            return False
    
    def interactive_demo(self):
        """交互式演示"""
        print("\\n💬 进入交互式问答")
        print("=" * 40)
        print("输入问题，输入'quit'退出")
        
        while True:
            try:
                question = input("\\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if not question:
                    continue
                
                answer = self.ask_question(question)
                
            except KeyboardInterrupt:
                print("\\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")


def main():
    """主函数 - 快速开始示例"""
    print("📚 RAG系统快速入门")
    print("=" * 40)
    
    # 检查文件
    pdf_file = "./jr.pdf"
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        print("请确保当前目录有 jr.pdf 文件")
        return
    
    # 创建RAG系统
    rag = QuickRAG()
    
    # 构建系统
    success = rag.build_rag_system(pdf_file)
    
    if success:
        # 快速测试
        print("\\n🧪 快速测试:")
        test_questions = [
            "这个产品的风险等级是什么？",
            "投资期限多长？"
        ]
        
        for question in test_questions:
            print(f"\\n测试问题: {question}")
            answer = rag.ask_question(question)
        
        # 交互模式
        user_input = input("\\n是否进入交互模式? (y/n): ").strip().lower()
        if user_input in ['y', 'yes']:
            rag.interactive_demo()
    
    else:
        print("❌ 系统构建失败")
        print("\\n请检查:")
        print("1. Letta服务器是否运行 (http://localhost:8283)")
        print("2. BGE-M3服务是否运行 (http://127.0.0.1:8003)")
        print("3. 文件是否存在且可读")


if __name__ == "__main__":
    main()
