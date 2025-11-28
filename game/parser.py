"""Parse game actions from user messages and AI responses."""

import logging
import os
import re
from typing import Optional, Tuple, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from game.state import GameState

logger = logging.getLogger(__name__)


def parse_game_actions(user_message: str, response: str, state: GameState) -> dict:
    """Parse user message and AI response to update game state.

    Detects:
    - Suspect interrogations (updates suspects_talked_to)
    - Location searches (updates searched_locations)
    - Clue discoveries (updates clues_found)
    - Accusations (updates wrong_accusations, game_over, won)

    Args:
        user_message: The player's message
        response: The AI's response
        state: Current game state

    Returns:
        Dict with actions detected: {
            'suspect_talked_to': str or None,
            'location_searched': str or None,
            'clues_found': list of clue descriptions,
            'accusation_made': str or None,
            'accusation_correct': bool or None
        }
    """
    if not state.mystery:
        return {}

    actions = {
        "suspect_talked_to": None,
        "location_searched": None,
        "clues_found": [],
        "accusation_made": None,
        "accusation_correct": None,
    }

    message_lower = user_message.lower()
    response_lower = response.lower()

    # === DETECT SUSPECT INTERROGATION ===
    talk_keywords = [
        "talk to",
        "speak to",
        "speak with",
        "talk with",
        "ask ",
        "question ",
        "interrogate ",
        "interview ",
        "confront ",
        "approach ",
    ]

    if any(kw in message_lower for kw in talk_keywords):
        suspect_name = find_suspect_in_message(message_lower, state)
        if suspect_name:
            state.add_suspect_talked_to(suspect_name)
            actions["suspect_talked_to"] = suspect_name
            logger.info(f"🎭 Detected interrogation of: {suspect_name}")

    # === DETECT LOCATION SEARCH ===
    search_keywords = [
        "search ",
        "investigate ",
        "examine ",
        "look at ",
        "look in ",
        "look around ",
        "check ",
        "inspect ",
        "explore ",
        "go to ",
        "visit ",
    ]

    if any(kw in message_lower for kw in search_keywords):
        location = find_location_in_message(message_lower, state)
        if location:
            state.add_searched_location(location)
            actions["location_searched"] = location
            logger.info(f"📍 Detected search of: {location}")

    # === DETECT CLUE DISCOVERIES ===
    # Only mark clues as found when a location has been searched
    # and the searched location matches the clue's location
    if actions.get("location_searched"):
        searched_location = actions["location_searched"]
        found_clues = find_clues_in_response_for_location(
            response_lower, state, searched_location
        )
        for clue_id, clue_desc in found_clues:
            state.add_clue(clue_id, clue_desc)
            actions["clues_found"].append(clue_desc)
            logger.info(f"🔍 Detected clue found: {clue_id} at {searched_location}")
        
        # Debug: log if location was searched but no clues found
        if not found_clues and state.mystery:
            logger.debug(
                f"📍 Location '{searched_location}' searched but no clues detected. "
                f"Available clue locations: {[c.location for c in state.mystery.clues]}"
            )

    # === DETECT ACCUSATIONS ===
    accusation_keywords = [
        "i accuse ",
        "accuse ",
        "accused ",
        "accusing ",
        "the murderer is ",
        "the killer is ",
        "it was ",
        "guilty is ",
        "did it is ",
        "committed the murder",
        "is the murderer",
        "is the killer",
        "killed ",
        "of the murder",
        "is guilty",
        "did it",
    ]

    if any(kw in message_lower for kw in accusation_keywords):
        accused = find_suspect_in_message(message_lower, state)
        if accused:
            actions["accusation_made"] = accused

            # Check if accusation is correct
            if accused.lower() == state.mystery.murderer.lower():
                # Check if response indicates acceptance (has evidence)
                acceptance_indicators = [
                    "correct",
                    "right",
                    "solved",
                    "guilty",
                    "congratulations",
                    "well done",
                    "case closed",
                    "identified the murderer",
                    "found the killer",
                ]
                if any(ind in response_lower for ind in acceptance_indicators):
                    state.won = True
                    state.game_over = True
                    actions["accusation_correct"] = True
                    logger.info(f"🎉 Correct accusation! Game won!")
                else:
                    # Correct person but no evidence - still needs evidence
                    logger.info(f"🎯 Correct suspect accused but may need evidence")
            else:
                # Wrong accusation
                rejection_indicators = [
                    "wrong",
                    "incorrect",
                    "not the",
                    "innocent",
                    "no evidence",
                    "try again",
                    "not guilty",
                ]
                # For wrong accusations, always increment if it's the wrong person
                # Don't require rejection indicators - if they accused wrong person, it's wrong
                state.wrong_accusations += 1
                actions["accusation_correct"] = False
                logger.info(
                    f"❌ Wrong accusation! Count: {state.wrong_accusations}/3"
                )

                if state.wrong_accusations >= 3:
                    state.game_over = True
                    logger.info(f"💀 Game over - too many wrong accusations")

    return actions


def find_suspect_in_message(message_lower: str, state: GameState) -> Optional[str]:
    """Find a suspect name in the message.

    Handles partial name matches (first name, last name, or full name).
    """
    if not state.mystery:
        return None

    for suspect in state.mystery.suspects:
        suspect_name = suspect.name
        name_lower = suspect_name.lower()

        # Check for full name
        if name_lower in message_lower:
            return suspect_name

        # Check for individual name parts
        name_parts = name_lower.split()
        for part in name_parts:
            # Skip very short parts (like "Dr." or "Jr.")
            if len(part) > 2 and part in message_lower:
                # Make sure it's a word boundary (not part of another word)
                pattern = rf"\b{re.escape(part)}\b"
                if re.search(pattern, message_lower):
                    return suspect_name

    return None


def find_location_in_message(message_lower: str, state: GameState) -> Optional[str]:
    """Find a location name in the message."""
    if not state.mystery:
        return None

    locations = state.get_available_locations()

    # ---------- FAST HEURISTIC MATCHING ----------
    for location in locations:
        location_lower = location.lower()

        # Check for exact location name
        if location_lower in message_lower:
            return location

        # Check for key words in location name
        # e.g., "Captain's Quarters" -> check for "captain" or "quarters"
        location_words = location_lower.split()
        for word in location_words:
            # Skip common words
            if word in ["the", "a", "an", "of", "in", "at", "on", "'s"]:
                continue
            if len(word) > 3 and word in message_lower:
                # Make sure it's a word boundary
                pattern = rf"\b{re.escape(word)}\b"
                if re.search(pattern, message_lower):
                    return location

    # ---------- HYBRID FALLBACK: SMALL LLM RESOLVER ----------
    if not locations:
        return None

    try:
        llm = ChatOpenAI(
            model=os.getenv("LOCATION_RESOLVER_MODEL", "gpt-4o-mini"),
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        locations_summary = "\n".join(f"- {loc}" for loc in locations)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You map a player's message to ONE location from a list.\n"
                        "You MUST answer with exactly one location name from the list, "
                        "or the word NONE if no location clearly matches.\n"
                        "Do not add any explanation."
                    ),
                ),
                (
                    "human",
                    (
                        "Locations:\n"
                        "{location_list}\n\n"
                        "Player message:\n"
                        "{player_message}\n\n"
                        "Answer with exactly one location name from the list above, "
                        "or NONE if you are not sure."
                    ),
                ),
            ]
        )

        chain = prompt | llm
        result = chain.invoke(
            {
                "location_list": locations_summary,
                "player_message": message_lower,
            }
        )
        choice = (getattr(result, "content", "") or "").strip()
        first_line = choice.splitlines()[0].strip()
        # Strip bullets or quotes if present
        first_line = first_line.lstrip("-• ").strip().strip('"').strip("'")

        if first_line and first_line.upper() != "NONE":
            for loc in locations:
                if loc.lower() == first_line.lower():
                    logger.info(
                        "AI-resolved location mention: %s (from '%s')",
                        loc,
                        message_lower,
                    )
                    return loc

            logger.info(
                "AI location resolver returned '%s', which did not match any known location",
                first_line,
            )
        else:
            logger.info(
                "AI location resolver chose NONE for message: %s", message_lower
            )
    except Exception:
        logger.exception(
            "Error resolving location via AI; falling back to heuristics only"
        )

    return None


def find_clues_in_response_for_location(
    response_lower: str, state: GameState, searched_location: str
) -> List[Tuple[str, str]]:
    """Find clue revelations in the AI response for a specific searched location.

    Only returns clues that:
    1. Are at the searched location
    2. Have not been found yet
    3. Are mentioned in the response

    Args:
        response_lower: The AI response in lowercase
        state: Current game state
        searched_location: The location that was searched

    Returns:
        List of (clue_id, clue_description) tuples.
    """
    if not state.mystery:
        return []

    found_clues = []
    searched_location_lower = searched_location.lower()

    for clue in state.mystery.clues:
        # Skip clues already found
        if clue.id in state.clue_ids_found:
            continue

        # Only check clues at the searched location
        clue_location_lower = clue.location.lower()
        
        # Check if the searched location matches the clue's location
        # First try exact match (normalized)
        location_matches = (
            clue_location_lower == searched_location_lower
            or clue_location_lower in searched_location_lower
            or searched_location_lower in clue_location_lower
        )
        
        # If no exact match, try word-based matching for variations
        # e.g., "Beneath Zara Orion's bed" vs "Zara Orion's bed"
        if not location_matches:
            # Extract meaningful words (skip common words and short words)
            clue_words = {
                word.strip(".,!?;:'\"")
                for word in clue_location_lower.split()
                if len(word.strip(".,!?;:'\"")) > 3
                and word.strip(".,!?;:'\"") not in ["the", "a", "an", "of", "in", "at", "on"]
            }
            searched_words = {
                word.strip(".,!?;:'\"")
                for word in searched_location_lower.split()
                if len(word.strip(".,!?;:'\"")) > 3
                and word.strip(".,!?;:'\"") not in ["the", "a", "an", "of", "in", "at", "on"]
            }
            # Match if most meaningful words overlap
            if clue_words and searched_words:
                overlap = clue_words & searched_words
                # Match if at least 50% of words overlap or if there's significant overlap
                location_matches = (
                    len(overlap) >= min(2, len(clue_words), len(searched_words))
                    or len(overlap) / max(len(clue_words), len(searched_words)) >= 0.5
                )

        if not location_matches:
            continue

        clue_desc_lower = clue.description.lower()

        # Check for significant portions of the clue description
        # This helps detect when the GM narratively reveals a clue
        desc_words = clue_desc_lower.split()

        # Look for sequences of 3+ consecutive words from the description
        phrase_found = False
        for i in range(len(desc_words) - 2):
            phrase = " ".join(desc_words[i : i + 3])
            if phrase in response_lower:
                phrase_found = True
                break

        # If no 3-word phrase found, try 2-word phrases (more flexible)
        if not phrase_found and len(desc_words) >= 2:
            for i in range(len(desc_words) - 1):
                phrase = " ".join(desc_words[i : i + 2])
                # Only use 2-word phrases if they're meaningful (not common words)
                common = ["the", "a", "an", "of", "in", "at", "on", "to", "for"]
                if len(phrase) > 8 and phrase not in common:
                    if phrase in response_lower:
                        phrase_found = True
                        break

        # Extract key words (nouns, names, important terms) for flexible matching
        stop_words = {
            "the", "a", "an", "of", "in", "at", "on", "to", "for",
            "with", "from", "about", "that", "this", "these", "those",
        }
        key_words = [
            word.strip(".,!?;:'\"")
            for word in desc_words
            if len(word.strip(".,!?;:'\"")) > 4
            and word.strip(".,!?;:'\"") not in stop_words
        ]

        # Also check for key entities: extract important nouns/names from clue description
        # and see if they appear together in the response
        if not phrase_found and len(key_words) >= 2:
            # Check if at least 2 key words from the clue appear in the response
            matches = sum(1 for word in key_words if word in response_lower)
            # If at least 2 key words match, consider it found
            if matches >= 2:
                phrase_found = True

        # If still no match, but response suggests discovery, try lenient matching
        if not phrase_found and len(key_words) >= 1:
            discovery_keywords = [
                "find", "discover", "notice", "see", "read", "unfold",
                "letter", "document", "note", "paper", "envelope",
                "evidence", "threat", "threatening", "accus", "court",
            ]
            has_discovery = any(kw in response_lower for kw in discovery_keywords)
            
            if has_discovery:
                # Discovery language + 1 key word = found
                matches = sum(1 for word in key_words if word in response_lower)
                if matches >= 1:
                    phrase_found = True

        if phrase_found:
            found_clues.append((clue.id, clue.description))

        # Also check for the clue ID being mentioned
        if clue.id.lower() in response_lower:
            if (clue.id, clue.description) not in found_clues:
                found_clues.append((clue.id, clue.description))

    return found_clues


def detect_game_end_in_response(response: str, state: GameState) -> Optional[str]:
    """Detect if the response indicates game end.

    Returns:
        'won' if player won
        'lost' if player lost
        None if game continues
    """
    if not state.mystery:
        return None

    response_lower = response.lower()

    # Win indicators
    win_phrases = [
        "congratulations",
        "you win",
        "case solved",
        "case closed",
        "correctly identified",
        "found the murderer",
        "justice is served",
        "well done, detective",
        "you've solved",
    ]

    # Loss indicators
    loss_phrases = [
        "game over",
        "you lose",
        "case remains unsolved",
        "run out of accusations",
        "three strikes",
        "failed to solve",
        "the murderer escapes",
        "justice was not served",
    ]

    for phrase in win_phrases:
        if phrase in response_lower:
            return "won"

    for phrase in loss_phrases:
        if phrase in response_lower:
            return "lost"

    return None
