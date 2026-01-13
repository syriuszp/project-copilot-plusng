import zipfile
import os
import glob

def package_repo():
    out_zip = "releases/v4.2_production_ready.zip"
    if not os.path.exists("releases"):
        os.makedirs("releases")
        
    print(f"Creating {out_zip}...")
    
    # Files/Dirs to include
    includes = [
        "app",
        "tests",
        "config",
        "db",
        "scripts",
        "pyproject.toml",
        "pytest.ini",
        "README.md",
        "MANIFEST.in",
        "manual_init.py",
        "data/project_copilot.db"
    ]
    
    with zipfile.ZipFile(out_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in includes:
            if os.path.isfile(item):
                print(f"Adding {item}")
                zf.write(item)
            elif os.path.isdir(item):
                print(f"Adding {item}/...")
                for root, dirs, files in os.walk(item):
                    # Exclude __pycache__
                    if "__pycache__" in dirs:
                        dirs.remove("__pycache__")
                    
                    for file in files:
                        if file == ".DS_Store" or file.endswith(".pyc"):
                            continue
                        path = os.path.join(root, file)
                        zf.write(path)
                        
    print("Done.")

if __name__ == "__main__":
    package_repo()
