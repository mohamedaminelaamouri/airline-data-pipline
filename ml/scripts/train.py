from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath("src"))

from yno_ml.__main__ import main


if __name__ == "__main__":
    sys.argv = ["yno_ml", "train", *sys.argv[1:]]
    main()
