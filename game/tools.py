"""Tools for the game master agent."""

import json
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
    suspect_name: Annotated[str, "The full name of the suspect to interrogate"],
    player_question: Annotated[str, "The player's question or statement to the suspect"],
    emotional_context: Annotated[
        str,
        "Current emotional state and conversation history: trust %, nervousness %, past exchanges"
    ] = "",
) -> str:
    """Interrogate Suspect - Use when player wants to talk to a suspect.
    
    Just provide:
    1) suspect_name - full name (the tool looks up their secrets internally)
    2) player_question - what the player said
    3) emotional_context - current trust/nervousness and conversation history
    
    The tool has secure access to suspect secrets and will roleplay correctly.
    You do NOT need to include secrets or guilt - the tool handles that privately."""

    logger.info("\n%s", "=" * 60)
    logger.info("INTERROGATE_SUSPECT TOOL CALLED")
    logger.info("Suspect: %s", suspect_name)
    logger.info("Player question: %s", player_question)
    logger.info("Emotional context: %s", emotional_context[:200] if emotional_context else "None")
    logger.info("%s\n", "=" * 60)
    
    # Look up suspect from game state (secure access to hidden info)
    from game.state_manager import get_game_state
    state = get_game_state()
    
    suspect = None
    voice_id = None
    if state and state.mystery:
        for s in state.mystery.suspects:
            if s.name.lower() == suspect_name.lower() or suspect_name.lower() in s.name.lower():
                suspect = s
                voice_id = s.voice_id
                break
    
    if not suspect:
        logger.warning("Suspect not found: %s", suspect_name)
        return f"I'm sorry, I couldn't find a suspect named {suspect_name}."
    
    # Build the FULL profile internally (including secrets the GM shouldn't narrate)
    full_profile = f"""
Name: {suspect.name}
Role: {suspect.role}
Personality: {suspect.personality}
Alibi: "{suspect.alibi}"
Secret (protect this): {suspect.secret}
Info to share if trust is high: {suspect.clue_they_know}
Guilty: {suspect.isGuilty}
{"Murder details (NEVER confess): Used " + state.mystery.weapon + " because " + state.mystery.motive if suspect.isGuilty else ""}

{emotional_context}
"""

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
- Low trust (<30%): Be defensive, give short answers, act suspicious of the detective
- High trust (>70%): Be more open, consider sharing your "info to share" if pressed
- High nervousness (>70%): Show stress - speak faster, fidget, might slip up

Suspect Profile:
{suspect_profile}""",
            ),
            ("human", "Player says: {player_question}"),
        ]
    )

    chain = prompt | llm

    response = chain.invoke(
        {"suspect_profile": full_profile, "player_question": player_question}
    )

    text_response = response.content

    # Generate audio if voice_id is available
    audio_path = None
    if voice_id:
        audio_path = generate_suspect_audio(text_response, voice_id, suspect.name)

    # Return response with audio path marker if audio was generated
    if audio_path:
        # Use a special marker that we can parse in app.py
        return f"[AUDIO:{audio_path}]{text_response}"

    return text_response


@tool
def describe_scene_for_image(
    location_name: Annotated[str, "Name of the location being searched (matches a SEARCHABLE LOCATION)"],
) -> str:
    """Search a location and reveal what the detective finds there.

    Just provide the location_name - the tool looks up clue details internally.
    
    The image will focus on the CLUE ITSELF (not just the location):
    - Close-up for documents, objects, and traces
    - Wide shot only for environment/scene clues
    
    Returns narration + [SCENE_BRIEF{...}] marker for image generation.
    Also includes [SEARCHED:location] and [CLUE_FOUND:id] markers.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("DESCRIBE_SCENE_FOR_IMAGE TOOL CALLED")
    logger.info("Location: %s", location_name)
    logger.info("%s\n", "=" * 60)
    
    # Look up clue from game state (secure access)
    from game.state_manager import get_game_state
    state = get_game_state()
    
    clue = None
    clue_description = "an empty area"
    clue_id = None
    clue_type = "environment"
    # Use exact clue location for consistent image mapping
    exact_location = location_name
    
    if state and state.mystery:
        # Find matching clue by location (fuzzy match)
        location_lower = location_name.lower()
        for c in state.mystery.clues:
            if c.location.lower() in location_lower or location_lower in c.location.lower():
                clue = c
                clue_description = c.description
                clue_id = c.id
                # Use the EXACT clue location name for consistent caching
                exact_location = c.location
                # Infer clue type from description
                desc_lower = c.description.lower()
                if any(w in desc_lower for w in ["letter", "note", "document", "paper", "file", "email", "message"]):
                    clue_type = "document"
                elif any(w in desc_lower for w in ["blood", "stain", "fingerprint", "footprint", "residue", "mark"]):
                    clue_type = "trace"
                elif any(w in desc_lower for w in ["room", "scene", "area", "space", "position"]):
                    clue_type = "environment"
                else:
                    clue_type = "object"
                logger.info("Matched location '%s' -> exact clue location '%s'", location_name, exact_location)
                break
    
    logger.info("Found clue: %s (type: %s) at '%s'", clue_id or "none", clue_type, exact_location)
    
    # Determine optimal camera angle based on clue type
    camera_guidance = {
        "document": "extreme close-up, document filling frame, dramatic lighting from above",
        "object": "close-up on the object, shallow depth of field, mysterious lighting",
        "trace": "macro close-up, forensic detail visible, stark lighting",
        "environment": "wide establishing shot, atmospheric, the scene tells a story"
    }
    suggested_camera = camera_guidance.get(clue_type, camera_guidance["object"])

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a Game Master narrator + concept artist for a murder mystery game.

Your job is to:
1. Write SHORT spoken narration (2-3 sentences, ~50 words) about finding the CLUE
2. Design an image brief that FOCUSES ON THE CLUE, not the location

IMAGE COMPOSITION RULES:
- The CLUE is the HERO of the image - it should be the visual focus
- The location provides atmospheric BACKGROUND, not the main subject
- Use the suggested camera angle for this clue type
- Think like a film director: what shot reveals this evidence dramatically?

CAMERA ANGLE GUIDANCE:
- DOCUMENT clues: Extreme close-up, text partially visible, dramatic top lighting
- OBJECT clues: Close-up with shallow depth of field, object isolated, moody lighting  
- TRACE clues: Macro/forensic style, details crisp, clinical lighting
- ENVIRONMENT clues: Wide shot, room tells a story, atmospheric

NARRATION RULES:
- ALWAYS write in ENGLISH
- Focus on the DISCOVERY moment - what the detective notices
- Be atmospheric but brief
- Write in second person ("You notice...", "Something catches your eye...")

Return STRICT JSON ONLY:
  "spoken_narration": string (2-3 sentences about finding this clue)
  "location_name": string (for background context)
  "clue_focus": string (what the image should focus on - the clue itself)
  "camera_angle": string (specific shot type: close-up, macro, wide, etc.)
  "lighting_mood": string (dramatic, forensic, atmospheric, etc.)
  "background_hint": string (location details visible in background, blurred)
  "prompt_hint": string (additional image generation hints)

Do NOT wrap JSON in markdown. Return ONLY the JSON object.
""",
            ),
            (
                "human",
                """LOCATION (background): {location_name}

CLUE FOUND (image focus): {clue_description}

CLUE TYPE: {clue_type}

SUGGESTED CAMERA: {suggested_camera}

PREVIOUS SEARCHES: {previous_searches}

Design an image that dramatically reveals this CLUE with the location as background context.""",
            ),
        ]
    )

    chain = prompt | llm
    result = chain.invoke(
        {
            "location_name": exact_location,  # Use exact clue location for consistent mapping
            "clue_description": clue_description,
            "clue_type": clue_type,
            "suggested_camera": suggested_camera,
            "previous_searches": "",  # Could be enhanced to check state.searched_locations
        }
    )

    raw_json = result.content.strip() if hasattr(result, "content") else str(result).strip()
    logger.info("Scene brief JSON (raw): %s", raw_json[:300])

    # Parse JSON to extract spoken_narration and build the final output
    try:
        data = json.loads(raw_json)
        spoken = data.get("spoken_narration", "").strip()
        
        # Build scene brief focused on the CLUE (not just the location)
        # Use exact_location for consistent image cache mapping
        scene_brief = {
            "location_name": exact_location,  # Exact clue location for cache consistency
            "clue_focus": data.get("clue_focus", clue_description),
            "camera_angle": data.get("camera_angle", suggested_camera),
            "lighting_mood": data.get("lighting_mood", "dramatic"),
            "background_hint": data.get("background_hint", ""),
            "prompt_hint": data.get("prompt_hint", ""),
        }
        scene_json = json.dumps(scene_brief)
        
        # Build output with all necessary markers (use exact_location for consistency)
        markers = [f"[SEARCHED:{exact_location}]"]
        if clue_id:
            markers.append(f"[CLUE_FOUND:{clue_id}]")
        
        # Return spoken narration + markers + scene brief marker
        output = f"{spoken}\n\n{' '.join(markers)}\n[SCENE_BRIEF{scene_json}]"
        logger.info("Scene tool output: spoken=%d chars, clue=%s", len(spoken), clue_id or "none")
        return output
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse scene brief JSON: %s", e)
        # Fallback with basic markers (use exact_location for consistency)
        markers = f"[SEARCHED:{exact_location}]"
        if clue_id:
            markers += f" [CLUE_FOUND:{clue_id}]"
        return f"You search {exact_location} carefully. {markers}"


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


@tool
def make_accusation(
    suspect_name: Annotated[str, "The full name of the suspect being accused of the murder"],
    evidence_summary: Annotated[str, "Brief summary of evidence or reasoning the player cited"] = "",
) -> str:
    """Make Accusation - Use when the player accuses a suspect of being the murderer.
    
    Call this tool when the player says things like:
    - "I accuse X of the murder"
    - "X is the killer" / "X did it"
    - "I think X is the murderer"
    - "It was X all along"
    - "X must be guilty"
    
    This tool:
    1. Checks if the accusation is correct against the actual murderer
    2. Updates the game state (wrong accusations count, win/lose)
    3. Returns a dramatic response for the Game Master to deliver
    
    IMPORTANT: Only call this for FINAL ACCUSATIONS, not casual suspicions.
    If the player is just theorizing, respond conversationally instead.
    """
    logger.info("\n" + "=" * 60)
    logger.info("🎯 MAKE_ACCUSATION TOOL CALLED")
    logger.info("Accused: %s", suspect_name)
    logger.info("Evidence: %s", evidence_summary[:200] if evidence_summary else "None cited")
    logger.info("=" * 60 + "\n")
    
    # Generate dramatic accusation response with marker for parser
    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.8, 
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are the Game Master for a murder mystery game. The player has made a FORMAL ACCUSATION.

Generate a DRAMATIC response that:
1. Acknowledges their accusation with gravitas
2. References any evidence they provided
3. Builds tension before the reveal
4. Ends on a cliffhanger (the actual result will be shown by the game)

Keep it SHORT (2-3 sentences) for voice narration. Be theatrical!

CRITICAL: You MUST include this exact marker in your response: [ACCUSATION:{suspect_name}]
This marker is how the game system tracks the accusation. Put it at the start of your response."""),
        ("human", """Player formally accuses: {suspect_name}
Their reasoning: {evidence}

Generate the dramatic Game Master response. Start with the [ACCUSATION:{suspect_name}] marker.""")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "suspect_name": suspect_name,
        "evidence": evidence_summary or "Gut instinct - no specific evidence cited"
    })
    
    result = response.content.strip()
    
    # Ensure the accusation marker is present (failsafe)
    marker = f"[ACCUSATION:{suspect_name}]"
    if marker not in result and "[ACCUSATION:" not in result:
        result = f"{marker} {result}"
    
    logger.info("Accusation response generated: %s...", result[:150])
    return result


def get_all_tools() -> List:
    """Get all tools for the game master agent.
    
    Returns a list of all available tools, including RAG tools if available.
    """
    tools = [interrogate_suspect, describe_scene_for_image, make_accusation]
    
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
