import os
import sys
import subprocess
import shutil


def run_cmd(cmd, description):
    print(f"\n>>> Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error executing command! Code: {result.returncode}")
        print("STDOUT:")
        print(result.stdout)
        print("STDERR:")
        print(result.stderr)
        sys.exit(1)
    print("Command completed successfully.")
    return result


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root_dir)

    print("==========================================")
    print("INTHON WINDOWS INSTALLER BUILD PIPELINE")
    print("==========================================")

    # 0. Ensure icon.ico exists in documents directory
    ico_path = os.path.abspath(os.path.join(root_dir, "..", "documents", "icon.ico"))
    png_path = os.path.abspath(os.path.join(root_dir, "..", "documents", "icon.png"))
    if not os.path.exists(ico_path):
        if os.path.exists(png_path):
            print(f"\n>>> Generating ICO from {png_path}...")
            try:
                from PIL import Image

                img = Image.open(png_path)
                sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                img.save(ico_path, format="ICO", sizes=sizes)
                print(f"ICO saved to {ico_path}")
            except Exception as e:
                print(f"Error generating ICO: {e}")
                sys.exit(1)
        else:
            print(f"[ERROR] Original logo not found at {png_path}!")
            sys.exit(1)

    # 1. Clean previous build files
    print("\n>>> Cleaning previous build artifacts...")
    for folder in ["build", "dist"]:
        path = os.path.join(root_dir, folder)
        if os.path.exists(path):
            print(f"Removing {path}...")
            shutil.rmtree(path, ignore_errors=True)

    # 2. Build inthon.exe (CLI & Interpreter)
    # We add grammar.lark to inthon/parser in the packed binary
    # We must ensure to NOT use --noconsole here since it is a command-line tool.
    excludes = [
        "torch",
        "transformers",
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        "sklearn",
        "pyarrow",
        "polars",
        "datasets",
        "huggingface_hub",
        "sympy",
        "jedi",
        "PyPDF2",
        "pdfminer",
        "yt_dlp",
        "IPython",
        "notebook",
        "jupyter",
        "openai",
        "seaborn",
        "scikit-learn",
        "comm",
        "ipykernel",
        "ipywidgets",
        "widgetsnbextension",
        "nbconvert",
        "nbformat",
        "notebook_shim",
    ]

    build_inthon_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "-y",
        "--onefile",
        "--icon",
        ico_path,
        "--name",
        "inthon",
        "--add-data",
        f"../inthon/parser/grammar.lark{os.pathsep}inthon/parser",
        "inthon_bin.py",
    ]
    for ex in excludes:
        build_inthon_cmd.extend(["--exclude-module", ex])
    run_cmd(build_inthon_cmd, "Stage 1/3: Compiling INTHON Compiler CLI (inthon.exe)")

    # 3. Sanity check: Run compiled inthon.exe on examples/hello.inth
    inthon_exe = os.path.join(root_dir, "dist", "inthon.exe")
    if not os.path.exists(inthon_exe):
        print("[ERROR] compiled inthon.exe not found!")
        sys.exit(1)

    print("\n>>> Stage 1.5/3: Verifying compiled inthon.exe...")
    verify_cmd = [inthon_exe, "run", "../examples/hello.inth"]
    verify_res = subprocess.run(verify_cmd, capture_output=True, text=True)
    if (
        verify_res.returncode != 0
        or "Hello, INTHON Developer!" not in verify_res.stdout
    ):
        print("[ERROR] Compiled inthon.exe failed verification test!")
        print("Exit Code:", verify_res.returncode)
        print("STDOUT:", verify_res.stdout)
        print("STDERR:", verify_res.stderr)
        sys.exit(1)
    print("Sanity Check Passed! Output:", verify_res.stdout.strip())

    # 4. Build uninstall.exe (GUI Uninstaller)
    # Since it is a GUI program, we use --noconsole to prevent black command window
    build_uninstall_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "-y",
        "--onefile",
        "--noconsole",
        "--icon",
        ico_path,
        "--name",
        "uninstall",
        "--add-data",
        f"{ico_path}{os.pathsep}.",
        "uninstaller.py",
    ]
    for ex in excludes:
        build_uninstall_cmd.extend(["--exclude-module", ex])
    run_cmd(
        build_uninstall_cmd,
        "Stage 2/3: Compiling INTHON Uninstaller GUI (uninstall.exe)",
    )

    # Verify uninstall.exe exists
    uninstall_exe = os.path.join(root_dir, "dist", "uninstall.exe")
    if not os.path.exists(uninstall_exe):
        print("[ERROR] compiled uninstall.exe not found!")
        sys.exit(1)

    # 5. Build inthon-installer.exe (GUI Installer)
    # We bundle the compiled inthon.exe, uninstall.exe, and the inthon.toml config
    # Since it is a GUI program, we use --noconsole
    build_installer_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "-y",
        "--onefile",
        "--noconsole",
        "--icon",
        ico_path,
        "--name",
        "inthon-installer",
        "--add-data",
        f"dist/inthon.exe{os.pathsep}.",
        "--add-data",
        f"dist/uninstall.exe{os.pathsep}.",
        "--add-data",
        f"../inthon.toml{os.pathsep}.",
        "--add-data",
        f"{ico_path}{os.pathsep}.",
        "installer.py",
    ]
    for ex in excludes:
        build_installer_cmd.extend(["--exclude-module", ex])
    run_cmd(
        build_installer_cmd,
        "Stage 3/3: Compiling Unified INTHON Installer GUI (inthon-installer.exe)",
    )

    # Verify installer exists
    installer_exe = os.path.join(root_dir, "dist", "inthon-installer.exe")
    if not os.path.exists(installer_exe):
        print("[ERROR] compiled inthon-installer.exe not found!")
        sys.exit(1)

    # 6. Copy compiled binaries to the root dist directory
    root_dist_dir = os.path.abspath(os.path.join(root_dir, "..", "dist"))
    print(
        f"\n>>> Stage 4/3: Copying compiled binaries to root dist directory ({root_dist_dir})..."
    )
    os.makedirs(root_dist_dir, exist_ok=True)
    for exe_name in ["inthon.exe", "uninstall.exe", "inthon-installer.exe"]:
        src_path = os.path.join(root_dir, "dist", exe_name)
        dst_path = os.path.join(root_dist_dir, exe_name)
        print(f"Copying {src_path} -> {dst_path}...")
        shutil.copy2(src_path, dst_path)

    print("\n==========================================")
    print("BUILD SUCCESSFUL!")
    print("==========================================")
    print("Generated binaries in the 'dist' directory:")
    print("1. CLI Compiler:  ", inthon_exe)
    print("2. Uninstaller:   ", uninstall_exe)
    print("3. Setup Installer:", installer_exe)
    print("==========================================")


if __name__ == "__main__":
    main()
