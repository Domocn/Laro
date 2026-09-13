#!/usr/bin/env python3
"""
Fine-tune Whisper on Laro cooking-reel transcripts, then convert for faster-whisper.

Bootstrap labels come from SocialFetch (paid, temporary). After training, set:
  WHISPER_FINETUNED_DIR=<dataset>/models/ct2-cooking
  SOCIALFETCH_TRANSCRIPT=off

Requires (install separately — not in production image by default):
  pip install -r requirements-whisper-finetune.txt

Example:
  cd backend
  ./venv/bin/python scripts/whisper_finetune_train.py \\
      --data-dir uploads/whisper-finetune \\
      --base-model openai/whisper-base.en \\
      --epochs 3

Then convert:
  ct2-transformers-converter --model uploads/whisper-finetune/models/hf-cooking \\
      --output_dir uploads/whisper-finetune/models/ct2-cooking \\
      --quantization int8 --copy_files tokenizer.json preprocessor_config.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_manifest(data_dir: Path) -> list[dict]:
    path = data_dir / "manifest.jsonl"
    if not path.exists():
        raise SystemExit(f"Missing {path} — import some audio-primary reels first")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        audio = data_dir / row["audio"]
        if audio.exists() and (row.get("text") or "").strip():
            rows.append({"audio": str(audio), "text": row["text"].strip(), "id": row.get("id")})
    if len(rows) < 5:
        raise SystemExit(
            f"Need at least ~5 labeled samples to fine-tune (have {len(rows)}). "
            "Keep SOCIALFETCH_TRANSCRIPT=bootstrap until the manifest grows."
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("uploads/whisper-finetune"))
    parser.add_argument("--base-model", default="openai/whisper-base.en")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--max-samples", type=int, default=0, help="0 = all")
    parser.add_argument("--dry-run", action="store_true", help="Validate dataset only")
    args = parser.parse_args()

    rows = load_manifest(args.data_dir)
    if args.max_samples:
        rows = rows[: args.max_samples]
    out = args.output_dir or (args.data_dir / "models" / "hf-cooking")
    print(f"samples={len(rows)} base={args.base_model} out={out}")

    if args.dry_run:
        for r in rows[:5]:
            print(f"  {r['id']}: {r['text'][:80]!r}…")
        print("dry-run ok")
        return 0

    try:
        import torch
        from datasets import Dataset
        from transformers import (
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
            WhisperForConditionalGeneration,
            WhisperProcessor,
        )
    except ImportError as e:
        print(
            "Missing fine-tune deps. Install with:\n"
            "  pip install -r requirements-whisper-finetune.txt\n"
            f"Detail: {e}",
            file=sys.stderr,
        )
        return 2

    processor = WhisperProcessor.from_pretrained(args.base_model)
    model = WhisperForConditionalGeneration.from_pretrained(args.base_model)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []

    def prepare(batch):
        import soundfile as sf

        audio_arr, sr = sf.read(batch["audio"])
        if getattr(audio_arr, "ndim", 1) > 1:
            audio_arr = audio_arr.mean(axis=1)
        feats = processor.feature_extractor(
            audio_arr, sampling_rate=sr, return_tensors="np"
        ).input_features[0]
        labels = processor.tokenizer(batch["text"]).input_ids
        return {"input_features": feats, "labels": labels}

    ds = Dataset.from_list(rows).map(prepare, remove_columns=["audio", "text", "id"])

    def collate(features):
        input_features = [
            {"input_features": f["input_features"]} for f in features
        ]
        batch = processor.feature_extractor.pad(input_features, return_tensors="pt")
        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = processor.tokenizer.pad(label_features, return_tensors="pt")
        labels = labels_batch["input_ids"].masked_fill(
            labels_batch["attention_mask"].ne(1), -100
        )
        batch["labels"] = labels
        return batch

    use_fp16 = torch.cuda.is_available()
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(out),
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        fp16=use_fp16,
        gradient_checkpointing=True,
        save_strategy="epoch",
        logging_steps=5,
        report_to=[],
        predict_with_generate=False,
        remove_unused_columns=False,
    )

    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=ds,
        data_collator=collate,
        tokenizer=processor.feature_extractor,
    )
    trainer.train()
    trainer.save_model(str(out))
    processor.save_pretrained(str(out))
    print(f"Saved HF model to {out}")
    print(
        "Convert for faster-whisper:\n"
        f"  ct2-transformers-converter --model {out} "
        f"--output_dir {args.data_dir / 'models' / 'ct2-cooking'} "
        "--quantization int8 --copy_files tokenizer.json preprocessor_config.json"
    )
    print("Then set WHISPER_FINETUNED_DIR to the ct2 dir and SOCIALFETCH_TRANSCRIPT=off")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
