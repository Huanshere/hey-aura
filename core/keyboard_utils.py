import time
import pyperclip
import platform
from pynput.keyboard import Key, Controller
from pynput import keyboard
from .i18n import _

_kbd_controller = Controller()

def type_text(text: str):
    """将文本粘贴到当前焦点处，支持跨平台（Windows、macOS）"""
    if not text:
        return
    try:
        pyperclip.copy(text)
        time.sleep(0.1)
        kbd = _kbd_controller
        modifier_key = Key.cmd if platform.system() == "Darwin" else Key.ctrl
        kbd.press(modifier_key)
        kbd.press('v')
        kbd.release('v')
        kbd.release(modifier_key)
    except Exception as e:
        print(_("→ Input failed: {}").format(e))


class FnKeyListener:
    """macOS Fn key listener"""
    def __init__(self, transcriber_instance):
        self.transcriber = transcriber_instance
        self.fn_pressed = False
        self.ctrl_pressed = False
        self.fn_press_time = None
        self.fn_delay = 0.2  # 200ms delay to wait for Control key
        self.debug = False # set to True to enable debug logs
        self.listeners_disabled = False  # Flag to disable listeners during meeting mode

    def setup_quartz_listener(self):
        """Setup Quartz Event Tap to listen for Fn and Control key combinations"""
        try:
            import Quartz
            from Quartz import CGEventTapCreate, kCGEventFlagsChanged, CGEventTapEnable, CFRunLoopGetMain, kCGSessionEventTap, kCGHeadInsertEventTap, CGEventMaskBit
            
            def event_callback(proxy, event_type, event, refcon):
                try:
                    # Get modifier key states using CGEventGetFlags
                    flags = Quartz.CGEventGetFlags(event)
                    
                    # Handle modifier key change events
                    if event_type == kCGEventFlagsChanged:
                        fn_pressed = (flags & 0x800000) != 0
                        ctrl_pressed = (flags & 0x40000) != 0  # Control key
                        
                        # Check if in meeting mode first - ignore all Fn key events
                        if hasattr(self.transcriber, 'meeting_recorder') and self.transcriber.meeting_recorder.meeting_mode:
                            if self.debug:
                                print("🚫 Fn key ignored - meeting mode active")
                            return event
                        
                        if self.debug:
                            print(f"🔍 Keyboard state: Fn={fn_pressed}, Ctrl={ctrl_pressed}, Recording={self.transcriber.rec}")
                        
                        # Detect Fn key press
                        if fn_pressed and not self.fn_pressed:
                            # Check if listeners are disabled or in meeting mode
                            if self.listeners_disabled:
                                if self.debug:
                                    print("🚫 Fn key ignored - listeners disabled")
                                return event
                            
                            self.fn_pressed = True
                            self.fn_press_time = time.time()
                            
                            # If Control is also pressed, enter command mode immediately
                            if ctrl_pressed and not self.transcriber.rec:
                                self.ctrl_pressed = True
                                self.transcriber.mode = 'command'
                                print(_("🪼 Command mode - Fn + Ctrl"))
                                self.transcriber.start_rec()
                        
                        # Detect Control key press while Fn is already pressed
                        elif fn_pressed and ctrl_pressed and self.fn_pressed and not self.ctrl_pressed and not self.transcriber.rec:
                            # Check if listeners are disabled (meeting mode)
                            if self.listeners_disabled:
                                if self.debug:
                                    print("🚫 Fn+Ctrl ignored - meeting mode active")
                                return event
                            
                            self.ctrl_pressed = True
                            # Cancel pending dictation mode, switch to command mode
                            self.transcriber.mode = 'command'
                            print(_("🪼 Command mode - Fn + Ctrl"))
                            self.transcriber.start_rec()
                        
                        # Detect Fn key held alone for delay time (dictation mode)
                        elif fn_pressed and not ctrl_pressed and self.fn_pressed and not self.ctrl_pressed and not self.transcriber.rec:
                            if self.fn_press_time and (time.time() - self.fn_press_time) >= self.fn_delay:
                                # Check if listeners are disabled (meeting mode)
                                if self.listeners_disabled:
                                    if self.debug:
                                        print("🚫 Fn dictation ignored - meeting mode active")
                                    return event
                                
                                self.transcriber.mode = 'dictation'
                                print(_("📝 Dictation mode - Fn key"))
                                self.transcriber.start_rec()
                        
                        # Stop recording when Fn key is released
                        elif not fn_pressed and self.fn_pressed:
                            self.fn_pressed = False
                            self.ctrl_pressed = False
                            self.fn_press_time = None
                            # Don't stop recording if listeners are disabled (meeting mode)
                            if not self.listeners_disabled and self.transcriber.rec:  # Only stop if recording and not in meeting mode
                                self.transcriber.stop_rec()
                        
                        # In command mode, releasing Control also stops recording
                        elif not ctrl_pressed and self.ctrl_pressed and self.transcriber.rec and self.transcriber.mode == 'command':
                            self.fn_pressed = False
                            self.ctrl_pressed = False
                            self.fn_press_time = None
                            # Don't stop recording if listeners are disabled (meeting mode)
                            if not self.listeners_disabled:
                                self.transcriber.stop_rec()
                            
                except Exception as e:
                    print(_("→ Keyboard listener error: {}").format(e))
                
                return event
            
            # Create event mask to only listen for modifier key changes (for Fn key detection)
            event_mask = CGEventMaskBit(kCGEventFlagsChanged)
            
            # Create event tap
            event_tap = CGEventTapCreate(kCGSessionEventTap, kCGHeadInsertEventTap, 0, event_mask, event_callback, None)
            
            if event_tap:
                # Create run loop source
                run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, event_tap, 0)
                # Add to run loop
                Quartz.CFRunLoopAddSource(CFRunLoopGetMain(), run_loop_source, Quartz.kCFRunLoopCommonModes)
                # Enable event tap
                CGEventTapEnable(event_tap, True)
                
                # Use loop to keep event loop running
                try:
                    while True:
                        # Check if event tap is still enabled
                        if not Quartz.CGEventTapIsEnabled(event_tap):
                            CGEventTapEnable(event_tap, True)
                            time.sleep(0.1)
                        
                        # Run event loop with timeout
                        Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 0.1, False)
                        
                        # Check for delayed dictation mode trigger
                        if (self.fn_pressed and not self.ctrl_pressed and 
                            not self.transcriber.rec and self.fn_press_time and 
                            (time.time() - self.fn_press_time) >= self.fn_delay):
                            self.transcriber.mode = 'dictation'
                            print(_("📝 Dictation mode - Fn key delayed trigger"))
                            self.transcriber.start_rec()
                        
                        time.sleep(0.01)  # Short sleep to avoid high CPU usage
                except KeyboardInterrupt:
                    print(_("→ Event listener stopped"))
                    CGEventTapEnable(event_tap, False)
            else:
                print(_("⚠️ Failed to create event listener"))
                print(_("⚠️ Please check: Add Terminal/Python to System Preferences > Security & Privacy > Privacy > Accessibility"))
                return False

        except Exception as e:
            print(_("⚠️ Quartz listener error: {}").format(e))
            return False
        
        return True


    def disable_all_listeners(self):
        """Disable all keyboard listeners during meeting mode"""
        self.listeners_disabled = True
        self.fn_pressed = False
        self.ctrl_pressed = False
        self.fn_press_time = None
    
    def enable_all_listeners(self):
        """Re-enable keyboard listeners after meeting mode"""
        self.listeners_disabled = False


class KeyboardEventHandler:
    """Keyboard event handler for detecting key combinations and controlling recording"""
    
    def __init__(self, transcriber_instance):
        self.transcriber = transcriber_instance
        
        # Key states
        self.ctrl = False
        self.win = False
        self.alt = False
        
        # Key debouncing
        self.last_key_time = 0
        self.key_combo_timeout = 0.5
        self.debug_keys = False
        
        # Meeting mode flag
        self.listeners_disabled = False

    def reset_key_states(self, reason=""):
        """Reset all key states"""
        if self.debug_keys and (self.ctrl or self.win or self.alt):
            print(f"🔄 Resetting key states ({reason}): Ctrl:{self.ctrl}, Win:{self.win}, Alt:{self.alt} -> False")
        self.ctrl = self.win = self.alt = False
        self.last_key_time = 0

    def check_key_combinations(self):
        """Check and handle key combinations"""
        if self.listeners_disabled or self.transcriber.rec:  # Don't trigger if disabled or already recording
            return
        
        # Debug output current key states
        if self.debug_keys:
            print(f"🔍 Checking key combos: Ctrl:{self.ctrl}, Win:{self.win}, Alt:{self.alt}")
        
        # Strict check: Must have correct combo pressed with no interfering keys
        # Dictation mode: Ctrl+Win (both must be pressed, Alt must not be)
        if self.ctrl and self.win and not self.alt:
            self.transcriber.mode = 'dictation'
            print(_("📝 Dictation mode - Combo confirmed: Ctrl+Win"))
            self.transcriber.start_rec()
        
        # Command mode: Win+Alt (both must be pressed, Ctrl must not be)
        elif self.win and self.alt and not self.ctrl:
            self.transcriber.mode = 'command'
            print(_("🪼 Command mode - Combo confirmed: Win+Alt"))
            self.transcriber.start_rec()

    def reset_old_keys(self, current_time):
        """Reset timed-out key states to prevent stuck keys"""
        # Reset keys if held too long (timeout)
        if current_time - self.last_key_time > self.key_combo_timeout:
            # Only reset if not currently recording and keys timed out
            if not self.transcriber.rec:
                self.reset_key_states("key timeout")

    def on_press(self, k):
        """Handle key press events"""
        # Skip if listeners are disabled
        if self.listeners_disabled:
            return
        
        # On Windows/Linux - detect Ctrl, Win and Alt keys
        # On Mac - Fn key detection handled by Quartz
        if platform.system() != "Darwin":
            current_time = time.time()
            
            # Update key states
            if k in [Key.ctrl_l, Key.ctrl_r]: 
                self.ctrl = True
                self.last_key_time = current_time
                if self.debug_keys: print(f"DEBUG: Ctrl pressed (Ctrl:{self.ctrl}, Win:{self.win}, Alt:{self.alt})")
            elif k in [Key.cmd, Key.cmd_l, Key.cmd_r]: 
                self.win = True
                self.last_key_time = current_time
                if self.debug_keys: print(f"DEBUG: Win pressed (Ctrl:{self.ctrl}, Win:{self.win}, Alt:{self.alt})")
            elif k in [Key.alt_l, Key.alt_r]: 
                self.alt = True
                self.last_key_time = current_time
                if self.debug_keys: print(f"DEBUG: Alt pressed (Ctrl:{self.ctrl}, Win:{self.win}, Alt:{self.alt})")
            
            # Immediately check for key combinations
            self.check_key_combinations()
            
            # Reset if single key held too long (prevent stuck keys)
            self.reset_old_keys(current_time)

    def on_release(self, k):
        """Handle key release events"""
        # Skip if listeners are disabled
        if self.listeners_disabled:
            return
        
        # Only process non-Mac systems (Mac uses Quartz for Fn key)
        if platform.system() != "Darwin":
            # Track which key was released
            released_key = None
            if k in [Key.ctrl_l, Key.ctrl_r]: 
                self.ctrl = False
                released_key = "ctrl"
            elif k in [Key.cmd, Key.cmd_l, Key.cmd_r]: 
                self.win = False
                released_key = "win"
            elif k in [Key.alt_l, Key.alt_r]: 
                self.alt = False
                released_key = "alt"
            
            # Only check stop conditions if part of combo was released during recording
            if released_key and self.transcriber.rec:
                # Check if current mode's shortcut is still held
                dictation_active = self.ctrl and self.win and not self.alt
                command_active = self.win and self.alt and not self.ctrl
                
                # Stop recording if all keys for current mode are released
                if not dictation_active and not command_active:
                    self.transcriber.stop_rec()
            
            # Reset states if all keys released (prevent stuck states)
            if not self.ctrl and not self.win and not self.alt and not self.transcriber.rec:
                self.reset_key_states("all keys released")

    def disable_all_listeners(self):
        """Disable all keyboard listeners during meeting mode"""
        # Stop processing keyboard events by setting a flag
        self.listeners_disabled = True
        self.reset_key_states("listeners disabled")
    
    def enable_all_listeners(self):
        """Re-enable keyboard listeners after meeting mode"""
        # Re-enable processing keyboard events
        self.listeners_disabled = False
    
    def start_keyboard_listener(self):
        """Start keyboard listener"""
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as l:
            l.join()


if __name__ == "__main__":
    print("Test starting - will paste to selected text field in 3s...")
    for _ in range(3):
        print(str(3-_)+"...",end=" ",flush=True)
        time.sleep(1)
    print("Starting paste...")
    type_text("Hello, World!")