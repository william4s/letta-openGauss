#!/usr/bin/env python3
"""
测试 BGE 嵌入器和简单文本解析器的脚本
"""

import asyncio
import tempfile
import os
from pathlib import Path

from letta.services.file_processor.embedder.bge_embedder import BGEEmbedder
from letta.services.file_processor.parser.simple_text_parser import SimpleTextParser
from letta.schemas.embedding_config import EmbeddingConfig
from letta.schemas.user import User
from letta.settings import model_settings


async def test_simple_text_parser():
    """测试简单文本解析器"""
    print("Testing SimpleTextParser...")
    
    parser = SimpleTextParser()
    test_content = "Hello, this is a test document.\nIt has multiple lines.\nAnd some Chinese text: 你好世界！"
    content_bytes = test_content.encode('utf-8')
    
    try:
        response = await parser.extract_text(content_bytes, "text/plain")
        print(f"✅ SimpleTextParser success!")
        print(f"   Model: {response.model}")
        print(f"   Pages: {len(response.pages)}")
        print(f"   Text length: {len(response.pages[0].markdown)}")
        print(f"   First 100 chars: {response.pages[0].markdown[:100]}...")
        return True
    except Exception as e:
        print(f"❌ SimpleTextParser failed: {e}")
        return False


async def test_bge_embedder():
    """测试 BGE 嵌入器"""
    print("\nTesting BGEEmbedder...")
    
    # 创建 BGE 配置
    embedding_config = EmbeddingConfig(
        embedding_model="bge-m3",
        embedding_endpoint_type="openai",
        embedding_endpoint=model_settings.bge_api_base,
        embedding_dim=1024,
        embedding_chunk_size=300,
        batch_size=2,
    )
    
    embedder = BGEEmbedder(embedding_config=embedding_config)
    
    # 创建一个虚拟用户
    user = User(
        id="test-user",
        name="Test User",
        organization_id="test-org"
    )
    
    test_chunks = [
        "This is the first test chunk for embedding.",
        "This is the second test chunk with different content.",
        "这是第三个测试块，包含中文内容。"
    ]
    
    try:
        passages = await embedder.generate_embedded_passages(
            file_id="test-file-id",
            source_id="test-source-id",
            chunks=test_chunks,
            actor=user
        )
        
        print(f"✅ BGEEmbedder success!")
        print(f"   Generated {len(passages)} passages")
        print(f"   First embedding dimension: {len(passages[0].embedding)}")
        print(f"   First passage text: {passages[0].text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ BGEEmbedder failed: {e}")
        print(f"   Make sure BGE server is running at {model_settings.bge_api_base}")
        return False


async def test_integration():
    """测试集成：解析 + 嵌入"""
    print("\nTesting Integration (Parser + Embedder)...")
    
    # 1. 使用简单解析器解析文本
    parser = SimpleTextParser()
    test_content = """# Test Document

This is a test document for integration testing.

## Section 1
This section contains some basic text.

## Section 2  
This section contains more text with different content.
It has multiple paragraphs.

The end.
"""
    content_bytes = test_content.encode('utf-8')
    
    try:
        # 解析文本
        parse_response = await parser.extract_text(content_bytes, "text/markdown")
        raw_text = parse_response.pages[0].markdown
        
        # 简单分块（按段落）
        chunks = [chunk.strip() for chunk in raw_text.split('\n\n') if chunk.strip()]
        
        print(f"   Parsed text into {len(chunks)} chunks")
        
        # 创建 BGE 配置和嵌入器
        embedding_config = EmbeddingConfig(
            embedding_model="bge-m3",
            embedding_endpoint_type="openai", 
            embedding_endpoint=model_settings.bge_api_base,
            embedding_dim=1024,
            embedding_chunk_size=300,
            batch_size=2,
        )
        
        embedder = BGEEmbedder(embedding_config=embedding_config)
        
        # 创建虚拟用户
        user = User(
            id="test-user",
            name="Test User", 
            organization_id="test-org"
        )
        
        # 生成嵌入
        passages = await embedder.generate_embedded_passages(
            file_id="integration-test-file",
            source_id="integration-test-source",
            chunks=chunks,
            actor=user
        )
        
        print(f"✅ Integration test success!")
        print(f"   Generated {len(passages)} embedded passages")
        for i, passage in enumerate(passages):
            print(f"   Passage {i+1}: {len(passage.embedding)} dims, text: {passage.text[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


async def main():
    """运行所有测试"""
    print("🚀 Testing BGE integration for file upload...")
    print(f"BGE API Base: {model_settings.bge_api_base}")
    print(f"BGE API Key: {'✅ Set' if model_settings.bge_api_key else '❌ Not set'}")
    print("=" * 60)
    
    results = []
    
    # 测试简单文本解析器
    results.append(await test_simple_text_parser())
    
    # 测试 BGE 嵌入器  
    results.append(await test_bge_embedder())
    
    # 测试集成
    results.append(await test_integration())
    
    print("\n" + "=" * 60)
    print("📊 Test Results:")
    test_names = ["SimpleTextParser", "BGEEmbedder", "Integration"]
    
    for name, result in zip(test_names, results):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {name}: {status}")
    
    all_passed = all(results)
    print(f"\n🎯 Overall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    if all_passed:
        print("\n🎉 Your BGE integration is working correctly!")
        print("You can now upload files and they will use BGE for embeddings.")
    else:
        print("\n🔧 Please check your BGE server configuration and try again.")


if __name__ == "__main__":
    asyncio.run(main())
