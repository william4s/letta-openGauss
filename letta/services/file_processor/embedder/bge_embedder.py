import asyncio
from typing import List, Optional, Tuple, cast

from letta.llm_api.llm_client import LLMClient
from letta.llm_api.openai_client import OpenAIClient
from letta.log import get_logger
from letta.otel.tracing import log_event, trace_method
from letta.schemas.embedding_config import EmbeddingConfig
from letta.schemas.enums import ProviderType
from letta.schemas.passage import Passage
from letta.schemas.user import User
from letta.services.file_processor.embedder.base_embedder import BaseEmbedder
from letta.settings import model_settings

logger = get_logger(__name__)


class BGEEmbedder(BaseEmbedder):
    """BGE-based embedding generation using OpenAI-compatible API"""

    def __init__(self, embedding_config: Optional[EmbeddingConfig] = None):
        # Default BGE configuration
        self.default_embedding_config = EmbeddingConfig(
            embedding_model="bge-m3",
            embedding_endpoint_type="openai",
            embedding_endpoint=model_settings.bge_api_base,
            embedding_dim=1024,
            embedding_chunk_size=300,
            batch_size=32,
        )
        self.embedding_config = embedding_config or self.default_embedding_config
        self.max_concurrent_requests = 20

        # Create OpenAI-compatible client for BGE
        self.client: OpenAIClient = cast(
            OpenAIClient,
            LLMClient.create(
                provider_type=ProviderType.openai,
                put_inner_thoughts_first=False,
                actor=None,  # Not necessary
            ),
        )

    @trace_method
    async def _embed_batch(self, batch: List[str], batch_indices: List[int]) -> List[Tuple[int, List[float]]]:
        """Embed a single batch and return embeddings with their original indices"""
        log_event(
            "embedder.batch_started",
            {
                "batch_size": len(batch),
                "model": self.embedding_config.embedding_model,
                "embedding_endpoint_type": self.embedding_config.embedding_endpoint_type,
            },
        )
        embeddings = await self.client.request_embeddings(inputs=batch, embedding_config=self.embedding_config)
        log_event("embedder.batch_completed", {"batch_size": len(batch), "embeddings_generated": len(embeddings)})
        return [(idx, e) for idx, e in zip(batch_indices, embeddings)]

    @trace_method
    async def generate_embedded_passages(self, file_id: str, source_id: str, chunks: List[str], actor: User) -> List[Passage]:
        """Generate embeddings for chunks with batching and concurrent processing"""
        if not chunks:
            return []

        logger.info(f"Generating BGE embeddings for {len(chunks)} chunks using {self.embedding_config.embedding_model}")
        log_event(
            "embedder.generation_started",
            {
                "total_chunks": len(chunks),
                "model": self.embedding_config.embedding_model,
                "embedding_endpoint_type": self.embedding_config.embedding_endpoint_type,
                "batch_size": self.embedding_config.batch_size,
                "file_id": file_id,
                "source_id": source_id,
            },
        )

        # Create batches with their original indices
        batches = []
        batch_indices = []

        for i in range(0, len(chunks), self.embedding_config.batch_size):
            batch = chunks[i : i + self.embedding_config.batch_size]
            indices = list(range(i, min(i + self.embedding_config.batch_size, len(chunks))))
            batches.append(batch)
            batch_indices.append(indices)

        logger.info(f"Processing {len(batches)} batches with BGE")
        log_event(
            "embedder.batching_completed",
            {"total_batches": len(batches), "batch_size": self.embedding_config.batch_size, "total_chunks": len(chunks)},
        )

        async def process(batch: List[str], indices: List[int]):
            try:
                return await self._embed_batch(batch, indices)
            except Exception as e:
                logger.error("Failed to embed batch of size %s with BGE: %s", len(batch), e)
                log_event("embedder.batch_failed", {"batch_size": len(batch), "error": str(e), "error_type": type(e).__name__})
                raise

        # Execute all batches concurrently with semaphore control
        tasks = [process(batch, indices) for batch, indices in zip(batches, batch_indices)]

        semaphore = asyncio.Semaphore(self.max_concurrent_requests)

        async def bounded_process(task):
            async with semaphore:
                return await task

        bounded_tasks = [bounded_process(task) for task in tasks]
        results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

        # Check for any exceptions in the results
        exceptions = [r for r in results if isinstance(r, Exception)]
        if exceptions:
            logger.error("Failed to generate embeddings for %d batches", len(exceptions))
            log_event("embedder.generation_failed", {"failed_batches": len(exceptions), "total_batches": len(batches)})
            raise exceptions[0]  # Raise the first exception

        # Flatten results and sort by original indices
        all_embeddings = []
        for batch_result in results:
            all_embeddings.extend(batch_result)

        # Sort by original index to maintain order
        all_embeddings.sort(key=lambda x: x[0])
        sorted_embeddings = [embedding for _, embedding in all_embeddings]

        logger.info(f"Successfully generated {len(sorted_embeddings)} BGE embeddings")
        log_event("embedder.generation_completed", {"total_embeddings": len(sorted_embeddings)})

        # Create passages with embeddings
        passages = []
        for i, (chunk, embedding) in enumerate(zip(chunks, sorted_embeddings)):
            passage = Passage(
                file_id=file_id,
                source_id=source_id,
                embedding=embedding,
                text=chunk,
                doc_id=f"{file_id}-{i}",
            )
            passages.append(passage)

        return passages
