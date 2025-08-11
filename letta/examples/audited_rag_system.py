#!/usr/bin/env python3
"""
带安全审计功能的RAG系统
基于quick_rag_template.py扩展，添加完整的安全审计机制
"""

import os
import sys
import time
import uuid
import requests
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate
from security_audit import SecurityAuditor, AuditEventType, AuditLevel


class AuditedQuickRAG:
    """带安全审计功能的RAG系统"""
    
    def __init__(self, 
                 user_id: str = "anonymous", 
                 session_id: str = None,
                 ip_address: str = None,
                 user_agent: str = None,
                 letta_url: str = "http://localhost:8283", 
                 embedding_url: str = "http://127.0.0.1:8003/v1/embeddings"):
        
        # 用户会话信息
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self.ip_address = ip_address
        self.user_agent = user_agent
        
        # 原有的RAG组件
        self.client = Letta(base_url=letta_url)
        self.embedding_url = embedding_url
        self.text_chunks = []
        self.chunk_embeddings = []
        self.agent = None
        
        # 审计器
        self.auditor = SecurityAuditor()
        
        # 记录用户会话开始
        self.auditor.log_user_session(
            user_id=self.user_id,
            action="login",
            session_id=self.session_id,
            ip_address=self.ip_address
        )
        
        print(f"🔐 用户 {self.user_id} 会话开始 (Session: {self.session_id[:8]}...)")
    
    def step1_extract_text(self, file_path: str) -> str:
        """步骤1: 提取文档文本 (带审计)"""
        print("📄 步骤1: 提取文档文本")
        
        start_time = time.time()
        
        try:
            # 记录文档访问
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            self.auditor.log_document_operation(
                user_id=self.user_id,
                document_name=Path(file_path).name,
                operation="access",
                session_id=self.session_id,
                file_size=file_size
            )
            
            if file_path.endswith('.pdf'):
                text = self._extract_pdf_text(file_path)
            elif file_path.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                raise ValueError(f"不支持的文件格式: {file_path}")
            
            # 记录成功的文本提取
            response_time = int((time.time() - start_time) * 1000)
            self.auditor.log_event(
                event_type=AuditEventType.DOCUMENT_ACCESS,
                level=AuditLevel.INFO,
                action="extract_text",
                user_id=self.user_id,
                session_id=self.session_id,
                resource=Path(file_path).name,
                details={
                    "file_path": file_path,
                    "text_length": len(text),
                    "file_size": file_size,
                    "extraction_method": "pdf" if file_path.endswith('.pdf') else "txt"
                },
                success=True,
                response_time_ms=response_time
            )
            
            return text
            
        except Exception as e:
            # 记录错误
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="text_extraction_error",
                error_message=str(e),
                session_id=self.session_id,
                context={"file_path": file_path}
            )
            raise
    
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
            error_msg = "需要安装pypdf: pip install pypdf"
            print(f"❌ {error_msg}")
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="missing_dependency",
                error_message=error_msg,
                session_id=self.session_id
            )
            return ""
        except Exception as e:
            print(f"❌ PDF提取失败: {e}")
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="pdf_extraction_error",
                error_message=str(e),
                session_id=self.session_id
            )
            return ""
    
    def step2_chunk_text(self, text: str, chunk_size: int = 300) -> List[str]:
        """步骤2: 文本分块 (带审计)"""
        print("✂️ 步骤2: 文本分块")
        
        start_time = time.time()
        
        try:
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
            
            # 记录文本分块操作
            response_time = int((time.time() - start_time) * 1000)
            self.auditor.log_event(
                event_type=AuditEventType.DOCUMENT_ACCESS,
                level=AuditLevel.INFO,
                action="chunk_text",
                user_id=self.user_id,
                session_id=self.session_id,
                details={
                    "original_length": len(text),
                    "chunks_count": len(chunks),
                    "chunk_size": chunk_size,
                    "avg_chunk_length": sum(len(c) for c in chunks) / len(chunks) if chunks else 0
                },
                success=True,
                response_time_ms=response_time
            )
            
            print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c) for c in chunks)/len(chunks):.1f}字符")
            return chunks
            
        except Exception as e:
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="text_chunking_error",
                error_message=str(e),
                session_id=self.session_id
            )
            raise
    
    def step3_generate_embeddings(self) -> List[List[float]]:
        """步骤3: 生成embedding向量 (带审计)"""
        print("🧠 步骤3: 生成embedding向量")
        
        start_time = time.time()
        
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
            
            response_time = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                embeddings = [item['embedding'] for item in data['data']]
                self.chunk_embeddings = embeddings
                
                # 记录向量生成成功
                self.auditor.log_embedding_generation(
                    user_id=self.user_id,
                    text_chunks=self.text_chunks,
                    session_id=self.session_id
                )
                
                self.auditor.log_event(
                    event_type=AuditEventType.DATA_EMBEDDING,
                    level=AuditLevel.INFO,
                    action="generate_embeddings",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    details={
                        "embeddings_count": len(embeddings),
                        "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                        "model": "bge-m3",
                        "api_response_time": response_time
                    },
                    success=True,
                    response_time_ms=response_time
                )
                
                print(f"✅ Embedding生成成功: {len(embeddings)}个向量, 维度{len(embeddings[0])}")
                return embeddings
            else:
                error_msg = f"Embedding调用失败: {response.status_code}"
                print(f"❌ {error_msg}")
                
                self.auditor.log_system_error(
                    user_id=self.user_id,
                    error_type="embedding_api_error",
                    error_message=error_msg,
                    session_id=self.session_id,
                    context={"status_code": response.status_code, "response": response.text[:200]}
                )
                return []
                
        except Exception as e:
            error_msg = f"Embedding生成出错: {e}"
            print(f"❌ {error_msg}")
            
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="embedding_generation_error", 
                error_message=str(e),
                session_id=self.session_id
            )
            return []
    
    def step4_create_agent(self) -> None:
        """步骤4: 创建RAG智能体 (带审计)"""
        print("🤖 步骤4: 创建RAG智能体")
        
        start_time = time.time()
        
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
            
            response_time = int((time.time() - start_time) * 1000)
            
            # 记录智能体创建
            self.auditor.log_event(
                event_type=AuditEventType.AGENT_CREATION,
                level=AuditLevel.INFO,
                action="create_rag_agent",
                user_id=self.user_id,
                session_id=self.session_id,
                resource=self.agent.id,
                details={
                    "agent_name": self.agent.name,
                    "agent_id": self.agent.id,
                    "model": "openai/qwen3",
                    "embedding": "bge/bge-m3",
                    "memory_blocks_count": len(memory_blocks)
                },
                success=True,
                response_time_ms=response_time
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            
        except Exception as e:
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="agent_creation_error",
                error_message=str(e),
                session_id=self.session_id
            )
            print(f"❌ 创建智能体失败: {e}")
    
    def search_similar_chunks(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索相似文档块 (带审计)"""
        if not self.chunk_embeddings:
            return []
        
        start_time = time.time()
        
        # 获取查询的embedding
        try:
            response = requests.post(
                self.embedding_url,
                json={"model": "bge-m3", "input": [query]},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code != 200:
                self.auditor.log_system_error(
                    user_id=self.user_id,
                    error_type="query_embedding_error",
                    error_message=f"查询embedding API失败: {response.status_code}",
                    session_id=self.session_id
                )
                return []
            
            query_embedding = response.json()['data'][0]['embedding']
            
        except Exception as e:
            print(f"查询embedding失败: {e}")
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="query_embedding_error",
                error_message=str(e),
                session_id=self.session_id
            )
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
        results = similarities[:top_k]
        
        # 记录搜索操作
        response_time = int((time.time() - start_time) * 1000)
        self.auditor.log_rag_search(
            user_id=self.user_id,
            query=query,
            results_count=len(results),
            session_id=self.session_id,
            response_time_ms=response_time
        )
        
        return results
    
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
        """RAG问答 (带审计)"""
        print(f"❓ 问题: {question}")
        
        start_time = time.time()
        
        try:
            # 1. 检索相关文档
            relevant_docs = self.search_similar_chunks(question, top_k=3)
            
            if not relevant_docs:
                answer = "抱歉，没有找到相关的文档内容。"
                self.auditor.log_event(
                    event_type=AuditEventType.QUERY_EXECUTION,
                    level=AuditLevel.WARN,
                    action="ask_question_no_results",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    details={
                        "question": question[:100],
                        "question_length": len(question),
                        "results_found": False
                    },
                    success=False
                )
                return answer
            
            print(f"🔍 找到{len(relevant_docs)}个相关片段")
            
            # 2. 构建增强的prompt
            context = "\\n\\n".join([doc['text'] for doc in relevant_docs])
            enhanced_question = f"""基于以下文档内容回答问题：

文档内容：
{context}

问题：{question}

请基于上述文档内容给出准确的回答。"""
            
            # 3. 调用智能体
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=enhanced_question)],
            )
            
            # 提取回答
            answer = ""
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    answer = msg.content
                    print(f"🤖 回答: {msg.content}")
                    break
            
            if not answer:
                answer = "智能体没有返回有效回答"
            
            # 记录成功的问答
            response_time = int((time.time() - start_time) * 1000)
            self.auditor.log_event(
                event_type=AuditEventType.QUERY_EXECUTION,
                level=AuditLevel.INFO,
                action="ask_question",
                user_id=self.user_id,
                session_id=self.session_id,
                details={
                    "question_length": len(question),
                    "answer_length": len(answer),
                    "relevant_docs_found": len(relevant_docs),
                    "max_similarity": max([doc['similarity'] for doc in relevant_docs]) if relevant_docs else 0,
                    "agent_id": self.agent.id
                },
                success=True,
                data_content=question,
                response_time_ms=response_time
            )
            
            # 记录智能体交互
            self.auditor.log_agent_interaction(
                user_id=self.user_id,
                agent_id=self.agent.id,
                message_type="question_answer",
                content_length=len(question) + len(answer),
                session_id=self.session_id
            )
            
            return answer
            
        except Exception as e:
            error_msg = f"处理问题时出错: {e}"
            print(f"❌ 问答过程出错: {e}")
            
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="question_answering_error",
                error_message=str(e),
                session_id=self.session_id,
                context={"question": question[:100]}
            )
            
            return error_msg
    
    def build_rag_system(self, file_path: str) -> bool:
        """构建完整的RAG系统 (带审计)"""
        print("🚀 开始构建RAG系统")
        print("=" * 50)
        
        overall_start_time = time.time()
        
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
            
            # 记录系统构建成功
            total_time = int((time.time() - overall_start_time) * 1000)
            self.auditor.log_event(
                event_type=AuditEventType.SYSTEM_ERROR,  # 重用作为系统事件
                level=AuditLevel.INFO,
                action="build_rag_system_complete",
                user_id=self.user_id,
                session_id=self.session_id,
                resource=Path(file_path).name,
                details={
                    "document_name": Path(file_path).name,
                    "text_chunks": len(self.text_chunks),
                    "embedding_dimension": len(self.chunk_embeddings[0]) if self.chunk_embeddings else 0,
                    "agent_name": self.agent.name,
                    "build_time_ms": total_time
                },
                success=True,
                response_time_ms=total_time
            )
            
            print("\\n" + "=" * 50)
            print("✅ RAG系统构建完成!")
            print(f"   文档: {Path(file_path).name}")
            print(f"   文本块: {len(self.text_chunks)}个")
            print(f"   向量维度: {len(self.chunk_embeddings[0])}")
            print(f"   智能体: {self.agent.name}")
            print(f"   用户: {self.user_id}")
            print(f"   会话: {self.session_id[:8]}...")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统构建失败: {e}")
            self.auditor.log_system_error(
                user_id=self.user_id,
                error_type="rag_system_build_error",
                error_message=str(e),
                session_id=self.session_id,
                context={"file_path": file_path}
            )
            return False
    
    def interactive_demo(self):
        """交互式演示 (带审计)"""
        print("\\n💬 进入交互式问答")
        print("=" * 40)
        print("输入问题，输入'quit'退出，输入'report'查看审计报告")
        
        while True:
            try:
                question = input("\\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if question.lower() == 'report':
                    self.show_audit_report()
                    continue
                
                if not question:
                    continue
                
                answer = self.ask_question(question)
                
            except KeyboardInterrupt:
                print("\\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")
                self.auditor.log_system_error(
                    user_id=self.user_id,
                    error_type="interactive_demo_error",
                    error_message=str(e),
                    session_id=self.session_id
                )
    
    def show_audit_report(self, hours: int = 1):
        """显示审计报告"""
        print("\\n📊 生成审计报告...")
        report = self.auditor.generate_audit_report(hours)
        
        print(f"\\n=== 审计报告 ({report['report_period']}) ===")
        print(f"总事件数: {report['total_events']}")
        print(f"唯一用户数: {report['unique_users']}")
        print(f"系统健康: {report['system_health']}")
        
        print("\\n风险分布:")
        print(f"  高风险: {report['risk_distribution']['high']} 事件")
        print(f"  中风险: {report['risk_distribution']['medium']} 事件") 
        print(f"  低风险: {report['risk_distribution']['low']} 事件")
        
        print("\\n事件类型:")
        for event_type, count in report['event_types'].items():
            print(f"  {event_type}: {count}")
        
        if report['high_risk_events']:
            print(f"\\n⚠️  高风险事件: {len(report['high_risk_events'])}个")
        
        if report['error_count'] > 0:
            print(f"\\n❌ 错误事件: {report['error_count']}个")
    
    def get_user_activity_summary(self, hours: int = 24):
        """获取用户活动摘要"""
        return self.auditor.get_user_activity_summary(self.user_id, hours)
    
    def __del__(self):
        """析构函数：记录会话结束"""
        try:
            self.auditor.log_user_session(
                user_id=self.user_id,
                action="logout", 
                session_id=self.session_id,
                ip_address=self.ip_address
            )
        except:
            pass  # 忽略析构时的错误


def main():
    """主函数 - 带安全审计的RAG系统演示"""
    print("🔒 安全审计RAG系统")
    print("=" * 40)
    
    # 检查文件
    pdf_file = "./jr.pdf"
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        print("请确保当前目录有 jr.pdf 文件")
        return
    
    # 创建带审计的RAG系统
    user_id = input("请输入用户ID (默认: test_user): ").strip() or "test_user"
    
    audited_rag = AuditedQuickRAG(
        user_id=user_id,
        ip_address="127.0.0.1",  # 在实际Web应用中从请求中获取
        user_agent="RAG-Client/1.0"
    )
    
    # 构建系统
    success = audited_rag.build_rag_system(pdf_file)
    
    if success:
        # 快速测试
        print("\\n🧪 快速测试:")
        test_questions = [
            "这个产品的风险等级是什么？",
            "投资期限多长？",
            "密码是什么？"  # 测试敏感词检测
        ]
        
        for question in test_questions:
            print(f"\\n测试问题: {question}")
            answer = audited_rag.ask_question(question)
        
        # 显示初始审计报告
        audited_rag.show_audit_report(hours=1)
        
        # 交互模式
        user_input = input("\\n是否进入交互模式? (y/n): ").strip().lower()
        if user_input in ['y', 'yes']:
            audited_rag.interactive_demo()
    
    else:
        print("❌ 系统构建失败")
        print("\\n请检查:")
        print("1. Letta服务器是否运行 (http://localhost:8283)")
        print("2. BGE-M3服务是否运行 (http://127.0.0.1:8003)")
        print("3. 文件是否存在且可读")


if __name__ == "__main__":
    main()
