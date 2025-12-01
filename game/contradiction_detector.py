"""AI-powered contradiction detection using LLM.

Instead of brittle regex/string matching, we use the LLM to determine
if two statements actually contradict each other.
"""

import logging
from typing import Optional, Tuple
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ContradictionResult(BaseModel):
    """Result of contradiction check."""
    is_contradiction: bool = Field(description="True if the statements contradict each other")
    confidence: float = Field(description="Confidence level 0-1")
    explanation: str = Field(description="Brief explanation of why they do/don't contradict")


# Cache to avoid repeated LLM calls for same comparisons
_contradiction_cache: dict[tuple[str, str], ContradictionResult] = {}


async def check_contradiction_async(
    statement1: str,
    statement2: str,
    suspect_name: Optional[str] = None,
) -> ContradictionResult:
    """Use LLM to check if two statements contradict each other.
    
    Args:
        statement1: First statement (e.g., alibi claim)
        statement2: Second statement (e.g., witness claim)
        suspect_name: Optional suspect name for context
        
    Returns:
        ContradictionResult with is_contradiction, confidence, explanation
    """
    # Check cache first
    cache_key = (statement1.lower().strip(), statement2.lower().strip())
    if cache_key in _contradiction_cache:
        return _contradiction_cache[cache_key]
    
    # Reverse key also
    reverse_key = (cache_key[1], cache_key[0])
    if reverse_key in _contradiction_cache:
        return _contradiction_cache[reverse_key]
    
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        structured_llm = llm.with_structured_output(ContradictionResult)
        
        context = f" (regarding {suspect_name})" if suspect_name else ""
        
        prompt = f"""Analyze these two statements{context} and determine if they CONTRADICT each other.

Statement 1: "{statement1}"
Statement 2: "{statement2}"

A contradiction means:
- The statements CANNOT both be true at the same time
- They claim different things about the SAME situation/time/place
- One statement directly conflicts with the other

NOT a contradiction:
- Different statements about DIFFERENT people or times
- Additional information that doesn't conflict
- Witness seeing different things at different times
- One statement being more detailed than another

Be conservative - only mark as contradiction if they genuinely conflict."""

        result = await structured_llm.ainvoke(prompt)
        
        # Cache the result
        _contradiction_cache[cache_key] = result
        
        logger.info(
            "[CONTRADICTION] %s vs %s → %s (%.0f%% confidence): %s",
            statement1[:50], statement2[:50],
            "CONTRADICTION" if result.is_contradiction else "OK",
            result.confidence * 100,
            result.explanation
        )
        
        return result
        
    except Exception as e:
        logger.warning("[CONTRADICTION] LLM check failed: %s", e)
        # Default to no contradiction on error
        return ContradictionResult(
            is_contradiction=False,
            confidence=0.0,
            explanation=f"Could not analyze: {e}"
        )


def check_contradiction_sync(
    statement1: str,
    statement2: str,
    suspect_name: Optional[str] = None,
) -> ContradictionResult:
    """Synchronous version of check_contradiction_async."""
    import asyncio
    
    # Check cache first (avoid async overhead)
    cache_key = (statement1.lower().strip(), statement2.lower().strip())
    if cache_key in _contradiction_cache:
        return _contradiction_cache[cache_key]
    reverse_key = (cache_key[1], cache_key[0])
    if reverse_key in _contradiction_cache:
        return _contradiction_cache[reverse_key]
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    check_contradiction_async(statement1, statement2, suspect_name)
                )
                return future.result(timeout=10)
        else:
            return loop.run_until_complete(
                check_contradiction_async(statement1, statement2, suspect_name)
            )
    except Exception as e:
        logger.warning("[CONTRADICTION] Sync check failed: %s", e)
        return ContradictionResult(
            is_contradiction=False,
            confidence=0.0,
            explanation=f"Could not analyze: {e}"
        )


def clear_cache():
    """Clear the contradiction cache."""
    global _contradiction_cache
    _contradiction_cache = {}
    logger.info("[CONTRADICTION] Cache cleared")



