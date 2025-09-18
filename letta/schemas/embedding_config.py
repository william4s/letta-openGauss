from typing import Literal, Optional

from pydantic import BaseModel, Field


class OpenGaussConfig(BaseModel):
    """
    OpenGauss database configuration for vector storage.
    
    Attributes:
        host (str): Database host
        port (int): Database port
        database (str): Database name
        username (str): Username for authentication
        password (str): Password for authentication
        table_name (str): Table name for storing embeddings
        ssl_mode (str): SSL mode for connection
    """
    
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="letta", description="Database name")
    username: str = Field(default="postgres", description="Username for authentication")
    password: str = Field(description="Password for authentication")
    table_name: str = Field(default="passage_embeddings", description="Table name for storing embeddings")
    ssl_mode: str = Field(default="prefer", description="SSL mode for connection")
    
    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/"
            f"{self.database}?sslmode={self.ssl_mode}"
        )


class EmbeddingConfig(BaseModel):
    """

    Embedding model configuration. This object specifies all the information necessary to access an embedding model to usage with Letta, except for secret keys.

    Attributes:
        embedding_endpoint_type (str): The endpoint type for the model.
        embedding_endpoint (str): The endpoint for the model.
        embedding_model (str): The model for the embedding.
        embedding_dim (int): The dimension of the embedding.
        embedding_chunk_size (int): The chunk size of the embedding.
        azure_endpoint (:obj:`str`, optional): The Azure endpoint for the model (Azure only).
        azure_version (str): The Azure version for the model (Azure only).
        azure_deployment (str): The Azure deployment for the model (Azure only).
        opengauss_config (:obj:`OpenGaussConfig`, optional): OpenGauss configuration for vector storage.

    """

    embedding_endpoint_type: Literal[
        "openai",
        "anthropic",
        "bedrock",
        "cohere",
        "google_ai",
        "google_vertex",
        "azure",
        "groq",
        "ollama",
        "webui",
        "webui-legacy",
        "lmstudio",
        "lmstudio-legacy",
        "llamacpp",
        "koboldcpp",
        "vllm",
        "hugging-face",
        "mistral",
        "together",  # completions endpoint
    ] = Field(..., description="The endpoint type for the model.")
    embedding_endpoint: Optional[str] = Field(None, description="The endpoint for the model (`None` if local).")
    embedding_model: str = Field(..., description="The model for the embedding.")
    embedding_dim: int = Field(..., description="The dimension of the embedding.")
    embedding_chunk_size: Optional[int] = Field(300, description="The chunk size of the embedding.")
    handle: Optional[str] = Field(None, description="The handle for this config, in the format provider/model-name.")
    batch_size: int = Field(32, description="The maximum batch size for processing embeddings.")
    
    # Vector storage configuration
    opengauss_config: Optional[OpenGaussConfig] = Field(None, description="OpenGauss configuration for vector storage.")

    # azure only
    azure_endpoint: Optional[str] = Field(None, description="The Azure endpoint for the model.")
    azure_version: Optional[str] = Field(None, description="The Azure version for the model.")
    azure_deployment: Optional[str] = Field(None, description="The Azure deployment for the model.")

    @classmethod
    def default_config(cls, model_name: Optional[str] = None, provider: Optional[str] = None):


        if model_name == "bge-m3" and provider == "bge":
            # Get endpoint from environment variable or use default
            import os
            endpoint = os.getenv("BGE_API_BASE", "http://127.0.0.1:8003/v1")
            return cls(
                embedding_model="bge-m3",
                embedding_endpoint_type="openai",
                embedding_endpoint=endpoint,
                embedding_dim=1024,
                embedding_chunk_size=300,
            )
        
        if model_name == "text-embedding-ada-002" and provider == "openai":
            return cls(
                embedding_model="text-embedding-ada-002",
                embedding_endpoint_type="openai",
                embedding_endpoint="https://api.openai.com/v1",
                embedding_dim=1536,
                embedding_chunk_size=300,
            )
        if (model_name == "text-embedding-3-small" and provider == "openai") or (not model_name and provider == "openai"):
            return cls(
                embedding_model="text-embedding-3-small",
                embedding_endpoint_type="openai",
                embedding_endpoint="https://api.openai.com/v1",
                embedding_dim=2000,
                embedding_chunk_size=300,
            )
        elif model_name == "letta":
            return cls(
                embedding_endpoint="https://embeddings.memgpt.ai",
                embedding_model="BAAI/bge-large-en-v1.5",
                embedding_dim=1024,
                embedding_chunk_size=300,
                embedding_endpoint_type="hugging-face",
            )
        else:
            raise ValueError(f"Model {model_name} not supported.")

    def pretty_print(self) -> str:
        return (
            f"{self.embedding_model}"
            + (f" [type={self.embedding_endpoint_type}]" if self.embedding_endpoint_type else "")
            + (f" [ip={self.embedding_endpoint}]" if self.embedding_endpoint else "")
        )
