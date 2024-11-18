import os
import platform
import sys
import subprocess
import logging
from datetime import datetime

# Create a timestamped log file name (e.g., minecraft_launcher_2024-11-13_13-45-30.log)
log_filename = datetime.now().strftime("minecraft_launcher_%Y-%m-%d_%H-%M-%S.log")

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, mode="w")  # Write to the timestamped log file
    ]
)

# Ensure that the Python version is 3.12 or higher
required_python_version = (3, 12)
current_python_version = sys.version_info

if current_python_version < required_python_version:
    logging.error(f"Python {required_python_version[0]}.{required_python_version[1]} or higher is required. "
                  f"Current version: {current_python_version[0]}.{current_python_version[1]}")
    sys.exit(1)

# Ensure that the script is running on macOS
if platform.system() != "Darwin":
    logging.error("Error, you are not running macOS. Please use a Mac to run this.")
    sys.exit(1)

# Get the current working directory and set game paths
cwd = os.getcwd()
MCPath = os.path.join(cwd, "game")
MCBinPath = os.path.join(MCPath, "bin")

# Get the path to Java 6 using the `java_home` utility
try:
    JavaHome = subprocess.check_output(["/usr/libexec/java_home", "-v", "1.6"]).strip().decode("utf-8")
    JavaPath = os.path.join(JavaHome, "bin", "java")
    logging.info(f"Java 6 found at {JavaPath}")
except subprocess.CalledProcessError as e:
    logging.error("Java 6 is not installed or could not be found.\nIf you would like to download Java 6, go here: https://updates.cdn-apple.com/2019/cert/041-88384-20191011-3d8da658-dca4-4a5b-b67c-26e686876403/JavaForOSX.dmg")
    sys.exit(1)

# JVM arguments and user settings
JVMArgs = "-Xmx768M -Xms768M"
MCUser = "Steve"

# Game launch information
logging.info("Minecraft 1.2.5 for Legacy Mac OS, version 1.0.4")
logging.info("Adapted from the PowerPC version of Minecraft 1.2.5")
logging.info("And Minecraft Fast SP by Thicc Industries")
logging.info("Made by TheGamersHollow in 2024")
logging.info("Launching the game...\n\n\n")

# Construct the classpath for the game
classpaths = [
    os.path.join(MCBinPath, "minecraft.jar"),
    os.path.join(MCBinPath, "lwjgl.jar"),
    os.path.join(MCBinPath, "lwjgl_util.jar"),
    os.path.join(MCBinPath, "jinput.jar")
]

# Join classpaths with the correct separator for macOS (colon)
classpath = ":".join(classpaths)

# Specify the Java library path
library_path = os.path.join(MCBinPath, "natives")

# Construct the full command with user-specific options
command = (
    f'"{JavaPath}" -cp "{classpath}" '
    f'-Djava.library.path="{library_path}" '
    f'{JVMArgs} '
    f'net.minecraft.client.Minecraft --username "{MCUser}"'
)

# Log the command (optional)
logging.debug(f"Launching Minecraft with command: {command}")

# Execute the command
try:
    subprocess.run(command, shell=True, check=True)
    logging.info("Minecraft launched successfully.")
except subprocess.CalledProcessError as e:
    logging.error(f"Failed to launch Minecraft: {e}")
    sys.exit(1)
