#!/usr/bin/env python3
"""
基于归档记忆的Letta RAG系统
将PDF文档块直接存储到智能体的归档记忆中
"""

import os
import sys
import time
from pathlib import Path
from typing import List

# 添加letta模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate


class ArchivalMemoryRAG:
    """基于归档记忆的RAG系统"""
    
    def __init__(self, letta_url="http://localhost:8283"):
        """初始化RAG系统"""
        print("🚀 初始化基于归档记忆的Letta RAG系统")
        self.client = Letta(base_url=letta_url)
        self.agent = None
        self.text_chunks = []
        
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
            sentence = sentence.strip() + "。"
            
            if not sentence.strip():
                continue
                
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                # 保留重叠部分
                if len(current_chunk) > overlap:
                    overlap_start = len(current_chunk) - overlap
                    overlap_text = current_chunk[overlap_start:]
                    last_period = overlap_text.rfind('。')
                    if last_period != -1:
                        current_chunk = overlap_text[last_period+1:] + sentence
                    else:
                        current_chunk = overlap_text + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        self.text_chunks = chunks
        print(f"✅ 分块完成: {len(chunks)}个块")
        return chunks
    
    def create_agent_with_archival_memory(self, document_name: str) -> bool:
        """创建智能体并设置归档记忆"""
        print("🤖 创建智能体并配置归档记忆")
        
        try:
            system_instruction = f"""你是一个专业的金融文档问答助手，专门回答人民币理财产品相关问题。

你的归档记忆中已经存储了文档"{document_name}"的全部内容，分为{len(self.text_chunks)}个片段。
当用户询问相关问题时，你应该：

1. 使用archival_memory_search函数搜索相关信息
2. 基于检索到的内容提供准确、专业的回答
3. 特别注意产品风险、收益率、投资期限、费用等关键信息
4. 如果涉及风险评估，请明确提醒用户注意风险

你可以使用以下函数：
- archival_memory_search(query): 搜索归档记忆中的相关内容
- archival_memory_insert(content): 向归档记忆中插入新内容
"""
            
            memory_blocks = [
                CreateBlock(
                    value=system_instruction,
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
    
    def store_chunks_in_archival_memory(self) -> bool:
        """将文本块存储到智能体的归档记忆中"""
        print("💾 将文档块存储到归档记忆中")
        
        if not self.agent or not self.text_chunks:
            print("❌ 智能体或文本块未准备好")
            return False
        
        try:
            success_count = 0
            for i, chunk in enumerate(self.text_chunks):
                try:
                    # 为每个块添加标识前缀
                    formatted_chunk = f"[文档片段 {i+1}/{len(self.text_chunks)}]\n{chunk}"
                    
                    # 插入到归档记忆
                    self.client.agents.archival.insert(
                        agent_id=self.agent.id,
                        content=formatted_chunk
                    )
                    success_count += 1
                    
                    if (i + 1) % 10 == 0:
                        print(f"   已存储: {i+1}/{len(self.text_chunks)} 个块")
                        
                except Exception as chunk_error:
                    print(f"❌ 存储第{i+1}个块失败: {chunk_error}")
                    continue
            
            print(f"✅ 成功存储 {success_count}/{len(self.text_chunks)} 个文档块到归档记忆")
            return success_count > 0
            
        except Exception as e:
            print(f"❌ 存储文档块失败: {e}")
            return False
    
    def setup_rag_system(self, file_path: str, chunk_size: int = 800, overlap: int = 200) -> bool:
        """设置完整的RAG系统"""
        print("🚀 设置基于归档记忆的RAG系统")
        print("=" * 50)
        
        try:
            document_name = Path(file_path).name
            
            # 1. 提取文本
            text = self.extract_text_from_pdf(file_path)
            if not text:
                return False
            
            # 2. 文本分块
            chunks = self.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
            if not chunks:
                return False
            
            # 3. 创建智能体
            success = self.create_agent_with_archival_memory(document_name)
            if not success:
                return False
            
            # 4. 存储文档块到归档记忆
            success = self.store_chunks_in_archival_memory()
            if not success:
                return False
            
            print("\n" + "=" * 50)
            print("✅ 基于归档记忆的RAG系统设置完成!")
            print(f"   文档: {document_name}")
            print(f"   文本块: {len(self.text_chunks)}个")
            print(f"   智能体: {self.agent.name}")
            print(f"   归档记忆: 已存储所有文档块")
            print("   💡 智能体现在可以从归档记忆中检索信息")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统设置失败: {e}")
            return False
    
    def chat_with_agent(self, message: str) -> str:
        """与智能体聊天 - 智能体会自动使用归档记忆搜索"""
        if not self.agent:
            return "智能体尚未创建"
        
        try:
            print(f"👤 用户: {message}")
            
            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=message)],
            )
            
            # 提取最后的助手回复
            assistant_reply = ""
            for msg in response.messages:
                if msg.message_type == "assistant_message":
                    assistant_reply = msg.content
                elif msg.message_type == "function_call":
                    # 显示函数调用信息
                    print(f"🔍 智能体调用函数: {msg.function_call.name}")
                    if msg.function_call.name == "archival_memory_search":
                        print(f"   搜索: {msg.function_call.arguments}")
                elif msg.message_type == "function_return":
                    # 显示函数返回结果
                    if len(msg.content) > 200:
                        print(f"📋 归档记忆返回: {msg.content[:200]}...")
                    else:
                        print(f"📋 归档记忆返回: {msg.content}")
            
            print(f"🤖 智能体: {assistant_reply}")
            return assistant_reply
            
        except Exception as e:
            error_msg = f"与智能体聊天时出错: {e}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def test_archival_memory_search(self, query: str) -> None:
        """测试归档记忆搜索功能"""
        if not self.agent:
            print("❌ 智能体尚未创建")
            return
        
        try:
            print(f"🔍 测试归档记忆搜索: {query}")
            
            # 直接调用归档记忆搜索
            results = self.client.agents.archival.list(
                agent_id=self.agent.id,
                query=query,
                limit=3
            )
            
            print(f"📋 找到 {len(results)} 个相关结果:")
            for i, result in enumerate(results, 1):
                print(f"   结果 {i}: {result.content[:100]}...")
                
        except Exception as e:
            print(f"❌ 归档记忆搜索失败: {e}")
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n💬 进入交互式对话模式")
        print("=" * 40)
        print("智能体已配备归档记忆，会自动搜索文档回答问题")
        print("输入问题，输入'test:查询内容'可测试归档记忆搜索")
        print("输入'quit'退出")
        
        while True:
            try:
                question = input("\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if not question:
                    continue
                
                # 测试命令
                if question.startswith('test:'):
                    test_query = question[5:].strip()
                    if test_query:
                        self.test_archival_memory_search(test_query)
                    continue
                
                self.chat_with_agent(question)
                
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")


def main():
    """主函数"""
    # 配置
    pdf_file = "/home/shiwc24/ospp/letta-openGauss/letta/examples/jr.pdf"
    chunk_size = 800
    overlap = 200
    
    print("🧠 基于归档记忆的Letta RAG系统")
    print("=" * 50)
    print(f"文档路径: {pdf_file}")
    print(f"块大小: {chunk_size}, 重叠: {overlap}")
    print("文档块将存储到智能体的归档记忆中")
    print("=" * 50)
    
    # 检查文件
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        return
    
    # 创建RAG系统
    rag_system = ArchivalMemoryRAG()
    
    # 设置系统
    success = rag_system.setup_rag_system(pdf_file, chunk_size=chunk_size, overlap=overlap)
    
    if success:
        # 测试归档记忆搜索
        print("\n🧪 测试归档记忆搜索功能:")
        test_queries = ["风险", "收益率", "投资期限"]
        for query in test_queries:
            rag_system.test_archival_memory_search(query)
            print()
        
        # 快速测试对话
        print("\n🧪 快速测试对话:")
        test_questions = [
            "这个产品的风险等级是什么？",
            "投资期限多长？",
            "产品的预期收益率是多少？"
        ]
        
        for question in test_questions:
            print(f"\n" + "="*30)
            rag_system.chat_with_agent(question)
        
        # 交互模式
        user_input = input("\n是否进入交互模式? (y/n): ").strip().lower()
        if user_input in ['y', 'yes', '是']:
            rag_system.interactive_demo()
    
    else:
        print("❌ 系统设置失败")
        print("\n请检查:")
        print("1. Letta服务器是否运行 (http://localhost:8283)")
        print("2. 文件是否存在且可读")


if __name__ == "__main__":
    main()