#!/usr/bin/env python3
"""
WordPress Poster GUI Launcher

This script launches the WordPress Poster GUI application.
"""

import os
import sys
from pathlib import Path

# Ensure the current directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import and run the GUI application
from gui.wp_poster_app import main

if __name__ == "__main__":
    main()
