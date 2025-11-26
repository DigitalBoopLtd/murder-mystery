"""Test script to inspect ElevenLabs API voice data structure.

This script makes a real API call to see what data is returned,
particularly for voices in the "characters and animation" category.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not API_KEY:
    print("ERROR: ELEVENLABS_API_KEY not set in environment")
    exit(1)

def get_headers():
    return {"xi-api-key": API_KEY, "Content-Type": "application/json"}

def test_voices_api():
    """Fetch voices and inspect the data structure."""
    print("=" * 80)
    print("Fetching voices from ElevenLabs API...")
    print("=" * 80)
    
    try:
        # Try the standard voices endpoint
        print("Calling /voices endpoint...")
        response = requests.get(
            f"{ELEVENLABS_API_URL}/voices",
            headers=get_headers(),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        # Check if there's pagination info
        print(f"Response keys: {list(data.keys())}")
        if "pagination" in data:
            print(f"Pagination info: {data['pagination']}")
        
        # Check if there are more voices by category
        print("\n" + "=" * 80)
        print("BREAKDOWN BY CATEGORY:")
        print("=" * 80)
        
        premade_count = sum(1 for v in data.get("voices", []) if v.get("category") == "premade")
        professional_count = sum(1 for v in data.get("voices", []) if v.get("category") == "professional")
        cloned_count = sum(1 for v in data.get("voices", []) if v.get("category") == "cloned")
        generated_count = sum(1 for v in data.get("voices", []) if v.get("category") == "generated")
        
        print(f"Premade (default): {premade_count}")
        print(f"Professional: {professional_count}")
        print(f"Cloned (custom): {cloned_count}")
        print(f"Generated (custom): {generated_count}")
        print(f"Total: {len(data.get('voices', []))}")
        
        # Note: The /voices endpoint only returns voices available to YOUR account
        # This includes default voices + any custom voices you've created/added
        # There may be more default voices available, but they're not returned if
        # they're not accessible to your account tier or haven't been added to your library
        
        print("\n" + "=" * 80)
        print("NOTE: The /voices endpoint returns only voices available to YOUR account.")
        print("This may be limited by your subscription tier or which voices you've added.")
        print("=" * 80)
        
        # Check if there are any pagination hints or if we can get more
        print("\n" + "=" * 80)
        print("CHECKING FOR MORE VOICES:")
        print("=" * 80)
        print("The API returned 27 voices. ElevenLabs typically has more default voices.")
        print("This might be because:")
        print("  1. Your subscription tier limits access to certain voices")
        print("  2. The API only returns voices you've 'added' to your account")
        print("  3. There's pagination we're not handling (unlikely - no pagination info in response)")
        print("\nTo get more voices, you may need to:")
        print("  - Check your ElevenLabs dashboard to see all available default voices")
        print("  - Add more default voices to your account/library")
        print("  - Upgrade your subscription tier if applicable")
        
        print(f"\nTotal voices returned: {len(data.get('voices', []))}\n")
        
        # Show structure of first voice (full data)
        if data.get("voices"):
            print("=" * 80)
            print("SAMPLE VOICE DATA (first voice, full structure):")
            print("=" * 80)
            first_voice = data["voices"][0]
            print(json.dumps(first_voice, indent=2))
            
            print("\n" + "=" * 80)
            print("KEY FIELDS IN FIRST VOICE:")
            print("=" * 80)
            for key in first_voice.keys():
                value = first_voice[key]
                if isinstance(value, dict):
                    print(f"  {key}: (dict with keys: {list(value.keys())})")
                elif isinstance(value, list):
                    print(f"  {key}: (list with {len(value)} items)")
                else:
                    print(f"  {key}: {value}")
        
        # Analyze all voices
        print("\n" + "=" * 80)
        print("ANALYZING ALL VOICES:")
        print("=" * 80)
        
        categories = {}
        use_cases = {}
        characters_animation = []
        
        for voice in data.get("voices", []):
            # Category analysis
            category = voice.get("category")
            if category:
                categories[category] = categories.get(category, 0) + 1
            else:
                categories["None/null"] = categories.get("None/null", 0) + 1
            
            # Use case analysis
            labels = voice.get("labels", {})
            use_case = labels.get("use_case", "")
            if use_case:
                use_cases[use_case] = use_cases.get(use_case, 0) + 1
            
            # Check for "characters and animation" category
            if category and "character" in category.lower():
                characters_animation.append(voice)
            elif use_case and ("character" in use_case.lower() or "animation" in use_case.lower()):
                characters_animation.append(voice)
        
        print(f"\nCategories found:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count} voices")
        
        print(f"\nUse cases found:")
        for uc, count in sorted(use_cases.items()):
            print(f"  {uc}: {count} voices")
        
        # Show characters and animation voices
        print("\n" + "=" * 80)
        print(f"CHARACTERS AND ANIMATION VOICES ({len(characters_animation)} found):")
        print("=" * 80)
        
        for voice in characters_animation[:10]:  # Show first 10
            print(f"\nName: {voice.get('name')}")
            print(f"  Voice ID: {voice.get('voice_id')}")
            print(f"  Category: {voice.get('category')}")
            labels = voice.get("labels", {})
            print(f"  Use Case: {labels.get('use_case')}")
            print(f"  Gender: {labels.get('gender')}")
            print(f"  Age: {labels.get('age')}")
            print(f"  Accent: {labels.get('accent')}")
            print(f"  Description: {labels.get('description', 'N/A')}")
        
        if len(characters_animation) > 10:
            print(f"\n... and {len(characters_animation) - 10} more")
        
        # Show a few default/premade voices for comparison
        print("\n" + "=" * 80)
        print("SAMPLE DEFAULT/PREMADE VOICES (for comparison):")
        print("=" * 80)
        
        premade_voices = [v for v in data.get("voices", []) if v.get("category") == "premade" or v.get("category") is None]
        for voice in premade_voices[:5]:
            print(f"\nName: {voice.get('name')}")
            print(f"  Voice ID: {voice.get('voice_id')}")
            print(f"  Category: {voice.get('category')}")
            labels = voice.get("labels", {})
            print(f"  Use Case: {labels.get('use_case')}")
            print(f"  Gender: {labels.get('gender')}")
            print(f"  Age: {labels.get('age')}")
            print(f"  Accent: {labels.get('accent')}")
        
        # Show a few custom/cloned voices for comparison
        print("\n" + "=" * 80)
        print("SAMPLE CUSTOM/CLONED VOICES (for comparison):")
        print("=" * 80)
        
        custom_voices = [v for v in data.get("voices", []) if v.get("category") in ["cloned", "custom", "professional"]]
        for voice in custom_voices[:5]:
            print(f"\nName: {voice.get('name')}")
            print(f"  Voice ID: {voice.get('voice_id')}")
            print(f"  Category: {voice.get('category')}")
            labels = voice.get("labels", {})
            print(f"  Use Case: {labels.get('use_case')}")
            print(f"  Gender: {labels.get('gender')}")
            print(f"  Age: {labels.get('age')}")
            print(f"  Accent: {labels.get('accent')}")
        
        # Save full response to file for inspection
        output_file = "elevenlabs_voices_response.json"
        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"\n" + "=" * 80)
        print(f"Full API response saved to: {output_file}")
        print("=" * 80)
        
    except requests.RequestException as e:
        print(f"ERROR: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")

if __name__ == "__main__":
    test_voices_api()

