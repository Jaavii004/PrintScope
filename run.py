import sys
import os

# Add the current directory to sys.path to ensure printscope package is found
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from printscope.main import main

if __name__ == "__main__":
    main()
