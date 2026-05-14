"""
Run this once to generate a base64-encoded beep WAV.
Paste the output into the <source src="data:audio/wav;base64,..." /> in your layout.

Usage:
    python generate_beep.py
"""
import math
import struct
import base64
import wave
import io


def generate_beep_wav(frequency=880, duration=0.4, volume=0.5, sample_rate=22050):
    """Generate a simple sine wave beep as WAV bytes."""
    num_samples = int(sample_rate * duration)
    buf = io.BytesIO()

    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)

        frames = []
        for i in range(num_samples):
            # Sine wave with fade-out envelope
            t = i / sample_rate
            envelope = max(0.0, 1.0 - (t / duration))
            sample = int(volume * envelope * 32767 * math.sin(2 * math.pi * frequency * t))
            frames.append(struct.pack('<h', sample))

        wf.writeframes(b''.join(frames))

    return buf.getvalue()


if __name__ == '__main__':
    wav_bytes = generate_beep_wav(frequency=880, duration=0.5, volume=0.6)
    b64 = base64.b64encode(wav_bytes).decode('ascii')
    print("Paste this into your <source src='data:audio/wav;base64,...'>:")
    print()
    print(f"data:audio/wav;base64,{b64}")