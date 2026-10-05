import torch

import sys
import uuid
from PyQt6.QtWidgets import QApplication, QMessageBox
from app_logic import MainApp

# 🔐 Hardcoded authorized MAC address
AUTHORIZED_MAC = "70:5a:0f:d7:c5:75"   # <-- replace with your real MAC


def get_mac_address():
    mac = uuid.getnode()    
    return ':'.join([f"{(mac >> ele) & 0xff:02x}" for ele in range(40, -1, -8)])


def check_license():
    current_mac = get_mac_address().lower()

    if current_mac != AUTHORIZED_MAC.lower():
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "License Error",
            "Unauthorized device! License check failed."
        )
        sys.exit(1)

    print("✅ License verified. Running application...")


def main():
    # 🔐 Run license check before launching GUI
    check_license()

    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()