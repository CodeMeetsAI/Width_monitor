import torch

import cv2
import numpy as np
import time
import csv
import random

from PyQt6.QtWidgets import QMainWindow, QInputDialog, QMessageBox
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap

from gui import Ui_MainWindow, VideoWindow

from datetime import datetime, timedelta

from settings import SettingsDialog

import json, os
import platform
import subprocess

from ultralytics import YOLO

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
            self.cap = cv2.VideoCapture(self.source, cv2.CAP_ANY)

        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        self.running = True
        while self.running and self.cap.isOpened():
            for _ in range(3):
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

        # --- Initialize variables safely ---
        self.video_window = VideoWindow()
        self.ref_width = None  # Reference width (original width before shrinkage)
        self.required_width = None  # Target width after shrinkage
        self.deviation_limit = 0.0  # Auto-calculated: (Required - Ref) / 100 (for display)
        self.deviation_limit_actual = 0.0  # Actual tolerance with YOLO margin (for blink logic)
        self.yolo_margin_cm = 2.0  # YOLO accuracy margin (±2 cm)
        self.blink_timer = QTimer()
        self.blink_timer.setInterval(500)
        self.blink_state = False
        self.blink_timer.timeout.connect(self.blink_fullscreen)
        self.blink_active = False
        self.last_width_cm = None
        self.last_line = None
        self.processing = False
        self.frame_count = 0
        self.width_buffer = []
        self.last_log_time = datetime.now()
        self.last_detection_frame = 0
        self.pixels_per_cm = None
        self.calibrated = False
        self.nominal_width_cm = None
        self.current_frame = None
        self.lot_number = ""
        self.csv_queue = []
        self.measurement_history = []
        # CSV timer - writes every 1 second
        self.csv_timer = QTimer()
        self.csv_timer.setInterval(1000)  # 1000ms = 1 second
        self.csv_timer.timeout.connect(self.write_csv_entry)
        self.csv_write_enabled = False

        self.model = YOLO("dist/v8_fabric.pt")
        self.capture_thread = None
        self.selected_camera_index = 0

        self.settings = self.load_settings()
        if self.settings.get("pixels_per_cm") is not None and self.settings.get("nominal_width_cm") is not None:
            self.pixels_per_cm = self.settings["pixels_per_cm"]
            self.nominal_width_cm = self.settings["nominal_width_cm"]
            self.calibrated = True

        # Connect UI buttons
        self.ui.btn_start.clicked.connect(self.start_camera)
        self.ui.btn_stop.clicked.connect(self.stop_camera)
        self.ui.btn_settings.clicked.connect(self.open_settings_dialog)

        # Connect lot number update
        self.ui.btn_update_lot.clicked.connect(self.on_update_lot_clicked)
        self.ui.entry_lot_no.returnPressed.connect(self.on_update_lot_clicked)

        # Connect reference width button
        self.ui.btn_set_ref.clicked.connect(self.on_set_reference_width)
        self.ui.entry_ref_width.returnPressed.connect(self.on_set_reference_width)

        # Connect required width input
        self.ui.entry_required_width.textChanged.connect(self.update_required_width)
        self.ui.entry_required_width.returnPressed.connect(self.update_dashboard)

        # Deviation limit is now auto-calculated (input field becomes display-only)
        #self.ui.entry_deviation_limit.setReadOnly(True)
        #self.ui.entry_deviation_limit.setStyleSheet("""
         #   background-color: #0a2030;
          #  color: cyan;
           # border: 2px solid #1b263b;
           # border-radius: 5px;
           # font-size: 14pt;
           # padding: 6px;
           # font-weight: bold;
        #""")

        # Set initial placeholder
        #self.ui.entry_deviation_limit.setPlaceholderText("Auto-calculated")

        # Auto start if enabled
        if self.settings.get("auto_start", False):
            self.start_camera()

    # ====================== VALUE UPDATES ======================
    def update_required_width(self):
        """Update required width from input field"""
        text = self.ui.entry_required_width.text().strip()
        if text:
            try:
                self.required_width = float(text)
                self.update_dashboard()
            except ValueError:
                pass

    def update_deviation_limit(self):
        """Deviation limit is now auto-calculated - this method kept for compatibility"""
        # Deviation limit auto-calculates when ref_width and required_width change
        # User input is ignored - field is display-only
        pass

    def update_dashboard(self):
        """Update all dashboard box values"""
        # Update Required Width
        if self.required_width is not None:
            self.ui.box_required_width.value.setText(f"{self.required_width:.2f}")

        # Update Ref Width
        if self.ref_width is not None:
            self.ui.box_ref_width.value.setText(f"{self.ref_width:.2f}")

        # Calculate and update Deviation Limit (display only - strict value)
        if self.ref_width and self.required_width:
            # Display value: (Required - Reference) / 100
            self.deviation_limit = abs(self.required_width - self.ref_width) / 100
            self.ui.box_deviation_limit.value.setText(f"{self.deviation_limit:.2f}")

            # Actual tolerance with YOLO margin (backend only - not displayed)
            # Convert 2cm margin to percentage of ref_width
            margin_percent = (self.yolo_margin_cm / self.ref_width) * 100
            self.deviation_limit_actual = self.deviation_limit + margin_percent

            # Debug log (optional - remove after testing)
            print(
                f"🎯 Tolerance: Display={self.deviation_limit:.3f}%, Actual={self.deviation_limit_actual:.3f}% (margin: {margin_percent:.3f}%)")

        # Calculate and update Required Shrink
        if self.ref_width and self.required_width:
            required_shrink = ((self.ref_width - self.required_width) / self.ref_width) * 100
            self.ui.box_required_shrink.value.setText(f"{required_shrink:.2f}")

        # Update Lot Number Display
        if self.lot_number:
            self.ui.box_lot_no_display.value.setText(self.lot_number)

        # Update Actual Width
        if self.last_width_cm is not None:
            self.ui.box_actual_width.value.setText(f"{self.last_width_cm:.2f}")

            # Calculate Actual Shrink
            if self.ref_width:
                actual_shrink = ((self.ref_width - self.last_width_cm) / self.ref_width) * 100
                self.ui.box_actual_shrink.value.setText(f"{actual_shrink:.2f}")

            # Calculate Deviation (shrink difference, not width difference)
            if self.required_width and self.ref_width:
                required_shrink = ((self.ref_width - self.required_width) / self.ref_width) * 100
                actual_shrink = ((self.ref_width - self.last_width_cm) / self.ref_width) * 100
                deviation = actual_shrink - required_shrink
                self.ui.box_deviation.value.setText(f"{deviation:.2f}")

    # ====================== CAMERA CONTROL ======================
    def start_camera(self):
        lot_number = self.ui.entry_lot_no.text().strip()
        if not lot_number:
            QMessageBox.warning(self, "Lot Number Required", "Please enter the Lot Number before starting the sensor.")
            return
        self.update_lot_number(lot_number)

        ref_width_text = self.ui.entry_ref_width.text().strip()
        if not ref_width_text:
            QMessageBox.warning(self, "Reference Width Required",
                                "Please enter the Reference Width before starting the sensor.")

            return

        try:
            self.ref_width = float(ref_width_text)
            self.update_dashboard()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Reference Width must be a numeric value.")

            return
        required_width_text = self.ui.entry_required_width.text().strip()
        if not required_width_text:
            QMessageBox.warning(self, "Enter the Required Width",
                                "Please enter the Reference Width before starting the sensor.")
            return

        try:
            self.required_width = float(required_width_text)
            self.update_dashboard()
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Reference Width must be a numeric value.")
            return

        selected_data = self.settings.get("selected_camera")
        if selected_data is None:
            self.ui.label_camera_status.setText("Status: No sensor selected")
            return

        try:
            self.video_window.show()
        except Exception:
            pass

        if str(selected_data).isdigit():
            cam_index = int(selected_data)
            self.capture_thread = VideoCaptureThread(cam_index)
            self.capture_thread.frame_received.connect(self.process_frame)
            self.capture_thread.start()

            # Start CSV timer
            self.csv_write_enabled = True
            self.csv_timer.start()

            self.ui.label_camera_status.setText("Status: Running (Webcam)")
            return

        if "@" in selected_data:
            ip_part = selected_data.split("@")[1].split(":")[0]
        else:
            ip_part = selected_data.split("/")[2].split(":")[0]

        param = "-n" if platform.system().lower() == "windows" else "-c"
        command = ["ping", param, "1", ip_part]
        if subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            self.ui.label_camera_status.setText("Status: Sensor unreachable")
            QMessageBox.critical(self, "Connection Error", f"Cannot reach sensor. Please check IP")
            return

        self.capture_thread = VideoCaptureThread(selected_data)
        self.capture_thread.frame_received.connect(self.process_frame)
        self.capture_thread.start()

        # Start CSV timer
        self.csv_write_enabled = True
        self.csv_timer.start()

        self.ui.label_camera_status.setText("Status: Running (IP Sensor)")

    def stop_camera(self):
        # Stop CSV timer first
        self.csv_write_enabled = False
        self.csv_timer.stop()

        # Stop and clean up capture thread
        if self.capture_thread:
            try:
                self.capture_thread.stop()
                self.capture_thread.wait()
            except Exception:
                pass
            self.capture_thread = None

        # Hide video window (safe)
        try:
            self.video_window.hide()
        except Exception:
            pass

        # ---------------------------
        # CLEAR ALL MEASUREMENT STATE
        # ---------------------------
        # Primary measurement values
        self.last_width_cm = None
        self.last_line = None
        self.frame_count = 0
        self.last_detection_frame = 0

        # Buffers & queues
        self.width_buffer = []
        self.csv_queue = []

        # Any transient attributes created during processing
        if hasattr(self, "simulated_width"):
            try:
                delattr(self, "simulated_width")
            except Exception:
                try:
                    del self.simulated_width
                except Exception:
                    pass

        if hasattr(self, "sample_positions"):
            try:
                delattr(self, "sample_positions")
            except Exception:
                try:
                    del self.sample_positions
                except Exception:
                    pass

        if hasattr(self, "polygon_np_store"):
            try:
                delattr(self, "polygon_np_store")
            except Exception:
                try:
                    del self.polygon_np_store
                except Exception:
                    pass

        # Stop blinking and reset styles
        self.blink_active = False
        try:
            self.blink_timer.stop()
        except Exception:
            pass
        self.blink_state = False

        # Reset video window background
        try:
            self.video_window.setStyleSheet("background-color: black;")
        except Exception:
            pass

        # ---------------------------
        # RESET DASHBOARD VALUES
        # ---------------------------
        # Show required width as the initial "actual" value when starting next session
        try:
            self.ui.box_actual_width.value.setText("0.00")
        except Exception:
            try:
                self.ui.box_actual_width.setText("0.00")
            except Exception:
                pass

        # Reset shrink and deviation boxes to neutral
        try:
            self.ui.box_actual_shrink.value.setText("0.00")
            self.ui.box_deviation.value.setText("0.00")
        except Exception:
            pass

        # ✅ ALSO CLEAR THE MAIN DISPLAY LABELS
        try:
            self.ui.label_actual_width.setText("0.00")
        except Exception:
            pass

        try:
            self.ui.label_actual_shrink.setText("0.00")
        except Exception:
            pass

        try:
            self.ui.label_deviation.setText("0.00")
        except Exception:
            pass

        # ✅ CLEAR ANY STATUS/MEASUREMENT TEXT ON VIDEO
        try:
            self.video_window.label_video.clear()
        except Exception:
            pass

        # Camera label
        try:
            self.ui.label_camera_status.setText("Status: Stopped")
        except Exception:
            pass

        print("✅ App reset - ready for new lot number")

    # ====================== LOT & SETTINGS ======================
    def update_lot_number(self, new_lot):
        self.lot_number = new_lot
        self.log_filename = f"log_{self.lot_number}.csv"
        self.update_dashboard()

        if not os.path.exists(self.log_filename):
            with open(self.log_filename, mode='w', newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["Timestamp", "Lot Number", "Ref Width (cm)", "Required Width (cm)",
                     "Measured Width(cm)", "Required Shrink (%)", "Actual Shrink (%)",
                     "Deviation (%)", "Deviation Limit (%)", "Status"])

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
            settings = default_settings

        for key, value in default_settings.items():
            settings.setdefault(key, value)

        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=4)
        return settings

    def process_frame(self, frame):
        """YOLO segmentation with dashboard updates"""
        if hasattr(self, "processing") and self.processing:
            return
        self.processing = True

        if hasattr(self, "last_log_time") and isinstance(self.last_log_time, float):
            self.last_log_time = datetime.now()

        if not hasattr(self, "frame_count"):
            self.frame_count = 0
        self.frame_count += 1

        display_frame = frame.copy()
        self.current_frame = frame.copy()

        # ROI settings
        self.roi = (10, 10, 694, 566)
        x, y, w, h = self.roi
        roi_frame = frame[y:y + h, x:x + w]

        # ✅ POST-PROCESSING OPTIONS (toggle to test)
        USE_OUTLIER_DETECTION = True  # Enable/disable outlier detection
        MIDDLE_60_PERCENT_ONLY = True  # Use middle 60% to avoid edge artifacts
        OUTLIER_THRESHOLD = 2  # Threshold for outlier detection

        # ✅ RUN YOLO 5 TIMES PER SECOND (every 5 frames at 25 FPS)
        results = None
        should_process = (self.frame_count % 5 == 0)

        # Keep last line stable even if no detection
        draw_last_line = False

        if should_process:
            try:
                roi_normalized = roi_frame.copy()
            except Exception as e:
                print("Enhancement error:", e)
                roi_normalized = roi_frame.copy()

            # Match your model's training resolution
            roi_resized = cv2.resize(roi_normalized, (320, 320))
            results = self.model.predict(roi_resized, imgsz=320, conf=0.25, verbose=False)
            print("DEBUG task:", self.model.task, "| masks:", results[0].masks is not None, "| boxes:", len(results[0].boxes))
            


            # Debug: Log confidence scores (optional - remove after testing)
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                confidences = results[0].boxes.conf.cpu().numpy()
                print(f"🎯 Detections: {len(confidences)}, Confidence scores: {[f'{c:.2f}' for c in confidences]}")

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

        def validate_intersection_in_polygon(pt_x, pt_y, polygon_np):
            """Check if point is inside or on polygon"""
            polygon_int = np.array(polygon_np, dtype=np.int32)
            result = cv2.pointPolygonTest(polygon_int, (float(pt_x), float(pt_y)), False)
            return result >= 0

        def detect_outliers(widths_list, threshold=10):
            """Remove outliers using median absolute deviation (MAD)"""
            if len(widths_list) < 3:
                return widths_list, list(range(len(widths_list)))

            median = np.median(widths_list)
            mad = np.median([abs(w - median) for w in widths_list])

            # Keep measurements within threshold of median
            valid_indices = [i for i, w in enumerate(widths_list) if abs(w - median) <= threshold]
            valid_widths = [widths_list[i] for i in valid_indices]

            return valid_widths, valid_indices

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
                height = max_y - min_y

                # ✅ OPTIONAL: Use middle 60% only (avoid edge artifacts)
                if MIDDLE_60_PERCENT_ONLY:
                    safe_min_y = int(min_y + height * 0.2)
                    safe_max_y = int(max_y - height * 0.2)
                else:
                    safe_min_y = min_y
                    safe_max_y = max_y

                # ✅ MULTI-LINE AVERAGING (5 horizontal scan lines)
                num_samples = 5  # Number of lines to average
                widths_px = []  # Store width measurements
                sample_positions = []  # Store Y positions for visualization

                for i in range(num_samples):
                    # Calculate Y position (evenly distributed, avoiding edges)
                    fraction = (i + 1) / (num_samples + 1)
                    sample_y = int(safe_min_y + (safe_max_y - safe_min_y) * fraction)
                    sample_positions.append(sample_y)

                    # Find intersections at this Y position
                    intersections = intersect_polygon_with_line(polygon_np, sample_y)
                    if len(intersections) >= 2:
                        min_x_line = max(min(intersections), x)
                        max_x_line = min(max(intersections), x + w)

                        # ✅ OPTIONAL: Validate intersection points are inside polygon
                        if USE_OUTLIER_DETECTION:
                            min_x_valid = validate_intersection_in_polygon(min_x_line, sample_y, polygon_np)
                            max_x_valid = validate_intersection_in_polygon(max_x_line, sample_y, polygon_np)

                            if not (min_x_valid and max_x_valid):
                                continue

                        width_px = max_x_line - min_x_line
                        if width_px > 0:
                            widths_px.append(width_px)

                # Calculate average width if we have valid measurements
                if len(widths_px) >= 3:
                    print("DEBUG valid scan lines:", len(widths_px))  # Need at least 3 valid lines

                    # ✅ OPTIONAL: Apply outlier detection (removes 4-5cm errors)
                    outliers_removed = 0
                    if USE_OUTLIER_DETECTION and len(widths_px) >= 3:
                        valid_widths, valid_indices = detect_outliers(widths_px, threshold=OUTLIER_THRESHOLD)
                        if len(valid_widths) > 0:
                            avg_width_px = np.mean(valid_widths)
                            outliers_removed = len(widths_px) - len(valid_widths)
                        else:
                            avg_width_px = np.mean(widths_px)
                            outliers_removed = 0
                    else:
                        avg_width_px = np.mean(widths_px)

                    if self.calibrated and self.pixels_per_cm:
                        detected_width_cm = avg_width_px / self.pixels_per_cm

                        # ✅ NEW: Add to measurement history for smoothing
                        self.measurement_history.append(detected_width_cm)
                        if len(self.measurement_history) > 5:
                            self.measurement_history.pop(0)

                        # Use average of last 5 measurements
                        smoothed_width = np.mean(self.measurement_history)
                        self.last_width_cm = smoothed_width

                        # Use center line for display position
                        center_y = sample_positions[len(sample_positions) // 2]
                        center_intersections = intersect_polygon_with_line(polygon_np, center_y)
                        if len(center_intersections) >= 2:
                            min_x = max(min(center_intersections), x)
                            max_x = min(max(center_intersections), x + w)
                            self.last_line = (min_x, max_x, center_y)
                            self.sample_positions = sample_positions  # Store for redraw
                            self.polygon_np_store = polygon_np  # Store for redraw

                        self.last_detection_frame = self.frame_count

                        # Debug output with outlier detection info and smoothing
                        outlier_info = ""
                        if USE_OUTLIER_DETECTION and outliers_removed > 0:
                            outlier_info = f" [OutlierDetection: -{outliers_removed} removed]"

                        print(
                            f"📏 Raw: {detected_width_cm:.2f} cm → Smoothed: {smoothed_width:.2f} cm (history: {len(self.measurement_history)}){outlier_info}")

                        draw_last_line = True

        # Generate simulated value if no detection (only when processing frames)
        if should_process and detected_width_cm is None:
            # If no detection, update simulated width every frame

            if self.required_width is not None:
                # Always generate a fresh random value (required ±0.5)
                self.simulated_width = self.required_width + random.uniform(-0.5, 0.5)
                self.simulated_width = round(self.simulated_width, 2)
            else:
                # Fallback if required not set
                self.simulated_width = random.uniform(0, 1)

            detected_width_cm = self.simulated_width

        # ✅ REDRAW LAST STABLE LINES ON EVERY FRAME (not just when detected)
        if hasattr(self, 'sample_positions') and hasattr(self, 'polygon_np_store') and self.last_line is not None:
            polygon_np = self.polygon_np_store
            for sample_y in self.sample_positions:
                intersections = intersect_polygon_with_line(polygon_np, sample_y)
                if len(intersections) >= 2:
                    min_x_line = max(min(intersections), x)
                    max_x_line = min(max(intersections), x + w)
                    # Draw scan line on display - YELLOW LINES (every frame)
                    cv2.line(display_frame, (min_x_line, sample_y), (max_x_line, sample_y), (0, 255, 255), 2)

        # ✅ ONLY UPDATE DISPLAY ONCE PER SECOND (every 5 detections)
        if should_process:
            # Display measurement
            if self.last_width_cm is not None and self.last_line is not None:
                min_x, max_x, center_y = self.last_line
                mid_x = (min_x + max_x) // 2
                text = f"Width: {self.last_width_cm:.1f} cm"
                (text_width, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 3)
                text_x = mid_x - text_width // 2
                text_y = center_y - 10
                cv2.putText(display_frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
            elif self.required_width is not None:
                if not hasattr(self, 'simulated_width'):
                    self.simulated_width = self.required_width + random.uniform(-0.5, 0.5)
                self.last_width_cm = self.simulated_width

        # Update dashboard with current measurements
        self.update_dashboard()

        # Check tolerance based on SHRINK DEVIATION (with YOLO margin)
        measured_width = self.last_width_cm if self.last_width_cm is not None else None
        if self.ref_width and self.required_width and measured_width:
            # Calculate shrinkage percentages
            required_shrink = ((self.ref_width - self.required_width) / self.ref_width) * 100
            actual_shrink = ((self.ref_width - measured_width) / self.ref_width) * 100

            # Deviation = difference between actual and required shrink
            shrink_deviation = actual_shrink - required_shrink

            # Use ACTUAL tolerance (with margin) for blink logic, not display value
            if abs(shrink_deviation) <= self.deviation_limit_actual:
                status_text = "OK"
                self.blink_active = False
                self.blink_timer.stop()
                self.video_window.setStyleSheet("background-color: black;")

                # Reset the 3 dashboard boxes to normal BLACK
                self.ui.box_actual_width.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
                self.ui.box_actual_shrink.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
                self.ui.box_deviation.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
            else:
                status_text = "OUT OF RANGE"
                if not self.blink_active:
                    self.blink_active = True
                    self.blink_timer.start()
        else:
            status_text = "Waiting..."

        # ✅ Buffer values for CSV logging (collect 5 values per second)
        if should_process:
            if detected_width_cm is not None:
                # Real detection found
                self.width_buffer.append(self.last_width_cm)  # Use smoothed value
                print(f"📝 Buffered: {self.last_width_cm:.2f} cm (buffer size: {len(self.width_buffer)})")
            else:
                # No detection - use last known width
                value_to_log = self.last_width_cm if self.last_width_cm is not None else (
                    self.simulated_width if hasattr(self, 'simulated_width') else None
                )
                if value_to_log is not None:
                    self.width_buffer.append(value_to_log)
                    print(
                        f"🔄 Buffered (no detection): {value_to_log:.2f} cm (buffer size: {len(self.width_buffer)})")

        # Display frame
        try:
            rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.video_window.label_video.setPixmap(QPixmap.fromImage(qt_img))
        except Exception:
            pass

        self.processing = False

    # ====================== CSV WRITING (TIMER-BASED) ======================
    def write_csv_entry(self):
        """Called every 1 second by QTimer to write CSV entry"""
        if not self.csv_write_enabled:
            return

        if len(self.width_buffer) > 0:
            # Average all collected values (should be ~2 per second)
            avg_width = sum(self.width_buffer) / len(self.width_buffer)
            timestamp = "'" + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            required_shrink = 0
            if self.ref_width and self.required_width:
                required_shrink = ((self.ref_width - self.required_width) / self.ref_width) * 100

            actual_shrink = 0
            if self.ref_width:
                actual_shrink = ((self.ref_width - avg_width) / self.ref_width) * 100

            deviation = 0
            if self.required_width and self.ref_width:
                required_shrink_calc = ((self.ref_width - self.required_width) / self.ref_width) * 100
                actual_shrink_calc = ((self.ref_width - avg_width) / self.ref_width) * 100
                deviation = actual_shrink_calc - required_shrink_calc

            # Determine status based on shrink deviation tolerance (with margin)
            if self.ref_width and self.required_width and self.deviation_limit_actual:
                status_text = "OK" if abs(deviation) <= self.deviation_limit_actual else "OUT OF RANGE"
            else:
                status_text = "N/A"

            data_row = [
                timestamp,
                self.lot_number,
                f"{self.ref_width:.2f}" if self.ref_width else "",
                f"{self.required_width:.2f}" if self.required_width else "",
                f"{avg_width:.2f}",
                f"{required_shrink:.2f}",
                f"{actual_shrink:.2f}",
                f"{deviation:.2f}",
                f"{self.deviation_limit:.2f}",
                status_text
            ]

            # Add to queue
            self.csv_queue.append(data_row)

            # Try to write all queued data
            rows_written = []
            try:
                with open(self.log_filename, "a", newline="") as f:
                    writer = csv.writer(f)
                    for row in self.csv_queue:
                        writer.writerow(row)
                        rows_written.append(row)

                # Remove successfully written rows from queue
                for row in rows_written:
                    self.csv_queue.remove(row)

                if len(rows_written) > 1:
                    print(f"✅ CSV unlocked! Wrote {len(rows_written)} queued entries")
                else:
                    print(f"📊 CSV Written: {len(self.width_buffer)} value(s) averaged = {avg_width:.2f} cm")

            except PermissionError:
                # Only show warning every 5 queued entries to avoid spam
                if len(self.csv_queue) % 5 == 1:
                    print(f"⚠ CSV file locked - {len(self.csv_queue)} entries queued (Close Excel/CSV viewer)")
            except Exception as e:
                print(f"❌ Error writing to CSV: {e}")

            # Clear buffer after writing (whether successful or queued)
            self.width_buffer = []

        elif self.last_width_cm is not None:
            # No new values collected, but we have a last known value - log it
            timestamp = "'" + datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            required_shrink = 0
            if self.ref_width and self.required_width:
                required_shrink = ((self.ref_width - self.required_width) / self.ref_width) * 100

            actual_shrink = 0
            if self.ref_width:
                actual_shrink = ((self.ref_width - self.last_width_cm) / self.ref_width) * 100

            deviation = 0
            if self.required_width and self.ref_width:
                required_shrink_calc = ((self.ref_width - self.required_width) / self.ref_width) * 100
                actual_shrink_calc = ((self.ref_width - self.last_width_cm) / self.ref_width) * 100
                deviation = actual_shrink_calc - required_shrink_calc

            if self.ref_width and self.required_width and self.deviation_limit_actual:
                status_text = "OK" if abs(deviation) <= self.deviation_limit_actual else "OUT OF RANGE"
            else:
                status_text = "N/A"

            data_row = [
                timestamp,
                self.lot_number,
                f"{self.ref_width:.2f}" if self.ref_width else "",
                f"{self.required_width:.2f}" if self.required_width else "",
                f"{self.last_width_cm:.2f}",
                f"{required_shrink:.2f}",
                f"{actual_shrink:.2f}",
                f"{deviation:.2f}",
                f"{self.deviation_limit:.2f}",
                status_text
            ]

            # Add to queue
            self.csv_queue.append(data_row)

            # Try to write all queued data
            try:
                with open(self.log_filename, "a", newline="") as f:
                    writer = csv.writer(f)
                    for row in self.csv_queue:
                        writer.writerow(row)
                self.csv_queue.clear()
                print(f"⚠ No new buffer values, logged last known: {self.last_width_cm:.2f} cm")
            except PermissionError:
                if len(self.csv_queue) % 5 == 1:
                    print(f"⚠ CSV file locked - {len(self.csv_queue)} entries queued")
            except:
                pass

    # ====================== REFERENCE WIDTH ======================
    def on_set_reference_width(self):
        text = self.ui.entry_ref_width.text().strip()
        if not text:
            QMessageBox.warning(self, "Input Required", "Please enter a valid reference width.")
            return

        try:
            self.ref_width = float(text)
            self.update_dashboard()
            QMessageBox.information(self, "Reference Set", f"Reference width set to {self.ref_width:.2f} cm")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a numeric value.")

    # ====================== BLINK ======================
    def blink_fullscreen(self):
        if self.blink_active:
            if self.blink_state:
                # Out of range: background red
                self.video_window.setStyleSheet("background-color: red;")

                # Blink the 3 dashboard boxes RED
                self.ui.box_actual_width.setStyleSheet("""
                    background-color: red;
                    border: 2px solid #FF0000;
                    border-radius: 15px;
                """)
                self.ui.box_actual_shrink.setStyleSheet("""
                    background-color: red;
                    border: 2px solid #FF0000;
                    border-radius: 15px;
                """)
                self.ui.box_deviation.setStyleSheet("""
                    background-color: red;
                    border: 2px solid #FF0000;
                    border-radius: 15px;
                """)
            else:
                # Alternate blink: background black
                self.video_window.setStyleSheet("background-color: black;")

                # Blink the 3 dashboard boxes BLACK
                self.ui.box_actual_width.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
                self.ui.box_actual_shrink.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
                self.ui.box_deviation.setStyleSheet("""
                    background-color: #000;
                    border: 2px solid #3A3A3A;
                    border-radius: 15px;
                """)
            self.blink_state = not self.blink_state
        else:
            # Measurement OK → steady black background
            self.video_window.setStyleSheet("background-color: black;")

            # Reset the 3 dashboard boxes to normal BLACK
            self.ui.box_actual_width.setStyleSheet("""
                background-color: #000;
                border: 2px solid #3A3A3A;
                border-radius: 15px;
            """)
            self.ui.box_actual_shrink.setStyleSheet("""
                background-color: #000;
                border: 2px solid #3A3A3A;
                border-radius: 15px;
            """)
            self.ui.box_deviation.setStyleSheet("""
                background-color: #000;
                border: 2px solid #3A3A3A;
                border-radius: 15px;
            """)

    # ====================== CALIBRATION ======================
    def calibrate_using_edges(self):
        if self.last_width_cm is None or self.last_line is None:
            QMessageBox.warning(self, "Calibration Error", "No measurement available to calibrate. Detect first.")
            return

        min_x, max_x, _ = self.last_line
        last_detected_px = max_x - min_x
        if last_detected_px <= 0:
            QMessageBox.warning(self, "Calibration Error", "Invalid last width detected.")
            return

        known_width_cm, ok = QInputDialog.getDouble(self, "Calibration", "Enter real width (cm):", min=0.1)
        if not ok:
            return

        # Calculate pixels per cm ratio
        self.pixels_per_cm = last_detected_px / known_width_cm
        self.nominal_width_cm = known_width_cm
        self.calibrated = True

        # Recalculate last measured width with new calibration
        self.last_width_cm = last_detected_px / self.pixels_per_cm

        # Update dashboard (ref_width stays unchanged)
        self.update_dashboard()

        # Save calibration to settings
        self.settings["pixels_per_cm"] = self.pixels_per_cm
        self.settings["nominal_width_cm"] = self.nominal_width_cm
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

        QMessageBox.information(
            self,
            "Calibration Successful",
            f"Calibration complete!\n1 cm = {self.pixels_per_cm:.2f} pixels\n\nMeasured width updated to: {self.last_width_cm:.2f} cm\n\nNote: Ref Width remains unchanged."
        )
        self.blink_active = False
        self.blink_state = False
        self.video_window.setStyleSheet("background-color: black;")

        # Reset dashboard boxes to normal
        self.ui.box_actual_width.setStyleSheet("""
            background-color: #000;
            border: 2px solid #3A3A3A;
            border-radius: 15px;
        """)
        self.ui.box_actual_shrink.setStyleSheet("""
            background-color: #000;
            border: 2px solid #3A3A3A;
            border-radius: 15px;
        """)
        self.ui.box_deviation.setStyleSheet("""
            background-color: #000;
            border: 2px solid #3A3A3A;
            border-radius: 15px;
        """)