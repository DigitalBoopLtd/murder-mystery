"""Tools for the game master agent."""

import logging
import os
import re
import tempfile
from typing import Annotated, Optional, List
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from services.tts_service import text_to_speech
from services.game_memory import get_game_memory

logger = logging.getLogger(__name__)

# Directory for storing generated audio files
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "murder_mystery_audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

# Global dict to store alignment data for tool-generated audio
# Key: audio_path, Value: alignment_data list
_audio_alignment_cache = {}


@tool
def interrogate_suspect(
    suspect_name: Annotated[str, "The name of the suspect to interrogate"],
    suspect_profile: Annotated[
        str,
        "Full profile including: static info (role, personality, alibi, secret, "
        "clue_they_know, isGuilty), EMOTIONAL STATE (trust %, nervousness %), "
        "CONVERSATION HISTORY (past exchanges), and BEHAVIORAL INSTRUCTIONS",
    ],
    player_question: Annotated[
        str, "The player's question or statement to the suspect"
    ],
    voice_id: Annotated[Optional[str], "Optional ElevenLabs voice ID for TTS"] = None,
) -> str:
    """Interrogate Suspect - Use when player wants to talk to a suspect.

    You MUST include in your request:
    1) Suspect's name
    2) Their FULL profile including:
       - Static info: role, personality, alibi, secret, what they know, isGuilty
       - EMOTIONAL STATE: trust %, nervousness %, contradictions caught
       - CONVERSATION HISTORY: all previous exchanges with this suspect
       - BEHAVIORAL INSTRUCTIONS: how to behave based on emotional state
    3) Player's question
    4) Optionally, their voice_id for audio generation
    
    The tool needs all this info to roleplay correctly and consistently."""

    logger.info("\n%s", "=" * 60)
    logger.info("INTERROGATE_SUSPECT TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("Player question: %s", player_question)
    logger.info("Profile length: %d chars", len(suspect_profile))
    logger.info("Voice ID: %s", voice_id)
    logger.info("%s\n", "=" * 60)

    llm = ChatOpenAI(
        model="gpt-4o", temperature=0.8, api_key=os.getenv("OPENAI_API_KEY")
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are roleplaying as a murder mystery suspect. Stay completely in character.

CORE RULES:
- Speak in first person AS this character
- Use their personality in how you speak
- Protect your secret unless pressed very hard
- If GUILTY: be evasive, deflect, give alibis, NEVER confess unless overwhelming evidence
- If INNOCENT: you don't know who did it, but share what you know if asked well
- NEVER break character or mention AI
- Keep responses VERY concise for voice: 1–3 sentences, maximum ~80 words total.
- If the player asks multiple things at once, answer the most important parts now and leave room for follow‑up questions later.
- The player might speak in any language, but you MUST ALWAYS answer in natural, fluent ENGLISH only

CONSISTENCY RULES (CRITICAL):
- Your profile includes CONVERSATION HISTORY - what you've said before to this detective
- You MUST be consistent with your previous statements unless deliberately lying
- If you contradict yourself, it should be subtle and due to nervousness, not carelessness
- Reference past conversations naturally: "As I told you before...", "I already mentioned..."

EMOTIONAL STATE RULES:
- Your profile includes EMOTIONAL STATE (trust %, nervousness %)
- Low trust (<30%): Be defensive, give short answers, act suspicious of the detective
- High trust (>70%): Be more open, consider sharing secrets if pressed
- High nervousness (>70%): Show stress - speak faster, fidget, might slip up
- If BEHAVIORAL INSTRUCTIONS are provided, follow them

Suspect Profile:
{suspect_profile}""",
            ),
            ("human", "Player says: {player_question}"),
        ]
    )

    chain = prompt | llm

    response = chain.invoke(
        {"suspect_profile": suspect_profile, "player_question": player_question}
    )

    text_response = response.content

    # Generate audio if voice_id is provided
    audio_path = None
    if voice_id:
        audio_path = generate_suspect_audio(text_response, voice_id, suspect_name)

    # Return response with audio path marker if audio was generated
    if audio_path:
        # Use a special marker that we can parse in app.py
        return f"[AUDIO:{audio_path}]{text_response}"

    return text_response


@tool
def describe_scene_for_image(
    location_name: Annotated[str, "Exact name of the location being searched"],
    clue_summary: Annotated[
        str,
        "Short summary of clues at this location and why it matters in the case",
    ],
    current_narration: Annotated[
        str,
        "What you (the Game Master) are about to narrate about this search action"
    ],
    previous_searches: Annotated[
        str,
        "Brief log of any previous searches at this location in this session (or empty string)"
    ],
    desired_view: Annotated[
        Optional[str],
        'Optional: hint about camera view, e.g. "inside briefcase", "outside door, down the hallway", "overhead".',
    ] = None,
) -> str:
    """Design a visual scene brief for a location image.

    Returns STRICT JSON with:
        - location_name: str (echo of the input location name)
        - environment_description: str (1-2 sentences describing the environment)
        - camera_position: str (e.g. "inside looking out", "outside wide shot", "overhead", etc.)
        - focal_objects: str (comma-separated list of key props/objects to emphasize)
        - prompt_hint: str (optional extra hint to pass directly to the image generator)

    The Game Master will:
        1. Use this brief to shape their spoken narration.
        2. Embed the JSON inside a [SCENE_BRIEF{...}] marker at the END of their response.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("DESCRIBE_SCENE_FOR_IMAGE TOOL CALLED")
    logger.info("Location: %s", location_name)
    logger.info("Desired view: %s", desired_view or "None")
    logger.info("%s\n", "=" * 60)

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a background concept artist and cinematic director for a 1990s point-and-click adventure game.

Your job is to design a SINGLE, clear visual brief for a location scene that will be used
for both narration and image generation.

CRITICAL:
- Focus primarily on the environment, but you MAY include people in the scene when it makes sense.
- Be explicit about how many people are clearly visible and where they are (e.g. "two technicians at the consoles",
  "one silhouetted figure in the doorway", or "no one is visible, the room is empty").
- Be very clear about whether the camera is OUTSIDE an object/room or INSIDE a confined space.
- Use the clue summary to pick the most important props, focal objects, and any characters that should appear.
- Keep everything consistent with the murder mystery tone and setting.

Return STRICT JSON ONLY with keys:
  "location_name": string (exactly the input location_name)
  "environment_description": string (1-2 vivid sentences describing the scene, including how many people are visible if any)
  "camera_position": string (e.g. "inside briefcase looking out over the desk",
                             "wide shot from doorway into the lab",
                             "close-up on control panel", "overhead view of the poker table")
  "focal_objects": string (comma-separated list of key objects to emphasize)
  "prompt_hint": string (optional extra hint for the image model, may repeat details)

Do NOT wrap JSON in markdown. Do NOT include any text before or after the JSON.
""",
            ),
            (
                "human",
                """LOCATION NAME:
{location_name}

CLUE SUMMARY (for this location):
{clue_summary}

CURRENT NARRATION (what you are about to say about this search):
{current_narration}

PREVIOUS SEARCHES AT THIS LOCATION (if any):
{previous_searches}

DESIRED VIEW (optional hint from game master):
{desired_view}

Design ONE scene brief and return ONLY the JSON object described above.""",
            ),
        ]
    )

    chain = prompt | llm
    result = chain.invoke(
        {
            "location_name": location_name,
            "clue_summary": clue_summary,
            "current_narration": current_narration,
            "previous_searches": previous_searches or "",
            "desired_view": desired_view or "",
        }
    )

    text_response = result.content.strip() if hasattr(result, "content") else str(result).strip()
    logger.info("Scene brief JSON (raw): %s", text_response[:300])
    return text_response


def enhance_text_for_speech(text: str) -> str:
    """Enhance text with capitalization for emphasis for more engaging speech.

    Uses capitalization and punctuation cues instead of emotional tags
    (which would be spoken). Voice settings handle emotional delivery.
    """
    enhanced = text

    # Don't add emotional tags - they get spoken! Instead, use:
    # - Capitalization for emphasis
    # - Voice settings for emotional delivery
    # - Natural text cues (exclamation marks, question marks)

    # Capitalize key dramatic words for emphasis
    dramatic_words = [
        "suddenly",
        "immediately",
        "finally",
        "quickly",
        "carefully",
        "silently",
        "slowly",
        "quietly",
    ]
    for word in dramatic_words:
        pattern = r"\b" + re.escape(word) + r"\b"
        enhanced = re.sub(pattern, word.upper(), enhanced, flags=re.IGNORECASE)

    return enhanced


def generate_suspect_audio(
    text: str, voice_id: str, suspect_name: str
) -> Optional[str]:
    """Generate audio for suspect response with alignment data.

    Args:
        text: The text to convert to speech
        voice_id: ElevenLabs voice ID
        suspect_name: Name of the suspect (for logging)

    Returns:
        Path to generated audio file, or None on error
        Also stores alignment data in _audio_alignment_cache
    """
    try:
        # Enhance text with capitalization for emphasis
        enhanced_text = enhance_text_for_speech(text)

        # Use services.tts_service to get audio with alignment data
        audio_path, alignment_data = text_to_speech(
            enhanced_text, voice_id=voice_id, speaker_name=suspect_name
        )

        if audio_path:
            # Store alignment data in cache for retrieval later
            _audio_alignment_cache[audio_path] = alignment_data
            if alignment_data:
                logger.info(
                    "Generated audio with %d word timestamps for %s: %s",
                    len(alignment_data),
                    suspect_name,
                    audio_path,
                )
            else:
                logger.info(
                    "Generated audio (no alignment data) for %s: %s",
                    suspect_name,
                    audio_path,
                )
            return audio_path
        else:
            logger.warning("Failed to generate audio for %s", suspect_name)
            return None

    except Exception as e:
        logger.error("Error generating audio: %s", e)
        return None


def get_audio_alignment_data(audio_path: str) -> Optional[list]:
    """Get alignment data for a tool-generated audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        Alignment data list or None if not found
    """
    return _audio_alignment_cache.get(audio_path)


# ============================================================================
# RAG-Powered Tools (Phase 2 AI Enhancements)
# ============================================================================


@tool
def search_past_statements(
    query: Annotated[str, "What to search for in past conversations"],
    suspect_name: Annotated[
        Optional[str],
        "Optional: filter to statements from a specific suspect"
    ] = None,
) -> str:
    """Search all past conversations for relevant statements.
    
    Use this tool when:
    - Player references something a suspect said earlier
    - You need to check what was discussed about a topic
    - Reconstructing a timeline of events based on testimony
    - Player asks "didn't [suspect] say something about...?"
    
    Returns relevant past statements from the game's memory.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("SEARCH_PAST_STATEMENTS TOOL CALLED")
    logger.info("Query: %s", query)
    logger.info("Suspect filter: %s", suspect_name or "None (all suspects)")
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No past conversations indexed yet. This is the first interrogation."
    
    try:
        if suspect_name:
            results = memory.search_by_suspect(suspect_name, query, k=5)
        else:
            results = memory.search(query, k=5, filter_type="conversation")
        
        if not results:
            if suspect_name:
                return f"No relevant statements found from {suspect_name}."
            return "No relevant statements found in past conversations."
        
        # Format results for the Game Master
        formatted = []
        for text, metadata in results:
            turn = metadata.get("turn", "?")
            speaker = metadata.get("suspect", "Unknown")
            formatted.append(f"[Turn {turn}] {speaker}: {text}")
        
        response = "Found the following relevant statements:\n\n" + "\n\n".join(formatted)
        logger.info("[RAG] search_past_statements returned %d results", len(results))
        return response
        
    except Exception as e:
        logger.error("[RAG] search_past_statements failed: %s", e)
        return "Error searching past statements. Please try again."


@tool
def find_contradictions(
    suspect_name: Annotated[str, "Name of the suspect to check"],
    new_statement: Annotated[str, "The suspect's new statement to check for contradictions"],
) -> str:
    """Check if a suspect's new statement contradicts their past statements.
    
    Use this tool when:
    - A suspect says something that might conflict with earlier testimony
    - Player accuses a suspect of lying
    - You want to verify consistency before proceeding
    
    Returns analysis of potential contradictions.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("FIND_CONTRADICTIONS TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("New statement: %s", new_statement[:100] + "..." if len(new_statement) > 100 else new_statement)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No past statements to compare against. This appears to be the suspect's first interrogation."
    
    try:
        # Find semantically similar past statements
        past_statements = memory.find_related_statements(suspect_name, new_statement, k=3)
        
        if not past_statements:
            return f"No previous statements from {suspect_name} found to compare against."
        
        # Use LLM to analyze for contradictions
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are analyzing testimony for contradictions in a murder mystery.
                
Compare the NEW STATEMENT against PAST STATEMENTS from the same suspect.
Identify any contradictions, inconsistencies, or suspicious changes in story.

Be specific about what contradicts what. Consider:
- Timeline inconsistencies
- Changed details (locations, times, people present)
- Contradictory claims about knowledge or actions
- Suspicious omissions or additions

If there's no contradiction, say so clearly."""
            ),
            (
                "human",
                """SUSPECT: {suspect_name}

NEW STATEMENT:
{new_statement}

PAST STATEMENTS:
{past_statements}

Analyze for contradictions:"""
            )
        ])
        
        chain = prompt | llm
        result = chain.invoke({
            "suspect_name": suspect_name,
            "new_statement": new_statement,
            "past_statements": "\n\n".join(past_statements)
        })
        
        analysis = result.content
        logger.info("[RAG] Contradiction analysis complete for %s", suspect_name)
        return analysis
        
    except Exception as e:
        logger.error("[RAG] find_contradictions failed: %s", e)
        return "Error analyzing contradictions. Please try again."


@tool
def get_cross_references(
    about_suspect: Annotated[str, "Name of the suspect you want to know about"],
) -> str:
    """Find what OTHER suspects have said about a specific suspect.
    
    Use this tool when:
    - Player wants to confront a suspect with what others said about them
    - You need to find alibis or accusations from other suspects
    - Building a case by cross-referencing testimony
    
    Returns statements from other suspects mentioning this person.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("GET_CROSS_REFERENCES TOOL CALLED")
    logger.info("About suspect: %s", about_suspect)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    if not memory.is_available:
        return "No cross-references available yet. Need more conversations first."
    
    try:
        cross_refs = memory.search_cross_references(about_suspect, k=5)
        
        if not cross_refs:
            return f"No other suspects have mentioned {about_suspect} yet."
        
        # Format for Game Master
        formatted = []
        for speaker, statement in cross_refs:
            formatted.append(f"• {speaker} said: {statement}")
        
        response = f"What others have said about {about_suspect}:\n\n" + "\n\n".join(formatted)
        logger.info("[RAG] Found %d cross-references about %s", len(cross_refs), about_suspect)
        return response
        
    except Exception as e:
        logger.error("[RAG] get_cross_references failed: %s", e)
        return "Error finding cross-references. Please try again."


@tool
def get_investigation_hint(
    current_situation: Annotated[str, "Brief description of where the player is stuck or what they're trying to figure out"],
) -> str:
    """Provide a hint to help the player progress in their investigation.
    
    Use this tool when:
    - Player explicitly asks for a hint or help
    - Player seems stuck and doesn't know what to do next
    - Player asks "what should I do?" or similar
    
    The hint will be based on what hasn't been explored yet and what
    evidence might be relevant.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("GET_INVESTIGATION_HINT TOOL CALLED")
    logger.info("Situation: %s", current_situation)
    logger.info("%s\n", "=" * 60)
    
    memory = get_game_memory()
    
    # Gather investigation status from memory
    hints = []
    
    # Check what's been covered
    total_docs = len(memory.documents) if memory.is_available else 0
    conversations = [d for d in memory.documents if d.get("metadata", {}).get("type") == "conversation"] if memory.is_available else []
    
    suspects_talked = set()
    for doc in conversations:
        suspect = doc.get("metadata", {}).get("suspect")
        if suspect:
            suspects_talked.add(suspect)
    
    # Generate contextual hints
    if total_docs == 0:
        hints.append("The detective hasn't gathered any testimony yet. Consider talking to the suspects to learn about the victim and their relationships.")
    elif len(suspects_talked) < 2:
        hints.append(f"Only {len(suspects_talked)} suspect(s) have been interviewed. Talking to more suspects might reveal conflicting stories or new leads.")
    
    # If RAG is available, search for unresolved threads
    if memory.is_available and total_docs > 0:
        try:
            # Look for mentions of unverified claims
            unverified = memory.search("alibi claimed said they were", k=3, filter_type="conversation")
            if unverified:
                hints.append("Some alibis mentioned in testimony could be verified by questioning other suspects or searching locations.")
            
            # Look for relationship hints
            relationships = memory.search("relationship secret affair argument fight", k=2, filter_type="conversation")
            if relationships:
                hints.append("There are hints about relationships between suspects that might be worth exploring further.")
        except Exception as e:
            logger.warning("[HINT] RAG search failed: %s", e)
    
    if not hints:
        hints.append("Consider searching locations you haven't explored yet, or pressing suspects on inconsistencies in their stories.")
    
    return "INVESTIGATION HINTS:\n\n• " + "\n• ".join(hints)


def get_all_tools() -> List:
    """Get all tools for the game master agent.
    
    Returns a list of all available tools, including RAG tools if available.
    """
    tools = [interrogate_suspect, describe_scene_for_image]
    
    # Add RAG tools if memory is available
    memory = get_game_memory()
    if memory.is_available:
        tools.extend([
            search_past_statements,
            find_contradictions,
            get_cross_references,
            get_investigation_hint,
        ])
        logger.info("[TOOLS] RAG tools enabled (including hint system)")
    else:
        # Still add hint tool even without RAG - it provides basic guidance
        tools.append(get_investigation_hint)
        logger.info("[TOOLS] RAG tools disabled, basic hint system enabled")
    
    return tools
