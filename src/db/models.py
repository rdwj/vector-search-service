from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from datetime import datetime
from typing import Dict, Any, Optional

Base = declarative_base()

class Collection(Base):
    __tablename__ = "collections"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text)
    doc_metadata = Column(JSON, default={})
    embedding_dimension = Column(Integer, default=384)
    distance_function = Column(String(50), default="cosine")
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationship to documents
    documents = relationship("Document", back_populates="collection", cascade="all, delete-orphan")
    
    def to_dict(self, include_document_count: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "metadata": self.doc_metadata,
            "embedding_dimension": self.embedding_dimension,
            "distance_function": self.distance_function,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_document_count:
            result["document_count"] = len(self.documents)
            
        return result

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    doc_metadata = Column(JSON, default={})
    content_tsvector = Column(TSVECTOR)  # Full-text search index
    embedding = Column(Vector(768), nullable=True)  # Made nullable for FTS-only documents
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationship to collection
    collection = relationship("Collection", back_populates="documents")

    # Define GIN index for full-text search
    __table_args__ = (
        Index('idx_documents_content_tsvector', 'content_tsvector', postgresql_using='gin'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "document_id": self.document_id,
            "content": self.content,
            "metadata": self.doc_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }