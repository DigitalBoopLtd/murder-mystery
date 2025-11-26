"""Live captions generation for word-by-word highlighting.

Shows all text with individual words, highlighting the current word being spoken.
Uses precise word timestamps from alignment data when available.

NOTE: Gradio sanitizes <script> tags in HTML components, so all JavaScript
must be injected via Gradio's js parameter in app.py instead.
"""

import re
import uuid
import logging
import base64
import os
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


def create_live_captions_html(
    text: str, alignment_data: Optional[List[Dict]] = None, audio_path: Optional[str] = None
) -> str:
    """Create HTML for live captions with word-by-word highlighting.

    Args:
        text: The text to display as live captions
        alignment_data: Optional list of word timestamps from TTS
                       Each dict should have 'word', 'start', and 'end' keys
        audio_path: Optional path to audio file to embed

    Returns:
        HTML string (JavaScript is injected via Gradio's js parameter)
    """
    if not text or not text.strip():
        logger.debug("Empty text provided for live captions")
        return '<div class="live-captions" id="live-captions-container"><em>Waiting for response...</em></div>'

    # Clean text - remove markdown formatting and emotional tags
    clean_text = re.sub(r"\*\*", "", text)
    clean_text = re.sub(r"\*", "", clean_text)
    clean_text = re.sub(r"<[^>]+>", "", clean_text)
    clean_text = re.sub(r"\[.*?\]", "", clean_text)  # Remove [excited], etc.
    clean_text = clean_text.strip()

    # Generate unique container ID - use a fixed prefix so JS can find it
    unique_id = f"live-captions-{uuid.uuid4().hex[:8]}"
    audio_id = f"caption-audio-{uuid.uuid4().hex[:8]}"
    
    # Check if we have valid alignment data
    has_timestamps = alignment_data and len(alignment_data) > 0
    
    if has_timestamps:
        logger.info(f"[Captions] Creating word-level captions with {len(alignment_data)} timestamps")
        words_html = ""
        total_duration = 0.0
        
        for i, word_data in enumerate(alignment_data):
            word = word_data.get("word", "")
            start = float(word_data.get("start", 0.0))
            end = float(word_data.get("end", 0.0))
            total_duration = max(total_duration, end)
            
            # First word is active, rest are upcoming
            state_class = "active" if i == 0 else "upcoming"
            
            words_html += (
                f'<span class="caption-word {state_class}" '
                f'data-index="{i}" '
                f'data-start="{start:.3f}" '
                f'data-end="{end:.3f}">'
                f'{word} </span>'
            )
    else:
        # Fallback: split text into words with estimated timing
        logger.info("[Captions] No alignment data, using estimated timing")
        words = clean_text.split()
        words_html = ""
        estimated_duration_per_word = 0.35  # ~170 words per minute
        current_time = 0.0
        
        for i, word in enumerate(words):
            end_time = current_time + estimated_duration_per_word
            state_class = "active" if i == 0 else "upcoming"
            
            words_html += (
                f'<span class="caption-word {state_class}" '
                f'data-index="{i}" '
                f'data-start="{current_time:.3f}" '
                f'data-end="{end_time:.3f}">'
                f'{word} </span>'
            )
            current_time = end_time
        
        total_duration = current_time

    # Embed audio as base64 data URL if path provided
    audio_html = ""
    if audio_path and os.path.exists(audio_path):
        try:
            with open(audio_path, "rb") as f:
                audio_bytes = f.read()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            # Use data-caption-audio class so our JS can find it
            audio_html = f'''
            <div class="caption-audio-container" style="text-align: center; margin: 15px 0;">
                <audio id="{audio_id}" class="caption-audio" controls preload="auto"
                    style="width: 100%; max-width: 500px; margin: 10px auto; display: block;">
                    <source src="data:audio/mpeg;base64,{audio_b64}" type="audio/mpeg">
                    Your browser does not support audio.
                </audio>
            </div>
            '''
            logger.info(f"[Captions] Embedded audio: {len(audio_bytes)} bytes as base64 (id={audio_id})")
        except Exception as e:
            logger.error(f"[Captions] Failed to embed audio: {e}")

    # Create HTML - NO script tags (Gradio sanitizes them)
    # JavaScript is injected via Gradio's js parameter
    html = f'''
    <div class="live-captions-wrapper" data-audio-id="{audio_id}">
        {audio_html}
        <div class="live-captions" id="{unique_id}" data-duration="{total_duration:.2f}">
            {words_html}
        </div>
    </div>
    '''

    return html


def estimate_duration(text: str) -> float:
    """Estimate speaking duration for text (~150 words per minute)."""
    word_count = len(text.split())
    return max(word_count * 0.4, 1.0)


# JavaScript to be injected via Gradio's js parameter
CAPTION_SYNC_JS = """
() => {
    // Caption sync system - runs once on page load
    console.log('[CaptionSync] Initializing caption sync system...');
    
    let currentAudio = null;
    let currentContainer = null;
    let pollInterval = null;
    
    function updateHighlight(words, index) {
        words.forEach((w, i) => {
            w.classList.remove('active', 'spoken', 'upcoming');
            if (i < index) {
                w.classList.add('spoken');
            } else if (i === index) {
                w.classList.add('active');
            } else {
                w.classList.add('upcoming');
            }
        });
        
        // Scroll active word into view
        if (words[index] && index > 0) {
            words[index].scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'nearest'
            });
        }
    }
    
    function syncCaptions() {
        if (!currentAudio || !currentContainer) return;
        
        const words = currentContainer.querySelectorAll('.caption-word');
        if (words.length === 0) return;
        
        const currentTime = currentAudio.currentTime || 0;
        
        // Find active word based on timestamps
        let activeIndex = 0;
        for (let i = 0; i < words.length; i++) {
            const start = parseFloat(words[i].dataset.start) || 0;
            const end = parseFloat(words[i].dataset.end) || 0;
            
            if (currentTime >= start && currentTime < end) {
                activeIndex = i;
                break;
            } else if (currentTime >= start) {
                activeIndex = i;
            }
        }
        
        updateHighlight(words, activeIndex);
    }
    
    function setupAudio(audio, container) {
        if (currentAudio === audio) return; // Already set up
        
        console.log('[CaptionSync] Setting up new audio element');
        currentAudio = audio;
        currentContainer = container;
        
        // Clear old interval
        if (pollInterval) {
            clearInterval(pollInterval);
        }
        
        // Set up event listeners
        audio.addEventListener('timeupdate', syncCaptions);
        audio.addEventListener('play', () => {
            console.log('[CaptionSync] ▶ Audio playing');
            syncCaptions();
        });
        audio.addEventListener('ended', () => {
            console.log('[CaptionSync] ⏹ Audio ended');
            const words = container.querySelectorAll('.caption-word');
            updateHighlight(words, words.length);
        });
        
        // Poll as backup (timeupdate can be slow)
        pollInterval = setInterval(syncCaptions, 50);
        
        // Try autoplay
        audio.play().then(() => {
            console.log('[CaptionSync] ✅ Autoplay succeeded');
        }).catch(err => {
            console.log('[CaptionSync] ⚠ Autoplay blocked - user must click play');
        });
    }
    
    function scanForCaptions() {
        // Find caption containers
        const wrappers = document.querySelectorAll('.live-captions-wrapper');
        
        wrappers.forEach(wrapper => {
            const audioId = wrapper.dataset.audioId;
            const audio = wrapper.querySelector('.caption-audio');
            const container = wrapper.querySelector('.live-captions');
            
            if (audio && container && audio !== currentAudio) {
                console.log('[CaptionSync] Found new caption audio:', audioId);
                setupAudio(audio, container);
            }
        });
    }
    
    // Initial scan
    scanForCaptions();
    
    // Watch for new captions being added (Gradio updates DOM dynamically)
    const observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                // Small delay to let Gradio finish rendering
                setTimeout(scanForCaptions, 100);
                break;
            }
        }
    });
    
    observer.observe(document.body, { 
        childList: true, 
        subtree: true 
    });
    
    console.log('[CaptionSync] ✅ Caption sync system ready');
}
"""
