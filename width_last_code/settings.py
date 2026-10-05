from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QCheckBox, QMessageBox, QInputDialog, QComboBox
import json
import os

SETTINGS_FILE = "settings.json"
PASSWORD = "admin123"

class SettingsDialog(QDialog):
    def __init__(self, parent=None, calibrate_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(300)
        self.calibrate_callback = calibrate_callback
        self.layout = QVBoxLayout()

        self.settings = self.load_settings()
        self.label_camera = QLabel("Select Sensor:")
        self.combo_camera = QComboBox()
        self.populate_camera_list()
        self.combo_camera.setEnabled(False)

        self.checkbox_autostart = QCheckBox("Auto-start Sensor")
        self.checkbox_autostart.setChecked(self.settings.get("auto_start", False))
        self.checkbox_autostart.setEnabled(False)

        self.btn_calibrate = QPushButton("Calibrate")
        self.btn_calibrate.setEnabled(False)

        self.btn_unlock = QPushButton("Unlock Settings")
        self.btn_save = QPushButton("Save Settings")

        self.btn_unlock.clicked.connect(self.unlock_settings)
        self.btn_calibrate.clicked.connect(self.call_calibrate)
        self.btn_save.clicked.connect(self.save)

        self.layout.addWidget(self.label_camera)
        self.layout.addWidget(self.combo_camera)
        self.layout.addWidget(self.checkbox_autostart)
        self.layout.addWidget(self.btn_calibrate)
        self.layout.addWidget(self.btn_unlock)
        self.layout.addWidget(self.btn_save)
        self.setLayout(self.layout)

        previous_camera = self.settings.get("selected_camera")
        if previous_camera:
            index = self.combo_camera.findData(previous_camera)
            if index >= 0:
                self.combo_camera.setCurrentIndex(index)

    def populate_camera_list(self):
        """Populate with webcam + pre-defined IP camera streams"""
        self.combo_camera.clear()

        # Always read the latest IP from file
        settings = self.load_settings()
        camera_ip = settings.get("camera_ip", "192.168.1.108")

        # ✅ Add webcam option
        self.combo_camera.addItem("Webcam (Default)", "0")

        # ✅ Add RTSP streams
        self.combo_camera.addItem(
            "Sensor Stream (Main)",
            f"rtsp://admin:Miniload1!@{camera_ip}:554/cam/realmonitor?channel=1&subtype=0"
        )
        self.combo_camera.addItem(
            "Sensor Stream (Sub)",
            f"rtsp://admin:Miniload1!@{camera_ip}:554/cam/realmonitor?channel=1&subtype=1"
        )

        # Restore last saved selection
        previous_camera = settings.get("selected_camera")
        if previous_camera is not None:
            index = self.combo_camera.findData(previous_camera)
            if index >= 0:
                self.combo_camera.setCurrentIndex(index)



    def unlock_settings(self):
        password, ok = QInputDialog.getText(self, "Password", "Enter password:", QLineEdit.EchoMode.Password)
        if ok and password == PASSWORD:
            self.combo_camera.setEnabled(True)
            self.checkbox_autostart.setEnabled(True)
            self.btn_calibrate.setEnabled(True)
        else:
            QMessageBox.warning(self, "Access Denied", "Incorrect password!")

    def call_calibrate(self):
        self.close()
        if self.calibrate_callback:
            self.calibrate_callback()

    def save(self):
        self.settings["auto_start"] = self.checkbox_autostart.isChecked()
        self.settings["selected_camera"] = self.combo_camera.currentData()

        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f)

        QMessageBox.information(self, "Saved", "Settings saved successfully!")

        if self.parent():
            self.parent().settings = self.parent().load_settings()

            # Restart camera with the new stream immediately
            self.parent().stop_camera()
            self.parent().start_camera()

        self.close()

    def load_settings(self):
        default_settings = {
            "camera_ip": "192.168.1.108",
            "auto_start": False,
            "selected_camera": "192.168.1.108",
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
