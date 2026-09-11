"""Generate a natural neural TTS track without logging credentials."""

from __future__ import annotations

import subprocess
from pathlib import Path

from openai import OpenAI

from householdos.config import Settings


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "output" / "video"
TRANSCRIPT = VIDEO_DIR / "HouseholdOS_TTS_Transcript.txt"
SEGMENTS = VIDEO_DIR / "neural_segments"
FFMPEG = next((ROOT / ".venv/lib/python3.14/site-packages/imageio_ffmpeg/binaries").glob("ffmpeg-*"))


def main() -> None:
    settings = Settings.from_env()
    if not settings.openai_api_key:
        raise SystemExit("OPENAI_API_KEY is required")
    client = OpenAI(api_key=settings.openai_api_key)
    paragraphs = [p.strip() for p in TRANSCRIPT.read_text().split("\n\n") if p.strip()]
    SEGMENTS.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    instructions = (
        "Speak like a warm, confident technical presenter explaining a project to peers. "
        "Use natural conversational phrasing, varied intonation, and brief pauses after key results. "
        "Avoid announcer style, exaggerated enthusiasm, and rushed delivery. Pronounce HouseholdOS "
        "as Household O S, LINE as line, SQLite as S Q Lite, and Pydantic as pie-dantic."
    )
    for index, paragraph in enumerate(paragraphs, 1):
        output = SEGMENTS / f"segment-{index:02d}.mp3"
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="cedar",
            input=paragraph,
            instructions=instructions,
            response_format="mp3",
            speed=1.0,
        ) as response:
            response.stream_to_file(output)
        files.append(output)
        print(f"Generated segment {index}/{len(paragraphs)}")
    concat = VIDEO_DIR / "neural_audio.concat.txt"
    concat.write_text("\n".join(f"file '{item.resolve()}'" for item in files) + "\n")
    final = VIDEO_DIR / "HouseholdOS_Natural_Neural_TTS.mp3"
    subprocess.run([
        str(FFMPEG), "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
        "-c:a", "libmp3lame", "-b:a", "192k", str(final),
    ], check=True)
    print(final)


if __name__ == "__main__":
    main()
