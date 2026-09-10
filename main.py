#!/usr/bin/env python3
"""Vehicle Counting AI — Entry point.

Starts the FastAPI server and opens the browser.
"""
import os
import signal
import socket
import sys
import threading
import time
import webbrowser


def find_free_port(default=8080):
    """Find a free port, starting with the default."""
    for port in [default] + range(default + 1, default + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    raise RuntimeError("No free port found")


def wait_for_server(port, timeout=10):
    """Wait until the server is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def main():
    # Set working directory to project root
    if getattr(sys, "frozen", False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # Ensure output directory exists
    from core.paths import OUTPUT_DIR
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Find a free port
    port = find_free_port()

    print(f"Vehicle Counting AI")
    print(f"Starting server at http://localhost:{port}")
    print(f"Press Ctrl+C to stop.\n")

    # Start server in a background thread
    server_thread = threading.Thread(
        target=_run_server,
        args=(port,),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to be ready
    if not wait_for_server(port):
        print("Warning: Server may not be ready yet, opening browser anyway...")

    # Open browser
    webbrowser.open(f"http://localhost:{port}")

    # Keep main thread alive until Ctrl+C
    _wait_for_exit()


def _run_server(port):
    """Run the FastAPI server (blocking call)."""
    import uvicorn
    from server import app

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server.run()


def _wait_for_exit():
    """Keep the main thread alive, handling Ctrl+C gracefully."""
    shutdown_event = threading.Event()

    def signal_handler(sig, frame):
        print("\nShutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        while not shutdown_event.is_set():
            shutdown_event.wait(timeout=1)
    except KeyboardInterrupt:
        pass

    print("Goodbye.")


if __name__ == "__main__":
    main()
