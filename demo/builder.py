import json
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from compiler import Compiler


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "cfg" / "configuration.json"
DEFAULT_CONFIG_PATH = ROOT / "cfg" / "default_configuration.json"
BACKGROUND_PATH = ROOT.parent / "src" / "img" / "builder_backgrounds" / "1.jpg"


class Builder:
    def __init__(self, master):
        self.master = master
        self.master.title("PySilon Builder")
        self.master.geometry("760x560")
        self.master.resizable(False, False)

        self.config = self.load_config()
        self.background = None

        self.canvas = tk.Canvas(master, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.draw_background()
        self.draw_form()

    def load_config(self):
        if not CONFIG_PATH.exists():
            shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def save_config(self):
        self.config["supabase_url"] = self.supabase_url_var.get().strip()
        self.config["supabase_anon_key"] = self.supabase_anon_key_var.get().strip()
        self.config["install_dir"] = self.install_dir_var.get().strip() or "C:\\Program Files (x86)\\Monitoring"
        self.config["executable_name"] = self.executable_name_var.get().strip() or "client"
        self.config["state_dir"] = "./state"
        self.config["features"] = {
            "cpu": self.cpu_var.get(),
            "ram": self.ram_var.get(),
            "disk": self.disk_var.get(),
        }
        CONFIG_PATH.write_text(json.dumps(self.config, indent=4), encoding="utf-8")

    def draw_background(self):
        try:
            from PIL import Image, ImageTk

            image = Image.open(BACKGROUND_PATH).resize((760, 560))
            self.background = ImageTk.PhotoImage(image)
            self.canvas.create_image(0, 0, image=self.background, anchor=tk.NW)
        except Exception:
            self.canvas.configure(bg="#101216")

    def add_label(self, text, x, y):
        label = tk.Label(
            self.canvas,
            text=text,
            bg="#101216",
            fg="white",
            font=("Consolas", 11),
            anchor="w",
        )
        self.canvas.create_window(x, y, window=label, anchor=tk.W)

    def add_entry(self, variable, x, y, width=52, show=None):
        entry = tk.Entry(
            self.canvas,
            textvariable=variable,
            width=width,
            show=show,
            font=("Consolas", 10),
        )
        self.canvas.create_window(x, y, window=entry, anchor=tk.W)
        return entry

    def draw_form(self):
        panel = tk.Frame(self.canvas, bg="#101216", padx=22, pady=22)
        self.canvas.create_window(380, 280, window=panel, anchor=tk.CENTER, width=640, height=470)

        title = tk.Label(
            panel,
            text="PySilon Builder",
            bg="#101216",
            fg="white",
            font=("Consolas", 18, "bold"),
        )
        title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

        self.supabase_url_var = tk.StringVar(value=self.config.get("supabase_url", ""))
        self.supabase_anon_key_var = tk.StringVar(value=self.config.get("supabase_anon_key", ""))
        self.install_dir_var = tk.StringVar(value=self.config.get("install_dir", "C:\\Program Files (x86)\\Monitoring"))
        self.executable_name_var = tk.StringVar(value=self.config.get("executable_name", "client"))

        self.cpu_var = tk.BooleanVar(value=self.config.get("features", {}).get("cpu", True))
        self.ram_var = tk.BooleanVar(value=self.config.get("features", {}).get("ram", True))
        self.disk_var = tk.BooleanVar(value=self.config.get("features", {}).get("disk", True))

        labels = [
            ("Supabase URL", self.supabase_url_var, None),
            ("Supabase Anon Key", self.supabase_anon_key_var, "*"),
            ("Install Dir", self.install_dir_var, None),
            ("Exe Name", self.executable_name_var, None),
        ]

        for row, (label_text, variable, show) in enumerate(labels, start=1):
            label = tk.Label(panel, text=label_text, bg="#101216", fg="white", font=("Consolas", 11), anchor="w")
            label.grid(row=row, column=0, sticky="w", pady=7)
            entry = tk.Entry(panel, textvariable=variable, show=show, width=48, font=("Consolas", 10))
            entry.grid(row=row, column=1, sticky="ew", pady=7)

        feature_title = tk.Label(
            panel,
            text="Features",
            bg="#101216",
            fg="white",
            font=("Consolas", 12, "bold"),
        )
        feature_title.grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 8))

        features = [
            ("CPU usage", self.cpu_var),
            ("RAM usage", self.ram_var),
            ("Disk usage", self.disk_var),
        ]
        for index, (text, variable) in enumerate(features, start=6):
            checkbox = tk.Checkbutton(
                panel,
                text=text,
                variable=variable,
                bg="#101216",
                fg="white",
                selectcolor="#101216",
                activebackground="#101216",
                activeforeground="white",
                font=("Consolas", 11),
            )
            checkbox.grid(row=index, column=0, columnspan=2, sticky="w", pady=2)

        self.status_var = tk.StringVar(value="Ready.")
        status = tk.Label(
            panel,
            textvariable=self.status_var,
            bg="#101216",
            fg="#d7e8ff",
            font=("Consolas", 10),
            anchor="w",
            wraplength=580,
            justify=tk.LEFT,
        )
        status.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(20, 10))

        build_button = tk.Button(
            panel,
            text="Build",
            command=self.start_build,
            font=("Consolas", 12, "bold"),
            cursor="hand2",
        )
        build_button.grid(row=10, column=1, sticky="e", pady=(8, 0))

        panel.columnconfigure(1, weight=1)

    def validate_config(self):
        if not self.supabase_url_var.get().strip():
            raise ValueError("Supabase URL is required.")
        if not self.supabase_anon_key_var.get().strip():
            raise ValueError("Supabase anon key is required.")
        if not any([self.cpu_var.get(), self.ram_var.get(), self.disk_var.get()]):
            raise ValueError("Select at least one feature.")

    def start_build(self):
        try:
            self.validate_config()
            self.save_config()
        except Exception as exc:
            messagebox.showerror("Build configuration", str(exc))
            return

        self.status_var.set("Building client...")
        thread = threading.Thread(target=self.build, daemon=True)
        thread.start()

    def build(self):
        try:
            result = Compiler(ROOT).build(build_exe=True)
            if result["ok"]:
                message = f"Build finished: {result['exe']}"
            else:
                message = f"{result['reason']} Generated source: {result['source']}"
            self.master.after(0, lambda: self.status_var.set(message))
        except Exception as exc:
            message = f"Build failed: {type(exc).__name__}: {exc}"
            self.master.after(0, lambda: self.status_var.set(message))


def main():
    root = tk.Tk()
    Builder(root)
    root.mainloop()


if __name__ == "__main__":
    main()
