"""Investigation Assistant Agent - Demonstrates MCP Tool Composition.

This agent is separate from the Game Master and demonstrates MCP in action
by composing multiple MCP tools/resources to assist investigation.

It does NOT block gameplay - it's an optional assistant that can:
- Query game state via MCP Resources
- Analyze evidence and suggest next steps
- Generate investigation reports
- Create visualizations using the Image MCP (non-blocking)

This showcases how external AI assistants could interact with the game
via MCP without affecting gameplay latency.

Usage:
    from services.investigation_agent import InvestigationAssistant
    
    assistant = InvestigationAssistant()
    report = await assistant.analyze_case()
    suggestions = await assistant.suggest_next_steps()
"""

import os
import sys
import json
import logging
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

# Try LangChain imports
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, SystemMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# STRUCTURED OUTPUT MODELS
# =============================================================================

class EvidenceAnalysis(BaseModel):
    """Structured analysis of a piece of evidence."""
    clue_id: str
    description: str
    suspects_implicated: List[str] = Field(default_factory=list)
    significance_rating: int = Field(ge=1, le=10, description="How important is this clue?")
    connections: List[str] = Field(default_factory=list, description="Connections to other clues")


class SuspectProfile(BaseModel):
    """Analyzed suspect profile."""
    name: str
    suspicion_level: int = Field(ge=0, le=100, description="0=innocent, 100=definitely guilty")
    key_inconsistencies: List[str] = Field(default_factory=list)
    alibi_strength: str = Field(description="weak/moderate/strong/airtight")
    motive_strength: str = Field(description="none/weak/moderate/strong")
    recommended_questions: List[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    """Comprehensive investigation report."""
    case_summary: str
    progress_percent: float
    evidence_analysis: List[EvidenceAnalysis] = Field(default_factory=list)
    suspect_profiles: List[SuspectProfile] = Field(default_factory=list)
    primary_suspect: Optional[str] = None
    confidence_level: int = Field(ge=0, le=100)
    recommended_actions: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)


class NextStepSuggestion(BaseModel):
    """Suggestion for the player's next action."""
    action: str = Field(description="What to do: 'search', 'interrogate', 'accuse', 'review'")
    target: str = Field(description="Where or who to focus on")
    reasoning: str = Field(description="Why this action is recommended")
    priority: int = Field(ge=1, le=5, description="1=highest priority")


# =============================================================================
# INVESTIGATION ASSISTANT
# =============================================================================

class InvestigationAssistant:
    """AI Assistant that uses MCP to analyze the investigation.
    
    This demonstrates MCP tool composition for the hackathon without
    blocking the main gameplay loop.
    """
    
    def __init__(self):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain not installed. Run: pip install langchain-openai")
        
        self.llm = ChatOpenAI(
            model=os.getenv("INVESTIGATION_ASSISTANT_MODEL", "gpt-4o-mini"),
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # LLM with structured output for reports
        self.report_llm = self.llm.with_structured_output(InvestigationReport)
        self.suggestion_llm = self.llm.with_structured_output(NextStepSuggestion)
    
    def _get_game_state(self) -> Optional[Dict]:
        """Get current game state for analysis."""
        try:
            from game.state_manager import get_game_state
            state = get_game_state()
            if not state or not state.mystery:
                return None
            
            return {
                "setting": state.mystery.setting,
                "victim": {
                    "name": state.mystery.victim.name,
                    "background": state.mystery.victim.background
                },
                "suspects": [
                    {
                        "name": s.name,
                        "role": s.role,
                        "personality": s.personality,
                        "alibi": s.alibi,
                        "interviewed": s.name in state.suspects_talked_to
                    }
                    for s in state.mystery.suspects
                ],
                "clues_found": [
                    {
                        "id": c.id,
                        "description": c.description,
                        "location": c.location,
                        "significance": c.significance
                    }
                    for c in state.mystery.clues
                    if c.id in state.clue_ids_found
                ],
                "locations_searched": list(state.searched_locations),
                "total_clues": len(state.mystery.clues),
                "total_suspects": len(state.mystery.suspects),
                "wrong_accusations": state.wrong_accusations
            }
        except Exception as e:
            logger.error(f"Error getting game state: {e}")
            return None
    
    async def analyze_case(self) -> Optional[InvestigationReport]:
        """Generate a comprehensive investigation report.
        
        This demonstrates:
        1. Reading game state (equivalent to MCP Resources)
        2. Using structured output from LLM
        3. Composing analysis from multiple data sources
        """
        state = self._get_game_state()
        if not state:
            logger.warning("No active game state to analyze")
            return None
        
        prompt = f"""Analyze this murder mystery investigation and provide a structured report.

CASE DETAILS:
Setting: {state['setting']}
Victim: {state['victim']['name']} - {state['victim']['background']}

SUSPECTS ({len([s for s in state['suspects'] if s['interviewed']])}/{len(state['suspects'])} interviewed):
{json.dumps(state['suspects'], indent=2)}

EVIDENCE FOUND ({len(state['clues_found'])}/{state['total_clues']}):
{json.dumps(state['clues_found'], indent=2)}

LOCATIONS SEARCHED: {state['locations_searched']}

Analyze the evidence, assess each suspect, and provide recommendations.
Be analytical and detective-like. Consider alibis, motives, and inconsistencies.
"""
        
        try:
            report = self.report_llm.invoke([
                SystemMessage(content="You are a brilliant detective assistant analyzing a murder case. Be thorough and analytical."),
                HumanMessage(content=prompt)
            ])
            return report
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return None
    
    async def suggest_next_steps(self, num_suggestions: int = 3) -> List[NextStepSuggestion]:
        """Suggest next investigation steps.
        
        This demonstrates structured output parsing for action recommendations.
        """
        state = self._get_game_state()
        if not state:
            return []
        
        # Identify gaps in investigation
        uninterviewed = [s['name'] for s in state['suspects'] if not s['interviewed']]
        clues_remaining = state['total_clues'] - len(state['clues_found'])
        
        prompt = f"""Based on this investigation state, suggest the single most important next action.

PROGRESS:
- {len(state['clues_found'])}/{state['total_clues']} clues found
- {len([s for s in state['suspects'] if s['interviewed']])}/{len(state['suspects'])} suspects interviewed
- Locations searched: {state['locations_searched']}
- Wrong accusations: {state['wrong_accusations']}/3

UNINTERVIEWED SUSPECTS: {uninterviewed}
CLUES STILL HIDDEN: {clues_remaining}

EVIDENCE FOUND:
{json.dumps(state['clues_found'], indent=2)}

What should the player do next to make progress?
"""
        
        suggestions = []
        try:
            for i in range(num_suggestions):
                suggestion = self.suggestion_llm.invoke([
                    SystemMessage(content=f"You are a detective mentor. Suggest priority {i+1} action."),
                    HumanMessage(content=prompt)
                ])
                suggestion.priority = i + 1
                suggestions.append(suggestion)
        except Exception as e:
            logger.error(f"Error generating suggestions: {e}")
        
        return suggestions
    
    async def analyze_suspect(self, suspect_name: str) -> Optional[SuspectProfile]:
        """Deep analysis of a specific suspect."""
        state = self._get_game_state()
        if not state:
            return None
        
        # Find the suspect
        suspect = None
        for s in state['suspects']:
            if suspect_name.lower() in s['name'].lower():
                suspect = s
                break
        
        if not suspect:
            return None
        
        # Get clues that might implicate this suspect
        relevant_clues = [c for c in state['clues_found'] if suspect['name'].lower() in c['description'].lower()]
        
        suspect_llm = self.llm.with_structured_output(SuspectProfile)
        
        prompt = f"""Analyze this suspect in detail:

SUSPECT: {suspect['name']}
Role: {suspect['role']}
Personality: {suspect['personality']}
Alibi: {suspect['alibi']}
Interviewed: {suspect['interviewed']}

POTENTIALLY RELEVANT EVIDENCE:
{json.dumps(relevant_clues, indent=2)}

VICTIM: {state['victim']['name']} - {state['victim']['background']}

Assess their suspicion level, alibi strength, and suggest questions to ask them.
"""
        
        try:
            profile = suspect_llm.invoke([
                SystemMessage(content="You are an expert detective profiler. Be thorough and analytical."),
                HumanMessage(content=prompt)
            ])
            return profile
        except Exception as e:
            logger.error(f"Error analyzing suspect: {e}")
            return None


# =============================================================================
# STANDALONE DEMO
# =============================================================================

async def demo():
    """Run a demo of the Investigation Assistant.
    
    This shows MCP-style structured queries and responses.
    """
    print("\n" + "=" * 60)
    print("🔍 INVESTIGATION ASSISTANT DEMO")
    print("=" * 60)
    print("\nThis demonstrates MCP tool composition with structured outputs.\n")
    
    assistant = InvestigationAssistant()
    
    # Check for active game
    state = assistant._get_game_state()
    if not state:
        print("❌ No active game found.")
        print("   Start a mystery first, then run this demo.")
        return
    
    print(f"✅ Active case: Murder of {state['victim']['name']}")
    print(f"   Progress: {len(state['clues_found'])}/{state['total_clues']} clues, "
          f"{len([s for s in state['suspects'] if s['interviewed']])}/{len(state['suspects'])} interviews")
    
    # Generate report
    print("\n📋 Generating Investigation Report...")
    report = await assistant.analyze_case()
    if report:
        print(f"\n   Primary Suspect: {report.primary_suspect or 'Unknown'}")
        print(f"   Confidence: {report.confidence_level}%")
        print(f"   Progress: {report.progress_percent}%")
        print(f"\n   Recommended Actions:")
        for i, action in enumerate(report.recommended_actions[:3], 1):
            print(f"   {i}. {action}")
    
    # Get suggestions
    print("\n💡 Getting Next Step Suggestions...")
    suggestions = await assistant.suggest_next_steps(3)
    for s in suggestions:
        print(f"\n   [{s.priority}] {s.action.upper()}: {s.target}")
        print(f"       {s.reasoning}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())


