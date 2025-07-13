#!/usr/bin/env python3
"""
调试embedding模型调用情况
检查为什么embedding模型没有被调用
"""

import os
import sys
import time
import requests
import json
from pathlib import Path

# 添加 letta 模块路径
current_dir = Path(__file__).parent
letta_root = current_dir.parent
sys.path.insert(0, str(letta_root))

from letta_client import Letta


def check_embedding_service():
    """检查embedding服务是否运行"""
    print("🔍 检查embedding服务...")
    
    embedding_endpoints = [
        "http://127.0.0.1:8003/v1/models",
        "http://localhost:8003/v1/models",
        "http://127.0.0.1:11434/api/tags",  # Ollama
    ]
    
    for endpoint in embedding_endpoints:
        try:
            print(f"🔗 测试端点: {endpoint}")
            response = requests.get(endpoint, timeout=5)
            if response.status_code == 200:
                print(f"✅ 端点可用: {endpoint}")
                data = response.json()
                print(f"   响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")
                return endpoint
            else:
                print(f"❌ 端点返回: {response.status_code}")
        except Exception as e:
            print(f"❌ 端点不可用: {e}")
    
    print("❌ 没有找到可用的embedding服务")
    return None


def test_embedding_call():
    """直接测试embedding调用"""
    print("\n🧪 测试embedding调用...")
    
    embedding_url = "http://127.0.0.1:8003/v1/embeddings"
    test_text = "这是一个测试文本，用于验证embedding模型是否工作"
    
    try:
        response = requests.post(
            embedding_url,
            json={
                "model": "bge-m3",
                "input": [test_text]
            },
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            embedding = data['data'][0]['embedding']
            print(f"✅ Embedding调用成功!")
            print(f"   模型: bge-m3")
            print(f"   文本长度: {len(test_text)}")
            print(f"   向量维度: {len(embedding)}")
            print(f"   向量前5个值: {embedding[:5]}")
            return True
        else:
            print(f"❌ Embedding调用失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Embedding调用出错: {e}")
        return False


def check_letta_models():
    """检查Letta服务器的模型配置"""
    print("\n🔍 检查Letta模型配置...")
    
    try:
        client = Letta(base_url="http://localhost:8283")
        
        # 检查可用模型
        models = client.models.list()
        print(f"📋 可用模型数量: {len(models)}")
        
        embedding_models = []
        llm_models = []
        
        for model in models:
            print(f"   - {model.name}")
            if hasattr(model, 'model_type'):
                print(f"     类型: {model.model_type}")
                if 'embedding' in model.model_type.lower():
                    embedding_models.append(model)
                else:
                    llm_models.append(model)
            
            if hasattr(model, 'embedding_dim'):
                print(f"     向量维度: {model.embedding_dim}")
        
        print(f"\n📊 模型统计:")
        print(f"   LLM模型: {len(llm_models)}")
        print(f"   Embedding模型: {len(embedding_models)}")
        
        # 检查bge/bge-m3是否可用
        bge_available = any("bge" in model.name.lower() for model in models)
        print(f"   BGE模型可用: {bge_available}")
        
        return models
        
    except Exception as e:
        print(f"❌ 检查Letta模型失败: {e}")
        return []


def debug_source_creation():
    """调试文档源创建过程"""
    print("\n🔍 调试文档源创建...")
    
    try:
        client = Letta(base_url="http://localhost:8283")
        
        # 创建文档源并仔细检查配置
        source_name = f"debug_embedding_{int(time.time())}"
        
        print(f"📝 创建文档源: {source_name}")
        source = client.sources.create(
            name=source_name,
            embedding="bge/bge-m3",
        )
        
        print(f"✅ 文档源创建成功!")
        print(f"   ID: {source.id}")
        print(f"   名称: {source.name}")
        
        # 检查embedding配置
        if hasattr(source, 'embedding_config'):
            print(f"   Embedding配置: {source.embedding_config}")
        else:
            print("   ⚠️ 没有embedding_config属性")
        
        # 打印所有可用属性
        print(f"   所有属性: {dir(source)}")
        
        return source
        
    except Exception as e:
        print(f"❌ 创建文档源失败: {e}")
        return None


def debug_file_upload(source):
    """调试文件上传和处理过程"""
    print("\n🔍 调试文件上传...")
    
    if not source:
        print("❌ 没有文档源，跳过文件上传")
        return None
    
    pdf_path = "./jr.pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ PDF文件不存在: {pdf_path}")
        return None
    
    try:
        client = Letta(base_url="http://localhost:8283")
        
        print(f"📤 上传文件: {pdf_path}")
        job = client.sources.files.upload(
            source_id=source.id,
            file=pdf_path,
        )
        
        print(f"🔄 任务创建成功: {job.id}")
        
        # 详细监控任务状态
        max_attempts = 20
        attempt = 0
        
        while attempt < max_attempts:
            try:
                job_status = client.jobs.get(job_id=job.id)
                print(f"⏳ [{attempt+1}/{max_attempts}] 状态: {job_status.status}")
                
                # 打印所有可用的任务信息
                print(f"   任务属性: {dir(job_status)}")
                
                if hasattr(job_status, 'metadata') and job_status.metadata:
                    print(f"   元数据: {job_status.metadata}")
                
                if hasattr(job_status, 'output') and job_status.output:
                    print(f"   输出: {job_status.output}")
                
                if hasattr(job_status, 'error') and job_status.error:
                    print(f"   错误: {job_status.error}")
                
                if job_status.status == "completed":
                    print("✅ 任务完成!")
                    return job_status
                elif job_status.status == "failed":
                    print("❌ 任务失败!")
                    return job_status
                
                time.sleep(3)
                attempt += 1
                
            except Exception as e:
                print(f"⚠️ 检查任务状态出错: {e}")
                time.sleep(3)
                attempt += 1
        
        print("⚠️ 任务监控超时")
        return None
        
    except Exception as e:
        print(f"❌ 文件上传失败: {e}")
        return None


def check_passages_and_embeddings(source):
    """检查是否生成了文档片段和向量"""
    print("\n🔍 检查文档片段和向量...")
    
    if not source:
        print("❌ 没有文档源")
        return
    
    try:
        client = Letta(base_url="http://localhost:8283")
        
        # 获取文档片段
        passages = client.sources.passages.list(source_id=source.id)
        print(f"📄 文档片段数量: {len(passages)}")
        
        if len(passages) == 0:
            print("❌ 没有找到文档片段，embedding可能失败")
            return
        
        # 显示前几个片段
        for i, passage in enumerate(passages[:3]):
            print(f"   片段 {i+1}:")
            print(f"     ID: {passage.id}")
            print(f"     长度: {len(passage.text)} 字符")
            print(f"     预览: {passage.text[:100]}...")
            
            # 检查是否有embedding相关属性
            print(f"     属性: {dir(passage)}")
        
        # 测试向量搜索
        print(f"\n🔍 测试向量搜索...")
        try:
            search_results = client.sources.passages.search(
                source_id=source.id,
                query="测试搜索",
                limit=2
            )
            
            print(f"✅ 搜索成功，返回 {len(search_results)} 个结果")
            for result in search_results:
                score = getattr(result, 'score', 'N/A')
                print(f"   相似度: {score}")
                print(f"   文本: {result.text[:100]}...")
            
            if len(search_results) > 0:
                print("✅ 向量搜索工作正常，说明embedding被正确调用了")
            else:
                print("⚠️ 搜索返回空结果")
                
        except Exception as e:
            print(f"❌ 向量搜索失败: {e}")
        
    except Exception as e:
        print(f"❌ 检查文档片段失败: {e}")


def full_debug():
    """完整的调试流程"""
    print("🚀 开始完整的embedding调试...")
    print("=" * 60)
    
    # 1. 检查embedding服务
    embedding_service = check_embedding_service()
    
    # 2. 测试embedding调用
    embedding_works = test_embedding_call()
    
    # 3. 检查Letta模型
    models = check_letta_models()
    
    # 4. 创建文档源
    source = debug_source_creation()
    
    # 5. 上传文件
    job_result = debug_file_upload(source)
    
    # 6. 检查结果
    check_passages_and_embeddings(source)
    
    print("\n" + "=" * 60)
    print("🏁 调试完成!")
    
    # 总结
    print(f"\n📊 调试总结:")
    print(f"   Embedding服务: {'✅' if embedding_service else '❌'}")
    print(f"   Embedding调用: {'✅' if embedding_works else '❌'}")
    print(f"   Letta模型数量: {len(models)}")
    print(f"   文档源创建: {'✅' if source else '❌'}")
    print(f"   文件上传: {'✅' if job_result else '❌'}")
    
    return source


if __name__ == "__main__":
    full_debug()
