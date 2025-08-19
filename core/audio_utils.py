import numpy as np
from typing import List, Optional
import sounddevice as sd
import noisereduce as nr
import pyloudnorm as pyln
import os
import warnings
from .i18n import _
import onnxruntime

class AudioDeviceSelector:
    @staticmethod
    def get_best_input_device() -> Optional[int]:
        devices = sd.query_devices()
        default_input = sd.default.device[0]
        
        external_kw = ['USB', 'External', 'Wireless', 'Blue', 'Logitech', 'Rode', 
                      'Audio-Technica', 'Shure', 'Yeti', 'Snowball', 'Samson', 
                      'HyperX']
        builtin_kw = ['MacBook', 'Built-in', 'Internal', 'System', 'Default']
        headphone_kw = ['AirPod', 'Headphone', 'Headset', 'Earphone', 
                       'Earbud', 'Beats', 'Sony WH', 'Bose', 'JBL']
        virtual_kw = ['Virtual', 'WeMeet', 'Zoom', 'Teams', 'Skype', 'Discord', 
                     'OBS', 'Soundflower', 'BlackHole', 'Loopback', 'Aggregate']
        
        if default_input is not None:
            try:
                default_device = devices[default_input]
                default_name = default_device['name'].lower()
                if not any(kw.lower() in default_name for kw in headphone_kw):
                    print(_("→ 🎙️ Using default audio device: {}").format(default_device['name']))
                    return default_input
            except (IndexError, KeyError):
                pass
        
        print(_("📍 Default device is headphone mic, enabling priority selection"))
        
        mics = {
            "external": [], "builtin": [], "headphone": [], "other": []
        }
        
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] <= 0:
                continue
                
            name = dev['name'].lower()
            if any(kw.lower() in name for kw in virtual_kw):
                continue
                
            if any(kw.lower() in name for kw in external_kw):
                mics["external"].append((i, dev['name']))
            elif any(kw.lower() in name for kw in builtin_kw):
                mics["builtin"].append((i, dev['name']))
            elif any(kw.lower() in name for kw in headphone_kw):
                mics["headphone"].append((i, dev['name']))
            else:
                mics["other"].append((i, dev['name']))
        
        for k, v, p in [("external", mics["external"], "External mic"), 
                        ("builtin", mics["builtin"], "Built-in mic"),
                        ("headphone", mics["headphone"], "Headphone mic")]:
            if v:
                print(_("🎙️ Selected audio device: {} ({})").format(v[0][1], p))
                return v[0][0]
        
        return None

class SileroVAD:
    def __init__(self, threshold=0.5, min_speech_duration_ms=250, 
                 min_silence_duration_ms=100, window_size_samples=1536):
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self.window_size_samples = window_size_samples
        self.model = None
        self.sample_rate = 16000
        
    def initialize(self):
        if self.model: 
            return
            
        try:
            onnx_model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'silero_vad.onnx')
            # Create ONNX inference session with optimized settings
            opts = onnxruntime.SessionOptions()
            opts.inter_op_num_threads = 1
            opts.intra_op_num_threads = 1
            
            # Each instance gets its own completely independent ONNX session
            self.model = onnxruntime.InferenceSession(
                onnx_model_path, 
                providers=['CPUExecutionProvider'], 
                sess_options=opts
            )
            
            # Initialize states for this instance
            self._reset_states()
            
        except Exception as e:
            print(_("Warning: Silero VAD ONNX init failed: {}").format(e))
            print(_("→ Skipping VAD processing"))
            self.model = None
    
    def _reset_states(self):
        """Reset VAD internal states"""
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self._last_sr = 0
        self._last_batch_size = 0
    
    def get_speech_timestamps(self, audio: np.ndarray, sample_rate=16000) -> List[dict]:
        if not self.model:
            return [{'start': 0, 'end': len(audio)}]
        
        # Resample if needed
        if sample_rate != self.sample_rate:
            print(_("Warning: Sample rate mismatch {} != {}, resampling").format(sample_rate, self.sample_rate))
            ratio = self.sample_rate / sample_rate
            audio = np.interp(
                np.arange(0, len(audio), 1/ratio),
                np.arange(len(audio)),
                audio
            ).astype(np.float32)
        
        try:
            # Ensure audio is writable
            if not audio.flags.writeable:
                audio = audio.copy()
            
            # Use simplified timestamp extraction (based on Silero's get_speech_timestamps)
            return self._get_speech_timestamps_onnx(audio)
            
        except Exception as e:
            print(_("VAD processing error: {}").format(e))
            return [{'start': 0, 'end': len(audio)}]
    
    def _get_speech_timestamps_onnx(self, audio: np.ndarray) -> List[dict]:
        """ONNX-based speech timestamp extraction"""
        window_size_samples = 512  # Fixed for 16kHz
        min_speech_samples = self.sample_rate * self.min_speech_duration_ms / 1000
        min_silence_samples = self.sample_rate * self.min_silence_duration_ms / 1000
        speech_pad_samples = self.sample_rate * 30 / 1000  # 30ms padding
        
        # Reset states for this audio
        self._reset_states()
        
        audio_length_samples = len(audio)
        speech_probs = []
        
        # Process audio in chunks
        for current_start_sample in range(0, audio_length_samples, window_size_samples):
            chunk = audio[current_start_sample: current_start_sample + window_size_samples]
            if len(chunk) < window_size_samples:
                chunk = np.pad(chunk, (0, window_size_samples - len(chunk)))
            
            # ONNX inference for this chunk
            speech_prob = self._predict_chunk(chunk)
            speech_probs.append(speech_prob)
        
        # Convert probabilities to timestamps
        triggered = False
        speeches = []
        current_speech = {}
        temp_end = 0
        neg_threshold = max(self.threshold - 0.15, 0.01)
        
        for i, speech_prob in enumerate(speech_probs):
            if (speech_prob >= self.threshold) and temp_end:
                temp_end = 0
            
            if (speech_prob >= self.threshold) and not triggered:
                triggered = True
                current_speech['start'] = window_size_samples * i
                continue
            
            if (speech_prob < neg_threshold) and triggered:
                if not temp_end:
                    temp_end = window_size_samples * i
                if (window_size_samples * i) - temp_end < min_silence_samples:
                    continue
                else:
                    current_speech['end'] = temp_end
                    if (current_speech['end'] - current_speech['start']) > min_speech_samples:
                        speeches.append(current_speech)
                    current_speech = {}
                    temp_end = 0
                    triggered = False
                    continue
        
        # Handle final speech segment
        if current_speech and (audio_length_samples - current_speech['start']) > min_speech_samples:
            current_speech['end'] = audio_length_samples
            speeches.append(current_speech)
        
        # Add padding
        for i, speech in enumerate(speeches):
            if i == 0:
                speech['start'] = int(max(0, speech['start'] - speech_pad_samples))
            if i != len(speeches) - 1:
                silence_duration = speeches[i+1]['start'] - speech['end']
                if silence_duration < 2 * speech_pad_samples:
                    speech['end'] += int(silence_duration // 2)
                    speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - silence_duration // 2))
                else:
                    speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))
                    speeches[i+1]['start'] = int(max(0, speeches[i+1]['start'] - speech_pad_samples))
            else:
                speech['end'] = int(min(audio_length_samples, speech['end'] + speech_pad_samples))
        
        return speeches
    
    def _predict_chunk(self, chunk: np.ndarray) -> float:
        """Predict speech probability for a single chunk using ONNX"""
        # Prepare input
        x = chunk.reshape(1, -1).astype(np.float32)  # Add batch dimension
        x = np.concatenate([self._context, x], axis=1)
        
        # ONNX inference
        ort_inputs = {
            'input': x,
            'state': self._state,
            'sr': np.array(self.sample_rate, dtype=np.int64)
        }
        ort_outs = self.model.run(None, ort_inputs)
        out, state = ort_outs
        
        # Update states
        self._state = state
        self._context = x[:, -64:]  # Keep last 64 samples as context
        
        return float(out[0, 0])  # Return probability
    
    def extract_speech_segments(self, audio: np.ndarray, sample_rate=16000, padding_ms=300) -> np.ndarray:
        if not self.model:
            return audio.copy()  # Return a copy to ensure it's writable
            
        timestamps = self.get_speech_timestamps(audio, sample_rate)
        
        if not timestamps:
            print(_("No speech detected"))
            return np.array([], dtype=audio.dtype)
        
        # Calculate padding samples
        padding_samples = int(padding_ms * sample_rate / 1000)
        
        # Find the overall speech range (from first start to last end)
        overall_start = timestamps[0]['start']
        overall_end = timestamps[-1]['end']
        
        # Extend the range by padding_ms, but keep within audio bounds
        extended_start = max(0, overall_start - padding_samples)
        extended_end = min(len(audio), overall_end + padding_samples)
        
        # Extract the extended segment that includes original audio padding
        result = audio[extended_start:extended_end].copy()
        
        return result
    
    def is_speech_realtime(self, audio_chunk: np.ndarray, sample_rate=16000) -> bool:
        if not self.model:
            return np.mean(np.abs(audio_chunk)) > 0.01
        
        req_samples = 512 if sample_rate == 16000 else 256
        
        # Ensure correct chunk size
        if len(audio_chunk) != req_samples:
            if len(audio_chunk) < req_samples:
                audio_chunk = np.pad(audio_chunk, (0, req_samples - len(audio_chunk)), 'constant')
            else:
                audio_chunk = audio_chunk[:req_samples]
        
        # Resample if needed
        if sample_rate != self.sample_rate:
            ratio = self.sample_rate / sample_rate
            audio_chunk = np.interp(
                np.arange(0, len(audio_chunk), 1/ratio), 
                np.arange(len(audio_chunk)), 
                audio_chunk
            ).astype(np.float32)
            
            if len(audio_chunk) < 512:
                audio_chunk = np.pad(audio_chunk, (0, 512 - len(audio_chunk)), 'constant')
            elif len(audio_chunk) > 512:
                audio_chunk = audio_chunk[:512]
        
        try:
            # ONNX-based realtime speech detection
            speech_prob = self._predict_chunk(audio_chunk)
            return speech_prob > self.threshold
        except Exception as e:
            print(_("Realtime VAD error: {}").format(e))
            return np.mean(np.abs(audio_chunk)) > 0.01  # Fallback to energy detection


class AudioEnhancer:
    def __init__(self, sample_rate=16000):
        self.sr = sample_rate
    
    def _to_mono_1d(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        if x.ndim > 1: x = np.squeeze(x)
        x = x.reshape(-1).astype(np.float32, copy=False)
        return np.clip(np.nan_to_num(x, copy=False), -1.0, 1.0)
    
    def _loudness_normalize(self, audio: np.ndarray, target_lufs=-23.0) -> np.ndarray:
        """Normalize audio using LUFS loudness standard"""
        a = np.asarray(audio, dtype=np.float32)
        if a.size == 0:
            return a
        
        meter = pyln.Meter(self.sr)
        loudness = meter.integrated_loudness(a)
        
        # Suppress the clipped samples warning from pyloudnorm
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Possible clipped samples in output")
            normalized = pyln.normalize.loudness(a, loudness, target_lufs)
        
        return np.clip(np.asarray(normalized, dtype=np.float32), -1.0, 1.0)
    
    def enhance_audio(self, audio: np.ndarray) -> np.ndarray:
        # Ensure we're working with a writable copy
        if not audio.flags.writeable:
            audio = audio.copy()
        a = self._to_mono_1d(audio)
        n = a.size
        
        if n < max(20, int(self.sr * 0.08)):
            return a
        
        n_fft = 2048 if n >= 2048 else 1024 if n >= 1024 else 512 if n >= 512 else 256 if n >= 256 else 128
        hop = max(32, n_fft // 4)
        
        try:
            den = nr.reduce_noise(
                y=a, sr=self.sr, stationary=True, prop_decrease=0.9,
                n_fft=n_fft, hop_length=hop, win_length=n_fft
            )
        except Exception as e:
            print(_("Noise reduction failed ({}), skipping.").format(e))
            den = a
        
        # Apply loudness normalization instead of manual peak normalization
        normalized_audio = self._loudness_normalize(den, target_lufs=-23.0)
        
        return np.clip(np.tanh(normalized_audio * 0.8) * 0.95, -1.0, 1.0)
