#!/usr/bin/env python3
"""
Adeptus Mechanicus Prayer Dataset Generator (Claude Haiku API)

Goal: generate prompt→completion pairs that *strongly* match the user request
for small-dataset GPT-2 training.

Key improvements vs original:
- Stable, explicit control header in the training prompt (REQUEST / TOPIC / COMPONENT / OPERATION / FORMAT / MUST_INCLUDE).
- Strong lexical anchoring: generated prayers must include exact COMPONENT multiple times (verbatim).
- Per-item validation + targeted regeneration for failures (instead of accepting drift).
- Cleaner batch numbering, resumable generation, fixed retry logic.
"""

import json
import time
import itertools
import random
import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-4-5-20251001"  # your chosen Haiku model

# Output Configuration
OUTPUT_DIR = Path("mechanicus_prayers_dataset_haiku_strong")
BATCH_SIZE = 10
TARGET_TOTAL = 4000

# Generation Parameters
RATE_LIMIT_DELAY = 4.5
TEMPERATURE = 0.75  # slightly lower = better instruction-following
MAX_TOKENS = 4000

# Quality + regeneration
MAX_ITEM_RETRIES = 2          # re-ask Claude for only the failed items
MAX_BATCH_RETRIES = 2         # re-ask Claude for the whole batch if parsing fails
REQUIRE_TOPIC_VERBATIM = False  # set True if you really want exact TOPIC phrase included

# Formats: For small datasets, fewer formats = better conditioning.
# You can broaden later once the model follows the controls reliably.
FORMAT_STYLES = [
    "sequential",      # must include First/Second/Third
    "call_response",   # Priest:/Congregation: alternating
    # Uncomment once you have >5k–20k examples:
    # "prose",
    # "binary_cant",
    # "brief",
]

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

ALL_TOPICS = [topic for category in TOPICS.values() for topic in category]

# ============================================================================
# PROMPT STYLES - Varied user request phrasings (but still anchored)
# ============================================================================

PROMPT_STYLES = [
    "Prayer for {operation} of the {component}",
    "Blessing for the {component} during {operation}",
    "Emergency rite: {component} requires {operation}",
    "My {component} is failing during {operation} — help",
    "The {component} demands guidance for {operation}",
    "Can you sanctify the {component} for {operation}?",
    "Offer a litany to steady the {component} before {operation}",
    "Rite request: {operation} on {component}",
]

CONTEXT_CHOICES = [
    "routine operation",
    "emergency situation",
    "first use blessing",
    "post-repair consecration",
    "combat preparation",
    "maintenance ritual",
]

# ============================================================================
# FORMAT RULES
# ============================================================================

FORMAT_RULES = {
    "sequential": (
        "Use numbered sequential steps. Include lines starting exactly with "
        '"First:", "Second:", "Third:" (optionally "Fourth:").'
    ),
    "call_response": (
        "Use call-and-response. Alternate lines beginning with "
        '"Priest:" and "Congregation:" starting with Priest:.'
    ),
    "prose": (
        "Use flowing prose litany with no lists and no First/Second/Third labels."
    ),
    "binary_cant": (
        "Mix binary cant with archaic High Gothic. Include at least one 8+ bit binary chunk "
        "(e.g., 01010000 01110010...)."
    ),
    "brief": (
        "Make it a brief invocation (still 4 lines minimum, up to 6). No step labels."
    ),
}

# ============================================================================
# STRONGER SYSTEM INSTRUCTION FOR DATA GENERATION
# ============================================================================

SYSTEM_INSTRUCTION = """You are a prayer generator in the style of Warhammer 40,000 Adeptus Mechanicus.

CRITICAL OUTPUT REQUIREMENT:
- You MUST output ONLY valid JSON. No Markdown. No explanation. No preamble.
- Output must begin with { and end with }.

GROUNDING REQUIREMENTS (NON-NEGOTIABLE):
- You will be given a list of items, each with: id, user_request, topic, component, operation, format.
- You MUST NOT modify any provided strings.
- Each prayer MUST:
  1) Be 4–10 lines (non-empty lines).
  2) Include the exact COMPONENT string at least 2 times (verbatim, character-for-character).
  3) Include the exact OPERATION string at least 1 time (verbatim).
  4) Have at least 3 concrete procedure actions that plausibly relate to the topic/component.
  5) Mix archaic/Latinate language with technical terminology.
  6) Reference the Omnissiah and/or Machine Spirits tastefully (not spammed).
  7) Follow the FORMAT rules for that item exactly.
  LINE BREAKS (IMPORTANT):
- The "prayer" value MUST contain real line breaks (newline characters) so it becomes 4–10 separate lines.
- Do NOT put all steps in a single line separated by spaces.
- For sequential: "First:", "Second:", "Third:" must each start a new line.
- For call_response: each "Priest:" / "Congregation:" must start a new line.


FORMAT RULES:
- sequential: must include "First:", "Second:", "Third:".
- call_response: alternate "Priest:" and "Congregation:" lines, starting with "Priest:".

Return JSON schema exactly:
{
  "prayers": [
    {
      "id": "string",
      "prayer": "string",
      "check": {
        "used_component_exactly": true/false,
        "used_operation_exactly": true/false,
        "format_followed": true/false
      }
    }
  ]
}
"""

# ============================================================================
# HELPERS: topic -> component + operation
# ============================================================================

# Longest first to match multiword suffixes
PROCEDURE_SUFFIXES = sorted([
    "boot sequence",
    "opening sequence",
    "retrieval protocol",
    "link establishment",
    "key generation",
    "error correction",
    "display calibration",
    "programming upload",
    "containment check",
    "transmission check",
    "track tension",
    "fuel purification",
    "drop pod descent prep",
    "pre-flight",
    "power cell insertion",
    "firing rite",
    "capacitor charge",
    "capacit(or|ance) bank discharge",  # regex-like handled separately
    "emergency shutdown",
    "restart after failure",
    "stuck mechanism freeing",

    # common single-word-ish ends
    "startup",
    "shutdown",
    "activation",
    "operation",
    "initialization",
    "priming",
    "purge",
    "cycling",
    "regulation",
    "calibration",
    "engagement",
    "check",
    "cooling",
    "preparation",
    "loading",
    "targeting",
    "harmonization",
    "consecration",
    "blessing",
    "feed",
    "warmup",
    "recharging",
    "reset",
    "failover",
    "diagnostics",
    "balancing",
    "tuning",
    "verification",
    "testing",
    "maintenance",
    "replacement",
    "stabilization",
    "sequence",
    "protocol",
    "installation",
    "sterilization",
    "synchronization",
    "connection",
    "initiation",
    "broadcast",
    "encoding",
    "processing",
    "sealing",
    "repair",
    "isolation",
    "equalization",
    "treatment",
    "welding",
    "freeing",
    "prevention",
    "dampening",
    "reduction",
    "inspection",
    "removal",
], key=lambda s: len(s), reverse=True)


def infer_component_operation(topic: str) -> Tuple[str, str]:
    """
    Heuristic split of a topic phrase into (component, operation).
    Falls back to (topic, "operation") if no suffix match.
    """
    t = topic.strip()

    # Special-case regex-ish pattern for "capacitor bank discharge"
    if re.search(r"\bcapacitor bank discharge\b", t, flags=re.IGNORECASE):
        comp = re.sub(r"\bcapacitor bank discharge\b", "", t, flags=re.IGNORECASE).strip()
        comp = comp if comp else "capacitor bank"
        return comp, "capacitor bank discharge"

    lower = t.lower()

    # Try multiword suffixes
    for suf in PROCEDURE_SUFFIXES:
        # Treat suf as literal unless it contains regex metacharacters
        if any(ch in suf for ch in "().|?+*[]{}\\"):
            if re.search(rf"\b{suf}\b$", t, flags=re.IGNORECASE):
                comp = re.sub(rf"\b{suf}\b$", "", t, flags=re.IGNORECASE).strip()
                op = re.search(rf"({suf})$", t, flags=re.IGNORECASE).group(1)
                comp = comp if comp else t
                return comp, op
        else:
            if lower.endswith(" " + suf) or lower == suf:
                comp = t[: -(len(suf) + 1)].strip() if lower != suf else ""
                comp = comp if comp else t
                return comp, suf

    # Fallback: use last token as operation if it looks procedural
    tokens = t.split()
    if len(tokens) >= 2:
        last = tokens[-1].lower()
        if last in {"startup", "shutdown", "activation", "calibration", "repair", "tuning", "check"}:
            comp = " ".join(tokens[:-1]).strip()
            return comp, tokens[-1]

    return t, "operation"

# ============================================================================
# TRAINING PROMPT TEMPLATE (stable conditioning block)
# ============================================================================

def build_training_prompt(spec: Dict) -> str:
    """
    This is the *actual* prompt you will feed to GPT-2 during training.
    It is stable and control-field-rich, which dramatically improves adherence
    for small datasets.
    """
    must_include_lines = [
        f"- {spec['component']}",
        f"- {spec['operation']}",
    ]
    if REQUIRE_TOPIC_VERBATIM:
        must_include_lines.append(f"- {spec['topic']}")

    return (
        "### REQUEST\n"
        f"{spec['user_request']}\n\n"
        "### TOPIC\n"
        f"{spec['topic']}\n\n"
        "### COMPONENT\n"
        f"{spec['component']}\n\n"
        "### OPERATION\n"
        f"{spec['operation']}\n\n"
        "### FORMAT\n"
        f"{spec['format']}\n\n"
        "### MUST_INCLUDE\n"
        + "\n".join(must_include_lines) + "\n\n"
        "### PRAYER\n"
    )

# ============================================================================
# QUALITY / VALIDATION
# ============================================================================

def nonempty_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]

def count_occurrences_case_insensitive(hay: str, needle: str) -> int:
    # exact substring count, case-insensitive
    return hay.lower().count(needle.lower())

def validate_format(prayer: str, fmt: str) -> bool:
    lines = nonempty_lines(prayer)
    if fmt == "sequential":
        return any(ln.startswith("First:") for ln in lines) and \
               any(ln.startswith("Second:") for ln in lines) and \
               any(ln.startswith("Third:") for ln in lines)
    if fmt == "call_response":
        # must alternate Priest:/Congregation:, starting Priest:
        labels = []
        for ln in lines:
            if ln.startswith("Priest:"):
                labels.append("P")
            elif ln.startswith("Congregation:"):
                labels.append("C")
        if len(labels) < 4:
            return False
        if labels[0] != "P":
            return False
        # alternation check
        for i in range(1, len(labels)):
            if labels[i] == labels[i-1]:
                return False
        return True
    if fmt == "prose":
        return not any(ln.startswith(("First:", "Second:", "Third:", "Priest:", "Congregation:")) for ln in lines)
    if fmt == "binary_cant":
        return bool(re.search(r"\b[01]{8,}\b", prayer))
    if fmt == "brief":
        return len(lines) <= 6 and not any(ln.startswith(("First:", "Second:", "Third:", "Priest:", "Congregation:")) for ln in lines)
    return True

def normalize_prayer_text(prayer: str, fmt: str) -> str:
    # If Claude double-escaped newlines, fix that
    prayer = prayer.replace("\\n", "\n").strip()

    # If Claude wrote everything in one physical line, split by labels
    if fmt == "sequential":
        prayer = re.sub(r"\s+(First:|Second:|Third:|Fourth:)\s*", r"\n\1 ", prayer).lstrip()
    elif fmt == "call_response":
        prayer = re.sub(r"\s+(Priest:|Congregation:)\s*", r"\n\1 ", prayer).lstrip()

    return prayer


def validate_prayer_against_spec(prayer: str, spec: Dict) -> Tuple[bool, List[str]]:
    reasons = []
    lines = nonempty_lines(prayer)

    if not (4 <= len(lines) <= 10):
        reasons.append(f"line_count={len(lines)} (need 4–10)")

    comp = spec["component"]
    op = spec["operation"]
    topic = spec["topic"]

    comp_count = count_occurrences_case_insensitive(prayer, comp)
    if comp_count < 2:
        reasons.append(f"component_count={comp_count} (need >=2 verbatim)")

    # At least 3 lines must contain COMPONENT verbatim (case-insensitive)
    comp_lines = sum(1 for ln in lines if comp.lower() in ln.lower())
    if comp_lines < 3:
        reasons.append(f"component_lines={comp_lines} (need >=3 lines containing COMPONENT)")

    op_count = count_occurrences_case_insensitive(prayer, op)
    if op_count < 1:
        reasons.append(f"operation_count={op_count} (need >=1 verbatim)")

    if REQUIRE_TOPIC_VERBATIM:
        topic_count = count_occurrences_case_insensitive(prayer, topic)
        if topic_count < 1:
            reasons.append("topic_missing (verbatim required)")

    if not validate_format(prayer, spec["format"]):
        reasons.append("format_not_followed")

    # Minimal Mechanicus flavor check (keep light; we already anchor via system prompt)
    flavor_tokens = ["omnissiah", "machine spirit", "machine-spirits", "machine", "spirit", "blessed", "sacred", "forge"]
    if not any(tok in prayer.lower() for tok in flavor_tokens):
        reasons.append("weak_mechanicus_flavor")

    return (len(reasons) == 0), reasons

# ============================================================================
# DEFENSIVE JSON PARSING
# ============================================================================

def parse_claude_response(response_text: str) -> List[Dict]:
    text = response_text.strip()

    # Strip markdown fences if present (despite instructions)
    if "```" in text:
        parts = text.split("```")
        # take the largest chunk that contains { ... }
        text = max(parts, key=lambda s: s.count("{") + s.count("}")).strip()

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
# SPEC GENERATION
# ============================================================================

def make_specs_for_batch(topics: List[str], fmt: str, batch_size: int, batch_idx: int) -> List[Dict]:
    specs = []
    for i in range(batch_size):
        topic = random.choice(topics)
        component, operation = infer_component_operation(topic)

        # Build a realistic user request (varied, but still anchored to component+operation)
        style = random.choice(PROMPT_STYLES)
        user_request = style.format(component=component, operation=operation)

        spec_id = f"b{batch_idx:04d}_i{i:02d}"
        specs.append({
            "id": spec_id,
            "user_request": user_request,
            "topic": topic,
            "component": component,
            "operation": operation,
            "format": fmt,
            "context": random.choice(CONTEXT_CHOICES),
        })
    return specs

# ============================================================================
# CLAUDE CALL (generate prayers for given specs)
# ============================================================================

def call_claude_for_specs(client: Anthropic, specs: List[Dict]) -> List[Dict]:
    """
    Ask Claude to generate prayers for exactly the provided specs.
    Returns list of {id, prayer, check}.
    """
    # We give Claude only what it needs; it must not alter the strings.
    payload_items = []
    for s in specs:
        payload_items.append({
            "id": s["id"],
            "user_request": s["user_request"],
            "topic": s["topic"],
            "component": s["component"],
            "operation": s["operation"],
            "format": s["format"],
            "format_rules": FORMAT_RULES.get(s["format"], ""),
        })

    user_prompt = (
        "Generate prayers for the following items. "
        "Return ONLY the JSON object described in the system message.\n\n"
        "ITEMS:\n"
        + json.dumps(payload_items, ensure_ascii=False, indent=2)
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_INSTRUCTION,
        messages=[{"role": "user", "content": user_prompt}],
    )

    response_text = response.content[0].text
    return parse_claude_response(response_text)

# ============================================================================
# BATCH GENERATION WITH VALIDATION + TARGETED REGEN
# ============================================================================

def generate_validated_batch(
    client: Anthropic,
    topics: List[str],
    fmt: str,
    batch_idx: int,
) -> List[Dict]:
    """
    Create specs -> ask Claude -> validate -> regenerate failed items.
    Returns finalized dataset rows with training prompt included.
    """
    specs = make_specs_for_batch(topics, fmt, BATCH_SIZE, batch_idx)
    spec_by_id = {s["id"]: s for s in specs}

    # NEW: rejection diagnostics (counts + sample logging)
    reason_counts: Dict[str, int] = {}
    def bump(reasons: List[str]) -> None:
        for r in reasons:
            reason_counts[r] = reason_counts.get(r, 0) + 1

    def log_reject(stage: str, sid: str, spec: Dict, prayer_text: str, reasons: List[str]) -> None:
        # concise console log
        print(f"    ✗ [{stage}] {sid} rejected: {reasons}")
        print("    repr:", repr(prayer_text[:200]))

        # optional: persist rejects for offline inspection (no extra API calls)
        try:
            with open(OUTPUT_DIR / "rejected_samples.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {
                        "stage": stage,
                        "id": sid,
                        "format": spec.get("format"),
                        "topic": spec.get("topic"),
                        "component": spec.get("component"),
                        "operation": spec.get("operation"),
                        "user_request": spec.get("user_request"),
                        "prayer": prayer_text,
                        "reasons": reasons,
                    },
                    ensure_ascii=False
                ) + "\n")
        except Exception:
            pass

    # Attempt the batch call (with batch-level retries for parse errors)
    last_err: Optional[Exception] = None
    prayers_out: List[Dict] = []
    for attempt in range(MAX_BATCH_RETRIES + 1):
        try:
            prayers_out = call_claude_for_specs(client, specs)
            break
        except Exception as e:
            last_err = e
            if attempt < MAX_BATCH_RETRIES:
                time.sleep(RATE_LIMIT_DELAY)
            else:
                raise

    # Map returned prayers by id
    out_by_id = {}
    for item in prayers_out:
        if isinstance(item, dict) and "id" in item and "prayer" in item:
            out_by_id[item["id"]] = item

    # Validate and collect failures
    finalized: Dict[str, Dict] = {}
    failed_ids: List[str] = []

    for sid, spec in spec_by_id.items():
        got = out_by_id.get(sid)
        if not got:
            bump(["missing_item_in_response"])
            log_reject("initial", sid, spec, "", ["missing_item_in_response"])
            failed_ids.append(sid)
            continue

        prayer_text = got.get("prayer", "").strip()
        prayer_text = normalize_prayer_text(prayer_text, spec["format"])

        ok, reasons = validate_prayer_against_spec(prayer_text, spec)

        if ok:
            finalized[sid] = {
                **spec,
                "training_prompt": build_training_prompt(spec),
                "prayer": prayer_text,
                "validation": {"ok": True, "reasons": []},
                "generator_check": got.get("check", {}),
            }
        else:
            bump(reasons)
            log_reject("initial", sid, spec, prayer_text, reasons)
            failed_ids.append(sid)

    # NEW: print summary of initial rejection reasons
    if reason_counts:
        print("  Rejection reasons (initial):", dict(sorted(reason_counts.items(), key=lambda x: -x[1])))

    # Targeted regeneration for failed items
    for retry in range(1, MAX_ITEM_RETRIES + 1):
        if not failed_ids:
            break

        # reset per-retry reason counts for clearer diagnostics
        retry_reason_counts: Dict[str, int] = {}
        def bump_retry(reasons: List[str]) -> None:
            for r in reasons:
                retry_reason_counts[r] = retry_reason_counts.get(r, 0) + 1

        failed_specs = [spec_by_id[sid] for sid in failed_ids]
        time.sleep(RATE_LIMIT_DELAY)

        try:
            regen = call_claude_for_specs(client, failed_specs)
        except Exception:
            # keep failures; proceed
            print(f"  ✗ Regen attempt {retry}/{MAX_ITEM_RETRIES} failed (API/parse). Keeping failures.")
            continue

        regen_by_id = {}
        for item in regen:
            if isinstance(item, dict) and "id" in item and "prayer" in item:
                regen_by_id[item["id"]] = item

        new_failed: List[str] = []
        for sid in failed_ids:
            spec = spec_by_id[sid]
            got = regen_by_id.get(sid)
            if not got:
                bump_retry(["missing_item_in_regen"])
                log_reject(f"regen{retry}", sid, spec, "", ["missing_item_in_regen"])
                new_failed.append(sid)
                continue

            prayer_text = got.get("prayer", "").strip()
            prayer_text = normalize_prayer_text(prayer_text, spec["format"])

            ok, reasons = validate_prayer_against_spec(prayer_text, spec)

            if ok:
                finalized[sid] = {
                    **spec,
                    "training_prompt": build_training_prompt(spec),
                    "prayer": prayer_text,
                    "validation": {"ok": True, "reasons": []},
                    "generator_check": got.get("check", {}),
                }
            else:
                bump_retry(reasons)
                log_reject(f"regen{retry}", sid, spec, prayer_text, reasons)
                new_failed.append(sid)

        failed_ids = new_failed

        # NEW: print summary of rejection reasons for this regen round
        if retry_reason_counts:
            print(f"  Rejection reasons (regen {retry}):",
                  dict(sorted(retry_reason_counts.items(), key=lambda x: -x[1])))

    # Anything still failed is dropped (do not poison small datasets)
    if failed_ids:
        print(f"  Dropped {len(failed_ids)} items after regen: {failed_ids[:5]}{'...' if len(failed_ids) > 5 else ''}")

    return list(finalized.values())


# ============================================================================
# RESUME / BATCH DISCOVERY
# ============================================================================

def list_existing_batches(output_dir: Path) -> set:
    existing = set()
    for f in output_dir.glob("batch_*.json"):
        m = re.match(r"batch_(\d{4})\.json$", f.name)
        if m:
            existing.add(int(m.group(1)))
    return existing

# ============================================================================
# MAIN
# ============================================================================

def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable!")
        print("Get your key from: https://console.anthropic.com/settings/keys")
        return

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    OUTPUT_DIR.mkdir(exist_ok=True)

    num_batches = TARGET_TOTAL // BATCH_SIZE
    format_cycle = itertools.cycle(FORMAT_STYLES)

    print("🔧 Mechanicus Prayer Dataset Generator (Claude Haiku)")
    print("━" * 70)
    print(f"Target: {TARGET_TOTAL} prayers ({num_batches} batches × {BATCH_SIZE})")
    print(f"Model: {MODEL}")
    print(f"Output: {OUTPUT_DIR.resolve()}")
    print(f"Topics: {len(ALL_TOPICS)}")
    print(f"Formats enabled: {FORMAT_STYLES}")
    print(f"Validation: component>=2 occurrences, component in >=3 lines, operation>=1, 4–10 lines")
    print("━" * 70)

    existing = list_existing_batches(OUTPUT_DIR)
    print(f"Resume: found {len(existing)} existing batch files.")

    all_rows: List[Dict] = []

    # Load existing batches (so final combined + training file includes them)
    for bidx in sorted(existing):
        batch_file = OUTPUT_DIR / f"batch_{bidx:04d}.json"
        try:
            with open(batch_file, "r", encoding="utf-8") as f:
                rows = json.load(f)
                if isinstance(rows, list):
                    all_rows.extend(rows)
        except Exception:
            pass

    successful = 0
    for batch_idx in range(num_batches):
        if batch_idx in existing:
            continue

        fmt = next(format_cycle)
        print(f"\n[Batch {batch_idx + 1}/{num_batches}] format={fmt}")

        try:
            rows = generate_validated_batch(
                client=client,
                topics=ALL_TOPICS,
                fmt=fmt,
                batch_idx=batch_idx,
            )
        except Exception as e:
            print(f"  ✗ Batch {batch_idx:04d} failed hard: {e}")
            time.sleep(RATE_LIMIT_DELAY)
            continue

        print(f"  ✓ Kept {len(rows)}/{BATCH_SIZE} after validation+regen")
        if rows:
            successful += 1
            all_rows.extend(rows)

            batch_file = OUTPUT_DIR / f"batch_{batch_idx:04d}.json"
            with open(batch_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)

        # Rate limiting
        if batch_idx < num_batches - 1:
            time.sleep(RATE_LIMIT_DELAY)

    # Combine + output training text
    combined_file = OUTPUT_DIR / "all_prayers.json"
    with open(combined_file, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, indent=2, ensure_ascii=False)

    # Create training file for nanoGPT (or similar)
    training_file = OUTPUT_DIR / "training_data.txt"
    with open(training_file, "w", encoding="utf-8") as f:
        for row in all_rows:
            # We train the model to produce the prayer given the structured prompt block
            f.write(f"<|user|>{row['training_prompt']}<|end|>\n")
            f.write(f"<|assistant|>{row['prayer']}<|end|>\n\n")

    # Stats
    print("\n" + "━" * 70)
    print("✓ Generation complete!")
    print(f"  New successful batches this run: {successful}")
    print(f"  Total retained examples: {len(all_rows)}")
    print(f"  Combined JSON: {combined_file}")
    print(f"  Training file: {training_file}")

    if all_rows:
        total_chars = sum(len(r.get("training_prompt", "")) + len(r.get("prayer", "")) for r in all_rows)
        avg_prayer_len = sum(len(r.get("prayer", "")) for r in all_rows) / len(all_rows)

        fmt_counts: Dict[str, int] = {}
        for r in all_rows:
            k = r.get("format", "unknown")
            fmt_counts[k] = fmt_counts.get(k, 0) + 1

        print("\n📊 Dataset Statistics:")
        print(f"  Total characters: {total_chars:,}")
        print(f"  Estimated tokens: ~{total_chars // 4:,}")
        print(f"  Avg prayer length: {avg_prayer_len:.0f} chars")
        print("  Format distribution:")
        for k, c in sorted(fmt_counts.items(), key=lambda x: -x[1]):
            print(f"    {k}: {c} ({100*c/len(all_rows):.1f}%)")

    print("\n🎯 Notes:")
    print("  - This dataset is now strongly conditioned: GPT-2 sees explicit COMPONENT/OPERATION/FORMAT controls.")
    print("  - If you later want freer user prompts, keep the control block but allow REQUEST to be more varied.")
    print("  - Once adherence is strong, you can re-enable more formats (prose/binary/brief) in FORMAT_STYLES.")


if __name__ == "__main__":
    main()
