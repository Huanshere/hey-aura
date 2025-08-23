import time
import threading
import queue
import numpy as np
import sounddevice as sd
import subprocess
import shutil
from datetime import datetime
import scipy.io.wavfile as wav
from scipy import signal
from pydub import AudioSegment
import os
from core.audio_utils import SileroVAD
from core.i18n import _


class SystemAudioRecorder:
    """System audio recorder for macOS using BlackHole/hey-aura"""

    def __init__(self, sample_rate=16000, vad_instance=None):
        self.sr = sample_rate
        self.vad = vad_instance if vad_instance else SileroVAD(threshold=0.6)
        self.is_recording = False
        self.recording_thread = None
        self.audio_queue = queue.Queue(maxsize=100)
        self.audio_buffer = []
        self.buffer_lock = threading.RLock()
        self.segment_counter = 0
        self.original_device = None
        self.stream = None
        self.sas_bin = shutil.which("SwitchAudioSource") or "/opt/homebrew/bin/SwitchAudioSource"
        self.skip_system_recording = False
        # Use Event for clean thread communication
        self._stop_event = threading.Event()
        self._device_sample_rate = None  # Store device's native sample rate

    def _get_current_output_device(self):
        """Get current output device name"""
        out = subprocess.check_output([self.sas_bin, "-c"], encoding="utf-8")
        return out.strip()

    def _set_output_device(self, name):
        """Switch output device by name"""
        subprocess.run([self.sas_bin, "-t", "output", "-s", name], check=True)
        subprocess.run([self.sas_bin, "-t", "system", "-s", name], check=True)
    
    def _is_builtin_speaker(self, device_name):
        """Check if device is built-in speaker"""
        device_lower = device_name.lower()
        
        # Exclude headphones/earphones first
        headphone_keywords = ['headphone', 'airpod', '耳机', 'earphone', 'headset']
        if any(keyword in device_lower for keyword in headphone_keywords):
            return False
        
        # Exclude external/bluetooth devices
        external_keywords = ['external', 'bluetooth', 'usb', 'wireless', 'immersed', 'virtual', 'hey-aura']
        if any(keyword in device_lower for keyword in external_keywords):
            return False
            
        # Check for built-in speaker indicators
        builtin_keywords = ['macbook', '扬声器', 'built-in', '内置']
        is_builtin = any(keyword in device_lower for keyword in builtin_keywords)
        
        # Special case: generic "speaker" is only builtin if it contains macbook/built-in context
        if 'speaker' in device_lower and not any(k in device_lower for k in ['macbook', 'built-in']):
            return False
            
        return is_builtin

    def start(self):
        """Start system audio recording"""
        if self.is_recording:
            return False

        self.original_device = self._get_current_output_device()
        print(_("→ Original audio device: {}").format(self.original_device))

        # Check if current device is built-in speaker
        if self._is_builtin_speaker(self.original_device):
            print(_("→ Built-in speaker detected, skipping system audio recording"))
            print(_("→ Microphone will capture speaker audio naturally"))
            self.skip_system_recording = True
            self.is_recording = True  # Mark as recording but skip actual recording
            return True  # Return True to indicate "successful" start

        # For headphones/external devices, proceed with BlackHole recording
        out = subprocess.check_output([self.sas_bin, "-a"], encoding="utf-8")
        devices = [line.strip() for line in out.splitlines() if line.strip()]
        hey_aura = next((d for d in devices if "hey-aura" in d.lower()), None)

        if not hey_aura:
            print(_("→ hey-aura output device not found"))
            return False

        self._set_output_device(hey_aura)
        print(_("→ System output switched to: {}").format(hey_aura))
        # Wait for device switching to stabilize
        time.sleep(0.3)

        input_devices = sd.query_devices()
        blackhole_input = None
        for idx, device in enumerate(input_devices):
            if device['max_input_channels'] > 0 and 'blackhole' in device['name'].lower():
                blackhole_input = idx
                break

        if blackhole_input is None:
            print(_("→ BlackHole input device not found, cannot record system audio"))
            self._set_output_device(self.original_device)
            return False

        print(_("→ Using recording device: {} (index: {})").format(input_devices[blackhole_input]['name'], blackhole_input))
        
        # Get device's native sample rate
        device_info = sd.query_devices(blackhole_input)
        self._device_sample_rate = int(device_info.get('default_samplerate', 48000))
        if self._device_sample_rate != self.sr:
            print(_("→ Device sample rate: {}Hz, will resample to {}Hz").format(self._device_sample_rate, self.sr))

        self.is_recording = True
        self.skip_system_recording = False
        self.audio_buffer = []
        self.segment_counter = 0
        self._stop_event.clear()

        self.recording_thread = threading.Thread(
            target=self._recording_loop,
            args=(blackhole_input,),
            daemon=True
        )
        self.recording_thread.start()
        print(_("→ System audio recording started"))
        return True

    def _recording_loop(self, device_index):
        """System audio recording loop"""
        stream = None
        try:
            device_info = sd.query_devices(device_index)
            channels = min(2, device_info['max_input_channels'])
            # Use device's native sample rate to avoid resampling issues
            actual_sr = self._device_sample_rate or self.sr

            # Create stream with context manager pattern
            stream = sd.InputStream(
                samplerate=actual_sr,
                channels=channels,
                dtype=np.float32,
                blocksize=512,
                latency='low',
                device=device_index
            )
            self.stream = stream  # Store reference for abort() if needed
            stream.start()

            print(_("→ Recording started, channels: {}, sample_rate: {}Hz").format(channels, actual_sr))

            silence_duration = 0.0
            speech_segment_buffer = []
            speech_active = False
            SILENCE_THRESHOLD = 1.5
            CHUNK_SIZE = 512
            need_resample = actual_sr != self.sr

            while not self._stop_event.is_set():
                try:
                    if stream and hasattr(stream, 'read'):
                        audio_chunk, overflowed = stream.read(CHUNK_SIZE)
                    else:
                        break
                        
                    if overflowed:
                        print(_("→ [System] Audio input overflowed"))
                except Exception:
                    if self._stop_event.is_set():
                        break
                    continue

                if audio_chunk is None or len(audio_chunk) == 0:
                    continue

                if audio_chunk.ndim == 2:
                    audio_chunk = audio_chunk.mean(axis=1)
                audio_chunk = audio_chunk.astype(np.float32).flatten()
                
                # Resample if needed
                if need_resample and len(audio_chunk) > 0:
                    audio_chunk = signal.resample_poly(audio_chunk, self.sr, actual_sr)
                    audio_chunk = audio_chunk.astype(np.float32)

                chunk_bytes = audio_chunk.tobytes()
                with self.buffer_lock:
                    self.audio_buffer.append(chunk_bytes)

                if self.vad:
                    chunk_has_speech = self.vad.is_speech_realtime(audio_chunk, self.sr)
                    chunk_duration = len(audio_chunk) / self.sr

                    speech_segment_buffer.append(chunk_bytes)

                    if chunk_has_speech:
                        if not speech_active:
                            speech_active = True
                            print(_("→ [System] Speech detected"))
                        silence_duration = 0.0
                    else:
                        if speech_active:
                            silence_duration += chunk_duration
                            if silence_duration >= SILENCE_THRESHOLD and len(speech_segment_buffer) > 0:
                                segment_audio = self._bytes_to_audio(speech_segment_buffer)
                                try:
                                    self.audio_queue.put(segment_audio.tobytes(), block=False)
                                    self.segment_counter += 1
                                    print(_("→ [System] Speech segment {}: {:.1f}s").format(self.segment_counter, len(segment_audio)/self.sr))
                                except queue.Full:
                                    print(_("→ [System] Queue full"))
                                speech_segment_buffer = []
                                speech_active = False
                                silence_duration = 0.0
                        else:
                            # Trim buffer to save memory
                            max_buffer_chunks = int(1.0 * self.sr / CHUNK_SIZE)
                            if len(speech_segment_buffer) > max_buffer_chunks:
                                speech_segment_buffer = speech_segment_buffer[-max_buffer_chunks:]

        except Exception as e:
            print(_("→ [System] Recording failed: {}").format(e))
        finally:
            # Clean up stream only in this thread
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception as e:
                    print(_("→ [System] Stream cleanup error: {}").format(e))
            # Clear the reference
            self.stream = None
            self.is_recording = False
            print(_("→ [System] Recording loop ended"))

    def _bytes_to_audio(self, byte_chunks):
        """Convert byte chunks to audio array"""
        if not byte_chunks:
            return np.array([], dtype=np.float32)
        return np.frombuffer(b''.join(byte_chunks), dtype=np.float32).copy()

    def stop(self):
        """Stop recording and restore original device"""
        if not self.is_recording:
            return None

        print(_("→ Stopping system audio recording..."))
        
        # If we skipped system recording, just return
        if self.skip_system_recording:
            print(_("→ System audio was not recorded (built-in speaker mode)"))
            self.skip_system_recording = False
            self.is_recording = False
            return None

        # Signal recording thread to stop
        self._stop_event.set()
        
        # Use abort() to interrupt blocking read() - safer than stop()
        if self.stream:
            try:
                self.stream.abort()  # Non-blocking, safer than stop()
            except Exception as e:
                print(_("→ Warning: Error aborting stream: {}").format(e))
        
        # Wait for thread to finish
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=8)  # Generous timeout
            if self.recording_thread.is_alive():
                print(_("→ Warning: Recording thread still alive after timeout"))
        
        # Clear thread reference to prevent conflicts with subsequent recordings
        self.recording_thread = None
        
        # Reset all flags to clean state
        self.is_recording = False
        self._stop_event.clear()

        # Wait for device stabilization before switching back
        time.sleep(0.2)
        
        if self.original_device:
            try:
                self._set_output_device(self.original_device)
                print(_("→ Restored to original device: {}").format(self.original_device))
                # Wait for device switching to stabilize
                time.sleep(0.3)
            except Exception as e:
                print(_("→ Warning: Could not restore audio device: {}").format(e))

        with self.buffer_lock:
            if self.audio_buffer:
                full_audio = self._bytes_to_audio(self.audio_buffer)
                print(_("→ Total system audio length: {:.1f}s").format(len(full_audio)/self.sr))
                return full_audio
        return None

    def get_speech_segments(self):
        """Get speech segments from queue"""
        # If we skipped system recording, return empty
        if self.skip_system_recording:
            return []
        
        segments = []
        while not self.audio_queue.empty():
            try:
                segment_bytes = self.audio_queue.get_nowait()
                segments.append(np.frombuffer(segment_bytes, dtype=np.float32).copy())
            except queue.Empty:
                break
        return segments


if __name__ == "__main__":
    print(_("System audio recording test (5 seconds) - macOS"))
    recorder = SystemAudioRecorder(sample_rate=16000)

    if recorder.start():
        print(_("Recording..."))
        time.sleep(5)
        audio_data = recorder.stop()

        if audio_data is not None and len(audio_data) > 0:
            output_dir = "./test_recordings"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_path = f"{output_dir}/system_audio_test_{timestamp}.wav"
            mp3_path = f"{output_dir}/system_audio_test_{timestamp}.mp3"

            wav.write(wav_path, 16000, (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16))
            AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", parameters=["-q:a", "2"])
            os.unlink(wav_path)

            segments = recorder.get_speech_segments()
            print(_("Recording finished, MP3: {}, speech segments: {}").format(mp3_path, len(segments)))
        else:
            print(_("No audio recorded"))
    else:
        print(_("Unable to start recording"))