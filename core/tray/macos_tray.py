import time
import threading
import math
import platform
import json
import os
from core.i18n import _

if platform.system() == 'Darwin':
    import objc
    from PyObjCTools import AppHelper
    from AppKit import (
        NSApplication, NSBezierPath, NSColor,
        NSGraphicsContext, NSImage, NSMenu,
        NSMenuItem, NSObject, NSPoint, NSRect,
        NSSize, NSStatusBar, NSSquareStatusItemLength,
        NSCompositeClear
    )


class MacOSTrayAnimator(NSObject):
    def __new__(cls):
        return cls.alloc().init()
    
    def init(self):
        self = objc.super(MacOSTrayAnimator, self).init()
        if self is None:
            return None
        
        # Load config file
        config_path = os.path.join(os.path.dirname(__file__), "icon_config_macos.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.app = None
        self.statusbar = None
        self.frame = 0
        self.status = "idle"
        self.run = False
        self.quit_callback = None
        self.animation_thread = None
        self.menu_delegate = None
        self.meeting_callback = None
        self.meeting_recording = False
        
        # Cache config values
        self.icon_width = self.config['icon_size']['width']
        self.icon_height = self.config['icon_size']['height']
        self.transform_matrix = self.config['transform_matrix']
        self.animation_config = self.config['animation']
        
        return self
    
    def apply_transform(self, x, y, tx, ty):
        """Apply SVG matrix transformation"""
        m = self.transform_matrix
        new_x = m['a'] * x + m['c'] * y + tx
        new_y = m['b'] * x + m['d'] * y + ty
        return new_x, self.icon_height - new_y  # Flip Y axis
    
    def draw_main_path(self, alpha=1.0):
        """Draw main shape"""
        NSColor.colorWithCalibratedWhite_alpha_(0.0, alpha).set()
        
        path = NSBezierPath.bezierPath()
        points = self.config['main_path']['points']
        
        for point in points:
            if point['type'] == 'move':
                path.moveToPoint_(NSPoint(point['x'], self.icon_height - point['y']))
            elif point['type'] == 'curve':
                path.curveToPoint_controlPoint1_controlPoint2_(
                    NSPoint(point['x'], self.icon_height - point['y']),
                    NSPoint(point['cp1_x'], self.icon_height - point['cp1_y']),
                    NSPoint(point['cp2_x'], self.icon_height - point['cp2_y'])
                )
        
        path.closePath()
        path.fill()
    
    def draw_cutouts(self):
        """Draw cutout shapes"""
        NSGraphicsContext.currentContext().setCompositingOperation_(NSCompositeClear)
        
        for cutout in self.config['cutouts']:
            cx, cy = self.apply_transform(
                cutout['radius'],
                cutout['radius'],
                cutout['tx'],
                cutout['ty']
            )
            
            # Apply offset
            offset = cutout['offset']
            cx -= offset
            cy += offset
            
            radius = cutout['radius'] + 0.1  # Slightly enlarge radius to ensure complete cutout
            cutout_path = NSBezierPath.bezierPathWithOvalInRect_(NSRect(
                (cx - radius, cy - radius),
                (radius * 2, radius * 2)
            ))
            cutout_path.fill()
        
        # Restore normal drawing mode
        NSGraphicsContext.currentContext().setCompositingOperation_(1)
    
    def draw_dots(self, state_config, processing_state=None):
        """Draw decorative dots"""
        dots_config = self.config['dots']
        
        for row_name, row_dots in dots_config.items():
            row_state = state_config['dots'][row_name]
            
            # Check visibility
            visible = row_state['visible']
            if isinstance(visible, str):
                # Handle conditional expression
                if processing_state is not None:
                    visible = eval(visible, {'state': processing_state})
                else:
                    visible = True
            
            if not visible:
                continue
            
            # Set alpha
            alpha = row_state['alpha']
            if alpha == 'breathing':
                alpha = self.calculate_breathing_alpha()
            
            NSColor.colorWithCalibratedWhite_alpha_(0.0, alpha).set()
            
            # Draw all dots in this row
            for dot in row_dots:
                if dot.get('transform', False):
                    # Apply transformation
                    cx, cy = self.apply_transform(
                        dot['radius'],
                        dot['radius'],
                        dot['tx'],
                        dot['ty']
                    )
                    
                    circle = NSBezierPath.bezierPathWithOvalInRect_(NSRect(
                        (cx - dot['radius'], cy - dot['radius']),
                        (dot['radius'] * 2, dot['radius'] * 2)
                    ))
                    circle.fill()
                else:
                    # No transformation needed (ellipse)
                    if dot['type'] == 'ellipse':
                        ellipse = NSBezierPath.bezierPathWithOvalInRect_(NSRect(
                            (dot['x'] - dot['rx'], self.icon_height - dot['y'] - dot['ry']),
                            (dot['rx'] * 2, dot['ry'] * 2)
                        ))
                        ellipse.fill()
    
    def calculate_breathing_alpha(self):
        """Calculate breathing effect alpha"""
        anim = self.animation_config
        alpha = (anim['breathing_min_alpha'] + anim['breathing_max_alpha']) / 2
        amplitude = (anim['breathing_max_alpha'] - anim['breathing_min_alpha']) / 2
        return alpha + amplitude * math.sin(self.frame * anim['breathing_speed'])
    
    def create_icon(self, status):
        """Create icon for specified status"""
        image = NSImage.alloc().initWithSize_(NSSize(self.icon_width, self.icon_height))
        image.lockFocus()
        
        # Clear background
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(NSRect((0, 0), (self.icon_width, self.icon_height)))
        
        state_config = self.config['states'][status]
        
        # Draw main shape
        main_alpha = state_config['main_path']['alpha']
        if main_alpha == 'breathing':
            main_alpha = self.calculate_breathing_alpha()
        self.draw_main_path(main_alpha)
        
        # Draw cutouts
        self.draw_cutouts()
        
        # Draw decorative dots
        processing_state = None
        if status == 'processing':
            # Calculate processing state (0, 1, 2 cycle)
            processing_state = (self.frame // self.animation_config['state_switch_frames']) % 3
        
        self.draw_dots(state_config, processing_state)
        
        image.unlockFocus()
        image.setTemplate_(True)  # Set as template image for dark mode support
        return image
    
    def update_icon(self):
        """Update icon"""
        if not self.statusbar:
            return
        
        icon = self.create_icon(self.status)
        
        # Get button and set icon
        button = self.statusbar.button()
        if button:
            button.setImage_(icon)
        self.frame += 1
    
    def animate(self):
        """Animation loop"""
        while self.run:
            if self.status in ["recording", "processing"]:
                # Use AppHelper.callAfter to ensure UI updates run on main thread
                AppHelper.callAfter(self.update_icon)
            time.sleep(self.animation_config['frame_interval'])
    
    def start_animation(self):
        """Start animation"""
        if not self.animation_thread or not self.animation_thread.is_alive():
            self.run = True
            self.animation_thread = threading.Thread(target=self.animate, daemon=True)
            self.animation_thread.start()
    
    def stop_animation(self):
        """Stop animation"""
        self.run = False
    
    def set_status(self, status):
        """Set status"""
        self.status = status
        if status == "idle":
            # Ensure UI update runs on main thread
            AppHelper.callAfter(self.update_icon)
    
    def quitAction_(self, sender):
        """Quit action"""
        _ = sender  # Avoid unused parameter warning
        if self.quit_callback:
            self.quit_callback()
        self.stop_animation()
        NSApplication.sharedApplication().terminate_(None)
    
    def setup_tray(self, quit_callback):
        """Setup tray"""
        # Ensure NSApplication is initialized on main thread
        self.app = NSApplication.sharedApplication()
        self.quit_callback = quit_callback
        
        # Create status bar item
        self.statusbar = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
        
        # Use button API to set icon and tooltip
        button = self.statusbar.button()
        if button:
            button.setImage_(self.create_icon("idle"))
            button.setToolTip_(_("Hey Aura"))
        
        # Create menu
        menu = NSMenu.alloc().init()
        
        # 标题项
        title_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Hey Aura"), None, "")
        title_item.setEnabled_(False)
        menu.addItem_(title_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # 快捷键提示
        shortcut_item1 = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Fn Key Dictation Mode"), None, "")
        shortcut_item1.setEnabled_(False)
        menu.addItem_(shortcut_item1)
        
        shortcut_item2 = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Fn + Ctrl Command Mode"), None, "")
        shortcut_item2.setEnabled_(False)
        menu.addItem_(shortcut_item2)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # 退出项
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Quit"), "quitAction:", "")
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)
        
        self.statusbar.setMenu_(menu)
    
    def setup_tray_with_meeting(self, meeting_callback, quit_callback):
        """Setup tray with meeting recording option"""
        # Ensure NSApplication is initialized on main thread
        self.app = NSApplication.sharedApplication()
        self.meeting_callback = meeting_callback
        self.quit_callback = quit_callback
        
        # Create status bar item
        self.statusbar = NSStatusBar.systemStatusBar().statusItemWithLength_(NSSquareStatusItemLength)
        
        # Use button API to set icon and tooltip
        button = self.statusbar.button()
        if button:
            button.setImage_(self.create_icon("idle"))
            button.setToolTip_(_("Hey Aura"))
        
        self._update_meeting_menu()
    
    def _update_meeting_menu(self):
        """Update menu with current meeting state"""
        menu = NSMenu.alloc().init()
        
        # Title item
        title_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Hey Aura"), None, "")
        title_item.setEnabled_(False)
        menu.addItem_(title_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Meeting recording item
        meeting_text = _("Stop Meeting Recording") if self.meeting_recording else _("Start Meeting Recording")
        meeting_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(meeting_text, "meetingAction:", "")
        meeting_item.setTarget_(self)
        menu.addItem_(meeting_item)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Shortcut hints
        shortcut_item1 = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Fn Key Dictation Mode"), None, "")
        shortcut_item1.setEnabled_(False)
        menu.addItem_(shortcut_item1)
        
        shortcut_item2 = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Fn + Ctrl Command Mode"), None, "")
        shortcut_item2.setEnabled_(False)
        menu.addItem_(shortcut_item2)
        
        menu.addItem_(NSMenuItem.separatorItem())
        
        # Quit item
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(_("Quit"), "quitAction:", "")
        quit_item.setTarget_(self)
        menu.addItem_(quit_item)
        
        if self.statusbar:
            self.statusbar.setMenu_(menu)
    
    def update_meeting_menu(self, is_recording):
        """Update menu to reflect meeting recording state"""
        self.meeting_recording = is_recording
        self._update_meeting_menu()
    
    @objc.selector
    def meetingAction_(self, sender):
        """Handle meeting recording action"""
        if self.meeting_callback:
            self.meeting_callback()
    
    def run_tray(self):
        """运行托盘（在主线程）"""
        # 确保应用程序类型设置正确
        if self.app:
            self.app.setActivationPolicy_(1)  # NSApplicationActivationPolicyAccessory
        AppHelper.runEventLoop()


# 使用示例
if __name__ == "__main__":
    def test_quit():
        print("Quitting...")
    
    animator = MacOSTrayAnimator.new()
    animator.setup_tray(test_quit)
    
    # 测试动画
    animator.start_animation()
    
    # 测试状态切换
    def cycle_states():
        states = ["idle", "recording", "processing"]
        current = 0
        while True:
            time.sleep(3)
            current = (current + 1) % len(states)
            animator.set_status(states[current])
            print(f"Status changed to: {states[current]}")
    
    # 启动状态循环线程
    state_thread = threading.Thread(target=cycle_states, daemon=True)
    state_thread.start()
    
    # 运行托盘
    animator.run_tray()