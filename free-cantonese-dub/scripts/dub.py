"""Free Cantonese dub: download, transcribe, then render spoken audio and written subtitles."""

import argparse
import asyncio
import json
import re
import subprocess
import sys
import wave
from pathlib import Path

import av
import edge_tts
import imageio_ffmpeg
import numpy as np
from faster_whisper import WhisperModel

_av_open = av.open


def _open_compat(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return _av_open(*args, **kwargs)


av.open = _open_compat

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SAMPLE_RATE = 44100
MAX_TEMPO = 1.55
SUBTITLE_STYLE = (
    "FontName=Microsoft JhengHei,FontSize=22,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00111111,BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=32"
)


def run(args: list[str], cwd: Path | None = None) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace")[-2000:]
        raise RuntimeError(message or f"command failed: {args[0]}")


def duration_seconds(media: Path) -> float:
    result = subprocess.run([FFMPEG, "-i", str(media)], capture_output=True)
    text = result.stderr.decode("utf-8", "replace")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        raise RuntimeError(f"could not read duration of {media}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    if millis == 1000:
        whole += 1
        millis = 0
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    current = ""
    for char in text.strip():
        current += char
        if char in "。？！":
            sentence = current.strip()
            if sentence:
                sentences.append(sentence)
            current = ""
    leftover = current.strip()
    if leftover:
        raise RuntimeError(f"subtitle is not a complete sentence: {leftover}")
    if not sentences:
        raise RuntimeError("subtitle is empty")
    return sentences


def download(url: str, workdir: Path) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    source = workdir / "source.mp4"
    run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--ffmpeg-location",
            FFMPEG,
            "-f",
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b",
            "--merge-output-format",
            "mp4",
            "-o",
            str(source),
            url,
        ]
    )
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(workdir / "audio.wav"),
        ]
    )
    print(f"DOWNLOADED {source}", flush=True)


def transcribe(workdir: Path, language: str) -> None:
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(workdir / "audio.wav"),
        language=language,
        vad_filter=True,
        beam_size=5,
    )
    rows = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        row = {"start": round(segment.start, 2), "end": round(segment.end, 2), "text": text}
        rows.append(row)
        print(f"{row['start']:.2f}-{row['end']:.2f} {text}", flush=True)
    out = workdir / "segments.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {len(rows)} {out}", flush=True)


def group(workdir: Path) -> None:
    segments = json.loads((workdir / "segments.json").read_text(encoding="utf-8"))
    chunks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for segment in segments:
        if current is None:
            current = {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
            continue
        gap = float(segment["start"]) - float(current["end"])
        span = float(segment["end"]) - float(current["start"])
        if gap < 0.45 and span <= 9.5:
            current["end"] = segment["end"]
            current["text"] = f"{current['text']} {segment['text']}".strip()
        else:
            chunks.append(current)
            current = {"start": segment["start"], "end": segment["end"], "text": segment["text"]}
    if current is not None:
        chunks.append(current)
    out = workdir / "chunks.json"
    out.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {len(chunks)} {out}", flush=True)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2 or handle.getframerate() != SAMPLE_RATE:
            raise RuntimeError(f"unexpected wav format: {path}")
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path: Path, samples: np.ndarray) -> None:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())


def to_wav(src: Path, dest: Path, tempo: float) -> None:
    filters = ["aresample=44100", "pan=mono|c0=c0"]
    if abs(tempo - 1.0) > 0.03:
        remaining = tempo
        while remaining > 2.0:
            filters.append("atempo=2.0")
            remaining /= 2.0
        filters.append(f"atempo={remaining:.4f}")
    run([FFMPEG, "-y", "-i", str(src), "-af", ",".join(filters), str(dest)])


async def synthesize(cues: list[dict[str, object]], folder: Path, voice: str, rate: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(4)

    async def one(index: int, text: str) -> None:
        path = folder / f"{index:03d}.mp3"
        async with semaphore:
            if not path.exists() or path.stat().st_size < 800:
                await edge_tts.Communicate(text, voice, rate=rate).save(str(path))
            print(f"tts {index:03d}", flush=True)

    await asyncio.gather(*(one(index, str(cue["spoken"])) for index, cue in enumerate(cues)))


def build_srt(cues: list[dict[str, object]]) -> str:
    lines: list[str] = []
    index = 1
    for cue in cues:
        start = float(cue["start"])
        end = float(cue["end"])
        sentences = split_sentences(str(cue["written"]))
        weights = [max(1, len(sentence)) for sentence in sentences]
        total = sum(weights)
        cursor = start
        span = max(0.2, end - start)
        for sentence, weight in zip(sentences, weights):
            piece = span * weight / total
            cue_end = min(end, cursor + piece)
            lines.extend([str(index), f"{srt_time(cursor)} --> {srt_time(cue_end)}", sentence, ""])
            index += 1
            cursor += piece
    return "\n".join(lines)


def render(workdir: Path, cues_path: Path, output: Path, voice: str, rate: str) -> None:
    cues = json.loads(cues_path.read_text(encoding="utf-8"))
    if not isinstance(cues, list) or not cues:
        raise RuntimeError("cues file must be a non-empty list")
    source = workdir / "source.mp4"
    video_seconds = duration_seconds(source)
    clip_dir = workdir / "clips"
    wav_dir = workdir / "wavs"
    wav_dir.mkdir(parents=True, exist_ok=True)
    asyncio.run(synthesize(cues, clip_dir, voice, rate))

    total = int(video_seconds * SAMPLE_RATE)
    mix = np.zeros(total, dtype=np.float32)
    for index, cue in enumerate(cues):
        start = float(cue["start"])
        next_start = float(cues[index + 1]["start"]) if index + 1 < len(cues) else video_seconds
        slot = max(0.8, next_start - start - 0.08)
        raw = clip_dir / f"{index:03d}.mp3"
        fitted = wav_dir / f"{index:03d}.wav"
        to_wav(raw, fitted, 1.0)
        audio = read_wav(fitted)
        slot_samples = int(slot * SAMPLE_RATE)
        tempo = 1.0
        if len(audio) > slot_samples:
            tempo = min(MAX_TEMPO, len(audio) / slot_samples)
            to_wav(raw, fitted, tempo)
            audio = read_wav(fitted)
            if len(audio) > slot_samples:
                audio = audio[:slot_samples]
        begin = int(start * SAMPLE_RATE)
        finish = min(total, begin + len(audio))
        mix[begin:finish] += audio[: finish - begin]
        print(f"fit {index:03d} tempo={tempo:.2f} slot={slot:.1f}s", flush=True)

    peak = float(np.max(np.abs(mix))) or 1.0
    if peak > 0.98:
        mix *= 0.98 / peak
    voice_wav = workdir / "cantonese.wav"
    write_wav(voice_wav, mix)
    srt_path = workdir / "written.srt"
    srt_path.write_text(build_srt(cues), encoding="utf-8")

    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(source),
            "-i",
            str(voice_wav),
            "-vf",
            f"subtitles={srt_path.name}:force_style='{SUBTITLE_STYLE}'",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(output),
        ],
        cwd=workdir,
    )
    print(f"BURNED {output}", flush=True)


def parser() -> argparse.ArgumentParser:
    commands = argparse.ArgumentParser(description="Free Hong Kong Cantonese dub")
    sub = commands.add_subparsers(dest="command", required=True)

    download_cmd = sub.add_parser("download")
    download_cmd.add_argument("url")
    download_cmd.add_argument("--workdir", type=Path, required=True)

    transcribe_cmd = sub.add_parser("transcribe")
    transcribe_cmd.add_argument("--workdir", type=Path, required=True)
    transcribe_cmd.add_argument("--language", default="en")

    group_cmd = sub.add_parser("group")
    group_cmd.add_argument("--workdir", type=Path, required=True)

    render_cmd = sub.add_parser("render")
    render_cmd.add_argument("--workdir", type=Path, required=True)
    render_cmd.add_argument("--cues", type=Path, required=True)
    render_cmd.add_argument("--out", type=Path, required=True)
    render_cmd.add_argument("--voice", default="zh-HK-WanLungNeural")
    render_cmd.add_argument("--rate", default="+12%")
    return commands


def main() -> None:
    args = parser().parse_args()
    if args.command == "download":
        download(args.url, args.workdir)
    elif args.command == "transcribe":
        transcribe(args.workdir, args.language)
    elif args.command == "group":
        group(args.workdir)
    elif args.command == "render":
        render(args.workdir, args.cues, args.out, args.voice, args.rate)
    else:
        raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
