"""Allow running minigit as a module: python -m minigit."""

import sys
from minigit.cli import main

if __name__ == "__main__":
    sys.exit(main())

