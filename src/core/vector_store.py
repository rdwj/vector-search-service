from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import Collection, Document
from src.db.connection import DatabaseManager
from pgvector.sqlalchemy import Vector
import logging

logger = logging.getLogger(__name__)

class PostgreSQLVectorStore:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def create_collection(
        self, 
        name: str, 
        description: str = None,
        embedding_dimension: int = 1024,
        distance_function: str = "cosine",
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a new collection"""
        try:
            async with self.db_manager.get_session_context() as session:
                collection = Collection(
                    name=name,
                    description=description,
                    embedding_dimension=embedding_dimension,
                    distance_function=distance_function,
                    doc_metadata=metadata or {}
                )
                session.add(collection)
                await session.commit()
                await session.refresh(collection)
                
                logger.info(f"Collection '{name}' created successfully")
                return collection.to_dict()
                
        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            raise
    
    async def get_collection(self, name: str) -> Optional[Dict[str, Any]]:
        """Get collection by name"""
        try:
            async with self.db_manager.get_session_context() as session:
                result = await session.execute(
                    select(Collection).where(Collection.name == name)
                )
                collection = result.scalar_one_or_none()
                
                if collection:
                    return collection.to_dict()
                return None
                
        except Exception as e:
            logger.error(f"Failed to get collection '{name}': {e}")
            raise
    
    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections"""
        try:
            async with self.db_manager.get_session_context() as session:
                result = await session.execute(select(Collection))
                collections = result.scalars().all()
                
                return [collection.to_dict() for collection in collections]
                
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise
    
    async def delete_collection(self, name: str) -> bool:
        """Delete collection and all associated documents"""
        try:
            async with self.db_manager.get_session_context() as session:
                result = await session.execute(
                    delete(Collection).where(Collection.name == name)
                )
                await session.commit()
                
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"Collection '{name}' deleted successfully")
                return deleted
                
        except Exception as e:
            logger.error(f"Failed to delete collection '{name}': {e}")
            raise
    
    async def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        embeddings: List[List[float]] = None,
        metadata: List[Dict[str, Any]] = None,
        document_ids: List[str] = None,
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Add documents to collection with batched commits to prevent OOM.

        If embeddings are None, documents are stored with tsvector only (automatic via trigger).
        The tsvector column is populated automatically by the database trigger.

        Args:
            batch_size: Number of documents to commit per transaction (default 10)
        """
        try:
            all_results = []
            total_docs = len(documents)

            # Process documents in batches to prevent OOM
            for batch_start in range(0, total_docs, batch_size):
                batch_end = min(batch_start + batch_size, total_docs)
                batch_docs = documents[batch_start:batch_end]

                async with self.db_manager.get_session_context() as session:
                    # Get collection (once per batch)
                    collection_result = await session.execute(
                        select(Collection).where(Collection.name == collection_name)
                    )
                    collection = collection_result.scalar_one_or_none()

                    if not collection:
                        raise ValueError(f"Collection '{collection_name}' not found")

                    # Prepare batch of documents
                    document_objects = []
                    for i in range(len(batch_docs)):
                        global_idx = batch_start + i
                        content = batch_docs[i]
                        doc_id = document_ids[global_idx] if document_ids else f"doc_{global_idx}"
                        doc_metadata = metadata[global_idx] if metadata else {}

                        # Create document kwargs without embedding initially
                        doc_kwargs = {
                            "collection_id": collection.id,
                            "document_id": doc_id,
                            "content": content,
                            "doc_metadata": doc_metadata,
                            # content_tsvector populated automatically by database trigger
                        }

                        # Only set embedding if provided (avoids pgvector NULL handling bug)
                        if embeddings is not None:
                            doc_kwargs["embedding"] = embeddings[global_idx]

                        document = Document(**doc_kwargs)
                        document_objects.append(document)

                    # Add batch to session and commit
                    session.add_all(document_objects)
                    await session.commit()

                    # Refresh objects to get IDs
                    for doc in document_objects:
                        await session.refresh(doc)

                    batch_results = [doc.to_dict() for doc in document_objects]
                    all_results.extend(batch_results)

                    logger.info(f"Committed batch {batch_start//batch_size + 1}: {len(batch_docs)} documents to collection '{collection_name}'")

            logger.info(f"Added total {len(all_results)} documents to collection '{collection_name}' (FTS mode, {total_docs//batch_size + 1} batches)")
            return all_results

        except Exception as e:
            logger.error(f"Failed to add documents to collection '{collection_name}': {e}")
            raise
    
    async def fulltext_search(
        self,
        collection_name: str,
        query_text: str,
        limit: int = 10,
        metadata_filter: Dict[str, Any] = None,
        language: str = "english"
    ) -> List[Dict[str, Any]]:
        """
        Perform full-text search using PostgreSQL tsvector and TF-IDF ranking.

        Args:
            collection_name: Name of the collection to search
            query_text: User's search query (plain text)
            limit: Maximum number of results to return
            metadata_filter: Optional metadata filters
            language: Text search language configuration (default: english)

        Returns:
            List of documents with relevance scores
        """
        try:
            async with self.db_manager.get_session_context() as session:
                # Get collection
                collection_result = await session.execute(
                    select(Collection).where(Collection.name == collection_name)
                )
                collection = collection_result.scalar_one_or_none()

                if not collection:
                    raise ValueError(f"Collection '{collection_name}' not found")

                # Build SQL query with TF-IDF ranking
                # Using plainto_tsquery for safety (handles special characters and creates AND queries)
                # ts_rank_cd with normalization 32 provides best TF-IDF-like ranking
                sql_query = text("""
                    SELECT
                        id,
                        collection_id,
                        document_id,
                        content,
                        doc_metadata,
                        ts_rank_cd(content_tsvector, query, 32) AS rank,
                        created_at,
                        updated_at
                    FROM documents,
                         plainto_tsquery(:language, :query_text) AS query
                    WHERE collection_id = :collection_id
                      AND content_tsvector @@ query
                    ORDER BY rank DESC
                    LIMIT :limit
                """)

                # Execute query
                result = await session.execute(
                    sql_query,
                    {
                        "language": language,
                        "query_text": query_text,
                        "collection_id": collection.id,
                        "limit": limit
                    }
                )
                rows = result.fetchall()

                # Format results
                search_results = []
                for row in rows:
                    result_dict = {
                        "id": row.id,
                        "collection_id": row.collection_id,
                        "document_id": row.document_id,
                        "content": row.content,
                        "metadata": row.doc_metadata,
                        "score": float(row.rank),  # TF-IDF rank as score
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "updated_at": row.updated_at.isoformat() if row.updated_at else None
                    }
                    search_results.append(result_dict)

                logger.info(f"Full-text search returned {len(search_results)} results from '{collection_name}'")
                return search_results

        except Exception as e:
            logger.error(f"Full-text search failed in collection '{collection_name}': {e}")
            raise

    async def similarity_search(
        self,
        collection_name: str,
        query_embedding: List[float],
        limit: int = 10,
        distance_threshold: float = None,
        metadata_filter: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Perform similarity search (LEGACY - kept for rollback capability)"""
        try:
            async with self.db_manager.get_session_context() as session:
                # Get collection
                collection_result = await session.execute(
                    select(Collection).where(Collection.name == collection_name)
                )
                collection = collection_result.scalar_one_or_none()

                if not collection:
                    raise ValueError(f"Collection '{collection_name}' not found")

                # Build query
                query = select(
                    Document,
                    Document.embedding.cosine_distance(query_embedding).label("distance")
                ).where(Document.collection_id == collection.id)

                # Apply metadata filter if provided
                if metadata_filter:
                    for key, value in metadata_filter.items():
                        query = query.where(Document.doc_metadata[key].as_string() == str(value))

                # Apply distance threshold if provided
                if distance_threshold is not None:
                    query = query.where(
                        Document.embedding.cosine_distance(query_embedding) <= distance_threshold
                    )

                # Order by distance and limit
                query = query.order_by("distance").limit(limit)

                # Execute query
                result = await session.execute(query)
                rows = result.all()

                # Format results
                search_results = []
                for document, distance in rows:
                    result_dict = document.to_dict()
                    result_dict["distance"] = float(distance)
                    search_results.append(result_dict)

                logger.info(f"Similarity search returned {len(search_results)} results from collection '{collection_name}'")
                return search_results

        except Exception as e:
            logger.error(f"Failed to perform similarity search in collection '{collection_name}': {e}")
            raise
    
    async def get_documents(
        self,
        collection_name: str,
        document_ids: List[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get documents from collection"""
        try:
            async with self.db_manager.get_session_context() as session:
                # Get collection
                collection_result = await session.execute(
                    select(Collection).where(Collection.name == collection_name)
                )
                collection = collection_result.scalar_one_or_none()
                
                if not collection:
                    raise ValueError(f"Collection '{collection_name}' not found")
                
                # Build query
                query = select(Document).where(Document.collection_id == collection.id)
                
                # Filter by document IDs if provided
                if document_ids:
                    query = query.where(Document.document_id.in_(document_ids))
                
                # Apply pagination
                query = query.offset(offset).limit(limit)
                
                # Execute query
                result = await session.execute(query)
                documents = result.scalars().all()
                
                return [doc.to_dict() for doc in documents]
                
        except Exception as e:
            logger.error(f"Failed to get documents from collection '{collection_name}': {e}")
            raise
    
    async def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> int:
        """Delete documents from collection"""
        try:
            async with self.db_manager.get_session_context() as session:
                # Get collection
                collection_result = await session.execute(
                    select(Collection).where(Collection.name == collection_name)
                )
                collection = collection_result.scalar_one_or_none()
                
                if not collection:
                    raise ValueError(f"Collection '{collection_name}' not found")
                
                # Delete documents
                result = await session.execute(
                    delete(Document).where(
                        Document.collection_id == collection.id,
                        Document.document_id.in_(document_ids)
                    )
                )
                await session.commit()
                
                deleted_count = result.rowcount
                logger.info(f"Deleted {deleted_count} documents from collection '{collection_name}'")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete documents from collection '{collection_name}': {e}")
            raise
    
    async def get_collection_stats(self, name: str) -> Dict[str, Any]:
        """Get collection statistics"""
        try:
            async with self.db_manager.get_session_context() as session:
                # Get collection
                collection_result = await session.execute(
                    select(Collection).where(Collection.name == name)
                )
                collection = collection_result.scalar_one_or_none()
                
                if not collection:
                    raise ValueError(f"Collection '{name}' not found")
                
                # Get document count
                count_result = await session.execute(
                    select(func.count(Document.id)).where(Document.collection_id == collection.id)
                )
                document_count = count_result.scalar()
                
                # Get collection size (approximate)
                size_result = await session.execute(
                    text("SELECT pg_total_relation_size('documents')::bigint")
                )
                total_size = size_result.scalar()
                
                return {
                    "name": collection.name,
                    "description": collection.description,
                    "document_count": document_count,
                    "embedding_dimension": collection.embedding_dimension,
                    "distance_function": collection.distance_function,
                    "metadata": collection.doc_metadata,
                    "created_at": collection.created_at.isoformat() if collection.created_at else None,
                    "updated_at": collection.updated_at.isoformat() if collection.updated_at else None,
                    "estimated_size_bytes": total_size
                }
                
        except Exception as e:
            logger.error(f"Failed to get collection stats for '{name}': {e}")
            raise