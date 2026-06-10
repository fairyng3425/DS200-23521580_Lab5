import base64
import json
import re
import socket
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import cv2
import numpy as np

from config import EXPERIMENTS_DIR


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp_for_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_name(name: str) -> str:
    name = str(name).strip().replace("\\", "/")
    name = name.split("/")[-1]
    name = Path(name).stem if "." in name else name
    name = re.sub(r"[^A-Za-z0-9_\-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "experiment"


def make_experiment_name(source: str, experiment_name: Optional[str] = None) -> str:
    if experiment_name:
        base = sanitize_name(experiment_name)
    else:
        base = f"webcam_{source}" if str(source).isdigit() else sanitize_name(source)
    return f"{base}_{timestamp_for_name()}"


def experiment_dir(experiment_name: str) -> Path:
    return EXPERIMENTS_DIR / sanitize_name(experiment_name)


def ensure_experiment_dirs(experiment_name: str) -> Dict[str, Path]:
    root = experiment_dir(experiment_name)
    dirs = {
        "root": root,
        "results": root / "results",
        "annotated": root / "annotated_frames",
        "report": root / "report",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs


def send_json_line(sock: socket.socket, obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"
    sock.sendall(data)


def iter_json_lines(sock: socket.socket) -> Iterable[Dict[str, Any]]:
    file = sock.makefile("rb")
    for raw in file:
        raw = raw.strip()
        if not raw:
            continue
        try:
            yield json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            print(f"[Common] Bỏ qua JSON lỗi: {exc}")


def connect_with_retry(host: str, port: int, label: str, retries: int = 60, delay: float = 0.5) -> socket.socket:
    last_exc = None
    for _ in range(retries):
        try:
            sock = socket.create_connection((host, port), timeout=5)
            print(f"[{label}] Đã kết nối {host}:{port}")
            return sock
        except OSError as exc:
            last_exc = exc
            time.sleep(delay)
    raise ConnectionError(f"Không kết nối được {label} tại {host}:{port}: {last_exc}")


def encode_frame_to_b64(frame: np.ndarray, quality: int = 85) -> str:
    quality = max(10, min(100, int(quality)))
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise ValueError("Không encode được frame thành JPEG")
    return base64.b64encode(buffer).decode("ascii")


def decode_frame_from_b64(image_b64: str) -> np.ndarray:
    data = base64.b64decode(image_b64.encode("ascii"))
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Không decode được frame từ base64")
    return frame


def draw_detections(frame: np.ndarray, boxes: list, count: int) -> np.ndarray:
    out = frame.copy()
    cv2.putText(out, f"Count: {count}", (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2, cv2.LINE_AA)
    for box in boxes:
        x1 = int(box.get("x1", 0))
        y1 = int(box.get("y1", 0))
        x2 = int(box.get("x2", 0))
        y2 = int(box.get("y2", 0))
        conf = float(box.get("confidence", 0.0))
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"person {conf:.2f}"
        cv2.putText(out, label, (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
    return out


def relative_to_base(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path(__file__).resolve().parents[1]))
    except Exception:
        return str(path)
