# ⚙ MultiTool Studio

**A modern, modular desktop productivity toolbox built with Python & PySide6.**

23+ integrated mini-tools in a single application with secure user authentication, encrypted password vault, dark theme UI, and a plugin-based architecture.

---

## 🚀 Features

- **23 integrated tools** across 7 categories
- **Secure login system** (bcrypt password hashing)
- **Encrypted password vault** (Fernet + PBKDF2 key derivation)
- **Modern dark UI** built with PySide6/Qt6
- **Plugin architecture** — add tools by dropping a folder in `/tools`
- **SQLite local database** — no cloud, no sync, your data stays local
- **Windows-primary**, also runs on Linux/macOS

---

## 📦 Installation

### Prerequisites
- Python 3.11+
- pip

### Install dependencies

```bash
pip install -r requirements.txt
```

### Optional (for AI tools)
```bash
pip install deepface tf-keras
```

### Optional (for MP4→MP3 without ffmpeg)
```bash
pip install moviepy
```

### Run the app
```bash
python main.py
```

---

## 🛠 Tools Included

### 🤖 AI Tools
| Tool | Description |
|------|-------------|
| Face Emotion Reader | Detect emotions from webcam or image (requires deepface) |
| Face Age Estimator | Estimate age, gender, ethnicity from face |
| Face Detector | Detect faces using OpenCV Haar Cascades (no extras needed) |
| Object Detector | YOLOv3-tiny object detection (place model files in tools/object_detector/) |

### 🔧 Utility Tools
| Tool | Description |
|------|-------------|
| QR Code Generator | Generate QR codes from text/URLs with error correction options |
| QR Code Scanner | Decode QR codes from image files |
| Password Generator | Cryptographically secure passwords with custom options |
| Random Number Generator | Integer/Float/Crypto-secure random numbers |
| UUID Generator | UUID v1 and v4 generation |

### 📁 File Tools
| Tool | Description |
|------|-------------|
| File Hash Generator | MD5, SHA-1, SHA-256, SHA-512 hashes |
| Batch File Renamer | Rename files with prefix, suffix, numbering |
| File Size Analyzer | Visual tree view of folder sizes |
| Text File Merger | Merge multiple text files with optional headers |

### 🎬 Media Tools
| Tool | Description |
|------|-------------|
| MP4 → MP3 Converter | Extract audio from video (ffmpeg or moviepy) |
| Image Converter | Convert between PNG, JPEG, WEBP, BMP, etc. |
| Image Resizer | Batch resize with aspect ratio preservation |

### 🌐 Networking Tools
| Tool | Description |
|------|-------------|
| IP Info Lookup | Geolocation and ISP info for any IP |
| Website Status Checker | Bulk URL status check with response times |
| HTTP Request Tester | Full HTTP client (GET, POST, PUT, DELETE, etc.) |

### 💻 Developer Tools
| Tool | Description |
|------|-------------|
| JSON Formatter | Format, minify, and validate JSON |
| Base64 Encoder/Decoder | Standard and URL-safe Base64 |
| Timestamp Converter | Unix ↔ human-readable date conversion |

### 🔒 Security Tools
| Tool | Description |
|------|-------------|
| **Password Vault** | Fully encrypted password manager with master password, search, clipboard auto-clear |

---

## 🔐 Security Architecture

### Authentication
- Passwords hashed with **bcrypt** (cost factor 12+)
- No plaintext passwords ever stored

### Password Vault Encryption
```
Master Password (your login password)
         ↓
    PBKDF2HMAC (SHA-256, 480,000 iterations)
         ↓
    Fernet symmetric key
         ↓
    AES-128-CBC encrypted credentials in SQLite
```

- Master password is **never stored** — used only to derive the encryption key
- Stored passwords cannot be decrypted without the master password
- Clipboard **auto-clears** after 30 seconds

---

## 🗂 Project Structure

```
multitool_studio/
├── main.py                  # Entry point
├── requirements.txt
├── build.spec               # PyInstaller config
├── core/
│   ├── auth_manager.py      # bcrypt user authentication
│   ├── plugin_manager.py    # Auto-discovers tools
│   └── config.py            # Constants & colors
├── database/
│   └── database.py          # SQLite init & connection
├── services/
│   └── encryption_service.py # Fernet + PBKDF2 encryption
├── ui/
│   ├── main_window.py       # Main app window
│   ├── login_window.py      # Login/Register screen
│   ├── sidebar.py           # Category navigation
│   ├── dashboard.py         # Tool card grid
│   └── theme.py             # Dark stylesheet
└── tools/
    ├── qr_generator/        # Each tool is a self-contained module
    ├── password_vault/
    │   ├── vault_ui.py
    │   └── vault_service.py
    └── ...                  # 20+ tool modules
```

---

## 🔌 Plugin System

Add a new tool by creating a folder in `/tools`:

```python
# tools/my_tool/__init__.py
from .my_widget import MyTool

TOOL_META = {
    "id": "my_tool",
    "name": "My Custom Tool",
    "category": "utility",  # ai | utility | file | media | network | developer | security
    "widget_class": MyTool,
}
```

```python
# tools/my_tool/my_widget.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class MyTool(QWidget):
    name = "My Custom Tool"
    description = "Does something cool"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hello from My Tool!"))
```

Then register it in `ui/main_window.py`'s `_register_tools()`.

---

## 🏗 Building Executable (Windows)

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller build.spec --clean

# Output: dist/MultiToolStudio/MultiToolStudio.exe
```


---

## 🗄 Database Schema

```sql
-- Users table
CREATE TABLE users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password vault
CREATE TABLE password_vault (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL,
    service_name       TEXT NOT NULL,
    username           TEXT NOT NULL,
    encrypted_password BLOB NOT NULL,
    notes              TEXT,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## ⚠️ Notes on AI Tools

- **Face Reader / Age Estimator**: require `pip install deepface tf-keras` (large download ~500MB)
- **Object Detector**: download `yolov3-tiny.cfg` and `yolov3-tiny.weights` from the YOLO website and place in `tools/object_detector/`
- **Face Detector**: works out of the box via OpenCV Haar Cascades

---

## 📄 License

MIT License — free to use, modify, and distribute.
