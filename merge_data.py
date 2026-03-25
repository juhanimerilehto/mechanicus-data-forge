import json
from pathlib import Path

# Combine all datasets
all_prayers = []
datasets = [
    'mechanicus_prayers_dataset1',
    'mechanicus_prayers_dataset2', 
    'mechanicus_prayers_dataset_haiku1',
    'mechanicus_prayers_dataset_haiku2',
    'mechanicus_prayers_dataset_haiku3',
    'mechanicus_prayers_dataset_haiku4'
]

for dataset in datasets:
    file = Path(dataset) / 'all_prayers.json'
    if file.exists():
        prayers = json.loads(file.read_text(encoding='utf-8'))
        all_prayers.extend(prayers)
        print(f"✓ Loaded {len(prayers)} from {dataset}")
    else:
        print(f"✗ Not found: {file}")

print(f"\n📊 Total prayers: {len(all_prayers)}")

# Save combined
Path('final_mechanicus_dataset').mkdir(exist_ok=True)
Path('final_mechanicus_dataset/all_prayers.json').write_text(
    json.dumps(all_prayers, indent=2, ensure_ascii=False), 
    encoding='utf-8'
)

# Create training file
with open('final_mechanicus_dataset/train.txt', 'w', encoding='utf-8') as f:
    for p in all_prayers:
        f.write(f"<|user|>{p['prompt']}<|end|>\n<|assistant|>{p['prayer']}<|end|>\n\n")

print(f"✓ Saved to final_mechanicus_dataset/")
print(f"  - all_prayers.json")
print(f"  - train.txt")