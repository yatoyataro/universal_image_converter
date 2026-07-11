import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image

# Set modern dark theme
ctk.set_appearance_mode("dark")  
ctk.set_default_color_theme("blue")  

class ImageConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Universal Image Converter 2.0")
        self.geometry("850x550")
        self.resizable(False, False)
        
        self.selected_files = []
        self.output_directory = ""
        
        self.create_layout()

    def create_layout(self):
        # --- Left Panel: Controls ---
        self.left_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.left_frame.pack(side="left", fill="y", padx=0, pady=0)
        
        self.title_label = ctk.CTkLabel(self.left_frame, text="Converter 2.0", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(30, 20))
        
        # Select Files
        self.btn_select = ctk.CTkButton(self.left_frame, text="Select Images", command=self.select_files, fg_color="#2EA043", hover_color="#237A32")
        self.btn_select.pack(pady=10, padx=20, fill="x")
        
        self.lbl_count = ctk.CTkLabel(self.left_frame, text="0 files selected", text_color="gray")
        self.lbl_count.pack(pady=(0, 10))

        # Select Output Directory
        self.btn_out_dir = ctk.CTkButton(self.left_frame, text="Choose Output Folder", command=self.select_output_dir, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"))
        self.btn_out_dir.pack(pady=10, padx=20, fill="x")
        
        self.lbl_out_dir = ctk.CTkLabel(self.left_frame, text="Default: Source Folder", text_color="gray", font=ctk.CTkFont(size=11))
        self.lbl_out_dir.pack(pady=(0, 20))

        # Target Format Selection
        self.format_label = ctk.CTkLabel(self.left_frame, text="Target Format:", font=ctk.CTkFont(weight="bold"))
        self.format_label.pack(pady=(10, 5))
        
        self.target_format = ctk.StringVar(value="webp")
        self.radio_webp = ctk.CTkRadioButton(self.left_frame, text="WebP", variable=self.target_format, value="webp")
        self.radio_png = ctk.CTkRadioButton(self.left_frame, text="PNG", variable=self.target_format, value="png")
        self.radio_jpg = ctk.CTkRadioButton(self.left_frame, text="JPEG", variable=self.target_format, value="jpg")
        
        self.radio_webp.pack(pady=5)
        self.radio_png.pack(pady=5)
        self.radio_jpg.pack(pady=5)

        # Spacer
        self.left_frame.pack_propagate(False)
        ctk.CTkLabel(self.left_frame, text="").pack(expand=True)

        # Progress and Convert Button
        self.progress_bar = ctk.CTkProgressBar(self.left_frame)
        self.progress_bar.pack(pady=10, padx=20, fill="x")
        self.progress_bar.set(0)
        
        self.lbl_status = ctk.CTkLabel(self.left_frame, text="Ready", text_color="gray")
        self.lbl_status.pack(pady=(0, 5))
        
        self.btn_convert = ctk.CTkButton(self.left_frame, text="Start Conversion", command=self.start_conversion_thread, state="disabled", height=40, font=ctk.CTkFont(weight="bold"))
        self.btn_convert.pack(pady=(10, 30), padx=20, fill="x")

        # --- Right Panel: Image Preview ---
        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.preview_label = ctk.CTkLabel(self.right_frame, text="Image Preview", font=ctk.CTkFont(size=18, weight="bold"))
        self.preview_label.pack(anchor="w", pady=(0, 10))
        
        # Scrollable area for image thumbnails
        self.scrollable_frame = ctk.CTkScrollableFrame(self.right_frame, label_text="Selected Files")
        self.scrollable_frame.pack(fill="both", expand=True)
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
        self.update_preview_scroll_state()

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

        self.refresh_convert_button_state()

    def load_previews(self):
        self.clear_previews()
        
        for path in self.selected_files:
            try:
                img = Image.open(path)
                img.thumbnail((120, 120))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                
                item_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
                item_frame.pack(side="top", fill="x", pady=5)
                
                img_label = ctk.CTkLabel(item_frame, image=ctk_img, text="")
                img_label.pack(side="left", padx=10)
                
                name_label = ctk.CTkLabel(item_frame, text=os.path.basename(path))
                name_label.pack(side="left", padx=10)

                remove_button = ctk.CTkButton(
                    item_frame,
                    text="Remove",
                    width=80,
                    fg_color="#9B2C2C",
                    hover_color="#7F2424",
                    command=lambda file_path=path: self.remove_selected_file(file_path)
                )
                remove_button.pack(side="right", padx=10)
                
            except Exception as e:
                # Basic error handling for preview rendering
                print(f"Preview error for {path}: {e}")

        self.update_preview_scroll_state()

    def update_preview_scroll_state(self):
        has_previews = len(self.scrollable_frame.winfo_children()) > 0

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
        target = self.target_format.get()
        total_files = len(self.selected_files)
        success_count = 0
        error_logs = []  # NEW: Array to collect errors
        
        for index, file_path in enumerate(self.selected_files):
            try:
                with Image.open(file_path) as img:
                    base_name, _ = os.path.splitext(os.path.basename(file_path))
                    output_name = f"{base_name}.{target}"

                    output_path = os.path.join(self.output_directory, output_name)
                    
                    if file_path.lower() == output_path.lower():
                        continue
                        
                    if target in ['jpg', 'jpeg'] and img.mode in ['RGBA', 'P']:
                        img = img.convert('RGB')
                    elif target == 'webp' and img.mode == 'P':
                        img = img.convert('RGBA')
                        
                    img.save(output_path, format=target.upper(), quality=90)
                    success_count += 1
                    
            except Exception as e:
                # Catch the specific error and log it with the filename
                filename = os.path.basename(file_path)
                error_logs.append(f"Failed '{filename}': {str(e)}")
                
            # Safely pass positional arguments to the helper method
            progress_value = (index + 1) / total_files
            status_text = f"Processing: {index + 1}/{total_files}"
            self.after(0, self.sync_ui_progress, progress_value, status_text)
            
        # Re-enable UI when finished and pass error logs
        self.after(0, self.finish_conversion, success_count, total_files, error_logs)

    def finish_conversion(self, success_count, total_files, error_logs):
        self.btn_select.configure(state="normal")
        self.refresh_convert_button_state()
        self.lbl_count.configure(text="0 files selected")
        self.selected_files = []
        self.clear_previews()
        
        # NEW: Handle user notifications based on success/failure
        if error_logs:
            self.lbl_status.configure(text="Completed with errors.", text_color="red")
            
            # Create a readable error string (limit to first 10 errors so it fits on screen)
            error_details = "\n".join(error_logs[:10])
            if len(error_logs) > 10:
                error_details += f"\n...and {len(error_logs) - 10} more errors."
                
            messagebox.showwarning(
                "Conversion Issues", 
                f"Converted {success_count} of {total_files} file(s).\n\nThe following errors occurred:\n\n{error_details}"
            )
        else:
            self.lbl_status.configure(text="Complete!", text_color="gray")
            messagebox.showinfo(
                "Conversion Complete", 
                f"Successfully converted all {success_count} file(s)!"
            )

if __name__ == "__main__":
    app = ImageConverterApp()
    app.mainloop()