#!/usr/bin/env python3
"""
Test script to verify BGE provider functionality
"""
import os
import sys
sys.path.insert(0, '/home/shiwc24/ospp/letta-openGauss')

from letta.schemas.providers import BGEProvider
from letta.schemas.enums import ProviderType

def test_bge_provider():
    # Test BGE provider creation
    provider = BGEProvider(
        name="bge",
        api_key="test-key",
        base_url="http://127.0.0.1:8003/v1"
    )
    
    print(f"Provider name: {provider.name}")
    print(f"Provider type: {provider.provider_type}")
    print(f"Base URL: {provider.base_url}")
    
    # Test embedding models listing
    embedding_models = provider.list_embedding_models()
    print(f"\nAvailable embedding models: {len(embedding_models)}")
    
    for model in embedding_models:
        print(f"  - {model.embedding_model} (handle: {model.handle})")
        print(f"    Dim: {model.embedding_dim}, Chunk size: {model.embedding_chunk_size}")
    
    # Test LLM models (should be empty for BGE)
    llm_models = provider.list_llm_models()
    print(f"\nLLM models: {len(llm_models)}")
    
    # Test handle generation
    handle = provider.get_handle("bge-m3", is_embedding=True)
    print(f"\nGenerated handle for bge-m3: {handle}")
    
    print("\n✅ BGE Provider test passed!")

if __name__ == "__main__":
    test_bge_provider()
