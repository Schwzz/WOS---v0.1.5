"""WOS-Overlay desktop window.

Opens the overlay UI as a small frameless, always-on-top window (pywebview)
that talks to the running WOS terminal. It does not run WOS itself: start WOS
with `python start.py --overlay` (run.bat does both).

Usage:
    python overlay/main.py            # desktop window (needs pywebview)
    python overlay/main.py --browser  # open in the default browser instead
    python overlay/main.py --debug    # desktop window with dev tools
If pywebview is not installed the browser is used automatically.
"""
import json
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Written by core/overlay.py when WOS starts with --overlay.
ENDPOINT = ROOT / "data" / "overlay_endpoint.json"
WIDTH, HEIGHT, EXPANDED_HEIGHT = 380, 480, 720
WAIT_SECONDS = 90

_window = None   # module level; storing it on the js_api object confuses pywebview
_height = HEIGHT


def read_endpoint():
    """The port and token of the running WOS, or None."""
    try:
        data = json.loads(ENDPOINT.read_text("utf-8"))
    except (OSError, ValueError):
        return None

    if (
        isinstance(data, dict)
        and type(data.get("port")) is int
        and isinstance(data.get("token"), str)
    ):
        return data

    return None


def is_running(port):
    """True if a WOS overlay server answers on this port."""
    try:
        url = f"http://127.0.0.1:{port}/api/ping"

        with urllib.request.urlopen(url, timeout=2) as response:
            return json.load(response).get("app") == "WOS-Overlay"
    except Exception:
        return False


def wait_for_backend(seconds=WAIT_SECONDS):
    """Wait for the WOS terminal to publish a live endpoint."""
    deadline = time.monotonic() + seconds
    announced = False

    while time.monotonic() < deadline:
        endpoint = read_endpoint()

        if endpoint and is_running(endpoint["port"]):
            return endpoint

        if not announced:
            print("Waiting for the WOS terminal (start.py --overlay)...")
            announced = True

        time.sleep(0.5)

    return None


class Api:
    """Methods here are callable from JS as pywebview.api.<name>()."""

    def close(self):
        if _window:
            _window.destroy()

    def minimize(self):
        if _window:
            _window.minimize()

    def get_endpoint(self):
        """Fresh token after a WOS /restart (the port stays the same)."""
        endpoint = read_endpoint()
        return {"token": endpoint["token"]} if endpoint else None

    def set_expanded(self, expanded):
        """Grow the window upward for the chat view, shrink it back for the
        avatar-only view, keeping the bottom edge where it is."""
        global _height

        if not _window:
            return

        height = EXPANDED_HEIGHT if expanded else HEIGHT

        try:
            y = max(0, _window.y - (height - _height))
            _window.resize(WIDTH, height)
            _window.move(_window.x, y)
            _height = height
        except Exception:
            pass


def main(argv):
    global _window

    endpoint = wait_for_backend()

    if endpoint is None:
        print("The WOS terminal did not start in time. Run run.bat again.")
        return 1

    url = f"http://127.0.0.1:{endpoint['port']}/#{endpoint['token']}"

    if "--browser" in argv:
        webbrowser.open(url)
        return 0

    try:
        import webview
    except ImportError:
        print("pywebview is not installed (pip install pywebview).")
        print("Opening in your browser instead.")
        webbrowser.open(url)
        return 0

    x = y = None

    try:  # bottom-right corner, above the taskbar
        screen = webview.screens[0]
        x = screen.width - WIDTH - 32
        y = screen.height - HEIGHT - 72
    except Exception:
        pass

    _window = webview.create_window(
        "WOS Overlay",
        url,
        js_api=Api(),
        width=WIDTH,
        height=HEIGHT,
        x=x,
        y=y,
        frameless=True,
        easy_drag=True,   # drag the window by any non-button area
        on_top=True,
        resizable=False,
        background_color="#000000",
    )
    webview.start(debug="--debug" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
