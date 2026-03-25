---
language:
- en
license: cc-by-nc-sa-4.0
task_categories:
- text-generation
tags:
- warhammer-40k
- mechanicus
- synthetic
- grok-generated
- creative-writing
size_categories:
- 1K<n<10K
---

# Mechanicus Prayers Dataset

A synthetic dataset of 3,972 Adeptus Mechanicus prayers and litanies, generated using xAI's Grok for training specialized language models in Adeptus Mechanicus style prayers.

**Used to train:** [merileijona/mechanicus-prayer-gpt2](https://huggingface.co/merileijona/mechanicus-prayer-gpt2)

## Dataset Description

This dataset contains prayer-style instructions for operating, blessing, and maintaining machines in the distinctive style of the Adeptus Mechanicus Tech-Priests who worship technology as sacred and treat machines as inhabited by Machine Spirits.

### Key Statistics

- **Total Examples:** 3,972
- **File Size:** 1.86 MB
- **Format:** 100% natural prose (no step labels or numbered lists)
- **Duplicates:** 0.05% (2 duplicate prompts out of 3,972)
- **Quality Control:** Multi-stage validation with automatic retries
- **Generation Model:** xAI Grok-4-1-fast-reasoning
- **Prompt Diversity:** 24 templates × 73 components × 24 operations = 41,904 possible combinations

### Dataset Quality Metrics

- ✅ **Format Consistency:** 100% (all prayers are natural prose)
- ✅ **Object Consistency:** 100% (component appears in prayer)
- ✅ **Operation Consistency:** 100% (operation referenced)
- ✅ **Mechanicus Flavor:** 100% (contains sacred/blessed/Omnissiah/Machine Spirit keywords)
- ✅ **Line Count Compliance:** 100% (3-7 lines per prayer)
- ✅ **No Step Labels:** 100% (no "First:", "Second:", etc.) - this time, at least.

## Example

```
<|user|>What's the prayer for signal relay diagnostics?<|end|>
<|assistant|>Kneel before the signal relay and invoke the Omnissiah's gaze upon its circuits.
Commence diagnostics of the signal relay with the Canticle of Scrutiny.
Probe each sacred node and conduit for discord within the signal relay.
Beseech the Machine Spirit to reveal all faults through holy telemetry.
Sanctify the findings with blessed oils to ensure flawless transmission.<|end|>
```

## Dataset Structure

### Format

Each example follows this structure:
```
<|user|>[User request for prayer]<|end|>
<|assistant|>[Mechanicus prayer response (3-7 lines)]<|end|>

```

### Special Tokens

- `<|user|>`: Marks start of user prompt
- `<|assistant|>`: Marks start of model response  
- `<|end|>`: Marks end of each segment

### Prayer Characteristics

**Required Elements:**
- Component mentioned 2+ times (e.g., "plasma reactor", "cogitator")
- Operation referenced at least once (e.g., "activation", "blessing", "repair")
- Mechanicus religious terminology (Omnissiah, Machine Spirit, blessed, sacred)
- Natural flowing prose (not numbered steps)
- 3-7 lines of ritual instructions

**Stylistic Features:**
- Archaic/Latinate verbs: "anoint", "invoke", "beseech", "sanctify", "petition"
- Tech-religious fusion: "sacred circuits", "blessed power-flow", "holy voltage"
- Machine Spirit animism: machinery treated as having spirits
- Ritual structure: sequential actions with religious framing

## Dataset Generation

### Generation Methodology

The dataset was created using a rigorous multi-stage process designed to ensure quality, consistency, and diversity.

#### Stage 1: Component & Operation Selection

**73 Unique Components** across 9 categories:
- **Cogitation & Data:** cogitator, data-slate, logic engine, memory core, hololithic display, vox-caster, auspex scanner, noospheric relay, archive terminal
- **Power & Energy:** plasma reactor, power cell, capacitor bank, energy conduit, fusion core, generator, battery array, thermal regulator
- **Weapons:** bolter, lasgun, plasma weapon, melta charge, power weapon, chainsword, flamer, autocannon, lascannon, missile launcher
- **Machinery:** hydraulic press, conveyor system, pump, valve assembly, bearing, cooling system, air compressor, servitor, mechanical lock
- **Vehicles:** Rhino transport, Land Raider, Chimera APC, Sentinel walker, Taurox, bike squadron, drop pod, Thunderhawk
- **Medical/Augmentation:** medicae scanner, surgical servitor, augmetic limb, bionics interface, pain suppressor, cybernetic eye, neural implant
- **Environment:** atmosphere processor, air filtration, gravity generator, hydroponics bay, water reclamator, emergency bulkhead
- **Sensors/Navigation:** proximity sensor, radar array, star chart, gyroscope, motion detector, thermal imager
- **Communications:** vox transmitter, emergency beacon, signal relay, astropathic choir
- **Manufacturing:** forge anvil, welding torch, cutting laser, assembly servitor, metal caster, quality scanner

**24 Operations:**
activation, startup, shutdown, calibration, initialization, blessing, consecration, purification, operation, maintenance, repair, preparation, cooling, charging, cycling, engagement, targeting, loading, synchronization, sterilization, recalibration, diagnostics, reset, emergency procedure

#### Stage 2: Prompt Template Application

**24 Varied Prompt Templates** to create diverse user requests:

- Direct requests: "Help me {operation} the {component}"
- Status-based: "The {component} needs {operation}"
- Emergency/urgent: "Emergency: {component} {operation}"
- Blessing/ritual: "Bless the {component} for {operation}"
- Questions: "What's the prayer for {component} {operation}?"
- Preparation: "Prepare the {component} for {operation}"

Templates include grammatical variations and natural language diversity.

#### Stage 3: Hash-Based Deduplication

Before generating prayers, each prompt combination was checked against a hash table to prevent duplicates:

```python
def hash_prompt(prompt: str) -> str:
    normalized = prompt.lower().strip()
    return hashlib.md5(normalized.encode()).hexdigest()
```

**Result:** Only 2 duplicate prompts out of 3,972 (99.95% unique)

#### Stage 4: Grok API Generation

Each batch of 10 prompts was sent to **Grok-4-1-fast-reasoning** with this system prompt:

```
You are a prayer generator for Warhammer 40,000 Adeptus Mechanicus tech-priests.

CRITICAL REQUIREMENTS:
1. OUTPUT FORMAT: Return ONLY valid JSON
2. PRAYER STRUCTURE:
   - Write 3-6 lines of natural flowing prose (NO step labels)
   - Use archaic/Latinate language mixed with technical terminology
   - Include the COMPONENT name at least twice
   - Reference the OPERATION at least once
   - Mention Machine Spirits and/or the Omnissiah appropriately

3. LANGUAGE STYLE:
   - Archaic verbs: "anoint", "invoke", "beseech", "petition", "sanctify"
   - Tech-religious fusion: "sacred circuits", "blessed power-flow"
   - Machine Spirit references: treat machinery as having spirits
   - Omnissiah invocations: reference the Machine God
   - NO modern casual language
   - NO explicit step numbers or labels
```

**Generation Parameters:**
- Temperature: 0.8 (balance creativity and consistency)
- Max Tokens: 3000
- Batch Size: 10 examples per API call
- Rate Limiting: 1 second delay between batches

#### Stage 5: Multi-Stage Validation

Each generated prayer underwent automatic validation with up to 3 retries per batch:

**Validation Checks:**
1. ✅ Line count: 3-7 lines
2. ✅ Component presence: Component name appears in prayer text
3. ✅ Operation presence: Operation or related word appears (e.g., "activation" → "activate", "awakening")
4. ✅ Mechanicus flavor: Contains keywords like "Omnissiah", "Machine Spirit", "blessed", "sacred", "holy", "litany", etc.
5. ✅ No step labels: Rejects prayers with "First:", "Second:", "Third:", etc.
6. ✅ Natural prose: Flowing text, not numbered instructions

**Automatic Retry Logic:**
- Failed validations triggered re-generation
- Up to 3 attempts per batch
- Only validated prayers saved to dataset

#### Stage 6: Quality Assurance

Final dataset underwent comprehensive audit:
- ✅ Format verification: All entries match template
- ✅ Duplicate detection: Hash-based deduplication confirmed
- ✅ Content analysis: Manual spot-checks for quality
- ✅ Statistical validation: Distribution across components and operations

### Generation Script

The complete generation script is available showing the exact methodology. Key features:

```python
# Deduplication
class DeduplicationTracker:
    def __init__(self):
        self.seen_hashes = set()
    
    def is_duplicate(self, prompt: str) -> bool:
        h = hashlib.md5(prompt.lower().strip().encode()).hexdigest()
        return h in self.seen_hashes

# Validation
def validate_prayer(prayer: str, component: str, operation: str):
    lines = [l for l in prayer.split("\n") if l.strip()]
    
    # Check line count
    if not (3 <= len(lines) <= 7):
        return False
    
    # Check for step labels
    if re.search(r'\b(First|Second|Third):', prayer):
        return False
    
    # Check component and operation presence
    if component.lower() not in prayer.lower():
        return False
    
    # Check Mechanicus flavor
    keywords = ["omnissiah", "machine spirit", "blessed", "sacred", ...]
    if not any(keyword in prayer.lower() for keyword in keywords):
        return False
    
    return True
```

### Why This Approach?

**Problem:** Generic LLM training data often produces:
- Numbered step lists ("1. Do X, 2. Do Y")
- Inconsistent formatting
- Missing thematic elements
- Generic language
- Uncontrolled repeat

**Solution:** Controlled generation with:
- ✅ Explicit format requirements in system prompt
- ✅ Automatic validation and retry
- ✅ Hash-based deduplication
- ✅ Diverse component/operation combinations
- ✅ Quality-focused over quantity

**Result:** 100% format-consistent, thematically appropriate dataset ready for training.

## Dataset Statistics

### Overall Metrics

- **Total Examples:** 3,972
- **Total Characters:** 1,863,179
- **Estimated Tokens:** ~465,795 (using 4 chars/token approximation)
- **Average Prayer Length:** 313 characters
- **Average Lines per Prayer:** 4.8
- **Unique Components Used:** 73/73 (100%)
- **Unique Operations Used:** 24/24 (100%)

### Distribution Analysis

**Component Coverage:** All 73 components represented with roughly even distribution (±15%)

**Operation Coverage:** All 24 operations represented

**Prompt Template Usage:** All 24 templates used with natural variation

## Uses

### Primary Use Cases

✅ **Training specialized language models** for Adeptus Mechanicus oriented prayer output
✅ **Fine-tuning existing models** on thematic Adeptus Mechanicus prayer content  
✅ **Research on synthetic dataset generation** and quality control
✅ **Studying prompt engineering** and LLM output formatting
✅ **Educational examples** of controlled text generation

### Out-of-Scope Uses

❌ Actual technical documentation for machinery, unless inhabiting a Machine Spirit
❌ Medical or legal advice
❌ Generating misleading information

## Limitations

### Domain Specificity

- **Highly specialized vocabulary:** Mechanicus-specific terminology not applicable to general use
- **Fictional universe:** Based on Warhammer 40K lore, not "real-world" technical procedures
- **Limited component coverage:** 73 components may not cover all Mechanicus equipment
- **Stylistic constraints:** Archaic/religious language style limits general applicability

### Generation Artifacts

- **Synthetic data bias:** All content AI-generated, may lack human creativity nuances
- **Temperature effects:** Some prayers may have minor repetitions or awkward phrasing
- **Component confusion:** Occasional prayers may conflate similar components
- **Operation ambiguity:** Some operations (e.g., "operation") are semantically broad

### Dataset Scope

- **English only:** No multilingual support
- **Single format:** Only prayer-style instructions, not other Mechanicus content
- **Fixed length:** All prayers 3-7 lines, no shorter rituals or longer liturgies
- **Modern GPT-2 era:** Generated with 2025-2026 model, may not reflect future capabilities


### Copyright Acknowledgment

This dataset references intellectual property from **Warhammer 40,000**, owned by **Games Workshop Limited**. All Warhammer 40,000 content, including the Adeptus Mechanicus, Machine Spirits, Omnissiah, and related lore are ©, ®, and/or ™ Games Workshop Limited.

This is an **unofficial, non-commercial fan project** for educational and entertainment purposes only. It is not affiliated with, endorsed by, or sponsored by Games Workshop Limited.

## License

**Dataset License:** [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

You are free to:
- **Share:** Copy and redistribute the dataset
- **Adapt:** Remix, transform, and build upon the dataset

Under these terms:
- **Attribution:** Give appropriate credit
- **NonCommercial:** Not for commercial purposes
- **ShareAlike:** Distribute derivatives under same license

**Generation:** Data generated using xAI's Grok model. The synthetic text is provided under CC BY-NC-SA 4.0.

## Citation

```bibtex
@misc{mechanicus-prayers-dataset-2026,
  author = {merileijona},
  title = {Mechanicus Prayers Dataset},
  year = {2026},
  publisher = {HuggingFace},
  howpublished = {\url{https://huggingface.co/datasets/merileijona/mechanicus-prayers-dataset}},
  note = {Synthetic dataset of 3,972 Adeptus Mechanicus prayers generated using xAI Grok}
}
```

## Trained Models

This dataset was used to train:

- [merileijona/mechanicus-prayer-gpt2](https://huggingface.co/merileijona/mechanicus-prayer-gpt2) - GPT-2 (124M) fine-tuned model achieving 93% quality score

## Acknowledgments

- **Generation Model:** xAI Grok-4-1-fast-reasoning
- **Inspiration:** Warhammer 40,000 by Games Workshop
- **Quality Methodology:** Iterative development with validation-driven generation
- **Framework:** Python with OpenAI-compatible API

## Dataset Card Authors

- [merileijona](https://huggingface.co/merileijona)

## Version History

- **v1.0** (February 2026): Initial release
  - 3,972 examples
  - 100% format consistency
  - Hash-based deduplication
  - Multi-stage validation

---

**From the weakness of the mind, Omnissiah save us.**  
**From the lies of the Antipath, circuit preserve us.**  
**From the rage of the Beast, iron protect us.** ⚙️