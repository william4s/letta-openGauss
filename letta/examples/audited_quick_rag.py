#!/usr/bin/env python3
"""
增强版Letta RAG系统 - 集成审计功能
基于quick_rag_template.py，添加了服务器审计集成
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
from letta.server.audit_system import log_server_event, AuditEventType, AuditLevel


class AuditedQuickRAG:
    """集成审计功能的快速RAG系统"""
    
    def __init__(self, letta_url="http://localhost:8283", embedding_url="http://127.0.0.1:8003/v1/embeddings", user_id="default_user"):
        self.client = Letta(base_url=letta_url)
        self.embedding_url = embedding_url
        self.user_id = user_id
        self.session_id = f"rag_session_{int(time.time())}"
        self.text_chunks = []
        self.chunk_embeddings = []
        self.agent = None
        
        # 记录会话开始
        log_server_event(
            event_type=AuditEventType.USER_SESSION_START,
            level=AuditLevel.INFO,
            action="rag_session_start",
            user_id=self.user_id,
            session_id=self.session_id,
            details={"letta_url": letta_url, "embedding_url": embedding_url}
        )
        
    def step1_extract_text(self, file_path: str) -> str:
        """步骤1: 提取文档文本 (带审计)"""
        print("📄 步骤1: 提取文档文本")
        
        # 记录文档访问事件
        log_server_event(
            event_type=AuditEventType.DOCUMENT_ACCESS,
            level=AuditLevel.INFO,
            action="document_text_extraction",
            user_id=self.user_id,
            session_id=self.session_id,
            resource=file_path,
            details={"file_path": file_path, "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0}
        )
        
        if file_path.endswith('.pdf'):
            return self._extract_pdf_text(file_path)
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            error_msg = f"不支持的文件格式: {file_path}"
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="unsupported_file_format",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=error_msg
            )
            raise ValueError(error_msg)
    
    def _extract_pdf_text(self, pdf_path: str) -> str:
        """提取PDF文本 (带审计)"""
        try:
            import pypdf
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                
                # 记录成功的PDF处理
                log_server_event(
                    event_type=AuditEventType.DOCUMENT_PROCESSING,
                    level=AuditLevel.INFO,
                    action="pdf_text_extraction",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    resource=pdf_path,
                    details={
                        "pages_count": len(reader.pages),
                        "text_length": len(text),
                        "file_size": os.path.getsize(pdf_path)
                    }
                )
                
                print(f"✅ PDF提取成功: {len(reader.pages)}页, {len(text)}字符")
                return text
                
        except ImportError:
            error_msg = "需要安装pypdf: pip install pypdf"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="missing_dependency",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=error_msg
            )
            return ""
        except Exception as e:
            error_msg = f"PDF提取失败: {e}"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="pdf_extraction_failed",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=error_msg
            )
            return ""
    
    def step2_chunk_text(self, text: str, chunk_size: int = 300) -> List[str]:
        """步骤2: 文本分块 (带审计)"""
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
        
        # 记录分块处理
        log_server_event(
            event_type=AuditEventType.DOCUMENT_PROCESSING,
            level=AuditLevel.INFO,
            action="text_chunking",
            user_id=self.user_id,
            session_id=self.session_id,
            details={
                "total_text_length": len(text),
                "chunks_count": len(chunks),
                "chunk_size": chunk_size,
                "avg_chunk_length": sum(len(c) for c in chunks) / len(chunks) if chunks else 0
            }
        )
        
        print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c) for c in chunks)/len(chunks):.1f}字符")
        return chunks
    
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
                
                # 记录成功的embedding生成
                log_server_event(
                    event_type=AuditEventType.EMBEDDING_GENERATION,
                    level=AuditLevel.INFO,
                    action="generate_embeddings",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    response_time_ms=response_time,
                    details={
                        "chunks_count": len(self.text_chunks),
                        "embeddings_count": len(embeddings),
                        "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                        "model": "bge-m3"
                    }
                )
                
                print(f"✅ Embedding生成成功: {len(embeddings)}个向量, 维度{len(embeddings[0])}")
                return embeddings
            else:
                error_msg = f"Embedding调用失败: {response.status_code}"
                print(f"❌ {error_msg}")
                log_server_event(
                    event_type=AuditEventType.SYSTEM_ERROR,
                    level=AuditLevel.ERROR,
                    action="embedding_api_failed",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    success=False,
                    response_time_ms=response_time,
                    error_message=error_msg
                )
                return []
                
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            error_msg = f"Embedding生成出错: {e}"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="embedding_generation_error",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                response_time_ms=response_time,
                error_message=error_msg
            )
            return []
    
    def step4_create_agent(self) -> None:
        """步骤4: 创建RAG智能体 (带审计)"""
        print("🤖 步骤4: 创建RAG智能体")
        
        try:
            memory_blocks = [
                CreateBlock(
                    value="你是一个专业的金融文档问答助手，专门回答人民币理财产品相关问题。请基于提供的文档内容准确回答问题，特别注意产品风险、收益、期限等关键信息。",
                    label="system_instruction",
                ),
                CreateBlock(
                    value=f"当前已加载金融理财产品说明书，共{len(self.text_chunks)}个文档片段，可以回答产品风险、收益、投资期限、费用结构等相关问题。",
                    label="document_status",
                ),
            ]
            
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # Qwen3模型
                embedding="bge/bge-m3",      # BGE-M3嵌入
            )
            
            # 记录智能体创建
            log_server_event(
                event_type=AuditEventType.AGENT_CREATION,
                level=AuditLevel.INFO,
                action="create_rag_agent",
                user_id=self.user_id,
                session_id=self.session_id,
                resource=self.agent.id if self.agent else None,
                details={
                    "agent_name": self.agent.name if self.agent else None,
                    "model": "openai/qwen3",
                    "embedding": "bge/bge-m3",
                    "memory_blocks_count": len(memory_blocks),
                    "document_chunks": len(self.text_chunks)
                }
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            
        except Exception as e:
            error_msg = f"创建智能体失败: {e}"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="agent_creation_failed",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=error_msg
            )
    
    def search_similar_chunks(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索相似文档块 (带审计)"""
        if not self.chunk_embeddings:
            return []
        
        start_time = time.time()
        
        # 记录RAG搜索事件
        log_server_event(
            event_type=AuditEventType.RAG_SEARCH,
            level=AuditLevel.INFO,
            action="search_similar_chunks",
            user_id=self.user_id,
            session_id=self.session_id,
            data_content=query,
            details={
                "query_length": len(query),
                "top_k": top_k,
                "total_chunks": len(self.chunk_embeddings)
            }
        )
        
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
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="query_embedding_failed",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=str(e)
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
        top_results = similarities[:top_k]
        
        response_time = int((time.time() - start_time) * 1000)
        
        # 记录搜索结果
        log_server_event(
            event_type=AuditEventType.RAG_SEARCH,
            level=AuditLevel.INFO,
            action="search_completed",
            user_id=self.user_id,
            session_id=self.session_id,
            response_time_ms=response_time,
            details={
                "query_length": len(query),
                "results_count": len(top_results),
                "top_similarity": top_results[0]['similarity'] if top_results else 0,
                "avg_similarity": sum(r['similarity'] for r in top_results) / len(top_results) if top_results else 0
            }
        )
        
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
        """RAG问答 (带审计)"""
        print(f"❓ 问题: {question}")
        
        start_time = time.time()
        
        # 记录查询事件
        log_server_event(
            event_type=AuditEventType.RAG_QUERY,
            level=AuditLevel.INFO,
            action="user_question",
            user_id=self.user_id,
            session_id=self.session_id,
            data_content=question,
            details={"question_length": len(question)}
        )
        
        # 1. 检索相关文档
        relevant_docs = self.search_similar_chunks(question, top_k=3)
        
        if not relevant_docs:
            response = "抱歉，没有找到相关的文档内容。"
            log_server_event(
                event_type=AuditEventType.RAG_RESPONSE,
                level=AuditLevel.WARN,
                action="no_relevant_docs",
                user_id=self.user_id,
                session_id=self.session_id,
                details={"question": question[:100]}
            )
            return response
        
        print(f"🔍 找到{len(relevant_docs)}个相关片段")
        
        # 2. 构建增强的prompt
        context = "\\n\\n".join([doc['text'] for doc in relevant_docs])
        enhanced_question = f"""基于以下金融理财产品文档内容回答问题：

文档内容：
{context}

问题：{question}

请基于上述文档内容给出准确的回答，特别注意产品风险、收益率、投资期限、费用等关键信息。如果涉及风险评估，请明确提醒用户注意风险。"""
        
        # 3. 调用智能体
        try:
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=enhanced_question)],
            )
            
            response_time = int((time.time() - start_time) * 1000)
            
            # 提取回答
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    answer = msg.content
                    print(f"🤖 回答: {answer}")
                    
                    # 记录成功的响应
                    log_server_event(
                        event_type=AuditEventType.RAG_RESPONSE,
                        level=AuditLevel.INFO,
                        action="agent_response",
                        user_id=self.user_id,
                        session_id=self.session_id,
                        response_time_ms=response_time,
                        details={
                            "question_length": len(question),
                            "answer_length": len(answer),
                            "relevant_docs_count": len(relevant_docs),
                            "context_length": len(context)
                        }
                    )
                    
                    return answer
            
            # 没有找到有效回答
            fallback_response = "智能体没有返回有效回答"
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.WARN,
                action="no_valid_response",
                user_id=self.user_id,
                session_id=self.session_id,
                response_time_ms=response_time,
                success=False
            )
            return fallback_response
            
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            error_msg = f"处理问题时出错: {e}"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="rag_query_error",
                user_id=self.user_id,
                session_id=self.session_id,
                response_time_ms=response_time,
                success=False,
                error_message=error_msg
            )
            return error_msg
    
    def build_rag_system(self, file_path: str) -> bool:
        """构建完整的RAG系统 (带审计)"""
        print("🚀 开始构建增强版RAG系统")
        print("=" * 50)
        
        # 记录系统构建开始
        log_server_event(
            event_type=AuditEventType.DOCUMENT_PROCESSING,
            level=AuditLevel.INFO,
            action="rag_system_build_start",
            user_id=self.user_id,
            session_id=self.session_id,
            resource=file_path,
            details={"file_path": file_path}
        )
        
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
            print("✅ 增强版RAG系统构建完成!")
            print(f"   文档: {Path(file_path).name}")
            print(f"   文本块: {len(self.text_chunks)}个")
            print(f"   向量维度: {len(self.chunk_embeddings[0])}")
            print(f"   智能体: {self.agent.name}")
            print("   🔍 审计功能: 已启用")
            
            # 记录系统构建成功
            log_server_event(
                event_type=AuditEventType.DOCUMENT_PROCESSING,
                level=AuditLevel.INFO,
                action="rag_system_build_success",
                user_id=self.user_id,
                session_id=self.session_id,
                resource=file_path,
                details={
                    "document_name": Path(file_path).name,
                    "text_chunks": len(self.text_chunks),
                    "embedding_dimension": len(self.chunk_embeddings[0]),
                    "agent_id": self.agent.id,
                    "agent_name": self.agent.name
                }
            )
            
            return True
            
        except Exception as e:
            error_msg = f"RAG系统构建失败: {e}"
            print(f"❌ {error_msg}")
            log_server_event(
                event_type=AuditEventType.SYSTEM_ERROR,
                level=AuditLevel.ERROR,
                action="rag_system_build_failed",
                user_id=self.user_id,
                session_id=self.session_id,
                success=False,
                error_message=error_msg
            )
            return False
    
    def interactive_demo(self):
        """交互式演示 (带审计)"""
        print("\\n💬 进入交互式问答")
        print("=" * 40)
        print("输入问题，输入'quit'退出")
        print("🔍 所有操作将被记录到审计日志")
        
        # 记录交互模式开始
        log_server_event(
            event_type=AuditEventType.USER_SESSION_START,
            level=AuditLevel.INFO,
            action="interactive_mode_start",
            user_id=self.user_id,
            session_id=self.session_id
        )
        
        question_count = 0
        
        while True:
            try:
                question = input("\\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    # 记录会话结束
                    log_server_event(
                        event_type=AuditEventType.USER_SESSION_END,
                        level=AuditLevel.INFO,
                        action="interactive_mode_end",
                        user_id=self.user_id,
                        session_id=self.session_id,
                        details={"questions_asked": question_count}
                    )
                    break
                
                if not question:
                    continue
                
                question_count += 1
                answer = self.ask_question(question)
                
            except KeyboardInterrupt:
                print("\\n👋 再见!")
                log_server_event(
                    event_type=AuditEventType.USER_SESSION_END,
                    level=AuditLevel.INFO,
                    action="interactive_mode_interrupted",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    details={"questions_asked": question_count}
                )
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")
                log_server_event(
                    event_type=AuditEventType.SYSTEM_ERROR,
                    level=AuditLevel.ERROR,
                    action="interactive_error",
                    user_id=self.user_id,
                    session_id=self.session_id,
                    error_message=str(e)
                )


def main():
    """主函数 - 增强版RAG系统示例"""
    print("📚 增强版RAG系统 (集成审计功能)")
    print("=" * 50)
    
    # 检查文件
    pdf_file = "./jr.pdf"
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        print("请确保当前目录有 jr.pdf 文件")
        return
    
    # 创建增强版RAG系统
    user_id = input("请输入用户ID (默认: default_user): ").strip() or "default_user"
    rag = AuditedQuickRAG(user_id=user_id)
    
    # 构建系统
    success = rag.build_rag_system(pdf_file)
    
    if success:
        print("\\n🔍 审计功能已启用，所有操作将被记录")
        print("可以访问 http://localhost:8283/v1/audit/dashboard 查看审计仪表板")
        
        # 快速测试
        print("\\n🧪 快速测试:")
        test_questions = [
            "这个产品的风险等级是什么？",
            "投资期限多长？",
            "产品的预期收益率是多少？"
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
