#!/usr/bin/env python3
"""
Claude Code Integration Module
==============================

This module provides seamless integration between Hey Aura's command mode and Claude AI 
assistant within the Cursor editor. It enables voice-activated AI code assistance through
platform-specific automation mechanisms.

Overview:
---------
The module implements two primary modes of operation:
1. Current Window Mode: Activates Claude in an already-open Cursor window
2. Project Opening Mode: Opens a specific project in Cursor and optionally activates Claude

Platform Implementation Details:
--------------------------------

macOS Implementation:
- Uses AppleScript via osascript for UI automation
- Activates Claude using Alt+C (Option+C) keyboard shortcut
  IMPORTANT: macOS users must configure this shortcut in Cursor:
  1. Open Cursor editor
  2. Go to Settings/Preferences
  3. Find Claude Code extension settings
  4. Set keyboard shortcut to Alt+C (Option+C)
- Direct window activation through application events
- Clipboard-based text input with Command+V paste
- Native macOS integration without additional dependencies

Windows Implementation:
- Uses PowerShell scripts with System.Windows.Forms for automation
- Terminal-based approach: creates new terminal and runs 'wsl claude'
- Requires WSL (Windows Subsystem for Linux) with claude CLI installed
- SendKeys API for keyboard simulation
- Process activation through MainWindowTitle detection

Key Functions:
--------------
1. is_cursor_active(): Checks if Cursor is the active window
2. execute_claude_in_current_cursor(input_text): Executes Claude in current window
3. open_cursor_with_claude(proj_path, input_text): Opens project and optionally activates Claude

Usage Examples:
---------------
Command Mode Integration (via command_mode.py):
- "claude_code|current|Fix this function" - Execute in current Cursor window
- "claude_code|hey-aura|Add error handling" - Open hey-aura project and execute
- "claude_code|my-project|" - Just open the project without Claude activation

Direct Python Usage:
```python
# Execute in current window
execute_claude_in_current_cursor("Refactor this code for better performance")

# Open project and execute
open_cursor_with_claude("~/projects/my-app", "Add unit tests for the API module")

# Just open project
open_cursor_with_claude("~/projects/my-app")
```

Requirements:
-------------
- macOS: Cursor app installed, cursor command in PATH
- Windows: Cursor app, WSL with claude CLI, PowerShell
- Both: pyperclip for clipboard operations

Technical Notes:
----------------
- Uses clipboard for text transfer to ensure special characters are preserved
- Implements delays between operations for UI responsiveness
- Error handling for missing commands and failed automations
- Platform detection for appropriate automation strategy selection
"""

import subprocess as sp, time, shutil, platform
from pathlib import Path
import pyperclip as pc

def is_cursor_active():
    """Check if Cursor is the currently active window - delegates to get_active_window module"""
    # Import here to avoid circular import
    from core.get_active_window import is_cursor_active as check_cursor
    return check_cursor()

def execute_claude_in_current_cursor(input_text):
    """Execute Claude Code in currently active Cursor window"""
    if not is_cursor_active():
        return False
    
    if platform.system() == "Darwin":
        # macOS: Use Alt+C shortcut to activate Claude
        script = '''tell app "System Events"
key code 8 using {option down}
end tell'''
        sp.run(["osascript", "-e", script])
        
        # Paste and submit text
        if input_text:
            time.sleep(3)
            pc.copy(input_text)
            script_input = '''tell app "System Events"
keystroke "v" using {command down}
delay 0.5
key code 36
end tell'''
            sp.run(["osascript", "-e", script_input])
    
    elif platform.system() == "Windows":
        # Windows: Use SendKeys to activate Claude and input text
        ps_script = '''Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("^+p")
sleep -m 500
[System.Windows.Forms.SendKeys]::SendWait("Terminal: Create New Terminal")
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
sleep -m 1000
[System.Windows.Forms.SendKeys]::SendWait("wsl claude")
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")'''
        
        sp.run(["powershell", "-Command", ps_script], stderr=sp.DEVNULL)
        
        if input_text:
            time.sleep(2)
            pc.copy(input_text)
            ps_input = '''Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
sleep -m 200
[System.Windows.Forms.SendKeys]::SendWait("^v")
sleep -m 200
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")'''
            sp.run(["powershell", "-Command", ps_input], stderr=sp.DEVNULL)
    
    return True

def open_cursor_with_claude(proj_path=None, input_text=None):
    """Open project in Cursor, only start claude if input text provided"""
    
    # Project path configuration
    project = Path(proj_path or f"~/Desktop/hey_aura").expanduser()
    
    # Check command
    if not shutil.which("cursor"):
        cmd = "Ctrl+Shift+P → 'Install cursor command'" if platform.system() == "Windows" else "⌘⇧P → 'Install cursor to shell'"
        raise SystemExit(f"Cursor command not found. In Cursor, press {cmd}")
    
    # Only check claude command if input text provided
    if input_text and platform.system() != "Windows" and not shutil.which("claude"):
        raise SystemExit("Claude command not found. Please run: npm install -g @anthropic-ai/claude-code")
    
    # Open Cursor
    sp.Popen(["cursor", str(project)], shell=(platform.system() == "Windows"))
    time.sleep(2)
    
    # Only automate if input text provided
    if input_text:
        {"Windows": lambda: _automate_windows(input_text), "Darwin": lambda: _automate_macos(input_text)}.get(platform.system(), lambda: print("→ Automation not supported on this OS"))()

def _automate_windows(input_text):
    """Windows automation - only called when input text provided"""
    ps_base = '''Add-Type -AssemblyName System.Windows.Forms,Microsoft.VisualBasic
$c=Get-Process Cursor -EA 0|?{$_.MainWindowTitle}|select -First 1
if($c){[Microsoft.VisualBasic.Interaction]::AppActivate($c.Id);sleep -m 500;[System.Windows.Forms.SendKeys]::SendWait("^+p");sleep -m 500;[System.Windows.Forms.SendKeys]::SendWait("^v");sleep -m 300;[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")}'''
    
    ps_cmd = '''Add-Type -AssemblyName System.Windows.Forms,Microsoft.VisualBasic
$c=Get-Process Cursor -EA 0|?{$_.MainWindowTitle}|select -First 1
if($c){[Microsoft.VisualBasic.Interaction]::AppActivate($c.Id);sleep -m 500;[System.Windows.Forms.SendKeys]::SendWait("^v");sleep -m 200;[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")}'''
    
    ps_input = '''Add-Type -AssemblyName System.Windows.Forms,Microsoft.VisualBasic
$c=Get-Process Cursor -EA 0|?{$_.MainWindowTitle}|select -First 1
if($c){[Microsoft.VisualBasic.Interaction]::AppActivate($c.Id);sleep -m 1000;[System.Windows.Forms.SendKeys]::SendWait("{ENTER}");sleep -m 200;[System.Windows.Forms.SendKeys]::SendWait("^v");sleep -m 200;[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")}'''
    
    tmp = Path.cwd() / "tmp_cursor.ps1"
    try:
        # Create terminal
        pc.copy("Terminal: Create New Terminal")
        tmp.write_text(ps_base, encoding='utf-8')
        sp.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(tmp)], check=True, stderr=sp.DEVNULL)
        time.sleep(1)
        
        # Run claude
        pc.copy("wsl claude")
        tmp.write_text(ps_cmd, encoding='utf-8')
        sp.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(tmp)], check=True, stderr=sp.DEVNULL)
        
        # Auto input text
        time.sleep(2)
        pc.copy(input_text)
        tmp.write_text(ps_input, encoding='utf-8')
        sp.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(tmp)], check=True, stderr=sp.DEVNULL)
    finally:
        tmp.unlink(missing_ok=True)

def _automate_macos(input_text):
    """macOS automation - only called when input text provided"""
    # Wait for Cursor to fully open
    time.sleep(5)
    
    # Activate Cursor window and use ALT+C shortcut to open Claude
    script = '''tell application "Cursor" to activate
delay 0.5
tell app "System Events"
key code 8 using {option down}
end tell'''
    sp.run(["osascript", "-e", script])
    
    # Paste and submit text
    time.sleep(3)
    pc.copy(input_text)
    script_input = '''tell app "System Events"
keystroke "v" using {command down}
delay 0.5
key code 36
end tell'''
    sp.run(["osascript", "-e", script_input])

if __name__ == "__main__":
    import platform
    open_cursor_with_claude("~/Desktop/hey-aura")
