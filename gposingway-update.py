#!/usr/bin/env python3
import os
import sys
import shutil
import json
import urllib.request
import zipfile
from datetime import datetime

# Helper to handle inputs safely (avoiding EOFError in non-interactive/piped environments)
def safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""

# Formatting helpers for a premium command-line interface
def print_success(msg):
    print(f"\033[92m✔ {msg}\033[0m")

def print_info(msg):
    print(f"\033[94mℹ {msg}\033[0m")

def print_warning(msg):
    print(f"\033[93m⚠ {msg}\033[0m")

def print_error(msg):
    print(f"\033[91m✘ {msg}\033[0m")

def ask_choice(prompt, options):
    """Prompt user for a choice with a list of allowed options."""
    opt_str = "/".join(options)
    while True:
        try:
            val = safe_input(f"{prompt} [{opt_str}]: ").strip().lower()
            if not val and 'y' in options:
                return 'y'
            if val in options:
                return val
            print_warning(f"Invalid option. Please choose one of: {opt_str}")
        except KeyboardInterrupt:
            print("\nOperation aborted by user.")
            sys.exit(0)

# Configurations
GPOSINGWAY_DEFINITIONS_URL = "https://github.com/gposingway/gposingway/releases/latest/download/gposingway-definitions.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def find_game_directory():
    """Scan the system for FFXIV installations, prompting the user if necessary."""
    # 1. Check if the current script directory contains the game
    if os.path.exists(os.path.join(SCRIPT_DIR, "ffxiv_dx11.exe")):
        return SCRIPT_DIR

    # 2. Check if the current working directory contains the game
    if os.path.exists(os.path.join(os.getcwd(), "ffxiv_dx11.exe")):
        return os.getcwd()

    # 3. Check standard Linux/Wine search paths
    search_paths = [
        os.path.expanduser("~/.xlcore/ffxiv/game"),
        os.path.expanduser("~/.local/share/Steam/steamapps/common/FINAL FANTASY XIV Online/game"),
        os.path.expanduser("~/.local/share/Steam/steamapps/common/FINAL FANTASY XIV - A Realm Reborn/game"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/FINAL FANTASY XIV Online/game"),
        os.path.expanduser("~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/FINAL FANTASY XIV - A Realm Reborn/game"),
    ]

    valid_paths = [p for p in search_paths if os.path.exists(os.path.join(p, "ffxiv_dx11.exe"))]

    if not valid_paths:
        print_warning("Could not automatically locate your FFXIV game directory.")
        while True:
            path_input = safe_input("Please enter the absolute path to your FFXIV 'game' folder: ").strip()
            if not path_input:
                continue
            path_expanded = os.path.abspath(os.path.expanduser(path_input))
            if os.path.exists(os.path.join(path_expanded, "ffxiv_dx11.exe")):
                return path_expanded
            print_error("Invalid directory. The folder must contain 'ffxiv_dx11.exe'.")

    if len(valid_paths) == 1:
        print_success(f"Detected FFXIV game folder: {valid_paths[0]}")
        return valid_paths[0]

    print_info("Multiple FFXIV game folders detected on your system:")
    for idx, path in enumerate(valid_paths):
        desc = "Steam" if "steam" in path.lower() else "XIVLauncher"
        print(f"  [{idx + 1}] {desc} ({path})")
    print()
    choices = [str(i + 1) for i in range(len(valid_paths))]
    ans = ask_choice("Select installation directory", choices)
    selected_path = valid_paths[int(ans) - 1]
    print_success(f"Selected: {selected_path}")
    return selected_path

GAME_DIR = find_game_directory()
GPOSINGWAY_WORK_DIR = os.path.join(GAME_DIR, ".gposingway")
BACKUP_DIR = os.path.join(GPOSINGWAY_WORK_DIR, "Backup")
TEMP_DIR = os.path.join(GPOSINGWAY_WORK_DIR, "temp")

def run_folder_checks():
    """Verify script is run inside FFXIV game folder and has write access."""
    # Check FFXIV executable and working directory
    exec_path = os.path.join(GAME_DIR, "ffxiv_dx11.exe")
    if not os.path.exists(exec_path):
        print_error("Please make sure this script is run from your FFXIV game directory:")
        print("  e.g., \"[...]/SquareEnix/FINAL FANTASY XIV - A Realm Reborn/game\"")
        safe_input("\nPress Enter to exit...")
        sys.exit(1)

    # Check write permissions
    test_file = os.path.join(GAME_DIR, "gposingway.temp")
    try:
        with open(test_file, 'w') as f:
            f.write("write-test")
        os.remove(test_file)
    except IOError:
        print_error("I don't have permission to write to the game directory.")
        print("This is necessary to perform modifications in the game directory.")
        print("Please check directory permissions and run again.")
        safe_input("\nPress Enter to exit...")
        sys.exit(1)

def main():
    # Welcome Message
    print("------------------------------------------------")
    print(" (\\(\\ ")
    print(" ( o.o)    GPosingway Update/Installer Tool")
    print(" O_(\")(\")  1.0.6 (Linux/Windows)")
    print("------------------------------------------------")
    print()

    # Check CLI arguments for uninstallation first
    if len(sys.argv) > 1 and sys.argv[1] in ["--uninstall", "-u"]:
        run_folder_checks()
        uninstall()
        return

    # Folder and write permission checks
    run_folder_checks()

    # Interactive Menu
    print("Welcome to the GPosingway Manager!")
    print("What would you like to do?")
    print("  [1] Install or Update GPosingway")
    print("  [2] Uninstall GPosingway")
    print("  [3] Exit")
    print()

    choice = ask_choice("Please select an option", ['1', '2', '3'])
    if choice == '2':
        uninstall()
        return
    elif choice == '3':
        print("Goodbye!")
        sys.exit(0)

    print("\nStarting installation/update process...")
    print("Let's check some things before we start...\n")

    # Create directories
    os.makedirs(GPOSINGWAY_WORK_DIR, exist_ok=True)
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # Determine current version
    current_version = None
    defs_path = os.path.join(GPOSINGWAY_WORK_DIR, "gposingway-definitions.json")
    old_ver_path = os.path.join(GPOSINGWAY_WORK_DIR, "gposingway-version.txt")

    if os.path.exists(defs_path):
        try:
            with open(defs_path, 'r', encoding='utf-8') as f:
                current_version = json.load(f).get("version")
        except Exception:
            pass
    elif os.path.exists(old_ver_path):
        try:
            with open(old_ver_path, 'r', encoding='utf-8') as f:
                current_version = f.read().strip()
        except Exception:
            pass

    initial_install = (current_version is None)

    if initial_install:
        print_info("No previous GPosingway installation found!")
        ans = ask_choice("Proceed with installation?", ['y', 'n'])
        if ans == 'n':
            print("Installation aborted.")
            sys.exit(0)
    else:
        print_info(f"Current installed version: {current_version}")

    # Download definitions
    print_info("Checking for the latest version definitions...")
    temp_defs = os.path.join(TEMP_DIR, "gposingway-definitions.json")
    if not download_file(GPOSINGWAY_DEFINITIONS_URL, temp_defs):
        print_error("Could not fetch the latest definitions. Check your internet connection.")
        safe_input("\nPress Enter to exit...")
        sys.exit(1)

    try:
        with open(temp_defs, 'r', encoding='utf-8') as f:
            definitions = json.load(f)
    except Exception as e:
        print_error(f"Failed to read definitions: {e}")
        sys.exit(1)

    latest_version = definitions.get("version")
    gposingway_url = definitions.get("gposingwayUrl")
    print_success(f"Latest version: {latest_version}")

    # Determine if update/install is required
    install_update = initial_install
    dxgi_path = os.path.join(GAME_DIR, "dxgi.dll")
    dxgi_exists = os.path.exists(dxgi_path)

    if not initial_install:
        if latest_version == current_version:
            if not dxgi_exists:
                # If version is correct but the DLL is missing, force install to restore it
                print_warning("ReShade dxgi.dll is missing! Forcing installation to restore ReShade binaries...")
                install_update = True
            else:
                print_success("You already have the latest version installed!")
                install_update = False
        else:
            print_warning(f"A newer version ({latest_version}) of GPosingway is available!")
            ans = ask_choice("Do you want to install this update?", ['y', 'n'])
            if ans == 'n':
                if not dxgi_exists:
                    print_warning("Warning: dxgi.dll is missing. Since you skipped the update, ReShade will not load.")
                install_update = False
            else:
                install_update = True

    # Backup & Install main package
    if install_update:
        # Generate datetime timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        curr_backup = os.path.join(BACKUP_DIR, timestamp)
        os.makedirs(curr_backup, exist_ok=True)

        print_info("Backing up existing shaders, presets, and settings...")
        
        backup_items = [
            ("reshade-shaders", os.path.join(curr_backup, "reshade-shaders")),
            ("reshade-presets", os.path.join(curr_backup, "reshade-presets")),
            ("ReShade.ini", os.path.join(curr_backup, "ReShade.ini"))
        ]

        for item_name, backup_dest in backup_items:
            item_path = os.path.join(GAME_DIR, item_name)
            if os.path.exists(item_path):
                try:
                    if os.path.isdir(item_path):
                        shutil.copytree(item_path, backup_dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item_path, backup_dest)
                except Exception as e:
                    print_error(f"Failed to backup {item_name}: {e}")
                    safe_input("\nPress Enter to exit...")
                    sys.exit(1)

        print_success(f"Backup saved to: .gposingway/Backup/{timestamp}")

        # If initial installation, clean shaders folder before extraction
        if initial_install:
            shaders_dir = os.path.join(GAME_DIR, "reshade-shaders", "shaders")
            if os.path.exists(shaders_dir):
                shutil.rmtree(shaders_dir, ignore_errors=True)

        # Download main zip
        print_info("Downloading latest GPosingway package...")
        zip_path = os.path.join(TEMP_DIR, "gposingway.zip")
        if not download_file(gposingway_url, zip_path):
            safe_input("\nPress Enter to exit...")
            sys.exit(1)

        # Extract
        print_info("Extracting GPosingway...")
        if not extract_zip(zip_path, GAME_DIR):
            safe_input("\nPress Enter to exit...")
            sys.exit(1)
        print_success("Package extracted successfully!")

        # Download and extract ReShade dxgi.dll if missing (Linux)
        setup_dxgi_dll(definitions)

    # Cleanup deprecated files/directories
    deprecated_items = definitions.get("Deprecated", [])
    if deprecated_items:
        print_info("Cleaning up deprecated files...")
        for item in deprecated_items:
            # Replace backslashes with platform-native separator
            item_normalized = item.replace('\\', '/')
            if item_normalized.startswith(('reshade-shaders/', 'reshade-presets/')):
                full_path = os.path.join(GAME_DIR, item_normalized)
                if os.path.exists(full_path):
                    try:
                        if os.path.isdir(full_path):
                            shutil.rmtree(full_path, ignore_errors=True)
                        else:
                            os.remove(full_path)
                        print(f"  - Removed deprecated: {item_normalized}")
                    except Exception as e:
                        print_warning(f"Could not remove deprecated {item_normalized}: {e}")

    # Process Optional add-ons
    optional_addons = definitions.get("Optional", [])
    if optional_addons:
        print()
        print_info("Some optional add-ons are available!")
        for addon in optional_addons:
            name = addon.get("Name")
            url = addon.get("Url")
            mappings_str = addon.get("Mappings", "")

            ans = ask_choice(f"Would you like to install optional add-on '{name}'?", ['y', 'n'])
            if ans == 'y':
                print_info(f"Installing optional add-on: {name}")
                addon_temp = os.path.join(TEMP_DIR, name)
                os.makedirs(addon_temp, exist_ok=True)

                addon_zip = os.path.join(addon_temp, f"{name}.zip")
                if download_file(url, addon_zip):
                    if extract_zip(addon_zip, addon_temp):
                        # Parse mappings: e.g. "iMMERSE-main\\Shaders:reshade-shaders\\Shaders"
                        mappings = mappings_str.split(';')
                        for mapping in mappings:
                            if not mapping or ':' not in mapping:
                                continue
                            src_rel, dest_rel = mapping.split(':', 1)
                            src_rel = src_rel.replace('\\', '/')
                            dest_rel = dest_rel.replace('\\', '/')

                            src_path = os.path.normpath(os.path.join(addon_temp, src_rel))
                            dest_path = os.path.normpath(os.path.join(GAME_DIR, dest_rel))

                            if os.path.exists(src_path):
                                print(f"  - Mapping: {src_rel} -> {dest_rel}")
                                if os.path.isdir(src_path):
                                    copy_merge(src_path, dest_path)
                                else:
                                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                                    shutil.copy2(src_path, dest_path)
                        print_success(f"Add-on '{name}' installed!")

    # Set up Linux system compiler dependencies
    setup_linux_dependencies()

    # Wrap up: Save definitions to working dir
    shutil.copy2(temp_defs, defs_path)

    # Copy updater scripts to FFXIV game folder for future run convenience if run from outside
    curr_script_path = os.path.abspath(__file__)
    dest_script_path = os.path.join(GAME_DIR, "gposingway-update.py")
    if curr_script_path != dest_script_path:
        try:
            shutil.copy2(curr_script_path, dest_script_path)
            os.chmod(dest_script_path, 0o755)
            shutil_sh_src = os.path.join(os.path.dirname(curr_script_path), "gposingway-update.sh")
            shutil_sh_dest = os.path.join(GAME_DIR, "gposingway-update.sh")
            if os.path.exists(shutil_sh_src):
                shutil.copy2(shutil_sh_src, shutil_sh_dest)
                os.chmod(shutil_sh_dest, 0o755)
        except Exception:
            pass

    # Clean up temp files
    print_info("Cleaning up temporary files...")
    shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print()
    
    # Final check of dxgi.dll installation status
    dxgi_final_path = os.path.join(GAME_DIR, "dxgi.dll")
    if os.path.exists(dxgi_final_path):
        print_success("GPosingway installation/update complete. Happy GPosing!")
    else:
        print_warning("GPosingway files extracted, but dxgi.dll (ReShade) was not found in the game folder.")
        print("To finish setting up ReShade, please download and copy dxgi.dll to this folder.")
        print("Download link: https://reshade.me/")

    # If running on Linux, output helpful Wine configuration hints
    if os.name != 'nt':
        print("\n" + "=" * 60)
        print("\033[93m★ LINUX WINE / PROTON POST-INSTALLATION TIPS ★\033[0m")
        print("DLL overrides have been automatically configured in your Wine prefix registry!")
        print("You don't need to configure manual launch environment variables.")
        print("ReShade and the D3D compiler should now load automatically in-game.")
        print("=" * 60 + "\n")

    safe_input("Press Enter to finish...")

def setup_dxgi_dll(definitions):
    """Download ReShade with Addon support directly from reshade.me and extract ReShade64.dll as dxgi.dll if missing."""
    if os.name == 'nt':
        return

    dxgi_dest = os.path.join(GAME_DIR, "dxgi.dll")
    if os.path.exists(dxgi_dest):
        return

    reshade_url = definitions.get("reshadeUrl")
    if not reshade_url:
        print_error("ReShade download URL ('reshadeUrl') is missing from the update definitions JSON.")
        print("Please contact the GPosingway maintainers to update the definitions file.")
        return

    # Extract version from URL for the log message
    version_str = "unknown"
    try:
        filename = reshade_url.split('/')[-1]
        if "ReShade_Setup_" in filename:
            version_str = filename.replace("ReShade_Setup_", "").replace("_Addon.exe", "")
        else:
            version_str = filename
    except Exception:
        pass

    print_info(f"dxgi.dll (ReShade) is missing. Downloading official ReShade {version_str} with Add-on support...")
    temp_setup_path = os.path.join(TEMP_DIR, f"ReShade_Setup_{version_str}_Addon.exe")

    if download_file(reshade_url, temp_setup_path):
        try:
            print_info("Extracting ReShade64.dll from installer...")
            with zipfile.ZipFile(temp_setup_path, 'r') as zip_ref:
                with zip_ref.open("ReShade64.dll") as source, open(dxgi_dest, 'wb') as target:
                    shutil.copyfileobj(source, target)
            os.chmod(dxgi_dest, 0o755)
            print_success("ReShade dxgi.dll setup complete!")
        except Exception as e:
            print_error(f"Failed to extract ReShade DLL from installer: {e}")
            if os.path.exists(dxgi_dest):
                try:
                    os.remove(dxgi_dest)
                except OSError:
                    pass
    else:
        print_error("Failed to download ReShade setup from reshade.me.")

def configure_wine_dll_overrides(prefix_path):
    """Automatically configure d3dcompiler_47 and dxgi overrides to native,builtin in Wine user.reg registry."""
    user_reg_path = os.path.join(prefix_path, "user.reg")
    if not os.path.exists(user_reg_path):
        return

    print_info(f"Configuring DLL overrides in Wine prefix registry: {user_reg_path}")
    try:
        with open(user_reg_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        new_lines = []
        in_dll_overrides = False
        has_dxgi = False
        has_d3dcompiler = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[Software\\\\Wine\\\\DllOverrides]"):
                in_dll_overrides = True
                new_lines.append(line)
                continue
            elif stripped.startswith("[") and in_dll_overrides:
                # Left the DllOverrides section; inject missing items
                if not has_d3dcompiler:
                    new_lines.append('"d3dcompiler_47"="native,builtin"\n')
                if not has_dxgi:
                    new_lines.append('"dxgi"="native,builtin"\n')
                in_dll_overrides = False
            
            if in_dll_overrides:
                if stripped.startswith('"dxgi"='):
                    new_lines.append('"dxgi"="native,builtin"\n')
                    has_dxgi = True
                    continue
                elif stripped.startswith('"d3dcompiler_47"='):
                    new_lines.append('"d3dcompiler_47"="native,builtin"\n')
                    has_d3dcompiler = True
                    continue
                elif stripped == "" and (not has_dxgi or not has_d3dcompiler):
                    continue
            
            new_lines.append(line)

        if in_dll_overrides:
            if not has_d3dcompiler:
                new_lines.append('"d3dcompiler_47"="native,builtin"\n')
            if not has_dxgi:
                new_lines.append('"dxgi"="native,builtin"\n')

        section_found = any("[Software\\\\Wine\\\\DllOverrides]" in line for line in lines)
        if not section_found:
            new_lines.append("\n[Software\\\\Wine\\\\DllOverrides]\n")
            new_lines.append('"d3dcompiler_47"="native,builtin"\n')
            new_lines.append('"dxgi"="native,builtin"\n')

        with open(user_reg_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print_success(f"Configured dll overrides in {os.path.basename(os.path.dirname(prefix_path))} prefix successfully.")
    except Exception as e:
        print_warning(f"Could not configure registry overrides for prefix {prefix_path}: {e}")

def uninstall_wine_dll_overrides(prefix_path):
    """Remove d3dcompiler_47 and dxgi DLL overrides from Wine registry."""
    user_reg_path = os.path.join(prefix_path, "user.reg")
    if not os.path.exists(user_reg_path):
        return

    print_info(f"Removing DLL overrides from Wine prefix registry: {user_reg_path}")
    try:
        with open(user_reg_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        new_lines = []
        in_dll_overrides = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("[Software\\\\Wine\\\\DllOverrides]"):
                in_dll_overrides = True
                new_lines.append(line)
                continue
            elif stripped.startswith("[") and in_dll_overrides:
                in_dll_overrides = False
            
            if in_dll_overrides:
                if stripped.startswith('"dxgi"=') or stripped.startswith('"d3dcompiler_47"='):
                    continue
            
            new_lines.append(line)

        with open(user_reg_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print_success(f"Removed dll overrides from {os.path.basename(os.path.dirname(prefix_path))} prefix.")
    except Exception as e:
        print_warning(f"Could not remove registry overrides for prefix {prefix_path}: {e}")

def uninstall():
    """Remove GPosingway/ReShade files and restore the latest backup if available."""
    print()
    print_info("Starting GPosingway uninstallation...")

    # 1. Check if backups exist
    backups = []
    if os.path.exists(BACKUP_DIR):
        try:
            backups = sorted(
                [d for d in os.listdir(BACKUP_DIR) if os.path.isdir(os.path.join(BACKUP_DIR, d))]
            )
        except OSError:
            pass

    restore_backup = False
    latest_backup_dir = None
    if backups:
        latest_backup = backups[-1]
        latest_backup_dir = os.path.join(BACKUP_DIR, latest_backup)
        print_info(f"Found a previous backup folder from: {latest_backup}")
        ans = ask_choice("Would you like to restore this backup?", ['y', 'n'])
        if ans == 'y':
            restore_backup = True

    # 2. Delete current GPosingway files/directories in game directory
    items_to_remove = [
        "reshade-shaders",
        "reshade-presets",
        "ReShade.ini",
        "ReShadePreset.ini",
        "dxgi.dll",
        "d3dcompiler_47.dll",
        "gposingway-update.py",
        "gposingway-update.sh"
    ]

    for item in items_to_remove:
        path = os.path.join(GAME_DIR, item)
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                print_success(f"Removed: {item} from game directory")
            except Exception as e:
                print_warning(f"Could not remove {item}: {e}")

    # 3. Restore files from backup if requested
    if restore_backup and latest_backup_dir:
        print_info("Restoring files from the latest backup...")
        for item in os.listdir(latest_backup_dir):
            src_path = os.path.join(latest_backup_dir, item)
            dest_path = os.path.join(GAME_DIR, item)
            try:
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_path)
                print_success(f"Restored: {item}")
            except Exception as e:
                print_error(f"Failed to restore {item}: {e}")

    # 4. Clean up Wine prefix d3dcompiler_47.dll modifications
    if os.name != 'nt':
        print_info("Cleaning up Wine prefixes...")
        prefixes = []
        
        # Check XIVLauncher prefix
        xlcore_prefix = os.path.expanduser("~/.xlcore/wineprefix")
        if os.path.exists(xlcore_prefix):
            prefixes.append(xlcore_prefix)
            
        # Check Steam prefixes
        steamapps_dir = os.path.abspath(os.path.join(GAME_DIR, "..", "..", ".."))
        if os.path.basename(steamapps_dir).lower() == "steamapps":
            compatdata_dir = os.path.join(steamapps_dir, "compatdata")
            if os.path.exists(compatdata_dir):
                try:
                    for appid in os.listdir(compatdata_dir):
                        pfx_dir = os.path.join(compatdata_dir, appid, "pfx")
                        if os.path.exists(pfx_dir) and is_ffxiv_prefix(pfx_dir):
                            prefixes.append(pfx_dir)
                except OSError:
                    pass

        for prefix in prefixes:
            sys32_dest = os.path.join(prefix, "drive_c", "windows", "system32", "d3dcompiler_47.dll")
            if os.path.exists(sys32_dest):
                try:
                    # Only remove if it's the Microsoft compiler we copied (size > 3MB)
                    if os.path.getsize(sys32_dest) > 3 * 1024 * 1024:
                        os.chmod(sys32_dest, 0o755)
                        os.remove(sys32_dest)
                        print_success(f"Removed Microsoft d3dcompiler_47.dll from Wine prefix: {os.path.basename(os.path.dirname(prefix))}")
                except Exception as e:
                    print_warning(f"Could not remove d3dcompiler_47.dll from prefix {prefix}: {e}")
            
            # Remove DLL overrides from prefix registry
            uninstall_wine_dll_overrides(prefix)

    # 5. Clean up definitions JSON
    defs_path = os.path.join(GPOSINGWAY_WORK_DIR, "gposingway-definitions.json")
    if os.path.exists(defs_path):
        try:
            os.remove(defs_path)
        except OSError:
            pass

    print()
    print_success("GPosingway has been successfully uninstalled!")
    
    if os.name != 'nt':
        print_info("Note: You can now remove 'WINEDLLOVERRIDES' from your launcher settings if you wish.")

    safe_input("\nPress Enter to finish...")
    sys.exit(0)

def setup_linux_dependencies():
    """Locate Wine prefixes, copy d3dcompiler_47.dll, and set registry overrides."""
    if os.name == 'nt':
        return

    print()
    print_info("Linux detected: Setting up native Microsoft D3D compiler dependencies...")

    # 1. Locate potential Wine prefixes
    prefixes = []

    # Check for XIVLauncher prefix
    xlcore_prefix = os.path.expanduser("~/.xlcore/wineprefix")
    if os.path.exists(xlcore_prefix):
        prefixes.append(xlcore_prefix)

    # Check for Steam prefixes (relative to game path)
    steamapps_dir = os.path.abspath(os.path.join(GAME_DIR, "..", "..", ".."))
    if os.path.basename(steamapps_dir).lower() == "steamapps":
        compatdata_dir = os.path.join(steamapps_dir, "compatdata")
        if os.path.exists(compatdata_dir):
            try:
                for appid in os.listdir(compatdata_dir):
                    pfx_dir = os.path.join(compatdata_dir, appid, "pfx")
                    if os.path.exists(pfx_dir):
                        # Check if this prefix is related to FFXIV
                        if is_ffxiv_prefix(pfx_dir):
                            prefixes.append(pfx_dir)
            except OSError:
                pass

    # Fallback to checking AppIDs specifically if no documents folder match succeeded
    if not prefixes and os.name != 'nt' and os.path.basename(steamapps_dir).lower() == "steamapps":
        compatdata_dir = os.path.join(steamapps_dir, "compatdata")
        for appid in ["39210", "312060"]:
            pfx_dir = os.path.join(compatdata_dir, appid, "pfx")
            if os.path.exists(pfx_dir):
                prefixes.append(pfx_dir)

    # 2. Find a valid Microsoft d3dcompiler_47.dll on the system (size > 3MB, x64 ELF/PE header)
    print_info("Searching system for official Microsoft d3dcompiler_47.dll (64-bit)...")
    search_paths = [
        os.path.expanduser("~/.local/share/Steam"),
        os.path.expanduser("~/.steam"),
        os.path.expanduser("~/.var/app"),
        "/var/lib/flatpak",
    ]
    if os.path.basename(steamapps_dir).lower() == "steamapps":
        search_paths.append(os.path.dirname(steamapps_dir))

    found_dll_path = None
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        for root, dirs, files in os.walk(search_path):
            if any(p in root for p in ["/proc", "/sys", "/dev", "/run", "/tmp", "/etc", "/var/log"]):
                continue
            if "d3dcompiler_47.dll" in files:
                full_path = os.path.join(root, "d3dcompiler_47.dll")
                try:
                    # Microsoft's official DLL is ~3.8MB to ~4.7MB. Wine stub is ~370KB.
                    if os.path.getsize(full_path) > 3 * 1024 * 1024:
                        # Parse PE header to verify it's x86-64 (64-bit)
                        with open(full_path, 'rb') as f:
                            header = f.read(1024)
                            if header.startswith(b'MZ'):
                                pe_offset = int.from_bytes(header[0x3C:0x40], byteorder='little')
                                if pe_offset + 24 < len(header) and header[pe_offset:pe_offset+4] == b'PE\x00\x00':
                                    machine = int.from_bytes(header[pe_offset+4:pe_offset+6], byteorder='little')
                                    if machine == 0x8664:  # AMD64 (64-bit)
                                        found_dll_path = full_path
                                        break
                except OSError:
                    pass
        if found_dll_path:
            break

    if not found_dll_path:
        print_warning("Could not find a native Microsoft d3dcompiler_47.dll (64-bit) on your system.")
        print("Some complex shaders may fail to compile or freeze the game.")
        print("To fix this, you can manually install it via: protontricks 312060 d3dcompiler_47")
        return

    print_success(f"Found Microsoft d3dcompiler_47.dll at: {found_dll_path}")

    # 3. Copy to the game directory
    game_dest = os.path.join(GAME_DIR, "d3dcompiler_47.dll")
    copy_dll_file(found_dll_path, game_dest, "game directory")

    # 4. Copy to found Wine prefixes and set overrides
    for prefix in prefixes:
        sys32_dir = os.path.join(prefix, "drive_c", "windows", "system32")
        if os.path.exists(sys32_dir):
            sys32_dest = os.path.join(sys32_dir, "d3dcompiler_47.dll")
            copy_dll_file(found_dll_path, sys32_dest, f"Wine prefix ({os.path.basename(os.path.dirname(prefix))})")
            # Apply DLL overrides directly to user.reg inside prefix
            configure_wine_dll_overrides(prefix)

def is_ffxiv_prefix(pfx_path):
    """Check if the given Wine prefix contains FFXIV document directories."""
    users_dir = os.path.join(pfx_path, "drive_c", "users")
    if os.path.exists(users_dir):
        try:
            for user in os.listdir(users_dir):
                user_path = os.path.join(users_dir, user)
                if not os.path.isdir(user_path):
                    continue
                for doc_sub in ["Documents", "My Documents"]:
                    docs_path = os.path.join(user_path, doc_sub, "My Games", "FINAL FANTASY XIV - A Realm Reborn")
                    if os.path.exists(docs_path):
                        return True
        except OSError:
            pass
    return False

def copy_dll_file(src, dest, dest_desc):
    try:
        # Check if destination file exists and is already native (size > 3MB)
        if os.path.exists(dest) and os.path.getsize(dest) > 3 * 1024 * 1024:
            print_success(f"Native d3dcompiler_47.dll is already present in {dest_desc}.")
            return

        if os.path.exists(dest):
            os.chmod(dest, 0o755)
        shutil.copy2(src, dest)
        os.chmod(dest, 0o755)
        print_success(f"Copied native d3dcompiler_47.dll to {dest_desc}.")
    except Exception as e:
        print_warning(f"Could not copy d3dcompiler_47.dll to {dest_desc}: {e}")

def download_file(url, dest_path):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print_error(f"Failed to download: {e}")
        return False

def extract_zip(zip_path, extract_dir):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        return True
    except Exception as e:
        print_error(f"Extraction failed: {e}")
        return False

def copy_merge(src, dst):
    """Recursively copies files from src into dst, merging directories."""
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_merge(s, d)
        else:
            shutil.copy2(s, d)

if __name__ == "__main__":
    main()
