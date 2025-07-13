#!/usr/bin/env python3
"""
Example usage of OpenGauss as vector database with Letta.
This script demonstrates how to configure and use OpenGauss for vector storage.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv  # 1. 导入 load_dotenv

# 2. 精准定位并加载 .env 文件
# __file__ 是当前脚本的路径 (letta/examples/opengauss_example.py)
# .parent 是父目录 (letta/examples/)
# .parent.parent 是父目录的父目录 (letta/)
# 然后拼接 .env 文件名
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

# Add the letta directory to the Python path
letta_dir = Path(__file__).parent.parent
sys.path.insert(0, str(letta_dir))

from letta.schemas.embedding_config import OpenGaussConfig, EmbeddingConfig
from letta.services.passage_manager import PassageManager
from letta.schemas.passage import Passage
from letta.schemas.user import User

def main():
    """Example of using OpenGauss with Letta."""
    
    # Configure OpenGauss
    opengauss_config = OpenGaussConfig(
        host=os.getenv("OPENGAUSS_HOST", "localhost"),
        port=int(os.getenv("OPENGAUSS_PORT", "5432")),
        database=os.getenv("OPENGAUSS_DATABASE", "letta"),
        username=os.getenv("OPENGAUSS_USERNAME", "postgres"),
        password=os.getenv("OPENGAUSS_PASSWORD", "password"),
        table_name=os.getenv("OPENGAUSS_TABLE_NAME", "passage_embeddings"),
        ssl_mode=os.getenv("OPENGAUSS_SSL_MODE", "prefer"),
    )
    
    print(f"OpenGauss connection string: {opengauss_config.connection_string}")
    
    # Set up environment for OpenGauss initialization
    os.environ['LETTA_ENABLE_OPENGAUSS'] = 'true'
    os.environ['LETTA_PG_URI'] = opengauss_config.connection_string
    
    # Import and reload settings to apply the new environment variables
    import importlib
    from letta import settings as settings_module
    importlib.reload(settings_module)
    
    # Initialize database through DatabaseRegistry
    from letta.server.db import DatabaseRegistry
    db_registry = DatabaseRegistry()
    
    try:
        print("Initializing database...")
        db_registry.initialize_sync(force=True)
        print("✓ Database initialization completed")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        print("Please check your OpenGauss configuration and ensure the database server is running")
        return
    
    # Initialize PassageManager with OpenGauss configuration
    passage_manager = PassageManager(opengauss_config=opengauss_config)
    
    # Check if OpenGauss is properly configured
    if passage_manager.vector_store:
        print("✓ OpenGauss vector store initialized successfully")
        
        # Get statistics
        stats = passage_manager.vector_store.get_stats()
        print(f"Vector store stats: {stats}")
        
        # Example of creating a passage with embedding (this would typically be done by Letta)
        # Note: In real usage, embeddings would be generated automatically
        example_embedding = [0.1] * 1536  # Example embedding vector
        
        # Create a mock user (in real usage, this would come from the authentication system)
        mock_user = User(id="user_123", name="Test User")
        
        # Create a passage with embedding
        passage = Passage(
            id="passage_123",
            text="This is an example passage for testing OpenGauss integration.",
            embedding=example_embedding,
            agent_id="agent_123",
            organization_id="org_123"
        )
        
        try:
            # This would create the passage and sync it to OpenGauss
            created_passage = passage_manager.create_agent_passage(passage, mock_user)
            print(f"✓ Created passage: {created_passage.id}")
            
            # Search for similar passages
            similar_passages = passage_manager._search_similar_passages_in_vector_store(
                query_embedding=example_embedding,
                top_k=5,
                agent_id="agent_123"
            )
            print(f"✓ Found {len(similar_passages)} similar passages")
            
        except Exception as e:
            print(f"✗ Error creating passage: {e}")
            
    else:
        print("✗ Failed to initialize OpenGauss vector store")
        print("Please check your OpenGauss configuration and ensure the database is running")

if __name__ == "__main__":
    main()
