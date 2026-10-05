"""
test_model.py - Diagnostic script for the fabric width measurement app.

Reads the camera source from settings.json (selected_camera), grabs ONE frame,
saves full_frame.png and roi_input.png, then runs fabric_new_model.pt at
conf 0.9 / 0.5 / 0.25 and reports boxes/masks counts plus annotated results.

Usage:
    python test_model.py
    python test_model.py <rtsp_url>      # override the camera source

The RTSP URL is read from settings.json by default so the password is never
hardcoded in this file or printed to stdout.
"""

import json
import os
import sys
import platform
import subprocess

import cv2
import numpy as np
from ultralytics import YOLO

# ROI must match app_logic.process_frame()
ROI = (10, 10, 694, 566)
MODEL_PATH = "fabric_new_model.pt"
OUT_FULL = "full_frame.png"
OUT_ROI = "roi_input.png"


def mask_url(url):
    """Show the URL without exposing the password."""
    if not url:
        return url
    if "@" in url:
        creds, rest = url.split("@", 1)
        return f"rtsp://***:***@{rest}"
    return url


def load_source(override=None):
    if override:
        return override
    with open("settings.json", "r") as f:
        s = json.load(f)
    return s.get("selected_camera")


def ping_host(url):
    """Return True if the host part of the URL answers to ping."""
    if not url or "@" not in url:
        return None  # not an IP camera URL
    ip_part = url.split("@")[1].split(":")[0]
    param = "-n" if platform.system().lower() == "windows" else "-c"
    rc = subprocess.call(["ping", param, "1", ip_part],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return rc == 0


def main():
    source = load_source(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Source from settings.json: {source!r}")

    if source is None:
        print("ERROR: no selected_camera in settings.json")
        sys.exit(2)

    if str(source).isdigit():
        print("Source is a webcam index (no network check needed)")
    else:
        reachable = ping_host(source)
        print(f"Host pingable: {reachable}")

    # ------------------------------------------------------------------
    # 1. Open the stream and grab a single frame
    # ------------------------------------------------------------------
    cap = cv2.VideoCapture(source, cv2.CAP_ANY)
    if not cap.isOpened():
        print("ERROR: cv2.VideoCapture FAILED to open the source.")
        print("       Check the IP, port, RTSP path, credentials and network.")
        print("       On Windows FFmpeg/OpenCV needs the stream reachable.")
        sys.exit(1)

    # Try to read up to 5 frames (first frames on an RTSP stream are often
    # corrupt/empty until the decoder warms up).
    frame = None
    for i in range(5):
        ret, frame = cap.read()
        if ret and frame is not None and frame.size > 0:
            print(f"Frame {i} read OK")
            break
        print(f"Frame {i} read failed/empty, retrying...")
    cap.release()

    if frame is None or frame.size == 0:
        print("ERROR: stream opened but no frame could be read.")
        sys.exit(1)

    fh, fw = frame.shape[:2]
    print(f"Camera frame shape: {frame.shape}  (W={fw}, H={fh})")

    # ------------------------------------------------------------------
    # 2. Check the hardcoded ROI against the frame
    # ------------------------------------------------------------------
    x, y, w, h = ROI
    fits = (x + w <= fw) and (y + h <= fh)
    print(f"ROI {ROI} fits frame: {fits}")
    if not fits:
        print(f"  !! ROI exceeds frame by "
              f"dx={max(0, x + w - fw)} dy={max(0, y + h - fh)}")

    # ------------------------------------------------------------------
    # 3. Save the full frame and the ROI crop
    # ------------------------------------------------------------------
    cv2.imwrite(OUT_FULL, frame)
    roi_frame = frame[y:y + h, x:x + w]
    cv2.imwrite(OUT_ROI, roi_frame)
    print(f"Saved {OUT_FULL} ({fw}x{fh}) and {OUT_ROI} ({roi_frame.shape[1]}x"
          f"{roi_frame.shape[0]})")

    # ------------------------------------------------------------------
    # 4. Inspect the model
    # ------------------------------------------------------------------
    model = YOLO(MODEL_PATH)
    print(f"Model task: {model.task}")
    print(f"Model names: {model.names}")

    # ------------------------------------------------------------------
    # 5. Run inference at multiple confidences
    # ------------------------------------------------------------------
    roi_resized = cv2.resize(roi_frame, (320, 320))
    for conf in (0.9, 0.5, 0.25):
        results = model.predict(roi_resized, imgsz=320, conf=conf, verbose=False)
        r = results[0]
        n_boxes = 0 if r.boxes is None else len(r.boxes)
        n_masks = 0 if r.masks is None else len(r.masks)
        confs = []
        if r.boxes is not None and len(r.boxes) > 0:
            confs = [f"{c:.2f}" for c in r.boxes.conf.cpu().tolist()]
        print(f"conf={conf}: boxes={n_boxes} masks={n_masks} "
              f"confidences={confs}")

        # Save annotated result for the lowest conf that produced something
        if n_boxes > 0 or n_masks > 0:
            annotated = r.plot()
            out_name = f"result_conf{conf}.png"
            cv2.imwrite(out_name, annotated)
            print(f"  -> saved annotated result as {out_name}")

    print("\nDone.")


if __name__ == "__main__":
    main()