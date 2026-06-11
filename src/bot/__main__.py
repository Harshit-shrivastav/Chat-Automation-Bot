"""Allow running as: python -m src.bot"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from main import main

if __name__ == "__main__":
    main()