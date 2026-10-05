import cv2
import numpy as np
import time
import csv
from PyQt6.QtWidgets import QMainWindow, QInputDialog, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from gui import Ui_MainWindow, VideoWindow   # import both classes
from datetime import datetime, timedelta
from settings import SettingsDialog
import json, os
import platform
import subprocess
from ultralytics import YOLO

# FIX: Added a capture thread to keep grabbing latest frame without buffering
class VideoCaptureThread(QThread):
    frame_received = pyqtSignal(np.ndarray)

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.cap = None
        self.running = False

    def run(self):
        if isinstance(self.source, int):
            self.cap = cv2.VideoCapture(self.source)
        else:
            # For RTSP / IP streams allow any backend
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_ANY)

        # Try to reduce buffering
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self.running = True
        while self.running and self.cap.isOpened():
            for _ in range(3):  # Discard stale frames
                if not self.running:
                    break
                self.cap.grab()
            if not self.running:
                break
            ret, frame = self.cap.read()
            if ret:
                self.frame_received.emit(frame)

        if self.cap:
            self.cap.release()

    def stop(self):
        self.running = False


class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # --- Create the separate camera display window immediately ---
        # This ensures it's available before any auto-start triggers process_frame
        self.video_window = VideoWindow()
        # Do NOT show it until start_camera is called (keeps behavior controlled)
        # self.video_window.show()   # uncomment if you want it visible at app start

        # --- Rest of your original initialization ---
        self.model = YOLO("v8_fabric.pt")

        self.roi = (210, 300, 2650, 600)
        self.current_frame = None

        # Camera setup
        self.capture_thread = None  # will be VideoCaptureThread instance
        self.selected_camera_index = 0

        self.calibrated = False
        self.pixels_per_cm = None
        self.last_detected_lines = None

        self.last_log_time = datetime.now() - timedelta(seconds=10)
        self.recent_widths = []

        self.settings = self.load_settings()

        if self.settings.get("pixels_per_cm") is not None and self.settings.get("nominal_width_cm") is not None:
            self.pixels_per_cm = self.settings["pixels_per_cm"]
            self.nominal_width_cm = self.settings["nominal_width_cm"]
            self.calibrated = True

        # Connect UI buttons (same as before)
        self.ui.btn_start.clicked.connect(self.start_camera)
        self.ui.btn_stop.clicked.connect(self.stop_camera)
        self.ui.btn_settings.clicked.connect(self.open_settings_dialog)
        self.ui.btn_update_lot.clicked.connect(self.on_update_lot_clicked)

        # If auto_start in settings, start camera (video_window exists already)
        if self.settings.get("auto_start", False):
            self.start_camera()

    def start_camera(self):
        # Get Lot Number from entry field
        lot_number = self.ui.entry_lot_no.text().strip()
        if not lot_number:
            QMessageBox.warning(self, "Lot Number Required", "Please enter the Lot Number before starting the sensor.")
            return

        self.update_lot_number(lot_number)

        # Reload latest settings
        self.settings = self.load_settings()
        selected_data = self.settings.get("selected_camera")

        if selected_data is None:
            self.ui.label_camera_status.setText("Status: No sensor selected")
            return

        # Show the separate camera window when starting
        try:
            self.video_window.show()
        except Exception:
            pass

        # Webcam branch (numeric string indicates index)
        if str(selected_data).isdigit():
            cam_index = int(selected_data)
            self.capture_thread = VideoCaptureThread(cam_index)
            self.capture_thread.frame_received.connect(self.process_frame)
            self.capture_thread.start()
            self.ui.label_camera_status.setText("Status: Running (Webcam)")
            return

        # Else → RTSP/IP camera branch
        if "@" in selected_data:
            ip_part = selected_data.split("@")[1].split(":")[0]
        else:
            # may raise if malformed; keep same as original
            ip_part = selected_data.split("/")[2].split(":")[0]

        # Ping test before starting RTSP
        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", ip_part]

        if subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            self.ui.label_camera_status.setText("Status: Sensor unreachable")
            QMessageBox.critical(self, "Connection Error", f"Cannot reach sensor. Please check IP")
            return

        # Start threaded capture for RTSP
        self.capture_thread = VideoCaptureThread(selected_data)
        self.capture_thread.frame_received.connect(self.process_frame)
        self.capture_thread.start()

        self.ui.label_camera_status.setText("Status: Running (IP Camera)")

    def stop_camera(self):
        if self.capture_thread:
            self.capture_thread.stop()   # Tell thread to stop
            self.capture_thread.wait()   # Wait until thread finishes
            self.capture_thread = None

        selected_data = self.settings.get("selected_camera")

        if selected_data is None:
            self.ui.label_camera_status.setText("Status: No sensor selected")
            return

        # Hide video window when stopped
        try:
            self.video_window.hide()
        except Exception:
            pass

        self.ui.label_camera_status.setText("Status: Stopped")

    def update_lot_number(self, new_lot):
        self.lot_number = new_lot

        self.log_filename = f"log_{self.lot_number}.csv"
        self.error_filename = f"error_{self.lot_number}.csv"

        # Create files with header if not exist
        if not os.path.exists(self.log_filename):
            with open(self.log_filename, mode='w', newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Width (cm)", "Status", "Lot Number"])

        if not os.path.exists(self.error_filename):
            with open(self.error_filename, mode='w', newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Width (cm)", "Status", "Lot Number"])

    def on_update_lot_clicked(self):
        new_lot = self.ui.entry_lot_no.text().strip()
        if not new_lot:
            QMessageBox.warning(self, "Lot Number Required", "Please enter a valid Lot Number.")
            return

        self.update_lot_number(new_lot)
        QMessageBox.information(self, "Lot Updated", f"Lot number updated to: {new_lot}")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, calibrate_callback=self.calibrate_using_edges)
        dialog.exec()

    def load_settings(self):
        default_settings = {
            "camera_ip": "0",
            "auto_start": False,
            "selected_camera": None,
            "pixels_per_cm": None,
            "nominal_width_cm": None
        }

        if not os.path.exists("settings.json"):
            with open("settings.json", "w") as f:
                json.dump(default_settings, f, indent=4)
            return default_settings

        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            settings = default_settings  # reset if corrupted

        for key, value in default_settings.items():
            settings.setdefault(key, value)

        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)

        return settings

    def process_frame(self, frame):
        """YOLO segmentation with stable width display and 10-second logging with 5-value average"""
        if hasattr(self, "processing") and self.processing:
            return
        self.processing = True

        # Ensure last_log_time is datetime, not float
        if hasattr(self, "last_log_time") and isinstance(self.last_log_time, float):
            self.last_log_time = datetime.now()

        if not hasattr(self, "frame_count"):
            self.frame_count = 0
        self.frame_count += 1

        display_frame = frame.copy()
        self.current_frame = frame.copy()

        # --- ROI settings (x, y, w, h) ---
        self.roi = (80, 50, 600, 120)
        x, y, w, h = self.roi
        roi_frame = frame[y:y + h, x:x + w]

        results = None
        if self.frame_count % 60 == 0:  # run YOLO every 60th frame (~2 sec)
            roi_resized = cv2.resize(roi_frame, (320, 320))
            results = self.model.predict(roi_resized, imgsz=320, conf=0.5, verbose=False)

        # Draw ROI rectangle
        cv2.rectangle(display_frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

        def intersect_polygon_with_line(polygon, y_line):
            intersections = []
            n = len(polygon)
            for i in range(n):
                x1, y1 = polygon[i]
                x2, y2 = polygon[(i + 1) % n]
                if (y1 <= y_line <= y2) or (y2 <= y_line <= y1):
                    if y1 == y2:
                        continue
                    x_int = x1 + (y_line - y1) * (x2 - x1) / (y2 - y1)
                    intersections.append(int(x_int))
            return intersections

        new_detection = False
        detected_width_cm = None

        if results and results[0].masks is not None:
            for polygon in results[0].masks.xy:
                polygon_np = np.array(polygon, dtype=np.float32)
                scale_x = w / 320
                scale_y = h / 320
                polygon_np[:, 0] *= scale_x
                polygon_np[:, 1] *= scale_y
                polygon_np[:, 0] += x
                polygon_np[:, 1] += y
                polygon_np[:, 0] = np.clip(polygon_np[:, 0], x, x + w)
                polygon_np[:, 1] = np.clip(polygon_np[:, 1], y, y + h)

                overlay = display_frame.copy()
                cv2.fillPoly(overlay, [polygon_np.astype(np.int32)], (0, 255, 0))
                display_frame = cv2.addWeighted(overlay, 0.4, display_frame, 0.6, 0)

                min_y = int(np.min(polygon_np[:, 1]))
                max_y = int(np.max(polygon_np[:, 1]))
                center_y = max(y, min((min_y + max_y) // 2, y + h))
                intersections = intersect_polygon_with_line(polygon_np, center_y)

                if len(intersections) >= 2:
                    min_x = max(min(intersections), x)
                    max_x = min(max(intersections), x + w)

                    if self.calibrated and self.pixels_per_cm:
                        width_px = max_x - min_x
                        detected_width_cm = width_px / self.pixels_per_cm
                        self.last_width_cm = detected_width_cm
                        self.last_line = (min_x, max_x, center_y)
                        self.last_detection_frame = self.frame_count
                        new_detection = True

        # Draw last known width line and text
        if hasattr(self, "last_width_cm") and self.last_width_cm is not None and hasattr(self, "last_line"):
            min_x, max_x, center_y = self.last_line
            cv2.line(display_frame, (min_x, center_y), (max_x, center_y), (0, 0, 255), 2)

            mid_x = (min_x + max_x) // 2
            text = f"Width: {self.last_width_cm:.2f} cm"

            # Get text size (width and height)
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 3)

            # Adjust position so text is centered
            text_x = mid_x - text_width // 2
            text_y = center_y - 10

            cv2.putText(display_frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

            self.ui.lcd_width.setText(f"{self.last_width_cm:.2f}")


        # Initialize width buffer if not exists
        if not hasattr(self, "width_buffer"):
            self.width_buffer = []

        # Add detected width to buffer
        if detected_width_cm:
            self.width_buffer.append(detected_width_cm)
            if len(self.width_buffer) > 5:
                self.width_buffer = self.width_buffer[-5:]

        # Log every 10 seconds using average of collected values
        if (datetime.now() - self.last_log_time).total_seconds() >= 10:
            if len(self.width_buffer) >= 5:
                avg_width = sum(self.width_buffer) / len(self.width_buffer)

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                lower_limit = self.nominal_width_cm - 5
                upper_limit = self.nominal_width_cm + 5

                with open(self.log_filename, "a", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, f"{avg_width:.2f}", "OK", self.lot_number])

                if avg_width < lower_limit or avg_width > upper_limit:
                    with open(self.error_filename, "a", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([timestamp, f"{avg_width:.2f}", "ERROR", self.lot_number])

                self.width_buffer = []

            self.last_log_time = datetime.now()

        # Display final frame in the separate VideoWindow
        try:
            rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.video_window.label_video.setPixmap(QPixmap.fromImage(qt_img))
        except Exception:
            # If anything goes wrong with GUI update, ignore to keep logic running
            pass

        self.processing = False

    def calibrate_using_edges(self):
        """Calibrate pixels_per_cm by detecting edges and asking user for real width"""
        if self.current_frame is None:
            QMessageBox.warning(self, "Calibration Error", "No frame available. Start camera first.")
            return

        # --- Run YOLO on ROI ---
        x, y, w, h = self.roi
        roi_frame = self.current_frame[y:y + h, x:x + w]  # last shown frame
        results = self.model.predict(roi_frame, verbose=False)

        if not results or results[0].masks is None:
            self.ui.label_camera_status.setText("Status: No object detected.")
            return

        # Get first mask polygon (take widest bounding X range)
        poly = results[0].masks.xy[0]
        xs = poly[:, 0]
        x1, x2 = int(xs.min()), int(xs.max())

        # --- Ask user for real width (cm) ---
        known_width_cm, ok = QInputDialog.getDouble(
            self, "Calibration", "Enter real width (cm):", min=0.1
        )
        if not ok:
            return

        # --- Compute calibration scale ---
        width_px = abs(x2 - x1)
        if width_px <= 0:
            QMessageBox.warning(self, "Calibration Error", "Invalid width detected.")
            return

        self.pixels_per_cm = width_px / known_width_cm
        self.nominal_width_cm = known_width_cm
        self.calibrated = True
        self.last_log_time = time.time()

        # --- Save calibration to settings.json ---
        self.settings["pixels_per_cm"] = self.pixels_per_cm
        self.settings["nominal_width_cm"] = self.nominal_width_cm
        with open("settings.json", "w") as f:
            json.dump(self.settings, f)

        QMessageBox.information(
            self,
            "Calibration Successful",
            f"Calibration complete!\n1 cm = {self.pixels_per_cm:.3f} pixels"
        )
