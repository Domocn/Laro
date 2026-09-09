"""
Cooking-reel Whisper fine-tune dataset + model path helpers.

Goal: bootstrap labels with SocialFetch transcripts (paid, temporary), then
fine-tune a local Whisper so production stops calling SocialFetch for speech.

Dataset layout (UPLOAD_DIR/whisper-finetune/):
  audio/<sample_id>.wav
  manifest.jsonl   — one JSON object per line
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def dataset_root() -> Path:
    base = os.getenv("WHISPER_FINETUNE_DIR", "").strip()
    if base:
        root = Path(base)
    else:
        root = Path(os.getenv("UPLOAD_DIR", "uploads")) / "whisper-finetune"
    (root / "audio").mkdir(parents=True, exist_ok=True)
    return root


def finetuned_model_dir() -> Optional[Path]:
    """
    Directory of a CTranslate2 / faster-whisper model produced by training.

    Set WHISPER_FINETUNED_DIR, or use <dataset>/models/ct2-cooking when present.
    """
    explicit = (os.getenv("WHISPER_FINETUNED_DIR") or "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(dataset_root() / "models" / "ct2-cooking")
    for path in candidates:
        if path.is_dir() and any(path.iterdir()):
            return path
    return None


def resolve_whisper_model_name() -> str:
    """Prefer fine-tuned local model so we can drop SocialFetch transcripts."""
    tuned = finetuned_model_dir()
    if tuned is not None:
        return str(tuned)
    return (os.getenv("WHISPER_LOCAL_MODEL") or "base.en").strip() or "base.en"


def collection_enabled() -> bool:
    """
    Save audio + label pairs for fine-tuning.

    Default: on when no fine-tuned model is loaded yet (bootstrap phase).
    Set WHISPER_FINETUNE_COLLECT=0 to disable; =1 to force.
    """
    flag = (os.getenv("WHISPER_FINETUNE_COLLECT") or "auto").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # auto: collect until a fine-tuned model exists
    return finetuned_model_dir() is None


def socialfetch_transcript_enabled(*, whisper_chars: int = 0, caption_is_recipe: bool = True) -> bool:
    """
    Paid SocialFetch transcript — bootstrap labels only.

    Modes (SOCIALFETCH_TRANSCRIPT):
      off / 0     — never
      always / 1  — always (expensive)
      bootstrap   — only while collecting / no fine-tuned model (default)
      auto        — bootstrap OR weak local transcript on audio-primary reels
    """
    mode = (os.getenv("SOCIALFETCH_TRANSCRIPT") or "bootstrap").strip().lower()
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on", "always"):
        return True
    has_tuned = finetuned_model_dir() is not None
    if mode in ("bootstrap", "train", "collect"):
        return collection_enabled() and not has_tuned
    # auto
    if has_tuned and not collection_enabled():
        return False
    if collection_enabled() and not has_tuned:
        return True
    if caption_is_recipe:
        return False
    return whisper_chars < 400


def _sample_id(url: str, audio_bytes: bytes) -> str:
    h = hashlib.sha1()
    h.update((url or "").encode("utf-8", errors="ignore"))
    h.update(audio_bytes[:65536])
    return h.hexdigest()[:16]


def save_finetune_sample(
    *,
    audio_wav_path: Path,
    label_text: str,
    url: str = "",
    import_id: str = "",
    whisper_text: str = "",
    socialfetch_text: str = "",
    label_source: str = "socialfetch",
    platform: str = "",
    extra: Optional[dict] = None,
) -> Optional[dict[str, Any]]:
    """
    Persist one (audio, transcript) pair. ``label_text`` is the training target
    (prefer SocialFetch or human-corrected text over raw Whisper).
    """
    label = (label_text or "").strip()
    if not label or not audio_wav_path.exists():
        return None
    try:
        audio_bytes = audio_wav_path.read_bytes()
    except Exception as e:
        logger.warning("whisper finetune: cannot read audio: %s", e)
        return None
    if len(audio_bytes) < 1000:
        return None

    sid = _sample_id(url, audio_bytes)
    root = dataset_root()
    dest = root / "audio" / f"{sid}.wav"
    manifest = root / "manifest.jsonl"

    record = {
        "id": sid,
        "audio": f"audio/{sid}.wav",
        "text": label,
        "url": url or "",
        "import_id": import_id or "",
        "whisper_text": (whisper_text or "")[:8000],
        "socialfetch_text": (socialfetch_text or "")[:8000],
        "label_source": label_source,
        "platform": platform or "",
        "duration_hint_bytes": len(audio_bytes),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

    with _lock:
        if not dest.exists():
            shutil.copy2(audio_wav_path, dest)
        # Upsert: rewrite manifest line with same id if present
        lines: list[str] = []
        if manifest.exists():
            for line in manifest.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    lines.append(line)
                    continue
                if row.get("id") == sid:
                    continue
                lines.append(line)
        lines.append(json.dumps(record, ensure_ascii=False))
        manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

    logger.info(
        "whisper finetune sample saved id=%s source=%s chars=%s",
        sid,
        label_source,
        len(label),
    )
    return record


def manifest_stats() -> dict[str, Any]:
    root = dataset_root()
    manifest = root / "manifest.jsonl"
    n = 0
    by_source: dict[str, int] = {}
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            n += 1
            src = row.get("label_source") or "unknown"
            by_source[src] = by_source.get(src, 0) + 1
    return {
        "root": str(root),
        "samples": n,
        "by_source": by_source,
        "finetuned_model": str(finetuned_model_dir() or ""),
        "collection_enabled": collection_enabled(),
    }


def attach_corrected_label(
    *,
    import_id: str,
    corrected_text: str,
) -> bool:
    """
    If a sample was stored for this import_id, upgrade its training label
    from a user correction (best signal).
    """
    text = (corrected_text or "").strip()
    if not import_id or not text:
        return False
    root = dataset_root()
    manifest = root / "manifest.jsonl"
    if not manifest.exists():
        return False
    updated = False
    lines: list[str] = []
    with _lock:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                lines.append(line)
                continue
            if row.get("import_id") == import_id:
                row["text"] = text
                row["label_source"] = "user_correction"
                row["corrected_at"] = datetime.now(timezone.utc).isoformat()
                updated = True
            lines.append(json.dumps(row, ensure_ascii=False))
        if updated:
            manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated
