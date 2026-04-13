import json
import os
import shutil
import re
from pathlib import Path

def normalize(name):
    # Remove punctuation, spaces and lowercase
    return re.sub(r'[^a-zA-Z0-9]', '', name).lower()

def gather_benchmark_corpus():
    print("Loading QA datasets...")
    r_qa_path = Path("data/research_papers_golden_qa.json")
    s_qa_path = Path("synthetic_data_v2/golden_qa_dataset.json")
    
    needed = set()
    if r_qa_path.exists():
        with open(r_qa_path, 'r', encoding='utf-8') as f:
            r_qa = json.load(f)
            needed.update([q.get('source_document') for q in r_qa if q.get('source_document')])
    if s_qa_path.exists():
        with open(s_qa_path, 'r', encoding='utf-8') as f:
            s_qa = json.load(f)
            needed.update([q.get('source_document') for q in s_qa if q.get('source_document')])
            
    print(f"Total unique documents needed: {len(needed)}")
    
    out_dir = Path("data/benchmark_corpus")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Pre-map all available files to their normalized names
    file_map = {}
    for root in ["data/curated_papers", "synthetic_data_v2"]:
        for f in Path(root).rglob('*'):
            if f.is_file():
                file_map[normalize(f.name)] = f
                file_map[normalize(f.stem)] = f
    
    found_count = 0
    for n in needed:
        norm_n = normalize(n)
        if norm_n in file_map:
            src = file_map[norm_n]
            shutil.copy2(src, out_dir / src.name)
            found_count += 1
        else:
            # Try splitting by underscore for synthetic docs
            found_any = False
            for chunk in n.split('_'):
                if normalize(chunk) in file_map:
                    # This might be risky, ignore for now unless needed
                    pass
            print(f"[MISSING] Could not find: {n}")
            
    print(f"\n[DONE] Gathered {found_count} documents into {out_dir}")

if __name__ == "__main__":
    gather_benchmark_corpus()
