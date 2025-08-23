ASCII = """
···································
   ┬ ┬ ┌─┐ ┬ ┬   ┌─┐ ┬ ┬ ┬─┐ ┌─┐
   ├─┤ ├┤  └┬┘   ├─┤ │ │ ├┬┘ ├─┤
   ┴ ┴ └─┘  ┴    ┴ ┴ └─┘ ┴└─ ┴ ┴
···································
"""
print(ASCII)

import time
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading
import tempfile
import os
import platform
import yaml
from pydub import AudioSegment
import datetime,json

from core.keyboard_utils import ClipboardInjector, FnKeyListener, KeyboardEventHandler
from core.tray.tray_animator import TrayAnimator
from core.transcription import create_transcriber
from core.transcription_queue import AsyncTranscriptionManager
from core.audio_utils import AudioEnhancer, SileroVAD, AudioDeviceSelector
from core.command_mode import command_mode
from core.i18n import _, set_language
from core.llm_rewriter import get_rewriter
from core.meeting_utils import MeetingRecorder

# Audio configuration constants
SAMPLE_RATE,SPEECH_PADDING_MS,VAD_THRESHOLD=16000,300,0.6

class VoiceTranscriber:
    def __init__(self,model=None,language=None):
        print(_("→ Initializing Hey Aura"))
        self.model,self.language=model,language
        self.load_config()
        print(_("→ Model: {}, Language: {}").format(self.model, self.language))
    
    def load_config(self):
        with open('config.yaml','r',encoding='utf-8')as f:
            self.config=yaml.safe_load(f)
        self.chat_config=self.config.get('chat',{})
        # Set UI language
        ui_language = self.config.get('ui_language', 'auto')
        if ui_language != 'auto':
            set_language(ui_language)
        
        print(_("→ Starting loading VAD and ASR models..."))
        vad_error,asr_error=None,None
        
        def init_vad():
            nonlocal vad_error
            try:
                print(_("  → Loading VAD model..."))
                self.vad=SileroVAD(threshold=VAD_THRESHOLD)
                self.vad.initialize()
                print(_("  ✅ VAD model loaded successfully"))
            except Exception as e:
                vad_error=e
                print(_("  ❌ Failed to load VAD model: {}").format(e))
        
        def init_asr():
            nonlocal asr_error
            try:
                print(_("  → Loading ASR model..."))
                self.transcriber=create_transcriber(self.model)
                # Check language support - ['*'] means all languages supported
                supported_langs = self.transcriber.get_supported_languages()
                if self.language and supported_langs != ['*'] and self.language not in supported_langs:
                    supported=supported_langs[:10]
                    raise ValueError(_("Language '{}' is not supported. Supported languages: {}...").format(self.language, ', '.join(supported)))
                self.transcriber.initialize()
                print(_("  ✅ ASR model loaded successfully"))
            except Exception as e:
                asr_error=e
                print(_("  ❌ Failed to load ASR model: {}").format(e))
        
        # Parallel model loading
        vad_thread,asr_thread=threading.Thread(target=init_vad),threading.Thread(target=init_asr)
        vad_thread.start();asr_thread.start()
        vad_thread.join();asr_thread.join()
        
        if vad_error:raise vad_error
        if asr_error:raise asr_error
        print(_("✅ All models loaded successfully"))
        
        # Initialize recording state
        self.sr,self.rec,self.aud,self.th=SAMPLE_RATE,False,[],None
        self.mode=None
        self.rec_lock = threading.Lock()  # Lock for thread safety
        self.active_stream = None  # Track active audio stream
        self.text_injector=ClipboardInjector()
        self.keyboard_handler=KeyboardEventHandler(self)
        self.fn_listener = None  # Will be initialized for macOS
        self.tray=TrayAnimator()
        self.audio_enhancer=AudioEnhancer(sample_rate=self.sr)
        self.rewriter=get_rewriter()
        self.json_lock = threading.Lock()
        
        # Initialize transcription queue
        self.transcription_manager = AsyncTranscriptionManager(transcriber=self.transcriber, max_workers=5)
        self.transcription_manager.start()
        
        # Initialize meeting recorder
        self.meeting_recorder = MeetingRecorder(self)
        
        # Setup tray with meeting recording callback
        self.tray.setup_tray_with_meeting(self.meeting_recorder.toggle_meeting_recording, self.quit_app)
        
        print(_("→ Fn for dictation, Fn+Ctrl for command mode, right-click tray to exit") if platform.system()=="Darwin" else _("→ Ctrl+Win for dictation, Win+Alt for command mode, right-click tray to exit"))
        
        self._setup_queue_monitoring()

    def _setup_queue_monitoring(self): # Queue status monitoring
        def monitor_queue():
            while hasattr(self, 'transcription_manager') and self.transcription_manager.queue.running:
                try:
                    stats = self.transcription_manager.get_stats()
                    if stats['queue_size'] > 0 or stats['active_tasks'] > 0:
                        status_msg = _("Queue: {} pending, {} active").format(stats['queue_size'], stats['active_tasks'])
                        if stats['queue_size'] > 5: print(_("⚠️ Transcription queue backlog: {} tasks").format(stats['queue_size']))
                    time.sleep(5)
                except Exception as e: print(_("Queue monitoring error: {}").format(e)); break
        threading.Thread(target=monitor_queue, daemon=True, name="QueueMonitor").start()

    def cleanup_stream(self):
        """Force cleanup audio stream"""
        if self.active_stream:
            try:
                self.active_stream.stop()
                self.active_stream.close()
            except:
                pass
            self.active_stream = None

    def quit_app(self):
        print(_("→ Exiting program"))
        self.cleanup_stream()
        if hasattr(self, 'transcription_manager'): self.transcription_manager.stop()
        self.tray.stop_animation()
        if platform.system()!="Darwin":
            self.tray.icon and self.tray.icon.stop()
        os._exit(0)

    def start_rec(self):
        with self.rec_lock:
            if self.rec:return
            # Check if meeting recording is active - prevent conflicting recording
            if hasattr(self, 'meeting_recorder') and self.meeting_recorder.meeting_mode:
                print(_("⚠️ Cannot start recording - meeting mode is active"))
                return
            # Cleanup any existing stream
            self.cleanup_stream()
            # Ensure previous thread is terminated
            if self.th and self.th.is_alive():
                print(_("⚠️ Detected unfinished recording thread, cleaning up..."))
                self.rec = False
                # Release lock to allow thread to finish
                self.rec_lock.release()
                self.th.join(timeout=1)
                self.rec_lock.acquire()
                if self.th.is_alive():
                    print(_("⚠️ Cannot terminate old recording thread, force cleanup"))
                    self.cleanup_stream()
                    self.th = None
                    return
            print(_("🎤 Recording... (Mode: {})").format(self.mode))
            self.rec,self.aud=True,[]
            self.tray.set_status("recording")
            
        def rec():
            stream = None
            try:
                # Refresh audio devices to get latest defaults
                sd._terminate()
                sd._initialize()
                
                # Get best input device using smart selector
                best_device_id = AudioDeviceSelector.get_best_input_device()
                
                if best_device_id is None:
                    # Fallback to system default if no suitable device found
                    default_device = sd.query_devices(kind='input')
                    print(_("🎙️ Using system default device: {}").format(default_device['name']))
                
                # Use non-blocking mode with smaller chunk size for better responsiveness
                stream = sd.InputStream(
                    samplerate=self.sr,
                    channels=1,
                    dtype=np.float32,
                    blocksize=512,  # Smaller chunk size
                    latency='low',  # Low latency mode
                    device=best_device_id  # Selected device or None (system default)
                )
                self.active_stream = stream
                stream.start()
                
                while True:
                    with self.rec_lock:
                        if not self.rec:
                            break
                    try:
                        # Non-blocking read
                        d,overflowed = stream.read(512)
                        if overflowed:
                            print(_("⚠️ Audio input overflow"))
                        if d is not None and len(d) > 0:
                            with self.rec_lock:
                                if self.rec:  # Double check state
                                    self.aud.append(np.asarray(d,dtype=np.float32).reshape(-1))
                    except sd.CallbackStop:
                        break
                    except Exception as e:
                        if self.rec:  # Only show errors during active recording
                            print(_("Error reading audio data: {}").format(e))
                        break
                        
            except sd.PortAudioError as e:
                error_code = str(e)
                if '-9986' in error_code or 'Internal PortAudio error' in error_code:
                    print(_("⚠️ Audio device disconnected or switched, please restart recording"))
                elif '-9985' in error_code:
                    print(_("⚠️ Audio device configuration error, please check microphone permissions"))
                else:
                    print(_("Recording error: {}").format(e))
                # Cleanup state
                with self.rec_lock:
                    self.rec = False
                    self.aud = []
            except Exception as e:
                print(_("Recording error: {}").format(e))
                import traceback
                traceback.print_exc()
                # Cleanup state
                with self.rec_lock:
                    self.rec = False
                    self.aud = []
            finally:
                if stream:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception as e:
                        print(_("Error closing audio stream: {}").format(e))
                self.active_stream = None
        
        self.th=threading.Thread(target=rec,daemon=True)
        self.th.start()

    def stop_rec(self):
        with self.rec_lock:
            if not self.rec:return
            print(_("✨ Processing..."))
            self.rec=False
            self.tray.set_status("processing")
            
        # Wait for thread to finish outside lock to avoid deadlock
        if self.th and self.th.is_alive():
            self.th.join(timeout=2)
            if self.th.is_alive():
                print(_("⚠️ Recording thread timeout, force cleanup resources"))
                # Force cleanup audio stream
                self.cleanup_stream()
                # Reset all states
                self.th = None
                self.aud = []
                self.tray.set_status("idle")
                # Reset keyboard states
                self.keyboard_handler.reset_key_states(_("Recording thread timeout"))
                return
                
        # Ensure thread reference is cleaned up
        self.th = None
        if not self.aud:
            self.tray.set_status("idle")
            return print(_("No data"))
        try:
            aud=self.audio_enhancer._to_mono_1d(np.concatenate(self.aud,axis=0)if len(self.aud)>1 else self.aud[0])
            if aud.size/self.sr<0.5:
                self.tray.set_status("idle")
                return print(_("Too short"))
            aud=self.audio_enhancer.enhance_audio(aud)
            aud=self.vad.extract_speech_segments(aud,self.sr,SPEECH_PADDING_MS)
            
            # Check for wakeword in dictation mode
            if self.mode == 'dictation':
                from core.wakeword import detect_from_audio
                kws_start = time.time()
                detected, confidence = detect_from_audio(aud.copy(), self.sr)
                kws_time = (time.time() - kws_start) * 1000  # Convert to milliseconds
                self.mode = 'command' if detected else 'dictation'
                if detected:
                    print(f"🎯 Hey Aura detected! Confidence: {confidence:.2f} | Time: {kws_time:.1f}ms | Switching to command mode")
                else:
                    print(f"🔍 Wake word check: {confidence:.2f} confidence | Time: {kws_time:.1f}ms")
            
            if aud.size/self.sr<0.3:
                self.tray.set_status("idle")
                return print(_("Audio too short after VAD processing"))
            tf=tempfile.NamedTemporaryFile(suffix=".wav",delete=False)
            wav.write(tf.name,self.sr,(np.clip(aud,-1.0,1.0)*32767).astype(np.int16))
            tf.close()
            t=time.time()
            
            # 使用转写队列进行异步转写
            try:
                txt = self.transcription_manager.transcribe_sync(
                    audio_path=tf.name,
                    language=self.language,
                    beam_size=5,
                    vad_filter=False,
                    timeout=30  # 30秒超时
                )
                
                if txt.strip():
                    txt=txt.strip()
                    # Save MP3 and record
                    try:
                        log_dir = "./recordings/push-to-talk"
                        os.makedirs(log_dir,exist_ok=True)
                        timestamp=datetime.datetime.now()
                        mp3_path=f"{log_dir}/{timestamp.strftime('%Y%m%d_%H%M%S')}.mp3"
                        AudioSegment.from_wav(tf.name).export(mp3_path,format="mp3",parameters=["-q:a","2"])
                        # Record to dictation.json
                        record={"file":mp3_path,"transcription":txt,"time":timestamp.isoformat(),"duration":round(aud.size/self.sr,2)}
                        # Use lock to protect JSON file read/write operations
                        with self.json_lock:
                            try: records = json.load(open(f"{log_dir}/transcription.json","r",encoding="utf-8"))
                            except: records = []
                            records.append(record)
                            with open(f"{log_dir}/transcription.json","w",encoding="utf-8") as f:
                                json.dump(records, f, ensure_ascii=False, indent=2)
                    except:pass
                    (self.process_dictation if self.mode=='dictation'else self.process_command if self.mode=='command'else self.process_dictation)(txt)
                else:print(_("No text"))
                    
            except TimeoutError:
                print(_("❌ Transcription timeout"))
            except Exception as e:
                print(_("❌ Transcription error: {}").format(e))
        except Exception as e:print(_("Error: {}").format(e))
        finally:
            try:os.unlink(tf.name)
            except:pass
            self.tray.set_status("idle")
            self.keyboard_handler.reset_key_states(_("Recording ended"))

    def process_dictation(self,text):
        print(_("📝 Dictation output: {}").format(text))
        # Apply LLM rewriting if enabled (only for dictation mode)
        if self.rewriter.enabled:
            rewritten_text = self.rewriter.rewrite(text, 'dictation')
            if rewritten_text != text:
                print(_("✨ Rewritten: {}").format(rewritten_text))
            self.text_injector.type(rewritten_text)
        else:
            self.text_injector.type(text)

    def process_command(self,text):
        print(_("🤖 Command input: {}").format(text))
        try:
            self.tray.set_status("processing")
            # LLM rewriting is not applied to command mode (only dictation)
            command_mode(text)
            print(_("\n✅ Command completed"))
        except Exception as e:print(_("❌ Command processing error: {}").format(e))
        finally:
            self.tray.set_status("idle")
            self.keyboard_handler.reset_key_states(_("Command ended"))

    def run(self):
        self.tray.start_animation()
        if platform.system()=="Darwin":
            # Initialize FnKeyListener immediately
            self.fn_listener=FnKeyListener(self)
            def run_fn_listener():
                self.fn_listener.setup_quartz_listener()
            threading.Thread(target=run_fn_listener,daemon=True).start()
            # Give listener thread time to initialize
            time.sleep(0.1)
            self.tray.run_tray()
        else:
            threading.Thread(target=self.tray.run_tray,daemon=True).start()
            self.keyboard_handler.start_keyboard_listener()

if __name__=="__main__":
    try:
        if platform.system()=="Darwin":
            from AppKit import NSApplication
            app=NSApplication.sharedApplication()
            app.setActivationPolicy_(1)
        with open('config.yaml','r',encoding='utf-8')as f:
            config=yaml.safe_load(f)
        asr_config=config['asr']
        model=asr_config['model']
        language=asr_config['language']
        transcriber=VoiceTranscriber(model=model,language=language)
        transcriber.run()
    except Exception as e:
        print(_("Startup error: {}").format(e))
        input(_("Press Enter to exit..."))
