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
from PyQt6.QtCore import QTimer
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
        self.actual_width = None  # ✅ will store the reference width (cm) entered by user
        self.blink_timer = QTimer()
        self.blink_timer.setInterval(500)  # 500 ms interval
        self.blink_state = False
        self.blink_timer.timeout.connect(self.blink_lcd)
        self.blink_active = False

        # Do NOT show it until start_camera is called (keeps behavior controlled)
        # self.video_window.show()   # uncomment if you want it visible at app start

        # --- Rest of your original initialization ---
        self.model = YOLO("v9_fab.pt")

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
        self.ui.entry_lot_no.returnPressed.connect(self.on_update_lot_clicked)
        self.ui.btn_set_ref.clicked.connect(self.on_set_reference_width)
        self.ui.entry_actual_width.returnPressed.connect(self.on_set_reference_width)

        # If auto_start in settings, start camera (video_window exists already)
        if self.settings.get("auto_start", False):
            self.start_camera()

    def start_camera(self):
        # --- Check Lot Number ---
        lot_number = self.ui.entry_lot_no.text().strip()
        if not lot_number:
            QMessageBox.warning(self, "Lot Number Required", "Please enter the Lot Number before starting the sensor.")
            return
        self.update_lot_number(lot_number)

        # --- Check Reference Width ---
        ref_width_text = self.ui.entry_actual_width.text().strip()
        if not ref_width_text:
            QMessageBox.warning(self, "Reference Width Required",
                                "Please enter the Reference Width before starting the sensor.")
            return

        try:
            self.actual_width = float(ref_width_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Reference Width must be a numeric value.")
            return

        # --- Continue with original camera start logic ---
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

        # Webcam branch
        if str(selected_data).isdigit():
            cam_index = int(selected_data)
            self.capture_thread = VideoCaptureThread(cam_index)
            self.capture_thread.frame_received.connect(self.process_frame)
            self.capture_thread.start()
            self.ui.label_camera_status.setText("Status: Running (Webcam)")
            return

        # RTSP/IP camera branch
        if "@" in selected_data:
            ip_part = selected_data.split("@")[1].split(":")[0]
        else:
            ip_part = selected_data.split("/")[2].split(":")[0]

        # Ping test
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
        self.roi = (60, 10, 580, 50)
        x, y, w, h = self.roi
        roi_frame = frame[y:y + h, x:x + w]

        results = None
        if self.frame_count % 30 == 0:  # run YOLO every 60th frame (~2 sec)
            # ================================================
            # ✅ ENHANCEMENT BLOCK (added safely)
            # ================================================
            try:
                # Convert to LAB color space for light control
                roi_lab = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(roi_lab)
                # Stronger CLAHE (adaptive contrast)
                clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
                cl = clahe.apply(l)
                roi_enhanced = cv2.merge((cl, a, b))
                roi_enhanced = cv2.cvtColor(roi_enhanced, cv2.COLOR_LAB2BGR)
                # Denoise but preserve edges
                roi_enhanced = cv2.bilateralFilter(roi_enhanced, d=9, sigmaColor=75, sigmaSpace=75)
                # Sharpen slightly to recover fine edges
                sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
                roi_enhanced = cv2.filter2D(roi_enhanced, -1, sharpen_kernel)
                # Optional mild Gaussian blur to remove artifacts
                roi_enhanced = cv2.GaussianBlur(roi_enhanced, (3, 3), 0)
            except Exception as e:
                print("Enhancement error:", e)
                roi_enhanced = roi_frame.copy()
            # ================================================
            # Resize enhanced ROI for YOLO
            roi_resized = cv2.resize(roi_enhanced, (320, 320))
            # Send enhanced frame into YOLO model
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

        # --- Draw last known width line and text ---
        if hasattr(self, "last_width_cm") and self.last_width_cm is not None and hasattr(self, "last_line"):
            min_x, max_x, center_y = self.last_line
            mid_x = (min_x + max_x) // 2
            text = f"Width: {self.last_width_cm:.1f} cm"
            (text_width, text_height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 3)
            text_x = mid_x - text_width // 2
            text_y = center_y - 10
            cv2.putText(display_frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)
            self.ui.lcd_width.setText(f"{self.last_width_cm:.1f}")

        # --- ✅ Reference (Actual Width) comparison with ±5% tolerance ---
        if hasattr(self, "actual_width") and self.actual_width:
            actual_width = self.actual_width
            measured_width = self.last_width_cm
            tolerance = actual_width * 0.05
            diff = abs(measured_width - actual_width)
            if diff <= tolerance:
                status_text = f"OK (Δ={diff:.2f} cm)"
                color = (0, 255, 0)  # ✅ Stop blinking, keep solid red
                self.blink_active = False
                self.ui.lcd_width.setStyleSheet("""
                    background-color: black; color: red; border: none; 
                    font-family: 'DS-Digital', 'Courier New', monospace; 
                    font-size: 620px; font-weight: bold;
                """)
            else:
                status_text = f"OUT OF RANGE (Δ={diff:.2f} cm)"
                color = (0, 0, 255)  # ✅ Start blinking
                if not self.blink_active:
                    self.blink_active = True
                    self.blink_timer.start()

        # --- Buffer + Logging (unchanged) ---
        if not hasattr(self, "width_buffer"):
            self.width_buffer = []
        if detected_width_cm:
            self.width_buffer.append(detected_width_cm)
        if len(self.width_buffer) > 5:
            self.width_buffer = self.width_buffer[-5:]

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

        # --- Display final frame ---
        try:
            rgb_image = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            qt_img = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
            self.video_window.label_video.setPixmap(QPixmap.fromImage(qt_img))
        except Exception:
            pass
        self.processing = False

    def on_set_reference_width(self):
        """
        Sets the reference (actual) width from the entry field.
        Can be triggered by either clicking 'Set Ref' button or pressing Enter.
        """
        text = self.ui.entry_actual_width.text().strip()
        if not text:
            QMessageBox.warning(self, "Input Required", "Please enter a valid reference width.")
            return

        try:
            self.actual_width = float(text)
            QMessageBox.information(
                self,
                "Reference Set",
                f"Reference width set to {self.actual_width:.2f} cm"
            )
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a numeric value.")

    def blink_lcd(self):
        if self.blink_active:
            if self.blink_state:
                self.ui.lcd_width.setStyleSheet("""
                    background-color: black;
                    color: red;
                    border: none;
                    font-family: 'DS-Digital', 'Courier New', monospace;
                    font-size: 620px;
                    font-weight: bold;
                """)
            else:
                self.ui.lcd_width.setStyleSheet("""
                    background-color: black;
                    color: white;
                    border: none;
                    font-family: 'DS-Digital', 'Courier New', monospace;
                    font-size: 620px;
                    font-weight: bold;
                """)
            self.blink_state = not self.blink_state

    def calibrate_using_edges(self):
        """Calibrate pixels_per_cm using last detected width instead of running YOLO again"""
        if not hasattr(self, "last_width_cm") or self.last_width_cm is None:
            QMessageBox.warning(self, "Calibration Error", "No measurement available to calibrate. Detect first.")
            return

        last_detected_px = None
        # Use last detected pixel width
        if hasattr(self, "last_line") and self.last_line:
            min_x, max_x, _ = self.last_line
            last_detected_px = max_x - min_x

        if not last_detected_px or last_detected_px <= 0:
            QMessageBox.warning(self, "Calibration Error", "Invalid last width detected.")
            return

        # Ask user for real width (cm)
        known_width_cm, ok = QInputDialog.getDouble(
            self, "Calibration", "Enter real width (cm):", min=0.1
        )
        if not ok:
            return

        # Compute pixels per cm
        self.pixels_per_cm = last_detected_px / known_width_cm
        self.nominal_width_cm = known_width_cm
        self.calibrated = True
        self.actual_width = known_width_cm  # set reference for display
        self.last_width_cm = last_detected_px / self.pixels_per_cm  # update last measured width in cm

        # Update LCD immediately
        self.ui.lcd_width.setText(f"{self.last_width_cm:.1f}")

        # --- Save calibration to settings.json ---
        self.settings["pixels_per_cm"] = self.pixels_per_cm
        self.settings["nominal_width_cm"] = self.nominal_width_cm
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

        QMessageBox.information(
            self,
            "Calibration Successful",
            f"Calibration complete!\n1 cm = {self.pixels_per_cm:.2f} pixels\nLast measured width updated."
        )


