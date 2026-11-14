"""Start the always-on-top strip (needs the tool running: run_stirtool.py)."""
import sys

from stirtool.strip import main

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8791)
