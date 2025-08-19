#!/usr/bin/env python3
import sys,numpy as np,yaml,tempfile,os,subprocess,shutil,platform
from pathlib import Path

def test_silero_vad():
    print("\n=== Testing Silero VAD ===")
    from core.audio_utils import SileroVAD
    vad = SileroVAD()
    vad.initialize()
    if not vad.model:
        raise RuntimeError("VAD model failed to load")
    ts = vad.get_speech_timestamps(np.random.randn(16000).astype(np.float32))
    print(f"✅ VAD initialized\n   Model: {type(vad.model)}\n   Test: {len(ts)} segments")

def test_asr_backend():
    print("\n=== Testing ASR Backend ===")
    from core.transcription import create_transcriber
    import soundfile as sf, librosa
    
    cfg = yaml.safe_load(open('config.yaml', encoding='utf-8'))
    model = cfg['asr']['model']
    print(f"→ Using ASR: {model}")
    
    tc = create_transcriber(model)
    tc.initialize()
    
    tf = Path("docs/test.mp3")
    if not tf.exists():
        raise FileNotFoundError(f"Test file missing: {tf}")
    
    audio, _ = librosa.load(str(tf), sr=16000, mono=True)
    print(f"   Audio: {len(audio)/16000:.2f}s")
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio, 16000)
        result = tc.transcribe(tmp.name)
        os.unlink(tmp.name)
    
    print(f"✅ ASR success\n   Result: '{result}'")

def test_llm():
    print("\n=== Testing LLM ===")
    from core.command_mode import command_mode, cfg
    llm_cfg = cfg['llm']
    print(f"→ Model: {llm_cfg['model']}\n→ URL: {llm_cfg['base_url']}\n→ Test: 'hey there'")
    command_mode("hey there")
    print("✅ LLM completed")

def test_macos_file_permissions():
    print("\n=== Testing macOS File Permissions ===")
    if platform.system() != "Darwin":
        print("⏭️  Skipped (macOS only)")
        return
    
    warnings = []
    
    try:
        # Test reading/writing to current directory (most important for Hey Aura)
        current_dir = Path.cwd()
        test_file = current_dir / "test_permission_file"
        try:
            test_file.write_text("test")
            content = test_file.read_text()
            test_file.unlink()
            if content == "test":
                print("✅ Current directory read/write access")
            else:
                warnings.append("File read/write test failed")
        except PermissionError:
            warnings.append("Cannot read/write in current directory")
            warnings.append("To fix file permissions:\n" +
                           "   1. Check directory ownership: ls -la\n" +
                           "   2. Ensure you have write permissions to this directory\n" +
                           "   3. Try running: chmod 755 .")
        
        # Test writing to user directory (for config and recordings)
        home_dir = Path.home()
        test_file = home_dir / ".hey_aura_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
            print("✅ User directory write access")
        except PermissionError:
            warnings.append("Cannot write to user directory")
        
        # Test creating recordings directory if it doesn't exist
        recordings_dir = current_dir / "recordings"
        try:
            recordings_dir.mkdir(exist_ok=True)
            test_recording = recordings_dir / "test_recording.txt"
            test_recording.write_text("test")
            test_recording.unlink()
            print("✅ Recordings directory access")
        except PermissionError:
            warnings.append("Cannot create or write to recordings directory")
        
    except Exception as e:
        warnings.append(f"File permission check failed: {e}")
    
    if warnings:
        for warning in warnings:
            print(f"⚠️  {warning}")
    else:
        print("✅ All required file permissions granted")

def test_macos_permissions():
    print("\n=== Testing macOS Input/Accessibility Permissions ===")
    if platform.system() != "Darwin":
        print("⏭️  Skipped (macOS only)")
        return
    
    try:
        # Check if we can access input monitoring (keyboard events)
        from CoreGraphics import CGEventCreateKeyboardEvent
        
        # Test creating a keyboard event
        try:
            event = CGEventCreateKeyboardEvent(None, 0, True)
            if event:
                print("✅ Input Monitoring permission granted")
                input_monitoring = True
            else:
                input_monitoring = False
        except:
            input_monitoring = False
        
        if not input_monitoring:
            raise RuntimeError("Input Monitoring permission not granted. To fix:\n" +
                              "   1. Open System Preferences → Privacy & Security\n" +
                              "   2. Go to Input Monitoring\n" +
                              "   3. Add Terminal (or your IDE) to the list\n" +
                              "   4. Restart Terminal after authorization")
        
        # Check accessibility permission (for system control)
        try:
            from ApplicationServices import AXIsProcessTrusted
            accessibility = AXIsProcessTrusted()
            if accessibility:
                print("✅ Accessibility permission granted")
            else:
                raise RuntimeError("Accessibility permission not granted. To fix:\n" +
                                  "   1. Open System Preferences → Privacy & Security\n" +
                                  "   2. Go to Accessibility\n" +
                                  "   3. Add Terminal (or your IDE) to the list\n" +
                                  "   4. Restart Terminal after authorization")
        except ImportError:
            print("⚠️  Cannot check Accessibility permission (missing ApplicationServices)")
        
    except ImportError as e:
        print(f"⚠️  Cannot check permissions (missing libraries): {e}")
        print("   Consider installing: pip install pyobjc-framework-Cocoa pyobjc-framework-Quartz")

def test_macos_audio_setup():
    print("\n=== Testing macOS Audio Setup ===")
    if platform.system() != "Darwin":
        print("⏭️  Skipped (macOS only)")
        return
    
    warnings = []
    
    # Check BlackHole installation
    try:
        import sounddevice as sd
        input_devices = sd.query_devices()
        blackhole_devices = [d for d in input_devices if 'blackhole' in d['name'].lower()]
        
        if not blackhole_devices:
            warnings.append("BlackHole not found in audio devices. Install from: https://github.com/ExistentialAudio/BlackHole")
        else:
            print(f"✅ BlackHole detected")
            for device in blackhole_devices:
                print(f"   Device: {device['name']} (channels: {device['max_input_channels']})")
    except Exception as e:
        warnings.append(f"BlackHole check failed: {e}")
    
    # Check hey-aura multi-output device
    try:
        sas_bin = shutil.which("SwitchAudioSource") or "/opt/homebrew/bin/SwitchAudioSource"
        
        if not os.path.exists(sas_bin):
            warnings.append("SwitchAudioSource not found. Install with: brew install switchaudio-osx")
        else:
            out = subprocess.check_output([sas_bin, "-a"], encoding="utf-8")
            devices = [line.strip() for line in out.splitlines() if line.strip()]
            hey_aura = next((d for d in devices if "hey-aura" in d.lower()), None)
            
            if not hey_aura:
                warnings.append("hey-aura multi-output device not configured. Create Multi-Output Device in Audio MIDI Setup:\n" +
                               "   1. Open Audio MIDI Setup app\n" +
                               "   2. Create Multi-Output Device\n" +
                               "   3. Name it 'hey-aura'\n" +
                               "   4. Check BlackHole and your speakers")
            else:
                print(f"✅ hey-aura device configured: {hey_aura}")
    except Exception as e:
        warnings.append(f"hey-aura device check failed: {e}")
    
    if warnings:
        for warning in warnings:
            print(f"⚠️  {warning}")
    else:
        print("✅ Audio setup complete")

def check_system_health():
    """Check system health and raise exception if critical components fail"""
    print("Hey Aura System Health Check\n" + "="*40)
    
    # Critical tests that must pass
    critical_tests = [
        ("Silero VAD", test_silero_vad),
        ("ASR Backend", test_asr_backend),
        ("LLM", test_llm),
        ("macOS Input/Accessibility Permissions", test_macos_permissions)
    ]
    
    for name, test_fn in critical_tests:
        try:
            test_fn()
            print(f"✅ {name}")
        except Exception as e:
            print(f"❌ {name} failed: {e}")
            raise RuntimeError(f"Critical system component '{name}' failed: {e}")
    
    # Non-critical tests (warnings only)
    test_macos_file_permissions()
    test_macos_audio_setup()
    
    print("\n✅ System health check passed!")

def main():
    """Run system health check in doctor mode"""
    try:
        check_system_health()
        return 0
    except Exception as e:
        print(f"\n❌ System health check failed: {e}")
        return 1

if __name__ == "__main__": sys.exit(main())
