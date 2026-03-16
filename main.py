"""
main.py — CryptoRadar entry point
"""
#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app import CryptoRadarApp


def main():
    start_minimized = "--minimized" in sys.argv
    app = CryptoRadarApp(start_minimized=start_minimized)
    sys.exit(app.run())


if __name__ == "__main__":
    main()