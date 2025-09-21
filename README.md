# Music Duplicate Detector

> Desktop application (Tkinter) to identify, compare, and safely remove duplicate audio files using **acoustic fingerprints** plus configurable **title similarity**.

---
## Table of Contents
1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Screenshots / UI Overview](#screenshots--ui-overview)
4. [Installation](#installation)
   - [Requirements](#requirements)
   - [Quick Setup](#quick-setup)
   - [Chromaprint / fpcalc](#chromaprint--fpcalc)
5. [Usage](#usage)
   - [Basic Workflow](#basic-workflow)
   - [Keyboard Shortcuts](#keyboard-shortcuts)
   - [Context Menus](#context-menus)
6. [Detection Algorithms](#detection-algorithms)
   - [Acoustic Fingerprinting](#acoustic-fingerprinting)
   - [Title Similarity Grouping](#title-similarity-grouping)
   - [Group Fusion Logic](#group-fusion-logic)
7. [Persistence & Configuration](#persistence--configuration)
   - [`column_config.json`](#column_configjson)
   - [`translations.json`](#translationsjson)
8. [Internationalization (i18n)](#internationalization-i18n)
9. [Internal Architecture](#internal-architecture)
10. [Main Files](#main-files)
11. [Supported Audio Formats](#supported-audio-formats)
12. [Performance Tips](#performance-tips)
13. [Known Limitations](#known-limitations)
14. [Troubleshooting](#troubleshooting)
15. [Roadmap / Future Ideas](#roadmap--future-ideas)
16. [Contributing](#contributing)
17. [License](#license)
18. [FAQ](#faq)
19. [Appendix A – Scan Data Structure](#appendix-a--scan-data-structure)
20. [Appendix B – Queue Message Protocol](#appendix-b--queue-message-protocol)

---
## Overview
**Music Duplicate Detector** scans one or more folders, extracts an **acoustic fingerprint** (Chromaprint / `fpcalc`) for each audio file, and groups identical ones. It optionally adds a **title similarity** pass (tunable ratio) to catch duplicates whose binary/acoustic fingerprint differs (e.g. different encode but likely same track) or where only naming differs.

The Tkinter + tksheet interface provides: visual grouping, difference highlighting, multi‑folder management, column customization (order, visibility, width), safe deletion (recycle bin), persistent layout, and real‑time language switching (English / French).

---
## Key Features
| Category | Description |
|----------|-------------|
| Acoustic detection | Chromaprint (`fpcalc`) fingerprinting with per‑file tag caching to avoid recomputation. |
| Title similarity | Supplemental grouping using normalized title string similarity (50–100% threshold). |
| Column layout persistence | Order, visibility, widths automatically saved & restored. |
| Internationalization | English / French – hot switch without restart. |
| Safe deletion | Uses OS recycle bin (`send2trash`) – recoverable. |
| Difference highlighting | Marks intra‑group differences (title, artist, album, bitrate, duration) in red. |
| Productivity shortcuts | Bulk toggle, group toggle, invert selection, spacebar toggle. |
| Multi-folder scanning | Add single or multiple root folders. |
| Live filtering | Text filter across title / artist / album / path. |
| Automatic config | `column_config.json` keeps user layout & language. |
| Modular architecture | Mixins for clean separation of concerns. |

---
## Screenshots / UI Overview
> *(Add screenshots here – placeholder).* 

---
## Installation
### Requirements
- **Python:** 3.9 / 3.10 / 3.11 / 3.12 (3.13 NOT supported – removal of `aifc` breaks some audio libs).
- **Chromaprint / fpcalc:** required binary for acoustic fingerprinting.
- OS: Windows (tested). Linux/macOS should work if `fpcalc` + dependencies are present.

### Quick Setup
```bash
# Clone repository
git clone <your-repo-url> music-duplicate-detector
cd music-duplicate-detector

# (Optional) create virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

### Chromaprint / fpcalc
1. Download from: https://acoustid.org/chromaprint
2. Place `fpcalc.exe` (Windows) or `fpcalc` (Linux/macOS) in the project root (same folder as `scanner.py`).
3. Start a scan; if missing, an error message is shown.

---
## Usage
### Basic Workflow
1. **Add folders** using *Add* / *Add multiple* buttons.
2. Adjust **Title similarity threshold** and **Duration tolerance** if needed.
3. Click **Scan Duplicates**.
4. Inspect groups (right‑click header to customize columns).
5. Check files you wish to remove (typically lowest bitrate or unwanted variants).
6. Click **Send to trash**.

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| `Ctrl+E` | Check all selected rows |
| `Ctrl+D` | Uncheck all selected rows |
| `Ctrl+I` | Invert selection state |
| `Ctrl+G` | Toggle (check/uncheck) whole current group |
| `Space`  | Toggle selected rows (or current row if none) |
| Double‑click | Open file with system default player |
| Right‑click header | Column menu (hide/show/reorder/reset) |

### Context Menus
- **Cell:** Check / uncheck row, invert selection, group operations, debug tools.
- **Header:** Hide column, reorder (left/right), show hidden columns, reset all, toggle visibility.

---
## Detection Algorithms
### Acoustic Fingerprinting
Process per file:
1. Generate fingerprint (`acoustid.fingerprint_file`) unless already cached in tags.
2. Persist fingerprint in audio metadata (custom tag) to skip future recomputation.
3. Group files by identical fingerprint → *acoustic groups*.

### Title Similarity Grouping
- Titles are normalized: removed bracketed/parenthetical segments, lowercased, trimmed.
- `difflib.SequenceMatcher` ratio compared to the configured threshold.
- Only groups with ≥ 2 matching titles and not already in an acoustic group are added.

### Group Fusion Logic
1. Start with acoustic groups.
2. Add title-based groups that introduce new paths not already in an acoustic group.
3. final = acoustic_groups + supplemental_title_groups.

---
## Persistence & Configuration
### `column_config.json`
Example:
```json
{
  "visible_columns": ["select", "title", "artist", "bitrate", "path", "group", "date"],
  "column_widths": {"select": 40, "title": 250, "artist": 180},
  "language": "en",
  "timestamp": "2025-09-21T12:34:56.123456",
  "version": 1
}
```
| Key | Meaning |
|-----|---------|
| `visible_columns` | Current order & subset of displayed columns (always keeps `select` first). |
| `column_widths` | Widths persisted between sessions. |
| `language` | UI language code (`en` / `fr`). |
| `timestamp` | Last save time (ISO 8601). |
| `version` | Config schema version. |

Automatic save triggers:
- Column reorder (drag & drop)
- Column resize
- Visibility changes

### `translations.json`
Excerpt:
```json
{
  "en": { "app.title": "Music Duplicate Detector", "ui.scan": "Scan Duplicates" },
  "fr": { "app.title": "Détecteur de Doublons de Musique", "ui.scan": "Scanner les Doublons" }
}
```
To add a language:
1. Add a root key (e.g. `"es"`).
2. Provide all needed translation keys.
3. Restart the app (JSON loaded + cached at runtime).

---
## Internationalization (i18n)
- Switch language via **Options > Language**.
- Instant update: column headers, buttons, menus, window title, context menus.
- Fallback order: Selected language → French → raw key.

---
## Internal Architecture
The UI logic is composed via *mixins* (composition over inheritance complexity):
| Mixin | Responsibility |
|-------|----------------|
| `ColumnManagerMixin` | Column order, visibility, width, language, persistence. |
| `SelectionMixin` | Row checkbox state, group toggles, selection transforms. |
| `HighlightMixin` | Intra‑group difference highlighting (title/artist/album/bitrate/duration). |
| `DataManagerMixin` | Table rebuild, duration filtering, grouping preparation. |
| `ScanMixin` | Background scanning & async queue messaging. |
| `DeletionMixin` | Safe file deletion (move to recycle bin). |
| `FoldersMixin` | Directory management (add/remove roots). |
| `scanner.py` | Fingerprint + metadata + grouping algorithms. |

---
## Main Files
| File | Description |
|------|-------------|
| `main.py` | Entry point creating the application instance. |
| `ui.py` | Integrates mixins, builds Tk interface & events. |
| `scanner.py` | Scanning & grouping logic (fingerprint + similarity). |
| `translations.json` | Language resources. |
| `column_config.json` | Generated user layout/state file. |
| `requirements.txt` | Python dependencies. |
| `dialogs.py` | Auxiliary dialogs (multi-folder selection). |

---
## Supported Audio Formats
Tested: `mp3`, `flac`, `wav`, `m4a`, `ogg`.  
Other formats may work if supported by **mutagen** & the backend libraries.

---
## Performance Tips
| Topic | Advice |
|-------|--------|
| Repeated scans | Fingerprints cached in tags → fewer recomputations. |
| Large libraries | Split scanning into batches if > 100k files. |
| Disk I/O | Keep `fpcalc` + library on SSD to reduce latency. |
| Title similarity | Lower threshold = more candidate groups (slower). |
| Memory footprint | Only lightweight metadata is parsed, not full audio decode. |

---
## Known Limitations
- Python 3.13 unsupported (removal of `aifc`).
- Fingerprint failures on corrupted or exotic files.
- No embedded audio preview yet (opens with system player instead).
- No advanced multi-column sort (manual reordering only for now).
- No real-time filesystem watching.

---
## Troubleshooting
| Issue                       | Likely Cause                  | Remedy                                                                 |
|-----------------------------|-------------------------------|------------------------------------------------------------------------|
| `fpcalc.exe not found`      | Missing binary                | Place `fpcalc.exe` beside `scanner.py`.                                |
| No duration visible         | File missing length info      | Status bar warning only; harmless.                                     |
| Expected duplicates missing | Different encodes / durations | Lower title similarity threshold; re‑scan.                             |
| Cannot open file            | Path / permissions issue      | Check access rights / rename path.                                     |
| UI seems frozen             | Huge scan on slow HDD         | Wait – scan runs in background thread; investigate console if blocked. |
| Column layout lost          | JSON write failed             | Check write permissions.                                               |
| Language unchanged          | Cached translations loaded    | Restart application.                                                   |

### Logs & Debug
- Debug mode (context menu) shows internal checkbox state sample.
- Warns if fingerprint tag write verification fails.

---
## Roadmap / Future Ideas
- [ ] Clickable header sort (ASC/DESC, multi-level).
- [ ] Column layout profiles (minimal / full / technical).
- [ ] Online AcoustID enrichment (metadata fetch).
- [ ] Embedded waveform preview / inline audio player.
- [ ] Export results (CSV / JSON report).
- [ ] Simulation mode (no deletion allowed). 
- [ ] Additional languages (Spanish, German, etc.).
- [ ] Incremental index & persistent on-disk cache.

---
## Contributing
1. Fork & create a feature branch (`feature/your-feature`).
2. Add or adjust functionality (keep style readable; PEP8 sensible). 
3. Manually test with a small sample folder.
4. Update README if user-facing changes are introduced.
5. Open a clear PR (description, reproduction steps, screenshots if UI changes).

*(See `CONTRIBUTING.md` if present – or propose one.)*

---
## License
Released under **MIT License**. See `LICENSE` for full text.

---
## FAQ
**Q: Are files deleted permanently?**  
A: No. They are moved to the OS recycle bin (recoverable).

**Q: What if I move a folder after scanning?**  
A: Fingerprints stored in tags remain valid; only new/changed files need recomputation.

**Q: Can I undo a deletion?**  
A: Yes – retrieve files from the recycle bin. 

**Q: Does language switching affect data?**  
A: No – only UI labels; groups are rebuilt with translated headers.

**Q: How do I add a language?**  
A: Add a new root object in `translations.json` and restart.

---
## Appendix A – Scan Data Structure
Each collected file entry:
```json
{
  "path": "C:/Music/Artist/Album/track.flac",
  "date": 1712345678.123,
  "title": "Song Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "bitrate": 921,
  "duration": 245.37
}
```
The final result sent to the UI: `List<List<file_info>>` (list of duplicate groups).

---
## Appendix B – Queue Message Protocol
Messages produced by the scanning thread and consumed by the UI:

| Type           | Payload                 | Effect                                |
|----------------|-------------------------|---------------------------------------|
| `status`       | `str`                   | Updates status bar text               |
| `progress_max` | `int`                   | Sets the progress bar maximum         |
| `progress`     | `int`                   | Increments current progress value     |
| `message`      | `(level, text)`         | Info or error popup                   |
| `results`      | `List<List<file_info>>` | Supplies grouped duplicates to UI     |
| `finished`     | `None`                  | Marks end of scan / resets busy state |

---
**Happy library cleaning!** 🎵
