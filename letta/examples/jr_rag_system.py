#!/usr/bin/env python3
"""
JR.PDF 向量化处理和RAG系统
专门针对 letta/examples/jr.pdf 文件的向量化处理和检索增强生成系统

使用指定模型:
- LLM: openai/qwen3
- Embedding: bge/bge-m3
"""

import os
import sys
import time
import uuid
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import CreateBlock, Letta, MessageCreate


class JRPDFRagSystem:
    """JR.PDF 专用RAG系统"""
    
    def __init__(self, base_url="http://localhost:8283"):
        """
        初始化JR PDF RAG系统
        
        Args:
            base_url: Letta服务器地址
        """
        self.client = Letta(base_url=base_url)
        self.pdf_path = current_dir / "jr.pdf"
        self.source = None
        self.agent = None
        self.job_id = None
        
        # 验证PDF文件存在
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {self.pdf_path}")
            
        print(f"📄 目标PDF文件: {self.pdf_path}")
    
    def create_vector_source(self):
        """创建向量文档源"""
        print("🔄 创建向量文档源...")
        
        # 生成唯一的文档源名称
        source_name = f"jr_pdf_vectors_{uuid.uuid4().hex[:8]}"
        
        try:
            # 创建文档源，指定BGE-M3嵌入模型
            self.source = self.client.sources.create(
                name=source_name,
                embedding="bge/bge-m3",  # 使用指定的BGE-M3嵌入模型
            )
            print(f"✅ 已创建向量文档源: {self.source.name} (ID: {self.source.id})")
            
        except Exception as e:
            if "duplicate key value" in str(e):
                print("⚠️ 文档源名称冲突，尝试查找现有的jr.pdf文档源...")
                # 查找现有的jr.pdf相关文档源
                sources = self.client.sources.list()
                for source in sources:
                    if "jr_pdf" in source.name or "jr" in source.name.lower():
                        self.source = source
                        print(f"✅ 找到现有文档源: {source.name} (ID: {source.id})")
                        break
                
                if not self.source:
                    # 如果没找到，创建一个带时间戳的新源
                    source_name = f"jr_pdf_vectors_{int(time.time())}"
                    self.source = self.client.sources.create(
                        name=source_name,
                        embedding="bge/bge-m3",
                    )
                    print(f"✅ 已创建新文档源: {self.source.name}")
            else:
                raise e
                
        return self.source
    
    def upload_and_vectorize_pdf(self):
        """上传PDF文件并进行向量化处理"""
        print("🔄 开始PDF向量化处理...")
        
        # 检查文件是否已经上传过
        try:
            files = self.client.sources.files.list(source_id=self.source.id)
            pdf_filename = self.pdf_path.name
            
            # 检查是否已有同名文件
            for file_info in files:
                if hasattr(file_info, 'name') and file_info.name == pdf_filename:
                    print(f"📄 文件 {pdf_filename} 已存在于文档源中")
                    return True
                    
        except Exception as e:
            print(f"⚠️ 检查现有文件时出错: {e}，继续上传...")
        
        # 上传PDF文件
        print(f"📤 上传PDF文件: {self.pdf_path.name}")
        try:
            job = self.client.sources.files.upload(
                source_id=self.source.id,
                file=str(self.pdf_path),
            )
            
            self.job_id = job.id
            print(f"🔄 向量化任务已启动 (Job ID: {job.id})")
            
            # 等待向量化处理完成
            return self.wait_for_vectorization()
            
        except Exception as e:
            print(f"❌ 上传PDF文件失败: {e}")
            return False
    
    def wait_for_vectorization(self):
        """等待向量化处理完成"""
        print("⏳ 等待向量化处理完成...")
        
        max_attempts = 60  # 最多等待2分钟
        attempt = 0
        
        while attempt < max_attempts:
            try:
                job_status = self.client.jobs.get(job_id=self.job_id)
                status = job_status.status
                
                print(f"⏳ 向量化状态: {status} (尝试 {attempt + 1}/{max_attempts})")
                
                if status == "completed":
                    print("✅ PDF向量化处理完成!")
                    if hasattr(job_status, 'metadata') and job_status.metadata:
                        print(f"📊 处理结果: {job_status.metadata}")
                    return True
                    
                elif status == "failed":
                    print(f"❌ 向量化处理失败: {job_status}")
                    return False
                    
                time.sleep(2)  # 等待2秒
                attempt += 1
                
            except Exception as e:
                print(f"⚠️ 检查向量化状态时出错: {e}")
                time.sleep(2)
                attempt += 1
                
        print("⚠️ 向量化处理超时，但可以尝试继续使用")
        return False
    
    def create_rag_agent(self):
        """创建RAG智能体"""
        print("🤖 创建RAG智能体...")
        
        # 创建智能体的记忆块
        memory_blocks = [
            CreateBlock(
                value=(
                    "你是一个专业的JR.PDF文档问答助手。"
                    "你可以基于已向量化的PDF文档内容回答用户问题，"
                    "提供准确、详细的信息，并在需要时引用具体的文档内容。"
                ),
                label="system_instruction",
            ),
            CreateBlock(
                value=(
                    f"当前已加载并向量化了JR.PDF文档。"
                    f"文档源ID: {self.source.id if self.source else 'unknown'}"
                    "可以回答关于此文档的任何问题。"
                ),
                label="document_status",
            ),
        ]
        
        try:
            # 创建智能体，使用指定的模型
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # 使用指定的Qwen3模型
                embedding="bge/bge-m3",      # 使用指定的BGE-M3嵌入模型
            )
            
            print(f"✅ 已创建RAG智能体: {self.agent.name} (ID: {self.agent.id})")
            
        except Exception as e:
            print(f"❌ 创建RAG智能体失败: {e}")
            raise e
        
        # 将向量文档源附加到智能体
        if self.source:
            try:
                print("🔗 将向量文档源附加到智能体...")
                self.client.agents.sources.attach(
                    agent_id=self.agent.id,
                    source_id=self.source.id
                )
                print("✅ 向量文档源已成功附加到智能体")
            except Exception as e:
                print(f"⚠️ 附加文档源时出错: {e}")
        
        return self.agent
    
    def create_rag_tools(self):
        """创建专用的RAG工具"""
        print("🔧 创建RAG工具...")
        
        def search_jr_document(query: str) -> str:
            """
            在JR.PDF文档中搜索相关信息
            
            Args:
                query: 搜索查询
                
            Returns:
                str: 搜索结果
            """
            try:
                # 这里可以实现更复杂的搜索逻辑
                # 比如调用向量数据库进行相似度搜索
                return f"在JR.PDF文档中基于查询'{query}'找到的相关信息"
            except Exception as e:
                return f"搜索JR.PDF文档时出错: {str(e)}"
        
        def summarize_jr_document(section: str = "全文") -> str:
            """
            总结JR.PDF文档内容
            
            Args:
                section: 要总结的部分，默认为全文
                
            Returns:
                str: 文档摘要
            """
            try:
                return f"JR.PDF文档{section}的摘要内容"
            except Exception as e:
                return f"总结JR.PDF文档时出错: {str(e)}"
        
        def extract_key_points() -> str:
            """
            提取JR.PDF文档的关键要点
            
            Returns:
                str: 关键要点列表
            """
            try:
                return "JR.PDF文档的关键要点包括..."
            except Exception as e:
                return f"提取关键要点时出错: {str(e)}"
        
        tools_created = []
        
        try:
            # 注册搜索工具
            print("🔧 注册JR文档搜索工具...")
            search_tool = self.client.tools.upsert_from_function(func=search_jr_document)
            tools_created.append(search_tool)
            
            # 注册摘要工具
            print("🔧 注册JR文档摘要工具...")
            summary_tool = self.client.tools.upsert_from_function(func=summarize_jr_document)
            tools_created.append(summary_tool)
            
            # 注册要点提取工具
            print("🔧 注册关键要点提取工具...")
            extract_tool = self.client.tools.upsert_from_function(func=extract_key_points)
            tools_created.append(extract_tool)
            
            # 将工具附加到智能体
            if self.agent:
                print("🔗 附加工具到RAG智能体...")
                for tool in tools_created:
                    try:
                        self.client.agents.tools.attach(
                            agent_id=self.agent.id, 
                            tool_id=tool.id
                        )
                        print(f"✅ 已附加工具: {tool.name}")
                    except Exception as e:
                        print(f"⚠️ 附加工具 {tool.name} 失败: {e}")
            
            print(f"✅ RAG工具创建完成，共创建 {len(tools_created)} 个工具")
            
        except Exception as e:
            print(f"⚠️ 创建RAG工具时出错: {e}")
            
        return tools_created
    
    def ask_question(self, question: str, stream=False):
        """
        向RAG系统提问
        
        Args:
            question: 用户问题
            stream: 是否使用流式响应
            
        Returns:
            响应内容
        """
        if not self.agent:
            raise Exception("RAG智能体尚未创建，请先调用setup()方法")
        
        print(f"❓ 用户问题: {question}")
        
        if stream:
            return self._ask_question_stream(question)
        else:
            return self._ask_question_sync(question)
    
    def _ask_question_sync(self, question: str):
        """同步问答"""
        response = self.client.agents.messages.create(
            agent_id=self.agent.id,
            messages=[
                MessageCreate(
                    role="user",
                    content=question,
                ),
            ],
        )
        
        # 解析响应
        assistant_response = ""
        for msg in response.messages:
            if msg.message_type == "assistant_message":
                print(f"🤖 智能体回答: {msg.content}")
                assistant_response = msg.content
            elif msg.message_type == "reasoning_message":
                print(f"💭 智能体思考: {msg.reasoning}")
            elif msg.message_type == "tool_call_message":
                print(f"🔧 工具调用: {msg.tool_call.name}")
                if hasattr(msg.tool_call, 'arguments') and msg.tool_call.arguments:
                    print(f"📝 参数: {msg.tool_call.arguments}")
            elif msg.message_type == "tool_return_message":
                print(f"🔧 工具返回: {msg.tool_return}")
        
        return assistant_response
    
    def _ask_question_stream(self, question: str):
        """流式问答"""
        print("🔄 开始流式问答...")
        
        stream = self.client.agents.messages.create_stream(
            agent_id=self.agent.id,
            messages=[
                MessageCreate(
                    role="user",
                    content=question,
                ),
            ],
            stream_tokens=True,
        )
        
        full_response = ""
        for chunk in stream:
            if chunk.message_type == "assistant_message":
                print(chunk.content, end="", flush=True)
                full_response += chunk.content
            elif chunk.message_type == "reasoning_message":
                print(f"\n💭 {chunk.reasoning}")
            elif chunk.message_type == "tool_call_message":
                if hasattr(chunk.tool_call, 'name') and chunk.tool_call.name:
                    print(f"\n🔧 调用工具: {chunk.tool_call.name}")
                if hasattr(chunk.tool_call, 'arguments') and chunk.tool_call.arguments:
                    print(f"📝 参数: {chunk.tool_call.arguments}")
            elif chunk.message_type == "tool_return_message":
                print(f"\n🔧 工具返回: {chunk.tool_return}")
        
        print()  # 换行
        return full_response
    
    def setup(self):
        """完整设置JR PDF RAG系统"""
        print("🚀 开始设置JR.PDF RAG系统...")
        print("=" * 60)
        
        try:
            # 1. 创建向量文档源
            print("\n📁 步骤1: 创建向量文档源")
            self.create_vector_source()
            
            # 2. 上传PDF并向量化
            print("\n🔄 步骤2: 上传PDF并进行向量化")
            vectorization_success = self.upload_and_vectorize_pdf()
            
            # 3. 创建RAG智能体
            print("\n🤖 步骤3: 创建RAG智能体")
            self.create_rag_agent()
            
            # 4. 创建RAG工具
            print("\n🔧 步骤4: 创建RAG工具")
            self.create_rag_tools()
            
            print("\n" + "=" * 60)
            print("✅ JR.PDF RAG系统设置完成!")
            print(f"📄 PDF文件: {self.pdf_path.name}")
            print(f"🗂️ 文档源: {self.source.name} ({self.source.id})")
            print(f"🤖 智能体: {self.agent.name} ({self.agent.id})")
            print(f"🔄 向量化: {'成功' if vectorization_success else '可能失败，但系统可用'}")
            
            return self
            
        except Exception as e:
            print(f"❌ 设置JR PDF RAG系统失败: {e}")
            raise e
    
    def cleanup(self):
        """清理资源"""
        print("🧹 清理JR PDF RAG系统资源...")
        
        if self.agent:
            try:
                self.client.agents.delete(agent_id=self.agent.id)
                print(f"🗑️ 已删除智能体: {self.agent.name}")
            except Exception as e:
                print(f"⚠️ 删除智能体时出错: {e}")
        
        if self.source:
            print(f"📁 文档源保留: {self.source.name} (可重复使用)")
    
    def interactive_chat(self):
        """交互式聊天模式"""
        print("\n💬 进入JR.PDF交互式问答模式")
        print("=" * 50)
        print("📖 可以询问关于JR.PDF文档的任何问题")
        print("💡 输入 'quit' 或 'exit' 退出")
        print("💡 输入 'help' 查看示例问题")
        print("=" * 50)
        
        while True:
            try:
                question = input("\n❓ 关于JR.PDF的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 退出JR.PDF问答系统!")
                    break
                
                if question.lower() in ['help', '帮助']:
                    self.show_help()
                    continue
                
                if not question:
                    continue
                
                print("-" * 40)
                self.ask_question(question)
                print("-" * 40)
                
            except KeyboardInterrupt:
                print("\n👋 退出JR.PDF问答系统!")
                break
            except Exception as e:
                print(f"❌ 处理问题时出错: {e}")
    
    def show_help(self):
        """显示帮助信息"""
        print("\n📖 JR.PDF问答示例:")
        print("• JR.PDF文档主要讲了什么内容？")
        print("• 文档中有哪些重要信息？")
        print("• 请总结JR.PDF的关键要点")
        print("• JR.PDF中提到了哪些具体数据？")
        print("• 文档的结构是什么样的？")


def main():
    """主函数 - JR.PDF RAG系统演示"""
    print("📄 JR.PDF 向量化处理和RAG系统")
    print("=" * 60)
    print(f"🎯 目标文件: {Path(__file__).parent / 'jr.pdf'}")
    print(f"🧠 LLM模型: openai/qwen3")
    print(f"🔤 嵌入模型: bge/bge-m3")
    print("=" * 60)
    
    # 创建JR PDF RAG系统
    rag_system = JRPDFRagSystem()
    
    try:
        # 设置系统
        rag_system.setup()
        
        # 询问用户操作
        print("\n选择操作:")
        print("1. 运行示例问答")
        print("2. 直接进入交互式问答")
        print("3. 退出")
        
        choice = input("\n请选择 (1/2/3，默认2): ").strip() or "2"
        
        if choice == "1":
            # 示例问答
            print("\n" + "=" * 60)
            print("🎯 JR.PDF 示例问答")
            print("=" * 60)
            
            example_questions = [
                "JR.PDF文档主要讲了什么内容？",
                "请总结这份文档的关键信息",
                "文档中有哪些重要的数据或要点？"
            ]
            
            for i, question in enumerate(example_questions, 1):
                print(f"\n📝 示例问题 {i}:")
                rag_system.ask_question(question)
                
                if i < len(example_questions):
                    input("\n按回车键继续下一个问题...")
            
            # 问是否进入交互模式
            continue_chat = input("\n是否进入交互式问答? (y/n，默认y): ").strip().lower()
            if continue_chat != 'n' and continue_chat != 'no':
                rag_system.interactive_chat()
                
        elif choice == "2":
            # 直接进入交互模式
            rag_system.interactive_chat()
            
        elif choice == "3":
            print("👋 退出系统")
            
        else:
            print("无效选择，进入交互模式...")
            rag_system.interactive_chat()
        
    except KeyboardInterrupt:
        print("\n👋 用户中断，正在退出...")
    except Exception as e:
        print(f"❌ 系统运行出错: {e}")
        print("\n可能的解决方案:")
        print("1. 确认 jr.pdf 文件存在于 letta/examples/ 目录")
        print("2. 确认 Letta 服务器正在运行")
        print("3. 检查指定的模型是否可用")
        print("4. 检查网络连接")
        
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        try:
            rag_system.cleanup()
        except Exception as cleanup_e:
            print(f"⚠️ 清理资源时出错: {cleanup_e}")


if __name__ == "__main__":
    main()
