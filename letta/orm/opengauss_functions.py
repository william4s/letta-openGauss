"""
OpenGauss vector storage implementation for Letta.
Provides vector storage and similarity search capabilities using OpenGauss database.
"""

import psycopg2
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
import json
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class OpenGaussVectorStore:
    """OpenGauss vector storage implementation."""
    
    def __init__(self, connection_string: str, table_name: str = "passage_embeddings"):
        """
        Initialize OpenGauss vector store.
        
        Args:
            connection_string: PostgreSQL connection string
            table_name: Name of the table to store embeddings
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self.conn = None
        self.connect()
        self.setup_tables()
    
    def connect(self):
        """Establish connection to OpenGauss database."""
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.conn.autocommit = True
            logger.info("Connected to OpenGauss database")
        except Exception as e:
            logger.error(f"Failed to connect to OpenGauss: {e}")
            raise ConnectionError(f"Failed to connect to OpenGauss: {e}")
    
    def setup_tables(self):
        """Set up necessary tables and indexes for vector storage."""
        with self.get_cursor() as cursor:
            # Create the embeddings table
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id SERIAL PRIMARY KEY,
                    passage_id VARCHAR(255) UNIQUE NOT NULL,
                    embedding FLOAT[] NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Create indexes for better performance
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_passage_id 
                ON {self.table_name}(passage_id);
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_embedding_dim 
                ON {self.table_name}(embedding_dim);
            """)
            
            # Create trigger for updated_at
            cursor.execute(f"""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """)
            
            cursor.execute(f"""
                DROP TRIGGER IF EXISTS update_{self.table_name}_updated_at ON {self.table_name};
                CREATE TRIGGER update_{self.table_name}_updated_at
                    BEFORE UPDATE ON {self.table_name}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column();
            """)
            
            logger.info(f"Vector storage tables set up successfully")
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursors."""
        cursor = self.conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
    
    def store_embedding(self, passage_id: str, embedding: List[float], metadata: Optional[Dict] = None):
        """
        Store an embedding vector in the database.
        
        Args:
            passage_id: Unique identifier for the passage
            embedding: The embedding vector
            metadata: Optional metadata associated with the embedding
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    INSERT INTO {self.table_name} (passage_id, embedding, embedding_dim, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (passage_id) 
                    DO UPDATE SET 
                        embedding = EXCLUDED.embedding,
                        embedding_dim = EXCLUDED.embedding_dim,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP;
                """, (passage_id, embedding, len(embedding), json.dumps(metadata) if metadata else None))
                
                logger.debug(f"Stored embedding for passage {passage_id}")
        except Exception as e:
            logger.error(f"Failed to store embedding for passage {passage_id}: {e}")
            raise
    
    def get_embedding(self, passage_id: str) -> Optional[Tuple[List[float], Optional[Dict]]]:
        """
        Retrieve an embedding by passage ID.
        
        Args:
            passage_id: The passage identifier
            
        Returns:
            Tuple of (embedding, metadata) or None if not found
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT embedding, metadata FROM {self.table_name} 
                    WHERE passage_id = %s
                """, (passage_id,))
                
                result = cursor.fetchone()
                if result:
                    embedding, metadata = result
                    metadata_dict = json.loads(metadata) if metadata else None
                    return embedding, metadata_dict
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve embedding for passage {passage_id}: {e}")
            raise
    
    def cosine_similarity_sql(self, embedding1: str, embedding2: str) -> str:
        """
        Generate SQL expression for cosine similarity calculation.
        
        Args:
            embedding1: First embedding column/expression
            embedding2: Second embedding column/expression
            
        Returns:
            SQL expression for cosine similarity
        """
        return f"""
        (
            -- Dot product
            (SELECT SUM(a.val * b.val)
             FROM unnest({embedding1}) WITH ORDINALITY a(val, idx)
             JOIN unnest({embedding2}) WITH ORDINALITY b(val, idx) ON a.idx = b.idx)
        ) / (
            -- Magnitude of first vector
            sqrt((SELECT SUM(val * val) FROM unnest({embedding1}) AS val)) *
            -- Magnitude of second vector  
            sqrt((SELECT SUM(val * val) FROM unnest({embedding2}) AS val))
        )
        """
    
    def search_similar_passages(
        self, 
        query_embedding: List[float], 
        top_k: int = 10,
        min_similarity: float = 0.0,
        embedding_dim: Optional[int] = None
    ) -> List[Tuple[str, float]]:
        """
        Search for similar passages using cosine similarity.
        
        Args:
            query_embedding: The query embedding vector
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold
            embedding_dim: Filter by embedding dimension
            
        Returns:
            List of (passage_id, similarity_score) tuples
        """
        try:
            with self.get_cursor() as cursor:
                # Build the WHERE clause
                where_conditions = []
                params = [query_embedding, query_embedding]
                
                if embedding_dim:
                    where_conditions.append("embedding_dim = %s")
                    params.append(embedding_dim)
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Build the similarity calculation
                similarity_expr = self.cosine_similarity_sql("embedding", "%s::float[]")
                
                query = f"""
                    SELECT passage_id, {similarity_expr} as similarity
                    FROM {self.table_name}
                    {where_clause}
                    HAVING {similarity_expr} >= %s
                    ORDER BY similarity DESC
                    LIMIT %s;
                """
                
                params.extend([query_embedding, min_similarity, top_k])
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                logger.debug(f"Found {len(results)} similar passages")
                return results
                
        except Exception as e:
            logger.error(f"Failed to search similar passages: {e}")
            raise
    
    def delete_embedding(self, passage_id: str) -> bool:
        """
        Delete an embedding by passage ID.
        
        Args:
            passage_id: The passage identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    DELETE FROM {self.table_name} WHERE passage_id = %s
                """, (passage_id,))
                
                deleted = cursor.rowcount > 0
                if deleted:
                    logger.debug(f"Deleted embedding for passage {passage_id}")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete embedding for passage {passage_id}: {e}")
            raise
    
    def batch_store_embeddings(self, embeddings_data: List[Tuple[str, List[float], Optional[Dict]]]):
        """
        Store multiple embeddings in a batch operation.
        
        Args:
            embeddings_data: List of (passage_id, embedding, metadata) tuples
        """
        try:
            with self.get_cursor() as cursor:
                # Use execute_batch for better performance
                from psycopg2.extras import execute_batch
                
                execute_batch(cursor, f"""
                    INSERT INTO {self.table_name} (passage_id, embedding, embedding_dim, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (passage_id) 
                    DO UPDATE SET 
                        embedding = EXCLUDED.embedding,
                        embedding_dim = EXCLUDED.embedding_dim,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP;
                """, [
                    (passage_id, embedding, len(embedding), json.dumps(metadata) if metadata else None)
                    for passage_id, embedding, metadata in embeddings_data
                ])
                
                logger.info(f"Batch stored {len(embeddings_data)} embeddings")
                
        except Exception as e:
            logger.error(f"Failed to batch store embeddings: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(f"""
                    SELECT 
                        COUNT(*) as total_embeddings,
                        COUNT(DISTINCT embedding_dim) as distinct_dimensions,
                        MIN(embedding_dim) as min_dimension,
                        MAX(embedding_dim) as max_dimension,
                        AVG(embedding_dim) as avg_dimension
                    FROM {self.table_name};
                """)
                
                result = cursor.fetchone()
                return {
                    "total_embeddings": result[0],
                    "distinct_dimensions": result[1],
                    "min_dimension": result[2],
                    "max_dimension": result[3],
                    "avg_dimension": float(result[4]) if result[4] else 0.0
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            raise
    
    def clear_all(self):
        """Clear all embeddings from the store."""
        try:
            with self.get_cursor() as cursor:
                cursor.execute(f"DELETE FROM {self.table_name}")
                logger.info("Cleared all embeddings from the store")
        except Exception as e:
            logger.error(f"Failed to clear embeddings: {e}")
            raise
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Closed OpenGauss connection")
    
    def __del__(self):
        """Cleanup on object destruction."""
        self.close()
