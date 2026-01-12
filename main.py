import os
import sys
import logging
from pygpt_net.app import run
from nexus.bridge import NexusBridgePlugin

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("NexusKernel")

def main():
    mods_str = os.getenv("NEXUS_MODS_ENABLED", "")
    enabled_mods = mods_str.split(",") if mods_str and mods_str != "None" else []

    logger.info("--- NEXUS SYSTEM LOAD SEQUENCE ---")
    logger.info(f"Active mods identified: {enabled_mods if enabled_mods else 'VANILLA'}")

    # Instantiate custom plugins
    plugins = []
    if enabled_mods:
        nexus_bridge = NexusBridgePlugin()
        plugins.append(nexus_bridge)
        logger.info("Nexus Bridge Plugin initialized.")

    logger.info("Launching PyGPT with active Nexus modules...")
    
    # This call starts the actual PyGPT GUI application
    run(plugins=plugins)

if __name__ == "__main__":
    main()
