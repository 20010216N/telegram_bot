
import os
import math
from pydub import AudioSegment

def apply_audio_effect(input_file, output_file, effect):
    audio = AudioSegment.from_mp3(input_file)
    processed = audio
    title_suffix = ""

    if effect == '8d':
        # 8D Panning Logic
        # Split into chunks (e.g., 200ms) and pan them sine-wave style
        pan_amount = 0
        chunk_len = 200 # ms
        chunks = []
        
        # Add some reverb feel (overlay slightly delayed) before panning?
        # Simple reverb
        reverb = audio - 10 # lower volume
        audio = audio.overlay(reverb, position=50) # 50ms delay
        
        for i, chunk in enumerate(audio[::chunk_len]):
            # Sine wave from -1.0 to 1.0
            # Complete cycle every ~10 seconds?
            cycle_len = 50 # chunks (50 * 200ms = 10s)
            pan = math.sin(2 * math.pi * i / cycle_len)
            chunks.append(chunk.pan(pan))
        
        processed = sum(chunks)
        title_suffix = " (8D Audio)"
        
    elif effect == 'slowed':
        # Slowed + Reverb
        # Slow down
        speed = 0.85
        # Manually change frame rate to pitch down
        new_rate = int(audio.frame_rate * speed)
        processed = audio._spawn(audio.raw_data, overrides={'frame_rate': new_rate})
        processed = processed.set_frame_rate(audio.frame_rate)
        
        # Add Reverb
        reverb = processed - 5
        processed = processed.overlay(reverb, position=100)
        
        title_suffix = " (Slowed & Reverb)"
        
    elif effect == 'concert':
        # Concert Hall (Reverb)
        # Multiple delays
        delay1 = audio - 5
        delay2 = audio - 10
        
        processed = audio.overlay(delay1, position=50).overlay(delay2, position=100)
        title_suffix = " (Concert Hall)"

    elif effect == 'bass':
        # Bass Boost
        # Low pass filter to isolate bass frequencies (below 150Hz)
        bass = audio.low_pass_filter(150)
        # Boost the bass (gain in dB) - e.g. +8dB
        bass = bass + 8
        # Overlay (mix) the boosted bass back onto the original track
        processed = audio.overlay(bass)
        title_suffix = " (Bass Boosted)"
        
    # Export
    processed.export(output_file, format="mp3")
    return processed, title_suffix
