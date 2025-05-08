import os
import json
import requests
import subprocess
import zipfile
import platform
import psutil
from pathlib import Path
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

SETTINGS_FILE = "settings.json"
BASE_DIR = Path("minecraft")
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
NATIVES_DIR = BASE_DIR / "natives"
VERSIONS_DIR = BASE_DIR / "versions"
JAVA_PATH = "java"  # Change if Java isn't in your PATH

# Load saved settings
def load_settings():
    if Path(SETTINGS_FILE).exists():
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

# Save settings
def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)

# Function for downloading files with progress bar
def download_file(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    response = requests.get(url, stream=True)
    response.raise_for_status()
    total = int(response.headers.get('content-length', 0))
    with open(dest, "wb") as f, tqdm(
        desc=f"Downloading {os.path.basename(dest)}",
        total=total,
        unit='B',
        unit_scale=True,
        unit_divisor=1024
    ) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

# Version selector
def choose_version():
    url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    data = requests.get(url).json()
    versions = data["versions"]

    include_snapshots = input("Show snapshots? (y/n): ").lower() == "y"
    filtered_versions = [v for v in versions if include_snapshots or v["type"] == "release"]

    print("Available versions:")
    for i, v in enumerate(filtered_versions[:20]):
        print(f"{i + 1}. {v['id']} ({v['type']})")

    while True:
        try:
            idx = int(input("Choose a version number: ")) - 1
            return filtered_versions[idx]["id"]
        except (ValueError, IndexError):
            print("Invalid input, try again.")

# Get full metadata for chosen version
def download_version_manifest(version_id):
    manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
    for version in manifest["versions"]:
        if version["id"] == version_id:
            return requests.get(version["url"]).json()
    raise Exception("Version not found.")

# Get native classifier

def get_native_for_os(classifiers):
    os_name = platform.system().lower()
    if os_name == "windows":
        return classifiers.get("natives-windows")
    elif os_name == "linux":
        return classifiers.get("natives-linux")
    elif os_name == "darwin":
        return classifiers.get("natives-osx")
    else:
        raise Exception(f"Unsupported OS: {os_name}")

# Download JAR and libraries
def download_client_and_libraries(version_data):
    version_id = version_data.get("id")
    version_dir = VERSIONS_DIR / version_id
    version_dir.mkdir(parents=True, exist_ok=True)

    downloads = []

    # Client
    client_path = version_dir / f"{version_id}.jar"
    if not client_path.exists():
        downloads.append((version_data["downloads"]["client"]["url"], client_path))

    # Version JSON
    json_path = version_dir / f"{version_id}.json"
    with open(json_path, "w") as f:
        json.dump(version_data, f, indent=2)

    # Libraries
    for lib in version_data["libraries"]:
        downloads_data = lib.get("downloads", {})
        if "artifact" in downloads_data:
            artifact = downloads_data["artifact"]
            path = LIBRARIES_DIR / artifact["path"]
            if not path.exists():
                downloads.append((artifact["url"], path))

        classifiers = downloads_data.get("classifiers", {})
        native = get_native_for_os(classifiers)
        if native:
            native_path = LIBRARIES_DIR / native["path"]
            if not native_path.exists():
                downloads.append((native["url"], native_path))

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(lambda args: download_file(*args), downloads)

# Download assets
def download_assets(version_data):
    asset_index_info = version_data.get("assetIndex")
    if not asset_index_info:
        print("[❌] No asset index found.")
        return

    asset_index_id = asset_index_info.get("id")
    asset_index_url = asset_index_info["url"]
    index_path = ASSETS_DIR / "indexes" / f"{asset_index_id}.json"
    (ASSETS_DIR / "indexes").mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "objects").mkdir(parents=True, exist_ok=True)

    asset_index = requests.get(asset_index_url).json()
    with open(index_path, "w") as f:
        json.dump(asset_index, f, indent=2)

    downloads = []
    for name, info in asset_index["objects"].items():
        hash_val = info["hash"]
        subdir = hash_val[:2]
        url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
        target = ASSETS_DIR / "objects" / subdir / hash_val
        if not target.exists():
            downloads.append((url, target))

    with ThreadPoolExecutor(max_workers=8) as executor:
        executor.map(lambda args: download_file(*args), downloads)

# Extract natives
def extract_natives(version_data):
    NATIVES_DIR.mkdir(parents=True, exist_ok=True)
    for lib in version_data["libraries"]:
        classifiers = lib.get("downloads", {}).get("classifiers", {})
        native = get_native_for_os(classifiers)
        if native:
            native_path = LIBRARIES_DIR / native["path"]
            try:
                with zipfile.ZipFile(native_path, 'r') as zip_ref:
                    zip_ref.extractall(NATIVES_DIR)
            except zipfile.BadZipFile:
                print(f"[⚠️] Bad ZIP file: {native_path}")

# Build classpath
def build_classpath(version_data):
    paths = []
    for lib in version_data["libraries"]:
        artifact = lib.get("downloads", {}).get("artifact")
        if artifact:
            paths.append(str(LIBRARIES_DIR / artifact["path"]))
    version_id = version_data["id"]
    client_jar = VERSIONS_DIR / version_id / f"{version_id}.jar"
    paths.append(str(client_jar))
    return os.pathsep.join(paths)

# Launch Minecraft
def launch_minecraft(version_data, username, ram):
    version_id = version_data["id"]
    asset_index_id = version_data.get("assetIndex", {}).get("id", version_id)

    args = [
        JAVA_PATH,
        f"-Xmx{ram}M",
        f"-Djava.library.path={NATIVES_DIR}",
        "-cp", build_classpath(version_data),
        version_data["mainClass"],
        "--username", username,
        "--version", version_id,
        "--gameDir", str(BASE_DIR),
        "--assetsDir", str(ASSETS_DIR),
        "--assetIndex", asset_index_id,
        "--accessToken", "0",
        "--uuid", "0"
    ]

    print(f"[🚀] Launching Minecraft {version_id}...")
    subprocess.run(args)

# Main

def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    settings = load_settings()

    if settings.get("version") and settings.get("username"):
        use_last = input(f"Launch last used version ({settings['version']}) as {settings['username']}? (y/n): ").lower() == "y"
    else:
        use_last = False

    if use_last:
        version_id = settings["version"]
        username = settings["username"]
    else:
        version_id = choose_version()
        username = input("Enter a Username: ")

    # RAM
    total_ram = psutil.virtual_memory().total // (1024 * 1024)
    print(f"Total system RAM: {total_ram}MB")
    while True:
        try:
            ram = int(input("Enter RAM to allocate in MB (e.g., 1024): "))
            if ram < 256 or ram > total_ram:
                raise ValueError("Invalid RAM size")
            break
        except ValueError:
            print("Invalid value. Please enter a number between 256 and your system's max RAM.")

    settings.update({"version": version_id, "username": username})
    save_settings(settings)

    version_data = download_version_manifest(version_id)
    download_client_and_libraries(version_data)
    download_assets(version_data)
    extract_natives(version_data)
    launch_minecraft(version_data, username, ram)

if __name__ == "__main__":
    main()
