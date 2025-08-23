import time
import sounddevice as sd
import numpy as np
import threading
import queue
import platform
import warnings

from core.audio_utils import AudioDeviceSelector
from core.i18n import _

if platform.system() == 'Windows':
    from core.meeting.system_recorder_win import SystemAudioRecorder
elif platform.system() == 'Darwin':
    from core.meeting.system_recorder_mac import SystemAudioRecorder
else:
    raise ImportError("System audio recording is not supported on this OS.")

class MeetingAudioProcessor:
    """Audio processor for meeting mode recording and processing."""

    def __init__(self, transcriber_ref):
        """Initialize the audio processor."""
        self.transcriber_ref = transcriber_ref

        # Use pre-initialized VAD instances from main app
        self.microphone_vad = transcriber_ref.meeting_microphone_vad
        self.system_vad = transcriber_ref.meeting_system_vad

        self.stream = None
        self.meeting_audio_buffer = []
        self.meeting_audio_buffer_lock = threading.RLock()

        self.system_recorder = None
        self.system_audio_thread = None
        self.system_audio_buffer = []
        self.system_audio_buffer_lock = threading.RLock()

        self.recording_start_time = None

        self.meeting_audio_queue = queue.Queue(maxsize=100)
        self.system_audio_queue = queue.Queue(maxsize=100)

    def start_audio_recording(self):
        """Start audio recording."""
        # Clean up existing stream
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
            self.stream = None

        # Clear audio buffers
        with self.meeting_audio_buffer_lock:
            self.meeting_audio_buffer = []
        with self.system_audio_buffer_lock:
            self.system_audio_buffer = []

        # Record start time for sync
        self.recording_start_time = time.time()

        # Start system audio recording
        if SystemAudioRecorder:
            try:
                self.system_recorder = SystemAudioRecorder(sample_rate=self.transcriber_ref.sr)
                
                if self.system_recorder.start():
                    print(_("→ 💡 System audio recording started"))

                    # Wait for audio system to stabilize
                    time.sleep(0.1)

                    # Start system audio processing thread
                    self.system_audio_thread = threading.Thread(target=self._process_system_audio, daemon=True)
                    self.system_audio_thread.start()
                else:
                    print(_("→ ⚠️ System audio recording failed, only recording microphone"))
                    self.system_recorder = None
            except Exception as e:
                print(_("→ ⚠️ Could not initialize system audio: {}").format(e))
                self.system_recorder = None

        # Start microphone recording thread after system audio setup
        print(_("→ 🎤 Starting microphone recording (after system audio setup)..."))
        microphone_thread = threading.Thread(target=self._microphone_recording_loop, daemon=True)
        microphone_thread.start()

        return microphone_thread

    def _microphone_recording_loop(self):
        """Microphone recording loop."""
        stream = None
        try:
            # Short delay to ensure audio system is ready
            time.sleep(0.1)

            best_device_id = AudioDeviceSelector.get_best_input_device()
            # Selected microphone device
            print(_("→ 🎙️ Selected microphone device: {}").format(sd.query_devices(best_device_id)['name'] if best_device_id is not None else "Default"))

            self.stream = sd.InputStream(
                samplerate=self.transcriber_ref.sr,
                channels=1,
                dtype=np.float32,
                blocksize=512,
                latency='low',
                device=best_device_id
            )
            stream = self.stream
            stream.start()

            segment_count = 0
            chunk_count = 0
            silence_duration = 0.0
            speech_segment_buffer = []
            speech_active = False
            SILENCE_THRESHOLD = 1.5

            while hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_mode and not self.transcriber_ref.meeting_recorder.meeting_stopping:
                try:
                    # Check stop signal
                    if self.transcriber_ref.meeting_recorder.meeting_stopping or not self.transcriber_ref.meeting_recorder.meeting_mode:
                        break

                    d, overflowed = stream.read(512)
                    if overflowed:
                        # Audio input overflow
                        print(_("  → Audio input overflow"))

                    if d is not None and len(d) > 0:
                        # Convert to float32 array
                        audio_chunk = np.asarray(d, dtype=np.float32).reshape(-1)
                        chunk_count += 1

                        # Store as bytes for full recording
                        with self.meeting_audio_buffer_lock:
                            chunk_bytes = audio_chunk.tobytes()
                            self.meeting_audio_buffer.append(chunk_bytes)

                        # Use microphone VAD for speech detection, pre-filter first
                        chunk_energy = np.mean(np.abs(audio_chunk))

                        # Pre-filter, only run VAD on audio with enough energy
                        if chunk_energy > 0.01 and self.microphone_vad is not None:
                            try:
                                chunk_has_speech = self.microphone_vad.is_speech_realtime(audio_chunk, self.transcriber_ref.sr)
                            except Exception as e:
                                print(_("→ [Mic] VAD detection error: {}").format(e))
                                chunk_has_speech = False
                        else:
                            # Skip VAD detection for low energy audio or if VAD is None
                            chunk_has_speech = False

                        chunk_duration = len(audio_chunk) / self.transcriber_ref.sr

                        # Store audio chunk bytes to speech buffer
                        speech_segment_buffer.append(chunk_bytes)

                        if chunk_has_speech:
                            if not speech_active:
                                speech_active = True
                                print(_("→ Speech detected, recording..."))
                                try:
                                    self.transcriber_ref.tray.set_status("recording")
                                except Exception:
                                    pass
                            silence_duration = 0.0
                        else:
                            if speech_active:
                                silence_duration += chunk_duration

                                if silence_duration >= SILENCE_THRESHOLD:
                                    if len(speech_segment_buffer) > 0:
                                        segment_count += 1

                                        # Reconstruct audio from bytes
                                        segment_audio = self._bytes_to_audio(speech_segment_buffer)
                                        segment_duration = len(segment_audio) / self.transcriber_ref.sr

                                        print(_("  → Speech paused, processing segment {}: {:.1f}s").format(segment_count, segment_duration))
                                        try:
                                            self.transcriber_ref.tray.set_status("processing")
                                        except Exception:
                                            pass

                                        # Send audio bytes to queue
                                        try:
                                            self.meeting_audio_queue.put(segment_audio.tobytes(), block=False)
                                        except queue.Full:
                                            print(_("  → Warning: Audio queue is full, skipping segment"))

                                        speech_segment_buffer = []
                                        speech_active = False
                                        silence_duration = 0.0
                                        try:
                                            self.transcriber_ref.tray.set_status("recording")
                                        except Exception:
                                            pass
                            else:
                                # Trim buffer to save memory
                                max_buffer_duration = 1.0
                                max_buffer_chunks = int(max_buffer_duration * self.transcriber_ref.sr / 512)
                                if len(speech_segment_buffer) > max_buffer_chunks:
                                    speech_segment_buffer = speech_segment_buffer[-max_buffer_chunks:]

                except Exception as e:
                    if hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_mode and not self.transcriber_ref.meeting_recorder.meeting_stopping:
                        print(_("  → Error in meeting recording: {}").format(e))
                    break

            if stream:
                stream.stop()
                stream.close()
            self.stream = None

        except Exception as e:
            print(_("  → Meeting recording error: {}").format(e))
            if hasattr(self.transcriber_ref, 'meeting_recorder'):
                self.transcriber_ref.meeting_recorder.meeting_mode = False
        finally:
            # Ensure proper cleanup with forced garbage collection
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self.stream = None
            # Force cleanup on macOS to prevent segfault
            import gc
            gc.collect()

    def _process_system_audio(self):
        """System audio processing and buffer storage."""
        # Check if system recorder is in skip mode
        if self.system_recorder and hasattr(self.system_recorder, 'skip_system_recording') and self.system_recorder.skip_system_recording:
            print(_("→ [System] Skipping system audio processing (built-in speaker mode)"))
            return
            
        while hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_mode and not self.transcriber_ref.meeting_recorder.meeting_stopping:
            if self.system_recorder:
                try:
                    segments = self.system_recorder.get_speech_segments()
                    for segment_audio in segments:
                        if segment_audio.size > 0:
                            # Store system audio segment to buffer for mixing
                            with self.system_audio_buffer_lock:
                                chunk_bytes = segment_audio.tobytes()
                                self.system_audio_buffer.append(chunk_bytes)

                            # Also put into queue for transcription
                            try:
                                self.system_audio_queue.put(
                                    segment_audio.tobytes(),
                                    block=False
                                )
                                print(_("→ [System] Speech segment queued for independent transcription"))
                            except queue.Full:
                                print(_("→ [System] Independent transcription queue is full"))
                except Exception as e:
                    if hasattr(self.transcriber_ref, 'meeting_recorder') and not self.transcriber_ref.meeting_recorder.meeting_stopping:
                        print(_("→ [System] Error processing audio: {}").format(e))
            time.sleep(0.1)

    def _bytes_to_audio(self, byte_chunks):
        """Convert list of byte chunks to numpy audio array."""
        if not byte_chunks:
            return np.array([], dtype=np.float32)

        # Join all bytes
        all_bytes = b''.join(byte_chunks)

        # Convert back to numpy array (make writable copy)
        audio = np.frombuffer(all_bytes, dtype=np.float32).copy()
        return audio

    def _loudness_normalize(self, audio, target_lufs=-23.0):
        """Loudness normalization."""
        a = np.asarray(audio, dtype=np.float32)
        if a.size == 0:
            return a
        import pyloudnorm as pyln
        meter = pyln.Meter(self.transcriber_ref.sr)
        loudness = meter.integrated_loudness(a)
        
        # Suppress the clipped samples warning from pyloudnorm
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Possible clipped samples in output")
            normalized = pyln.normalize.loudness(a, loudness, target_lufs)
        
        return np.clip(np.asarray(normalized, dtype=np.float32), -1.0, 1.0)

    def stop_audio_recording(self):
        """Stop audio recording."""
        # Stop system audio recording
        if self.system_recorder:
            print(_("→ Stopping system audio..."))
            try:
                # Stop system recorder, do not fetch data (avoid duplication)
                self.system_recorder.stop()
                print(_("→ System audio stopped successfully"))
            except Exception as e:
                print(_("→ Error stopping system audio: {}").format(e))

        # Wait for system audio thread to finish
        if self.system_audio_thread and self.system_audio_thread.is_alive():
            print(_("→ Waiting for system audio thread..."))
            self.system_audio_thread.join(timeout=5)
            if self.system_audio_thread.is_alive():
                print(_("→ Warning: System audio thread did not terminate cleanly"))

        # Close audio stream
        if self.stream:
            print(_("→ Closing audio stream..."))
            try:
                self.stream.stop()
                self.stream.close()
                print(_("→ Audio stream closed successfully"))
            except Exception as e:
                print(_("→ Error closing audio stream: {}").format(e))
            finally:
                self.stream = None

    def get_recorded_audio(self):
        """Get recorded audio data."""
        with self.meeting_audio_buffer_lock:
            mic_audio = self._bytes_to_audio(self.meeting_audio_buffer)

        # Get system audio buffer data
        with self.system_audio_buffer_lock:
            system_audio = self._bytes_to_audio(self.system_audio_buffer)

        # Check if we were in built-in speaker mode
        if self.system_recorder and hasattr(self.system_recorder, 'skip_system_recording'):
            was_builtin_speaker = getattr(self.system_recorder, 'skip_system_recording', False)
            if was_builtin_speaker:
                print(_("→ Built-in speaker mode: Using microphone audio only (includes speaker audio)"))
                print(_("→ Microphone audio length: {:.1f}s").format(len(mic_audio)/self.transcriber_ref.sr))
                return mic_audio

        # If system audio exists, mix
        if len(system_audio) > 0:
            # Align audio length
            max_len = max(len(mic_audio), len(system_audio))

            # Pad shorter audio
            if len(mic_audio) < max_len:
                mic_audio = np.pad(mic_audio, (0, max_len - len(mic_audio)))
            if len(system_audio) < max_len:
                system_audio = np.pad(system_audio, (0, max_len - len(system_audio)))

            # Loudness normalization
            target_lufs = -23.0
            mic_normalized = self._loudness_normalize(mic_audio, target_lufs=target_lufs)
            sys_normalized = self._loudness_normalize(system_audio, target_lufs=target_lufs)

            # Simple mixing: average normalized signals then clip
            mixed_audio = (mic_normalized + sys_normalized) / 2.0
            mixed_audio = np.clip(mixed_audio, -1.0, 1.0)

            print(_("→ Mixed audio: Microphone {:.1f}s + System {:.1f}s").format(
                len(mic_audio)/self.transcriber_ref.sr,
                len(system_audio)/self.transcriber_ref.sr
            ))

            return mixed_audio
        else:
            # Microphone audio only
            print(_("→ Microphone audio only: {:.1f}s").format(len(mic_audio)/self.transcriber_ref.sr))
            return mic_audio

    def cleanup_resources(self):
        """Cleanup resources."""
        # Force stop any remaining streams first
        if hasattr(self, 'stream') and self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            except Exception:
                pass
        
        # Don't cleanup VAD instances - they are managed at app level
        # VAD instances remain initialized throughout the application lifecycle

        # Clear queues
        try:
            while not self.meeting_audio_queue.empty():
                self.meeting_audio_queue.get_nowait()
        except Exception:
            pass

        try:
            while not self.system_audio_queue.empty():
                self.system_audio_queue.get_nowait()
        except Exception:
            pass

        # Clear system audio data
        try:
            with self.system_audio_buffer_lock:
                self.system_audio_buffer = []
        except Exception:
            pass
            
        # Clear meeting audio data
        try:
            with self.meeting_audio_buffer_lock:
                self.meeting_audio_buffer = []
        except Exception:
            pass
            
        # Force garbage collection on macOS
        import gc
        gc.collect()