"""Tests for Whisper fine-tune dataset helpers."""
import json
from pathlib import Path

from services.whisper_finetune import (
    collection_enabled,
    finetuned_model_dir,
    manifest_stats,
    resolve_whisper_model_name,
    save_finetune_sample,
    socialfetch_transcript_enabled,
)


def test_save_and_stats(tmp_path, monkeypatch):
    monkeypatch.setenv("WHISPER_FINETUNE_DIR", str(tmp_path / "ft"))
    monkeypatch.delenv("WHISPER_FINETUNED_DIR", raising=False)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFFxxxxWAVEfmt " + b"\x00" * 2000)

    rec = save_finetune_sample(
        audio_wav_path=wav,
        label_text="100 grams cucumber and sriracha",
        url="https://www.instagram.com/reel/Dc52em2IvQz/",
        whisper_text="100 grams cucumber and saranch",
        socialfetch_text="100 grams cucumber and sriracha",
        label_source="socialfetch",
    )
    assert rec and rec["id"]
    stats = manifest_stats()
    assert stats["samples"] == 1
    assert stats["by_source"]["socialfetch"] == 1
    assert (tmp_path / "ft" / "audio" / f"{rec['id']}.wav").exists()


def test_bootstrap_gates(monkeypatch, tmp_path):
    monkeypatch.setenv("WHISPER_FINETUNE_DIR", str(tmp_path / "ft"))
    monkeypatch.delenv("WHISPER_FINETUNED_DIR", raising=False)
    monkeypatch.setenv("SOCIALFETCH_TRANSCRIPT", "bootstrap")
    monkeypatch.setenv("WHISPER_FINETUNE_COLLECT", "auto")
    assert collection_enabled() is True
    assert socialfetch_transcript_enabled(whisper_chars=50, caption_is_recipe=False) is True

    # Simulate trained model present
    ct2 = tmp_path / "ft" / "models" / "ct2-cooking"
    ct2.mkdir(parents=True)
    (ct2 / "model.bin").write_text("x")
    monkeypatch.setenv("WHISPER_FINETUNE_COLLECT", "auto")
    assert finetuned_model_dir() is not None
    assert collection_enabled() is False
    assert socialfetch_transcript_enabled(whisper_chars=50, caption_is_recipe=False) is False
    assert resolve_whisper_model_name() == str(ct2)
