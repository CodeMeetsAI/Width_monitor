import hashlib, winreg

def get_machine_guid():
    registry_path = r"SOFTWARE\Microsoft\Cryptography"
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path)
    value, _ = winreg.QueryValueEx(key, "MachineGuid")
    winreg.CloseKey(key)
    return value.strip()

guid = get_machine_guid()
hashed = hashlib.sha256(guid.encode()).hexdigest()
print("Your authorized hash:")
print(hashed)
