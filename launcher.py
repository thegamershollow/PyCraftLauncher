import os
import json
import requests
import subprocess
import zipfile
import platform
import psutil
from pathlib import Path

# --------------------- Constants ---------------------
BASE_DIR = Path("minecraft")
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
NATIVES_DIR = BASE_DIR / "natives"
JAVA_PATH = "java"  # Change if Java isn't in your PATH
GAME_DIR = BASE_DIR
SETTINGS_FILE = BASE_DIR / "settings.json"

# --------------------- Utilities ---------------------
def download_file(url, dest):
    if dest.exists():
        print(f"[✔] Skipping existing file: {dest}")
        return
    os.makedirs(dest.parent, exist_ok=True)
    print(f"[⬇️] Downloading {url} -> {dest}")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    os.makedirs(BASE_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# --------------------- Version Selection ---------------------
def select_minecraft_version(settings):
    show_snapshots = input("Do you want to see snapshots? (y/N): ").strip().lower() == 'y'
    manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    manifest = requests.get(manifest_url).json()
    versions = [v for v in manifest["versions"] if show_snapshots or not v["type"].startswith("snapshot")]

    print("\nAvailable Versions:")
    for idx, v in enumerate(versions[:20]):
        print(f"{idx + 1}. {v['id']} ({v['type']})")

    while True:
        try:
            selection = int(input("Select a version by number (or 0 to enter manually): "))
            if selection == 0:
                version_id = input("Enter Minecraft version ID: ").strip()
            else:
                version_id = versions[selection - 1]["id"]
            for v in manifest["versions"]:
                if v["id"] == version_id:
                    return requests.get(v["url"]).json()
            print("[❌] Version not found.")
        except (ValueError, IndexError):
            print("[❌] Invalid selection.")

# --------------------- Username & RAM Input ---------------------
def get_username(settings):
    last_username = settings.get("username", "Player")
    use_last = input(f"Use last username '{last_username}'? (Y/n): ").strip().lower()
    if use_last in ["", "y", "yes"]:
        return last_username
    return input("Enter a Username: ").strip()

def get_ram_allocation(settings):
    total_mem_gb = psutil.virtual_memory().total // (1024 ** 3)
    print(f"[💾] Detected System RAM: {total_mem_gb} GB")

    last_xmx = settings.get("xmx", "2G")
    last_xms = settings.get("xms", "512M")
    use_last = input(f"Use last RAM settings? Xmx: {last_xmx}, Xms: {last_xms} (Y/n): ").strip().lower()
    if use_last in ["", "y", "yes"]:
        return last_xmx, last_xms

    def parse_ram_input(prompt):
        while True:
            val = input(prompt).strip().upper()
            if val.endswith("G") or val.endswith("M"):
                try:
                    num = int(val[:-1])
                    is_gb = val.endswith("G")
                    if (is_gb and num > total_mem_gb) or (not is_gb and num > total_mem_gb * 1024):
                        print(f"❌ You entered more than your system's {total_mem_gb} GB RAM.")
                    else:
                        return val
                except ValueError:
                    pass
            print("Invalid format. Use '2G' for GB or '512M' for MB.")

    xmx = parse_ram_input("Enter maximum RAM (Xmx, e.g., 2G): ")
    xms = parse_ram_input("Enter minimum RAM (Xms, e.g., 512M): ")
    settings["xmx"] = xmx
    settings["xms"] = xms
    return xmx, xms

# --------------------- Download Handlers ---------------------
def get_native_for_os(classifiers):
    os_name = platform.system().lower()
    return classifiers.get(f"natives-{os_name}")

def download_client_and_libraries(version_data):
    version_id = version_data["id"]
    version_dir = BASE_DIR / "versions" / version_id
    version_dir.mkdir(parents=True, exist_ok=True)

    client_url = version_data["downloads"]["client"]["url"]
    client_path = version_dir / f"{version_id}.jar"
    download_file(client_url, client_path)

    json_path = version_dir / f"{version_id}.json"
    with open(json_path, "w") as f:
        json.dump(version_data, f, indent=2)

    for lib in version_data["libraries"]:
        if "downloads" in lib:
            if "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                lib_path = LIBRARIES_DIR / Path(artifact["path"])
                download_file(artifact["url"], lib_path)

            classifiers = lib["downloads"].get("classifiers", {})
            native = get_native_for_os(classifiers)
            if native:
                native_path = LIBRARIES_DIR / Path(native["path"])
                download_file(native["url"], native_path)

def download_assets(version_data):
    asset_index_info = version_data.get("assetIndex")
    if not asset_index_info:
        print("[❌] No asset index found.")
        return

    index_path = ASSETS_DIR / "indexes" / f"{asset_index_info['id']}.json"
    (ASSETS_DIR / "indexes").mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "objects").mkdir(parents=True, exist_ok=True)

    response = requests.get(asset_index_info["url"])
    response.raise_for_status()
    asset_index = response.json()

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(asset_index, f, indent=2)

    print(f"[⬇️] Downloading assets for Minecraft {version_data['id']}...")
    for asset_name, asset_info in asset_index.get("objects", {}).items():
        hash_val = asset_info["hash"]
        subdir = hash_val[:2]
        url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
        target_path = ASSETS_DIR / "objects" / subdir / hash_val
        if not target_path.exists():
            download_file(url, target_path)
            print(f"Downloaded: {asset_name}")
        else:
            print(f"Exists: {asset_name}")
    print("[✅] All assets downloaded.")

def extract_natives(version_data):
    NATIVES_DIR.mkdir(parents=True, exist_ok=True)
    for lib in version_data["libraries"]:
        classifiers = lib.get("downloads", {}).get("classifiers", {})
        native = get_native_for_os(classifiers)
        if native:
            native_path = LIBRARIES_DIR / Path(native["path"])
            try:
                with zipfile.ZipFile(native_path, 'r') as zip_ref:
                    zip_ref.extractall(NATIVES_DIR)
            except zipfile.BadZipFile:
                print(f"Warning: Bad ZIP file for {native_path}")

def build_classpath(version_data):
    libs = []
    for lib in version_data["libraries"]:
        if "downloads" in lib and "artifact" in lib["downloads"]:
            artifact = lib["downloads"]["artifact"]
            lib_path = LIBRARIES_DIR / Path(artifact["path"])
            libs.append(str(lib_path))
    version_id = version_data["id"]
    client_jar = BASE_DIR / "versions" / version_id / f"{version_id}.jar"
    libs.append(str(client_jar))
    return os.pathsep.join(libs)

def launch_minecraft(version_data, username, xmx, xms):
    version_id = version_data["id"]
    asset_index_id = version_data["assetIndex"]["id"]
    classpath = build_classpath(version_data)

    args = [
        JAVA_PATH,
        f"-Xmx{xmx}",
        f"-Xms{xms}",
        f"-Djava.library.path={NATIVES_DIR}",
        "-cp", classpath,
        version_data["mainClass"],
        "--username", username,
        "--version", version_id,
        "--gameDir", str(GAME_DIR),
        "--assetsDir", str(ASSETS_DIR),
        "--assetIndex", asset_index_id,
        "--accessToken", "0",
        "--uuid", "0",
    ]

    print(f"[🚀] Launching Minecraft {version_id} with Xmx: {xmx}, Xms: {xms}...")
    subprocess.run(args)

# --------------------- Main ---------------------
def main():
    settings = load_settings()
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    use_last = False
    version_data = None

    if "version" in settings:
        answer = input(f"Last used version: '{settings['version']}'. Launch again? (Y/n): ").strip().lower()
        if answer in ["", "y", "yes"]:
            manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
            for v in manifest["versions"]:
                if v["id"] == settings["version"]:
                    version_data = requests.get(v["url"]).json()
                    use_last = True
                    break

    if not use_last or version_data is None:
        version_data = select_minecraft_version(settings)
        settings["version"] = version_data["id"]

    username = get_username(settings)
    xmx, xms = get_ram_allocation(settings)
    settings["username"] = username
    settings["xmx"] = xmx
    settings["xms"] = xms

    download_client_and_libraries(version_data)
    download_assets(version_data)
    extract_natives(version_data)
    launch_minecraft(version_data, username, xmx, xms)

    save_settings(settings)

if __name__ == "__main__":
    main()
