from __future__ import annotations

from pathlib import Path

from householdos.evaluation.harness import run_capstone_benchmark


root = Path(__file__).resolve().parents[2]
knowledge_path = root / "data/knowledge_items.json"
if not knowledge_path.exists():
    knowledge_path = root / "data/sample_knowledge_items.json"
result = run_capstone_benchmark(str(knowledge_path))
print(result.model_dump_json(indent=2))
