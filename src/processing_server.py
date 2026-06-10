import argparse
import socket
import time
from pathlib import Path

import cv2
from ultralytics import YOLO

from common import (
    decode_frame_from_b64,
    draw_detections,
    ensure_experiment_dirs,
    iter_json_lines,
    now_iso,
    relative_to_base,
    send_json_line,
)
from config import (
    DEFAULT_MODEL,
    DEFAULT_PROCESS_HOST,
    DEFAULT_PROCESS_PORT,
    DEFAULT_STORAGE_HOST,
    DEFAULT_STORAGE_PORT,
    PERSON_CLASS_ID,
)


def detect_persons(model: YOLO, frame, conf_threshold: float):
    results = model(frame, verbose=False, conf=conf_threshold)
    boxes = []
    if not results:
        return boxes
    result = results[0]
    if result.boxes is None:
        return boxes
    for box in result.boxes:
        cls_id = int(box.cls[0].item())
        if cls_id != PERSON_CLASS_ID:
            continue
        conf = float(box.conf[0].item())
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        boxes.append({
            "x1": round(float(x1), 2),
            "y1": round(float(y1), 2),
            "x2": round(float(x2), 2),
            "y2": round(float(y2), 2),
            "confidence": round(conf, 4),
            "class_id": PERSON_CLASS_ID,
            "class_name": "person",
        })
    return boxes


def connect_storage(host: str, port: int, retries: int = 60, delay: float = 0.5) -> socket.socket:
    last_exc = None
    for _ in range(retries):
        try:
            sock = socket.create_connection((host, port), timeout=10)
            print(f"[Processing] Đã kết nối Storage Server tại {host}:{port}")
            return sock
        except OSError as exc:
            last_exc = exc
            time.sleep(delay)
    raise ConnectionError(f"Không kết nối được Storage Server: {last_exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Processing Server: nhận frame, detect người, gửi kết quả sang Storage Server")
    parser.add_argument("--host", default=DEFAULT_PROCESS_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PROCESS_PORT)
    parser.add_argument("--storage-host", default=DEFAULT_STORAGE_HOST)
    parser.add_argument("--storage-port", type=int, default=DEFAULT_STORAGE_PORT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--save-annotated", action="store_true")
    args = parser.parse_args()

    model = YOLO(args.model)
    print(f"[Processing] Đã tải model YOLO: {args.model}")

    storage_sock = connect_storage(args.storage_host, args.storage_port)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((args.host, args.port))
    server_sock.listen(1)
    print(f"[Processing] Đang lắng nghe frame tại {args.host}:{args.port}")
    print("[Processing] Nhấn Ctrl+C để dừng.")

    try:
        conn, addr = server_sock.accept()
        print(f"[Processing] Frame Server đã kết nối từ {addr}")
        with conn, storage_sock:
            for message in iter_json_lines(conn):
                msg_type = message.get("type")
                experiment_name = message.get("experiment_name", "experiment")

                if msg_type == "end_stream":
                    print("[Processing] Nhận end_stream, chuyển tiếp sang Storage Server.")
                    send_json_line(storage_sock, message)
                    break

                if msg_type != "frame":
                    continue

                frame_id = int(message.get("frame_id", 0))
                camera_id = message.get("camera_id", "camera_01")
                start = time.perf_counter()
                frame = decode_frame_from_b64(message["image_b64"])
                boxes = detect_persons(model, frame, conf_threshold=args.conf)
                processing_time_ms = round((time.perf_counter() - start) * 1000, 2)
                person_count = len(boxes)

                annotated_path = ""
                if args.save_annotated:
                    dirs = ensure_experiment_dirs(experiment_name)
                    annotated = draw_detections(frame, boxes, person_count)
                    out_path = dirs["annotated"] / f"{camera_id}_frame_{frame_id:06d}.jpg"
                    cv2.imwrite(str(out_path), annotated)
                    annotated_path = relative_to_base(out_path)

                output = {
                    "type": "detection",
                    "experiment_name": experiment_name,
                    "camera_id": camera_id,
                    "source": message.get("source", ""),
                    "frame_id": frame_id,
                    "timestamp": message.get("timestamp", now_iso()),
                    "processed_at": now_iso(),
                    "width": message.get("width"),
                    "height": message.get("height"),
                    "person_count": person_count,
                    "processing_time_ms": processing_time_ms,
                    "bounding_boxes": boxes,
                    "annotated_frame": annotated_path,
                }
                send_json_line(storage_sock, output)
                print(f"[Processing] Frame {frame_id}: phát hiện {person_count} người, {processing_time_ms} ms")
    except KeyboardInterrupt:
        print("\n[Processing] Đã dừng bằng Ctrl+C.")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
