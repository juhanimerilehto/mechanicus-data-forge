#!/usr/bin/env python3
"""
Adeptus Mechanicus Prayer Generator using Claude Haiku API
Generates prompt-completion pairs for GPT-2 training
"""

import json
import time
import itertools
from pathlib import Path
from typing import List, Dict
import os

from anthropic import Anthropic

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Set this environment variable
MODEL = "claude-haiku-4-5-20251001"  # Latest Haiku model

# Output Configuration
OUTPUT_DIR = Path("mechanicus_prayers_dataset_haiku")
BATCH_SIZE = 10  # Prayers per API call
TARGET_TOTAL = 1000  # Total prayers to generate

# Generation Parameters
RATE_LIMIT_DELAY = 4.5  # Seconds between requests (adjust as needed)

# ============================================================================
# TOPICS - Comprehensive list of machinery/procedures
# ============================================================================

TOPICS = {
    "basic_machinery": [
        "diesel engine startup", "electric motor activation", "hydraulic press operation",
        "conveyor belt initialization", "pump priming", "valve opening sequence",
        "bearing lubrication", "cooling system purge", "air compressor cycling",
        "generator startup", "electric motor shutdown", "steam valve regulation",
        "pressure gauge calibration", "mechanical lock engagement", "gear meshing check"
    ],

    "weapons_combat": [
        "lasgun power cell insertion", "bolter firing rite", "plasma weapon cooling",
        "melta charge preparation", "artillery loading", "missile launcher targeting",
        "force field activation", "void shield harmonization", "point defense calibration",
        "demolition charge arming", "chainsword consecration", "power weapon blessing",
        "flamer promethium feed", "autocannon barrel cooling", "lascannon capacitor charge"
    ],

    "vehicles_transports": [
        "Rhino APC ignition", "Land Raider track tension", "Chimera transmission check",
        "Titan leg actuator warmup", "Knight ion shield activation", "Thunderhawk fuel purification",
        "servitor crane operation", "mag-lev train departure", "drop pod descent prep",
        "bike squadron pre-flight", "Sentinel walker balance", "Taurox wheel alignment"
    ],

    "cogitation_data": [
        "cogitator boot sequence", "data-slate activation", "noospheric link establishment",
        "archive retrieval protocol", "encryption key generation", "memory core defragmentation",
        "logic engine error correction", "hololithic display calibration", "vox-caster tuning",
        "auspex scanner initialization", "servitor programming upload", "data-core purification"
    ],

    "power_energy": [
        "plasma reactor startup", "fusion core containment check", "solar panel alignment",
        "power cell recharging", "circuit breaker reset", "capacitor bank discharge",
        "emergency generator failover", "energy conduit purification", "battery diagnostics",
        "thermal dissipation rite", "power distribution balancing", "voltage regulator tuning"
    ],

    "manufacturing_forges": [
        "manufactorum shift beginning", "assembly line consecration", "welding torch ignition",
        "cutting laser calibration", "mold temperature verification", "quality control scanning",
        "material purity testing", "waste recycling activation", "packaging servitor programming",
        "inventory stocktaking", "forge anvil heating", "metal casting preparation"
    ],

    "medical_augmentation": [
        "augmetic limb installation", "medicae scanner activation", "surgical servitor sterilization",
        "bionics synchronization", "pain suppressor engagement", "vital signs monitor calibration",
        "autodoc emergency protocol", "organ preservation unit", "cybernetic eye focusing",
        "neural interface connection", "rejuvenat treatment initiation", "chemical balancing"
    ],

    "environmental_life_support": [
        "atmosphere processor startup", "water reclamation system", "temperature regulation",
        "radiation shielding activation", "air filtration replacement", "waste disposal cycling",
        "hydroponics nutrient feed", "gravity generator stabilization", "decontamination sequence",
        "emergency bulkhead sealing", "oxygen scrubber maintenance", "humidity control"
    ],

    "navigation_sensors": [
        "astrogation calculation", "stellar cartography update", "proximity sensor sweep",
        "gyroscope recalibration", "altimeter verification", "compass magnetization",
        "radar array rotation", "sonar pulse emission", "thermal imaging activation",
        "motion detector arming", "star chart alignment", "gravitational anomaly detection"
    ],

    "communications": [
        "long-range vox transmission", "emergency beacon activation", "signal encryption",
        "relay station handoff", "jamming countermeasure", "distress call broadcast",
        "inter-ship hailing", "ground-to-orbit link", "secure channel establishment",
        "message queue processing", "astropathic choir preparation", "binary cant encoding"
    ],

    "emergency_maintenance": [
        "fire suppression system", "hull breach sealing", "coolant leak repair",
        "electrical short isolation", "pressure equalization", "corrosion treatment",
        "fracture welding", "component replacement", "emergency shutdown",
        "restart after failure", "stuck mechanism freeing", "overheating prevention",
        "vibration dampening", "noise reduction", "wear inspection", "rust removal"
    ]
}

# Flatten all topics into single list
ALL_TOPICS = [topic for category in TOPICS.values() for topic in category]

# ============================================================================
# FORMAT STYLES - Different prayer structures
# ============================================================================

FORMAT_STYLES = [
    "numbered sequential steps (First, Second, Third)",
    "call-and-response between tech-priest and congregation",
    "flowing prose litany without any lists or numbers",
    "mixing binary cant (e.g., 01010000 01110010...) with archaic High Gothic",
    "brief 2-3 line invocation only",
]

# ============================================================================
# SYSTEM INSTRUCTION & EXAMPLE
# ============================================================================

SYSTEM_INSTRUCTION = """You are a prayer generator for Warhammer 40,000 Adeptus Mechanicus.

CRITICAL FORMAT REQUIREMENT:
YOU MUST RETURN ONLY VALID JSON. NO MARKDOWN. NO EXPLANATION. NO PREAMBLE.
Start your response with { and end with }

Your prayers must:
1. Be ritualized technical procedures - mantras evolved from maintenance manuals
2. Mix archaic/Latinate language with technical terminology
3. Reference the Omnissiah and Machine Spirits (but not excessively)
4. Be 4-10 lines maximum (GPT-2 training constraint)
5. When procedure is sequential, include actual steps (but archaic-ified)
6. Vary structure based on the required format

Example of good prayer (sequential format for diesel engine):

Prompt: "Prayer for initiating a diesel engine"
Prayer:
"From the Litany of Ignition, Verse IV

Blessed be the fuel-spirit's awakening.
First: Let the sacred oils flow to the combustion-heart.
Second: Invoke the glow-plugs' warmth, that the air be made receptive.
Third: Engage the starter-servo with the Rite of Turning.

By the Omnissiah's will, let compression and flame unite."

Remember:
- Archaic wrapper around REAL procedure steps
- Sequential when format requires (First/Second/Third)
- Mix Latin/Gothic with tech terms ("combustion-heart", "starter-servo")
- Keep it SHORT (4-10 lines)
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_topic_variations(topics: List[str], batch_size: int) -> List[Dict]:
    """Generate varied prayer specifications for a batch"""
    import random

    variations = []
    for _ in range(batch_size):
        variations.append({
            "topic": random.choice(topics),
            "context": random.choice([
                "routine operation", "emergency situation", "first use blessing",
                "post-repair consecration", "combat preparation", "maintenance ritual"
            ])
        })
    return variations

def parse_claude_response(response_text: str) -> List[Dict]:
    """Ultra-defensive JSON parsing"""
    text = response_text.strip()

    # Remove markdown if present (despite instructions)
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}') + 1

    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")

    text = text[start:end]

    try:
        data = json.loads(text)
        if "prayers" not in data:
            raise ValueError("Response missing 'prayers' field")
        return data['prayers']
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Problematic text: {text[:500]}...")
        raise

def filter_quality(prayers: List[Dict]) -> List[Dict]:
    """Remove low-quality prayers"""
    filtered = []
    for p in prayers:
        prayer_text = p.get('prayer', '')
        prompt_text = p.get('prompt', '')

        # Basic quality checks
        if len(prayer_text) < 50:  # Too short
            continue
        if len(prompt_text) < 10:  # Prompt too vague
            continue
        if not any(word in prayer_text.lower() for word in
                   ['omnissiah', 'machine', 'spirit', 'blessed', 'sacred', 'forge']):
            continue  # Doesn't seem Mechanicus-themed

        filtered.append(p)

    return filtered

def get_missing_batch_numbers(output_dir: Path, total_batches: int) -> List[int]:
    """Find which batches are missing"""
    existing = set()
    for f in output_dir.glob("batch_*.json"):
        num = int(f.stem.split('_')[1])
        existing.add(num)

    return [i for i in range(total_batches) if i not in existing]

# ============================================================================
# MAIN GENERATION FUNCTION
# ============================================================================

def generate_prayer_batch(
    client: Anthropic,
    topics: List[str],
    format_style: str,
    batch_num: int
) -> List[Dict]:
    """Generate one batch of prayers"""

    variations = create_topic_variations(topics, BATCH_SIZE)

    # Construct the generation prompt
    user_prompt = f"""Generate exactly {BATCH_SIZE} Adeptus Mechanicus prayer-completion pairs.

CRITICAL: Return ONLY the JSON object. No markdown, no ```json```, no explanation.

{{
  "prayers": [
    {{
      "prompt": "user request for this prayer (e.g., 'Prayer for blessing a Knight before battle')",
      "prayer": "the actual Mechanicus prayer text (4-10 lines)",
      "format_type": "{format_style.split()[0]}"
    }}
  ]
}}

REQUIRED FORMAT FOR THIS BATCH: {format_style}

Topic variations for this batch:
{json.dumps(variations, indent=2)}

Guidelines:
- Each prayer MUST be {format_style}
- Mix archaic language (Latin/Gothic) with technical terms
- Base on REAL procedures when relevant (e.g., diesel startup = fuel, glow plugs, starter)
- 4-10 lines maximum per prayer
- Reference Omnissiah/Machine Spirits tastefully (not every prayer)
- Make prompts realistic (what a user would ask for)

Examples of good prompts:
- "Prayer for activating a plasma reactor"
- "Blessing before repair of a damaged cogitator"
- "Emergency rite for stuck landing gear"
"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            temperature=0.9,  # High creativity
            system=SYSTEM_INSTRUCTION,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Extract text from Claude response
        response_text = response.content[0].text

        # Parse JSON
        prayers = parse_claude_response(response_text)

        print(f"  ✓ Batch {batch_num}: Generated {len(prayers)} prayers")
        return prayers

    except Exception as e:
        print(f"  ✗ Batch {batch_num} failed: {e}")
        return []

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main generation loop"""

    # Validate API key
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable!")
        print("Get your key from: https://console.anthropic.com/settings/keys")
        return

    # Initialize client
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Calculate batches
    num_batches = TARGET_TOTAL // BATCH_SIZE

    # Format style rotation
    format_cycle = itertools.cycle(FORMAT_STYLES)

    print(f"🔧 Mechanicus Prayer Generator (Claude Haiku)")
    print(f"━" * 60)
    print(f"Target: {TARGET_TOTAL} prayers ({num_batches} batches of {BATCH_SIZE})")
    print(f"Model: {MODEL}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Topics: {len(ALL_TOPICS)} variations")
    print(f"Format styles: {len(FORMAT_STYLES)} types")
    print(f"━" * 60)

    all_prayers = []
    successful_batches = 0

    for batch_num in range(num_batches):
        current_format = next(format_cycle)

        print(f"\n[Batch {batch_num + 1}/{num_batches}] Format: {current_format[:40]}...")

        prayers = generate_prayer_batch(
            client=client,
            topics=ALL_TOPICS,
            format_style=current_format,
            batch_num=batch_num + 1
        )

        if prayers:
            # Filter quality
            filtered = filter_quality(prayers)
            print(f"  → Kept {len(filtered)}/{len(prayers)} after quality filter")

            all_prayers.extend(filtered)
            successful_batches += 1

            # Save incremental batch
            batch_file = OUTPUT_DIR / f"batch_{batch_num:04d}.json"
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2, ensure_ascii=False)

        # Rate limiting
        if batch_num < num_batches - 1:  # Don't sleep after last batch
            time.sleep(RATE_LIMIT_DELAY)

    # ========================================================================
    # FINAL DATASET CREATION
    # ========================================================================

    print(f"\n{'━' * 60}")
    print(f"✓ Generation complete!")
    print(f"  Successful batches: {successful_batches}/{num_batches}")
    print(f"  Total prayers: {len(all_prayers)}")

    # Save combined dataset
    combined_file = OUTPUT_DIR / "all_prayers.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_prayers, f, indent=2, ensure_ascii=False)

    print(f"  Combined JSON: {combined_file}")
    missing = get_missing_batch_numbers(OUTPUT_DIR, num_batches)
    if missing:
        print(f"\n🔄 Retrying {len(missing)} failed batches with smaller size...")
        for batch_num in missing:
            print(f"\n🔄 Retrying {len(missing)} failed batches...")

    for batch_num in missing:
        current_format = next(format_cycle)

        print(f"\n[Retry {batch_num + 1}] Format: {current_format[:40]}...")

        prayers = generate_prayer_batch(
            client=client,
            topics=ALL_TOPICS,
            format_style=current_format,
            batch_num=batch_num + 1
        )

        if prayers:
            filtered = filter_quality(prayers)
            all_prayers.extend(filtered)

            batch_file = OUTPUT_DIR / f"batch_{batch_num:04d}.json"
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(filtered, f, indent=2, ensure_ascii=False)

        time.sleep(RATE_LIMIT_DELAY)

    # Create training file for nanoGPT
    training_file = OUTPUT_DIR / "training_data.txt"
    with open(training_file, "w", encoding="utf-8") as f:
        for p in all_prayers:
            f.write(f"<|user|>{p['prompt']}<|end|>\n")
            f.write(f"<|assistant|>{p['prayer']}<|end|>\n\n")

    print(f"  Training file: {training_file}")

    # Statistics
    total_chars = sum(len(p['prompt']) + len(p['prayer']) for p in all_prayers)
    avg_prayer_len = sum(len(p['prayer']) for p in all_prayers) / len(all_prayers)

    print(f"\n📊 Dataset Statistics:")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Estimated tokens: ~{total_chars // 4:,}")
    print(f"  Avg prayer length: {avg_prayer_len:.0f} chars")
    print(f"  Format distribution:")

    format_counts = {}
    for p in all_prayers:
        fmt = p.get('format_type', 'unknown')
        format_counts[fmt] = format_counts.get(fmt, 0) + 1

    for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
        print(f"    {fmt}: {count} ({100*count/len(all_prayers):.1f}%)")

    print(f"\n🎯 Next steps:")
    print(f"  1. Review prayers in {combined_file}")
    print(f"  2. Use {training_file} for GPT-2 training")
    print(f"  3. Train with nanoGPT")

if __name__ == "__main__":
    main()
