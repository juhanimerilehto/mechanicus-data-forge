#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

import torch
import tiktoken

# Import your model code from train.py (must be in same directory)
from train import GPT, ModelConfig


"""
Test prompt generator - ALIGNED WITH TRAINING DATA VOCABULARY
Updated to use exact component names from training dataset
"""

DEFAULT_PROMPTS = [
    "Prayer for activating a plasma reactor.",
    "Emergency prayer for an emergency bulkhead.",
    "Blessing for a newly forged chainsword.",
    "Litany for cogitator boot sequence.",
    "Prayer for Sentinel walker leg actuator warmup.",
    "Prayer for a generator.",
    "Prayer for a failing servitor.",
    "Prayer for recalibrating auspex scanner.",
    "Prayer for sanctifying a data-slate.",
    "Prayer for restarting a stubborn cogitator.",
]

TEMPLATES = [
    "Prayer for {thing}.",
    "Emergency prayer for {thing}.",
    "Blessing for {thing}.",
    "Litany for {thing}.",
    "Rite of activation for {thing}.",
]

THINGS = [
    "a cooling system",
    "a plasma reactor",
    "a jammed bolter",
    "a corrupted logic engine",
    "an autocannon",
    "a misaligned cogitator",
    "a noisy bearing",
    "a distressed servitor",
    "a damaged power cell",
    "an auspex scanner",
    "an overheating plasma weapon",
    "a fractured hydraulic press",
    "a Rhino transport",
    "a thermal regulator",
    "a capacitor bank",
    "a fusion core",
    "a lascannon",
    "an air compressor",
    "a Thunderhawk",
    "a signal relay",
    "a mechanical lock",
    "a battery array",
    "a medicae scanner",
    "a noospheric relay",
    "an energy conduit",
    "a chainsword",
    "a flamer",
    "a vox transmitter",
    "a pump",
    "an emergency beacon",
    "a Land Raider",
    "a gyroscope",
    "a conveyor system",
    "a forge anvil",
    "an augmetic limb",
]


def wrap_prompt(user_text: str) -> str:
    # Matches your training formatting
    return f"<|user|>{user_text}<|end|>\n<|assistant|>"


def load_prompts(path: str | None, n: int) -> list[str]:
    if path is None:
        # Build a longer prompt pool from templates
        pool = list(DEFAULT_PROMPTS)
        for t in THINGS:
            for tpl in TEMPLATES:
                pool.append(tpl.format(thing=t))
        # Just cycle deterministically
        out = [pool[i % len(pool)] for i in range(n)]
        return out

    p = Path(path)
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        raise ValueError(f"prompts file is empty: {path}")
    return [lines[i % len(lines)] for i in range(n)]


@torch.no_grad()
def generate_one(model: GPT, enc, device: str, prompt: str, max_new_tokens: int, temperature: float, top_k: int):
    tokens = enc.encode(prompt)
    x = torch.tensor([tokens], dtype=torch.long, device=device)

    # autocast on CUDA for speed
    if device == "cuda":
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            y = model.generate(x, max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k)
    else:
        y = model.generate(x, max_new_tokens=max_new_tokens, temperature=temperature, top_k=top_k)

    text = enc.decode(y[0].tolist())

    # Trim after <|end|> if model produces it
    tail = text[len(prompt):]
    if "<|end|>" in tail:
        cut = text.index("<|end|>", len(prompt)) + len("<|end|>")
        text = text[:cut]

    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", default=["checkpoints", "checkpoints2", "checkpoints3", "checkpoints_strong1", "checkpoints_grok_data"],
                    help="Checkpoint directories to load (each must contain checkpoint_best.pt by default)")
    ap.add_argument("--ckpt-name", default="checkpoint_best.pt", help="Checkpoint filename inside each dir")
    ap.add_argument("--n", type=int, default=100, help="Samples per model")
    ap.add_argument("--prompts", default=None, help="Optional prompts.txt (one prompt per line). Cycles if < n.")
    ap.add_argument("--out", default="generations3", help="Output folder")
    ap.add_argument("--max-new-tokens", type=int, default=256)
    ap.add_argument("--temperature", type=float, default=0.65)
    ap.add_argument("--top-k", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[i] device = {device}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    enc = tiktoken.get_encoding("gpt2")
    user_prompts = load_prompts(args.prompts, args.n)
    wrapped_prompts = [wrap_prompt(p) for p in user_prompts]

    for d in args.dirs:
        dpath = Path(d)
        ckpt_path = dpath / args.ckpt_name
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Missing checkpoint: {ckpt_path}")

        print(f"\n=== Loading: {ckpt_path} ===")
        checkpoint = torch.load(ckpt_path, map_location=device, weights_only=False)

        model_cfg = ModelConfig(**checkpoint["model_config"])
        model = GPT(model_cfg).to(device)
        model.load_state_dict(checkpoint["model"])
        model.eval()

        # Safety: vocab must match
        if model_cfg.vocab_size != model.lm_head.out_features:
            raise RuntimeError("Vocab size mismatch in loaded model.")

        out_file = out_dir / f"{dpath.name}_{args.ckpt_name.replace('.pt','')}_{args.n}.jsonl"
        with out_file.open("w", encoding="utf-8") as f:
            for i in range(args.n):
                prompt = wrapped_prompts[i]
                text = generate_one(
                    model=model,
                    enc=enc,
                    device=device,
                    prompt=prompt,
                    max_new_tokens=args.max_new_tokens,
                    temperature=args.temperature,
                    top_k=args.top_k,
                )
                rec = {
                    "model_dir": str(dpath),
                    "checkpoint": args.ckpt_name,
                    "i": i,
                    "user_prompt": user_prompts[i],
                    "prompt_wrapped": prompt,
                    "completion_full": text,
                    "completion_only": text[len(prompt):].strip(),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(f"[ok] wrote {args.n} samples -> {out_file}")

        # Free VRAM before next model
        del model
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
