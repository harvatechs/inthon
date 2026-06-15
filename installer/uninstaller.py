import os
import sys
import shutil
import winreg
import ctypes
import threading
import time
import tempfile
import subprocess
import tkinter as tk
from tkinter import messagebox

# Theme colors
COLOR_BG = "#121214"
COLOR_CARD = "#1E1E22"
COLOR_TEXT = "#F3F4F6"
COLOR_SUBTEXT = "#9CA3AF"
COLOR_ACCENT = "#EF4444"  # Red for uninstall
COLOR_ACCENT_HOVER = "#F87171"
COLOR_BORDER = "#2E2E38"
COLOR_SUCCESS = "#10B981"
COLOR_GRADIENT_START = "#B91C1C"  # Dark red gradient
COLOR_GRADIENT_END = "#450A0A"
COLOR_INPUT_BG = "#26262B"

VERSION = "0.1.0"


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


class InthonUninstaller(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("INTHON Language Uninstall")
        self.geometry("680x420")
        self.resizable(False, False)
        self.configure(bg=COLOR_BG)

        # Set window icon (if available)
        try:
            icon_path = get_resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        # Center the window
        self.center_window()

        # Determine installation directory dynamically from executable location
        self.install_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.uninstall_in_progress = False

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
            text="Uninstall",
            font=("Segoe UI", 14),
            fill=COLOR_SUBTEXT,
            anchor=tk.CENTER,
        )
        self.sidebar.create_text(
            110,
            380,
            text="HarVa DeepLabs",
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
            text="Uninstall INTHON v0.1.0",
            font=("Segoe UI Semibold", 18),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 5))

        desc_lbl = tk.Label(
            self.content_frame,
            text="This wizard will completely remove INTHON from your computer.",
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
            text=" Location to Remove ",
            font=("Segoe UI Semibold", 9),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=10,
        )
        folder_frame.pack(fill=tk.X, pady=(0, 25))
        folder_frame.config(
            highlightbackground=COLOR_BORDER, highlightcolor=COLOR_BORDER
        )

        folder_lbl = tk.Label(
            folder_frame,
            text=self.install_dir,
            font=("Consolas", 10),
            bg=COLOR_BG,
            fg=COLOR_TEXT,
            anchor=tk.W,
            justify=tk.LEFT,
        )
        folder_lbl.pack(fill=tk.X)

        warning_lbl = tk.Label(
            self.content_frame,
            text="Warning: Uninstallation will clean up the registry settings, remove INTHON from your PATH, and delete all files in the directory above.",
            font=("Segoe UI", 10),
            fg=COLOR_ACCENT_HOVER,
            bg=COLOR_BG,
            wraplength=400,
            justify=tk.LEFT,
        )
        warning_lbl.pack(anchor=tk.W, pady=(0, 25))

        # Button frame
        btn_frame = tk.Frame(self.content_frame, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        uninstall_btn = tk.Button(
            btn_frame,
            text="Uninstall Now",
            font=("Segoe UI Semibold", 11),
            bg=COLOR_ACCENT,
            fg=COLOR_TEXT,
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground=COLOR_TEXT,
            bd=0,
            cursor="hand2",
            command=self.start_uninstallation,
        )
        uninstall_btn.pack(side=tk.RIGHT, ipadx=20, ipady=6)

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

    def start_uninstallation(self):
        self.uninstall_in_progress = True
        self.show_progress_page()

        # Start cleanup in a separate thread
        threading.Thread(target=self.run_uninstall_task, daemon=True).start()

    def show_progress_page(self):
        self.clear_content()

        # Title
        title_lbl = tk.Label(
            self.content_frame,
            text="Uninstalling INTHON...",
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
        width = self.content_frame.winfo_width() - 40
        if width < 100:
            width = 400
        fill_width = int(width * (percent / 100.0))
        self.pb_fill.config(width=fill_width)
        self.update_idletasks()

    def run_uninstall_task(self):
        try:
            self.set_progress(10)
            self.log("Initializing uninstaller...")
            time.sleep(0.5)

            # 1. Unregister Start Menu Shortcuts
            self.set_progress(25)
            self.log("Removing Start Menu shortcuts...")
            self.remove_shortcuts()
            time.sleep(0.2)

            # 2. Remove File Associations from Registry
            self.set_progress(45)
            self.log("Removing registry file associations...")
            self.remove_file_associations()
            time.sleep(0.2)

            # 3. Remove PATH Variable Entry
            self.set_progress(65)
            self.log("Removing directory from user PATH environment variable...")
            self.remove_from_path(self.install_dir)
            time.sleep(0.2)

            # 4. Remove Apps & Features Entry
            self.set_progress(80)
            self.log("Removing uninstaller registry database entry...")
            self.unregister_uninstaller_key()
            time.sleep(0.2)

            # 5. Delete payload files (except uninstall.exe itself)
            self.set_progress(95)
            self.log("Deleting files from installation directory...")
            self.delete_install_files()
            time.sleep(0.2)

            self.set_progress(100)
            self.log("Uninstallation steps finished successfully!")
            time.sleep(0.5)

            # Show Success Page
            self.after(100, self.show_success_page)

        except Exception as e:
            self.log(f"\n[ERROR] Uninstall failed: {e}")
            messagebox.showerror(
                "Uninstall Failed", f"An error occurred during uninstallation:\n{e}"
            )
            self.uninstall_in_progress = False
            self.show_welcome_page()

    def remove_shortcuts(self):
        try:
            appdata = os.environ.get("APPDATA")
            if not appdata:
                return
            shortcuts_dir = os.path.join(
                appdata, r"Microsoft\Windows\Start Menu\Programs\Inthon"
            )
            if os.path.exists(shortcuts_dir):
                shutil.rmtree(shortcuts_dir, ignore_errors=True)
                self.log("  Start Menu shortcuts removed.")
        except Exception as e:
            self.log(f"  [Warning] Failed to delete shortcuts: {e}")

    def delete_key_recursive(self, root, subkey):
        try:
            key = winreg.OpenKey(root, subkey, 0, winreg.KEY_ALL_ACCESS)
        except FileNotFoundError:
            return
        try:
            info = winreg.QueryInfoKey(key)
            for _ in range(info[0]):
                name = winreg.EnumKey(key, 0)
                self.delete_key_recursive(key, name)
        finally:
            winreg.CloseKey(key)
        winreg.DeleteKey(root, subkey)

    def remove_file_associations(self):
        try:
            self.delete_key_recursive(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\.inth"
            )
            self.log("  Removed registry key: HKCU\\Software\\Classes\\.inth")
        except Exception as e:
            self.log(
                f"  [Warning] Failed to delete HKCU\\Software\\Classes\\.inth: {e}"
            )

        try:
            self.delete_key_recursive(
                winreg.HKEY_CURRENT_USER, r"Software\Classes\Inthon.File"
            )
            self.log("  Removed registry key: HKCU\\Software\\Classes\\Inthon.File")
        except Exception as e:
            self.log(
                f"  [Warning] Failed to delete HKCU\\Software\\Classes\\Inthon.File: {e}"
            )

    def remove_from_path(self, target_dir):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS
            )
        except Exception as e:
            self.log(f"  [Warning] Failed to open registry Environment key: {e}")
            return

        try:
            path_val, val_type = winreg.QueryValueEx(key, "Path")
            norm_target = os.path.normpath(target_dir)
            paths = [
                os.path.normpath(p.strip()) for p in path_val.split(";") if p.strip()
            ]

            if norm_target in paths:
                paths.remove(norm_target)
                new_path_val = ";".join(paths)
                winreg.SetValueEx(key, "Path", 0, val_type, new_path_val)
                self.log("  PATH variable updated.")

                # Broadcast env change
                self.broadcast_setting_change()
            else:
                self.log("  PATH variable did not contain this installation directory.")
        except FileNotFoundError:
            self.log("  PATH variable not found.")
        except Exception as e:
            self.log(f"  [Warning] Failed to edit PATH environment: {e}")
        finally:
            winreg.CloseKey(key)

    def broadcast_setting_change(self):
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002

        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST,
            WM_SETTINGCHANGE,
            0,
            "Environment",
            SMTO_ABORTIFHUNG,
            1000,
            ctypes.byref(ctypes.c_size_t()),
        )

    def unregister_uninstaller_key(self):
        try:
            uninst_key = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Inthon"
            self.delete_key_recursive(winreg.HKEY_CURRENT_USER, uninst_key)
            self.log("  Removed from Windows Apps list.")
        except Exception as e:
            self.log(f"  [Warning] Failed to remove uninstall registry key: {e}")

    def delete_install_files(self):
        # Delete files in install_dir, except uninstall.exe itself
        try:
            for item in os.listdir(self.install_dir):
                item_path = os.path.join(self.install_dir, item)
                if os.path.isfile(item_path):
                    if item.lower() != "uninstall.exe":
                        os.remove(item_path)
                        self.log(f"  Deleted file: {item}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                    self.log(f"  Deleted directory: {item}")
        except Exception as e:
            self.log(f"  [Warning] File deletion warning: {e}")

    def show_success_page(self):
        self.clear_content()

        # Title
        title_lbl = tk.Label(
            self.content_frame,
            text="Uninstall Completed",
            font=("Segoe UI Semibold", 18),
            fg=COLOR_SUCCESS,
            bg=COLOR_BG,
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 10))

        success_lbl = tk.Label(
            self.content_frame,
            text="INTHON has been successfully removed from your computer.",
            font=("Segoe UI", 10, "bold"),
            fg=COLOR_TEXT,
            bg=COLOR_BG,
        )
        success_lbl.pack(anchor=tk.W, pady=(0, 20))

        info_lbl = tk.Label(
            self.content_frame,
            text="Click Finish to close this wizard. A final self-clean script will complete the folder cleanup after the window closes.",
            font=("Segoe UI", 10),
            fg=COLOR_SUBTEXT,
            bg=COLOR_BG,
            wraplength=400,
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
            command=self.finish_and_cleanup,
        )
        finish_btn.pack(side=tk.RIGHT, ipadx=25, ipady=6)

    def finish_and_cleanup(self):
        # Write batch script to self-delete the uninstall.exe and the directory
        uninstall_exe = os.path.abspath(sys.argv[0])
        temp_dir = tempfile.gettempdir()
        bat_path = os.path.join(temp_dir, "cleanup_inthon.bat")

        # Command to wait, delete uninstall.exe, delete directory, and delete self
        bat_content = f"""@echo off
timeout /t 1 /nobreak > nul
del /f /q "{uninstall_exe}"
rmdir /s /q "{self.install_dir}"
del /f /q "%~f0"
"""
        try:
            with open(bat_path, "w", encoding="ascii") as f:
                f.write(bat_content)

            # Spawn cleanup process asynchronously
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )
        except Exception:
            pass

        # Exit Immediately
        self.destroy()

    def on_close(self):
        if self.uninstall_in_progress:
            if not messagebox.askyesno(
                "Cancel Uninstall",
                "Uninstallation is in progress. Are you sure you want to cancel?",
            ):
                return
        self.destroy()


if __name__ == "__main__":
    app = InthonUninstaller()
    app.mainloop()
