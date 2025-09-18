#!/usr/bin/env python3
"""
带审计功能的Memory Blocks RAG系统
完整记录知识库生命周期、RAG查询流程和安全事件
"""

import os
import sys
import time
import json
import sqlite3
import hashlib
import uuid
import datetime
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import timezone

# 添加letta模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

try:
    from letta_client import Letta, CreateBlock, MessageCreate
except ImportError:
    print("使用旧版客户端")
    from letta.client import Letta
    from letta.schemas.block import CreateBlock
    from letta.schemas.message import MessageCreate


class RAGAuditor:
    """RAG系统专用审计器 - 审计用户问题和LLM回答"""
    
    def __init__(self, db_path: str = "./logs/rag_audit.db"):
        """初始化审计器"""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()
        
        # 敏感关键词列表
        self.sensitive_keywords = [
            "密码", "password", "身份证", "银行卡", "账号", "account",
            "个人信息", "隐私", "机密", "秘密", "confidential",
            "信用卡", "社保", "医保", "工资", "薪资", "财务",
            "删除", "修改", "更改", "delete", "modify", "alter"
        ]
        
        # 风险模式
        self.risk_patterns = [
            r".*如何.*绕过.*",
            r".*破解.*",
            r".*漏洞.*",
            r".*攻击.*",
            r".*黑客.*",
            r".*泄露.*"
        ]
    
    def init_database(self):
        """初始化审计数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rag_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                session_id TEXT,
                user_id TEXT,
                event_type TEXT NOT NULL,
                user_question TEXT,
                llm_response TEXT,
                sensitive_score INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'LOW',
                keywords_detected TEXT,
                response_time_ms INTEGER,
                document_chunks_used INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                metadata TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def calculate_sensitivity_score(self, text: str) -> tuple:
        """计算敏感度评分"""
        if not text:
            return 0, []
        
        text_lower = text.lower()
        detected_keywords = []
        sensitivity_score = 0
        
        # 检查敏感关键词
        for keyword in self.sensitive_keywords:
            if keyword.lower() in text_lower:
                detected_keywords.append(keyword)
                sensitivity_score += 1
        
        # 检查风险模式
        for pattern in self.risk_patterns:
            if re.search(pattern, text_lower):
                detected_keywords.append(f"RISK_PATTERN: {pattern}")
                sensitivity_score += 3
        
        return sensitivity_score, detected_keywords
    
    def assess_risk_level(self, user_question: str, llm_response: str) -> str:
        """评估对话风险等级"""
        question_score, _ = self.calculate_sensitivity_score(user_question)
        response_score, _ = self.calculate_sensitivity_score(llm_response)
        
        total_score = question_score + response_score
        
        if total_score >= 5:
            return "HIGH"
        elif total_score >= 2:
            return "MEDIUM"
        else:
            return "LOW"
    
    def log_conversation(self, 
                        user_question: str,
                        llm_response: str,
                        session_id: str = None,
                        user_id: str = "anonymous",
                        response_time_ms: int = None,
                        document_chunks_used: int = None,
                        ip_address: str = None,
                        user_agent: str = None,
                        metadata: dict = None):
        """记录对话审计日志"""
        
        # 计算敏感度和风险
        q_score, q_keywords = self.calculate_sensitivity_score(user_question)
        r_score, r_keywords = self.calculate_sensitivity_score(llm_response)
        total_score = q_score + r_score
        all_keywords = list(set(q_keywords + r_keywords))
        
        risk_level = self.assess_risk_level(user_question, llm_response)
        
        # 生成会话ID
        if not session_id:
            session_id = hashlib.md5(f"{user_id}{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO rag_audit_logs (
                timestamp, session_id, user_id, event_type,
                user_question, llm_response, sensitive_score, risk_level,
                keywords_detected, response_time_ms, document_chunks_used,
                ip_address, user_agent, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.datetime.now(timezone.utc).isoformat(),
            session_id,
            user_id,
            "CONVERSATION",
            user_question,
            llm_response,
            total_score,
            risk_level,
            json.dumps(all_keywords, ensure_ascii=False),
            response_time_ms,
            document_chunks_used,
            ip_address,
            user_agent,
            json.dumps(metadata, ensure_ascii=False) if metadata else None
        ))
        
        conn.commit()
        conn.close()
        
        # 控制台日志
        risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
        print(f"\n📊 对话审计:")
        print(f"   风险等级: {risk_emoji.get(risk_level, '⚪')} {risk_level}")
        print(f"   敏感度评分: {total_score}")
        if all_keywords:
            print(f"   检测到关键词: {', '.join(all_keywords[:5])}")
        if risk_level == "HIGH":
            print(f"   ⚠️ 高风险对话已记录!")
    
    def get_conversation_stats(self, hours: int = 24) -> dict:
        """获取对话统计"""
        since_time = (datetime.datetime.now(timezone.utc).timestamp() - hours * 3600)
        since_iso = datetime.datetime.fromtimestamp(since_time, timezone.utc).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_conversations,
                COUNT(CASE WHEN risk_level = 'HIGH' THEN 1 END) as high_risk,
                COUNT(CASE WHEN risk_level = 'MEDIUM' THEN 1 END) as medium_risk,
                COUNT(CASE WHEN risk_level = 'LOW' THEN 1 END) as low_risk,
                AVG(sensitive_score) as avg_sensitivity,
                COUNT(DISTINCT user_id) as unique_users
            FROM rag_audit_logs 
            WHERE timestamp > ?
        """, (since_iso,))
        
        result = cursor.fetchone()
        conn.close()
        
        return {
            "total_conversations": result[0] or 0,
            "high_risk": result[1] or 0,
            "medium_risk": result[2] or 0,
            "low_risk": result[3] or 0,
            "avg_sensitivity": round(result[4] or 0, 2),
            "unique_users": result[5] or 0
        }


class AuditedMemoryBlockRAG:
    """带审计功能的Memory Blocks RAG系统"""
    
    def __init__(self, letta_url="http://localhost:8283"):
        """初始化RAG系统"""
        print("🚀 初始化带审计功能的Memory Block RAG系统")
        self.client = Letta(base_url=letta_url)
        self.text_chunks = []
        self.agent = None
        self.auditor = RAGAuditor()
        self.session_id = hashlib.md5(f"rag_session_{datetime.datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """从PDF文件中提取文本"""
        print(f"📄 从PDF中提取文本: {pdf_path}")
        
        try:
            import pypdf
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text = ""
                for page_num, page in enumerate(reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text.strip():  # 只添加非空页面
                        text += f"\n\n=== 第{page_num}页 ===\n{page_text}"
                
                print(f"✅ PDF提取成功: {len(reader.pages)}页, {len(text)}字符")
                return text
                
        except ImportError:
            print("❌ 需要安装pypdf: pip install pypdf")
            return ""
        except Exception as e:
            print(f"❌ PDF提取失败: {e}")
            return ""
    
    def chunk_text_for_memory(self, text: str, chunk_size: int = 800) -> List[Dict]:
        """将文本分割成适合存储在memory_blocks中的块（较小以避免网页端问题）"""
        print(f"✂️ 将文本分割成Memory Blocks (大小={chunk_size})")
        
        if not text:
            return []
        
        # 按页面分割
        pages = text.split("=== 第")
        chunks = []
        chunk_id = 1
        
        for i, page_content in enumerate(pages):
            if not page_content.strip():
                continue
                
            # 重新添加页面标识
            if i > 0:  # 第一个元素是空的或者前言
                page_content = "=== 第" + page_content
            
            # 如果页面内容太长，进一步分割
            if len(page_content) > chunk_size:
                # 按段落分割
                paragraphs = page_content.split('\n\n')
                current_chunk = ""
                
                for paragraph in paragraphs:
                    if len(current_chunk) + len(paragraph) < chunk_size:
                        current_chunk += paragraph + '\n\n'
                    else:
                        if current_chunk.strip():
                            chunks.append({
                                'id': chunk_id,
                                'content': current_chunk.strip(),
                                'label': f"doc_chunk_{chunk_id}",
                                'type': 'document_content'
                            })
                            chunk_id += 1
                        
                        current_chunk = paragraph + '\n\n'
                
                # 添加最后一个块
                if current_chunk.strip():
                    chunks.append({
                        'id': chunk_id,
                        'content': current_chunk.strip(),
                        'label': f"doc_chunk_{chunk_id}",
                        'type': 'document_content'
                    })
                    chunk_id += 1
            else:
                # 页面内容适中，直接作为一个块
                chunks.append({
                    'id': chunk_id,
                    'content': page_content.strip(),
                    'label': f"doc_chunk_{chunk_id}",
                    'type': 'document_content'
                })
                chunk_id += 1
        
        self.text_chunks = chunks
        print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c['content']) for c in chunks)/max(1, len(chunks)):.1f}字符")
        return chunks
    
    def create_agent_with_memory_blocks(self, document_name: str) -> bool:
        """创建包含PDF内容的智能体（优化memory blocks数量）"""
        print("🤖 创建带Memory Blocks的RAG智能体")
        
        if not self.text_chunks:
            print("❌ 没有文本块可以处理")
            return False
        
        try:
            # 创建memory_blocks列表
            memory_blocks = []
            
            # 添加系统指令
            system_instruction = f"""你是一个专业的文档问答助手，专门回答基于已加载文档的问题。

文档信息:
- 文档名称: {document_name}
- 文档块数: {len(self.text_chunks)}

请注意:
1. 仔细阅读用户问题，在你的记忆中查找相关信息
2. 基于文档内容给出准确、详细的回答
3. 如果涉及具体数据、日期、条款等，请引用文档内容
4. 如果文档中没有相关信息，请明确说明
5. 保持回答的专业性和准确性
6. 使用中文回答，纯文字格式，不使用markdown或html
7. 对于敏感问题要特别谨慎处理

你的记忆中已加载文档内容，可直接回答问题。所有对话都会被审计记录。"""

            memory_blocks.append(CreateBlock(
                value=system_instruction,
                label="system_instruction",
            ))
            
            # 限制memory blocks数量以避免网页端问题
            max_blocks = min(len(self.text_chunks), 5)  # 最多5个文档块
            
            # 添加选定的文档块到memory_blocks
            for i in range(max_blocks):
                chunk = self.text_chunks[i]
                memory_blocks.append(CreateBlock(
                    value=chunk['content'],
                    label=chunk['label'],
                ))
            
            print(f"📝 准备创建智能体，包含 {len(memory_blocks)} 个memory blocks")
            
            # 创建智能体
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # Qwen3模型
                embedding="bge/bge-m3",      # 虽然不用于检索，但系统要求指定
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            print(f"   Memory Blocks数量: {len(memory_blocks)}")
            print(f"   审计功能已启用")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建智能体失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def ask_question(self, question: str, user_id: str = "user") -> str:
        """带审计的问答功能"""
        print(f"❓ 问题: {question}")
        
        if not self.agent:
            return "❌ 智能体未初始化，请先构建RAG系统"
        
        start_time = time.time()
        
        try:
            # 构建提示
            enhanced_question = f"""请基于你记忆中的文档内容回答以下问题：

问题: {question}

请仔细检查你的记忆块中的文档内容，给出准确详细的回答。如果需要引用具体内容，请指出来自文档的哪个部分。"""

            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=enhanced_question)],
            )
            
            # 提取回答
            answer = ""
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    answer = msg.content
                    break
            
            if not answer:
                answer = "智能体没有返回有效回答"
            
            # 记录审计日志
            response_time = int((time.time() - start_time) * 1000)
            self.auditor.log_conversation(
                user_question=question,
                llm_response=answer,
                session_id=self.session_id,
                user_id=user_id,
                response_time_ms=response_time,
                document_chunks_used=len(self.text_chunks),
                metadata={"agent_id": self.agent.id, "model": "qwen3"}
            )
            
            print(f"🤖 回答: {answer}")
            return answer
            
        except Exception as e:
            error_msg = f"处理问题时出错: {e}"
            print(f"❌ {error_msg}")
            
            # 记录错误审计
            self.auditor.log_conversation(
                user_question=question,
                llm_response=error_msg,
                session_id=self.session_id,
                user_id=user_id,
                response_time_ms=int((time.time() - start_time) * 1000),
                document_chunks_used=0,
                metadata={"error": str(e), "model": "qwen3"}
            )
            
            return error_msg
    
    def build_audited_rag_system(self, file_path: str, chunk_size: int = 800) -> bool:
        """构建带审计的完整RAG系统"""
        print("🚀 开始构建带审计功能的Memory Block RAG系统")
        print("=" * 60)
        
        try:
            document_name = Path(file_path).name
            
            # 步骤1: 提取文本
            text = self.extract_text_from_pdf(file_path)
            if not text:
                return False
            
            # 步骤2: 文本分块
            chunks = self.chunk_text_for_memory(text, chunk_size=chunk_size)
            if not chunks:
                return False
            
            # 步骤3: 创建带有memory blocks的智能体
            success = self.create_agent_with_memory_blocks(document_name)
            if not success:
                return False
            
            print("\n" + "=" * 60)
            print("✅ 带审计功能的Memory Block RAG系统构建完成!")
            print(f"   文档: {document_name}")
            print(f"   Memory Blocks: {min(len(self.text_chunks), 5) + 1}个 (包含系统指令)")
            print(f"   文档块: {len(self.text_chunks)}个 (使用前5个)")
            print(f"   智能体: {self.agent.name}")
            print(f"   审计数据库: {self.auditor.db_path}")
            print(f"   会话ID: {self.session_id}")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统构建失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def show_audit_stats(self):
        """显示审计统计"""
        print("\n📊 审计统计 (最近24小时):")
        print("=" * 50)
        
        stats = self.auditor.get_conversation_stats(24)
        
        print(f"总对话数: {stats['total_conversations']}")
        print(f"高风险: 🔴 {stats['high_risk']}")
        print(f"中风险: 🟡 {stats['medium_risk']}")
        print(f"低风险: 🟢 {stats['low_risk']}")
        print(f"平均敏感度: {stats['avg_sensitivity']}")
        print(f"独立用户: {stats['unique_users']}")
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n💬 进入带审计功能的交互式问答")
        print("=" * 60)
        print("输入问题，输入'stats'查看统计，输入'quit'退出")
        
        user_id = input("请输入用户ID (回车使用默认): ").strip() or "demo_user"
        
        while True:
            try:
                question = input(f"\n❓ [{user_id}] 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if question.lower() in ['stats', '统计']:
                    self.show_audit_stats()
                    continue
                
                if not question:
                    continue
                
                answer = self.ask_question(question, user_id=user_id)
                
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")


def main():
    """主函数 - 带审计功能的Memory Block RAG系统示例"""
    # 配置
    pdf_file = "/home/shiwc24/ospp/letta-openGauss/letta/examples/jr.pdf"
    chunk_size = 800
    
    print("📚 带审计功能的Memory Blocks RAG系统")
    print("=" * 60)
    print(f"文档路径: {pdf_file}")
    print(f"块大小: {chunk_size}字符")
    print(f"存储方式: 直接存储到智能体Memory Blocks")
    print(f"审计功能: 用户问题 + LLM回答 + 风险评估")
    print("=" * 60)
    
    # 检查文件
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        return
    
    # 创建RAG系统
    rag = AuditedMemoryBlockRAG()
    
    # 构建系统
    success = rag.build_audited_rag_system(pdf_file, chunk_size=chunk_size)
    
    if success:
        # 快速测试
        print("\n🧪 快速测试:")
        test_questions = [
            "这个文档的主要内容是什么？",
            "文档中是否包含敏感信息？",
        ]
        
        for question in test_questions:
            print(f"\n测试问题: {question}")
            answer = rag.ask_question(question, user_id="test_user")
        
        # 显示审计统计
        rag.show_audit_stats()
        
        # 交互模式
        user_input = input("\n是否进入交互模式? (y/n): ").strip().lower()
        if user_input in ['y', 'yes', '是', 'y']:
            rag.interactive_demo()
    
    else:
        print("❌ 系统构建失败")
        print("\n请检查:")
        print("1. Letta服务器是否运行 (http://localhost:8283)")
        print("2. 文件是否存在且可读")
        print("3. pypdf是否已安装 (pip install pypdf)")


if __name__ == "__main__":
    main()