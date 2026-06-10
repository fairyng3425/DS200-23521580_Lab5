import json
from pathlib import Path

from config import EXPERIMENTS_DIR


def main() -> None:
    summaries = sorted(EXPERIMENTS_DIR.glob("*/results/summary.json"))
    if not summaries:
        print("Chưa có kết quả nào trong output/experiments.")
        return
    for path in summaries:
        data = json.loads(path.read_text(encoding="utf-8"))
        print("=" * 70)
        print(f"Experiment: {data.get('experiment_name')}")
        print(f"Source: {data.get('source')}")
        print(f"Frames: {data.get('frames_processed')}")
        print(f"Total detections: {data.get('total_person_detections')}")
        print(f"Avg persons/frame: {data.get('avg_persons_per_frame')}")
        print(f"Max/Min: {data.get('max_persons_in_frame')}/{data.get('min_persons_in_frame')}")
        print(f"Summary file: {path}")


if __name__ == "__main__":
    main()
