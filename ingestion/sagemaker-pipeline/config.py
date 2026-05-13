"""
Configuration management for the CLaRa Legal Analysis System.
Handles environment variables and application settings.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class LLMConfig(BaseModel):
    """LLM configuration settings."""
    provider: str = Field(default="anthropic", description="LLM provider: 'anthropic', 'openai', or 'gemini'")
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    gemini_api_key: str | None = Field(default=None)

    # Model settings
    compression_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for document compression"
    )
    chat_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model for chat responses"
    )
    temperature: float = Field(default=0.1, description="Temperature for generation")
    max_tokens: int = Field(default=4096, description="Max tokens for responses")


class VectorStoreConfig(BaseModel):
    """Vector store configuration."""
    persist_directory: Path = Field(
        default=Path("./chroma_db"),
        description="Directory for ChromaDB persistence"
    )
    collection_name: str = Field(
        default="ms_legal_abstracts",
        description="ChromaDB collection name"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )


class DocumentConfig(BaseModel):
    """Document processing configuration."""
    documents_dir: Path = Field(
        default=Path("./documents"),
        description="Directory containing source PDFs"
    )
    chunk_size: int = Field(
        default=2000,
        description="Approximate chunk size for initial document splitting"
    )
    chunk_overlap: int = Field(
        default=200,
        description="Overlap between chunks"
    )


class RetrievalConfig(BaseModel):
    """Retrieval configuration."""
    top_k: int = Field(default=5, description="Number of abstracts to retrieve")
    similarity_threshold: float = Field(
        default=0.3,
        description="Minimum similarity score for retrieval"
    )


class AWSConfig(BaseModel):
    """AWS-specific configuration."""
    region: str = Field(default="us-east-1", description="AWS region")
    opensearch_endpoint: str = Field(default="", description="OpenSearch endpoint URL")
    opensearch_index: str = Field(default="ms-legal-abstracts", description="OpenSearch index name")
    s3_bucket: str = Field(default="", description="S3 bucket for document storage")

    # Bedrock models
    bedrock_llm_model: str = Field(
        default="us.anthropic.claude-sonnet-4-6",
        description="Bedrock LLM model ID (Claude Sonnet 4.6 via inference profile)"
    )
    bedrock_embedding_model: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="Bedrock embedding model ID (Titan Embed v2)"
    )

    # Lambda settings (for deployment)
    lambda_function_name: str = Field(
        default="ms-sos-clara-chat-query",
        description="Lambda function name"
    )

    # Phase 2: Multi-state crawler config
    crawler_dest_root: str = Field(
        default="./crawled_documents",
        description="Local destination root for crawled documents"
    )
    crawler_s3_prefix: str = Field(
        default="crawled-documents",
        description="S3 prefix for crawled documents"
    )


class AppConfig(BaseModel):
    """Main application configuration."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    documents: DocumentConfig = Field(default_factory=DocumentConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    aws: AWSConfig | None = Field(default=None, description="AWS configuration")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        # Check if AWS mode is enabled
        aws_config = None
        if os.getenv("USE_AWS", "false").lower() == "true":
            aws_config = AWSConfig(
                region=os.getenv("AWS_REGION", "us-east-1"),
                opensearch_endpoint=os.getenv("OPENSEARCH_ENDPOINT", ""),
                opensearch_index=os.getenv("OPENSEARCH_INDEX", "ms-legal-abstracts"),
                s3_bucket=os.getenv("S3_BUCKET", ""),
                bedrock_llm_model=os.getenv("BEDROCK_LLM_MODEL", "us.anthropic.claude-sonnet-4-6"),
                bedrock_embedding_model=os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
                lambda_function_name=os.getenv("LAMBDA_FUNCTION_NAME", "ms-sos-clara-chat-query"),
            )
        
        return cls(
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "anthropic"),
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
                openai_api_key=os.getenv("OPENAI_API_KEY"),
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                compression_model=os.getenv("COMPRESSION_MODEL", "claude-sonnet-4-20250514"),
                chat_model=os.getenv("CHAT_MODEL", "claude-sonnet-4-20250514"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
            ),
            vector_store=VectorStoreConfig(
                persist_directory=Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")),
                collection_name=os.getenv("CHROMA_COLLECTION", "ms_legal_abstracts"),
                embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            ),
            documents=DocumentConfig(
                documents_dir=Path(os.getenv("DOCUMENTS_DIR", "./documents")),
                chunk_size=int(os.getenv("CHUNK_SIZE", "2000")),
                chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            ),
            retrieval=RetrievalConfig(
                top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
                similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.3")),
            ),
            aws=aws_config,
        )


# Global configuration instance
config = AppConfig.from_env()
