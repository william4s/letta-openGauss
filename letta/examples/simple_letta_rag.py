#!/usr/bin/env python3
"""
基于Letta服务的简单RAG系统
"""

import os
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict

# 添加letta模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate


class SimpleLettaRAG:
    """基于Letta服务的简单RAG系统"""
    
    def __init__(self, letta_url="http://localhost:8283", embedding_url="http://127.0.0.1:8003/v1/embeddings"):
        """初始化RAG系统"""
        print("🚀 初始化Letta RAG系统")
        self.client = Letta(base_url=letta_url)
        self.embedding_url = embedding_url
        self.text_chunks = []
        self.chunk_embeddings = []
        self.agent = None
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """从PDF文件中提取文本"""
        print(f"📄 从PDF中提取文本: {pdf_path}")
        
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
    
    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
        """将文本分割成重叠的块"""
        print(f"✂️ 将文本分割成块 (大小={chunk_size}, 重叠={overlap})")
        
        if not text:
            return []
        
        # 先按句号分割
        sentences = text.split('。')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip() + "。"  # 添加句号
            
            if not sentence.strip():
                continue
                
            # 如果当前块加上新句子小于块大小，则添加句子
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence
            else:
                # 当前块已满，保存当前块
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 开始新块，保留部分重叠
                if len(current_chunk) > overlap:
                    # 尝试找到最后一个句号位置作为切分点
                    overlap_start = len(current_chunk) - overlap
                    overlap_text = current_chunk[overlap_start:]
                    
                    # 找最后一个完整句子
                    last_period = overlap_text.rfind('。')
                    if last_period != -1:
                        current_chunk = overlap_text[last_period+1:] + sentence
                    else:
                        current_chunk = overlap_text + sentence
                else:
                    current_chunk = sentence
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        self.text_chunks = chunks
        print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c) for c in chunks)/max(1, len(chunks)):.1f}字符")
        return chunks
    
    def generate_embeddings(self) -> List[List[float]]:
        """为文本块生成embedding向量"""
        print("🧠 生成embedding向量")
        
        if not self.text_chunks:
            print("❌ 没有文本块可以处理")
            return []
        
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
    
    def create_agent(self) -> bool:
        """创建RAG智能体"""
        print("🤖 创建RAG智能体")
        
        try:
            memory_blocks = [
                CreateBlock(
                    value=f"你是一个专业的金融文档问答助手，专门回答人民币理财产品相关问题。请基于提供的文档内容准确回答问题，特别注意产品风险、收益、期限等关键信息。当前已加载金融理财产品说明书，共{len(self.text_chunks)}个文档片段，可以回答产品风险、收益、投资期限、费用结构等相关问题。",
                    label="system_instruction",
                ),
            ]
            
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # Qwen3模型
                embedding="bge/bge-m3",      # BGE-M3嵌入
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            return True
            
        except Exception as e:
            print(f"❌ 创建智能体失败: {e}")
            return False
    
    def search_similar_chunks(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索与查询相似的文档块"""
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
                print(f"❌ 查询embedding请求失败: {response.status_code}")
                return []
            
            query_embedding = response.json()['data'][0]['embedding']
            
        except Exception as e:
            print(f"❌ 查询embedding失败: {e}")
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
        top_results = similarities[:top_k]
        
        return top_results
    
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
        context = "\n\n".join([doc['text'] for doc in relevant_docs])
        enhanced_question = f"""基于以下金融理财产品文档内容回答问题：

文档内容：
{context}

问题：{question}

请基于上述文档内容给出准确的回答，特别注意产品风险、收益率、投资期限、费用等关键信息。如果涉及风险评估，请明确提醒用户注意风险。使用中文回答。"""
        
        # 3. 调用智能体
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="system", content=enhanced_question)],
            )
            
            # 提取回答
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    answer = msg.content
                    print(f"🤖 回答: {answer}")
                    return answer
            
            # 没有找到有效回答
            return "智能体没有返回有效回答"
            
        except Exception as e:
            error_msg = f"处理问题时出错: {e}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def build_rag_system(self, file_path: str, chunk_size: int = 400, overlap: int = 100) -> bool:
        """构建完整的RAG系统"""
        print("🚀 开始构建RAG系统")
        print("=" * 50)
        
        try:
            # 步骤1: 提取文本
            text = self.extract_text_from_pdf(file_path)
            if not text:
                return False
            
            # 步骤2: 文本分块
            chunks = self.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                return False
            
            # 步骤3: 生成embedding
            embeddings = self.generate_embeddings()
            if not embeddings:
                return False
            
            # 步骤4: 创建智能体
            success = self.create_agent()
            if not success:
                return False
            
            print("\n" + "=" * 50)
            print("✅ RAG系统构建完成!")
            print(f"   文档: {Path(file_path).name}")
            print(f"   文本块: {len(self.text_chunks)}个")
            print(f"   块大小: {chunk_size}字符，重叠: {overlap}字符")
            print(f"   向量维度: {len(self.chunk_embeddings[0])}")
            print(f"   智能体: {self.agent.name}")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统构建失败: {e}")
            return False
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n💬 进入交互式问答")
        print("=" * 40)
        print("输入问题，输入'quit'退出")
        
        while True:
            try:
                question = input("\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if not question:
                    continue
                
                answer = self.ask_question(question)
                
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")


def main():
    """主函数 - 简单RAG系统示例"""
    # 配置
    pdf_file = "/home/shiwc24/ospp/letta-openGauss/letta/examples/jr.pdf"
    chunk_size = 800
    overlap = 200
    
    print("📚 基于Letta的简单RAG系统")
    print("=" * 50)
    print(f"文档路径: {pdf_file}")
    print(f"块大小: {chunk_size}, 重叠: {overlap}")
    print("=" * 50)
    
    # 检查文件
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        return
    
    # 创建RAG系统
    rag = SimpleLettaRAG()
    
    # 构建系统
    success = rag.build_rag_system(pdf_file, chunk_size=chunk_size, overlap=overlap)
    
    if success:
        # 快速测试
        print("\n🧪 快速测试:")
        test_questions = [
            "这个产品的风险等级是什么？",
            # "投资期限多长？",
            # "产品的预期收益率是多少？"
        ]
        
        for question in test_questions:
            print(f"\n测试问题: {question}")
            answer = rag.ask_question(question)
        
        # 交互模式
        user_input = input("\n是否进入交互模式? (y/n): ").strip().lower()
        if user_input in ['y', 'yes', '是', 'y']:
            rag.interactive_demo()
    
    else:
        print("❌ 系统构建失败")
        print("\n请检查:")
        print("1. Letta服务器是否运行 (http://localhost:8283)")
        print("2. BGE-M3服务是否运行 (http://127.0.0.1:8003)")
        print("3. 文件是否存在且可读")


if __name__ == "__main__":
    main()