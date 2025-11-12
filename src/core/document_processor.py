"""
Document processing pipeline for text chunking and metadata extraction
"""
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from src.config.settings import Settings

logger = logging.getLogger(__name__)

@dataclass
class DocumentChunk:
    """Represents a chunk of a document with metadata"""
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: Dict[str, Any]

class DocumentProcessor:
    """
    Document processing pipeline for RAG operations
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.default_chunk_size = settings.document_chunk_size
        self.default_chunk_overlap = settings.document_chunk_overlap
    
    def generate_document_id(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a unique document ID based on content and metadata
        """
        # Create a hash from content and relevant metadata
        hash_input = content
        if metadata:
            # Include key metadata in hash (excluding timestamp-like fields)
            relevant_keys = ['title', 'source', 'author', 'type']
            for key in relevant_keys:
                if key in metadata:
                    hash_input += f"_{key}:{metadata[key]}"
        
        # Generate SHA256 hash
        hash_object = hashlib.sha256(hash_input.encode())
        return hash_object.hexdigest()[:16]  # Use first 16 chars for readability
    
    def chunk_document(
        self,
        content: str,
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Split document into overlapping chunks
        """
        if not content or not content.strip():
            return []
        
        chunk_size = chunk_size or self.default_chunk_size
        overlap = overlap or self.default_chunk_overlap
        
        # Ensure overlap is not larger than chunk size
        overlap = min(overlap, chunk_size // 2)
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(content):
            # Calculate end position
            end = min(start + chunk_size, len(content))
            
            # Adjust end to avoid cutting words in the middle
            if end < len(content):
                end = self._find_word_boundary(content, end)
            
            # Extract chunk content
            chunk_content = content[start:end].strip()
            
            # Only add non-empty chunks
            if chunk_content:
                chunk = DocumentChunk(
                    content=chunk_content,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    metadata={
                        **(metadata or {}),
                        'chunk_size': len(chunk_content),
                        'is_first_chunk': chunk_index == 0,
                        'is_last_chunk': end >= len(content)
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
            
            # Move start position with overlap
            start = end - overlap
            
            # Prevent infinite loop
            if start >= end:
                break
        
        logger.debug(f"Split document into {len(chunks)} chunks")
        return chunks
    
    def _find_word_boundary(self, text: str, position: int) -> int:
        """
        Find the nearest word boundary before the given position
        """
        # Look backward for whitespace or punctuation
        for i in range(position, max(0, position - 100), -1):
            if text[i] in ' \n\t.,;:!?':
                return i + 1
        
        # If no boundary found, return original position
        return position
    
    def extract_metadata(self, content: str, base_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract metadata from document content
        """
        metadata = base_metadata.copy() if base_metadata else {}
        
        # Basic content statistics
        metadata.update({
            'content_length': len(content),
            'word_count': len(content.split()),
            'line_count': content.count('\n') + 1,
            'char_count': len(content)
        })
        
        # Simple content type detection
        if self._looks_like_code(content):
            metadata['content_type'] = 'code'
        elif self._looks_like_markdown(content):
            metadata['content_type'] = 'markdown'
        elif self._looks_like_html(content):
            metadata['content_type'] = 'html'
        else:
            metadata['content_type'] = 'text'
        
        # Extract title if possible
        title = self._extract_title(content)
        if title:
            metadata['title'] = title
        
        return metadata
    
    def _looks_like_code(self, content: str) -> bool:
        """Simple heuristic to detect code content"""
        code_indicators = [
            'def ', 'class ', 'import ', 'from ', 'function',
            '#!/', '<?', '/*', '//', '<!--', 'SELECT', 'FROM'
        ]
        return any(indicator in content for indicator in code_indicators)
    
    def _looks_like_markdown(self, content: str) -> bool:
        """Simple heuristic to detect markdown content"""
        markdown_indicators = ['# ', '## ', '### ', '**', '*', '`', '```', '[', '](']
        return any(indicator in content for indicator in markdown_indicators)
    
    def _looks_like_html(self, content: str) -> bool:
        """Simple heuristic to detect HTML content"""
        html_indicators = ['<html', '<div', '<p>', '<h1', '<h2', '<script', '<style']
        return any(indicator in content.lower() for indicator in html_indicators)
    
    def _extract_title(self, content: str) -> Optional[str]:
        """Extract title from content"""
        lines = content.split('\n')
        
        # Look for markdown title
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
            elif line.startswith('## '):
                return line[3:].strip()
        
        # Look for HTML title
        if '<title>' in content.lower():
            start = content.lower().find('<title>') + 7
            end = content.lower().find('</title>', start)
            if start > 6 and end > start:
                return content[start:end].strip()
        
        # Use first line if it looks like a title
        if lines:
            first_line = lines[0].strip()
            if first_line and len(first_line) < 100 and not first_line.endswith('.'):
                return first_line
        
        return None
    
    def validate_document(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate document content and metadata
        """
        # Check content
        if not content or not content.strip():
            return False, "Document content cannot be empty"

        # Use configurable max document size (default 5MB to prevent OOM)
        max_size_bytes = self.settings.max_document_size_mb * 1_000_000
        if len(content) > max_size_bytes:
            return False, f"Document content too large (max {self.settings.max_document_size_mb}MB)"
        
        # Check metadata
        if metadata:
            if not isinstance(metadata, dict):
                return False, "Metadata must be a dictionary"
            
            # Check for reserved keys
            reserved_keys = ['chunk_index', 'start_char', 'end_char', 'chunk_size']
            for key in reserved_keys:
                if key in metadata:
                    return False, f"Metadata key '{key}' is reserved"
        
        return True, None
    
    def preprocess_content(self, content: str) -> str:
        """
        Preprocess document content for better chunking
        """
        # Normalize whitespace
        content = ' '.join(content.split())
        
        # Remove excessive newlines
        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
        
        # Remove control characters
        content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\t')
        
        return content
    
    def get_chunk_texts(self, chunks: List[DocumentChunk]) -> List[str]:
        """
        Extract just the text content from chunks
        """
        return [chunk.content for chunk in chunks]
    
    def get_chunk_metadata(self, chunks: List[DocumentChunk]) -> List[Dict[str, Any]]:
        """
        Extract metadata from chunks
        """
        return [chunk.metadata for chunk in chunks]