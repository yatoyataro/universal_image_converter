# Universal Image Converter

A lightweight Windows desktop application for batch image conversion. It provides a modern dark or light GUI for selecting images, reviewing a conversion queue, choosing an output folder, and converting files to WebP, PNG, or JPG.

## Features

- Batch-select PNG, JPG, JPEG, WebP, and BMP images, or drag-and-drop files and folders from Explorer.
- Preview selected images before processing (thumbnails load in the background).
- Remove individual files from the queue with the ✕ button on each card.
- Dark and light appearance, switchable under **Settings → Appearance** and remembered between sessions.
- The left panel scrolls and the Convert/Stop buttons are pinned to the bottom, so every control stays reachable at any window size (minimum 720×500).
- **Settings** and **Help** menus in the top bar: appearance mode, error-report access (**Help → Report issue...**), and app info (**Help → About**).
- Convert images to WebP, PNG, or JPG in parallel across a thread pool.
- Conversion options: quality slider, lossless WebP, max-dimension resize, EXIF metadata preservation, and an overwrite policy.
- Existing outputs are never overwritten unless you enable **Overwrite existing files**; colliding outputs get `-1`, `-2`, ... suffixes.
- Preserve files that already use the selected target extension by copying them with `shutil.copy2`.
- Skip a file when its source and destination paths are identical.
- Show progress while the batch is processed, with a Stop button to cancel at any time (or press Escape).
- Failed files stay in the queue after a run for one-click retry; the full error report is written to `%TEMP%\universal_image_converter_errors.txt`.
- Settings and recent output folders persist between sessions in `%APPDATA%\UniversalImageConverter\settings.json`.
- Keyboard shortcuts: Enter starts the conversion, Ctrl+O opens the file picker, Escape stops a running conversion.
- Report conversion, copy, skipped, cancelled, and failed-file counts when processing finishes.
- Display readable error details and suggestions for common file and permission failures.

## Supported Formats

### Input

The file picker lists:

- PNG
- JPG/JPEG
- WebP
- BMP

Pillow performs the actual image decoding, so a file must be a valid image that the installed Pillow version can recognize. Drag-and-drop uses `tkinterdnd2`; if that package is missing, the app still runs and the file picker remains fully functional.

### Output

- WebP, saved at the quality slider's value (default 90, or lossless)
- PNG (the quality slider is disabled; PNG quality is fixed)
- JPG, saved at the quality slider's value (default 90)

For JPG output, RGBA, palette, and grayscale+alpha images are converted to RGB. CMYK images are converted to RGB for PNG and WebP output. Palette PNGs keep their palette. EXIF orientation is applied automatically, so rotated phone photos come out upright; tick **Keep EXIF metadata** to preserve the remaining EXIF data. JPG output uses the `.jpg` extension for both `.jpg` and `.jpeg` source files.

## Requirements

- Windows
- Python 3.9 or newer recommended
- `customtkinter`
- `Pillow`

The checked-in virtual environment currently contains:

```text
customtkinter 6.0.0
Pillow        12.3.0
PyInstaller   6.21.0
```

## Run From Source

Create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install customtkinter Pillow
```

Start the application:

```powershell
python app_v2.py
```

The application requires an output folder to be selected before **Start Conversion** becomes available. The folder is not created automatically.

## Use the Application

1. Drop images onto the window or select them with the file picker.
2. Review the image previews and remove any unwanted files.
3. Choose an output folder (recent folders are remembered).
4. Select WebP, PNG, or JPG and adjust the options (quality, resize, metadata, overwrite).
5. Click **Start Conversion** (or press Enter). Use **Stop** (or Escape) to cancel.

## Use the Application

1. Drop images onto the window or select them with the file picker.
2. Review the image previews and remove any unwanted files.
3. Choose an output folder (recent folders are remembered).
4. Select WebP, PNG, or JPG and adjust the options (quality, resize, metadata, overwrite).
5. Click **Start Conversion** (or press Enter). Use **Stop** (or Escape) to cancel.

Output files keep the original base name and receive the selected target extension. If an output file with the same name already exists, the new file is saved as `name-1.ext`, `name-2.ext`, and so on — existing files are never overwritten unless **Overwrite existing files** is enabled.

## Build a Windows Executable

Install PyInstaller in the virtual environment:

```powershell
venv\Scripts\python.exe -m pip install pyinstaller
```

Build using the included specification file:

```powershell
venv\Scripts\pyinstaller.exe app_v2.spec
```

The executable is generated at:

```text
dist\Universal_image_converter.exe
```

The spec file bundles CustomTkinter resources and uses `logo.ico` as the application icon. The build is configured as a windowed application without a console window.

## Project Structure

```text
app_v2.py             Application UI
ui_palette.py         Central light/dark color palette (theme switching)
converter_core.py     Pure conversion logic (headlessly testable)
tests/                pytest suite for converter_core and UI helpers
app_v2.spec           PyInstaller build configuration
requirements.txt      Runtime dependencies
requirements-dev.txt  Development dependencies (pytest)
logo.ico              Windows executable icon
build/                PyInstaller intermediate files (not tracked)
dist/                 Packaged executable output (not tracked)
```

## Run the Tests

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
venv\Scripts\python.exe -m pytest
```

## How It Works

`ImageConverterApp` builds the two-panel CustomTkinter interface. The left panel manages file selection, destination selection, target format, and progress. The right panel displays the current queue and image thumbnails.

When conversion starts, `process_images` handles each selected path in a worker thread. It validates the source and destination, copies files whose extension already matches the target, or opens and saves them through Pillow. Progress and completion dialogs are scheduled back on Tkinter's event loop with `after`.

## Troubleshooting

- **Start Conversion is disabled:** select at least one image and choose an output folder.
- **Permission error:** choose a folder where the application has write access and close files locked by another application.
- **Unrecognized image:** confirm the source file is a valid image supported by Pillow.
- **Same source and destination:** select a different output folder or target filename.

## License

No license file is currently included in this repository.