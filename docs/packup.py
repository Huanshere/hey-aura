"""
This script packages the project into a zip file for distribution.

Functions:
- collect_files(root, include_dirs): Collects files from the root directory and specified subdirectories for packaging. Only specific subfolders in 'models' are included.
- get_total_size(files): Calculates the total size of all files to be packaged.
- human_readable_size(size): Converts a file size in bytes to a human-readable string.
- print_progress_bar(iteration, total, ...): Prints a progress bar to the console during packaging.
- packup(): Main function to collect files, confirm with the user, and create the zip archive.
"""

"""
On MacOS, Pack the conda env:
# 1) 建环境并安装你的项目
conda create -n hey-aura-pack python=3.10 -y
conda activate hey-aura-pack
pip install .   # 安装你项目（已在 hey-aura/ 目录）
# 可选：装 ASR 依赖
# pip install parakeet-mlx funasr

# 2) 安装 conda-pack 并打包
pip install conda-pack
conda-pack -n hey-aura-pack -o hey-aura-macos-aarch64.tar.gz
"""
import os
import zipfile
import platform
import yaml

# Define result name based on platform
RESULT_NAME = "hey-aura-windows.zip" if platform.system() == "Windows" else "hey-aura-macos.zip"
print(f"Packaging for {platform.system()}")

def collect_files(root, include_dirs):
    files = []
    # Decide which files to ignore based on the operating system
    ignore_files = ["config.dev.yaml", "models_mac.zip", "models_windows.zip", "hey-aura-windows.zip", "hey-aura-macos.zip"]
    if platform.system() == "Windows":
        ignore_files.append("Start_MacOS.command")
    else:  # macOS or other systems
        ignore_files.append("Start_Windows.bat")
    
    # All files in the root directory that are not folders
    for item in os.listdir(root):
        item_path = os.path.join(root, item)
        if os.path.isfile(item_path) and item not in ignore_files:
            arcname = item
            files.append((item_path, arcname))
    
    # Specified folders and their contents
    for folder in include_dirs:
        folder_path = os.path.join(root, folder)
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            # Special handling for the models folder
            if folder == "models":
                # Platform-specific model selection
                allowed_models = []
                
                if platform.system() == "Windows":
                    allowed_models.append(os.path.join("models", "models--mobiuslabsgmbh--faster-whisper-large-v3-turbo"))
                else:  # macOS
                    allowed_models.append(os.path.join("models", "models--mlx-community--whisper-large-v3-turbo"))
                
                for allowed_model in allowed_models:
                    model_abs_path = os.path.join(root, allowed_model)
                    if os.path.exists(model_abs_path) and os.path.isdir(model_abs_path):
                        for dirpath, dirnames, filenames in os.walk(model_abs_path, followlinks=False):
                            for filename in filenames:
                                file_path = os.path.join(dirpath, filename)
                                arcname = os.path.relpath(file_path, root)
                                files.append((file_path, arcname))
            else:
                for dirpath, dirnames, filenames in os.walk(folder_path):
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        arcname = os.path.relpath(file_path, root)
                        files.append((file_path, arcname))
    return files


def get_total_size(files):
    total = 0
    for file_path, _ in files:
        if os.path.exists(file_path):
            if os.path.islink(file_path):
                # For symlinks, count the size of the link target string, not the linked file
                link_target = os.readlink(file_path)
                total += len(link_target)
            else:
                total += os.path.getsize(file_path)
    return total

def human_readable_size(size):
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end='\r')
    if iteration == total:
        print()

def check_config_safety():
    """Check if config.yaml contains default API key values before packaging"""
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.yaml"))
    
    if not os.path.exists(config_path):
        print("⚠️  Warning: config.yaml not found")
        return True
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Check LLM API key
        llm_config = config.get('llm', {})
        api_key = llm_config.get('api_key', '')
        
        if 'api' not in api_key.lower():
            print("⚠️  WARNING: API key does NOT contain 'api' - this might be a real API key!")
            print(f"   Current API key: {api_key}")
            print("   Please make sure to reset API key to default value before packaging for distribution.")
            print("   Default value should be something like: 'sk_your_api_key' or 'gsk_your_api_key'")
            
            confirm = input("Continue packaging anyway? (y/n): ")
            if confirm.lower() != 'y':
                print("Packaging cancelled due to API key check.")
                return False
        else:
            print("✅ API key check passed (contains 'api', appears to be default value)")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Warning: Could not check config.yaml: {e}")
        return True

def packup():
    # Check config safety first
    if not check_config_safety():
        return
    
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    include_dirs = ["core", "docs", "locales", "models"]
    if platform.system() == "Windows":  # 仅在 Windows 上包含 python_env
        include_dirs.insert(1, "python_env")
    
    # Collect all files including models
    files = collect_files(root, include_dirs)
    total_size = get_total_size(files)
    
    print(f"Package size: {human_readable_size(total_size)}")
    print(f"Total files: {len(files)}")
    
    confirm = input("Continue packaging? (y/n): ")
    if confirm.lower() != 'y':
        print("Packaging cancelled.")
        return
    
    # Package all files into a single zip
    print(f"Packaging into {RESULT_NAME}...")
    total_files = len(files)
    with zipfile.ZipFile(RESULT_NAME, "w", zipfile.ZIP_DEFLATED) as zipf:
        for idx, (file_path, arcname) in enumerate(files, 1):
            if os.path.islink(file_path):
                # Handle symlinks properly - create a ZipInfo with appropriate attributes
                link_target = os.readlink(file_path)
                zip_info = zipfile.ZipInfo(arcname)
                zip_info.create_system = 3  # Unix system
                zip_info.external_attr = (0o777 & 0xFFFF) << 16  # Set as link
                zip_info.external_attr |= 0x20000000  # Mark as symlink
                zipf.writestr(zip_info, link_target)
            else:
                zipf.write(file_path, arcname)
            print_progress_bar(idx, total_files, prefix='Progress', suffix='Complete', length=40)
    
    print(f"✅ Packaging complete: {RESULT_NAME}")
    print(f"   File size: {human_readable_size(os.path.getsize(RESULT_NAME))}")

if __name__ == "__main__":
    packup()
