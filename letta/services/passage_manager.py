import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from typing import List, Optional

from openai import AsyncOpenAI, OpenAI
from sqlalchemy import select

from letta.constants import MAX_EMBEDDING_DIM
from letta.embeddings import embedding_model, parse_and_chunk_text
from letta.helpers.decorators import async_redis_cache
from letta.orm.errors import NoResultFound
from letta.orm.passage import AgentPassage, SourcePassage
from letta.orm.opengauss_functions import OpenGaussVectorStore
from letta.otel.tracing import trace_method
from letta.schemas.agent import AgentState
from letta.schemas.embedding_config import OpenGaussConfig
from letta.schemas.file import FileMetadata as PydanticFileMetadata
from letta.schemas.passage import Passage as PydanticPassage
from letta.schemas.user import User as PydanticUser
from letta.server.db import db_registry
from letta.settings import settings
from letta.utils import enforce_types


# TODO: Add redis-backed caching for backend
@lru_cache(maxsize=8192)
def get_openai_embedding(text: str, model: str, endpoint: str) -> List[float]:
    from letta.settings import model_settings

    client = OpenAI(api_key=model_settings.openai_api_key, base_url=endpoint, max_retries=0)
    response = client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


@async_redis_cache(key_func=lambda text, model, endpoint: f"{model}:{endpoint}:{text}")
async def get_openai_embedding_async(text: str, model: str, endpoint: str) -> list[float]:
    from letta.settings import model_settings

    client = AsyncOpenAI(api_key=model_settings.openai_api_key, base_url=endpoint, max_retries=0)
    response = await client.embeddings.create(input=text, model=model)
    return response.data[0].embedding


class PassageManager:
    """Manager class to handle business logic related to Passages."""

    def __init__(self, opengauss_config: Optional[OpenGaussConfig] = None):
        """Initialize PassageManager with optional OpenGauss configuration."""
        self.opengauss_config = opengauss_config or self._get_opengauss_config_from_settings()
        self.vector_store = None

        # Initialize OpenGauss vector store if configuration is provided
        if self.opengauss_config:
            try:
                self.vector_store = OpenGaussVectorStore(
                    connection_string=self.opengauss_config.connection_string,
                    table_name=self.opengauss_config.table_name,
                )
            except Exception as e:
                import logging

                logging.warning(f"Failed to initialize OpenGauss vector store: {e}")
                self.vector_store = None

    def _get_opengauss_config_from_settings(self) -> Optional[OpenGaussConfig]:
        """Get OpenGauss configuration from settings."""
        if not settings.enable_opengauss or not settings.opengauss_password:
            return None

        return OpenGaussConfig(
            host=settings.opengauss_host,
            port=settings.opengauss_port,
            database=settings.opengauss_database,
            username=settings.opengauss_username,
            password=settings.opengauss_password,
            table_name=settings.opengauss_table_name,
            ssl_mode=settings.opengauss_ssl_mode,
        )

    def _sync_embedding_to_vector_store(self, passage: PydanticPassage):
        """Sync embedding to OpenGauss vector store."""
        if self.vector_store and passage.embedding:
            try:
                metadata = {
                    "agent_id": passage.agent_id,
                    "source_id": passage.source_id,
                    "text": passage.text[:1000],  # Store first 1000 chars as metadata
                    "created_at": passage.created_at.isoformat() if passage.created_at else None,
                }
                self.vector_store.store_embedding(
                    passage_id=passage.id,
                    embedding=passage.embedding,
                    metadata=metadata,
                )
            except Exception as e:
                import logging

                logging.warning(f"Failed to sync embedding to OpenGauss for passage {passage.id}: {e}")

    def _remove_embedding_from_vector_store(self, passage_id: str):
        """Remove embedding from OpenGauss vector store."""
        if self.vector_store:
            try:
                self.vector_store.delete_embedding(passage_id)
            except Exception as e:
                import logging

                logging.warning(f"Failed to remove embedding from OpenGauss for passage {passage_id}: {e}")

    def _search_similar_passages_in_vector_store(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        agent_id: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[str]:
        """Search similar passages in OpenGauss vector store."""
        if not self.vector_store:
            return []

        try:
            # Get similar passages from vector store
            similar_passages = self.vector_store.search_similar_passages(
                query_embedding=query_embedding,
                top_k=top_k,
                min_similarity=0.1,  # Minimum similarity threshold
                embedding_dim=len(query_embedding),
            )

            # Filter by agent_id or source_id if provided
            filtered_passage_ids = []
            for passage_id, similarity in similar_passages:
                # Get metadata to check agent_id/source_id
                embedding_data = self.vector_store.get_embedding(passage_id)
                if embedding_data:
                    _, metadata = embedding_data
                    if metadata:
                        if agent_id and metadata.get("agent_id") == agent_id:
                            filtered_passage_ids.append(passage_id)
                        elif source_id and metadata.get("source_id") == source_id:
                            filtered_passage_ids.append(passage_id)
                        elif not agent_id and not source_id:
                            filtered_passage_ids.append(passage_id)

            return filtered_passage_ids
        except Exception as e:
            import logging

            logging.warning(f"Failed to search similar passages in OpenGauss: {e}")
            return []

    # AGENT PASSAGE METHODS
    @enforce_types
    @trace_method
    def get_agent_passage_by_id(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """Fetch an agent passage by ID."""
        with db_registry.session() as session:
            try:
                passage = AgentPassage.read(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Agent passage with id {passage_id} not found in database.")

    @enforce_types
    @trace_method
    async def get_agent_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """Fetch an agent passage by ID."""
        async with db_registry.async_session() as session:
            try:
                passage = await AgentPassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Agent passage with id {passage_id} not found in database.")

    # SOURCE PASSAGE METHODS
    @enforce_types
    @trace_method
    def get_source_passage_by_id(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """Fetch a source passage by ID."""
        with db_registry.session() as session:
            try:
                passage = SourcePassage.read(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Source passage with id {passage_id} not found in database.")

    @enforce_types
    @trace_method
    async def get_source_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """Fetch a source passage by ID."""
        async with db_registry.async_session() as session:
            try:
                passage = await SourcePassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                raise NoResultFound(f"Source passage with id {passage_id} not found in database.")

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def get_passage_by_id(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """DEPRECATED: Use get_agent_passage_by_id() or get_source_passage_by_id() instead."""
        import warnings

        warnings.warn(
            "get_passage_by_id is deprecated. Use get_agent_passage_by_id() or get_source_passage_by_id() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        with db_registry.session() as session:
            # Try source passages first
            try:
                passage = SourcePassage.read(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                # Try archival passages
                try:
                    passage = AgentPassage.read(db_session=session, identifier=passage_id, actor=actor)
                    return passage.to_pydantic()
                except NoResultFound:
                    raise NoResultFound(f"Passage with id {passage_id} not found in database.")

    @enforce_types
    @trace_method
    async def get_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> Optional[PydanticPassage]:
        """DEPRECATED: Use get_agent_passage_by_id_async() or get_source_passage_by_id_async() instead."""
        import warnings

        warnings.warn(
            "get_passage_by_id_async is deprecated. Use get_agent_passage_by_id_async() or get_source_passage_by_id_async() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        async with db_registry.async_session() as session:
            # Try source passages first
            try:
                passage = await SourcePassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                return passage.to_pydantic()
            except NoResultFound:
                # Try archival passages
                try:
                    passage = await AgentPassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                    return passage.to_pydantic()
                except NoResultFound:
                    raise NoResultFound(f"Passage with id {passage_id} not found in database.")

    @enforce_types
    @trace_method
    def create_agent_passage(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """Create a new agent passage."""
        if not pydantic_passage.agent_id:
            raise ValueError("Agent passage must have agent_id")
        if pydantic_passage.source_id:
            raise ValueError("Agent passage cannot have source_id")

        data = pydantic_passage.model_dump(to_orm=True)
        common_fields = {
            "id": data.get("id"),
            "text": data["text"],
            "embedding": data["embedding"],
            "embedding_config": data["embedding_config"],
            "organization_id": data["organization_id"],
            "metadata_": data.get("metadata", {}),
            "is_deleted": data.get("is_deleted", False),
            "created_at": data.get("created_at", datetime.now(timezone.utc)),
        }
        agent_fields = {"agent_id": data["agent_id"]}
        passage = AgentPassage(**common_fields, **agent_fields)

        with db_registry.session() as session:
            passage.create(session, actor=actor)
            pydantic_result = passage.to_pydantic()
            self._sync_embedding_to_vector_store(pydantic_result)  # Sync to vector store
            return pydantic_result

    @enforce_types
    @trace_method
    async def create_agent_passage_async(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """Create a new agent passage."""
        if not pydantic_passage.agent_id:
            raise ValueError("Agent passage must have agent_id")
        if pydantic_passage.source_id:
            raise ValueError("Agent passage cannot have source_id")

        data = pydantic_passage.model_dump(to_orm=True)
        common_fields = {
            "id": data.get("id"),
            "text": data["text"],
            "embedding": data["embedding"],
            "embedding_config": data["embedding_config"],
            "organization_id": data["organization_id"],
            "metadata_": data.get("metadata", {}),
            "is_deleted": data.get("is_deleted", False),
            "created_at": data.get("created_at", datetime.now(timezone.utc)),
        }
        agent_fields = {"agent_id": data["agent_id"]}
        passage = AgentPassage(**common_fields, **agent_fields)

        async with db_registry.async_session() as session:
            passage = await passage.create_async(session, actor=actor)
            pydantic_result = passage.to_pydantic()
            self._sync_embedding_to_vector_store(pydantic_result)  # Sync to vector store
            return pydantic_result

    @enforce_types
    @trace_method
    def create_source_passage(
        self, pydantic_passage: PydanticPassage, file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> PydanticPassage:
        """Create a new source passage."""
        if not pydantic_passage.source_id:
            raise ValueError("Source passage must have source_id")
        if pydantic_passage.agent_id:
            raise ValueError("Source passage cannot have agent_id")

        data = pydantic_passage.model_dump(to_orm=True)
        common_fields = {
            "id": data.get("id"),
            "text": data["text"],
            "embedding": data["embedding"],
            "embedding_config": data["embedding_config"],
            "organization_id": data["organization_id"],
            "metadata_": data.get("metadata", {}),
            "is_deleted": data.get("is_deleted", False),
            "created_at": data.get("created_at", datetime.now(timezone.utc)),
        }
        source_fields = {
            "source_id": data["source_id"],
            "file_id": data.get("file_id"),
            "file_name": file_metadata.file_name,
        }
        passage = SourcePassage(**common_fields, **source_fields)

        with db_registry.session() as session:
            passage.create(session, actor=actor)
            pydantic_result = passage.to_pydantic()
            self._sync_embedding_to_vector_store(pydantic_result)  # Sync to vector store
            return pydantic_result

    @enforce_types
    @trace_method
    async def create_source_passage_async(
        self, pydantic_passage: PydanticPassage, file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> PydanticPassage:
        """Create a new source passage."""
        if not pydantic_passage.source_id:
            raise ValueError("Source passage must have source_id")
        if pydantic_passage.agent_id:
            raise ValueError("Source passage cannot have agent_id")

        data = pydantic_passage.model_dump(to_orm=True)
        common_fields = {
            "id": data.get("id"),
            "text": data["text"],
            "embedding": data["embedding"],
            "embedding_config": data["embedding_config"],
            "organization_id": data["organization_id"],
            "metadata_": data.get("metadata", {}),
            "is_deleted": data.get("is_deleted", False),
            "created_at": data.get("created_at", datetime.now(timezone.utc)),
        }
        source_fields = {
            "source_id": data["source_id"],
            "file_id": data.get("file_id"),
            "file_name": file_metadata.file_name,
        }
        passage = SourcePassage(**common_fields, **source_fields)

        async with db_registry.async_session() as session:
            passage = await passage.create_async(session, actor=actor)
            pydantic_result = passage.to_pydantic()
            self._sync_embedding_to_vector_store(pydantic_result)  # Sync to vector store
            return pydantic_result

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def create_passage(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage() or create_source_passage() instead."""
        import warnings

        warnings.warn(
            "create_passage is deprecated. Use create_agent_passage() or create_source_passage() instead.", DeprecationWarning, stacklevel=2
        )

        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)

        with db_registry.session() as session:
            passage.create(session, actor=actor)
            return passage.to_pydantic()

    @enforce_types
    @trace_method
    async def create_passage_async(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage_async() or create_source_passage_async() instead."""
        import warnings

        warnings.warn(
            "create_passage_async is deprecated. Use create_agent_passage_async() or create_source_passage_async() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Common fields for both passage types
        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)
        async with db_registry.async_session() as session:
            passage = await passage.create_async(session, actor=actor)
            return passage.to_pydantic()

    @trace_method
    def _preprocess_passage_for_creation(self, pydantic_passage: PydanticPassage) -> "SqlAlchemyBase":
        data = pydantic_passage.model_dump(to_orm=True)
        common_fields = {
            "id": data.get("id"),
            "text": data["text"],
            "embedding": data["embedding"],
            "embedding_config": data["embedding_config"],
            "organization_id": data["organization_id"],
            "metadata_": data.get("metadata", {}),
            "is_deleted": data.get("is_deleted", False),
            "created_at": data.get("created_at", datetime.now(timezone.utc)),
        }

        if "agent_id" in data and data["agent_id"]:
            assert not data.get("source_id"), "Passage cannot have both agent_id and source_id"
            agent_fields = {
                "agent_id": data["agent_id"],
            }
            passage = AgentPassage(**common_fields, **agent_fields)
        elif "source_id" in data and data["source_id"]:
            assert not data.get("agent_id"), "Passage cannot have both agent_id and source_id"
            source_fields = {
                "source_id": data["source_id"],
                "file_id": data.get("file_id"),
            }
            passage = SourcePassage(**common_fields, **source_fields)
        else:
            raise ValueError("Passage must have either agent_id or source_id")

        return passage

    @enforce_types
    @trace_method
    def create_many_agent_passages(self, passages: List[PydanticPassage], actor: PydanticUser) -> List[PydanticPassage]:
        """Create multiple agent passages."""
        return [self.create_agent_passage(p, actor) for p in passages]

    @enforce_types
    @trace_method
    async def create_many_agent_passages_async(self, passages: List[PydanticPassage], actor: PydanticUser) -> List[PydanticPassage]:
        """Create multiple agent passages."""
        agent_passages = []
        for p in passages:
            if not p.agent_id:
                raise ValueError("Agent passage must have agent_id")
            if p.source_id:
                raise ValueError("Agent passage cannot have source_id")

            data = p.model_dump(to_orm=True)
            common_fields = {
                "id": data.get("id"),
                "text": data["text"],
                "embedding": data["embedding"],
                "embedding_config": data["embedding_config"],
                "organization_id": data["organization_id"],
                "metadata_": data.get("metadata", {}),
                "is_deleted": data.get("is_deleted", False),
                "created_at": data.get("created_at", datetime.now(timezone.utc)),
            }
            agent_fields = {"agent_id": data["agent_id"]}
            agent_passages.append(AgentPassage(**common_fields, **agent_fields))

        async with db_registry.async_session() as session:
            agent_created = await AgentPassage.batch_create_async(items=agent_passages, db_session=session, actor=actor)
            return [p.to_pydantic() for p in agent_created]

    @enforce_types
    @trace_method
    def create_many_source_passages(
        self, passages: List[PydanticPassage], file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> List[PydanticPassage]:
        """Create multiple source passages."""
        return [self.create_source_passage(p, file_metadata, actor) for p in passages]

    @enforce_types
    @trace_method
    async def create_many_source_passages_async(
        self, passages: List[PydanticPassage], file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> List[PydanticPassage]:
        """Create multiple source passages."""
        source_passages = []
        for p in passages:
            if not p.source_id:
                raise ValueError("Source passage must have source_id")
            if p.agent_id:
                raise ValueError("Source passage cannot have agent_id")

            data = p.model_dump(to_orm=True)
            common_fields = {
                "id": data.get("id"),
                "text": data["text"],
                "embedding": data["embedding"],
                "embedding_config": data["embedding_config"],
                "organization_id": data["organization_id"],
                "metadata_": data.get("metadata", {}),
                "is_deleted": data.get("is_deleted", False),
                "created_at": data.get("created_at", datetime.now(timezone.utc)),
            }
            source_fields = {
                "source_id": data["source_id"],
                "file_id": data.get("file_id"),
                "file_name": file_metadata.file_name,
            }
            source_passages.append(SourcePassage(**common_fields, **source_fields))

        async with db_registry.async_session() as session:
            source_created = await SourcePassage.batch_create_async(items=source_passages, db_session=session, actor=actor)
            return [p.to_pydantic() for p in source_created]

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def create_passage(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage() or create_source_passage() instead."""
        import warnings

        warnings.warn(
            "create_passage is deprecated. Use create_agent_passage() or create_source_passage() instead.", DeprecationWarning, stacklevel=2
        )

        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)

        with db_registry.session() as session:
            passage.create(session, actor=actor)
            return passage.to_pydantic()

    @enforce_types
    @trace_method
    async def create_passage_async(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage_async() or create_source_passage_async() instead."""
        import warnings

        warnings.warn(
            "create_passage_async is deprecated. Use create_agent_passage_async() or create_source_passage_async() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Common fields for both passage types
        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)
        async with db_registry.async_session() as session:
            passage = await passage.create_async(session, actor=actor)
            return passage.to_pydantic()

    @enforce_types
    @trace_method
    def create_many_agent_passages(self, passages: List[PydanticPassage], actor: PydanticUser) -> List[PydanticPassage]:
        """Create multiple agent passages."""
        return [self.create_agent_passage(p, actor) for p in passages]

    @enforce_types
    @trace_method
    async def create_many_agent_passages_async(self, passages: List[PydanticPassage], actor: PydanticUser) -> List[PydanticPassage]:
        """Create multiple agent passages."""
        agent_passages = []
        for p in passages:
            if not p.agent_id:
                raise ValueError("Agent passage must have agent_id")
            if p.source_id:
                raise ValueError("Agent passage cannot have source_id")

            data = p.model_dump(to_orm=True)
            common_fields = {
                "id": data.get("id"),
                "text": data["text"],
                "embedding": data["embedding"],
                "embedding_config": data["embedding_config"],
                "organization_id": data["organization_id"],
                "metadata_": data.get("metadata", {}),
                "is_deleted": data.get("is_deleted", False),
                "created_at": data.get("created_at", datetime.now(timezone.utc)),
            }
            agent_fields = {"agent_id": data["agent_id"]}
            agent_passages.append(AgentPassage(**common_fields, **agent_fields))

        async with db_registry.async_session() as session:
            agent_created = await AgentPassage.batch_create_async(items=agent_passages, db_session=session, actor=actor)
            return [p.to_pydantic() for p in agent_created]

    @enforce_types
    @trace_method
    def create_many_source_passages(
        self, passages: List[PydanticPassage], file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> List[PydanticPassage]:
        """Create multiple source passages."""
        return [self.create_source_passage(p, file_metadata, actor) for p in passages]

    @enforce_types
    @trace_method
    async def create_many_source_passages_async(
        self, passages: List[PydanticPassage], file_metadata: PydanticFileMetadata, actor: PydanticUser
    ) -> List[PydanticPassage]:
        """Create multiple source passages."""
        source_passages = []
        for p in passages:
            if not p.source_id:
                raise ValueError("Source passage must have source_id")
            if p.agent_id:
                raise ValueError("Source passage cannot have agent_id")

            data = p.model_dump(to_orm=True)
            common_fields = {
                "id": data.get("id"),
                "text": data["text"],
                "embedding": data["embedding"],
                "embedding_config": data["embedding_config"],
                "organization_id": data["organization_id"],
                "metadata_": data.get("metadata", {}),
                "is_deleted": data.get("is_deleted", False),
                "created_at": data.get("created_at", datetime.now(timezone.utc)),
            }
            source_fields = {
                "source_id": data["source_id"],
                "file_id": data.get("file_id"),
                "file_name": file_metadata.file_name,
            }
            source_passages.append(SourcePassage(**common_fields, **source_fields))

        async with db_registry.async_session() as session:
            source_created = await SourcePassage.batch_create_async(items=source_passages, db_session=session, actor=actor)
            return [p.to_pydantic() for p in source_created]

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def create_passage(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage() or create_source_passage() instead."""
        import warnings

        warnings.warn(
            "create_passage is deprecated. Use create_agent_passage() or create_source_passage() instead.", DeprecationWarning, stacklevel=2
        )

        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)

        with db_registry.session() as session:
            passage.create(session, actor=actor)
            return passage.to_pydantic()

    @enforce_types
    @trace_method
    async def create_passage_async(self, pydantic_passage: PydanticPassage, actor: PydanticUser) -> PydanticPassage:
        """DEPRECATED: Use create_agent_passage_async() or create_source_passage_async() instead."""
        import warnings

        warnings.warn(
            "create_passage_async is deprecated. Use create_agent_passage_async() or create_source_passage_async() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        # Common fields for both passage types
        passage = self._preprocess_passage_for_creation(pydantic_passage=pydantic_passage)
        async with db_registry.async_session() as session:
            passage = await passage.create_async(session, actor=actor)
            return passage.to_pydantic()

    @enforce_types
    @trace_method
    def update_agent_passage_by_id(
        self, passage_id: str, passage: PydanticPassage, actor: PydanticUser, **kwargs
    ) -> Optional[PydanticPassage]:
        """Update an agent passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            try:
                curr_passage = AgentPassage.read(
                    db_session=session,
                    identifier=passage_id,
                    actor=actor,
                )
            except NoResultFound:
                raise ValueError(f"Agent passage with id {passage_id} does not exist.")

            # Update the database record with values from the provided record
            update_data = passage.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(curr_passage, key, value)

            # Commit changes
            curr_passage.update(session, actor=actor)
            return curr_passage.to_pydantic()

    @enforce_types
    @trace_method
    async def update_agent_passage_by_id_async(
        self, passage_id: str, passage: PydanticPassage, actor: PydanticUser, **kwargs
    ) -> Optional[PydanticPassage]:
        """Update an agent passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        async with db_registry.async_session() as session:
            try:
                curr_passage = await AgentPassage.read_async(
                    db_session=session,
                    identifier=passage_id,
                    actor=actor,
                )
            except NoResultFound:
                raise ValueError(f"Agent passage with id {passage_id} does not exist.")

            # Update the database record with values from the provided record
            update_data = passage.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(curr_passage, key, value)

            # Commit changes
            await curr_passage.update_async(session, actor=actor)
            return curr_passage.to_pydantic()

    @enforce_types
    @trace_method
    def update_source_passage_by_id(
        self, passage_id: str, passage: PydanticPassage, actor: PydanticUser, **kwargs
    ) -> Optional[PydanticPassage]:
        """Update a source passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            try:
                curr_passage = SourcePassage.read(
                    db_session=session,
                    identifier=passage_id,
                    actor=actor,
                )
            except NoResultFound:
                raise ValueError(f"Source passage with id {passage_id} does not exist.")

            # Update the database record with values from the provided record
            update_data = passage.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(curr_passage, key, value)

            # Commit changes
            curr_passage.update(session, actor=actor)
            return curr_passage.to_pydantic()

    @enforce_types
    @trace_method
    async def update_source_passage_by_id_async(
        self, passage_id: str, passage: PydanticPassage, actor: PydanticUser, **kwargs
    ) -> Optional[PydanticPassage]:
        """Update a source passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        async with db_registry.async_session() as session:
            try:
                curr_passage = await SourcePassage.read_async(
                    db_session=session,
                    identifier=passage_id,
                    actor=actor,
                )
            except NoResultFound:
                raise ValueError(f"Source passage with id {passage_id} does not exist.")

            # Update the database record with values from the provided record
            update_data = passage.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(curr_passage, key, value)

            # Commit changes
            await curr_passage.update_async(session, actor=actor)
            return curr_passage.to_pydantic()

    @enforce_types
    @trace_method
    def delete_agent_passage_by_id(self, passage_id: str, actor: PydanticUser) -> bool:
        """Delete an agent passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            try:
                passage = AgentPassage.read(db_session=session, identifier=passage_id, actor=actor)
                passage.hard_delete(session, actor=actor)
                self._remove_embedding_from_vector_store(passage_id)  # Remove from vector store
                return True
            except NoResultFound:
                raise NoResultFound(f"Agent passage with id {passage_id} not found.")

    @enforce_types
    @trace_method
    async def delete_agent_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> bool:
        """Delete an agent passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        async with db_registry.async_session() as session:
            try:
                passage = await AgentPassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                await passage.hard_delete_async(session, actor=actor)
                self._remove_embedding_from_vector_store(passage_id)  # Remove from vector store
                return True
            except NoResultFound:
                raise NoResultFound(f"Agent passage with id {passage_id} not found.")

    @enforce_types
    @trace_method
    def delete_source_passage_by_id(self, passage_id: str, actor: PydanticUser) -> bool:
        """Delete a source passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            try:
                passage = SourcePassage.read(db_session=session, identifier=passage_id, actor=actor)
                passage.hard_delete(session, actor=actor)
                return True
            except NoResultFound:
                raise NoResultFound(f"Source passage with id {passage_id} not found.")

    @enforce_types
    @trace_method
    async def delete_source_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> bool:
        """Delete a source passage."""
        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        async with db_registry.async_session() as session:
            try:
                passage = await SourcePassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                await passage.hard_delete_async(session, actor=actor)
                return True
            except NoResultFound:
                raise NoResultFound(f"Source passage with id {passage_id} not found.")

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def update_passage_by_id(self, passage_id: str, passage: PydanticPassage, actor: PydanticUser, **kwargs) -> Optional[PydanticPassage]:
        """DEPRECATED: Use update_agent_passage_by_id() or update_source_passage_by_id() instead."""
        import warnings

        warnings.warn(
            "update_passage_by_id is deprecated. Use update_agent_passage_by_id() or update_source_passage_by_id() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            # Try source passages first
            try:
                curr_passage = SourcePassage.read(
                    db_session=session,
                    identifier=passage_id,
                    actor=actor,
                )
            except NoResultFound:
                # Try agent passages
                try:
                    curr_passage = AgentPassage.read(
                        db_session=session,
                        identifier=passage_id,
                        actor=actor,
                    )
                except NoResultFound:
                    raise ValueError(f"Passage with id {passage_id} does not exist.")

            # Update the database record with values from the provided record
            update_data = passage.model_dump(to_orm=True, exclude_unset=True, exclude_none=True)
            for key, value in update_data.items():
                setattr(curr_passage, key, value)

            # Commit changes
            curr_passage.update(session, actor=actor)
            return curr_passage.to_pydantic()

    @enforce_types
    @trace_method
    def delete_passage_by_id(self, passage_id: str, actor: PydanticUser) -> bool:
        """DEPRECATED: Use delete_agent_passage_by_id() or delete_source_passage_by_id() instead."""
        import warnings

        warnings.warn(
            "delete_passage_by_id is deprecated. Use delete_agent_passage_by_id() or delete_source_passage_by_id() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        with db_registry.session() as session:
            # Try source passages first
            try:
                passage = SourcePassage.read(db_session=session, identifier=passage_id, actor=actor)
                passage.hard_delete(session, actor=actor)
                return True
            except NoResultFound:
                # Try archival passages
                try:
                    passage = AgentPassage.read(db_session=session, identifier=passage_id, actor=actor)
                    passage.hard_delete(session, actor=actor)
                    return True
                except NoResultFound:
                    raise NoResultFound(f"Passage with id {passage_id} not found.")

    @enforce_types
    @trace_method
    async def delete_passage_by_id_async(self, passage_id: str, actor: PydanticUser) -> bool:
        """DEPRECATED: Use delete_agent_passage_by_id_async() or delete_source_passage_by_id_async() instead."""
        import warnings

        warnings.warn(
            "delete_passage_by_id_async is deprecated. Use delete_agent_passage_by_id_async() or delete_source_passage_by_id_async() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if not passage_id:
            raise ValueError("Passage ID must be provided.")

        async with db_registry.async_session() as session:
            # Try source passages first
            try:
                passage = await SourcePassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                await passage.hard_delete_async(session, actor=actor)
                return True
            except NoResultFound:
                # Try archival passages
                try:
                    passage = await AgentPassage.read_async(db_session=session, identifier=passage_id, actor=actor)
                    await passage.hard_delete_async(session, actor=actor)
                    return True
                except NoResultFound:
                    raise NoResultFound(f"Passage with id {passage_id} not found.")

    @enforce_types
    @trace_method
    def delete_agent_passages(
        self,
        actor: PydanticUser,
        passages: List[PydanticPassage],
    ) -> bool:
        """Delete multiple agent passages."""
        # TODO: This is very inefficient
        # TODO: We should have a base `delete_all_matching_filters`-esque function
        for passage in passages:
            self.delete_agent_passage_by_id(passage_id=passage.id, actor=actor)
        return True

    @enforce_types
    @trace_method
    async def delete_agent_passages_async(
        self,
        actor: PydanticUser,
        passages: List[PydanticPassage],
    ) -> bool:
        """Delete multiple agent passages."""
        async with db_registry.async_session() as session:
            await AgentPassage.bulk_hard_delete_async(db_session=session, identifiers=[p.id for p in passages], actor=actor)
            return True

    @enforce_types
    @trace_method
    def delete_source_passages(
        self,
        actor: PydanticUser,
        passages: List[PydanticPassage],
    ) -> bool:
        """Delete multiple source passages."""
        # TODO: This is very inefficient
        # TODO: We should have a base `delete_all_matching_filters`-esque function
        for passage in passages:
            self.delete_source_passage_by_id(passage_id=passage.id, actor=actor)
        return True

    @enforce_types
    @trace_method
    async def delete_source_passages_async(
        self,
        actor: PydanticUser,
        passages: List[PydanticPassage],
    ) -> bool:
        async with db_registry.async_session() as session:
            await SourcePassage.bulk_hard_delete_async(db_session=session, identifiers=[p.id for p in passages], actor=actor)
            return True

    # DEPRECATED - Use specific methods above
    @enforce_types
    @trace_method
    def delete_passages(
        self,
        actor: PydanticUser,
        passages: List[PydanticPassage],
    ) -> bool:
        """DEPRECATED: Use delete_agent_passages() or delete_source_passages() instead."""
        import warnings

        warnings.warn(
            "delete_passages is deprecated. Use delete_agent_passages() or delete_source_passages() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # TODO: This is very inefficient
        # TODO: We should have a base `delete_all_matching_filters`-esque function
        for passage in passages:
            self.delete_passage_by_id(passage_id=passage.id, actor=actor)
        return True

    @enforce_types
    @trace_method
    def agent_passage_size(
        self,
        actor: PydanticUser,
        agent_id: Optional[str] = None,
    ) -> int:
        """Get the total count of agent passages with optional filters.

        Args:
            actor: The user requesting the count
            agent_id: The agent ID of the messages
        """
        with db_registry.session() as session:
            return AgentPassage.size(db_session=session, actor=actor, agent_id=agent_id)

    # DEPRECATED - Use agent_passage_size() instead since this only counted agent passages anyway
    @enforce_types
    @trace_method
    def size(
        self,
        actor: PydanticUser,
        agent_id: Optional[str] = None,
    ) -> int:
        """DEPRECATED: Use agent_passage_size() instead (this only counted agent passages anyway)."""
        import warnings

        warnings.warn("size is deprecated. Use agent_passage_size() instead.", DeprecationWarning, stacklevel=2)
        with db_registry.session() as session:
            return AgentPassage.size(db_session=session, actor=actor, agent_id=agent_id)

    @enforce_types
    @trace_method
    async def agent_passage_size_async(
        self,
        actor: PydanticUser,
        agent_id: Optional[str] = None,
    ) -> int:
        """Get the total count of agent passages with optional filters.
        Args:
            actor: The user requesting the count
            agent_id: The agent ID of the messages
        """
        async with db_registry.async_session() as session:
            return await AgentPassage.size_async(db_session=session, actor=actor, agent_id=agent_id)

    @enforce_types
    @trace_method
    def source_passage_size(
        self,
        actor: PydanticUser,
        source_id: Optional[str] = None,
    ) -> int:
        """Get the total count of source passages with optional filters.

        Args:
            actor: The user requesting the count
            source_id: The source ID of the passages
        """
        with db_registry.session() as session:
            return SourcePassage.size(db_session=session, actor=actor, source_id=source_id)

    @enforce_types
    @trace_method
    async def source_passage_size_async(
        self,
        actor: PydanticUser,
        source_id: Optional[str] = None,
    ) -> int:
        """Get the total count of source passages with optional filters.
        Args:
            actor: The user requesting the count
            source_id: The source ID of the passages
        """
        async with db_registry.async_session() as session:
            return await SourcePassage.size_async(db_session=session, actor=actor, source_id=source_id)

    @enforce_types
    @trace_method
    async def estimate_embeddings_size_async(
        self,
        actor: PydanticUser,
        agent_id: Optional[str] = None,
        storage_unit: str = "GB",
    ) -> float:
        """
        Estimate the size of the embeddings. Defaults to GB.
        """
        BYTES_PER_STORAGE_UNIT = {
            "B": 1,
            "KB": 1024,
            "MB": 1024**2,
            "GB": 1024**3,
            "TB": 1024**4,
        }
        if storage_unit not in BYTES_PER_STORAGE_UNIT:
            raise ValueError(f"Invalid storage unit: {storage_unit}. Must be one of {list(BYTES_PER_STORAGE_UNIT.keys())}.")
        BYTES_PER_EMBEDDING_DIM = 4
        GB_PER_EMBEDDING = BYTES_PER_EMBEDDING_DIM / BYTES_PER_STORAGE_UNIT[storage_unit] * MAX_EMBEDDING_DIM
        return await self.agent_passage_size_async(actor=actor, agent_id=agent_id) * GB_PER_EMBEDDING

    @enforce_types
    @trace_method
    async def list_passages_by_file_id_async(self, file_id: str, actor: PydanticUser) -> List[PydanticPassage]:
        """
        List all source passages associated with a given file_id.
        """
        async with db_registry.async_session() as session:
            result = await session.execute(
                select(SourcePassage).where(SourcePassage.file_id == file_id).where(SourcePassage.organization_id == actor.organization_id)
            )
            passages = result.scalars().all()
            return [p.to_pydantic() for p in passages]
