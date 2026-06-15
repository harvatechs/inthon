import os
import sys
import shutil
import winreg
import ctypes
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

# Theme colors
COLOR_BG = "#121214"
COLOR_CARD = "#1E1E22"
COLOR_TEXT = "#F3F4F6"
COLOR_SUBTEXT = "#9CA3AF"
COLOR_ACCENT = "#8B5CF6"
COLOR_ACCENT_HOVER = "#A78BFA"
COLOR_BORDER = "#2E2E38"
COLOR_INPUT_BG = "#26262B"
COLOR_SUCCESS = "#10B981"
COLOR_GRADIENT_START = "#7C3AED"
COLOR_GRADIENT_END = "#312E81"

VERSION = "0.1.0"


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class InthonInstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("INTHON Language Setup")
        self.geometry("680x420")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)

        # Center the window
        self.center_window()

        # Set window icon (if available)
        # self.iconbitmap(...)

        # Setup variables
        self.install_dir = tk.StringVar(
            value=os.path.join(
                os.environ.get("LOCALAPPDATA", "C:\\"), "Programs", "Inthon"
            )
        )
        self.add_to_path = tk.BooleanVar(value=True)
        self.associate_files = tk.BooleanVar(value=True)
        self.create_shortcuts = tk.BooleanVar(value=True)

        self.install_in_progress = False

        # Create Layout
        self.create_layout()

        # Show Page 1
        self.show_welcome_page()

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def create_layout(self):
        # Left Brand Panel (Sidebar Canvas)
        self.sidebar = tk.Canvas(
            self,
            width=220,
            height=420,
            bg=COLOR_GRADIENT_START,
            bd=0,
            highlightthickness=0,
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.bind("<Configure>", self.draw_sidebar_gradient)

        # Right Content Frame
        self.content_frame = tk.Frame(self, bg=COLOR_BG)
        self.content_frame.pack(
            side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=20, pady=20
        )

        # Intercept window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def draw_sidebar_gradient(self, event=None):
        width = self.sidebar.winfo_width()
        height = self.sidebar.winfo_height()
        self.sidebar.delete("gradient")

        # Draw smooth vertical gradient
        r1, g1, b1 = self.sidebar.winfo_rgb(COLOR_GRADIENT_START)
        r2, g2, b2 = self.sidebar.winfo_rgb(COLOR_GRADIENT_END)
        r1, g1, b1 = r1 // 256, g1 // 256, b1 // 256
        r2, g2, b2 = r2 // 256, g2 // 256, b2 // 256

        for i in range(height):
            r = r1 + (r2 - r1) * i // height
            g = g1 + (g2 - g1) * i // height
            b = b1 + (b2 - b1) * i // height
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.sidebar.create_line(0, i, width, i, fill=color, tags="gradient")

        # Draw Title
        self.sidebar.create_text(
            110,
            160,
            text="INTHON",
            font=("Segoe UI Semibold", 28, "bold"),
            fill=COLOR_TEXT,
            anchor=tk.CENTER,
        )
        self.sidebar.create_text(
            110,
            200,
            text=f"Version {VERSION}",
            font=("Segoe UI", 12),
            fill=COLOR_SUBTEXT,
            anchor=tk.CENTER,
        )
        self.sidebar.create_text(
            110,
            380,
            text="HarvaTechs Research",
            font=("Segoe UI", 9),
            fill=COLOR_SUBTEXT,
            anchor=tk.CENTER,
        )

    def clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def show_welcome_page(self):
        self.clear_content()

        # Title
        title_lbl = tk.Label(
            self.content_frame,
            text="Install INTHON v0.1.0",
            font=("Segoe UI Semibold", 18),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 5))

        desc_lbl = tk.Label(
            self.content_frame,
            text="Agent-level programming language for AI-native workflows.",
            font=("Segoe UI", 10),
            fg=COLOR_SUBTEXT,
            bg=COLOR_BG,
            wraplength=400,
            justify=tk.LEFT,
        )
        desc_lbl.pack(anchor=tk.W, pady=(0, 20))

        # Folder frame
        folder_frame = tk.LabelFrame(
            self.content_frame,
            text=" Destination Folder ",
            font=("Segoe UI Semibold", 9),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=10,
        )
        folder_frame.pack(fill=tk.X, pady=(0, 15))
        # Style the frame border using config
        folder_frame.config(
            highlightbackground=COLOR_BORDER, highlightcolor=COLOR_BORDER
        )

        self.folder_ent = tk.Entry(
            folder_frame,
            textvariable=self.install_dir,
            font=("Segoe UI", 10),
            bg=COLOR_INPUT_BG,
            fg=COLOR_TEXT,
            bd=1,
            relief=tk.FLAT,
            insertbackground=COLOR_TEXT,
        )
        self.folder_ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        browse_btn = tk.Button(
            folder_frame,
            text="Browse...",
            font=("Segoe UI", 9),
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT,
            activeforeground=COLOR_TEXT,
            bd=1,
            relief=tk.FLAT,
            command=self.browse_folder,
        )
        browse_btn.pack(side=tk.RIGHT, ipadx=10)

        # Options frame
        opts_frame = tk.Frame(self.content_frame, bg=COLOR_BG)
        opts_frame.pack(fill=tk.X, pady=(0, 25))

        cb_path = tk.Checkbutton(
            opts_frame,
            text="Add INTHON to User PATH environment variable",
            variable=self.add_to_path,
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT,
            selectcolor=COLOR_CARD,
        )
        cb_path.pack(anchor=tk.W, pady=3)

        cb_assoc = tk.Checkbutton(
            opts_frame,
            text="Associate .inth files with INTHON runner",
            variable=self.associate_files,
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT,
            selectcolor=COLOR_CARD,
        )
        cb_assoc.pack(anchor=tk.W, pady=3)

        cb_short = tk.Checkbutton(
            opts_frame,
            text="Create Start Menu shortcuts",
            variable=self.create_shortcuts,
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT,
            selectcolor=COLOR_CARD,
        )
        cb_short.pack(anchor=tk.W, pady=3)

        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        install_btn = tk.Button(
            btn_frame,
            text="Install Now",
            font=("Segoe UI Semibold", 11),
            bg=COLOR_ACCENT,
            fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground=COLOR_TEXT,
            bd=0,
            cursor="hand2",
            command=self.start_installation,
        )
        install_btn.pack(side=tk.RIGHT, ipadx=20, ipady=6)

        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            font=("Segoe UI", 10),
            bg=COLOR_BG,
            fg=COLOR_SUBTEXT,
            activebackground=COLOR_BG,
            activeforeground=COLOR_TEXT,
            bd=0,
            cursor="hand2",
            command=self.on_close,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=10, ipady=6)

    def browse_folder(self):
        selected = filedialog.askdirectory(
            title="Select Installation Folder", initialdir=self.install_dir.get()
        )
        if selected:
            # Normalize to Windows backslashes
            self.install_dir.set(os.path.normpath(selected))

    def start_installation(self):
        target = self.install_dir.get().strip()
        if not target:
            messagebox.showerror("Error", "Installation directory cannot be empty.")
            return

        self.install_in_progress = True
        self.show_progress_page()

        # Start copy and setup in a separate thread to keep GUI responsive
        threading.Thread(
            target=self.run_install_task, args=(target,), daemon=True
        ).start()

    def show_progress_page(self):
        self.clear_content()

        # Title
        title_lbl = tk.Label(
            self.content_frame,
            text="Installing INTHON...",
            font=("Segoe UI Semibold", 18),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 20))

        # Progress bar container
        pb_container = tk.Frame(self.content_frame, bg=COLOR_BORDER, height=12)
        pb_container.pack(fill=tk.X, pady=(0, 15))
        pb_container.pack_propagate(False)

        self.pb_fill = tk.Frame(pb_container, bg=COLOR_ACCENT, width=0, height=12)
        self.pb_fill.pack(side=tk.LEFT, fill=tk.Y)

        # Status log text
        self.log_txt = tk.Text(
            self.content_frame,
            font=("Consolas", 9),
            bg=COLOR_INPUT_BG,
            fg=COLOR_SUBTEXT,
            bd=1,
            relief=tk.SOLID,
            state=tk.DISABLED,
            highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_BORDER,
        )
        self.log_txt.pack(fill=tk.BOTH, expand=True)

    def log(self, message):
        self.log_txt.config(state=tk.NORMAL)
        self.log_txt.insert(tk.END, f"{message}\n")
        self.log_txt.see(tk.END)
        self.log_txt.config(state=tk.DISABLED)
        self.update_idletasks()

    def set_progress(self, percent):
        width = self.content_frame.winfo_width() - 40  # Estimate width minus pad
        if width < 100:
            width = 400
        fill_width = int(width * (percent / 100.0))
        self.pb_fill.config(width=fill_width)
        self.update_idletasks()

    def run_install_task(self, target_dir):
        try:
            self.set_progress(10)
            self.log("Initializing setup...")
            time.sleep(0.5)

            # 1. Create Directories
            self.set_progress(20)
            self.log(f"Creating directory: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            time.sleep(0.2)

            # 2. Extract and Copy Payload Files
            self.set_progress(40)
            self.log("Copying executable files...")

            files_to_copy = ["inthon.exe", "uninstall.exe", "inthon.toml"]
            for f in files_to_copy:
                src = get_resource_path(f)
                dst = os.path.join(target_dir, f)
                self.log(f"  Copying {f}...")
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                else:
                    # Fallback for dev mode
                    self.log(f"[Warning] Source file {f} not found in resources.")
                    # In a real build, we raise an error if critical files are missing
                    if f in ["inthon.exe", "uninstall.exe"]:
                        raise FileNotFoundError(f"Critical source file {f} missing.")
                time.sleep(0.2)

            # 3. Add to PATH
            self.set_progress(60)
            if self.add_to_path.get():
                self.log("Adding installation directory to user PATH...")
                self.update_env_path(target_dir)
                time.sleep(0.2)
            else:
                self.log("Skipping PATH registration.")

            # 4. Associate Files
            self.set_progress(75)
            if self.associate_files.get():
                self.log("Registering .inth file association in registry...")
                self.register_file_association(target_dir)
                time.sleep(0.2)
            else:
                self.log("Skipping file association.")

            # 5. Create Start Menu Shortcuts
            self.set_progress(85)
            if self.create_shortcuts.get():
                self.log("Creating Start Menu shortcuts...")
                self.register_shortcuts(target_dir)
                time.sleep(0.2)
            else:
                self.log("Skipping Start Menu shortcuts.")

            # 6. Register Uninstaller in Apps & Features
            self.set_progress(95)
            self.log("Registering uninstaller information in Windows registry...")
            self.register_uninstaller_key(target_dir)
            time.sleep(0.2)

            # Finalize
            self.set_progress(100)
            self.log("Installation completed successfully!")
            time.sleep(0.5)

            # Show Success Page
            self.after(100, self.show_success_page)

        except Exception as e:
            self.log(f"\n[ERROR] Setup failed: {e}")
            messagebox.showerror(
                "Installation Failed", f"An error occurred during setup:\n{e}"
            )
            self.install_in_progress = False
            self.show_welcome_page()

    def update_env_path(self, target_dir):
        # Open HKEY_CURRENT_USER\Environment
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS
            )
        except Exception as e:
            self.log(f"  [Error] Failed to open registry Environment key: {e}")
            return

        try:
            path_val, val_type = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            path_val, val_type = "", winreg.REG_EXPAND_SZ

        # Normalize paths for clean checking
        norm_target = os.path.normpath(target_dir)
        paths = [os.path.normpath(p.strip()) for p in path_val.split(";") if p.strip()]

        if norm_target not in paths:
            paths.append(norm_target)
            new_path_val = ";".join(paths)
            winreg.SetValueEx(key, "Path", 0, val_type, new_path_val)
            self.log("  PATH updated successfully.")

            # Broadcast system update
            self.log("  Broadcasting environment update to Windows...")
            self.broadcast_setting_change()
        else:
            self.log("  PATH already contains the installation directory.")
        winreg.CloseKey(key)

    def broadcast_setting_change(self):
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002

        # SendMessageTimeoutW
        result = ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            1000,
            ctypes.byref(ctypes.c_size_t()),
        )
        self.log(f"  Broadcast complete. Result: {result}")

    def register_file_association(self, target_dir):
        exe_path = os.path.join(target_dir, "inthon.exe")
        try:
            # 1. Write HKEY_CURRENT_USER\Software\Classes\.inth = Inthon.File
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\.inth"
            ) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Inthon.File")

            # 2. Write HKEY_CURRENT_USER\Software\Classes\Inthon.File = Inthon Source File
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\Inthon.File"
            ) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Inthon Source File")

            # 3. Write HKEY_CURRENT_USER\Software\Classes\Inthon.File\DefaultIcon = "inthon.exe,0"
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\Inthon.File\DefaultIcon"
            ) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}",0')

            # 4. Write HKEY_CURRENT_USER\Software\Classes\Inthon.File\shell\open\command = "inthon.exe" run "%1"
            with winreg.CreateKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Classes\Inthon.File\shell\open\command",
            ) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" run "%1"')
            self.log("  Registry file associations created.")
        except Exception as e:
            self.log(f"  [Warning] File association failed: {e}")

    def register_shortcuts(self, target_dir):
        try:
            appdata = os.environ.get("APPDATA")
            if not appdata:
                self.log(
                    "  [Warning] APPDATA environment variable not found, skipping shortcuts."
                )
                return

            programs_dir = os.path.join(
                appdata, r"Microsoft\Windows\Start Menu\Programs"
            )
            inthon_shortcuts_dir = os.path.join(programs_dir, "Inthon")
            os.makedirs(inthon_shortcuts_dir, exist_ok=True)

            exe_path = os.path.join(target_dir, "inthon.exe")
            uninst_path = os.path.join(target_dir, "uninstall.exe")

            # Write PowerShell script to create the shortcuts
            self.create_powershell_shortcut(
                exe_path,
                os.path.join(inthon_shortcuts_dir, "Inthon CLI.lnk"),
                "INTHON CLI Compiler & Interpreter",
            )
            self.create_powershell_shortcut(
                uninst_path,
                os.path.join(inthon_shortcuts_dir, "Uninstall Inthon.lnk"),
                "Uninstall INTHON",
            )
            self.log("  Start Menu shortcuts created.")
        except Exception as e:
            self.log(f"  [Warning] Shortcuts creation failed: {e}")

    def create_powershell_shortcut(self, target, lnk_path, desc):
        # Escaping for powershell string
        target_esc = target.replace("'", "''")
        lnk_esc = lnk_path.replace("'", "''")
        desc_esc = desc.replace("'", "''")

        cmd = (
            f"$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut('{lnk_esc}'); "
            f"$Shortcut.TargetPath = '{target_esc}'; "
            f"$Shortcut.Description = '{desc_esc}'; "
            f"$Shortcut.Save()"
        )
        import subprocess

        # Run PowerShell silently
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
        )

    def register_uninstaller_key(self, target_dir):
        try:
            uninst_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Inthon"
            uninst_exe = os.path.join(target_dir, "uninstall.exe")
            inthon_exe = os.path.join(target_dir, "inthon.exe")

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, uninst_key) as key:
                winreg.SetValueEx(
                    key,
                    "DisplayName",
                    0,
                    winreg.REG_SZ,
                    f"Inthon Language (v{VERSION})",
                )
                winreg.SetValueEx(
                    key, "UninstallString", 0, winreg.REG_SZ, f'"{uninst_exe}"'
                )
                winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, target_dir)
                winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, VERSION)
                winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "HarvaTechs")
                winreg.SetValueEx(
                    key, "DisplayIcon", 0, winreg.REG_SZ, f'"{inthon_exe}"'
                )
                winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            self.log("  Registered uninstaller in Windows database.")
        except Exception as e:
            self.log(f"  [Warning] Registering uninstaller failed: {e}")

    def show_success_page(self):
        self.clear_content()

        # Title
        title_lbl = tk.Label(
            self.content_frame,
            text="Installation Completed!",
            font=("Segoe UI Semibold", 18),
            fg=COLOR_SUCCESS,
            bg=COLOR_BG,
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 10))

        success_lbl = tk.Label(
            self.content_frame,
            text="INTHON v0.1.0 has been successfully installed on your computer.",
            font=("Segoe UI", 10, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        success_lbl.pack(anchor=tk.W, pady=(0, 15))

        info_lbl = tk.Label(
            self.content_frame,
            text="To verify the installation and run programs:\n"
            "1. Open a new Command Prompt or PowerShell terminal.\n"
            "2. Run: inthon --help\n"
            "3. Run: inthon run <file.inth>",
            font=("Segoe UI", 10),
            fg=COLOR_SUBTEXT,
            bg=COLOR_BG,
            justify=tk.LEFT,
        )
        info_lbl.pack(anchor=tk.W, pady=(0, 30))

        # Buttons
        btn_frame = tk.Frame(self.content_frame, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        finish_btn = tk.Button(
            btn_frame,
            text="Finish",
            font=("Segoe UI Semibold", 11),
            bg=COLOR_ACCENT,
            fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground=COLOR_TEXT,
            bd=0,
            cursor="hand2",
            command=self.exit_installer,
        )
        finish_btn.pack(side=tk.RIGHT, ipadx=25, ipady=6)

    def exit_installer(self):
        self.install_in_progress = False
        self.destroy()

    def on_close(self):
        if self.install_in_progress:
            if not messagebox.askyesno(
                "Cancel Setup",
                "Installation is in progress. Are you sure you want to cancel?",
            ):
                return
        self.destroy()


if __name__ == "__main__":
    app = InthonInstaller()
    app.mainloop()
