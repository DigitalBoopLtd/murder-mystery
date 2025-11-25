"""Parse game actions from user messages and AI responses."""

import logging
import re
from typing import Optional, Tuple, List
from game_state import GameState

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
    # Check if the response mentions any clue descriptions
    found_clues = find_clues_in_response(response_lower, state)
    for clue_id, clue_desc in found_clues:
        state.add_clue(clue_id, clue_desc)
        actions["clues_found"].append(clue_desc)
        logger.info(f"🔍 Detected clue found: {clue_id}")

    # === DETECT ACCUSATIONS ===
    accusation_keywords = [
        "i accuse ",
        "the murderer is ",
        "the killer is ",
        "it was ",
        "guilty is ",
        "did it is ",
        "committed the murder",
        "is the murderer",
        "is the killer",
        "killed ",
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
                if any(ind in response_lower for ind in rejection_indicators):
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

    return None


def find_clues_in_response(
    response_lower: str, state: GameState
) -> List[Tuple[str, str]]:
    """Find clue revelations in the AI response.

    Returns list of (clue_id, clue_description) tuples.
    """
    if not state.mystery:
        return []

    found_clues = []

    for clue in state.mystery.clues:
        # Skip clues already found
        if clue.id in state.clue_ids_found:
            continue

        clue_desc_lower = clue.description.lower()

        # Check for significant portions of the clue description (at least 20 chars)
        # This helps detect when the GM narratively reveals a clue
        desc_words = clue_desc_lower.split()

        # Look for sequences of 3+ consecutive words from the description
        for i in range(len(desc_words) - 2):
            phrase = " ".join(desc_words[i : i + 3])
            if phrase in response_lower:
                found_clues.append((clue.id, clue.description))
                break

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
