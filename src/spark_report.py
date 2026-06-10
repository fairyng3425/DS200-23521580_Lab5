import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd

from common import now_iso, relative_to_base, sanitize_name
from config import EXPERIMENTS_DIR


def parse_java_major(version_text: str) -> Optional[int]:
    text = version_text.strip()
    match = re.search(r'version "([0-9]+)(?:\.([0-9]+))?', text)
    if not match:
        match = re.search(r'openjdk version "([0-9]+)(?:\.([0-9]+))?', text)
    if not match:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2):
        return int(match.group(2))
    return major


def java_major_version() -> Optional[int]:
    try:
        proc = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=5)
        return parse_java_major((proc.stderr or "") + "\n" + (proc.stdout or ""))
    except Exception:
        return None


def pandas_report(csv_path: Path, report_dir: Path, reason: str = "") -> dict:
    df = pd.read_csv(csv_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    frame_count = int(len(df))
    total_people = int(df["person_count"].sum()) if frame_count else 0
    summary = {
        "generated_at": now_iso(),
        "engine": "python_fallback",
        "fallback_reason": reason,
        "frames_processed": frame_count,
        "total_person_detections": total_people,
        "avg_persons_per_frame": round(float(df["person_count"].mean()), 4) if frame_count else 0,
        "max_persons_in_frame": int(df["person_count"].max()) if frame_count else 0,
        "min_persons_in_frame": int(df["person_count"].min()) if frame_count else 0,
        "avg_processing_time_ms": round(float(df["processing_time_ms"].mean()), 4) if frame_count else 0,
    }

    by_count = df.groupby("person_count", as_index=False).size().rename(columns={"size": "num_frames"})
    by_count = by_count.sort_values("person_count")
    by_count.to_csv(report_dir / "frames_by_person_count.csv", index=False, encoding="utf-8")

    useful_cols = [c for c in ["frame_id", "person_count", "processing_time_ms", "annotated_frame"] if c in df.columns]
    df[useful_cols].to_csv(report_dir / "frame_level_report.csv", index=False, encoding="utf-8")

    out_path = report_dir / "report_summary.json"
    summary["files"] = {
        "report_summary": relative_to_base(out_path),
        "frames_by_person_count": relative_to_base(report_dir / "frames_by_person_count.csv"),
        "frame_level_report": relative_to_base(report_dir / "frame_level_report.csv"),
    }
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def pyspark_report(csv_path: Path, report_dir: Path) -> dict:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import avg, count, max as spark_max, min as spark_min, sum as spark_sum

    report_dir.mkdir(parents=True, exist_ok=True)
    spark = SparkSession.builder.master("local[*]").appName("DS200_Lab05_PeopleCounter_Report").getOrCreate()
    try:
        df = spark.read.option("header", True).option("inferSchema", True).csv(str(csv_path))
        agg_row = df.agg(
            count("frame_id").alias("frames_processed"),
            spark_sum("person_count").alias("total_person_detections"),
            avg("person_count").alias("avg_persons_per_frame"),
            spark_max("person_count").alias("max_persons_in_frame"),
            spark_min("person_count").alias("min_persons_in_frame"),
            avg("processing_time_ms").alias("avg_processing_time_ms"),
        ).collect()[0]

        df.groupBy("person_count").count().orderBy("person_count").coalesce(1).write.mode("overwrite").option("header", True).csv(str(report_dir / "frames_by_person_count_spark"))
        df.select("frame_id", "person_count", "processing_time_ms", "annotated_frame").coalesce(1).write.mode("overwrite").option("header", True).csv(str(report_dir / "frame_level_report_spark"))

        summary = {
            "generated_at": now_iso(),
            "engine": "pyspark",
            "frames_processed": int(agg_row["frames_processed"] or 0),
            "total_person_detections": int(agg_row["total_person_detections"] or 0),
            "avg_persons_per_frame": round(float(agg_row["avg_persons_per_frame"] or 0), 4),
            "max_persons_in_frame": int(agg_row["max_persons_in_frame"] or 0),
            "min_persons_in_frame": int(agg_row["min_persons_in_frame"] or 0),
            "avg_processing_time_ms": round(float(agg_row["avg_processing_time_ms"] or 0), 4),
        }
        out_path = report_dir / "report_summary.json"
        summary["files"] = {
            "report_summary": relative_to_base(out_path),
            "frames_by_person_count_spark_dir": relative_to_base(report_dir / "frames_by_person_count_spark"),
            "frame_level_report_spark_dir": relative_to_base(report_dir / "frame_level_report_spark"),
        }
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        spark.stop()


def report_one_experiment(exp_dir: Path, force_python: bool = False) -> dict:
    csv_path = exp_dir / "results" / "detections.csv"
    report_dir = exp_dir / "report"
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {csv_path}")

    if force_python:
        return pandas_report(csv_path, report_dir, reason="Người dùng chọn --force-python")

    java_major = java_major_version()
    if java_major is None:
        return pandas_report(csv_path, report_dir, reason="Không tìm thấy Java, dùng Python fallback để không lỗi Spark")
    if java_major < 17:
        return pandas_report(csv_path, report_dir, reason=f"Java hiện tại là {java_major}, PySpark mới cần Java 17; dùng Python fallback")

    try:
        return pyspark_report(csv_path, report_dir)
    except Exception as exc:
        return pandas_report(csv_path, report_dir, reason=f"PySpark lỗi nên tự động dùng Python fallback: {type(exc).__name__}: {exc}")


def collect_all_experiments() -> list[Path]:
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted([p for p in EXPERIMENTS_DIR.iterdir() if (p / "results" / "detections.csv").exists()])


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo báo cáo Big Data. Có PySpark thì dùng PySpark, không có Java 17 thì tự fallback sang Python nên không bị crash.")
    parser.add_argument("--experiment-name", help="Tên experiment trong output\\experiments")
    parser.add_argument("--all", action="store_true", help="Tạo report cho tất cả experiments")
    parser.add_argument("--force-python", action="store_true", help="Ép dùng Python fallback, không gọi Spark")
    args = parser.parse_args()

    if args.experiment_name:
        experiments = [EXPERIMENTS_DIR / sanitize_name(args.experiment_name)]
    elif args.all:
        experiments = collect_all_experiments()
    else:
        experiments = collect_all_experiments()[-1:]

    if not experiments:
        print("[Report] Chưa có experiment nào để tạo report.")
        return

    all_summaries = []
    for exp_dir in experiments:
        summary = report_one_experiment(exp_dir, force_python=args.force_python)
        all_summaries.append({"experiment_name": exp_dir.name, **summary})
        print(f"[Report] {exp_dir.name}: engine={summary['engine']}, frames={summary['frames_processed']}, avg={summary['avg_persons_per_frame']}")
        if summary.get("fallback_reason"):
            print(f"[Report] Fallback: {summary['fallback_reason']}")

    if len(all_summaries) > 1:
        out_csv = EXPERIMENTS_DIR.parent / "all_experiments_summary.csv"
        pd.DataFrame(all_summaries).to_csv(out_csv, index=False, encoding="utf-8")
        print(f"[Report] Đã lưu tổng hợp tất cả experiments: {relative_to_base(out_csv)}")


if __name__ == "__main__":
    main()
