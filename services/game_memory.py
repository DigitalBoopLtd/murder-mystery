"""RAG-based game memory service for semantic search across conversations.

This provides vector-based search across all game knowledge, complementing
the structured state in GameState. The Game Master uses this to:
- Find relevant past statements when players ask questions
- Detect contradictions between old and new statements
- Retrieve cross-references (what other suspects said about someone)
"""

import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_faiss_available = None
_embeddings = None
_vectorstore_class = None


def _check_faiss():
    """Check if FAISS is available and import dependencies."""
    global _faiss_available, _embeddings, _vectorstore_class
    
    if _faiss_available is not None:
        return _faiss_available
    
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        _vectorstore_class = FAISS
        _embeddings = OpenAIEmbeddings
        _faiss_available = True
        logger.info("[RAG] FAISS and embeddings available")
    except ImportError as e:
        _faiss_available = False
        logger.warning("[RAG] FAISS not available: %s", e)
    
    return _faiss_available


class ContradictionResult(BaseModel):
    """Result of contradiction analysis."""
    is_contradiction: bool = False
    old_statement: Optional[str] = None
    new_statement: Optional[str] = None
    explanation: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class GameMemory:
    """Centralized memory with structured state and vector search.
    
    This service provides RAG capabilities for the murder mystery game:
    - Indexes all conversation exchanges
    - Semantic search across game knowledge
    - Contradiction detection
    - Cross-reference retrieval
    
    The Game Master (orchestrator) owns this memory and uses it to
    assemble rich context for stateless suspect agents.
    """
    
    def __init__(self):
        self.vectorstore = None
        self.documents: List[Dict] = []  # Backup of all indexed docs
        self._initialized = False
        
    @property
    def is_available(self) -> bool:
        """Check if RAG functionality is available."""
        return _check_faiss() and self._initialized
    
    def initialize(self) -> bool:
        """Initialize empty vectorstore.
        
        Returns:
            True if initialization succeeded, False otherwise.
        """
        if not _check_faiss():
            logger.warning("[RAG] Cannot initialize - FAISS not available")
            return False
        
        try:
            embeddings = _embeddings()
            # Initialize with a placeholder document (FAISS requires at least one)
            self.vectorstore = _vectorstore_class.from_texts(
                ["Game memory initialized. No conversations recorded yet."],
                embeddings,
                metadatas=[{"type": "system", "suspect": None, "turn": -1}]
            )
            self._initialized = True
            logger.info("[RAG] GameMemory initialized successfully")
            return True
        except Exception as e:
            logger.error("[RAG] Failed to initialize GameMemory: %s", e)
            self._initialized = False
            return False
    
    def add_conversation(
        self,
        suspect: str,
        question: str,
        answer: str,
        turn: int,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Index a conversation exchange for semantic search.
        
        Args:
            suspect: Name of the suspect
            question: Player's question
            answer: Suspect's response
            turn: Game turn number
            metadata: Optional additional metadata
            
        Returns:
            True if indexing succeeded, False otherwise.
        """
        if not self.is_available:
            logger.debug("[RAG] Skipping indexing - not available")
            return False
        
        try:
            # Create a searchable document combining question and answer
            doc = (
                f"Turn {turn}: Detective asked {suspect}: \"{question}\" "
                f"and {suspect} responded: \"{answer}\""
            )
            
            doc_metadata = {
                "type": "conversation",
                "suspect": suspect,
                "turn": turn,
                "question": question,
                "answer": answer,
                **(metadata or {})
            }
            
            self.vectorstore.add_texts([doc], metadatas=[doc_metadata])
            self.documents.append({"text": doc, "metadata": doc_metadata})
            
            logger.info(
                "[RAG] Indexed conversation with %s (turn %d, %d total docs)",
                suspect, turn, len(self.documents)
            )
            return True
            
        except Exception as e:
            logger.error("[RAG] Failed to index conversation: %s", e)
            return False
    
    def add_clue(
        self,
        clue_id: str,
        description: str,
        location: str,
        significance: str,
        turn: int
    ) -> bool:
        """Index a discovered clue for semantic search.
        
        Args:
            clue_id: Unique clue identifier
            description: Clue description
            location: Where it was found
            significance: What it means
            turn: Game turn when discovered
            
        Returns:
            True if indexing succeeded, False otherwise.
        """
        if not self.is_available:
            return False
        
        try:
            doc = (
                f"Turn {turn}: Clue discovered at {location}: {description}. "
                f"Significance: {significance}"
            )
            
            doc_metadata = {
                "type": "clue",
                "clue_id": clue_id,
                "location": location,
                "turn": turn
            }
            
            self.vectorstore.add_texts([doc], metadatas=[doc_metadata])
            self.documents.append({"text": doc, "metadata": doc_metadata})
            
            logger.info("[RAG] Indexed clue %s from %s", clue_id, location)
            return True
            
        except Exception as e:
            logger.error("[RAG] Failed to index clue: %s", e)
            return False
    
    def search(
        self,
        query: str,
        k: int = 5,
        filter_type: Optional[str] = None
    ) -> List[Tuple[str, Dict]]:
        """Semantic search across all indexed content.
        
        Args:
            query: Search query
            k: Number of results to return
            filter_type: Optional filter by document type ("conversation", "clue")
            
        Returns:
            List of (document_text, metadata) tuples.
        """
        if not self.is_available:
            return []
        
        try:
            if filter_type:
                results = self.vectorstore.similarity_search(
                    query, k=k, filter={"type": filter_type}
                )
            else:
                results = self.vectorstore.similarity_search(query, k=k)
            
            return [(r.page_content, r.metadata) for r in results]
            
        except Exception as e:
            logger.error("[RAG] Search failed: %s", e)
            return []
    
    def search_by_suspect(
        self,
        suspect: str,
        query: str,
        k: int = 3
    ) -> List[Tuple[str, Dict]]:
        """Search statements from a specific suspect.
        
        Args:
            suspect: Suspect name to filter by
            query: Search query
            k: Number of results
            
        Returns:
            List of (document_text, metadata) tuples from this suspect.
        """
        if not self.is_available:
            return []
        
        try:
            results = self.vectorstore.similarity_search(
                query, k=k, filter={"suspect": suspect}
            )
            return [(r.page_content, r.metadata) for r in results]
            
        except Exception as e:
            logger.error("[RAG] Suspect search failed: %s", e)
            return []
    
    def get_suspect_history(self, suspect: str) -> List[Dict]:
        """Get all indexed conversations with a suspect.
        
        Args:
            suspect: Suspect name
            
        Returns:
            List of conversation metadata dicts, sorted by turn.
        """
        convos = [
            doc["metadata"]
            for doc in self.documents
            if doc["metadata"].get("suspect") == suspect
            and doc["metadata"].get("type") == "conversation"
        ]
        return sorted(convos, key=lambda x: x.get("turn", 0))
    
    def find_related_statements(
        self,
        suspect: str,
        new_statement: str,
        k: int = 3
    ) -> List[str]:
        """Find past statements from a suspect related to a new statement.
        
        Used for contradiction detection - finds semantically similar
        past statements that might conflict with the new one.
        
        Args:
            suspect: Suspect name
            new_statement: The new statement to check against
            k: Number of similar statements to retrieve
            
        Returns:
            List of past statement texts.
        """
        results = self.search_by_suspect(suspect, new_statement, k=k)
        return [text for text, _ in results]
    
    def search_cross_references(
        self,
        about_suspect: str,
        k: int = 3
    ) -> List[Tuple[str, str]]:
        """Find what other suspects said about a specific suspect.
        
        Args:
            about_suspect: Name of suspect being discussed
            k: Number of results
            
        Returns:
            List of (speaker_name, statement) tuples.
        """
        if not self.is_available:
            return []
        
        # Search for mentions of this suspect in other suspects' statements
        query = f"statements about {about_suspect} or mentions {about_suspect}"
        results = self.search(query, k=k * 2, filter_type="conversation")
        
        # Filter out statements BY the suspect (we want statements ABOUT them)
        cross_refs = []
        for text, metadata in results:
            speaker = metadata.get("suspect")
            if speaker and speaker != about_suspect:
                cross_refs.append((speaker, text))
        
        return cross_refs[:k]
    
    def clear(self):
        """Clear all indexed documents (for game reset)."""
        self.documents = []
        self._initialized = False
        self.vectorstore = None
        logger.info("[RAG] GameMemory cleared")


# ============================================================================
# Singleton instance for game-wide memory
# ============================================================================

_game_memory: Optional[GameMemory] = None


def get_game_memory() -> GameMemory:
    """Get or create the singleton GameMemory instance."""
    global _game_memory
    if _game_memory is None:
        _game_memory = GameMemory()
    return _game_memory


def initialize_game_memory() -> bool:
    """Initialize the game memory service.
    
    Call this at game start to set up the vector store.
    
    Returns:
        True if initialization succeeded.
    """
    memory = get_game_memory()
    return memory.initialize()


def reset_game_memory():
    """Reset game memory for a new game."""
    memory = get_game_memory()
    memory.clear()


