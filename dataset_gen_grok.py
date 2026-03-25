#!/usr/bin/env python3
"""
Adeptus Mechanicus Prayer Dataset Generator - Grok Edition
Clean, focused approach based on audit findings:
- Single format: natural prose (no First/Second labels)
- Hash-based deduplication
- Simple validation
- Semi-structured varied prompts
"""
import json
import time
import hashlib
import random
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import os

try:
    from openai import OpenAI  # xAI uses OpenAI-compatible API
except ImportError:
    print("ERROR: Install openai package: pip install openai")
    exit(1)

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    print("ERROR: Set XAI_API_KEY environment variable!")
    print("Get your key from: https://console.x.ai")
    exit(1)

# xAI Grok configuration
MODEL = "grok-4-1-fast-reasoning"  # Fast reasoning model
XAI_BASE_URL = "https://api.x.ai/v1"

# Output configuration
OUTPUT_DIR = Path("mechanicus_dataset_grok")
BATCH_SIZE = 10  # Generate this many per API call
TARGET_TOTAL = 4000

# Generation parameters
RATE_LIMIT_DELAY = 1.0  # Adjust based on your rate limits
TEMPERATURE = 0.8  # Balance between creativity and consistency
MAX_TOKENS = 3000

# Validation parameters
MIN_PRAYER_LINES = 3
MAX_PRAYER_LINES = 7
MAX_RETRIES_PER_BATCH = 3

# ============================================================================
# COMPONENTS & OPERATIONS
# Diverse but focused - based on audit analysis
# ============================================================================

COMPONENTS = {
    # Cogitation & Data
    "cogitator", "data-slate", "logic engine", "memory core", "hololithic display",
    "vox-caster", "auspex scanner", "noospheric relay", "archive terminal",
    
    # Power & Energy
    "plasma reactor", "power cell", "capacitor bank", "energy conduit", 
    "fusion core", "generator", "battery array", "thermal regulator",
    
    # Weapons
    "bolter", "lasgun", "plasma weapon", "melta charge", "power weapon",
    "chainsword", "flamer", "autocannon", "lascannon", "missile launcher",
    
    # Machinery
    "hydraulic press", "conveyor system", "pump", "valve assembly", "bearing",
    "cooling system", "air compressor", "servitor", "mechanical lock",
    
    # Vehicles
    "Rhino transport", "Land Raider", "Chimera APC", "Sentinel walker",
    "Taurox", "bike squadron", "drop pod", "Thunderhawk",
    
    # Medical/Augmentation
    "medicae scanner", "surgical servitor", "augmetic limb", "bionics interface",
    "pain suppressor", "cybernetic eye", "neural implant",
    
    # Environment
    "atmosphere processor", "air filtration", "gravity generator", 
    "hydroponics bay", "water reclamator", "emergency bulkhead",
    
    # Sensors/Navigation
    "proximity sensor", "radar array", "star chart", "gyroscope",
    "motion detector", "thermal imager",
    
    # Communications
    "vox transmitter", "emergency beacon", "signal relay", "astropathic choir",
    
    # Manufacturing
    "forge anvil", "welding torch", "cutting laser", "assembly servitor",
    "metal caster", "quality scanner",
}

OPERATIONS = {
    "activation", "startup", "shutdown", "calibration", "initialization",
    "blessing", "consecration", "purification", "operation", "maintenance",
    "repair", "preparation", "cooling", "charging", "cycling",
    "engagement", "targeting", "loading", "synchronization", "sterilization",
    "recalibration", "diagnostics", "reset", "emergency procedure",
}

# ============================================================================
# PROMPT TEMPLATES - Semi-structured but varied
# ============================================================================

PROMPT_TEMPLATES = [
    # Direct requests
    "Help me {operation} the {component}",
    "I need to {operation} the {component}",
    "Guide me through {component} {operation}",
    "Assist with {component} {operation}",
    
    # Status-based
    "The {component} needs {operation}",
    "The {component} requires {operation}",
    "My {component} is ready for {operation}",
    
    # Emergency/urgent
    "Emergency: {component} {operation}",
    "Urgent {component} {operation} needed",
    "Critical: {component} requires {operation}",
    
    # Blessing/ritual requests
    "Bless the {component} for {operation}",
    "Sanctify the {component} during {operation}",
    "Consecrate the {component} before {operation}",
    "Offer prayer for {component} {operation}",
    
    # Questions
    "What's the prayer for {component} {operation}?",
    "How do I bless the {component} for {operation}?",
    "Can you guide {component} {operation}?",
    
    # Preparation
    "Prepare the {component} for {operation}",
    "Ready the {component} for {operation}",
    "The {component} awaits {operation}",
]

# ============================================================================
# SYSTEM PROMPT FOR GROK
# ============================================================================

SYSTEM_PROMPT = """You are a prayer generator for Warhammer 40,000 Adeptus Mechanicus tech-priests.

CRITICAL REQUIREMENTS:

1. OUTPUT FORMAT: Return ONLY valid JSON. No markdown, no explanation, no preamble.
   Must start with { and end with }

2. PRAYER STRUCTURE:
   - Write 3-6 lines of natural flowing prose (NO "First:", "Second:", "Third:" labels)
   - Each line describes a sequential ritual step
   - Use archaic/Latinate language mixed with technical terminology
   - Include the COMPONENT name at least twice
   - Reference the OPERATION at least once
   - Mention Machine Spirits and/or the Omnissiah appropriately

3. STYLE EXAMPLES:

BAD (has labels):
First: Approach the cogitator with reverence.
Second: Clear corrupted data fragments.
Third: Initiate boot sequence.

GOOD (natural prose):
Approach the cogitator with reverence and speak the Litany of Awakening.
Clear all corrupted data-fragments from its blessed memory banks.
Initiate the boot sequence whilst anointing each circuit with sacred oil.
Verify the Machine Spirit's return through diagnostic incantations.

4. RETURN FORMAT:
{
  "prayers": [
    {
      "id": "string",
      "prayer": "string with real newlines between lines"
    }
  ]
}

5. LANGUAGE STYLE:
   - Archaic verbs: "anoint", "invoke", "beseech", "petition", "sanctify"
   - Tech-religious fusion: "sacred circuits", "blessed power-flow", "holy voltage"
   - Machine Spirit references: treat machinery as having spirits
   - Omnissiah invocations: reference the Machine God when appropriate
   - NO modern casual language
   - NO explicit step numbers or labels"""

# ============================================================================
# DEDUPLICATION - Hash-based tracking
# ============================================================================

class DeduplicationTracker:
    """Track generated prompts to prevent duplicates"""
    
    def __init__(self):
        self.seen_hashes: Set[str] = set()
        self.seen_prompts: Dict[str, int] = defaultdict(int)
    
    def hash_prompt(self, prompt: str) -> str:
        """Create hash of normalized prompt"""
        normalized = prompt.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def is_duplicate(self, prompt: str) -> bool:
        """Check if prompt is duplicate"""
        h = self.hash_prompt(prompt)
        return h in self.seen_hashes
    
    def add(self, prompt: str):
        """Register a prompt as seen"""
        h = self.hash_prompt(prompt)
        self.seen_hashes.add(h)
        self.seen_prompts[prompt] += 1
    
    def get_stats(self) -> Dict:
        """Get deduplication statistics"""
        return {
            "unique_hashes": len(self.seen_hashes),
            "total_prompts": len(self.seen_prompts),
            "duplicates_prevented": sum(count - 1 for count in self.seen_prompts.values() if count > 1)
        }

# ============================================================================
# VALIDATION
# ============================================================================

def normalize_prayer(prayer: str) -> str:
    """Normalize prayer text"""
    # Fix escaped newlines
    prayer = prayer.replace("\\n", "\n")
    # Remove excessive whitespace
    lines = [line.strip() for line in prayer.split("\n") if line.strip()]
    return "\n".join(lines)

def validate_prayer(prayer: str, component: str, operation: str) -> Tuple[bool, List[str]]:
    """
    Simple validation:
    1. Correct line count (3-7)
    2. Contains component
    3. Contains operation or operation-related word
    4. Has Mechanicus flavor (sacred/blessed/Machine Spirit/Omnissiah)
    5. No explicit step labels (First:, Second:, etc.)
    """
    reasons = []
    
    # Normalize
    prayer = normalize_prayer(prayer)
    lines = [l for l in prayer.split("\n") if l.strip()]
    
    # Check line count
    if not (MIN_PRAYER_LINES <= len(lines) <= MAX_PRAYER_LINES):
        reasons.append(f"line_count={len(lines)} (need {MIN_PRAYER_LINES}-{MAX_PRAYER_LINES})")
    
    # Check for step labels (we DON'T want these)
    if re.search(r'\b(First|Second|Third|Fourth|Fifth):', prayer):
        reasons.append("has_step_labels (should be prose)")
    
    # Check component appears
    prayer_lower = prayer.lower()
    component_lower = component.lower()
    if component_lower not in prayer_lower:
        reasons.append("component_missing")
    
    # Check operation appears (or related word)
    operation_lower = operation.lower()
    # Build related words for operation
    operation_related = {operation_lower}
    if "activation" in operation_lower or operation_lower == "activate":
        operation_related.update(["activate", "activation", "awaken", "awakening"])
    if "startup" in operation_lower or operation_lower == "start":
        operation_related.update(["start", "startup", "ignition", "commence"])
    if "shutdown" in operation_lower:
        operation_related.update(["shutdown", "deactivate", "cease"])
    if "calibration" in operation_lower or operation_lower == "calibrate":
        operation_related.update(["calibrate", "calibration", "adjust"])
    if "blessing" in operation_lower or operation_lower == "bless":
        operation_related.update(["bless", "blessing", "consecrate", "sanctify"])
    
    has_operation = any(word in prayer_lower for word in operation_related)
    if not has_operation:
        reasons.append("operation_missing")
    
    # Check Mechanicus flavor
    mechanicus_keywords = [
        "omnissiah", "machine spirit", "machine-spirit", "blessed", "sacred",
        "holy", "litany", "canticle", "rite", "ritual", "consecrate",
        "sanctify", "invoke", "anoint", "prayer"
    ]
    has_flavor = any(keyword in prayer_lower for keyword in mechanicus_keywords)
    if not has_flavor:
        reasons.append("missing_mechanicus_flavor")
    
    return (len(reasons) == 0), reasons

# ============================================================================
# GROK API INTERACTION
# ============================================================================

def call_grok(client: OpenAI, specs: List[Dict]) -> List[Dict]:
    """
    Call Grok API to generate prayers for given specifications
    """
    # Prepare items for Grok
    items = []
    for spec in specs:
        items.append({
            "id": spec["id"],
            "component": spec["component"],
            "operation": spec["operation"],
            "user_prompt": spec["user_prompt"],
        })
    
    user_message = (
        "Generate Adeptus Mechanicus prayers for these requests. "
        "Return ONLY the JSON object as specified.\n\n"
        "ITEMS:\n" + json.dumps(items, indent=2)
    )
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    
    response_text = response.choices[0].message.content
    
    # Parse response
    return parse_grok_response(response_text)

def parse_grok_response(response_text: str) -> List[Dict]:
    """Parse Grok's JSON response"""
    text = response_text.strip()
    
    # Strip markdown fences if present
    if "```" in text:
        parts = text.split("```")
        text = max(parts, key=lambda s: s.count("{") + s.count("}")).strip()
        # Remove json language marker
        if text.startswith("json"):
            text = text[4:].strip()
    
    # Find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    
    if start == -1 or end <= 0:
        raise ValueError("No JSON object found in response")
    
    text = text[start:end]
    data = json.loads(text)
    
    if "prayers" not in data or not isinstance(data["prayers"], list):
        raise ValueError("Response missing 'prayers' list")
    
    return data["prayers"]

# ============================================================================
# BATCH GENERATION
# ============================================================================

def generate_specs(
    component_pool: List[str],
    operation_pool: List[str],
    dedup: DeduplicationTracker,
    batch_idx: int,
    batch_size: int
) -> List[Dict]:
    """
    Generate specifications for a batch, ensuring no duplicates
    """
    specs = []
    attempts = 0
    max_attempts = batch_size * 10  # Prevent infinite loop
    
    while len(specs) < batch_size and attempts < max_attempts:
        attempts += 1
        
        # Random component and operation
        component = random.choice(component_pool)
        operation = random.choice(operation_pool)
        
        # Generate prompt from template
        template = random.choice(PROMPT_TEMPLATES)
        
        # Handle grammatical variations
        # Add article for operation if needed
        if operation[0] in 'aeiou':
            operation_with_article = f"an {operation}" if "{operation}" in template and "for {operation}" not in template else operation
        else:
            operation_with_article = f"a {operation}" if "{operation}" in template and "for {operation}" not in template else operation
        
        # Some templates need bare operation, others need article
        if "for {operation}" in template or "during {operation}" in template or "before {operation}" in template:
            prompt = template.format(component=component, operation=operation)
        elif template.startswith("What's") or template.startswith("How do"):
            prompt = template.format(component=component, operation=operation)
        else:
            prompt = template.format(component=component, operation=operation_with_article)
        
        # Check for duplicate
        if dedup.is_duplicate(prompt):
            continue
        
        # Add to specs
        spec_id = f"b{batch_idx:04d}_i{len(specs):02d}"
        specs.append({
            "id": spec_id,
            "component": component,
            "operation": operation,
            "user_prompt": prompt,
        })
        
        # Register in dedup tracker
        dedup.add(prompt)
    
    if len(specs) < batch_size:
        print(f"  ⚠ Warning: Could only generate {len(specs)}/{batch_size} unique prompts")
    
    return specs

def generate_batch(
    client: OpenAI,
    component_pool: List[str],
    operation_pool: List[str],
    dedup: DeduplicationTracker,
    batch_idx: int
) -> List[Dict]:
    """
    Generate and validate one batch of prayers
    """
    # Generate specifications
    specs = generate_specs(component_pool, operation_pool, dedup, batch_idx, BATCH_SIZE)
    spec_by_id = {s["id"]: s for s in specs}
    
    # Try to get valid prayers from Grok
    for retry in range(MAX_RETRIES_PER_BATCH):
        try:
            # Call Grok
            prayers = call_grok(client, specs)
            
            # Map by ID
            prayer_by_id = {}
            for item in prayers:
                if isinstance(item, dict) and "id" in item and "prayer" in item:
                    prayer_by_id[item["id"]] = item
            
            # Validate and collect results
            results = []
            failed = []
            
            for spec_id, spec in spec_by_id.items():
                prayer_item = prayer_by_id.get(spec_id)
                
                if not prayer_item:
                    failed.append((spec_id, ["missing_from_response"]))
                    continue
                
                prayer_text = normalize_prayer(prayer_item.get("prayer", ""))
                
                # Validate
                is_valid, reasons = validate_prayer(
                    prayer_text,
                    spec["component"],
                    spec["operation"]
                )
                
                if is_valid:
                    results.append({
                        "user_prompt": spec["user_prompt"],
                        "prayer": prayer_text,
                        "component": spec["component"],
                        "operation": spec["operation"],
                        "spec_id": spec_id,
                    })
                else:
                    failed.append((spec_id, reasons))
            
            # Report results
            if failed:
                print(f"    ⚠ {len(failed)} failed validation:")
                for spec_id, reasons in failed[:3]:
                    print(f"      {spec_id}: {reasons}")
            
            if results:
                return results
            
            # If all failed, retry
            if retry < MAX_RETRIES_PER_BATCH - 1:
                print(f"    Retry {retry + 1}/{MAX_RETRIES_PER_BATCH}...")
                time.sleep(RATE_LIMIT_DELAY)
        
        except Exception as e:
            print(f"    ✗ API error: {e}")
            if retry < MAX_RETRIES_PER_BATCH - 1:
                time.sleep(RATE_LIMIT_DELAY * 2)
            else:
                raise
    
    # If we get here, all retries failed
    return []

# ============================================================================
# MAIN
# ============================================================================

def main():
    # Initialize Grok client
    client = OpenAI(
        api_key=XAI_API_KEY,
        base_url=XAI_BASE_URL,
    )
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Initialize deduplication tracker and results
    dedup = DeduplicationTracker()
    all_results = []
    successful_batches = 0
    
    # Prepare component and operation pools
    component_pool = list(COMPONENTS)
    operation_pool = list(OPERATIONS)
    
    # Calculate batches needed
    num_batches = (TARGET_TOTAL + BATCH_SIZE - 1) // BATCH_SIZE
    
    # Load existing batches and populate dedup tracker
    existing_batches = set()
    for batch_file in OUTPUT_DIR.glob("batch_*.json"):
        match = re.match(r"batch_(\d{4})\.json", batch_file.name)
        if match:
            batch_idx = int(match.group(1))
            existing_batches.add(batch_idx)
            
            # Load and add to results
            try:
                with open(batch_file, "r", encoding="utf-8") as f:
                    batch_data = json.load(f)
                    if isinstance(batch_data, list):
                        all_results.extend(batch_data)
                        successful_batches += 1
                        # Populate dedup tracker
                        for item in batch_data:
                            if "user_prompt" in item:
                                dedup.add(item["user_prompt"])
            except Exception as e:
                print(f"⚠ Warning: Could not load {batch_file.name}: {e}")
    
    print("🔧 Adeptus Mechanicus Prayer Dataset Generator (Grok)")
    print("=" * 70)
    print(f"Target: {TARGET_TOTAL} prayers")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Model: {MODEL}")
    print(f"Components: {len(component_pool)}")
    print(f"Operations: {len(operation_pool)}")
    print(f"Prompt templates: {len(PROMPT_TEMPLATES)}")
    print(f"Format: Natural prose (no step labels)")
    print(f"Deduplication: Hash-based")
    
    if existing_batches:
        print(f"\n📂 Resuming: Found {len(existing_batches)} existing batches")
        print(f"   Already generated: {len(all_results)} prayers")
        print(f"   Starting from batch {max(existing_batches) + 2}/{num_batches}")
    
    print("=" * 70)
    
    # Generate batches
    for batch_idx in range(num_batches):
        # Skip existing batches
        if batch_idx in existing_batches:
            continue
        
        print(f"\n[Batch {batch_idx + 1}/{num_batches}]")
        
        try:
            results = generate_batch(
                client,
                component_pool,
                operation_pool,
                dedup,
                batch_idx
            )
            
            if results:
                print(f"  ✓ Generated {len(results)} valid prayers")
                all_results.extend(results)
                successful_batches += 1
                
                # Save batch file
                batch_file = OUTPUT_DIR / f"batch_{batch_idx:04d}.json"
                with open(batch_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)
            else:
                print(f"  ✗ Batch failed - no valid results")
        
        except Exception as e:
            print(f"  ✗ Batch error: {e}")
        
        # Rate limiting
        if batch_idx < num_batches - 1:
            time.sleep(RATE_LIMIT_DELAY)
        
        # Early stop if we hit target
        if len(all_results) >= TARGET_TOTAL:
            print(f"\n✓ Reached target of {TARGET_TOTAL} prayers!")
            break
    
    # Save combined results
    combined_file = OUTPUT_DIR / "all_prayers.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    # Create training file
    training_file = OUTPUT_DIR / "training_data.txt"
    with open(training_file, "w", encoding="utf-8") as f:
        for item in all_results:
            f.write(f"<|user|>{item['user_prompt']}<|end|>\n")
            f.write(f"<|assistant|>{item['prayer']}<|end|>\n\n")
    
    # Statistics
    dedup_stats = dedup.get_stats()
    
    print("\n" + "=" * 70)
    print("✓ GENERATION COMPLETE")
    print("=" * 70)
    print(f"Successful batches: {successful_batches}/{num_batches}")
    print(f"Total prayers: {len(all_results)}")
    print(f"Unique prompts: {dedup_stats['unique_hashes']}")
    print(f"Duplicates prevented: {dedup_stats['duplicates_prevented']}")
    print(f"\nOutput files:")
    print(f"  Combined JSON: {combined_file}")
    print(f"  Training file: {training_file}")
    
    if all_results:
        # Calculate statistics
        avg_prayer_len = sum(len(r["prayer"]) for r in all_results) / len(all_results)
        total_chars = sum(len(r["user_prompt"]) + len(r["prayer"]) for r in all_results)
        
        # Component distribution
        component_counts = defaultdict(int)
        operation_counts = defaultdict(int)
        for r in all_results:
            component_counts[r["component"]] += 1
            operation_counts[r["operation"]] += 1
        
        print(f"\n📊 Dataset Statistics:")
        print(f"  Total characters: {total_chars:,}")
        print(f"  Estimated tokens: ~{total_chars // 4:,}")
        print(f"  Avg prayer length: {avg_prayer_len:.0f} chars")
        print(f"  Unique components used: {len(component_counts)}/{len(component_pool)}")
        print(f"  Unique operations used: {len(operation_counts)}/{len(operation_pool)}")
        
        print(f"\n  Top 10 components:")
        for comp, count in sorted(component_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {comp}: {count}")
        
        print(f"\n  Top 10 operations:")
        for op, count in sorted(operation_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"    {op}: {count}")
    
    print("\n🎯 Ready for GPT-2 training!")
    print("   No duplicates, consistent format, clean data.")

if __name__ == "__main__":
    main()