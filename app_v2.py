import os
import queue
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

from converter_core import convert_files, describe_error

# Set modern dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ImageConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Universal Image Converter")
        self.geometry("1100x700")
        self.minsize(980, 640)
        self.resizable(True, True)
        self.configure(fg_color="#111111")
        
        self.selected_files = []
        self.output_directory = ""
        self.preview_empty_state_frame = None
        self.is_converting = False
        self.remove_buttons = []
        self.cancel_event = threading.Event()
        self._preview_generation = 0
        # Thread-safe bridge: workers put (callable, args) here and the
        # main-thread poller executes them. Calling tkinter from worker
        # threads directly is unsafe (RuntimeError: main thread is not in
        # main loop) -- this replaces all cross-thread after() calls.
        self._ui_queue: queue.Queue = queue.Queue()
        self.after(50, self._drain_ui_queue)
        
        self.create_layout()

    def create_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0, minsize=330)
        self.grid_columnconfigure(1, weight=1)

        self.workspace = ctk.CTkFrame(self, fg_color="transparent")
        self.workspace.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=18, pady=18)
        self.workspace.grid_rowconfigure(0, weight=1)
        self.workspace.grid_columnconfigure(0, weight=0, minsize=330)
        self.workspace.grid_columnconfigure(1, weight=1)

        # --- Left Panel: Controls ---
        self.left_frame = ctk.CTkFrame(self.workspace, width=330, corner_radius=24, fg_color="#1b1b1b", border_width=1, border_color="#2d2d2d")
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=0)
        self.left_frame.grid_columnconfigure(0, weight=1)
        
        self.left_content = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.left_content.grid(row=0, column=0, sticky="nsew", padx=22, pady=22)
        self.left_content.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self.left_content, text="Converter", font=ctk.CTkFont(size=25, weight="bold"))
        self.title_label.grid(row=0, column=0, sticky="w", pady=(2, 8))
        self.subtitle_label = ctk.CTkLabel(
            self.left_content,
            text="Select, preview, remove, and convert",
            text_color="#9a9a9a",
            font=ctk.CTkFont(size=11)
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(0, 18))

        self.controls_card = ctk.CTkFrame(self.left_content, fg_color="#202020", corner_radius=18, border_width=1, border_color="#2f2f2f")
        self.controls_card.grid(row=2, column=0, sticky="nsew")
        self.controls_card.grid_columnconfigure(0, weight=1)

        self.controls_inner = ctk.CTkFrame(self.controls_card, fg_color="transparent")
        self.controls_inner.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        self.controls_inner.grid_columnconfigure(0, weight=1)
        
        # Select Files
        self.btn_select = ctk.CTkButton(self.controls_inner, text="Select Images", command=self.select_files, fg_color="#2EA043", hover_color="#237A32", height=40)
        self.btn_select.grid(row=0, column=0, pady=(0, 10), sticky="ew")
        
        self.lbl_count = ctk.CTkLabel(self.controls_inner, text="0 files selected", text_color="#a5a5a5")
        self.lbl_count.grid(row=1, column=0, pady=(0, 10), sticky="w")

        # Select Output Directory
        self.btn_out_dir = ctk.CTkButton(self.controls_inner, text="Choose Output Folder", command=self.select_output_dir, fg_color="transparent", border_width=1, border_color="#4a4a4a", text_color=("gray10", "gray90"), height=40)
        self.btn_out_dir.grid(row=2, column=0, pady=(0, 8), sticky="ew")
        
        self.lbl_out_dir = ctk.CTkLabel(self.controls_inner, text="Default: Source Folder", text_color="#a5a5a5", font=ctk.CTkFont(size=11))
        self.lbl_out_dir.grid(row=3, column=0, pady=(0, 18), sticky="w")

        # Target Format Selection
        self.format_label = ctk.CTkLabel(self.controls_inner, text="Target Format", font=ctk.CTkFont(weight="bold", size=13))
        self.format_label.grid(row=4, column=0, pady=(0, 10), sticky="w")
        
        self.target_format = ctk.StringVar(value="webp")
        self.target_format.trace_add("write", self.on_target_format_change)
        self.radio_webp = ctk.CTkRadioButton(self.controls_inner, text="WebP", variable=self.target_format, value="webp")
        self.radio_png = ctk.CTkRadioButton(self.controls_inner, text="PNG", variable=self.target_format, value="png")
        self.radio_jpg = ctk.CTkRadioButton(self.controls_inner, text="JPG (.jpg)", variable=self.target_format, value="jpg")
        
        self.radio_webp.grid(row=5, column=0, pady=(0, 6), sticky="w")
        self.radio_png.grid(row=6, column=0, pady=(0, 6), sticky="w")
        self.radio_jpg.grid(row=7, column=0, pady=(0, 12), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.controls_inner)
        self.progress_bar.grid(row=8, column=0, pady=(10, 6), sticky="ew")
        self.progress_bar.set(0)
        
        self.lbl_status = ctk.CTkLabel(self.controls_inner, text="Ready", text_color="#a5a5a5")
        self.lbl_status.grid(row=9, column=0, pady=(0, 8), sticky="w")
        
        self.btn_convert = ctk.CTkButton(self.controls_inner, text="Start Conversion", command=self.start_conversion_thread, state="disabled", height=44, font=ctk.CTkFont(weight="bold"))
        self.btn_convert.grid(row=10, column=0, pady=(8, 0), sticky="ew")

        self.btn_cancel = ctk.CTkButton(
            self.controls_inner,
            text="Stop",
            command=self.cancel_conversion,
            height=36,
            fg_color="#B93838",
            hover_color="#9B2C2C",
        )
        # Hidden until a conversion is running (M10).
        self.btn_cancel.grid(row=11, column=0, pady=(8, 0), sticky="ew")
        self.btn_cancel.grid_remove()

        # --- Right Panel: Image Preview ---
        self.right_frame = ctk.CTkFrame(self.workspace, fg_color="#151515", corner_radius=24, border_width=1, border_color="#2d2d2d")
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        self.preview_shell = ctk.CTkFrame(self.right_frame, fg_color="#202020", corner_radius=18, border_width=1, border_color="#2f2f2f")
        self.preview_shell.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        self.preview_shell.grid_rowconfigure(1, weight=1)
        self.preview_shell.grid_columnconfigure(0, weight=1)

        self.preview_header = ctk.CTkFrame(self.preview_shell, fg_color="transparent")
        self.preview_header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        self.preview_header.grid_columnconfigure(0, weight=1)

        self.preview_label = ctk.CTkLabel(self.preview_header, text="Image Queue", font=ctk.CTkFont(size=20, weight="bold"))
        self.preview_label.grid(row=0, column=0, sticky="w")

        self.preview_meta_label = ctk.CTkLabel(self.preview_header, text="No images selected", text_color="#9a9a9a", font=ctk.CTkFont(size=11))
        self.preview_meta_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.preview_count_chip = ctk.CTkLabel(
            self.preview_header,
            text="0 items",
            width=84,
            height=28,
            corner_radius=999,
            fg_color="#2a2a2a",
            text_color="#d7d7d7",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.preview_count_chip.grid(row=0, column=1, rowspan=2, sticky="e")

        self.scrollable_frame = ctk.CTkScrollableFrame(self.preview_shell, fg_color="#202020", corner_radius=0)
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.update_preview_scroll_state()

    def select_files(self):
        filetypes = (
            ("Supported Images", "*.png *.jpg *.jpeg *.webp *.bmp"),
            ("All Files", "*.*")
        )
        files = filedialog.askopenfilenames(title="Select Images", filetypes=filetypes)
        
        if files:
            self.selected_files = list(files)
            self.lbl_count.configure(text=f"{len(self.selected_files)} file(s) selected")
            self.load_previews()
            self.progress_bar.set(0)
            self.lbl_status.configure(text="Ready")
            self.refresh_convert_button_state()

    def select_output_dir(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_directory = folder
            display_path = folder if len(folder) < 30 else f"...{folder[-27:]}"
            self.lbl_out_dir.configure(text=f"Output: {display_path}")
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
        if self.selected_files:
            self.load_previews()

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

        self.update_preview_header()
        self.refresh_convert_button_state()

    def load_previews(self):
        self._preview_generation += 1
        generation = self._preview_generation
        self.clear_previews()
        self._preview_cards = {}

        if not self.selected_files:
            self.preview_empty_state_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="#252525", corner_radius=16, border_width=1, border_color="#333333")
            self.preview_empty_state_frame.pack(fill="both", expand=True, padx=8, pady=8)
            self.preview_empty_state_frame.grid_columnconfigure(0, weight=1)
            self.preview_empty_state_frame.grid_rowconfigure(0, weight=1)

            empty_title = ctk.CTkLabel(self.preview_empty_state_frame, text="No images selected", font=ctk.CTkFont(size=16, weight="bold"))
            empty_title.grid(row=0, column=0, sticky="s", pady=(0, 4))

            empty_message = ctk.CTkLabel(
                self.preview_empty_state_frame,
                text="Pick images on the left to build the conversion queue.",
                text_color="#9a9a9a",
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
                fg_color="#262626",
                corner_radius=16,
                border_width=1,
                border_color="#343434"
            )
            item_frame.pack(side="top", fill="x", pady=(0, 12), padx=4)
            item_frame.grid_columnconfigure(1, weight=1)

            preview_wrap = ctk.CTkFrame(item_frame, fg_color="#1f1f1f", corner_radius=12, width=132, height=132)
            preview_wrap.grid(row=0, column=0, rowspan=2, sticky="w", padx=12, pady=12)
            preview_wrap.grid_propagate(False)

            img_label = ctk.CTkLabel(preview_wrap, text="", font=ctk.CTkFont(size=10))
            img_label.configure(text_color="#7a7a7a")
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
                text_color="#9a9a9a",
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
                fg_color="#B93838",
                hover_color="#9B2C2C",
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
            card["frame"].configure(fg_color="#2b2320", border_color="#8a5a2a")
            card["img_label"].configure(text="!", text_color="#c9a227")
            card["details"].configure(
                text=f"{reason} The file stays in the queue and will still be converted.",
                text_color="#c9a227",
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
            args=(files, target_ext, output_dir),
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

    def process_images(self, files, target_ext, output_dir):
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
        self.lbl_count.configure(text="0 files selected")
        self.selected_files = []
        self.clear_previews()
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
            error_details = "\n\n".join(error_logs[:8])
            if len(error_logs) > 8:
                error_details += f"\n\n...and {len(error_logs) - 8} more errors."
            messagebox.showwarning(
                "Conversion Issues",
                f"Finished with {summary}.\n\nThe following errors occurred:\n\n{error_details}"
            )
        else:
            self.lbl_status.configure(text="Complete!", text_color="gray")
            messagebox.showinfo("Conversion Complete", f"Successfully processed: {summary}.")

if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()