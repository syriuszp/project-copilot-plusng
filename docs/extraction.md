# Text Extraction & External Tools

Project Copilot uses a registry of extractors to index content from various file formats.

## Supported Formats

| Config Key | Format | Extractor | Requirement |
| :--- | :--- | :--- | :--- |
| `docx` | .docx | `DocxExtractor` | Native padding |
| `doc` | .doc | `DocExtractor` | `antiword.exe` |
| `pdf` | .pdf | `PdfExtractor` | `pypdf` (Text) / `poppler` (Images) |
| `images` | .png, .jpg | `ImageExtractor` | `tesseract` |
| `html` | .html, .mht| `HtmlExtractor` | `beautifulsoup4` |
| `csv` | .csv | `CsvExtractor` | Native |

## External Tools Setup (Option A: Portable)

For strictly local/portable deployments (no system installation required), binaries should be placed in `tools/` within the repository root.

### 1. Antiword (.doc support)
Required for extracting text from legacy Word 97-2003 documents.

- **Download**: Get `antiword` for Windows (e.g. from portableapps or cygwin build, or official mswin port).
- **Placement**:
    - `tools/antiword/antiword.exe`
    - (Optional) `tools/antiword/8859-1.txt` etc (mapping files)
- **Configuration**:
    - Automatically detected by `ExternalTools`.
    - Fallback: `NOT_EXTRACTABLE` status if missing.

### 2. Tesseract (OCR)
Required for Image extraction.
- **Placement**: `tools/tesseract/tesseract.exe` (+ `tessdata`)

### 3. Poppler (PDF Images)
Required for PDF rendering (preview/OCR).
- **Placement**: `tools/poppler/bin/pdftoppm.exe`
