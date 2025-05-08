import os
import json
import requests
import subprocess
import zipfile
import platform
from pathlib import Path
from tqdm import tqdm

JAVA_PATH = "java"
BASE_DIR = Path("minecraft")
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
NATIVES_DIR = BASE_DIR / "natives"
GAME_DIR = BASE_DIR

# Download file with progress bar
def download_file(url, dest):
    if os.path.exists(dest):
        print(f"[✔️] Exists: {dest}")
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    response = requests.get(url, stream=True)
    total = int(response.headers.get('content-length', 0))
    with open(dest, "wb") as file, tqdm(
        desc=f"⬇️ {os.path.basename(dest)}",
        total=total,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            file.write(data)
            bar.update(len(data))

# Let user pick Minecraft version
def select_minecraft_version():
    print("Fetching Minecraft versions...")
    manifest = requests.get("https://launchermeta.mojang.com/mc/game/version_manifest_v2.json").json()
    versions = manifest["versions"][:20]  # Limit to latest 20 for brevity
    for idx, v in enumerate(versions):
        print(f"{idx + 1}. {v['id']} ({v['type']})")
    while True:
        try:
            choice = int(input("Select Minecraft version [1-20]: "))
            if 1 <= choice <= len(versions):
                selected = versions[choice - 1]
                version_json = requests.get(selected["url"]).json()
                return version_json
        except (ValueError, IndexError):
            pass
        print("Invalid selection. Try again.")

# Get native library for current OS
def get_native_for_os(classifiers):
    os_name = platform.system().lower()
    return classifiers.get({
        "windows": "natives-windows",
        "linux": "natives-linux",
        "darwin": "natives-osx"
    }.get(os_name, ""), None)

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

            native = get_native_for_os(lib["downloads"].get("classifiers", {}))
            if native:
                native_path = LIBRARIES_DIR / Path(native["path"])
                download_file(native["url"], native_path)

def download_assets(version_data):
    index_info = version_data.get("assetIndex")
    if not index_info:
        print(f"[❌] No asset index found for version {version_data['id']}.")
        return

    index_path = ASSETS_DIR / "indexes" / f"{index_info['id']}.json"
    os.makedirs(index_path.parent, exist_ok=True)
    asset_index = requests.get(index_info["url"]).json()
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(asset_index, f, indent=2)

    print(f"[⬇️] Downloading assets for Minecraft {version_data['id']}...")
    for name, info in asset_index["objects"].items():
        hash_val = info["hash"]
        subdir = hash_val[:2]
        target = ASSETS_DIR / "objects" / subdir / hash_val
        if not target.exists():
            url = f"https://resources.download.minecraft.net/{subdir}/{hash_val}"
            download_file(url, target)

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
                print(f"[⚠️] Bad ZIP file for {native_path}")

def build_classpath(version_data):
    libs = []
    for lib in version_data["libraries"]:
        if "artifact" in lib.get("downloads", {}):
            lib_path = LIBRARIES_DIR / Path(lib["downloads"]["artifact"]["path"])
            libs.append(str(lib_path))
    version_id = version_data["id"]
    client_jar = BASE_DIR / "versions" / version_id / f"{version_id}.jar"
    libs.append(str(client_jar))
    return os.pathsep.join(libs)

def launch_minecraft(version_data, username):
    version_id = version_data["id"]
    asset_index_id = version_data["assetIndex"]["id"]
    classpath = build_classpath(version_data)
    main_class = version_data["mainClass"]

    args = [
        JAVA_PATH,
        "-Xmx1G",
        f"-Djava.library.path={NATIVES_DIR}",
        "-cp", classpath,
        main_class,
        "--username", username,
        "--version", version_id,
        "--gameDir", str(GAME_DIR),
        "--assetsDir", str(ASSETS_DIR),
        "--assetIndex", asset_index_id,
        "--accessToken", "0",
        "--uuid", "0",
    ]

    print(f"[🚀] Launching Minecraft {version_id} in Offline Mode...")
    subprocess.run(args)

def main():
    version_data = select_minecraft_version()
    username = input("Enter a Username [default: Steve]: ").strip() or "Steve"
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    download_client_and_libraries(version_data)
    download_assets(version_data)
    extract_natives(version_data)
    launch_minecraft(version_data, username)

if __name__ == "__main__":
    main()
