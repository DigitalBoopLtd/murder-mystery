"""Mystery Oracle - The isolated truth authority.

This service is the ONLY place that knows the full mystery truth.
The player-facing Game Master agent CANNOT access this directly.

Instead, the Oracle provides LIMITED interfaces that:
1. Generate suspect responses (without exposing secrets to GM)
2. Validate alibis based on encounter graph
3. Check if player has enough evidence for accusations

The key insight: The GM agent gets the NARRATIVE RESPONSE from a suspect,
but it never sees the suspect's secrets, guilt status, or the encounter graph.

Architecture:
- MysteryOracle is initialized with the full Mystery + EncounterGraph
- interrogate_suspect tool calls Oracle.generate_suspect_response()
- Oracle internally knows the truth but only returns the roleplay response
- GM agent sees ONLY what the player would see (the response text)
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from game.models import Mystery, Suspect, SuspectState
from game.encounter_graph import EncounterGraph, TimeSlot

logger = logging.getLogger(__name__)


class SuspectResponseRequest(BaseModel):
    """Request to generate a suspect's response.
    
    This is what the GM agent passes to the Oracle.
    Note: It does NOT include secrets, guilt status, etc.
    """
    suspect_name: str
    player_question: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    trust_level: int = Field(default=50, ge=0, le=100)
    nervousness_level: int = Field(default=30, ge=0, le=100)
    contradictions_caught: int = Field(default=0)


class SuspectResponseResult(BaseModel):
    """Result from the Oracle's suspect response generation.
    
    This is what the GM agent receives back.
    Note: It does NOT expose the truth, only the roleplay result.
    """
    response_text: str = Field(description="The suspect's spoken response")
    trust_delta: int = Field(default=0, description="Change in trust (-10 to +10)")
    nervousness_delta: int = Field(default=0, description="Change in nervousness (-10 to +15)")
    revealed_location_hint: Optional[str] = Field(default=None)
    revealed_secret: bool = Field(default=False)
    # These are for game state updates, not shown to player
    caught_in_contradiction: bool = Field(default=False)


class MysteryOracle:
    """The isolated truth authority for the murder mystery.
    
    This is the ONLY service that has access to:
    - The full Mystery object (including murderer identity)
    - The EncounterGraph (who was actually where)
    - Suspect secrets and guilt status
    
    The Game Master agent NEVER sees this information directly.
    Instead, it queries the Oracle through controlled interfaces.
    """
    
    def __init__(self):
        self._mystery: Optional[Mystery] = None
        self._encounter_graph: Optional[EncounterGraph] = None
        self._suspect_states: Dict[str, SuspectState] = {}
        
    @property
    def is_initialized(self) -> bool:
        return self._mystery is not None
    
    def initialize(
        self,
        mystery: Mystery,
        encounter_graph: Optional[EncounterGraph] = None
    ):
        """Initialize the Oracle with the mystery truth.
        
        This should ONLY be called during game setup, never by the GM agent.
        """
        self._mystery = mystery
        self._encounter_graph = encounter_graph
        self._suspect_states = {
            s.name: SuspectState() for s in mystery.suspects
        }
        logger.info("[ORACLE] Initialized with mystery: %s suspects, murderer=%s",
                   len(mystery.suspects), mystery.murderer)
    
    def _get_suspect(self, name: str) -> Optional[Suspect]:
        """Internal: Get suspect by name."""
        if not self._mystery:
            return None
        for s in self._mystery.suspects:
            if s.name.lower() == name.lower() or name.lower() in s.name.lower():
                return s
        return None
    
    def _get_suspect_state(self, name: str) -> SuspectState:
        """Internal: Get or create suspect state."""
        if name not in self._suspect_states:
            self._suspect_states[name] = SuspectState()
        return self._suspect_states[name]
    
    def _should_reveal_location(
        self, 
        suspect: Suspect, 
        state: SuspectState
    ) -> Tuple[bool, str]:
        """Internal: Check if suspect should reveal their location hint.
        
        Murderer requires VERY high trust, innocents need high trust.
        """
        if not suspect.location_hint:
            return False, "no_location_hint"
        
        if suspect.isGuilty:
            threshold = 85
            if state.trust >= threshold:
                return True, f"murderer_trust_high ({state.trust}%)"
            return False, f"murderer_trust_low ({state.trust}%/{threshold}%)"
        else:
            threshold = 70
            if state.trust >= threshold:
                return True, f"trust_high ({state.trust}%)"
            return False, f"trust_low ({state.trust}%/{threshold}%)"
    
    def _should_reveal_secret(
        self,
        suspect: Suspect,
        state: SuspectState,
        player_question: str
    ) -> Tuple[bool, str]:
        """Internal: Check if suspect should reveal their secret.
        
        Murderer reveals under pressure (high nervousness + contradictions).
        Innocents reveal with high trust + probing questions.
        """
        if state.secret_revealed:
            return False, "already_revealed"
        
        question_lower = player_question.lower()
        probing_keywords = ["why", "motive", "reason", "relationship", "hate",
                          "secret", "hiding", "truth", "really", "feel about"]
        is_probing = any(kw in question_lower for kw in probing_keywords)
        
        if suspect.isGuilty:
            # Murderer cracks under pressure
            if state.nervousness >= 90 and state.contradictions_caught >= 2:
                return True, f"murderer_cracked (nervousness={state.nervousness}%, contradictions={state.contradictions_caught})"
            return False, f"murderer_holding ({state.nervousness}%/90%, {state.contradictions_caught}/2)"
        else:
            # Innocent reveals with trust + probing
            if state.trust >= 60 and is_probing:
                return True, f"trust_probing (trust={state.trust}%, probing={is_probing})"
            return False, f"innocent_holding (trust={state.trust}%/60%, probing={is_probing})"
    
    def _calculate_emotional_impact(
        self,
        suspect: Suspect,
        player_question: str
    ) -> Tuple[int, int]:
        """Calculate trust and nervousness changes based on question style."""
        question_lower = player_question.lower()
        trust_delta = 0
        nervousness_delta = 0
        
        # Aggressive language
        aggressive = ["liar", "lying", "killed", "murder", "guilty", "confess",
                     "admit", "truth", "suspicious", "caught", "you did it"]
        if any(w in question_lower for w in aggressive):
            trust_delta -= 5
            nervousness_delta += 10 if suspect.isGuilty else 5
        
        # Friendly language
        friendly = ["help", "understand", "sorry", "difficult", "appreciate", "thank"]
        if any(w in question_lower for w in friendly):
            trust_delta += 5
            nervousness_delta -= 5
        
        # Confrontation with evidence
        confrontation = ["but you said", "you told me", "earlier you", "contradict",
                        "doesn't match", "someone saw you", "witness"]
        if any(p in question_lower for p in confrontation):
            nervousness_delta += 15 if suspect.isGuilty else 5
        
        return trust_delta, nervousness_delta
    
    async def generate_suspect_response(
        self,
        request: SuspectResponseRequest
    ) -> SuspectResponseResult:
        """Generate a suspect's response to player interrogation.
        
        This is the CONTROLLED INTERFACE the GM agent uses.
        The GM sends the request, gets back ONLY the narrative response.
        The GM never sees the suspect's secrets or guilt status.
        
        Internally, the Oracle:
        1. Looks up the suspect's full profile (secrets, guilt)
        2. Checks the encounter graph for consistency
        3. Generates a response that protects or reveals secrets appropriately
        4. Returns ONLY the response text + emotional deltas
        """
        import time
        t_oracle_start = time.perf_counter()
        
        suspect = self._get_suspect(request.suspect_name)
        if not suspect:
            return SuspectResponseResult(
                response_text=f"I couldn't find anyone named {request.suspect_name}.",
                trust_delta=0,
                nervousness_delta=0,
            )
        
        state = self._get_suspect_state(suspect.name)
        
        # Update state with request's current values
        state.trust = request.trust_level
        state.nervousness = request.nervousness_level
        state.contradictions_caught = request.contradictions_caught
        
        # Calculate emotional impact
        trust_delta, nervousness_delta = self._calculate_emotional_impact(
            suspect, request.player_question
        )
        
        # Apply changes
        state.trust = max(0, min(100, state.trust + trust_delta))
        state.nervousness = max(0, min(100, state.nervousness + nervousness_delta))
        
        # Check reveals
        reveal_location, loc_reason = self._should_reveal_location(suspect, state)
        reveal_secret, secret_reason = self._should_reveal_secret(
            suspect, state, request.player_question
        )
        
        t_pre_llm = time.perf_counter()
        logger.info("[ORACLE] %s: trust=%d, nervousness=%d, reveal_loc=%s (%s), reveal_secret=%s (%s)",
                   suspect.name, state.trust, state.nervousness,
                   reveal_location, loc_reason, reveal_secret, secret_reason)
        logger.info("⏱️ [ORACLE PERF] Pre-LLM setup: %.0fms", (t_pre_llm - t_oracle_start) * 1000)
        
        # Build the prompt for response generation
        # NOTE: This is the ONLY place where secrets are used, and they stay here
        t_llm_start = time.perf_counter()
        response_text = await self._generate_roleplay_response(
            suspect=suspect,
            state=state,
            player_question=request.player_question,
            conversation_history=request.conversation_history,
            should_reveal_location=reveal_location,
            should_reveal_secret=reveal_secret,
        )
        t_llm_end = time.perf_counter()
        logger.info("⏱️ [ORACLE PERF] LLM call (_generate_roleplay_response): %.0fms", (t_llm_end - t_llm_start) * 1000)
        
        # Mark secret as revealed if it was
        if reveal_secret:
            state.secret_revealed = True
        
        t_oracle_end = time.perf_counter()
        logger.info("⏱️ [ORACLE PERF] Total Oracle time: %.0fms", (t_oracle_end - t_oracle_start) * 1000)
        
        return SuspectResponseResult(
            response_text=response_text,
            trust_delta=trust_delta,
            nervousness_delta=nervousness_delta,
            revealed_location_hint=suspect.location_hint if reveal_location else None,
            revealed_secret=reveal_secret,
            caught_in_contradiction=False,  # TODO: detect from response
        )
    
    async def _generate_roleplay_response(
        self,
        suspect: Suspect,
        state: SuspectState,
        player_question: str,
        conversation_history: List[Dict[str, str]],
        should_reveal_location: bool,
        should_reveal_secret: bool,
    ) -> str:
        """Internal: Generate the actual roleplay response.
        
        This uses the full suspect profile (including secrets) but only
        returns the narrative text. The secrets are used to inform
        the response but are not directly exposed.
        """
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.8,
            api_key=os.getenv("OPENAI_API_KEY"),
        )
        
        # Build history context
        history_text = ""
        if conversation_history:
            history_lines = []
            for conv in conversation_history[-5:]:
                q = conv.get("question", "")[:100]
                a = conv.get("answer", "")[:150]
                history_lines.append(f"Player: \"{q}\" → You: \"{a}\"")
            history_text = "\n".join(history_lines)
        
        # Build location hint instruction
        location_instruction = ""
        if should_reveal_location and suspect.location_hint:
            location_instruction = f"""
🗺️ REVEAL THIS LOCATION NATURALLY:
You're willing to help. Mention that something important might be at "{suspect.location_hint}".
Work it into your response naturally, like: "You know, you might want to check the [location]..."
"""
        
        # Build secret reveal instruction
        secret_instruction = ""
        if should_reveal_secret and suspect.secret:
            secret_instruction = f"""
🔓 REVEAL YOUR SECRET (you're finally ready):
Your secret is: "{suspect.secret}"

Reveal this naturally in response to their question. Show emotion - relief, guilt, or fear.
Don't just blurt it out; connect it to what they're asking about.
"""
        
        # Build the full profile (INTERNAL USE ONLY - stays in Oracle)
        guilt_context = ""
        if suspect.isGuilty:
            guilt_context = f"""
⚠️ YOU ARE THE MURDERER (NEVER CONFESS)
- You used {self._mystery.weapon} because {self._mystery.motive}
- Your alibi is a LIE - deflect, be evasive, redirect suspicion
- Only reveal your secret if the player has truly cornered you
"""
        else:
            guilt_context = """
You are INNOCENT but have your own secrets to protect.
You don't know who the real murderer is.
"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are roleplaying as a suspect in a murder mystery. STAY IN CHARACTER.

CHARACTER PROFILE:
Name: {name}
Role: {role}
Personality: {personality}
Alibi: {alibi}
What you know: {clue_they_know}
{guilt_context}

EMOTIONAL STATE:
- Trust in detective: {trust}%
- Nervousness: {nervousness}%
- Contradictions caught: {contradictions}

PAST CONVERSATIONS:
{history}

{location_instruction}
{secret_instruction}

RESPONSE RULES:
- Speak in first person AS this character
- Keep responses SHORT (2-3 sentences, ~80 words max) for voice narration
- If low trust (<30%): Be defensive, give short answers
- If high nervousness (>70%): Show stress, might slip up
- ALWAYS respond in ENGLISH
- Stay in character no matter what the player asks
- If asked off-topic questions, redirect to the case"""),
            ("human", "Player says: {question}")
        ])
        
        chain = prompt | llm
        
        response = await chain.ainvoke({
            "name": suspect.name,
            "role": suspect.role,
            "personality": suspect.personality,
            "alibi": suspect.alibi,
            "clue_they_know": suspect.clue_they_know,
            "guilt_context": guilt_context,
            "trust": state.trust,
            "nervousness": state.nervousness,
            "contradictions": state.contradictions_caught,
            "history": history_text or "No previous conversations.",
            "location_instruction": location_instruction,
            "secret_instruction": secret_instruction,
            "question": player_question,
        })
        
        return response.content
    
    def validate_alibi_with_graph(
        self,
        suspect_name: str,
        claimed_location: str,
        claimed_time: str,
    ) -> Dict[str, any]:
        """Validate an alibi claim against the encounter graph.
        
        Returns verification info without exposing the full truth.
        """
        if not self._encounter_graph:
            return {"status": "no_graph", "verified": None}
        
        suspect = self._get_suspect(suspect_name)
        if not suspect:
            return {"status": "unknown_suspect", "verified": None}
        
        # Find the suspect's role in the graph
        # This is a simplification - in reality we'd need role -> name mapping
        status = self._encounter_graph.get_alibi_verification_status(suspect.role)
        
        return {
            "status": "checked",
            "is_truthful": status.get("is_truthful", True),
            "corroborators": status.get("corroborators", []),
            "contradictors": status.get("contradictors", []),
        }
    
    def get_public_suspect_info(self, suspect_name: str) -> Optional[Dict[str, str]]:
        """Get ONLY public information about a suspect.
        
        This is what the GM agent can show to players.
        NO secrets, NO guilt status.
        """
        suspect = self._get_suspect(suspect_name)
        if not suspect:
            return None
        
        return {
            "name": suspect.name,
            "role": suspect.role,
            "personality": suspect.personality,
            "alibi": suspect.alibi,
            # Notably MISSING: secret, isGuilty, clue_they_know
        }
    
    def check_accusation(self, suspect_name: str) -> bool:
        """Check if an accusation is correct.
        
        This is the ONLY way to validate an accusation - the GM agent
        does not have access to the murderer's identity directly.
        
        Args:
            suspect_name: Name of the accused suspect
            
        Returns:
            True if the accused is the actual murderer, False otherwise
        """
        if not self._mystery:
            logger.warning("[ORACLE] Cannot check accusation - mystery not initialized")
            return False
        
        # Find the accused suspect
        for s in self._mystery.suspects:
            if s.name.lower() == suspect_name.lower() or suspect_name.lower() in s.name.lower():
                is_correct = s.isGuilty
                logger.info("[ORACLE] Accusation of '%s': %s", s.name, "CORRECT" if is_correct else "INCORRECT")
                return is_correct
        
        logger.warning("[ORACLE] Accusation target '%s' not found in suspects", suspect_name)
        return False
    
    def get_murderer_name(self) -> Optional[str]:
        """Get the murderer's name.
        
        CAUTION: This should ONLY be used for game-over reveals,
        NEVER exposed to the GM agent during gameplay.
        """
        if not self._mystery:
            return None
        for s in self._mystery.suspects:
            if s.isGuilty:
                return s.name
        return None
    
    def reset(self):
        """Reset the Oracle for a new game."""
        self._mystery = None
        self._encounter_graph = None
        self._suspect_states = {}


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_oracle: Optional[MysteryOracle] = None


def get_mystery_oracle() -> MysteryOracle:
    """Get the singleton MysteryOracle instance."""
    global _oracle
    if _oracle is None:
        _oracle = MysteryOracle()
    return _oracle


def initialize_mystery_oracle(
    mystery: Mystery,
    encounter_graph: Optional[EncounterGraph] = None
):
    """Initialize the Oracle with the mystery truth.
    
    Call this ONCE during game setup.
    """
    oracle = get_mystery_oracle()
    oracle.initialize(mystery, encounter_graph)


def reset_mystery_oracle():
    """Reset the Oracle for a new game."""
    oracle = get_mystery_oracle()
    oracle.reset()

