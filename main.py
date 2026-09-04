#!/usr/bin/env python3
import os
import sys


def main():
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
        os.chdir(app_dir)
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    os.makedirs("Output", exist_ok=True)

    from gui import App

    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
