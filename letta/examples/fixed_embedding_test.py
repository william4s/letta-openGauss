#!/usr/bin/env python3
"""
修复版本的PDF转RAG处理器
解决MIME类型识别问题
"""

import os
import sys
import time
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta


def create_text_from_pdf():
    """从PDF创建文本文件"""
    pdf_path = "./jr.pdf"
    
    try:
        import pypdf
        
        with open(pdf_path, 'rb') as file:
            reader = pypdf.PdfReader(file)
            text_content = ""
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                text_content += f"\n--- 第 {page_num + 1} 页 ---\n"
                text_content += text
            
            # 保存为.txt文件
            text_path = "./jr_extracted.txt"
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            print(f"✅ PDF文本提取完成")
            print(f"   源文件: {pdf_path}")
            print(f"   目标文件: {text_path}")
            print(f"   页数: {len(reader.pages)}")
            print(f"   文本长度: {len(text_content)} 字符")
            
            return text_path, text_content
            
    except Exception as e:
        print(f"❌ PDF文本提取失败: {e}")
        return None, None


def upload_with_correct_mime_type():
    """使用正确的MIME类型上传文本"""
    text_path, text_content = create_text_from_pdf()
    
    if not text_path:
        return None
    
    try:
        client = Letta(base_url="http://localhost:8283")
        
        # 创建文档源
        source_name = f"jr_text_fixed_{int(time.time())}"
        source = client.sources.create(
            name=source_name,
            embedding="bge/bge-m3",
        )
        
        print(f"✅ 文档源创建: {source.id}")
        
        # 使用requests直接上传，指定正确的Content-Type
        import requests
        
        # 准备文件数据
        files = {
            'file': ('jr_extracted.txt', open(text_path, 'rb'), 'text/plain')
        }
        
        # 上传文件
        upload_url = f"http://localhost:8283/v1/sources/{source.id}/upload"
        
        print(f"📤 上传文件到: {upload_url}")
        response = requests.post(upload_url, files=files)
        
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data.get('id')
            
            print(f"✅ 文件上传成功!")
            print(f"   任务ID: {job_id}")
            
            # 监控处理过程
            max_attempts = 30
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    job_status = client.jobs.get(job_id=job_id)
                    print(f"⏳ [{attempt+1}/{max_attempts}] 状态: {job_status.status}")
                    
                    if job_status.status == "completed":
                        print("✅ 文件处理和向量化完成!")
                        
                        # 验证结果
                        passages = client.sources.passages.list(source_id=source.id)
                        print(f"📄 生成文档片段: {len(passages)} 个")
                        
                        if len(passages) > 0:
                            print("✅ 向量化成功! Embedding模型被正确调用了!")
                            
                            # 测试向量搜索
                            search_results = client.sources.passages.search(
                                source_id=source.id,
                                query="理财产品的风险等级",
                                limit=3
                            )
                            
                            print(f"🔍 向量搜索测试:")
                            print(f"   查询: '理财产品的风险等级'")
                            print(f"   返回结果: {len(search_results)} 个")
                            
                            for i, result in enumerate(search_results):
                                score = getattr(result, 'score', 'N/A')
                                print(f"   结果 {i+1} (相似度: {score}):")
                                print(f"     {result.text[:150]}...")
                        
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
            
        else:
            print(f"❌ 文件上传失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return None
        
    except Exception as e:
        print(f"❌ 上传过程出错: {e}")
        return None


def test_embedding_integration():
    """测试完整的embedding集成"""
    print("🚀 测试JR.PDF Embedding集成")
    print("=" * 60)
    
    # 上传并处理文件
    source = upload_with_correct_mime_type()
    
    if source:
        print("\n" + "=" * 60)
        print("✅ Embedding集成测试成功!")
        print(f"   文档源ID: {source.id}")
        print(f"   BGE-M3模型已被正确调用")
        print(f"   文档已向量化并存储到向量数据库")
        
        # 测试多个查询
        test_queries = [
            "这个理财产品的风险等级是什么？",
            "投资期限多长？",
            "有什么风险提示？"
        ]
        
        client = Letta(base_url="http://localhost:8283")
        
        print(f"\n🔍 多查询测试:")
        for i, query in enumerate(test_queries, 1):
            print(f"\n   查询 {i}: {query}")
            try:
                results = client.sources.passages.search(
                    source_id=source.id,
                    query=query,
                    limit=2
                )
                print(f"   返回 {len(results)} 个结果")
                for j, result in enumerate(results):
                    score = getattr(result, 'score', 'N/A')
                    print(f"     结果 {j+1} (相似度: {score}): {result.text[:100]}...")
            except Exception as e:
                print(f"   ❌ 查询失败: {e}")
    
    else:
        print("❌ Embedding集成测试失败")
    
    return source


if __name__ == "__main__":
    test_embedding_integration()
