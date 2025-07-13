#!/usr/bin/env python3
"""
PDF转文本处理器
将PDF文件转换为文本，绕过Mistral API要求
"""

import os
import sys
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

def extract_pdf_text():
    """提取PDF文本内容"""
    pdf_path = "./jr.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF文件不存在: {pdf_path}")
        return None
    
    print(f"🔄 提取PDF文本: {pdf_path}")
    
    try:
        # 尝试使用PyMuPDF (fitz)
        import fitz
        
        doc = fitz.open(pdf_path)
        text_content = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            text_content += f"\n--- 第 {page_num + 1} 页 ---\n"
            text_content += text
        
        doc.close()
        
        print(f"✅ PDF提取成功")
        print(f"   页数: {len(doc)}")
        print(f"   文本长度: {len(text_content)} 字符")
        print(f"   文本预览: {text_content[:200]}...")
        
        return text_content
        
    except ImportError:
        print("⚠️ PyMuPDF (fitz) 未安装，尝试其他方法...")
        
        try:
            # 尝试使用pypdf
            import pypdf
            
            with open(pdf_path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                text_content = ""
                
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    text_content += f"\n--- 第 {page_num + 1} 页 ---\n"
                    text_content += text
                
                print(f"✅ PDF提取成功 (使用pypdf)")
                print(f"   页数: {len(reader.pages)}")
                print(f"   文本长度: {len(text_content)} 字符")
                print(f"   文本预览: {text_content[:200]}...")
                
                return text_content
                
        except ImportError:
            print("❌ 没有可用的PDF处理库")
            print("请安装: pip install PyMuPDF 或 pip install pypdf")
            return None
    
    except Exception as e:
        print(f"❌ PDF提取失败: {e}")
        return None


def save_text_file(text_content):
    """保存文本到文件"""
    if not text_content:
        return None
    
    text_path = "./jr.txt"
    
    try:
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text_content)
        
        print(f"✅ 文本文件已保存: {text_path}")
        return text_path
        
    except Exception as e:
        print(f"❌ 保存文本文件失败: {e}")
        return None


def upload_text_file(text_path):
    """上传文本文件到Letta"""
    if not text_path or not os.path.exists(text_path):
        print("❌ 文本文件不存在")
        return None
    
    try:
        from letta_client import Letta
        import time
        
        client = Letta(base_url="http://localhost:8283")
        
        # 创建文档源
        source_name = f"jr_text_source_{int(time.time())}"
        source = client.sources.create(
            name=source_name,
            embedding="bge/bge-m3",
        )
        
        print(f"✅ 文档源创建成功: {source.id}")
        print(f"   Embedding配置: {source.embedding_config}")
        
        # 上传文本文件
        print(f"📤 上传文本文件...")
        job = client.sources.files.upload(
            source_id=source.id,
            file=text_path,
        )
        
        print(f"🔄 处理任务: {job.id}")
        
        # 监控处理过程
        max_attempts = 30
        attempt = 0
        
        while attempt < max_attempts:
            try:
                job_status = client.jobs.get(job_id=job.id)
                print(f"⏳ [{attempt+1}/{max_attempts}] 状态: {job_status.status}")
                
                if job_status.status == "completed":
                    print("✅ 文本文件处理完成!")
                    
                    # 检查结果
                    passages = client.sources.passages.list(source_id=source.id)
                    print(f"📄 生成文档片段: {len(passages)} 个")
                    
                    if len(passages) > 0:
                        print("✅ 向量化成功!")
                        
                        # 测试搜索
                        search_results = client.sources.passages.search(
                            source_id=source.id,
                            query="文档内容",
                            limit=3
                        )
                        print(f"🔍 测试搜索返回: {len(search_results)} 个结果")
                        
                        for i, result in enumerate(search_results):
                            score = getattr(result, 'score', 'N/A')
                            print(f"   结果 {i+1} (相似度: {score}): {result.text[:100]}...")
                    
                    return source
                    
                elif job_status.status == "failed":
                    print(f"❌ 处理失败: {job_status}")
                    return None
                
                time.sleep(2)
                attempt += 1
                
            except Exception as e:
                print(f"⚠️ 检查状态出错: {e}")
                time.sleep(2)
                attempt += 1
        
        print("⚠️ 处理超时")
        return source
        
    except Exception as e:
        print(f"❌ 上传文本文件失败: {e}")
        return None


def pdf_to_rag_pipeline():
    """完整的PDF转RAG流程"""
    print("🚀 PDF转RAG流程开始...")
    print("=" * 50)
    
    # 1. 提取PDF文本
    text_content = extract_pdf_text()
    if not text_content:
        return None
    
    # 2. 保存为文本文件
    text_path = save_text_file(text_content)
    if not text_path:
        return None
    
    # 3. 上传并向量化
    source = upload_text_file(text_path)
    
    print("\n" + "=" * 50)
    if source:
        print("✅ PDF转RAG流程完成!")
        print(f"   文档源ID: {source.id}")
        print(f"   可以用于RAG问答了")
    else:
        print("❌ PDF转RAG流程失败")
    
    return source


if __name__ == "__main__":
    pdf_to_rag_pipeline()
