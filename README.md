# Universal Image Converter

A lightweight Windows desktop application for batch image conversion. It provides a dark, modern GUI for selecting images, reviewing a conversion queue, choosing an output folder, and converting files to WebP, PNG, or JPG.

## Features

- Batch-select PNG, JPG, JPEG, WebP, and BMP images.
- Preview selected images before processing.
- Remove individual files from the queue.
- Convert images to WebP, PNG, or JPG.
- Preserve files that already use the selected target extension by copying them with `shutil.copy2`.
- Skip a file when its source and destination paths are identical.
- Show progress while the batch is processed.
- Keep the interface responsive by running conversion in a background thread.
- Report conversion, copy, skipped, and failed-file counts when processing finishes.
- Display readable error details and suggestions for common file and permission failures.

## Supported Formats

### Input

The file picker lists:

- PNG
- JPG/JPEG
- WebP
- BMP

Pillow performs the actual image decoding, so a file must be a valid image that the installed Pillow version can recognize.

### Output

- WebP, saved at quality 90
- PNG
- JPG, saved at quality 90

For JPG output, RGBA and palette images are converted to RGB. Palette images are converted to RGBA for WebP and PNG output when needed. JPG output uses the `.jpg` extension for both `.jpg` and `.jpeg` source files.

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

1. Select one or more images.
2. Review the image previews and remove any unwanted files.
3. Choose an output folder.
4. Select WebP, PNG, or JPG.
5. Click **Start Conversion**.

Output files keep the original base name and receive the selected target extension. If an output file with the same name already exists, the new file is saved as `name-1.ext`, `name-2.ext`, and so on — existing files are never overwritten.

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
converter_core.py     Pure conversion logic (headlessly testable)
tests/                pytest suite for converter_core
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