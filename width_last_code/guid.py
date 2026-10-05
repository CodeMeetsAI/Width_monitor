import sys
import hashlib
import winreg
from PyQt6.QtWidgets import QApplication, QMessageBox
from app_logic import MainApp


# 🔐 Hardcoded authorized machine ID (generated from Machine GUID)
AUTHORIZED_DEVICE_ID = "94140c25d09d30eec97c1dccd609b537f612dc636f1a149ca0dbc6c949b7a752"  # <-- replace with real authorized hash


def get_machine_guid():
    """
    Read the Windows Machine GUID from registry.
    """
    try:
        registry_path = r"SOFTWARE\Microsoft\Cryptography"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path)
        value, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return value.strip()
    except Exception as e:
        print("Error reading MachineGuid:", e)
        return None


def get_device_id():
    """
    Generate a hashed device ID from Machine GUID for privacy.
    """
    guid = get_machine_guid()
    if not guid:
        return None

    # Hash it for privacy — never expose raw Machine GUID
    hashed = hashlib.sha256(guid.encode()).hexdigest()
    return hashed


def check_license():
    """
    Check whether the device is authorized to run the application.
    """
    device_id = get_device_id()

    if not device_id or device_id.lower() != AUTHORIZED_DEVICE_ID.lower():
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "License Error",
            "❌ Unauthorized device detected!\n\nLicense check failed.",
        )
        sys.exit(1)

    print("✅ License verified. Running application...")


def main():
    # Run license check before launching GUI
    check_license()

    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
