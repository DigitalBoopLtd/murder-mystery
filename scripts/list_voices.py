#!/usr/bin/env python3
"""List all ElevenLabs voices with full metadata and save to files."""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from elevenlabs import ElevenLabs
except ImportError:
    print("Error: elevenlabs package not installed. Run: pip install elevenlabs")
    sys.exit(1)

# Load environment variables
load_dotenv()

def format_voice_table(voices_data):
    """Format voices as a readable table."""
    lines = []
    lines.append("=" * 120)
    lines.append("ELEVENLABS VOICE LIBRARY")
    lines.append("=" * 120)
    lines.append("")
    
    for i, voice in enumerate(voices_data, 1):
        labels = voice.get("labels", {})
        lines.append(f"{i}. {voice['name']}")
        lines.append(f"   Voice ID: {voice['voice_id']}")
        lines.append(f"   Gender: {labels.get('gender', 'N/A')}")
        lines.append(f"   Age: {labels.get('age', 'N/A')}")
        lines.append(f"   Accent: {labels.get('accent', 'N/A')}")
        lines.append(f"   Style: {labels.get('descriptive', 'N/A')}")
        lines.append(f"   Language: {labels.get('language', 'N/A')}")
        lines.append(f"   Use Case: {labels.get('use_case', 'N/A')}")
        lines.append(f"   Category: {voice.get('category', 'N/A')}")
        lines.append(f"   Description: {voice.get('description', 'N/A')}")
        if voice.get('preview_url'):
            lines.append(f"   Preview: {voice['preview_url']}")
        lines.append("")
    
    return "\n".join(lines)

def main():
    """Main function to fetch and save voice metadata."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment variables")
        print("Make sure you have a .env file with ELEVENLABS_API_KEY set")
        sys.exit(1)
    
    print("Fetching voices from ElevenLabs...")
    
    try:
        client = ElevenLabs(api_key=api_key)
        voices_response = client.voices.get_all()
        
        if not voices_response.voices:
            print("No voices found in your library")
            return
        
        print(f"Found {len(voices_response.voices)} voices")
        
        # Extract all metadata
        voices_data = []
        for voice in voices_response.voices:
            voice_dict = {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category,
                "description": voice.description,
                "preview_url": getattr(voice, 'preview_url', None),
                "labels": {
                    "gender": voice.labels.get("gender") if voice.labels else None,
                    "age": voice.labels.get("age") if voice.labels else None,
                    "accent": voice.labels.get("accent") if voice.labels else None,
                    "descriptive": voice.labels.get("descriptive") if voice.labels else None,
                    "language": voice.labels.get("language") if voice.labels else None,
                    "use_case": voice.labels.get("use_case") if voice.labels else None,
                    "locale": voice.labels.get("locale") if voice.labels else None,
                },
                "settings": voice.settings.model_dump() if hasattr(voice, 'settings') and voice.settings else None,
                "sharing": voice.sharing.model_dump() if hasattr(voice, 'sharing') and voice.sharing else None,
            }
            voices_data.append(voice_dict)
        
        # Save as JSON
        output_dir = Path(__file__).parent.parent
        json_path = output_dir / "voices_metadata.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(voices_data, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved JSON to: {json_path}")
        
        # Save as formatted table
        table_path = output_dir / "voices_metadata.txt"
        table_text = format_voice_table(voices_data)
        with open(table_path, "w", encoding="utf-8") as f:
            f.write(table_text)
        print(f"✓ Saved formatted table to: {table_path}")
        
        # Also print summary to console
        print("\n" + "=" * 120)
        print("SUMMARY")
        print("=" * 120)
        
        # Count by gender
        genders = {}
        for voice in voices_data:
            gender = voice["labels"].get("gender", "unknown")
            genders[gender] = genders.get(gender, 0) + 1
        
        print(f"\nTotal voices: {len(voices_data)}")
        print("\nBy Gender:")
        for gender, count in sorted(genders.items()):
            print(f"  {gender}: {count}")
        
        # Count by accent
        accents = {}
        for voice in voices_data:
            accent = voice["labels"].get("accent", "unknown")
            accents[accent] = accents.get(accent, 0) + 1
        
        print("\nBy Accent:")
        for accent, count in sorted(accents.items(), key=lambda x: (x[0] is None, str(x[0]) if x[0] else "")):
            print(f"  {accent or 'N/A'}: {count}")
        
        # Count by age
        ages = {}
        for voice in voices_data:
            age = voice["labels"].get("age", "unknown")
            ages[age] = ages.get(age, 0) + 1
        
        print("\nBy Age:")
        for age, count in sorted(ages.items(), key=lambda x: (x[0] is None, str(x[0]) if x[0] else "")):
            print(f"  {age or 'N/A'}: {count}")
        
        print("\n" + "=" * 120)
        print(f"\nFull details saved to:")
        print(f"  - {json_path}")
        print(f"  - {table_path}")
        
    except Exception as e:
        print(f"Error fetching voices: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

