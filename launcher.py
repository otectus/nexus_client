import os
import sys
import subprocess
from datetime import datetime

class NexusLauncher:
    def __init__(self):
        self.plugins = {
            "synthcore": {"name": "Synth Core", "enabled": True},
            "synthmemory": {"name": "Synth Memory", "enabled": True},
            "synthidentity": {"name": "Synth Identity", "enabled": True},
            "synthmood": {"name": "Synth Mood", "enabled": True},
        }
        self.version = "3.1.0"

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def show_header(self):
        print("="*40)
        print(f"      NEXUS SYSTEM LAUNCHER v{self.version}")
        print("="*40)

    def run(self):
        while True:
            self.clear_screen()
            self.show_header()
            print("1. Load with Plugins (Default)")
            print("2. Choose Plugins")
            print("3. Load [No Plugins]")
            print("4. Settings")
            print("5. Quit")
            print("-"*40)
            
            choice = input("Selection: ").strip()

            if choice == "1":
                self.launch(all_plugins=True)
            elif choice == "2":
                self.plugin_menu()
            elif choice == "3":
                self.launch(all_plugins=False)
            elif choice == "4":
                self.settings_menu()
            elif choice == "5":
                print("Exiting.")
                sys.exit(0)

    def plugin_menu(self):
        while True:
            self.clear_screen()
            self.show_header()
            print("--- PLUGIN SELECTION ---")
            plugin_keys = list(self.plugins.keys())
            for i, key in enumerate(plugin_keys, 1):
                info = self.plugins[key]
                status = "[ON]" if info["enabled"] else "[OFF]"
                print(f"{i}. {info['name']} {status}")
            
            print(f"{len(self.plugins)+1}. BACK to Main Menu")
            print(f"{len(self.plugins)+2}. LAUNCH with current selection")
            
            choice = input("Toggle # or selection: ").strip()
            
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(self.plugins):
                    key = plugin_keys[idx-1]
                    self.plugins[key]["enabled"] = not self.plugins[key]["enabled"]
                elif idx == len(self.plugins) + 1:
                    break
                elif idx == len(self.plugins) + 2:
                    self.launch(custom=True)

    def settings_menu(self):
        self.clear_screen()
        self.show_header()
        print("--- SETTINGS ---")
        print("(Backend settings and environment configuration)")
        input("\nPress Enter to return...")

    def launch(self, all_plugins=True, custom=False):
        enabled = []
        if all_plugins and not custom:
            enabled = list(self.plugins.keys())
        elif custom:
            enabled = [k for k, v in self.plugins.items() if v["enabled"]]
        
        env = os.environ.copy()
        env["NEXUS_MODS_ENABLED"] = ",".join(enabled) if enabled else "None"
        env["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))

        print(f"\nLaunching main instance with mods: {enabled}...")
        try:
            main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
            subprocess.Popen([sys.executable, main_path], env=env)
            sys.exit(0)
        except Exception as e:
            print(f"Launch Error: {e}")
            input("Press Enter...")

if __name__ == "__main__":
    launcher = NexusLauncher()
    launcher.run()