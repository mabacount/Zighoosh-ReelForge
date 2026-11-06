"""
Zighoosh ReelForge (P-09)
کارخانه ساخت ریلز زیگهوش - نسخه ایران اویل جاب
نقطه ورود اصلی برنامه
"""

import logging
import os
import sys
from pathlib import Path

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Ensure Windows C-extension DLL paths are registered for Python 3.8+
if os.name == "nt":
    py_dir = Path(sys.prefix)
    torch_lib = py_dir / "Lib" / "site-packages" / "torch" / "lib"
    if torch_lib.exists():
        try:
            os.add_dll_directory(str(torch_lib))
        except Exception:
            pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from ui.main_window import run_app

if __name__ == "__main__":
    run_app()
