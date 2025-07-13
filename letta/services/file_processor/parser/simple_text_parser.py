from typing import NamedTuple, List, Optional

from letta.log import get_logger
from letta.otel.tracing import trace_method
from letta.services.file_processor.file_types import is_simple_text_mime_type
from letta.services.file_processor.parser.base_parser import FileParser

logger = get_logger(__name__)


class SimplePageObject(NamedTuple):
    """Simple representation of a parsed page"""
    index: int
    markdown: str
    images: List = []
    dimensions: Optional[tuple] = None


class SimpleUsageInfo(NamedTuple):
    """Simple usage information"""
    pages_processed: int


class SimpleParseResponse(NamedTuple):
    """Simple parse response that mimics Mistral's OCRResponse structure"""
    model: str
    pages: List[SimplePageObject]
    usage_info: SimpleUsageInfo
    document_annotation: Optional[str] = None


class SimpleTextParser(FileParser):
    """Simple text parser for text files that don't require OCR"""

    def __init__(self, model: str = "simple-text-parser"):
        self.model = model

    @trace_method
    async def extract_text(self, content: bytes, mime_type: str) -> SimpleParseResponse:
        """Extract text from simple text files."""
        try:
            if is_simple_text_mime_type(mime_type):
                logger.info(f"Extracting text directly using simple parser: {self.model}")
                text = content.decode("utf-8", errors="replace")
                return SimpleParseResponse(
                    model=self.model,
                    pages=[
                        SimplePageObject(
                            index=0,
                            markdown=text,
                            images=[],
                            dimensions=None,
                        )
                    ],
                    usage_info=SimpleUsageInfo(pages_processed=1),
                    document_annotation=None,
                )
            else:
                raise ValueError(f"Unsupported MIME type for simple text parser: {mime_type}")

        except UnicodeDecodeError as e:
            logger.error(f"Failed to decode text content: {e}")
            raise ValueError(f"Failed to decode text content as UTF-8: {e}")
        except Exception as e:
            logger.error(f"Failed to extract text using simple parser: {e}")
            raise
