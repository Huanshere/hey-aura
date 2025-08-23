import time
import tempfile
import os
import datetime
import queue
import threading
import numpy as np
import scipy.io.wavfile as wav

from core.i18n import _
from core import transcription_queue


class MeetingTranscriptionProcessor:
    """Transcription processor for meeting mode audio."""

    def __init__(self, transcriber_ref, audio_processor):
        """Initialize the transcription processor."""
        self.transcriber_ref = transcriber_ref
        self.audio_processor = audio_processor

        # Transcription state
        self.meeting_transcription_thread = None
        self.system_transcription_thread = None
        self.meeting_transcription_active = False
        self.system_transcription_active = False

        # Transcription results
        self.meeting_transcripts = []

    def start_transcription_processing(self):
        """Start transcription processing threads."""
        # Start microphone transcription thread
        self.meeting_transcription_thread = threading.Thread(target=self._process_microphone_transcription, daemon=True)
        self.meeting_transcription_thread.start()

        # Only start system audio transcription if not in built-in speaker mode
        if (hasattr(self.audio_processor, 'system_recorder') and 
            self.audio_processor.system_recorder and 
            not getattr(self.audio_processor.system_recorder, 'skip_system_recording', False)):
            # Start system audio transcription thread
            self.system_transcription_thread = threading.Thread(target=self._process_system_transcription, daemon=True)
            self.system_transcription_thread.start()
            print(_("→ 💡 System audio transcription thread started"))
        else:
            print(_("→ Skipping system audio transcription (built-in speaker mode)"))

    def _process_microphone_transcription(self):
        """Process microphone audio queue and transcribe."""
        segment_counter = 0
        SPEECH_PADDING_MS = 300

        while (hasattr(self.transcriber_ref, 'meeting_recorder') and
               self.transcriber_ref.meeting_recorder.meeting_mode) or not self.audio_processor.meeting_audio_queue.empty():
            try:
                # Get audio bytes from queue
                segment_bytes = self.audio_processor.meeting_audio_queue.get(timeout=1.0)
                segment_counter += 1
                self.meeting_transcription_active = True

                # Safely update tray status
                try:
                    self.transcriber_ref.tray.set_status("processing")
                except Exception:
                    pass

                # Convert bytes to audio (make writable copy)
                segment_audio = np.frombuffer(segment_bytes, dtype=np.float32).copy()

                # Enhance audio
                if not segment_audio.flags.writeable:
                    segment_audio = segment_audio.copy()
                segment_audio = self.transcriber_ref.audio_enhancer.enhance_audio(segment_audio)

                # Extract speech segments using microphone VAD
                if self.audio_processor.microphone_vad is not None:
                    processed_audio = self.audio_processor.microphone_vad.extract_speech_segments(
                        segment_audio, self.transcriber_ref.sr, SPEECH_PADDING_MS
                    )
                else:
                    print(_("  → Warning: Microphone VAD is None, using raw audio"))
                    processed_audio = segment_audio

                print(_("  → Starting ASR transcription, length: {:.1f} s ... ").format(
                    processed_audio.size / self.transcriber_ref.sr
                ))

                if processed_audio.size / self.transcriber_ref.sr < 0.5:
                    print(_("  → Warning: Audio too short, skipping transcription"))
                    try:
                        self.transcriber_ref.tray.set_status("recording")
                    except Exception:
                        pass
                    continue

                # Save to temp file and transcribe
                tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                wav.write(tf.name, self.transcriber_ref.sr,
                          (np.clip(processed_audio, -1.0, 1.0) * 32767).astype(np.int16))
                tf.close()

                start_time = time.time()

                try:
                    text = transcription_queue.transcribe(
                        audio_path=tf.name,
                        language=self.transcriber_ref.language
                    )
                    print(_("  ✓ Transcription completed in {:.1f} s").format(time.time() - start_time))
                except Exception as e:
                    print(_("  ❌ Meeting transcription error: {}").format(e))
                    text = ""
                finally:
                    try:
                        os.unlink(tf.name)
                    except:
                        pass

                if text.strip():
                    timestamp = datetime.datetime.now()
                    text = text.strip() + ('' if text and text[-1] in '.,!?;:。，！？；：' else '.')

                    transcript_entry = {
                        'timestamp': timestamp,
                        'text': text,
                        'source': 'microphone'  # Mark as microphone audio
                    }
                    self.meeting_transcripts.append(transcript_entry)

                    print(_("→ [Mic-{}] {}").format(timestamp.strftime("%H:%M:%S"), text))
                else:
                    print(_("→ Transcription result is empty"))

                if not (hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_stopping):
                    try:
                        self.transcriber_ref.tray.set_status("recording")
                    except Exception:
                        pass
                self.meeting_transcription_active = False

            except queue.Empty:
                self.meeting_transcription_active = False
                continue
            except Exception as e:
                if not (hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_stopping):
                    print(_("  → Meeting transcription error: {}").format(e))
                    try:
                        self.transcriber_ref.tray.set_status("recording")
                    except Exception:
                        pass
                self.meeting_transcription_active = False

    def _process_system_transcription(self):
        """Process system audio transcription independently."""
        segment_counter = 0
        SPEECH_PADDING_MS = 300

        print(_("🎤 [System] Independent transcription processor started"))

        while (hasattr(self.transcriber_ref, 'meeting_recorder') and
               self.transcriber_ref.meeting_recorder.meeting_mode) or not self.audio_processor.system_audio_queue.empty():
            try:
                # Get audio bytes from system queue
                segment_bytes = self.audio_processor.system_audio_queue.get(timeout=1.0)
                segment_counter += 1
                self.system_transcription_active = True

                print(_("  → [System] Starting independent ASR transcription #{} ... ").format(segment_counter))

                # Convert bytes to audio (make writable copy)
                segment_audio = np.frombuffer(segment_bytes, dtype=np.float32).copy()

                # Enhance audio
                if not segment_audio.flags.writeable:
                    segment_audio = segment_audio.copy()
                segment_audio = self.transcriber_ref.audio_enhancer.enhance_audio(segment_audio)

                # Extract speech segments using system VAD (independent instance)
                if self.audio_processor.system_vad is not None:
                    processed_audio = self.audio_processor.system_vad.extract_speech_segments(
                        segment_audio, self.transcriber_ref.sr, SPEECH_PADDING_MS
                    )
                else:
                    print(_("  → [System] Warning: System VAD is None, using raw audio"))
                    processed_audio = segment_audio

                duration = processed_audio.size / self.transcriber_ref.sr
                print(_("  → [System] Processing audio length: {:.1f}s").format(duration))

                if duration < 0.5:
                    print(_("  → [System] Warning: Audio too short, skipping transcription"))
                    self.system_transcription_active = False
                    continue

                # Save to temp file and transcribe
                tf = tempfile.NamedTemporaryFile(suffix="_system.wav", delete=False)
                wav.write(tf.name, self.transcriber_ref.sr,
                          (np.clip(processed_audio, -1.0, 1.0) * 32767).astype(np.int16))
                tf.close()

                start_time = time.time()

                try:
                    text = transcription_queue.transcribe(
                        audio_path=tf.name,
                        language=self.transcriber_ref.language
                    )
                    transcription_time = time.time() - start_time
                    print(_("  ✓ [System] Transcription completed in {:.1f}s").format(transcription_time))
                except Exception as e:
                    print(_("  ❌ [System] Transcription error: {}").format(e))
                    text = ""
                finally:
                    try:
                        os.unlink(tf.name)
                    except:
                        pass

                if text.strip():
                    timestamp = datetime.datetime.now()
                    text = text.strip() + ('' if text and text[-1] in '.,!?;:。，！？；：' else '.')

                    transcript_entry = {
                        'timestamp': timestamp,
                        'text': text,
                        'source': 'system'  # Mark as system audio
                    }
                    self.meeting_transcripts.append(transcript_entry)

                    print(_("→ [System-{:02d}] {}").format(segment_counter, text))
                else:
                    print(_("→ [System] Transcription result is empty"))

                self.system_transcription_active = False

            except queue.Empty:
                self.system_transcription_active = False
                continue
            except Exception as e:
                if not (hasattr(self.transcriber_ref, 'meeting_recorder') and self.transcriber_ref.meeting_recorder.meeting_stopping):
                    print(_("  → [System] Independent transcription error: {}").format(e))
                self.system_transcription_active = False

        print(_("🎤 [System] Independent transcription processor stopped"))

    def wait_for_transcription_completion(self, max_wait_time=30):
        """Wait for all transcriptions to complete."""
        print(_("⏳ Waiting for final transcriptions to complete..."))
        try:
            self.transcriber_ref.tray.set_status("processing")
        except Exception:
            pass

        start_wait = time.time()

        # Wait for microphone and system audio transcription to complete, safer queue check
        while (time.time() - start_wait < max_wait_time):
            try:
                mic_queue_size = self.audio_processor.meeting_audio_queue.qsize()
                sys_queue_size = self.audio_processor.system_audio_queue.qsize() if self.system_transcription_thread else 0

                # Check if transcription is still active or there are items in the queue
                mic_busy = mic_queue_size > 0 or self.meeting_transcription_active
                sys_busy = (sys_queue_size > 0 or self.system_transcription_active) if self.system_transcription_thread else False

                if not mic_busy and not sys_busy:
                    break

                if mic_queue_size > 0 or sys_queue_size > 0:
                    print(_("  → {} mic + {} system segments remaining").format(mic_queue_size, sys_queue_size))

                time.sleep(0.5)
            except Exception as e:
                print(_("→ Error checking transcription queues: {}").format(e))
                break

        # Wait for transcription threads to finish
        if self.meeting_transcription_thread and self.meeting_transcription_thread.is_alive():
            print(_("→ Waiting for microphone transcription thread..."))
            self.meeting_transcription_thread.join(timeout=5)
            if self.meeting_transcription_thread.is_alive():
                print(_("→ Warning: Microphone transcription thread did not terminate cleanly"))

        if self.system_transcription_thread and self.system_transcription_thread.is_alive():
            print(_("→ Waiting for system transcription thread..."))
            self.system_transcription_thread.join(timeout=5)
            if self.system_transcription_thread.is_alive():
                print(_("→ Warning: System transcription thread did not terminate cleanly"))

        if time.time() - start_wait >= max_wait_time:
            print(_("⚠️ Timeout waiting for transcriptions, some audio may not be processed"))

    def get_transcripts(self):
        """Get all transcription results."""
        return self.meeting_transcripts

    def clear_transcripts(self):
        """Clear all transcription results."""
        self.meeting_transcripts = []

    def cleanup_resources(self):
        """Cleanup transcription processor resources."""
        # Stop all transcription processing
        if self.meeting_transcription_thread and self.meeting_transcription_thread.is_alive():
            self.meeting_transcription_thread.join(timeout=3)
        
        if self.system_transcription_thread and self.system_transcription_thread.is_alive():
            self.system_transcription_thread.join(timeout=3)
        
        # Clear transcripts
        self.meeting_transcripts = []
        
        # Reset active flags
        self.meeting_transcription_active = False
        self.system_transcription_active = False