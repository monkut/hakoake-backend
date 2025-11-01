"""Generate multiple TTS audio samples with different tuning parameters."""

import asyncio
import json
import logging
from pathlib import Path

import edge_tts
import numpy as np
import ollama
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from pydub import AudioSegment
from pydub.generators import WhiteNoise

logger = logging.getLogger(__name__)

# Available voices for Orpheus TTS
ORPHEUS_VOICES = ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe", "ceylia"]

# Constants for audio effects
MIN_WORD_LENGTH_FOR_STUTTER = 3
STUTTER_THRESHOLD_FOR_GLITCH = 0.15
VOLUME_DROP_PROBABILITY = 0.1


class Command(BaseCommand):
    help = "Generate N TTS audio samples with different tuning parameters for comparison"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--count",
            "-n",
            type=int,
            default=5,
            help="Number of TTS samples to generate with different tunings (default: 5)",
        )
        parser.add_argument(
            "--text",
            "-t",
            type=str,
            help="Text to convert to speech (if not provided, uses a default sample)",
        )
        parser.add_argument(
            "--output-dir",
            "-o",
            type=str,
            help="Output directory for audio files (default: data/tts_samples/)",
        )
        parser.add_argument(
            "--model",
            "-m",
            type=str,
            default=settings.VIDEO_TTS_MODEL,
            help=f"TTS model to use (default: {settings.VIDEO_TTS_MODEL})",
        )
        parser.add_argument(
            "--voice",
            type=str,
            default="tara",
            choices=ORPHEUS_VOICES,
            help=f"Voice to use for TTS (choices: {', '.join(ORPHEUS_VOICES)})",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN002, ANN003, PLR0915, C901, PLR0912
        """Generate TTS samples with different tuning parameters."""
        count = options["count"]
        text = options["text"]
        output_dir = options["output_dir"]
        model = options["model"]
        voice = options["voice"]

        # Use default text if not provided
        if not text:
            text = (
                "Welcome to HAKOAKE's monthly playlist, where we dive into the heart of Tokyo's live music scene. "
                "This month, we're thrilled to spotlight five incredible bands who are all performing in intimate "
                "venues with a capacity of 350 or less. These artists are not just playing music; "
                "they're creating experiences that you can feel in your chest."
            )

        # Set output directory
        if output_dir:
            output_path = Path(output_dir)
        else:
            output_path = Path(settings.BASE_DIR) / "data" / "tts_samples"

        output_path.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"Generating {count} TTS samples...")
        self.stdout.write(f"Model: {model}")
        self.stdout.write(f"Voice: {voice}")
        self.stdout.write(f"Output directory: {output_path}")
        self.stdout.write(f"Text length: {len(text)} characters\n")

        # Define tuning presets - 10 different robotic voice variations
        tuning_presets = [
            {
                "name": "robotic_deep_slow",
                "description": "Deep robotic voice - slow and mechanical",
                "temperature": 0.5,
                "top_p": 0.75,
                "repetition_penalty": 1.1,
                "edge_voice": "en-US-GuyNeural",
                "rate": "-20%",
                "pitch": "-20Hz",
                "static_level": -15,  # dB
                "stutter_probability": 0.0,
                "bitrate": "64k",
                "sample_rate": 16000,
            },
            {
                "name": "robotic_high_fast",
                "description": "High-pitched robotic voice - fast monotone",
                "temperature": 1.5,
                "top_p": 1.0,
                "repetition_penalty": 1.3,
                "edge_voice": "en-US-ChristopherNeural",
                "rate": "+25%",
                "pitch": "+10Hz",
                "static_level": -18,
                "stutter_probability": 0.0,
                "bitrate": "64k",
                "sample_rate": 16000,
            },
            {
                "name": "robotic_military",
                "description": "Military-style robotic voice - authoritative",
                "temperature": 0.8,
                "top_p": 0.85,
                "repetition_penalty": 1.2,
                "edge_voice": "en-US-EricNeural",
                "rate": "+5%",
                "pitch": "-15Hz",
                "static_level": -12,
                "stutter_probability": 0.0,
                "bitrate": "56k",
                "sample_rate": 12000,
            },
            {
                "name": "robotic_female_android",
                "description": "Female android voice - synthetic",
                "temperature": 1.0,
                "top_p": 0.9,
                "repetition_penalty": 1.15,
                "edge_voice": "en-US-JennyNeural",
                "rate": "+10%",
                "pitch": "-10Hz",
                "static_level": -16,
                "stutter_probability": 0.0,
                "bitrate": "64k",
                "sample_rate": 16000,
            },
            {
                "name": "robotic_glitchy_heavy",
                "description": "Glitchy robotic voice - heavy static and stuttering",
                "temperature": 1.3,
                "top_p": 0.95,
                "repetition_penalty": 1.4,
                "edge_voice": "en-US-GuyNeural",
                "rate": "+30%",
                "pitch": "-25Hz",
                "static_level": -8,  # Much louder static
                "stutter_probability": 0.15,  # 15% chance of stutter per word
                "bitrate": "48k",  # Lower quality for more artifacts
                "sample_rate": 11025,
            },
            {
                "name": "robotic_damaged_transmission",
                "description": "Damaged transmission - heavy interference and frequent stuttering",
                "temperature": 1.2,
                "top_p": 0.92,
                "repetition_penalty": 1.35,
                "edge_voice": "en-US-EricNeural",
                "rate": "+15%",
                "pitch": "-18Hz",
                "static_level": -10,
                "stutter_probability": 0.25,  # Heavy stuttering
                "bitrate": "40k",
                "sample_rate": 11025,
            },
            {
                "name": "robotic_corrupted_ai_ultra",
                "description": "Ultra robotic corrupted AI - heavy glitches and static",
                "temperature": 1.4,
                "top_p": 0.96,
                "repetition_penalty": 1.45,
                "edge_voice": "en-US-ChristopherNeural",
                "rate": "+20%",
                "pitch": "-18Hz",
                "static_level": -6,  # Much louder static
                "stutter_probability": 0.25,  # More stuttering
                "bitrate": "32k",  # Lower quality
                "sample_rate": 8000,  # Much lower sample rate
                "static_probability_override": 0.15,  # 15% of audio gets static
            },
            {
                "name": "robotic_corrupted_ai_variant1",
                "description": "Corrupted AI variant - fast with heavy artifacts",
                "temperature": 1.5,
                "top_p": 0.95,
                "repetition_penalty": 1.5,
                "edge_voice": "en-US-ChristopherNeural",
                "rate": "+30%",
                "pitch": "-20Hz",
                "static_level": -7,
                "stutter_probability": 0.22,
                "bitrate": "32k",
                "sample_rate": 8000,
                "static_probability_override": 0.12,
            },
            {
                "name": "robotic_corrupted_ai_variant2",
                "description": "Corrupted AI variant - deep voice heavy static",
                "temperature": 1.3,
                "top_p": 0.94,
                "repetition_penalty": 1.4,
                "edge_voice": "en-US-GuyNeural",
                "rate": "+15%",
                "pitch": "-25Hz",
                "static_level": -5,  # Very loud static
                "stutter_probability": 0.28,
                "bitrate": "32k",
                "sample_rate": 8000,
                "static_probability_override": 0.18,  # 18% static
            },
            {
                "name": "robotic_corrupted_ai_variant3",
                "description": "Corrupted AI variant - authoritative with interference",
                "temperature": 1.2,
                "top_p": 0.93,
                "repetition_penalty": 1.42,
                "edge_voice": "en-US-EricNeural",
                "rate": "+18%",
                "pitch": "-22Hz",
                "static_level": -8,
                "stutter_probability": 0.20,
                "bitrate": "40k",
                "sample_rate": 11025,
                "static_probability_override": 0.10,
            },
            {
                "name": "robotic_corrupted_ai_variant4",
                "description": "Corrupted AI variant - ultra compressed transmission",
                "temperature": 1.45,
                "top_p": 0.97,
                "repetition_penalty": 1.48,
                "edge_voice": "en-US-ChristopherNeural",
                "rate": "+25%",
                "pitch": "-15Hz",
                "static_level": -6,
                "stutter_probability": 0.24,
                "bitrate": "24k",  # Very low quality
                "sample_rate": 8000,
                "static_probability_override": 0.14,
            },
            {
                "name": "robotic_corrupted_ai_variant5",
                "description": "Corrupted AI variant - slow corrupted processing",
                "temperature": 1.35,
                "top_p": 0.92,
                "repetition_penalty": 1.43,
                "edge_voice": "en-US-GuyNeural",
                "rate": "+10%",
                "pitch": "-28Hz",
                "static_level": -7,
                "stutter_probability": 0.26,
                "bitrate": "32k",
                "sample_rate": 8000,
                "static_probability_override": 0.13,
            },
            {
                "name": "robotic_deep_corrupted",
                "description": "Deep corrupted voice - low pitch with moderate static",
                "temperature": 0.7,
                "top_p": 0.82,
                "repetition_penalty": 1.25,
                "edge_voice": "en-US-GuyNeural",
                "rate": "-10%",
                "pitch": "-30Hz",
                "static_level": -13,
                "stutter_probability": 0.10,
                "bitrate": "56k",
                "sample_rate": 12000,
            },
            {
                "name": "robotic_android_malfunction",
                "description": "Android malfunction - synthetic female with stutters",
                "temperature": 1.1,
                "top_p": 0.88,
                "repetition_penalty": 1.3,
                "edge_voice": "en-US-JennyNeural",
                "rate": "+5%",
                "pitch": "-8Hz",
                "static_level": -14,
                "stutter_probability": 0.18,
                "bitrate": "56k",
                "sample_rate": 16000,
            },
            {
                "name": "robotic_emergency_broadcast",
                "description": "Emergency broadcast - military style with light static",
                "temperature": 0.6,
                "top_p": 0.78,
                "repetition_penalty": 1.15,
                "edge_voice": "en-US-EricNeural",
                "rate": "+0%",
                "pitch": "-22Hz",
                "static_level": -17,
                "stutter_probability": 0.05,  # Minimal stuttering
                "bitrate": "64k",
                "sample_rate": 16000,
            },
        ]

        # Select N presets based on count
        selected_presets = tuning_presets[:count]

        # Generate TTS for each preset
        results = []
        for i, preset in enumerate(selected_presets, 1):
            self.stdout.write(f"\n[{i}/{len(selected_presets)}] Generating: {preset['name']}")
            self.stdout.write(f"Description: {preset['description']}")
            self.stdout.write(f"Voice: {preset['edge_voice']} (rate: {preset['rate']})")
            self.stdout.write(
                f"Orpheus settings: temp={preset['temperature']}, top_p={preset['top_p']}, "
                f"rep_penalty={preset['repetition_penalty']}"
            )

            # Format prompt for Orpheus TTS with voice tag
            # Orpheus uses special format: <|{voice}|>{text}<|eot_id|>
            prompt = f"<|{voice}|>{text}<|eot_id|>"

            # Generate TTS using Ollama generate API
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={
                    "temperature": preset["temperature"],
                    "top_p": preset["top_p"],
                    "repetition_penalty": preset["repetition_penalty"],
                    "num_predict": 2048,  # Max tokens for audio generation
                },
            )

            # Save the response to a text file (contains audio tokens/phonemes)
            tokens_filename = f"sample_{i:02d}_{preset['name']}_tokens.txt"
            tokens_path = output_path / tokens_filename

            # Write the generated tokens/response
            with tokens_path.open("w") as f:
                if isinstance(response, dict) and "response" in response:
                    f.write(response["response"])
                else:
                    f.write(str(response))

            self.stdout.write(self.style.SUCCESS(f"✓ Tokens saved to: {tokens_filename}"))

            # Generate playable audio using edge-tts
            audio_filename = f"sample_{i:02d}_{preset['name']}.mp3"
            audio_path = output_path / audio_filename

            self.stdout.write(f"  Generating playable audio with edge-tts ({preset['edge_voice']})...")

            async def generate_audio(
                text_content: str, output_file: Path, edge_voice: str, rate: str, pitch: str | None = None
            ) -> None:
                """Generate TTS audio using edge-tts with custom voice and rate."""
                # Build SSML-like rate/pitch modifiers
                communicate_text = text_content
                if pitch:
                    communicate = edge_tts.Communicate(communicate_text, edge_voice, rate=rate, pitch=pitch)
                else:
                    communicate = edge_tts.Communicate(communicate_text, edge_voice, rate=rate)
                await communicate.save(str(output_file))

            try:
                # Initialize random generator
                rng = np.random.default_rng()

                # Apply stuttering effect to text if needed
                stutter_prob = preset.get("stutter_probability", 0.0)
                processed_text = text

                if stutter_prob > 0:
                    self.stdout.write(f"  Adding stuttering effect (probability: {stutter_prob:.0%})...")
                    words = text.split()
                    stuttered_words = []
                    for word in words:
                        stuttered_words.append(word)
                        # Random chance to stutter
                        if rng.random() < stutter_prob:
                            # Repeat first syllable or first few letters
                            if len(word) > MIN_WORD_LENGTH_FOR_STUTTER:
                                stutter_part = word[:2] + "-"
                                stuttered_words[-1] = stutter_part + stutter_part + word
                            else:
                                stuttered_words[-1] = word + "-" + word
                    processed_text = " ".join(stuttered_words)
                    self.stdout.write(f"    Stuttered {sum(1 for w in stuttered_words if '-' in w)} words")

                pitch_value = preset.get("pitch", None)
                asyncio.run(
                    generate_audio(processed_text, audio_path, preset["edge_voice"], preset["rate"], pitch_value)
                )

                # Add static noise and effects to make it more robotic
                static_level = preset.get("static_level", -15)
                sample_rate = preset.get("sample_rate", 16000)
                bitrate = preset.get("bitrate", "64k")
                # Use override if specified, otherwise random 5-10%
                static_probability = preset.get("static_probability_override", rng.uniform(0.05, 0.10))

                self.stdout.write(
                    f"  Adding robotic effects (static: {static_level}dB in {static_probability:.0%} of audio, "
                    f"rate: {sample_rate}Hz, bitrate: {bitrate})..."
                )

                # Load the audio
                audio = AudioSegment.from_mp3(str(audio_path))

                # Apply static intermittently (only to 5-10% of audio chunks)
                chunk_duration_ms = 200  # 200ms chunks for static application
                chunks = []
                static_chunks_count = 0

                for chunk_start in range(0, len(audio), chunk_duration_ms):
                    chunk = audio[chunk_start : chunk_start + chunk_duration_ms]

                    # Random chance to add static to this chunk
                    if rng.random() < static_probability:
                        # Generate noise for this chunk only
                        noise = WhiteNoise().to_audio_segment(duration=len(chunk))
                        # Mix chunk with noise
                        chunk = chunk.overlay(noise + static_level)
                        static_chunks_count += 1

                    chunks.append(chunk)

                robotic_audio = sum(chunks) if chunks else audio
                self.stdout.write(
                    f"    Applied static to {static_chunks_count} chunks "
                    f"({static_chunks_count * chunk_duration_ms}ms total)"
                )

                # Apply quality reduction based on preset for more "digital" artifacts
                robotic_audio = robotic_audio.set_frame_rate(sample_rate)

                # For glitchy presets, add random volume drops (simulating signal loss)
                if stutter_prob > STUTTER_THRESHOLD_FOR_GLITCH:  # Only for heavy stutter presets
                    self.stdout.write("  Adding glitch effects (random volume drops)...")
                    # Split audio into chunks and randomly reduce volume
                    chunk_duration_ms = 100  # 100ms chunks
                    chunks = []
                    for chunk_start in range(0, len(robotic_audio), chunk_duration_ms):
                        chunk = robotic_audio[chunk_start : chunk_start + chunk_duration_ms]
                        # Random chance of volume drop
                        if rng.random() < VOLUME_DROP_PROBABILITY:
                            chunk = chunk - 8  # Reduce volume by 8dB
                        chunks.append(chunk)
                    robotic_audio = sum(chunks) if chunks else robotic_audio

                # Export with preset's bitrate for varied compression artifacts
                robotic_audio.export(str(audio_path), format="mp3", bitrate=bitrate)

                self.stdout.write(self.style.SUCCESS(f"✓ Audio with effects saved to: {audio_filename}"))
                audio_status = "success"
            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f"✗ Audio generation failed: {e}"))
                audio_status = "failed"
                audio_path = None

            results.append(
                {
                    "sample_number": i,
                    "preset_name": preset["name"],
                    "description": preset["description"],
                    "orpheus_settings": {
                        "temperature": preset["temperature"],
                        "top_p": preset["top_p"],
                        "repetition_penalty": preset["repetition_penalty"],
                    },
                    "edge_tts_settings": {
                        "voice": preset["edge_voice"],
                        "rate": preset["rate"],
                        "pitch": preset.get("pitch", "default"),
                    },
                    "robotic_effects": {
                        "static_level": preset.get("static_level", -15),
                        "stutter_probability": preset.get("stutter_probability", 0.0),
                        "bitrate": preset.get("bitrate", "64k"),
                        "sample_rate": preset.get("sample_rate", 16000),
                    },
                    "orpheus_voice": voice,
                    "tokens_file": str(tokens_path),
                    "audio_file": str(audio_path) if audio_path else None,
                    "audio_status": audio_status,
                    "status": "success",
                }
            )

        # Save results summary
        summary_path = output_path / "generation_summary.json"
        note_text = (
            "Each sample uses a different voice and settings for variety. "
            "Features include: variable static levels, stuttering effects, "
            "glitch simulation (random volume drops), and quality reduction. "
            "Orpheus tokens are for reference; MP3 files use edge-tts with "
            "varied voices, rates, pitch, and robotic effects."
        )
        with summary_path.open("w") as f:
            json.dump(
                {
                    "model": model,
                    "orpheus_voice": voice,
                    "text": text,
                    "total_samples": len(selected_presets),
                    "results": results,
                    "note": note_text,
                },
                f,
                indent=2,
            )

        self.stdout.write(f"\n{self.style.SUCCESS('=== Generation Complete ===')}")
        self.stdout.write(f"Total samples: {len(results)}")
        self.stdout.write(f"Summary saved to: {summary_path}")
