import time
import threading
import queue
import numpy as np
import soundcard as sc
import os
import warnings
from datetime import datetime
import scipy.io.wavfile as wav
from pydub import AudioSegment
from soundcard.mediafoundation import SoundcardRuntimeWarning
from core.audio_utils import SileroVAD
from core.i18n import _
import pythoncom

warnings.filterwarnings("ignore", category=SoundcardRuntimeWarning, message="data discontinuity in recording")

class SystemAudioRecorder:
    """System audio recorder for Windows loopback"""
    def __init__(self, sample_rate=16000, vad_instance=None):
        """Initialize the system audio recorder"""
        self.sr = sample_rate
        self.vad = vad_instance if vad_instance else SileroVAD()
        self.is_recording = False
        self.is_stopping = False
        self.recording_thread = None
        self.audio_queue = queue.Queue(maxsize=100)
        self.audio_buffer = []
        self.buffer_lock = threading.RLock()
        self.segment_counter = 0

    def start(self):
        """Start system audio recording"""
        if self.is_recording:
            return False
        try:
            speaker = sc.default_speaker()
            self.loopback = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            print(_("→ System audio device: {}").format(speaker.name))
        except Exception as e:
            print(_("→ Unable to initialize system audio: {}").format(e))
            return False
        self.is_recording = True
        self.is_stopping = False
        self.audio_buffer = []
        self.segment_counter = 0
        self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self.recording_thread.start()
        print(_("→ System audio recording started"))
        return True

    def _recording_loop(self):
        """System audio recording loop"""
        # Initialize COM for this thread (required for Windows audio)
        pythoncom.CoInitialize()
        try:
            with self.loopback.recorder(samplerate=self.sr) as recorder:
                silence_duration = 0.0
                speech_segment_buffer = []
                speech_active = False
                SILENCE_THRESHOLD = 1.5
                CHUNK_SIZE = 512
                while self.is_recording and not self.is_stopping:
                    try:
                        audio_chunk = recorder.record(numframes=CHUNK_SIZE)
                        if audio_chunk is None or len(audio_chunk) == 0:
                            continue
                        # Convert to mono if stereo
                        if audio_chunk.ndim == 2:
                            audio_chunk = audio_chunk.mean(axis=1)
                        audio_chunk = audio_chunk.astype(np.float32)
                        chunk_bytes = audio_chunk.tobytes()
                        with self.buffer_lock:
                            self.audio_buffer.append(chunk_bytes)
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
                                        print(_("→ [System] Speech segment {}: {:.1f}s").format(
                                            self.segment_counter, len(segment_audio)/self.sr))
                                    except queue.Full:
                                        print(_("→ [System] Queue is full"))
                                    speech_segment_buffer = []
                                    speech_active = False
                                    silence_duration = 0.0
                            else:
                                # Limit buffer size for silence
                                max_buffer_chunks = int(1.0 * self.sr / CHUNK_SIZE)
                                if len(speech_segment_buffer) > max_buffer_chunks:
                                    speech_segment_buffer = speech_segment_buffer[-max_buffer_chunks:]
                    except Exception as e:
                        if self.is_recording:
                            print(_("→ [System] Recording error: {}").format(e))
                        break
        except Exception as e:
            print(_("→ [System] Recording failed: {}").format(e))
            self.is_recording = False
        finally:
            # Uninitialize COM when thread exits
            pythoncom.CoUninitialize()

    def _bytes_to_audio(self, byte_chunks):
        """Convert byte chunks to numpy audio array"""
        if not byte_chunks:
            return np.array([], dtype=np.float32)
        return np.frombuffer(b''.join(byte_chunks), dtype=np.float32).copy()

    def stop(self):
        """Stop system audio recording and return audio data"""
        if not self.is_recording:
            return None
        print(_("→ Stopping system audio recording..."))
        # Set stopping flags FIRST before any operations
        self.is_stopping = True
        self.is_recording = False
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=5)  # Increased timeout for safer cleanup
            if self.recording_thread.is_alive():
                print(_("→ Warning: Recording thread still alive, forcing cleanup"))
        with self.buffer_lock:
            if self.audio_buffer:
                full_audio = self._bytes_to_audio(self.audio_buffer)
                print(_("→ Total system audio length: {:.1f}s").format(len(full_audio)/self.sr))
                return full_audio
        return None

    def get_speech_segments(self):
        """Get speech segments from queue"""
        segments = []
        while not self.audio_queue.empty():
            try:
                segment_bytes = self.audio_queue.get_nowait()
                segments.append(np.frombuffer(segment_bytes, dtype=np.float32).copy())
            except queue.Empty:
                break
        return segments

if __name__ == "__main__":
    print(_("System audio recording test (5 seconds) - Windows"))
    # Test with new VAD instance
    test_vad = SileroVAD()
    recorder = SystemAudioRecorder(sample_rate=16000, vad_instance=test_vad)
    recorder.start()
    print(_("Recording..."))
    time.sleep(5)
    audio_data = recorder.stop()
    if audio_data is not None and len(audio_data) > 0:
        output_dir = "./"
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