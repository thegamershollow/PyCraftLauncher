import os
import json
import requests
import subprocess
import zipfile
import platform
from pathlib import Path

MINECRAFT_VERSION = input("Please enter the Minecraft Version you wish to play: ")
USERNAME = input("Enter a Username: ")
BASE_DIR = Path("minecraft")
LIBRARIES_DIR = BASE_DIR / "libraries"
ASSETS_DIR = BASE_DIR / "assets"
NATIVES_DIR = BASE_DIR / "natives"
JAVA_PATH = "java"  # Change if Java isn't in your PATH

GAME_DIR = BASE_DIR

# Function for downloading files
def download_file(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

# Download version manifest and full metadata
def download_version_manifest():
    url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    data = requests.get(url).json()
    for version in data["versions"]:
        if version["id"] == MINECRAFT_VERSION:
            return requests.get(version["url"]).json()
    raise Exception("Version not found.")

# Get native classifier for current OS
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
    version_id = version_data.get("id", MINECRAFT_VERSION)
    version_dir = BASE_DIR / "versions" / version_id
    version_dir.mkdir(parents=True, exist_ok=True)

    # Download client
    client_url = version_data["downloads"]["client"]["url"]
    client_path = version_dir / f"{version_id}.jar"
    download_file(client_url, client_path)

    # Save version JSON
    json_path = version_dir / f"{version_id}.json"
    with open(json_path, "w") as f:
        json.dump(version_data, f, indent=2)

    # Download libraries
    for lib in version_data["libraries"]:
        if "downloads" in lib:
            if "artifact" in lib["downloads"]:
                artifact = lib["downloads"]["artifact"]
                lib_path = LIBRARIES_DIR / Path(artifact["path"])
                download_file(artifact["url"], lib_path)

            # Native libraries
            classifiers = lib["downloads"].get("classifiers", {})
            native = get_native_for_os(classifiers)
            if native:
                native_path = LIBRARIES_DIR / Path(native["path"])
                download_file(native["url"], native_path)

# Download assets and save index JSON using correct ID
def download_assets(version_data):
    asset_index_info = version_data.get("assetIndex")
    if not asset_index_info:
        print(f"[❌] No asset index found for version {MINECRAFT_VERSION}.")
        return

    asset_index_id = asset_index_info.get("id", MINECRAFT_VERSION)
    asset_index_url = asset_index_info["url"]

    index_path = ASSETS_DIR / "indexes" / f"{asset_index_id}.json"
    (ASSETS_DIR / "indexes").mkdir(parents=True, exist_ok=True)
    (ASSETS_DIR / "objects").mkdir(parents=True, exist_ok=True)

    # Download asset index JSON
    response = requests.get(asset_index_url)
    response.raise_for_status()
    asset_index = response.json()

    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(asset_index, f, indent=2)

    # Download all asset objects
    print(f"[⬇️] Downloading assets for Minecraft {MINECRAFT_VERSION}...")
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

# Extract native libraries
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

# Build classpath for Java launch
def build_classpath(version_data):
    libs = []
    for lib in version_data["libraries"]:
        if "downloads" in lib and "artifact" in lib["downloads"]:
            artifact = lib["downloads"]["artifact"]
            lib_path = LIBRARIES_DIR / Path(artifact["path"])
            libs.append(str(lib_path))
    version_id = version_data.get("id", MINECRAFT_VERSION)
    client_jar = BASE_DIR / "versions" / version_id / f"{version_id}.jar"
    libs.append(str(client_jar))
    return os.pathsep.join(libs)

# Launch the game
def launch_minecraft(version_data):
    version_id = version_data.get("id", MINECRAFT_VERSION)
    asset_index_id = version_data.get("assetIndex", {}).get("id", version_id)

    classpath = build_classpath(version_data)
    main_class = version_data["mainClass"]

    args = [
        JAVA_PATH,
        "-Xmx1G",
        f"-Djava.library.path={NATIVES_DIR}",
        "-cp", classpath,
        main_class,
        "--username", USERNAME,
        "--version", version_id,
        "--gameDir", str(GAME_DIR),
        "--assetsDir", str(ASSETS_DIR),
        "--assetIndex", asset_index_id,
        "--accessToken", "0",
        "--uuid", "0",
    ]

    print(f"[🚀] Launching Minecraft {version_id} in Offline Mode on {platform.system()}...")
    subprocess.run(args)

# Main execution
def main():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    version_data = download_version_manifest()
    download_client_and_libraries(version_data)
    download_assets(version_data)
    extract_natives(version_data)
    launch_minecraft(version_data)

if __name__ == "__main__":
    main()
