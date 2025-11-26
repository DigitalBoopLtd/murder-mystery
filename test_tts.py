#!/usr/bin/env python3
"""Test script to verify ElevenLabs TTS is working.

Run this to diagnose TTS issues independently of the game.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_elevenlabs():
    """Test ElevenLabs TTS functionality."""

    print("=" * 60)
    print("ElevenLabs TTS Test")
    print("=" * 60)

    # Check API key
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("❌ ERROR: ELEVENLABS_API_KEY not set in environment!")
        print("   Set it in .env file or export it in your shell.")
        return False

    print(f"✅ API key found: {api_key[:8]}...{api_key[-4:]}")

    # Try to import elevenlabs
    try:
        from elevenlabs import ElevenLabs

        print("✅ elevenlabs package imported successfully")
    except ImportError as e:
        print(f"❌ ERROR: Cannot import elevenlabs: {e}")
        print("   Run: pip install elevenlabs")
        return False

    # Initialize client
    try:
        client = ElevenLabs(api_key=api_key)
        print("✅ ElevenLabs client initialized")
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize client: {e}")
        return False

    # Check available methods
    print("\nChecking available TTS methods:")
    tts = client.text_to_speech

    methods = ["convert", "convert_with_timestamps", "stream", "stream_with_timestamps"]
    for method in methods:
        available = hasattr(tts, method)
        status = "✅" if available else "❌"
        print(f"  {status} {method}: {'available' if available else 'NOT available'}")

    # Test basic convert
    print("\n" + "=" * 60)
    print("Testing basic TTS (convert)...")
    print("=" * 60)

    test_text = "Hello, this is a test of the ElevenLabs text to speech system."
    voice_id = "JBFqnCBsd6RMkjVDRZzb"  # George voice

    try:
        print(f"Voice ID: {voice_id}")
        print(f"Text: {test_text}")
        print("Generating audio...")

        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=test_text,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        )

        # Collect audio
        audio_chunks = []
        for chunk in audio_generator:
            if chunk:
                audio_chunks.append(chunk)

        if not audio_chunks:
            print("❌ ERROR: No audio chunks received!")
            return False

        audio_bytes = b"".join(audio_chunks)
        print(f"✅ Generated {len(audio_bytes)} bytes of audio")

        # Save to file
        output_path = "/tmp/test_tts_output.mp3"
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"✅ Saved audio to: {output_path}")
        print(f"   File size: {os.path.getsize(output_path)} bytes")

    except Exception as e:
        print(f"❌ ERROR: TTS convert failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Test convert_with_timestamps
    print("\n" + "=" * 60)
    print("Testing TTS with timestamps (convert_with_timestamps)...")
    print("=" * 60)

    if hasattr(tts, "convert_with_timestamps"):
        try:
            response = client.text_to_speech.convert_with_timestamps(
                voice_id=voice_id,
                text=test_text,
                model_id="eleven_flash_v2_5",
                output_format="mp3_44100_128",
            )

            print(f"Response type: {type(response)}")

            # Check for audio
            audio_data = None
            if hasattr(response, "audio_base64") and response.audio_base64:
                import base64

                audio_data = base64.b64decode(response.audio_base64)
                print(f"✅ Found audio_base64: {len(audio_data)} bytes")
            elif hasattr(response, "audio_base_64") and response.audio_base_64:
                import base64

                audio_data = base64.b64decode(response.audio_base_64)
                print(f"✅ Found audio_base_64: {len(audio_data)} bytes")
            else:
                print("❌ No audio data found in response")
                print(
                    f"   Available attributes: {[a for a in dir(response) if not a.startswith('_')]}"
                )

            # Check for alignment
            alignment = getattr(response, "alignment", None)
            if alignment:
                chars = getattr(alignment, "characters", [])
                starts = getattr(alignment, "character_start_times_seconds", [])
                ends = getattr(alignment, "character_end_times_seconds", [])
                print(f"✅ Found alignment data: {len(chars)} characters")
                if chars:
                    print(f"   First 10 chars: {''.join(str(c) for c in chars[:10])}")
                    print(f"   First 5 start times: {starts[:5]}")
            else:
                print("❌ No alignment data in response")

            if audio_data:
                output_path_ts = "/tmp/test_tts_with_timestamps.mp3"
                with open(output_path_ts, "wb") as f:
                    f.write(audio_data)
                print(f"✅ Saved timestamped audio to: {output_path_ts}")

        except Exception as e:
            print(f"❌ ERROR: convert_with_timestamps failed: {e}")
            import traceback

            traceback.print_exc()
    else:
        print("⚠️  convert_with_timestamps not available in this SDK version")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nIf basic TTS worked, your ElevenLabs setup is correct.")
    print("Check the generated audio files in /tmp/")

    return True


if __name__ == "__main__":
    success = test_elevenlabs()
    sys.exit(0 if success else 1)
