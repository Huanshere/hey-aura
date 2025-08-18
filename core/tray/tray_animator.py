import time
import threading
import math
import platform
from core.i18n import _

system = platform.system()
if system == "Darwin":  # macOS
    from core.tray.macos_tray import MacOSTrayAnimator as PlatformTrayAnimator
else:  # Windows
    import pystray
    from PIL import Image, ImageDraw
    PlatformTrayAnimator = None


class TrayAnimator:
    def __init__(self):
        # Use macOS implementation if available
        if system == "Darwin" and PlatformTrayAnimator:
            self._impl = PlatformTrayAnimator()
        else:
            self._impl = None
            self.icon,self.frame,self.status,self.th,self.run=None,0,"idle",None,False
            self.meeting_callback = None
            self.meeting_recording = False
            self.icon_lock = threading.Lock()  # Add lock for thread-safe icon updates
        
    def create_idle_icon(self):
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Create modern microphone icon
        # Microphone body - rounded rectangle
        draw.rounded_rectangle([24, 16, 40, 36], radius=8, fill=(70, 130, 180, 220))
        
        # Microphone stand
        draw.rectangle([30, 36, 34, 44], fill=(70, 130, 180, 220))
        
        # Microphone base
        draw.ellipse([26, 44, 38, 48], fill=(70, 130, 180, 220))
        
        # Add highlight effect
        draw.ellipse([26, 18, 30, 22], fill=(255, 255, 255, 100))
        
        return img
        
    def create_recording_icon(self, f):
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Pulsing red dot that changes size over time
        base_size = 16
        pulse_size = 8 * math.sin(f * 0.3)
        radius = base_size + pulse_size
        
        # Red dot
        draw.ellipse([32 - radius, 32 - radius, 32 + radius, 32 + radius], 
                    fill=(255, 50, 50, 220))
        
        # Inner highlight effect
        inner_radius = radius * 0.3
        draw.ellipse([32 - inner_radius, 32 - inner_radius, 32 + inner_radius, 32 + inner_radius], 
                    fill=(255, 150, 150, 150))
        
        return img
        
    def create_processing_icon(self, f):
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Smooth rotating animation for processing state
        for i in range(8):
            angle = i * math.pi / 4 + f * 0.15
            x = 32 + 18 * math.cos(angle)
            y = 32 + 18 * math.sin(angle)
            
            # Gradient opacity effect
            alpha = int(100 + 155 * (1 + math.sin(angle - f * 0.15)) / 2)
            size = 3 + 2 * math.sin(f * 0.1 + i)
            
            draw.ellipse([x - size, y - size, x + size, y + size], 
                        fill=(50, 150, 255, alpha))
        
        return img
    
    def create_meeting_icon(self, f):
        """Create meeting recording icon with pulsing effect"""
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Meeting icon - multiple dots for participants
        center_x, center_y = 32, 32
        base_radius = 8
        
        # Main recording indicator (center)
        pulse = abs(math.sin(f * 0.2))
        main_radius = base_radius + 4 * pulse
        draw.ellipse([center_x - main_radius, center_y - main_radius,
                     center_x + main_radius, center_y + main_radius],
                    fill=(255, 70, 70, 220))
        
        # Participant dots around
        for i in range(4):
            angle = i * math.pi / 2 + f * 0.05
            x = center_x + 20 * math.cos(angle)
            y = center_y + 20 * math.sin(angle)
            dot_radius = 4 + 2 * math.sin(f * 0.15 + i)
            alpha = int(150 + 50 * math.sin(f * 0.1 + i))
            draw.ellipse([x - dot_radius, y - dot_radius,
                         x + dot_radius, y + dot_radius],
                        fill=(100, 150, 200, alpha))
        
        return img
    
    def create_speaking_icon(self, f):
        """Create TTS playback icon with sound wave effect"""
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw speaker icon
        # Speaker body
        draw.polygon([(20, 28), (28, 24), (28, 40), (20, 36)], fill=(34, 139, 34, 220))
        draw.rectangle([16, 30, 20, 34], fill=(34, 139, 34, 220))
        
        # Sound wave lines with animation
        for i in range(3):
            wave_alpha = int(100 + 100 * math.sin(f * 0.2 + i * 0.8))
            radius = 8 + i * 4
            thickness = 2
            
            # Draw wave arcs
            for angle_offset in range(-30, 31, 10):
                angle1 = math.radians(-30 + angle_offset)
                angle2 = math.radians(-20 + angle_offset)
                
                x1 = 32 + radius * math.cos(angle1)
                y1 = 32 + radius * math.sin(angle1)
                x2 = 32 + radius * math.cos(angle2)
                y2 = 32 + radius * math.sin(angle2)
                
                draw.line([(x1, y1), (x2, y2)], fill=(34, 139, 34, wave_alpha), width=thickness)
        
        return img
        
    def update_icon(self):
        if self._impl:
            return self._impl.update_icon()
            
        if self.status == "recording":
            img = self.create_recording_icon(self.frame)
        elif self.status == "processing":
            img = self.create_processing_icon(self.frame)
        elif self.status == "speaking":
            img = self.create_speaking_icon(self.frame)
        else:
            img = self.create_idle_icon()
        
        # Thread-safe icon update with exception handling
        try:
            with self.icon_lock:
                if self.icon:
                    self.icon.icon = img
        except (OSError, AttributeError) as e:
            # Ignore Windows cursor handle errors and continue
            if "1402" not in str(e):
                print(f"Tray icon update error (ignored): {e}")
        
        # Only increment frame counter in animated states
        if self.status in ["recording", "processing", "speaking"]:
            self.frame+=1
        
    def animate(self):
        while self.run:
            self.status in["recording","processing","speaking"]and self.update_icon()
            time.sleep(0.1)
            
    def start_animation(self):
        if self._impl:
            return self._impl.start_animation()
        
        if not self.th or not self.th.is_alive():
            self.run=True
            self.th=threading.Thread(target=self.animate,daemon=True)
            self.th.start()
            
    def stop_animation(self):
        if self._impl:
            return self._impl.stop_animation()
        self.run=False
        
    def set_status(self,s):
        if self._impl:
            return self._impl.set_status(s)
        
        self.status=s
        # Update icon immediately regardless of state with error handling
        try: self.update_icon()
        except Exception: pass
        
        # Reset frame counter for idle state
        if s == "idle":
            self.frame = 0
    
    def force_reset_to_idle(self):
        """Force reset to idle state to ensure correct icon display"""
        if self._impl:
            return self._impl.force_reset_to_idle()
        
        self.status = "idle"
        self.frame = 0
        self.update_icon()
            
    def setup_tray(self,quit_cb):
        if self._impl:
            return self._impl.setup_tray(quit_cb)
        
        # Adjust shortcut hints based on platform
        if system == "Darwin":
            shortcut_text1 = _("Fn Key Dictation Mode")
            shortcut_text2 = _("Fn + Ctrl Command Mode")
        else:
            shortcut_text1 = _("Ctrl+Win dictation")
            shortcut_text2 = _("Win+Alt command mode")
        
        menu=pystray.Menu(
            pystray.MenuItem(_("Hey Aura Voice Assistant"), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(shortcut_text1, None, enabled=False),
            pystray.MenuItem(shortcut_text2, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_("Quit"), lambda icon, item: quit_cb())
        )
        self.icon=pystray.Icon("voice_transcriber",self.create_idle_icon(),_("Hey Aura"),menu)
    
    def setup_tray_with_meeting(self, meeting_callback, quit_callback):
        """Setup tray with meeting recording option"""
        if self._impl:
            return self._impl.setup_tray_with_meeting(meeting_callback, quit_callback)
        
        self.meeting_callback = meeting_callback
        self.quit_callback = quit_callback
        self._update_meeting_menu()
    
    def _update_meeting_menu(self):
        """Update menu with current meeting state"""
        if system == "Darwin":
            shortcut_text1 = _("Fn Key Dictation Mode")
            shortcut_text2 = _("Fn + Ctrl Command Mode")
        else:
            shortcut_text1 = _("Ctrl+Win dictation")
            shortcut_text2 = _("Win+Alt command mode")
        
        meeting_text = _("Stop Meeting Recording") if self.meeting_recording else _("Start Meeting Recording")
        
        menu = pystray.Menu(
            pystray.MenuItem(_("Hey Aura Voice Assistant"), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(meeting_text, lambda icon, item: self.meeting_callback()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(shortcut_text1, None, enabled=False),
            pystray.MenuItem(shortcut_text2, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(_("Quit"), lambda icon, item: self.quit_callback())
        )
        
        if self.icon:
            self.icon.menu = menu
        else:
            self.icon = pystray.Icon("voice_transcriber", self.create_idle_icon(), _("Hey Aura"), menu)
    
    def update_meeting_menu(self, is_recording):
        """Update menu to reflect meeting recording state"""
        if self._impl:
            return self._impl.update_meeting_menu(is_recording)
        
        self.meeting_recording = is_recording
        self._update_meeting_menu()
    
    def run_tray(self):
        if self._impl:
            return self._impl.run_tray()
        self.icon and self.icon.run()