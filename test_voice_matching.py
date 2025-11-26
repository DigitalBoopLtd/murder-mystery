"""Test script to verify suspect-to-voice matching results."""

import os
import logging
from dotenv import load_dotenv
from voice_service import get_voice_service

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

def test_voice_matching():
    """Test what voices we're getting when matching suspects."""
    
    voice_service = get_voice_service()
    
    if not voice_service.is_available:
        print("ERROR: ElevenLabs API key not set")
        return
    
    # Test suspects with different characteristics
    test_suspects = [
        {
            "name": "Lady Victoria Ashworth",
            "role": "Victim's wealthy aunt",
            "personality": "Strict, formal, aristocratic",
            "gender": "female",
            "age": "old",
            "nationality": "british"
        },
        {
            "name": "James Mitchell",
            "role": "Butler",
            "personality": "Loyal, reserved, observant",
            "gender": "male",
            "age": "middle_aged",
            "nationality": "british"
        },
        {
            "name": "Sarah Chen",
            "role": "Young intern",
            "personality": "Energetic, naive, ambitious",
            "gender": "female",
            "age": "young",
            "nationality": "american"
        },
        {
            "name": "Robert Thompson",
            "role": "Business partner",
            "personality": "Suspicious, calculating, secretive",
            "gender": "male",
            "age": "middle_aged",
            "nationality": "american"
        }
    ]
    
    print("=" * 80)
    print("TESTING VOICE MATCHING")
    print("=" * 80)
    
    # Test with current default_only=True (should only get professional voices)
    print("\n" + "=" * 80)
    print("TEST 1: With default_only=True (current setting)")
    print("=" * 80)
    
    voices_default_only = voice_service.get_available_voices(
        force_refresh=True,
        english_only=True,
        default_only=True
    )
    
    print(f"\nTotal voices available: {len(voices_default_only)}")
    if voices_default_only:
        print("\nSample voices:")
        for v in voices_default_only[:5]:
            print(f"  - {v.name} ({v.gender}, {v.age}, {v.accent}, use_case={v.use_case}, category={v.category})")
    else:
        print("\n⚠️  NO VOICES FOUND! This is the problem.")
    
    # Test with default_only=False (should get premade + professional)
    print("\n" + "=" * 80)
    print("TEST 2: With default_only=False (include premade voices)")
    print("=" * 80)
    
    voices_all = voice_service.get_available_voices(
        force_refresh=False,  # Use cache
        english_only=True,
        default_only=False
    )
    
    print(f"\nTotal voices available: {len(voices_all)}")
    if voices_all:
        print("\nSample voices:")
        for v in voices_all[:10]:
            print(f"  - {v.name} ({v.gender}, {v.age}, {v.accent}, use_case={v.use_case}, category={v.category})")
    
    # Count by category and use_case
    print("\n" + "=" * 80)
    print("BREAKDOWN BY CATEGORY AND USE_CASE:")
    print("=" * 80)
    
    from collections import defaultdict
    breakdown = defaultdict(int)
    characters_animation_voices = []
    for v in voices_all:
        key = f"{v.category or 'None'}/{v.use_case or 'None'}"
        breakdown[key] += 1
        if v.use_case and "character" in v.use_case.lower():
            characters_animation_voices.append(v)
    
    for key, count in sorted(breakdown.items()):
        print(f"  {key}: {count}")
    
    print(f"\nVoices with 'character' in use_case: {len(characters_animation_voices)}")
    if characters_animation_voices:
        print("\nSample characters_animation voices:")
        for v in characters_animation_voices[:5]:
            print(f"  - {v.name} (category={v.category}, use_case={v.use_case})")
    
    # Test matching
    print("\n" + "=" * 80)
    print("TEST 3: Matching suspects to voices (with default_only=True)")
    print("=" * 80)
    
    assignments = voice_service.assign_voices_to_suspects(
        test_suspects,
        english_only=True,
        default_only=True
    )
    
    print(f"\nAssignments made: {len(assignments)}")
    for suspect_name, voice_id in assignments.items():
        # Find the voice details
        voice = next((v for v in voices_default_only if v.voice_id == voice_id), None)
        if voice:
            print(f"\n{suspect_name}:")
            print(f"  Voice: {voice.name}")
            print(f"  Voice ID: {voice_id}")
            print(f"  Gender: {voice.gender}")
            print(f"  Age: {voice.age}")
            print(f"  Accent: {voice.accent}")
            print(f"  Use Case: {voice.use_case}")
            print(f"  Category: {voice.category}")
        else:
            print(f"\n{suspect_name}: Voice ID {voice_id} (not found in available voices)")
    
    # Test matching with all voices
    print("\n" + "=" * 80)
    print("TEST 4: Matching suspects to voices (with default_only=False)")
    print("=" * 80)
    
    assignments_all = voice_service.assign_voices_to_suspects(
        test_suspects,
        english_only=True,
        default_only=False
    )
    
    print(f"\nAssignments made: {len(assignments_all)}")
    for suspect_name, voice_id in assignments_all.items():
        # Find the voice details
        voice = next((v for v in voices_all if v.voice_id == voice_id), None)
        if voice:
            print(f"\n{suspect_name}:")
            print(f"  Voice: {voice.name}")
            print(f"  Voice ID: {voice_id}")
            print(f"  Gender: {voice.gender}")
            print(f"  Age: {voice.age}")
            print(f"  Accent: {voice.accent}")
            print(f"  Use Case: {voice.use_case}")
            print(f"  Category: {voice.category}")
        else:
            print(f"\n{suspect_name}: Voice ID {voice_id} (not found in available voices)")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"With default_only=True: {len(voices_default_only)} voices available")
    print(f"With default_only=False: {len(voices_all)} voices available")
    print(f"Characters/animation voices found: {len(characters_animation_voices)}")
    
    if len(voices_all) > len(voices_default_only):
        print(f"\n✅ RECOMMENDATION: Use default_only=False to get {len(voices_all) - len(voices_default_only)} more voices")
    else:
        print("\n✅ Current setting is fine")

if __name__ == "__main__":
    test_voice_matching()

