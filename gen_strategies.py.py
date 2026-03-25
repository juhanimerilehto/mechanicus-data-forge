#!/usr/bin/env python3
"""
Try different generation strategies to fix mid-prayer generation
"""

from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch
from pathlib import Path

MODEL_DIR = Path("mechanicus-prayer-gpt2")

print("=" * 80)
print("TESTING DIFFERENT GENERATION STRATEGIES")
print("=" * 80)

# Load
tokenizer = GPT2Tokenizer.from_pretrained(MODEL_DIR)
model = GPT2LMHeadModel.from_pretrained(MODEL_DIR)
model.eval()

test_prompt = "Prayer for activating a plasma reactor."

# Strategy 1: Standard (current broken approach)
print("\n" + "=" * 80)
print("STRATEGY 1: Standard Generation")
print("=" * 80)

full_prompt = f"<|user|>{test_prompt}<|end|>\n<|assistant|>"
inputs = tokenizer(full_prompt, return_tensors="pt")
input_length = inputs["input_ids"].shape[1]

with torch.no_grad():
    outputs = model.generate(
        inputs["input_ids"],
        max_new_tokens=100,
        temperature=0.8,
        do_sample=True,
    )

generated = outputs[0][input_length:]
prayer1 = tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer1:
    prayer1 = prayer1.split("<|end|>")[0].strip()

print(f"Result: {prayer1[:150]}...")

# Strategy 2: Greedy (no sampling)
print("\n" + "=" * 80)
print("STRATEGY 2: Greedy Decoding (No Sampling)")
print("=" * 80)

with torch.no_grad():
    outputs = model.generate(
        inputs["input_ids"],
        max_new_tokens=100,
        do_sample=False,  # Greedy
    )

generated = outputs[0][input_length:]
prayer2 = tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer2:
    prayer2 = prayer2.split("<|end|>")[0].strip()

print(f"Result: {prayer2[:150]}...")

# Strategy 3: Higher temperature
print("\n" + "=" * 80)
print("STRATEGY 3: Higher Temperature (1.2)")
print("=" * 80)

with torch.no_grad():
    outputs = model.generate(
        inputs["input_ids"],
        max_new_tokens=100,
        temperature=1.2,
        do_sample=True,
    )

generated = outputs[0][input_length:]
prayer3 = tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer3:
    prayer3 = prayer3.split("<|end|>")[0].strip()

print(f"Result: {prayer3[:150]}...")

# Strategy 4: With repetition penalty
print("\n" + "=" * 80)
print("STRATEGY 4: With Repetition Penalty")
print("=" * 80)

with torch.no_grad():
    outputs = model.generate(
        inputs["input_ids"],
        max_new_tokens=100,
        temperature=0.8,
        do_sample=True,
        repetition_penalty=1.1,
    )

generated = outputs[0][input_length:]
prayer4 = tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer4:
    prayer4 = prayer4.split("<|end|>")[0].strip()

print(f"Result: {prayer4[:150]}...")

# Strategy 5: Beam search
print("\n" + "=" * 80)
print("STRATEGY 5: Beam Search (num_beams=3)")
print("=" * 80)

with torch.no_grad():
    outputs = model.generate(
        inputs["input_ids"],
        max_new_tokens=100,
        num_beams=3,
        early_stopping=True,
    )

generated = outputs[0][input_length:]
prayer5 = tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer5:
    prayer5 = prayer5.split("<|end|>")[0].strip()

print(f"Result: {prayer5[:150]}...")

# Strategy 6: Add explicit start token
print("\n" + "=" * 80)
print("STRATEGY 6: Force Start with 'Approach' Token")
print("=" * 80)

# Find the token ID for "Approach" or " Approach"
approach_tokens = tokenizer.encode("Approach", add_special_tokens=False)
print(f"'Approach' tokens: {approach_tokens}")

# Add "Approach" as the first generated token
forced_start = torch.cat([
    inputs["input_ids"],
    torch.tensor([[approach_tokens[0]]])
], dim=1)

with torch.no_grad():
    outputs = model.generate(
        forced_start,
        max_new_tokens=100,
        temperature=0.8,
        do_sample=True,
    )

generated = outputs[0][input_length + 1:]  # Skip the forced token too
prayer6 = "Approach" + tokenizer.decode(generated, skip_special_tokens=False)
if "<|end|>" in prayer6:
    prayer6 = prayer6.split("<|end|>")[0].strip()

print(f"Result: {prayer6[:150]}...")

# Analysis
print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

expected_starts = ['Approach', 'Kneel', 'Invoke', 'Beseech', 'Present', 'Grasp', 'Gather']

strategies = [
    ("Standard", prayer1),
    ("Greedy", prayer2),
    ("High Temp", prayer3),
    ("Rep Penalty", prayer4),
    ("Beam Search", prayer5),
    ("Forced Start", prayer6),
]

print("\nWhich strategies produce correct prayers?\n")
for name, prayer in strategies:
    starts_correctly = any(prayer.startswith(verb) for verb in expected_starts)
    status = "✅" if starts_correctly else "❌"
    print(f"{status} {name:15s}: {prayer[:60]}...")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("\nIf 'Forced Start' works but others don't:")
print("  → Model needs explicit starting token")
print("  → Generation function needs modification")
print("\nIf none work:")
print("  → Model weights may not have loaded correctly")
print("  → Try regenerating from checkpoint")