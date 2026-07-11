import os
import shutil
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, UnidentifiedImageError

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

    def get_error_reason(self, exc, source_path, output_path):
        if isinstance(exc, FileNotFoundError):
            return "The source file or destination folder could not be found."
        if isinstance(exc, PermissionError):
            return "Windows blocked access to the file or the destination folder."
        if isinstance(exc, UnidentifiedImageError):
            return "Pillow could not recognize this file as a supported image."
        if isinstance(exc, shutil.SameFileError):
            return "The app tried to copy the file onto itself in the same location."
        if isinstance(exc, IsADirectoryError):
            return "The selected path points to a folder instead of an image file."
        if isinstance(exc, OSError):
            return "The image may be damaged, locked by another app, or not supported by this format."
        return "An unexpected error occurred while processing the file."

    def get_error_suggestion(self, exc):
        if isinstance(exc, FileNotFoundError):
            return "Re-select the image or choose a destination folder that still exists."
        if isinstance(exc, PermissionError):
            return "Close the image in other apps or pick a folder where you have write access."
        if isinstance(exc, UnidentifiedImageError):
            return "Check that the file is a valid image and try again with another source file."
        if isinstance(exc, shutil.SameFileError):
            return "Use a different output folder or a different filename to avoid copying onto the same file."
        if isinstance(exc, IsADirectoryError):
            return "Make sure the selected item is an image file, not a folder."
        if isinstance(exc, OSError):
            return "Try another image file or another target format, and make sure the file is not locked."
        return "Try the file again or choose a different source image."

    def build_error_log(self, file_path, stage, exc, output_path=None):
        parts = [
            f"File: {os.path.basename(file_path)}",
            f"Stage: {stage}",
            f"Error: {exc.__class__.__name__}: {exc}",
            f"Reason: {self.get_error_reason(exc, file_path, output_path)}",
            f"Suggestion: {self.get_error_suggestion(exc)}",
        ]
        if output_path:
            parts.insert(2, f"Destination: {output_path}")
        return "\n".join(parts)

    def on_target_format_change(self, *_):
        if self.selected_files:
            self.load_previews()

    def remove_selected_file(self, file_path):
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
        self.clear_previews()

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
        
        for path in self.selected_files:
            try:
                img = Image.open(path)
                img.thumbnail((120, 120))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                
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

                img_label = ctk.CTkLabel(preview_wrap, image=ctk_img, text="")
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
                    text=f"Ready for {self.get_target_display_name()} conversion",
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
                
            except Exception as e:
                # Basic error handling for preview rendering
                print(f"Preview error for {path}: {e}")

        self.update_preview_scroll_state()
        self.update_preview_header()

    def update_preview_scroll_state(self):
        visible_children = [widget for widget in self.scrollable_frame.winfo_children() if widget is not self.preview_empty_state_frame]
        has_previews = len(visible_children) > 0

        if has_previews:
            self.scrollable_frame.unbind_all("<MouseWheel>")
            self.scrollable_frame.unbind_all("<Button-4>")
            self.scrollable_frame.unbind_all("<Button-5>")
            self.scrollable_frame.bind_all("<MouseWheel>", self.scrollable_frame._mouse_wheel_all, add=True)
            self.scrollable_frame.bind_all("<Button-4>", self.scrollable_frame._mouse_wheel_all, add=True)
            self.scrollable_frame.bind_all("<Button-5>", self.scrollable_frame._mouse_wheel_all, add=True)
            self.scrollable_frame._scrollbar.grid()
            self.scrollable_frame._parent_canvas.configure(scrollregion=self.scrollable_frame._parent_canvas.bbox("all"))
        else:
            self.scrollable_frame.unbind_all("<MouseWheel>")
            self.scrollable_frame.unbind_all("<Button-4>")
            self.scrollable_frame.unbind_all("<Button-5>")
            self.scrollable_frame._scrollbar.grid_remove()
            self.scrollable_frame._parent_canvas.yview_moveto(0)
            self.scrollable_frame._parent_canvas.configure(scrollregion=(0, 0, 0, 0))

    def start_conversion_thread(self):
        if not self.output_directory:
            messagebox.showwarning(
                "Output Folder Required",
                "Please choose an output folder before starting the conversion."
            )
            return

        self.btn_convert.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text="Converting...")
        
        thread = threading.Thread(target=self.process_images)
        thread.start()

    # NEW HELPER: Safely updates the UI from the background thread
    def sync_ui_progress(self, progress_val, status_text):
        self.progress_bar.set(progress_val)
        self.lbl_status.configure(text=status_text)

    def process_images(self):
        target_ext = self.get_target_extension()
        target_display = self.get_target_display_name()
        save_format = "JPEG" if target_ext == "jpg" else target_display
        total_files = len(self.selected_files)
        converted_count = 0
        copied_count = 0
        skipped_count = 0
        error_logs = []  # NEW: Array to collect errors
        
        for index, file_path in enumerate(self.selected_files):
            output_path = None
            try:
                if not os.path.isfile(file_path):
                    raise FileNotFoundError("The source image no longer exists.")

                if not self.output_directory or not os.path.isdir(self.output_directory):
                    raise FileNotFoundError("The selected output folder is missing or invalid.")

                base_name, source_ext = os.path.splitext(os.path.basename(file_path))
                source_ext = source_ext.lower().lstrip(".")
                output_name = f"{base_name}.{target_ext}"
                output_path = os.path.join(self.output_directory, output_name)

                source_same_as_target = source_ext == target_ext or (target_ext == "jpg" and source_ext == "jpeg")

                if os.path.abspath(file_path).lower() == os.path.abspath(output_path).lower():
                    skipped_count += 1
                    continue

                if source_same_as_target:
                    shutil.copy2(file_path, output_path)
                    copied_count += 1
                else:
                    with Image.open(file_path) as img:
                        if target_ext == 'jpg' and img.mode in ['RGBA', 'P']:
                            img = img.convert('RGB')
                        elif target_ext == 'webp' and img.mode == 'P':
                            img = img.convert('RGBA')
                        elif target_ext == 'png' and img.mode in ['CMYK', 'P']:
                            img = img.convert('RGBA')

                        save_kwargs = {}
                        if target_ext in {'jpg', 'webp'}:
                            save_kwargs['quality'] = 90

                        img.save(output_path, format=save_format, **save_kwargs)
                        converted_count += 1

            except Exception as e:
                error_logs.append(self.build_error_log(file_path, "convert/copy", e, output_path))
                
            # Safely pass positional arguments to the helper method
            progress_value = (index + 1) / total_files
            status_text = f"Processing: {index + 1}/{total_files}"
            self.after(0, self.sync_ui_progress, progress_value, status_text)
            
        # Re-enable UI when finished and pass error logs
        self.after(0, self.finish_conversion, converted_count, copied_count, skipped_count, total_files, error_logs)

    def finish_conversion(self, converted_count, copied_count, skipped_count, total_files, error_logs):
        self.btn_select.configure(state="normal")
        self.refresh_convert_button_state()
        self.lbl_count.configure(text="0 files selected")
        self.selected_files = []
        self.clear_previews()
        self.update_preview_header()
        
        # NEW: Handle user notifications based on success/failure
        if error_logs:
            self.lbl_status.configure(text="Completed with errors.", text_color="red")
            
            # Create a readable error string (limit to first 8 errors so it fits on screen)
            error_details = "\n\n".join(error_logs[:8])
            if len(error_logs) > 8:
                error_details += f"\n\n...and {len(error_logs) - 8} more errors."
                
            messagebox.showwarning(
                "Conversion Issues", 
                f"Processed {converted_count} converted, {copied_count} copied, and {skipped_count} already-in-place file(s) out of {total_files}.\n\nThe following errors occurred:\n\n{error_details}"
            )
        else:
            self.lbl_status.configure(text="Complete!", text_color="gray")
            messagebox.showinfo(
                "Conversion Complete", 
                f"Successfully processed {converted_count} converted, {copied_count} copied, and {skipped_count} already-in-place file(s)!"
            )

if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()