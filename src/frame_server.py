import argparse
import socket
import time
from pathlib import Path
from typing import Union

import cv2

from common import encode_frame_to_b64, now_iso, send_json_line
from config import DEFAULT_CAMERA_ID, DEFAULT_PROCESS_HOST, DEFAULT_PROCESS_PORT


def parse_source(source: str) -> Union[int, str]:
    return int(source) if str(source).isdigit() else source


def main() -> None:
    parser = argparse.ArgumentParser(description="Frame Server: đọc camera/video và gửi frame sang Processing Server")
    parser.add_argument("--source", required=True, help="0 cho webcam hoặc đường dẫn video, ví dụ data\\video\\people.mp4")
    parser.add_argument("--processing-host", default=DEFAULT_PROCESS_HOST)
    parser.add_argument("--processing-port", type=int, default=DEFAULT_PROCESS_PORT)
    parser.add_argument("--camera-id", default=DEFAULT_CAMERA_ID)
    parser.add_argument("--experiment-name", required=True, help="Tên lần chạy, dùng để lưu output riêng")
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--max-frames", type=int, default=150)
    parser.add_argument("--jpg-quality", type=int, default=85)
    parser.add_argument("--display", action="store_true")
    args = parser.parse_args()

    source_for_cv = parse_source(args.source)
    cap = cv2.VideoCapture(source_for_cv)
    if not cap.isOpened():
        raise RuntimeError(f"Không mở được nguồn video/camera: {args.source}")

    sleep_time = 0 if args.fps <= 0 else 1.0 / args.fps
    frame_id = 0

    with socket.create_connection((args.processing_host, args.processing_port), timeout=20) as sock:
        print(f"[FrameServer] Đã kết nối Processing Server tại {args.processing_host}:{args.processing_port}")
        print(f"[FrameServer] Source: {args.source}")
        print(f"[FrameServer] Experiment: {args.experiment_name}")

        while True:
            if args.max_frames > 0 and frame_id >= args.max_frames:
                break

            ok, frame = cap.read()
            if not ok:
                print("[FrameServer] Video/camera đã hết frame.")
                break

            frame_id += 1
            height, width = frame.shape[:2]
            image_b64 = encode_frame_to_b64(frame, quality=args.jpg_quality)
            message = {
                "type": "frame",
                "experiment_name": args.experiment_name,
                "camera_id": args.camera_id,
                "source": args.source,
                "frame_id": frame_id,
                "timestamp": now_iso(),
                "width": int(width),
                "height": int(height),
                "image_b64": image_b64,
            }
            send_json_line(sock, message)
            print(f"[FrameServer] Đã gửi frame {frame_id}")

            if args.display:
                cv2.imshow("Frame Server - input", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("[FrameServer] Người dùng nhấn q, kết thúc stream.")
                    break

            if sleep_time > 0:
                time.sleep(sleep_time)

        send_json_line(sock, {
            "type": "end_stream",
            "experiment_name": args.experiment_name,
            "camera_id": args.camera_id,
            "source": args.source,
            "timestamp": now_iso(),
            "last_frame_id": frame_id,
        })
        print("[FrameServer] Đã gửi tín hiệu kết thúc stream.")

    cap.release()
    if args.display:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
