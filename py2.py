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
    JavaHome = subprocess.check_output(["/usr/libexec/java_home", "-v", "1.6"]).strip()
    JavaPath = os.path.join(JavaHome, "bin", "java")
    logging.info("Java 6 found at %s", JavaPath)
except subprocess.CalledProcessError as e:
    logging.error("Java 6 is not installed or could not be found.")
    sys.exit(1)

# JVM arguments and user settings
JVMArgs = "-Xmx2048M -Xms2048M"
MCUser = "MCUser"

# Game launch information
logging.info("Minecraft 1.2.5 for Legacy Mac OS, version 1.0.0")
logging.info("Adapted from the PowerPC version of Minecraft 1.2.5")
logging.info("And minecraft fast sp by thicc industries")
logging.info("Made by TheGamersHollow in 2024")
logging.info("Launching the game...\n\n\n")

# Construct the launch command
command = "{0} -cp {1}:{2}:{3}:{4} -Djava.library.path={5} {6} net.minecraft.client.Minecraft --username {7}".format(
    JavaPath,
    os.path.join(MCBinPath, 'minecraft.jar'),
    os.path.join(MCBinPath, 'lwjgl.jar'),
    os.path.join(MCBinPath, 'lwjgl_util.jar'),
    os.path.join(MCBinPath, 'jinput.jar'),
    os.path.join(MCBinPath, 'natives'),
    JVMArgs,
    MCUser
)

# Log the command (optional, you can comment this if sensitive info is a concern)
logging.debug("Launching Minecraft with command: %s", command)

# Execute the command
try:
    subprocess.call(command, shell=True)  # Changed to subprocess.call() for Python 2.7
    logging.info("Minecraft launched successfully.")
except subprocess.CalledProcessError as e:
    logging.error("Failed to launch Minecraft: %s", e)
    sys.exit(1)
