#!/usr/bin/env python3
"""
Demo: Buffered mixed recording using working test_record.py approach
- Continuous microphone recording thread with buffer
- System audio recorded in parallel with test_record.py method
- Continuous mixing thread that processes from buffers
"""

import time
import sys
import threading
import queue
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from pathlib import Path
from datetime import datetime
from pydub import AudioSegment
import tempfile
import os
import uuid
from collections import deque

# Import system audio recording from test_record.py
from Foundation import NSObject, NSURL, NSDate, NSRunLoop
import objc
from ScreenCaptureKit import (
    SCShareableContent, SCContentFilter, SCStream, SCStreamConfiguration
)
try:
    from ScreenCaptureKit import SCStreamOutputTypeAudio as AUDIO_OUT_TYPE
except Exception:
    from ScreenCaptureKit import SCStreamOutputType as _SCType
    AUDIO_OUT_TYPE = _SCType.Audio

from AVFoundation import (
    AVAssetWriter, AVAssetWriterInput, AVMediaTypeAudio, AVFileTypeWAVE
)
from CoreMedia import CMSampleBufferGetPresentationTimeStamp, CMTimeMakeWithSeconds

kAudioFormatLinearPCM = 1819304813

def wait(cond, t=5, s=0.02):
    st = time.time()
    while not cond():
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(s))
        if t and time.time()-st > t: break

def get_content():
    b = {"ok": 0, "c": None, "e": None}
    SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, lambda c,e: b.update(ok=1, c=c, e=e))
    wait(lambda: b["ok"])
    if b["e"]: raise RuntimeError(b["e"])
    return b["c"]

def mk_cfg(sr=48000, ch=1, ex=True):
    c = SCStreamConfiguration.alloc().init()
    c.setCapturesAudio_(True)
    c.setCaptureMicrophone_(False)
    c.setExcludesCurrentProcessAudio_(ex)
    c.setSampleRate_(sr); c.setChannelCount_(ch)
    c.setWidth_(64); c.setHeight_(64)
    c.setMinimumFrameInterval_(CMTimeMakeWithSeconds(1, 1000))
    if hasattr(c, "setQueueDepth_"): c.setQueueDepth_(1)
    return c

class AudioOut(NSObject):
    def initWithURL_sampleRate_channels_(self, url, sr, ch):
        self = objc.super(AudioOut, self).init()
        if not self: return None
        self.on = self.done = False
        
        self.w, e = AVAssetWriter.alloc().initWithURL_fileType_error_(
            url, AVFileTypeWAVE, None)
        if e: raise RuntimeError(f"Writer: {e}")
        
        self.ai = AVAssetWriterInput.alloc().initWithMediaType_outputSettings_(
            AVMediaTypeAudio, {
                "AVFormatIDKey": kAudioFormatLinearPCM,
                "AVSampleRateKey": sr, 
                "AVNumberOfChannelsKey": ch,
                "AVLinearPCMBitDepthKey": 16,
                "AVLinearPCMIsFloatKey": False,
                "AVLinearPCMIsBigEndianKey": False,
                "AVLinearPCMIsNonInterleaved": False,
            })
        self.ai.setExpectsMediaDataInRealTime_(True)
        if self.w.canAddInput_(self.ai): self.w.addInput_(self.ai)
        else: raise RuntimeError("Can't add input")
        return self

    def stream_didOutputSampleBuffer_ofType_(self, s, sb, t):
        if t != AUDIO_OUT_TYPE: return
        if not self.on:
            if not self.w.startWriting(): 
                raise RuntimeError(f"Write: {self.w.error()}")
            self.w.startSessionAtSourceTime_(CMSampleBufferGetPresentationTimeStamp(sb))
            self.on = True
        if self.ai.isReadyForMoreMediaData(): 
            self.ai.appendSampleBuffer_(sb)

    def finish(self):
        if self.done: return
        self.ai.markAsFinished()
        d = {"ok": 0}
        self.w.finishWritingWithCompletionHandler_(lambda: d.update(ok=1))
        wait(lambda: d["ok"])
        self.done = True

class BufferedMixedRecorder:
    """Buffered recorder that continuously mixes mic and system audio"""
    
    def __init__(self, sample_rate=48000, channels=1):
        self.sr = sample_rate
        self.channels = channels
        
        # Audio buffers - use deques for efficient append/popleft operations
        self.mic_buffer = deque()
        self.system_buffer = deque()
        self.mixed_buffer = deque()
        
        # Control flags
        self.recording = False
        self.threads = []
        
        # System audio path
        self.system_audio_path = None
        
        # Mixing parameters
        self.chunk_duration = 0.25  # 0.25 second chunks for responsive mixing
        self.chunk_size = int(self.sr * self.chunk_duration)
        
        # Volume controls
        self.mic_volume = 1.0
        self.system_volume = 0.8
        
        # Synchronization
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'mic_chunks': 0,
            'system_chunks': 0,
            'mixed_chunks': 0,
            'start_time': None
        }
    
    def microphone_recording_thread(self):
        """Continuous microphone recording with chunked buffering"""
        print("🎤 Starting buffered microphone recording...")
        
        try:
            # Setup stream
            stream = sd.InputStream(
                samplerate=self.sr,
                channels=self.channels,
                dtype=np.float32,
                blocksize=512,
                latency='low',
                device=None
            )
            stream.start()
            
            chunk_buffer = []
            
            while self.recording:
                try:
                    audio_data, overflowed = stream.read(512)
                    if overflowed:
                        print("⚠️ Microphone overflow")
                    
                    if audio_data is not None and len(audio_data) > 0:
                        # Flatten to mono
                        if audio_data.ndim > 1:
                            audio_data = audio_data.mean(axis=1)
                        
                        chunk_buffer.extend(audio_data)
                        
                        # Process complete chunks
                        while len(chunk_buffer) >= self.chunk_size:
                            chunk = np.array(chunk_buffer[:self.chunk_size], dtype=np.float32)
                            
                            with self.lock:
                                self.mic_buffer.append(chunk)
                                self.stats['mic_chunks'] += 1
                            
                            chunk_buffer = chunk_buffer[self.chunk_size:]
                
                except Exception as e:
                    if self.recording:
                        print(f"Mic error: {e}")
                    break
            
            # Save remaining audio
            if chunk_buffer:
                chunk = np.array(chunk_buffer, dtype=np.float32)
                with self.lock:
                    self.mic_buffer.append(chunk)
                    self.stats['mic_chunks'] += 1
            
            stream.stop()
            stream.close()
            print("✓ Microphone recording finished")
            
        except Exception as e:
            print(f"❌ Microphone thread error: {e}")
    
    def system_audio_recording_thread(self):
        """System audio recording using test_record.py approach"""
        print("🔊 Starting system audio recording...")
        
        try:
            # Create unique temporary file
            temp_dir = Path(tempfile.gettempdir()) / "hey_aura_demo"
            temp_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.system_audio_path = str(temp_dir / f"system_{timestamp}_{uuid.uuid4().hex[:8]}.wav")
            
            # Setup ScreenCaptureKit recording
            cnt = get_content()
            dsp = cnt.displays()[0] if cnt.displays() else None
            if not dsp:
                raise RuntimeError("No display")
            
            flt = SCContentFilter.alloc().initWithDisplay_includingApplications_exceptingWindows_(
                dsp, cnt.applications(), [])
            cfg = mk_cfg(self.sr, self.channels, True)
            
            url = NSURL.fileURLWithPath_(self.system_audio_path)
            stm = SCStream.alloc().initWithFilter_configuration_delegate_(flt, cfg, None)
            ao = AudioOut.alloc().initWithURL_sampleRate_channels_(url, self.sr, self.channels)
            
            ok, e = stm.addStreamOutput_type_sampleHandlerQueue_error_(ao, AUDIO_OUT_TYPE, None, None)
            if e:
                raise RuntimeError(f"Add: {e}")
            
            # Start recording
            st = {"ok": 0, "e": None}
            stm.startCaptureWithCompletionHandler_(lambda e: st.update(ok=1, e=e))
            wait(lambda: st["ok"])
            if st["e"]:
                raise RuntimeError(f"Start: {st['e']}")
            
            print("✓ System audio recording started")
            
            # Keep running while recording
            while self.recording:
                time.sleep(0.1)
            
            # Stop recording
            sp = {"ok": 0}
            stm.stopCaptureWithCompletionHandler_(
                lambda e: (e and print(f"Stop: {e}")) or sp.update(ok=1))
            wait(lambda: sp["ok"])
            
            ao.finish()
            print("✓ System audio recording finished")
            
            # Process the recorded file into chunks
            self.process_system_audio_file()
            
        except Exception as e:
            print(f"❌ System audio thread error: {e}")
    
    def process_system_audio_file(self):
        """Process the system audio WAV file into chunks"""
        if not self.system_audio_path or not os.path.exists(self.system_audio_path):
            print("⚠️ No system audio file to process")
            return
        
        try:
            print("📊 Processing system audio file...")
            sr, audio_data = wav.read(self.system_audio_path)
            audio_float = audio_data.astype(np.float32) / 32768.0
            
            # Split into chunks
            chunk_count = 0
            for i in range(0, len(audio_float), self.chunk_size):
                chunk = audio_float[i:i+self.chunk_size]
                if len(chunk) > 0:
                    with self.lock:
                        self.system_buffer.append(chunk)
                        self.stats['system_chunks'] += 1
                    chunk_count += 1
            
            print(f"✓ Processed {chunk_count} system audio chunks")
            
        except Exception as e:
            print(f"❌ Error processing system audio: {e}")
        finally:
            # Clean up temp file
            if os.path.exists(self.system_audio_path):
                os.unlink(self.system_audio_path)
    
    def mixing_thread(self):
        """Continuous mixing thread that processes chunks from both buffers"""
        print("🎛️ Starting continuous mixing...")
        
        mixed_count = 0
        last_report_time = time.time()
        
        while self.recording or self.has_pending_audio():
            try:
                # Check if we have chunks to mix
                with self.lock:
                    has_mic = len(self.mic_buffer) > 0
                    has_system = len(self.system_buffer) > 0
                
                if has_mic or has_system:
                    # Get chunks
                    mic_chunk = None
                    system_chunk = None
                    
                    with self.lock:
                        if has_mic:
                            mic_chunk = self.mic_buffer.popleft()
                        if has_system:
                            system_chunk = self.system_buffer.popleft()
                    
                    # Create mixed chunk
                    if mic_chunk is not None and system_chunk is not None:
                        # Align chunk sizes
                        min_len = min(len(mic_chunk), len(system_chunk))
                        mixed = (mic_chunk[:min_len] * self.mic_volume + 
                                system_chunk[:min_len] * self.system_volume) / 2.0
                        
                        # Handle remaining samples
                        if len(mic_chunk) > min_len:
                            with self.lock:
                                self.mic_buffer.appendleft(mic_chunk[min_len:])
                        if len(system_chunk) > min_len:
                            with self.lock:
                                self.system_buffer.appendleft(system_chunk[min_len:])
                    
                    elif mic_chunk is not None:
                        mixed = mic_chunk * self.mic_volume
                    elif system_chunk is not None:
                        mixed = system_chunk * self.system_volume
                    else:
                        time.sleep(0.01)
                        continue
                    
                    # Prevent clipping
                    mixed = np.clip(mixed, -1.0, 1.0)
                    
                    # Add to output buffer
                    with self.lock:
                        self.mixed_buffer.append(mixed)
                        self.stats['mixed_chunks'] += 1
                    
                    mixed_count += 1
                    
                    # Periodic status update
                    current_time = time.time()
                    if current_time - last_report_time > 1.0:  # Every second
                        with self.lock:
                            mic_pending = len(self.mic_buffer)
                            sys_pending = len(self.system_buffer)
                            mixed_total = len(self.mixed_buffer)
                        
                        duration = mixed_total * self.chunk_duration
                        print(f"\r🎵 Mixed: {mixed_total} chunks ({duration:.1f}s) | "
                              f"Pending: {mic_pending} mic, {sys_pending} sys", end='')
                        
                        last_report_time = current_time
                
                else:
                    time.sleep(0.01)  # Small delay when no audio
                    
            except Exception as e:
                print(f"Mixing error: {e}")
                continue
        
        print(f"\n✅ Mixing completed: {mixed_count} chunks processed")
    
    def has_pending_audio(self):
        """Check if there's still audio to process"""
        with self.lock:
            return len(self.mic_buffer) > 0 or len(self.system_buffer) > 0
    
    def start_recording(self, duration=10):
        """Start buffered recording for specified duration"""
        print(f"🎬 Starting buffered mixed recording for {duration}s...")
        print("📊 Progress will be shown below:")
        print("-" * 60)
        
        self.recording = True
        self.stats['start_time'] = time.time()
        
        # Start all threads
        mic_thread = threading.Thread(target=self.microphone_recording_thread, daemon=True)
        system_thread = threading.Thread(target=self.system_audio_recording_thread, daemon=True)
        mixing_thread = threading.Thread(target=self.mixing_thread, daemon=True)
        
        self.threads = [mic_thread, system_thread, mixing_thread]
        
        for thread in self.threads:
            thread.start()
        
        # Monitor progress
        start_time = time.time()
        try:
            while time.time() - start_time < duration:
                elapsed = time.time() - start_time
                remaining = duration - elapsed
                
                with self.lock:
                    mic_chunks = self.stats['mic_chunks']
                    sys_chunks = self.stats['system_chunks']
                    mixed_chunks = self.stats['mixed_chunks']
                
                print(f"\r⏱️  {elapsed:.1f}s | {remaining:.1f}s left | "
                      f"Chunks: {mic_chunks}🎤 {sys_chunks}🔊 {mixed_chunks}🎵", end='')
                
                time.sleep(0.5)
                
        except KeyboardInterrupt:
            print("\n⏹️ Recording interrupted by user")
        
        # Stop recording
        print(f"\n⏹️ Stopping recording...")
        self.recording = False
        
        # Wait for system audio to finish processing
        if system_thread.is_alive():
            system_thread.join(timeout=5)
        
        # Wait for mixing to complete
        print("⏳ Finalizing mix...")
        mixing_thread.join(timeout=10)
        
        # Wait for other threads
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        print("✅ All recording threads completed")
    
    def save_audio(self, output_dir="output"):
        """Save the mixed audio as MP3"""
        if not self.mixed_buffer:
            print("❌ No mixed audio to save")
            return
        
        print(f"💾 Saving mixed audio...")
        
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Concatenate all chunks
        with self.lock:
            mixed_audio = np.concatenate(list(self.mixed_buffer))
        
        # Save as WAV first
        wav_path = Path(output_dir) / f"buffered_mixed_{timestamp}.wav"
        wav.write(str(wav_path), self.sr, (mixed_audio * 32767).astype(np.int16))
        
        # Convert to MP3
        mp3_path = Path(output_dir) / f"buffered_mixed_{timestamp}.mp3"
        audio_segment = AudioSegment.from_wav(str(wav_path))
        audio_segment.export(str(mp3_path), format="mp3", parameters=["-q:a", "2"])
        
        # Remove temporary WAV
        wav_path.unlink()
        
        # Print statistics
        duration = len(mixed_audio) / self.sr
        total_time = time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
        
        print(f"💾 Mixed audio saved: {mp3_path}")
        print(f"📊 Statistics:")
        print(f"   Duration: {duration:.1f}s")
        print(f"   Total recording time: {total_time:.1f}s")
        print(f"   Mixed chunks: {self.stats['mixed_chunks']}")
        print(f"   Mic chunks: {self.stats['mic_chunks']}")
        print(f"   System chunks: {self.stats['system_chunks']}")
        print(f"   Sample rate: {self.sr} Hz")
        
        return mp3_path

def main():
    """Main demo function"""
    try:
        # Parse arguments
        duration = int(sys.argv[1]) if len(sys.argv) > 1 else 10
        
        print("🎬 Buffered Mixed Audio Recording Demo")
        print("=" * 60)
        print(f"Duration: {duration} seconds")
        print(f"Approach: Continuous buffered recording + mixing")
        print(f"Chunk size: 0.25s for responsive mixing")
        print("-" * 60)
        
        # Create and start recorder
        recorder = BufferedMixedRecorder(sample_rate=48000, channels=1)
        recorder.start_recording(duration)
        
        # Save results
        output_path = recorder.save_audio()
        
        print(f"\n✅ Demo completed successfully!")
        print(f"🎵 Output file: {output_path}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Demo stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()