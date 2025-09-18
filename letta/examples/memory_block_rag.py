#!/usr/bin/env python3
"""
基于Memory Blocks的Letta RAG系统
将PDF内容直接保存到memory_blocks中，不使用向量检索
"""

import os
import sys
import time
from pathlib import Path
from typing import List, Dict

# 添加letta模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta, CreateBlock, MessageCreate


class MemoryBlockRAG:
    """基于Memory Blocks的RAG系统 - 将PDF内容直接存储到memory_blocks中"""
    
    def __init__(self, letta_url="http://localhost:8283"):
        """初始化RAG系统"""
        print("🚀 初始化Memory Block RAG系统")
        self.client = Letta(base_url=letta_url)
        self.text_chunks = []
        self.agent = None
        
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
    
    def chunk_text_for_memory(self, text: str, chunk_size: int = 1000) -> List[Dict]:
        """将文本分割成适合存储在memory_blocks中的块"""
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
                                'label': f"document_chunk_{chunk_id}",
                                'type': 'document_content'
                            })
                            chunk_id += 1
                        
                        current_chunk = paragraph + '\n\n'
                
                # 添加最后一个块
                if current_chunk.strip():
                    chunks.append({
                        'id': chunk_id,
                        'content': current_chunk.strip(),
                        'label': f"document_chunk_{chunk_id}",
                        'type': 'document_content'
                    })
                    chunk_id += 1
            else:
                # 页面内容适中，直接作为一个块
                chunks.append({
                    'id': chunk_id,
                    'content': page_content.strip(),
                    'label': f"document_chunk_{chunk_id}",
                    'type': 'document_content'
                })
                chunk_id += 1
        
        self.text_chunks = chunks
        print(f"✅ 分块完成: {len(chunks)}个块, 平均{sum(len(c['content']) for c in chunks)/max(1, len(chunks)):.1f}字符")
        return chunks
    
    def create_agent_with_memory_blocks(self, document_name: str) -> bool:
        """创建包含所有PDF内容的智能体"""
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
- 每个块都包含文档的一部分内容

请注意:
1. 仔细阅读用户问题，在你的记忆块中查找相关信息
2. 基于文档内容给出准确、详细的回答
3. 如果问题涉及具体数据、日期、条款等，请引用具体的文档内容
4. 如果文档中没有相关信息，请明确说明
5. 保持回答的专业性和准确性
6. 使用中文回答，内容纯文字
7. 回答不要使用html标签

你的记忆中已经加载了完整的文档内容，可以直接基于这些内容回答问题。"""

            memory_blocks.append(CreateBlock(
                value=system_instruction,
                label="system_instruction",
            ))
            
            # 添加所有文档块到memory_blocks
            for chunk in self.text_chunks:
                memory_blocks.append(CreateBlock(
                    value=chunk['content'],
                    label=chunk['label'],
                ))
            
            print(f"📝 准备创建智能体，包含 {len(memory_blocks)} 个memory blocks")
            
            # 创建智能体（需要指定embedding配置，即使不用于向量检索）
            self.agent = self.client.agents.create(
                memory_blocks=memory_blocks,
                model="openai/qwen3",        # Qwen3模型
                embedding="bge/bge-m3",      # 虽然不用于检索，但系统要求指定
            )
            
            print(f"✅ 智能体创建成功: {self.agent.name}")
            print(f"   Memory Blocks数量: {len(memory_blocks)}")
            print(f"   文档内容直接存储在智能体记忆中")
            
            return True
            
        except Exception as e:
            print(f"❌ 创建智能体失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def ask_question(self, question: str) -> str:
        """直接基于memory blocks中的内容回答问题"""
        print(f"❓ 问题: {question}")
        
        if not self.agent:
            return "❌ 智能体未初始化，请先构建RAG系统"
        
        try:
            # 构建提示，让智能体知道要基于记忆中的文档内容回答
            enhanced_question = f"""请基于你记忆中的文档内容回答以下问题：

问题: {question}

请仔细检查你的记忆块中的文档内容，给出准确详细的回答。如果需要引用具体内容，请指出是来自文档的哪个部分。"""

            response = self.client.agents.messages.create(
                agent_id=self.agent.id,
                messages=[MessageCreate(role="user", content=enhanced_question)],
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
            import traceback
            traceback.print_exc()
            return error_msg
    
    def build_memory_rag_system(self, file_path: str, chunk_size: int = 1000) -> bool:
        """构建基于Memory Blocks的完整RAG系统"""
        print("🚀 开始构建Memory Block RAG系统")
        print("=" * 60)
        
        try:
            document_name = Path(file_path).name
            
            # 步骤1: 提取文本
            text = self.extract_text_from_pdf(file_path)
            if not text:
                return False
            
            # 步骤2: 文本分块（适合memory blocks）
            chunks = self.chunk_text_for_memory(text, chunk_size=chunk_size)
            if not chunks:
                return False
            
            # 步骤3: 创建带有memory blocks的智能体
            success = self.create_agent_with_memory_blocks(document_name)
            if not success:
                return False
            
            print("\n" + "=" * 60)
            print("✅ Memory Block RAG系统构建完成!")
            print(f"   文档: {document_name}")
            print(f"   Memory Blocks: {len(self.text_chunks) + 1}个 (包含系统指令)")
            print(f"   文档块: {len(self.text_chunks)}个")
            print(f"   块大小: 平均{sum(len(c['content']) for c in chunks)/len(chunks):.0f}字符")
            print(f"   智能体: {self.agent.name}")
            print(f"   存储方式: 直接存储在智能体记忆中，无需向量检索")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG系统构建失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def show_memory_blocks_info(self):
        """显示memory blocks信息"""
        if not self.agent:
            print("❌ 智能体未初始化")
            return
            
        print("\n📊 Memory Blocks 信息:")
        print("=" * 50)
        
        try:
            # 获取智能体的memory blocks
            agent_info = self.client.agents.get(agent_id=self.agent.id)
            
            if hasattr(agent_info, 'memory_blocks'):
                for i, block in enumerate(agent_info.memory_blocks):
                    print(f"Block {i+1}: {block.label}")
                    content_preview = block.value[:100] + "..." if len(block.value) > 100 else block.value
                    print(f"  内容预览: {content_preview}")
                    print(f"  长度: {len(block.value)}字符")
                    print()
            else:
                print("无法获取memory blocks信息")
                
        except Exception as e:
            print(f"获取memory blocks信息失败: {e}")
    
    def interactive_demo(self):
        """交互式演示"""
        print("\n💬 进入Memory Block RAG交互式问答")
        print("=" * 50)
        print("输入问题，输入'quit'退出，输入'info'查看memory blocks信息")
        
        while True:
            try:
                question = input("\n❓ 您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出']:
                    print("👋 再见!")
                    break
                
                if question.lower() in ['info', '信息']:
                    self.show_memory_blocks_info()
                    continue
                
                if not question:
                    continue
                
                answer = self.ask_question(question)
                
            except KeyboardInterrupt:
                print("\n👋 再见!")
                break
            except Exception as e:
                print(f"❌ 出错了: {e}")


def main():
    """主函数 - Memory Block RAG系统示例"""
    # 从命令行参数获取PDF文件路径
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
    else:
        # 默认文件路径
        pdf_file = "jr.pdf"
    
    chunk_size = 1000
    
    print("📚 基于Memory Blocks的Letta RAG系统")
    print("=" * 60)
    print(f"文档路径: {pdf_file}")
    print(f"块大小: {chunk_size}字符")
    print(f"存储方式: 直接存储到智能体Memory Blocks")
    print("=" * 60)
    
    # 检查文件
    if not os.path.exists(pdf_file):
        print(f"❌ 找不到文件: {pdf_file}")
        print(f"💡 使用方法: python {sys.argv[0]} /path/to/your/document.pdf")
        return
    
    # 创建RAG系统
    rag = MemoryBlockRAG()
    
    # 构建系统
    success = rag.build_memory_rag_system(pdf_file, chunk_size=chunk_size)
    
    if success:
        # 显示memory blocks信息
        rag.show_memory_blocks_info()
        
        # 快速测试
        print("\n🧪 快速测试:")
        test_questions = [
            "这个文档的主要内容是什么？",
            "文档中提到了哪些重要信息？",
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
        print("2. 文件是否存在且可读")
        print("3. pypdf是否已安装 (pip install pypdf)")


if __name__ == "__main__":
    main()