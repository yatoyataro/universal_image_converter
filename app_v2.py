import json
import os
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

import ui_palette
from converter_core import ConvertOptions, convert_files, describe_error

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _DND_AVAILABLE = True
except ImportError:  # drag-and-drop stays optional
    _DND_AVAILABLE = False

SUPPORTED_INPUT_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
APP_VERSION = "1.1.0"
ERROR_REPORT_PATH = os.path.join(tempfile.gettempdir(), "universal_image_converter_errors.txt")

# Default appearance; _load_settings() overrides this from the saved
# preference. All widget colors are (light, dark) tuples from ui_palette.
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ImageConverterApp(
    ctk.CTk,
    *([TkinterDnD.DnDWrapper] if _DND_AVAILABLE else []),
):
    def __init__(self):
        super().__init__()
        
        self.title("Universal Image Converter")
        self.geometry("1100x700")
        # Small enough to snap to half of a 1440p-wide display; the scrollable
        # left panel keeps every control reachable below this.
        self.minsize(720, 500)
        self.resizable(True, True)
        self.configure(fg_color=ui_palette.BG_WINDOW)
        
        self.selected_files = []
        self.output_directory = ""
        self.preview_empty_state_frame = None
        self.is_converting = False
        self.remove_buttons = []
        self.cancel_event = threading.Event()
        self._preview_generation = 0
        self._preview_cards = {}
        self._recent_dirs: list[str] = []
        # Thread-safe bridge: workers put (callable, args) here and the
        # main-thread poller executes them. Calling tkinter from worker
        # threads directly is unsafe (RuntimeError: main thread is not in
        # main loop) -- this replaces all cross-thread after() calls.
        self._ui_queue: queue.Queue = queue.Queue()
        self.after(50, self._drain_ui_queue)

        # L14: keyboard shortcuts.
        self.bind("<Return>", self._on_enter_key)
        self.bind("<Control-o>", lambda _event: self.select_files())
        self.bind("<Escape>", self._on_escape_key)

        self.create_layout()

        # Must run after create_layout: these touch widgets.
        self._setup_drag_and_drop()
        self._load_settings()

    def create_layout(self):
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=330)
        self.grid_columnconfigure(1, weight=1)

        # --- Top bar: app name + Settings / Help buttons ---
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 4))
        self.top_bar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.top_bar,
            text="Universal Image Converter",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=ui_palette.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")

        menu_btn = {
            "height": 28, "width": 92, "corner_radius": 8, "fg_color": "transparent",
            "border_width": 1, "border_color": ui_palette.BORDER_INPUT,
            "font": ctk.CTkFont(size=12),
        }
        self.btn_settings = ctk.CTkButton(self.top_bar, text="Settings", command=self._open_settings_menu, **menu_btn)
        self.btn_settings.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.btn_help = ctk.CTkButton(self.top_bar, text="Help", command=self._open_help_menu, **menu_btn)
        self.btn_help.grid(row=0, column=2, sticky="e")

        self._setup_menus()

        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=18, pady=(4, 18))
        self.workspace.grid_rowconfigure(0, weight=1)
        self.workspace.grid_columnconfigure(0, weight=0, minsize=330)
        self.workspace.grid_columnconfigure(1, weight=1)

        # --- Left Panel: Controls ---
        # Row 0 scrolls (all configuration); row 1 is a pinned action bar so
        # progress/status/Convert/Stop stay reachable at any window size.
        self.left_frame = ctk.CTkFrame(self.workspace, width=330, corner_radius=24, fg_color=ui_palette.BG_PANEL, border_width=1, border_color=ui_palette.BORDER_PANEL)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=0)
        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=0)

        self.left_scroll = ctk.CTkScrollableFrame(
            self.left_frame,
            fg_color=ui_palette.BG_PANEL,
            corner_radius=0,
            border_width=0,
        )
        self.left_scroll.grid(row=0, column=0, sticky="nsew")
        self.left_scroll.grid_columnconfigure(0, weight=1)

        self.left_content = ctk.CTkFrame(self.left_scroll, fg_color="transparent")
        self.left_content.grid(row=0, column=0, sticky="nsew", padx=22, pady=22)
        self.left_content.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self.left_content, text="Converter", font=ctk.CTkFont(size=25, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", pady=(2, 8))
        self.subtitle_label = ctk.CTkLabel(
            self.left_content,
            text="Select, preview, remove, and convert",
            text_color=ui_palette.TEXT_MUTED,
            font=ctk.CTkFont(size=11)
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(0, 18))

        self.controls_card = ctk.CTkFrame(self.left_content, fg_color=ui_palette.BG_CARD, corner_radius=18, border_width=1, border_color=ui_palette.BORDER_CARD)
        self.controls_card.grid(row=2, column=0, sticky="nsew")
        self.controls_card.grid_columnconfigure(0, weight=1)

        self.controls_inner = ctk.CTkFrame(self.controls_card, fg_color="transparent")
        self.controls_inner.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.controls_inner.grid_columnconfigure(0, weight=1)

        # --- Options card (Step 4 features) ---
        self.options_card = ctk.CTkFrame(self.left_content, fg_color=ui_palette.BG_CARD, corner_radius=18, border_width=1, border_color=ui_palette.BORDER_CARD)
        self.options_card.grid(row=3, column=0, sticky="nsew", pady=(14, 0))
        self.options_card.grid_columnconfigure(0, weight=1)

        options_inner = ctk.CTkFrame(self.options_card, fg_color="transparent")
        options_inner.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        options_inner.grid_columnconfigure(1, weight=1)

        self.quality_value_label = ctk.CTkLabel(options_inner, text="Quality: 90", font=ctk.CTkFont(size=12))
        self.quality_value_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self.quality_slider = ctk.CTkSlider(options_inner, from_=1, to=100, number_of_steps=99, command=self._on_quality_change)
        self.quality_slider.set(90)
        self.quality_slider.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self.chk_lossless = ctk.CTkCheckBox(options_inner, text="Lossless WebP", checkbox_width=18, checkbox_height=18)
        self.chk_lossless.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))

        resize_row = ctk.CTkFrame(options_inner, fg_color="transparent")
        resize_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.chk_resize = ctk.CTkCheckBox(resize_row, text="Resize max", checkbox_width=18, checkbox_height=18, command=self._on_resize_toggle)
        self.chk_resize.pack(side="left")
        self.entry_max_dim = ctk.CTkEntry(resize_row, width=58, placeholder_text="1920")
        self.entry_max_dim.insert(0, "1920")
        self.entry_max_dim.configure(state="disabled")
        self.entry_max_dim.pack(side="left", padx=(10, 4))
        ctk.CTkLabel(resize_row, text="px", text_color=ui_palette.TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left")

        self.chk_metadata = ctk.CTkCheckBox(options_inner, text="Keep EXIF metadata", checkbox_width=18, checkbox_height=18)
        self.chk_metadata.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.chk_overwrite = ctk.CTkCheckBox(options_inner, text="Overwrite existing files", checkbox_width=18, checkbox_height=18)
        self.chk_overwrite.grid(row=5, column=0, columnspan=2, sticky="w")

        # Select Files
        self.btn_select = ctk.CTkButton(self.controls_inner, text="Select Images", command=self.select_files, fg_color=ui_palette.ACCENT, hover_color=ui_palette.ACCENT_HOVER, height=40)
        self.btn_select.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        
        self.lbl_count = ctk.CTkLabel(self.controls_inner, text="0 files selected", text_color=ui_palette.TEXT_FAINT)
        self.lbl_count.grid(row=1, column=0, pady=(0, 10), sticky="w")

        # Select Output Directory
        self.btn_out_dir = ctk.CTkButton(self.controls_inner, text="Choose Output Folder", command=self.select_output_dir, fg_color="transparent", border_width=1, border_color=ui_palette.BORDER_INPUT, text_color=("gray10", "gray90"), height=40)
        self.btn_out_dir.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        
        self.lbl_out_dir = ctk.CTkLabel(self.controls_inner, text="Default: Source Folder", text_color=ui_palette.TEXT_FAINT, font=ctk.CTkFont(size=11))
        self.lbl_out_dir.grid(row=3, column=0, pady=(0, 4), sticky="w")

        # Recently used output folders (persisted in settings)
        self.recent_menu = ctk.CTkOptionMenu(
            self.controls_inner,
            values=["Recent folders"],
            command=self._on_recent_dir_pick,
            height=32,
        )
        self.recent_menu.grid(row=4, column=0, pady=(0, 14), sticky="ew")

        # Target Format Selection
        self.format_label = ctk.CTkLabel(self.controls_inner, text="Target Format", font=ctk.CTkFont(weight="bold", size=13))
        self.format_label.grid(row=5, column=0, pady=(0, 10), sticky="w")
        
        self.target_format = ctk.StringVar(value="webp")
        self.target_format.trace_add("write", self.on_target_format_change)
        self.radio_webp = ctk.CTkRadioButton(self.controls_inner, text="WebP", variable=self.target_format, value="webp")
        self.radio_png = ctk.CTkRadioButton(self.controls_inner, text="PNG", variable=self.target_format, value="png")
        self.radio_jpg = ctk.CTkRadioButton(self.controls_inner, text="JPG (.jpg)", variable=self.target_format, value="jpg")
        
        self.radio_webp.grid(row=6, column=0, pady=(0, 6), sticky="w")
        self.radio_png.grid(row=7, column=0, pady=(0, 6), sticky="w")
        self.radio_jpg.grid(row=8, column=0, pady=(0, 12), sticky="w")

        # --- Pinned action bar (always visible, never scrolls) ---
        self.bottom_bar = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.bottom_bar.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 22))
        self.bottom_bar.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.bottom_bar)
        self.progress_bar.grid(row=0, column=0, pady=(0, 6), sticky="ew")
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(self.bottom_bar, text="Ready", text_color=ui_palette.TEXT_FAINT)
        self.lbl_status.grid(row=1, column=0, pady=(0, 8), sticky="w")

        self.btn_convert = ctk.CTkButton(self.bottom_bar, text="Start Conversion", command=self.start_conversion_thread, state="disabled", height=44, font=ctk.CTkFont(weight="bold"))
        self.btn_convert.grid(row=2, column=0, pady=(0, 0), sticky="ew")

        self.btn_cancel = ctk.CTkButton(
            self.bottom_bar,
            text="Stop",
            command=self.cancel_conversion,
            height=36,
            fg_color=ui_palette.DANGER,
            hover_color=ui_palette.DANGER_HOVER,
        )
        # Hidden until a conversion is running (M10).
        self.btn_cancel.grid(row=2, column=0, pady=(0, 0), sticky="ew")
        self.btn_cancel.grid_remove()

        # --- Right Panel: Image Preview ---
        self.right_frame = ctk.CTkFrame(self.workspace, fg_color=ui_palette.BG_PANEL_ALT, corner_radius=24, border_width=1, border_color=ui_palette.BORDER_PANEL)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.preview_shell = ctk.CTkFrame(self.right_frame, fg_color=ui_palette.BG_CARD, corner_radius=18, border_width=1, border_color=ui_palette.BORDER_CARD)
        self.preview_shell.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.preview_shell.grid_rowconfigure(1, weight=1)
        self.preview_shell.grid_columnconfigure(0, weight=1)

        self.preview_header = ctk.CTkFrame(self.preview_shell, fg_color="transparent")
        self.preview_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        self.preview_header.grid_columnconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(self.preview_header, text="Image Queue", font=ctk.CTkFont(size=20, weight="bold"))
        self.preview_label.grid(row=0, column=0, sticky="w")

        self.preview_meta_label = ctk.CTkLabel(self.preview_header, text="No images selected", text_color=ui_palette.TEXT_MUTED, font=ctk.CTkFont(size=11))
        self.preview_meta_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.preview_count_chip = ctk.CTkLabel(
            self.preview_header,
            text="0 items",
            width=84,
            height=28,
            corner_radius=999,
            fg_color=ui_palette.CHIP_BG,
            text_color=ui_palette.CHIP_TEXT,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.preview_count_chip.grid(row=0, column=1, rowspan=2, sticky="e")

        self.scrollable_frame = ctk.CTkScrollableFrame(self.preview_shell, fg_color=ui_palette.BG_CARD, corner_radius=0)
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.update_preview_scroll_state()

    # --- Top-bar menus (Settings / Help) ---

    def _setup_menus(self):
        self._appearance_var = tk.StringVar(
            value="Dark" if ctk.get_appearance_mode().lower() == "dark" else "Light")

        self._settings_menu = tk.Menu(self, tearoff=0)
        appearance_menu = tk.Menu(self._settings_menu, tearoff=0)
        appearance_menu.add_radiobutton(
            label="Dark", variable=self._appearance_var,
            command=lambda: self._set_appearance("dark"))
        appearance_menu.add_radiobutton(
            label="Light", variable=self._appearance_var,
            command=lambda: self._set_appearance("light"))
        self._settings_menu.add_cascade(label="Appearance", menu=appearance_menu)

        self._help_menu = tk.Menu(self, tearoff=0)
        self._help_menu.add_command(label="Report issue...", command=self._show_report_issue_dialog)
        self._help_menu.add_command(label="About", command=self._show_about_dialog)

    def _open_settings_menu(self):
        self._popup_menu(self._settings_menu, self.btn_settings)

    def _open_help_menu(self):
        self._popup_menu(self._help_menu, self.btn_help)

    def _popup_menu(self, menu, button):
        try:
            menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
        finally:
            menu.grab_release()

    def _set_appearance(self, mode):
        ctk.set_appearance_mode(mode)
        self._appearance_var.set("Dark" if mode == "dark" else "Light")
        self._save_settings()

    @staticmethod
    def _make_dialog(parent, title, width, height):
        dlg = ctk.CTkToplevel(parent)
        dlg.title(title)
        dlg.geometry(f"{width}x{height}")
        dlg.resizable(False, False)
        dlg.transient(parent)
        dlg.bind("<Escape>", lambda _event: dlg.destroy())
        # grab_set fails if the window is not yet viewable; retry shortly.
        dlg.after(150, lambda: dlg.grab_set() if dlg.winfo_exists() else None)
        return dlg

    def _show_report_issue_dialog(self):
        dlg = self._make_dialog(self, "Report an issue", 480, 300)
        dlg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(dlg, text="Report an issue", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(24, 6))
        ctk.CTkLabel(
            dlg,
            text=("Conversion failures are collected in an error report you can "
                  "export after a failed run. If the app misbehaves, include that "
                  "report file when you tell the developer."),
            wraplength=420, justify="left", text_color=ui_palette.TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, sticky="w", padx=24, pady=(0, 10))
        ctk.CTkLabel(
            dlg, text=f"Report location:\n{ERROR_REPORT_PATH}",
            wraplength=420, justify="left", font=ctk.CTkFont(size=11),
            text_color=ui_palette.TEXT_FAINT,
        ).grid(row=2, column=0, sticky="w", padx=24, pady=(0, 16))

        buttons = ctk.CTkFrame(dlg, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 24))
        buttons.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            buttons, text="Open error report file",
            command=self._open_error_report, height=36,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            buttons, text="Close", width=90, height=36, fg_color="transparent",
            border_width=1, border_color=ui_palette.BORDER_INPUT,
            command=dlg.destroy,
        ).grid(row=0, column=1, sticky="e")

    def _open_error_report(self):
        if os.path.isfile(ERROR_REPORT_PATH):
            try:
                os.startfile(ERROR_REPORT_PATH)
            except OSError as exc:
                messagebox.showerror("Could not open report", str(exc))
        else:
            messagebox.showinfo(
                "No report yet",
                "No error report exists. Run a conversion with failures and "
                "click 'Export Error Report', then try again.")

    def _show_about_dialog(self):
        dlg = self._make_dialog(self, "About", 380, 240)
        dlg.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(dlg, text="Universal Image Converter", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, pady=(32, 2))
        ctk.CTkLabel(dlg, text=f"Version {APP_VERSION}", text_color=ui_palette.TEXT_MUTED).grid(
            row=1, column=0, pady=(0, 12))
        ctk.CTkLabel(
            dlg,
            text="Batch-convert images between PNG, JPG, WebP and BMP.\n"
                 "Built with Python, CustomTkinter and Pillow.",
            justify="center", text_color=ui_palette.TEXT_MUTED, font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, pady=(0, 20), padx=24)
        ctk.CTkButton(dlg, text="Close", width=90, command=dlg.destroy).grid(
            row=3, column=0, pady=(0, 24))

    def select_files(self):
        filetypes = (
            ("Supported Images", "*.png *.jpg *.jpeg *.webp *.bmp"),
            ("All Files", "*.*")
        )
        files = filedialog.askopenfilenames(title="Select Images", filetypes=filetypes)
        
        if files:
            self.selected_files = list(files)
            self.lbl_count.configure(text=f"{len(self.selected_files)} file(s) selected")
            self.btn_convert.configure(text="Start Conversion")
            self.load_previews()
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Ready")
            self.refresh_convert_button_state()

    def select_output_dir(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self._set_output_directory(folder)

    def _set_output_directory(self, folder):
        self.output_directory = folder
        display_path = folder if len(folder) < 30 else f"...{folder[-27:]}"
        self.lbl_out_dir.configure(text=f"Output: {display_path}")
        self.refresh_convert_button_state()

    def _on_quality_change(self, value):
        self.quality_value_label.configure(text=f"Quality: {int(value)}")

    def _on_resize_toggle(self):
        self.entry_max_dim.configure(state="normal" if self.chk_resize.get() else "disabled")

    def _on_recent_dir_pick(self, choice):
        if choice != "Recent folders" and os.path.isdir(choice):
            self._set_output_directory(choice)

    def _collect_options(self) -> ConvertOptions:
        max_dim = None
        if self.chk_resize.get():
            try:
                max_dim = max(1, int(self.entry_max_dim.get()))
            except ValueError:
                max_dim = 1920
        return ConvertOptions(
            quality=int(self.quality_slider.get()),
            lossless_webp=bool(self.chk_lossless.get()),
            max_dimension=max_dim,
            keep_metadata=bool(self.chk_metadata.get()),
            overwrite=bool(self.chk_overwrite.get()),
        )

    # --- Settings persistence (feature 7) ---

    def _settings_path(self):
        base = os.environ.get("APPDATA") or tempfile.gettempdir()
        return os.path.join(base, "UniversalImageConverter", "settings.json")

    def _load_settings(self):
        try:
            with open(self._settings_path(), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        try:
            # Theme: applied before anything else so widgets build in the
            # right mode; color tuples do the rest of the work.
            appearance = str(data.get("appearance", "dark")).lower()
            ctk.set_appearance_mode("dark" if appearance == "dark" else "light")
            self.target_format.set(data.get("target_format", "webp"))
            quality = min(100, max(1, int(data.get("quality", 90))))
            self.quality_slider.set(quality)
            self.quality_value_label.configure(text=f"Quality: {quality}")
            for key, var in (("lossless", self.chk_lossless),
                             ("resize", self.chk_resize),
                             ("keep_metadata", self.chk_metadata),
                             ("overwrite", self.chk_overwrite)):
                (var.select if data.get(key) else var.deselect)()
            self._on_resize_toggle()
            self._recent_dirs = [d for d in data.get("recent_dirs", []) if os.path.isdir(d)][:5]
            self._refresh_recent_menu()
            last_dir = data.get("output_dir")
            if last_dir and os.path.isdir(last_dir):
                self._set_output_directory(last_dir)
        except Exception:
            pass  # corrupted settings must never block startup

    def _save_settings(self):
        data = {
            "appearance": ctk.get_appearance_mode().lower(),
            "target_format": self.target_format.get(),
            "quality": int(self.quality_slider.get()),
            "lossless": bool(self.chk_lossless.get()),
            "resize": bool(self.chk_resize.get()),
            "max_dimension": self.entry_max_dim.get(),
            "keep_metadata": bool(self.chk_metadata.get()),
            "overwrite": bool(self.chk_overwrite.get()),
            "output_dir": self.output_directory,
            "recent_dirs": self._recent_dirs,
        }
        try:
            os.makedirs(os.path.dirname(self._settings_path()), exist_ok=True)
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _remember_recent_dir(self, folder):
        if folder in self._recent_dirs:
            self._recent_dirs.remove(folder)
        self._recent_dirs.insert(0, folder)
        self._recent_dirs = self._recent_dirs[:5]
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        if self._recent_dirs:
            self.recent_menu.configure(values=list(self._recent_dirs))
            self.recent_menu.set(self._recent_dirs[0] if len(self._recent_dirs) == 1
                                 else "Recent folders")
        else:
            self.recent_menu.set("Recent folders")

    # --- Drag-and-drop (feature 1) ---

    def _setup_drag_and_drop(self):
        if not _DND_AVAILABLE:
            return
        try:
            TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.subtitle_label.configure(
                text="Select, preview, remove, and convert (or drop files here)")
        except Exception:
            pass  # the file picker remains fully functional without dnd

    def _on_drop(self, event):
        if self.is_converting:
            return
        try:
            raw_paths = self.tk.splitlist(event.data)
        except Exception:
            return
        added = []
        for raw in raw_paths:
            path = os.path.normpath(raw)
            if os.path.isdir(path):
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    if os.path.isfile(full) and os.path.splitext(name)[1].lower() in SUPPORTED_INPUT_EXTS:
                        added.append(full)
            elif os.path.isfile(path) and os.path.splitext(path)[1].lower() in SUPPORTED_INPUT_EXTS:
                added.append(path)
        added = [p for p in added if p not in self.selected_files]
        if not added:
            self.lbl_status.configure(text="Drop contained no supported images.")
            return
        self.selected_files.extend(added)
        self.lbl_count.configure(text=f"{len(self.selected_files)} file(s) selected")
        self.load_previews()
        self.refresh_convert_button_state()

    def refresh_convert_button_state(self):
        if self.selected_files and self.output_directory:
            self.btn_convert.configure(state="normal")
        else:
            self.btn_convert.configure(state="disabled")

    def clear_previews(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.preview_empty_state_frame = None
        self.update_preview_scroll_state()

    def update_preview_header(self):
        item_count = len(self.selected_files)
        if item_count:
            self.preview_meta_label.configure(text="Review the queue before converting")
        else:
            self.preview_meta_label.configure(text="No images selected")
        self.preview_count_chip.configure(text=f"{item_count} item{'s' if item_count != 1 else ''}")

    def get_target_extension(self):
        target = self.target_format.get().lower()
        if target in {"jpg", "jpeg"}:
            return "jpg"
        return target

    def get_target_display_name(self):
        target_ext = self.get_target_extension()
        if target_ext == "jpg":
            return "JPG"
        return target_ext.upper()

    def build_error_log(self, file_path, exc):
        reason, suggestion = describe_error(exc)
        return "\n".join([
            f"File: {os.path.basename(file_path)}",
            f"Error: {exc.__class__.__name__}: {exc}",
            f"Reason: {reason}",
            f"Suggestion: {suggestion}",
        ])

    def on_target_format_change(self, *_):
        # Update the per-item labels in place instead of rebuilding the
        # whole preview list on every radio click.
        display_name = self.get_target_display_name()
        for card in self._preview_cards.values():
            try:
                details = card["details"].cget("text")
                if "Ready for" in details:
                    card["details"].configure(text=f"Ready for {display_name} conversion")
            except Exception:
                pass

    def remove_selected_file(self, file_path):
        if self.is_converting:
            return
        self.selected_files = [path for path in self.selected_files if path != file_path]

        if self.selected_files:
            self.lbl_count.configure(text=f"{len(self.selected_files)} file(s) selected")
            self.load_previews()
            self.lbl_status.configure(text="Ready")
        else:
            self.lbl_count.configure(text="0 files selected")
            self.clear_previews()
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Ready")
            self.btn_convert.configure(text="Start Conversion")

        self.update_preview_header()
        self.refresh_convert_button_state()

    def load_previews(self):
        self._preview_generation += 1
        generation = self._preview_generation
        self.clear_previews()
        self._preview_cards = {}

        if not self.selected_files:
            self.preview_empty_state_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=ui_palette.EMPTY_BG, corner_radius=16, border_width=1, border_color=ui_palette.EMPTY_BORDER)
            self.preview_empty_state_frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.preview_empty_state_frame.grid_columnconfigure(0, weight=1)
            self.preview_empty_state_frame.grid_rowconfigure(0, weight=1)

            empty_title = ctk.CTkLabel(self.preview_empty_state_frame, text="No images selected", font=ctk.CTkFont(size=16, weight="bold"))
            empty_title.grid(row=0, column=0, sticky="s", pady=(0, 4))

            empty_message = ctk.CTkLabel(
                self.preview_empty_state_frame,
                text="Pick images on the left to build the conversion queue.",
                text_color=ui_palette.TEXT_MUTED,
                font=ctk.CTkFont(size=11)
            )
            empty_message.grid(row=1, column=0, sticky="n")

            self.update_preview_scroll_state()
            self.update_preview_header()
            return

        # M6: cards render instantly; thumbnails decode off the main thread.
        self.remove_buttons = []
        for path in self.selected_files:
            item_frame = ctk.CTkFrame(
                self.scrollable_frame,
                fg_color=ui_palette.BG_NESTED,
                corner_radius=16,
                border_width=1,
                border_color=ui_palette.BORDER_NESTED
            )
            item_frame.pack(side="top", fill="x", pady=(0, 12), padx=4)
            item_frame.grid_columnconfigure(1, weight=1)

            preview_wrap = ctk.CTkFrame(item_frame, fg_color=ui_palette.BG_THUMB, corner_radius=12, width=132, height=132)
            preview_wrap.grid(row=0, column=0, rowspan=2, sticky="w", padx=12, pady=12)
            preview_wrap.grid_propagate(False)

            img_label = ctk.CTkLabel(preview_wrap, text="", font=ctk.CTkFont(size=10))
            img_label.configure(text_color=ui_palette.TEXT_FAINT)
            img_label.place(relx=0.5, rely=0.5, anchor="center")

            name_label = ctk.CTkLabel(
                item_frame,
                text=os.path.basename(path),
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                justify="left",
                wraplength=300
            )
            name_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(18, 2))

            details_label = ctk.CTkLabel(
                item_frame,
                text="Loading preview..." if self.is_converting is False else f"Ready for {self.get_target_display_name()} conversion",
                text_color=ui_palette.TEXT_MUTED,
                font=ctk.CTkFont(size=11),
                anchor="w",
                justify="left"
            )
            details_label.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 18))

            remove_button = ctk.CTkButton(
                item_frame,
                text="Remove",
                width=94,
                height=34,
                corner_radius=10,
                fg_color=ui_palette.DANGER,
                hover_color=ui_palette.DANGER_HOVER,
                command=lambda file_path=path: self.remove_selected_file(file_path)
            )
            remove_button.grid(row=0, column=2, rowspan=2, sticky="e", padx=12, pady=12)
            self.remove_buttons.append(remove_button)

            self._preview_cards[path] = {
                "frame": item_frame,
                "wrap": preview_wrap,
                "img_label": img_label,
                "details": details_label,
            }

        if self.is_converting:
            for button in self.remove_buttons:
                button.configure(state="disabled")

        threading.Thread(
            target=self._generate_thumbnails,
            args=(list(self.selected_files), generation),
            daemon=True,
        ).start()

        self.update_preview_scroll_state()
        self.update_preview_header()

    def _on_enter_key(self, _event):
        if str(self.btn_convert.cget("state")) == "normal":
            self.start_conversion_thread()

    def _on_escape_key(self, _event):
        if self.is_converting:
            self.cancel_conversion()

    def _post_to_ui(self, func, *args):
        self._ui_queue.put((func, args))

    def _drain_ui_queue(self):
        try:
            while True:
                func, args = self._ui_queue.get_nowait()
                try:
                    func(*args)
                except Exception:
                    pass  # one stale callback must not kill the poller
        except queue.Empty:
            pass
        self.after(50, self._drain_ui_queue)

    def _generate_thumbnails(self, paths, generation):
        """Worker: decode thumbnails one by one and post them to the UI."""
        for path in paths:
            if generation != self._preview_generation:
                return  # queue changed; stale work is discarded
            try:
                # M7: context manager guarantees the file handle closes.
                with Image.open(path) as img:
                    img.thumbnail((120, 120))
                    thumb = img.copy()
                self._post_to_ui(self._apply_thumbnail, path, thumb, generation)
            except Exception as e:
                self._post_to_ui(self._mark_preview_failed, path, e, generation)

    def _apply_thumbnail(self, path, thumb, generation):
        if generation != self._preview_generation:
            return
        card = self._preview_cards.get(path)
        if card is None:
            return
        try:
            ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=thumb.size)
            card["img_label"].configure(image=ctk_img, text="")
            card["img_label"].image_ref = ctk_img  # prevent garbage collection
            card["details"].configure(text=f"Ready for {self.get_target_display_name()} conversion")
        except Exception:
            pass

    def _mark_preview_failed(self, path, exc, generation):
        """H4: preview failure must stay visible; the file is still converted."""
        if generation != self._preview_generation:
            return
        card = self._preview_cards.get(path)
        if card is None:
            return
        try:
            reason, _ = describe_error(exc)
            card["frame"].configure(fg_color=ui_palette.WARNING_BG, border_color=ui_palette.WARNING_BORDER)
            card["img_label"].configure(text="!", text_color=ui_palette.WARNING_TEXT)
            card["details"].configure(
                text=f"{reason} The file stays in the queue and will still be converted.",
                text_color=ui_palette.WARNING_TEXT,
                wraplength=420,
            )
        except Exception:
            pass

        self.update_preview_scroll_state()
        self.update_preview_header()

    def update_preview_scroll_state(self):
        visible_children = [widget for widget in self.scrollable_frame.winfo_children() if widget is not self.preview_empty_state_frame]
        has_previews = len(visible_children) > 0

        # M9: CustomTkinter exposes no public API for this; tolerate internal
        # layout changes instead of crashing on a library upgrade.
        try:
            if has_previews:
                self.scrollable_frame._scrollbar.grid()
                self.scrollable_frame._parent_canvas.configure(
                    scrollregion=self.scrollable_frame._parent_canvas.bbox("all"))
            else:
                self.scrollable_frame._scrollbar.grid_remove()
                self.scrollable_frame._parent_canvas.yview_moveto(0)
                self.scrollable_frame._parent_canvas.configure(scrollregion=(0, 0, 0, 0))
        except AttributeError:
            pass

    def start_conversion_thread(self):
        if not self.output_directory:
            messagebox.showwarning(
                "Output Folder Required",
                "Please choose an output folder before starting the conversion."
            )
            return
        if self.is_converting or not self.selected_files:
            return

        # H2: snapshot everything the worker needs on the main thread --
        # reading tkinter variables from the worker thread is unsafe.
        files = list(self.selected_files)
        target_ext = self.get_target_extension()
        output_dir = self.output_directory
        options = self._collect_options()

        self._remember_recent_dir(output_dir)
        self._save_settings()

        self.is_converting = True
        self.cancel_event.clear()
        self.btn_convert.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.btn_out_dir.configure(state="disabled")
        for radio in (self.radio_webp, self.radio_png, self.radio_jpg):
            radio.configure(state="disabled")
        for button in self.remove_buttons:
            button.configure(state="disabled")
        self.btn_cancel.grid()
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Converting...")

        thread = threading.Thread(
            target=self.process_images,
            args=(files, target_ext, output_dir, options),
            daemon=True,
        )
        thread.start()

    def cancel_conversion(self):
        """M10: ask the worker to stop before starting the next file."""
        self.cancel_event.set()
        self.btn_cancel.configure(state="disabled")
        self.lbl_status.configure(text="Stopping...")

    # NEW HELPER: Safely updates the UI from the background thread
    def sync_ui_progress(self, progress_val, status_text):
        self.progress_bar.set(progress_val)
        self.lbl_status.configure(text=status_text)

    def process_images(self, files, target_ext, output_dir, options):
        total_files = len(files)
        max_workers = min(4, os.cpu_count() or 1)

        batch = convert_files(
            files,
            output_dir,
            target_ext,
            max_workers=max_workers,
            cancel_event=self.cancel_event,
            progress_callback=lambda done, total: self._post_to_ui(
                self.sync_ui_progress, done / total, f"Processing: {done}/{total}"),
            options=options,
        )
        error_logs = [self.build_error_log(path, exc) for path, exc in batch.errors]
        self._post_to_ui(self.finish_conversion, batch, total_files, error_logs)

    def finish_conversion(self, batch, total_files, error_logs):
        self.is_converting = False
        self.btn_cancel.grid_remove()
        self.btn_cancel.configure(state="normal")
        self.btn_select.configure(state="normal")
        self.btn_out_dir.configure(state="normal")
        for radio in (self.radio_webp, self.radio_png, self.radio_jpg):
            radio.configure(state="normal")
        for button in self.remove_buttons:
            button.configure(state="normal")
        self.refresh_convert_button_state()

        # Feature 6: keep only the failures in the queue for a one-click retry.
        failed_paths = [str(path) for path, _ in batch.errors]
        if failed_paths:
            self.selected_files = failed_paths
            self.lbl_count.configure(text=f"{len(failed_paths)} failed file(s) kept in queue")
            self.btn_convert.configure(text=f"Retry Failed ({len(failed_paths)})")
        else:
            self.lbl_count.configure(text="0 files selected")
            self.selected_files = []
            self.btn_convert.configure(text="Start Conversion")
        self.clear_previews()
        self.load_previews()
        self.update_preview_header()

        summary = (f"{batch.converted} converted, {batch.copied} copied, "
                   f"{batch.skipped} already-in-place, {batch.failed} failed, "
                   f"{batch.cancelled} cancelled (of {total_files})")

        if batch.cancelled and not error_logs:
            self.lbl_status.configure(text="Cancelled.", text_color="gray")
            messagebox.showinfo("Conversion Cancelled", f"Stopped early. {summary}.")
            return

        if error_logs:
            self.lbl_status.configure(text="Completed with errors.", text_color="red")
            # L12: write the full report to disk; the dialog shows only a preview.
            report_path = ERROR_REPORT_PATH
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(error_logs))
                report_note = f"\n\nThe full error report was saved to:\n{report_path}"
            except OSError:
                report_note = ""
            error_details = "\n\n".join(error_logs[:5])
            if len(error_logs) > 5:
                error_details += f"\n\n...and {len(error_logs) - 5} more errors."
            messagebox.showwarning(
                "Conversion Issues",
                f"Finished with {summary}.{report_note}\n\nThe following errors occurred:\n\n{error_details}"
            )
        else:
            self.lbl_status.configure(text="Complete!", text_color="gray")
            messagebox.showinfo("Conversion Complete", f"Successfully processed: {summary}.")

if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()