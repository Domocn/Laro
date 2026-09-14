"""
Import recipes from uploaded social/cooking videos.

Flow:
1. Optional caption (strongly recommended for login-walled apps)
2. Optional video file → extract audio with ffmpeg → Whisper transcript (if OPENAI_API_KEY)
3. Combine caption + transcript → LLM recipe extraction
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-m4v",
    "video/mpeg",
    "application/octet-stream",  # some Android shares
}

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mpeg", ".mpg", ".mkv"}

MAX_VIDEO_BYTES = 80 * 1024 * 1024  # 80 MB


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


async def extract_audio_wav(video_path: Path, audio_path: Path) -> bool:
    """Extract mono 16kHz WAV for Whisper. Returns False if ffmpeg missing/fails."""
    if not ffmpeg_available():
        logger.warning("ffmpeg not installed — cannot transcribe video audio")
        return False

    def _run() -> bool:
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-f",
                    "wav",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            return audio_path.exists() and audio_path.stat().st_size > 0
        except Exception as e:
            logger.warning("ffmpeg audio extract failed: %s", e)
            return False

    return await asyncio.to_thread(_run)


async def transcribe_with_openai_whisper(audio_path: Path, api_key: str) -> Optional[str]:
    """Call OpenAI Whisper API. Returns transcript text or None."""

    def _upload() -> Optional[str]:
        try:
            with audio_path.open("rb") as f:
                resp = httpx.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (audio_path.name, f, "audio/wav")},
                    data={"model": "whisper-1", "response_format": "text"},
                    timeout=180.0,
                )
            if resp.status_code >= 400:
                logger.warning("Whisper API error %s: %s", resp.status_code, resp.text[:300])
                return None
            text = (resp.text or "").strip()
            return text or None
        except Exception as e:
            logger.warning("Whisper transcription failed: %s", e)
            return None

    return await asyncio.to_thread(_upload)


_whisper_models: dict[tuple[str, str, str], object] = {}

# Common Whisper mishears on cooking reels (cheap regex cleanup — no extra LLM).
_COOKING_TRANSCRIPT_FIXES: tuple[tuple[str, str], ...] = (
    (r"\bchinese\s+fire(?:\s*spice)?\b", "Chinese five-spice"),
    (r"\bchinese\s+firespice\b", "Chinese five-spice"),
    (r"\bKim%%\b", "kimchi"),
    (r"\bkim\s*%%\b", "kimchi"),
    (r"\bsaranch(?:a|it)?\b", "sriracha"),
    (r"\bsrirach(?:a|it)\b", "sriracha"),
    (r"\bgut\s+health\b", "gut health"),
)


def resolve_whisper_model_name() -> str:
    """Prefer fine-tuned CT2 model when present (see services.whisper_finetune)."""
    try:
        from services.whisper_finetune import resolve_whisper_model_name as _resolve

        return _resolve()
    except Exception:
        return (os.getenv("WHISPER_LOCAL_MODEL") or "base.en").strip() or "base.en"


def cleanup_cooking_transcript(text: str) -> str:
    """Fix frequent cooking-reel Whisper glitches without calling an LLM."""
    import re

    out = (text or "").strip()
    if not out:
        return ""
    fixes = list(_COOKING_TRANSCRIPT_FIXES)
    try:
        from services.import_learning import load_learned_transcript_fixes

        fixes.extend(load_learned_transcript_fixes())
    except Exception:
        pass
    for pat, repl in fixes:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def _get_local_whisper_model(model_name: str, device: str, compute: str):
    """Reuse loaded faster-whisper models across reel imports (cheap after first load)."""
    key = (model_name, device, compute)
    cached = _whisper_models.get(key)
    if cached is not None:
        return cached
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device=device, compute_type=compute)
    _whisper_models[key] = model
    return model


async def transcribe_with_local_whisper(
    audio_path: Path,
    *,
    model_name: Optional[str] = None,
    beam_size: Optional[int] = None,
) -> Optional[str]:
    """
    Offline Whisper via faster-whisper when OPENAI_API_KEY is unset.

    Default model is ``base.en`` (still free/local) so spoken grams on cooking reels
    are usable without an OpenAI key. Override with WHISPER_LOCAL_MODEL.

    Uses a soft VAD pad so finishing garnishes / air-fryer times at the end of
    cooking reels are not clipped (aggressive VAD was dropping cucumber / 180°C).
    """
    enabled = (os.getenv("WHISPER_LOCAL") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    if not enabled:
        return None

    def _run() -> Optional[str]:
        try:
            from faster_whisper import WhisperModel  # noqa: F401 — availability check
        except Exception as e:
            logger.info("faster-whisper unavailable: %s", e)
            return None
        name = (
            (model_name or "").strip()
            or resolve_whisper_model_name()
        )
        device = (os.getenv("WHISPER_LOCAL_DEVICE") or "cpu").strip() or "cpu"
        compute = (os.getenv("WHISPER_LOCAL_COMPUTE") or "int8").strip() or "int8"
        beam = beam_size
        if beam is None:
            try:
                beam = int((os.getenv("WHISPER_LOCAL_BEAM") or "3").strip() or "3")
            except ValueError:
                beam = 3
        beam = max(1, min(beam, 5))
        # Soft VAD: keep end-of-reel garnish / temp lines that default VAD clipped.
        vad_mode = (os.getenv("WHISPER_LOCAL_VAD") or "soft").strip().lower() or "soft"
        use_vad = vad_mode not in ("0", "false", "no", "off")
        vad_parameters = None
        if use_vad and vad_mode != "strict":
            vad_parameters = {
                "min_silence_duration_ms": 800,
                "speech_pad_ms": 400,
            }
        try:
            model = _get_local_whisper_model(name, device, compute)
            kwargs = {
                "language": "en",
                "vad_filter": use_vad,
                "beam_size": beam,
            }
            if vad_parameters is not None:
                kwargs["vad_parameters"] = vad_parameters
            segments, _info = model.transcribe(str(audio_path), **kwargs)
            parts = [seg.text.strip() for seg in segments if getattr(seg, "text", None)]
            text = cleanup_cooking_transcript(" ".join(p for p in parts if p))
            return text or None
        except Exception as e:
            logger.warning("Local Whisper transcription failed: %s", e)
            return None

    return await asyncio.to_thread(_run)


async def extract_keyframes_base64(
    media_bytes: bytes, ext: str = ".mp4", max_frames: int = 12
) -> list[str]:
    """
    Extract up to ``max_frames`` evenly-spaced JPEG keyframes from a video and return
    them base64-encoded. Recipe reels put ingredients/steps as on-screen text, which a
    vision model can read — this is the provider-agnostic path (works with whatever
    vision model is configured, not just OpenAI). Returns [] if ffmpeg is missing/fails.
    """
    import base64 as _b64

    if not media_bytes or not ffmpeg_available():
        if not ffmpeg_available():
            logger.warning("ffmpeg not installed — cannot extract video keyframes")
        return []
    if not ext.startswith("."):
        ext = "." + ext

    def _run() -> list[str]:
        frames: list[str] = []
        try:
            with tempfile.TemporaryDirectory(prefix="laro_frames_") as tmp:
                tmp_path = Path(tmp)
                media_path = tmp_path / f"input{ext}"
                media_path.write_bytes(media_bytes)
                # ~1 frame / 1.5s for cooking reels (spoken + on-screen amounts).
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", str(media_path),
                        "-vf", "fps=2/3,scale=768:-1",
                        "-frames:v", str(max_frames),
                        "-q:v", "5",
                        str(tmp_path / "frame_%03d.jpg"),
                    ],
                    check=True, capture_output=True, timeout=120,
                )
                for fp in sorted(tmp_path.glob("frame_*.jpg"))[:max_frames]:
                    frames.append(_b64.b64encode(fp.read_bytes()).decode("ascii"))
        except Exception as e:
            logger.warning("ffmpeg keyframe extraction failed: %s", e)
        return frames

    return await asyncio.to_thread(_run)


async def transcribe_media_bytes(
    media_bytes: bytes,
    ext: str = ".mp4",
    *,
    return_audio_path: bool = False,
) -> str | tuple[str, Optional[Path]]:
    """
    Transcribe already-downloaded media bytes (audio or video) via ffmpeg + Whisper.

    Used for social reels downloaded with yt-dlp in the URL-import path, where the
    recipe is spoken in the video rather than written in the caption. Returns "" when
    ffmpeg is missing, the bytes are empty, or transcription fails — callers should
    fall back to whatever text they already have.

    Order: OpenAI Whisper API (if OPENAI_API_KEY) → local faster-whisper
    (fine-tuned model preferred when WHISPER_FINETUNED_DIR is set).

    When ``return_audio_path`` is True, returns ``(text, Path|None)`` where the path
    is a temporary WAV kept for fine-tune collection (caller must delete).
    """
    if not media_bytes:
        return ("", None) if return_audio_path else ""
    if not ext.startswith("."):
        ext = "." + ext
    api_key = os.getenv("OPENAI_API_KEY") or ""

    # Keep WAV outside the temp dir when collecting so callers can copy it.
    keep_audio = return_audio_path
    tmp_keep: Optional[Path] = None
    with tempfile.TemporaryDirectory(prefix="laro_url_vid_") as tmp:
        tmp_path = Path(tmp)
        media_path = tmp_path / f"input{ext}"
        audio_path = tmp_path / "audio.wav"
        media_path.write_bytes(media_bytes)
        if not await extract_audio_wav(media_path, audio_path):
            return ("", None) if return_audio_path else ""
        if keep_audio:
            fd, keep_name = tempfile.mkstemp(prefix="laro_ft_", suffix=".wav")
            os.close(fd)
            tmp_keep = Path(keep_name)
            tmp_keep.write_bytes(audio_path.read_bytes())
        text = ""
        if api_key:
            text = (await transcribe_with_openai_whisper(audio_path, api_key)) or ""
        if not text:
            text = (await transcribe_with_local_whisper(audio_path)) or ""
        if return_audio_path:
            return text, tmp_keep
        if tmp_keep and tmp_keep.exists():
            tmp_keep.unlink(missing_ok=True)
        return text


async def build_recipe_source_text(
    *,
    caption: Optional[str],
    video_bytes: Optional[bytes],
    filename: Optional[str],
    content_type: Optional[str],
) -> tuple[str, dict]:
    """
    Build text for LLM recipe extraction from caption and/or uploaded video.

    Returns (combined_text, meta) where meta describes what sources were used.
    """
    caption = (caption or "").strip()
    meta = {
        "had_caption": bool(caption),
        "had_video": bool(video_bytes),
        "transcribed": False,
        "transcript_chars": 0,
        "ffmpeg": ffmpeg_available(),
    }

    transcript = ""
    if video_bytes:
        if len(video_bytes) > MAX_VIDEO_BYTES:
            raise ValueError(f"Video too large (max {MAX_VIDEO_BYTES // (1024 * 1024)} MB)")

        ext = Path(filename or "video.mp4").suffix.lower() or ".mp4"
        if ext not in ALLOWED_EXTENSIONS and (content_type or "") not in ALLOWED_VIDEO_TYPES:
            # Still allow if it looks like a video upload from mobile
            if not (content_type or "").startswith("video/"):
                raise ValueError("Unsupported file type. Upload mp4, mov, or webm.")

        api_key = os.getenv("OPENAI_API_KEY") or ""
        with tempfile.TemporaryDirectory(prefix="laro_vid_") as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / f"input{ext if ext in ALLOWED_EXTENSIONS else '.mp4'}"
            audio_path = tmp_path / "audio.wav"
            video_path.write_bytes(video_bytes)

            if await extract_audio_wav(video_path, audio_path):
                if api_key:
                    transcript = (await transcribe_with_openai_whisper(audio_path, api_key)) or ""
                if not transcript:
                    transcript = (await transcribe_with_local_whisper(audio_path)) or ""
                if transcript:
                    meta["transcribed"] = True
                    meta["transcript_chars"] = len(transcript)

    # Promo captions ("full recipe in the audio") must not outrank Whisper.
    caption_is_recipe = True
    if caption:
        try:
            from services.instagram_media import caption_looks_like_recipe

            caption_is_recipe = caption_looks_like_recipe(caption)
        except Exception:
            caption_is_recipe = True
    meta["caption_is_recipe"] = bool(caption_is_recipe)
    meta["audio_primary"] = bool(transcript and caption and not caption_is_recipe)

    parts: list[str] = []
    if caption:
        if transcript and not caption_is_recipe:
            parts.append(
                "Creator caption (promo/hashtags only — NOT the recipe; "
                "prefer the spoken transcript for all amounts):\n" + caption
            )
        else:
            parts.append("Creator caption / description:\n" + caption)
    if transcript:
        if caption and not caption_is_recipe:
            parts.append(
                "Spoken audio transcript (PRIMARY recipe source — caption has no ingredients):\n"
                + transcript
            )
        else:
            parts.append("Spoken audio transcript from the video:\n" + transcript)

    if not parts:
        raise ValueError(
            "Add the video caption (copy from TikTok/Instagram/YouTube) and/or upload an mp4. "
            "If the video is private/login-walled, paste the caption — that alone is enough."
        )

    combined = "\n\n".join(parts)
    # Soft cap for LLM prompt
    return combined[:12000], meta
