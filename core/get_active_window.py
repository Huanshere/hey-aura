import platform
import subprocess as sp


def get_active_window():
    """get current active window/application name, cross-platform simplified version"""
    try:
        sys = platform.system()
        if sys == "Darwin":
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            return sp.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip() or "Unknown"
        elif sys == "Windows":
            import win32gui, win32process, psutil
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            name = psutil.Process(pid).name()
            return f"{name} - {title}" if title else name
        else:
            return "Unknown"
    except:
        return "Unknown"

def is_cursor_active():
    """Check if Cursor is the currently active window"""
    active_window = get_active_window()
    # On Windows, Cursor might appear as "Code" process or in the window title
    # Check both process name and window title
    active_lower = active_window.lower()
    return "cursor" in active_lower or "code" in active_lower