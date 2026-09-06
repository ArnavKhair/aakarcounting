#!/usr/bin/env python3
import os
import sys


def main():
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from core.paths import OUTPUT_DIR

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    from gui import App

    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
