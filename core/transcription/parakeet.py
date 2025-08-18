import os
import sys
import signal
import time
from typing import Optional

# Windows compatibility for NeMo - must be before NeMo import
if sys.platform == "win32" and not hasattr(signal, "SIGKILL"):
    signal.SIGKILL = signal.SIGTERM  # Simulate SIGKILL on Windows

import librosa
import numpy as np
import platform
import torch
import soundfile as sf

from core.transcription.base import TranscriptionModel
from core.i18n import _

class NeMoTranscriber(TranscriptionModel):
    """NeMo/Parakeet transcription model implementation"""
    
    def __init__(self, model_name: str = "nvidia/parakeet-tdt-0.6b-v2", **kwargs):
        super().__init__(model_name, **kwargs)
        self.model = None
        self.backend = None
        self.device = None
        self.sample_rate = 16000
    
    def initialize(self, **kwargs) -> None:
        """Initialize NeMo/Parakeet model"""
        if self.is_initialized: return
        
        print(f"→ {_('Initializing transcription model')}: {self.model_name}")
        start = time.time()
        
        os.environ["HF_HUB_CACHE"] = os.path.join(os.getcwd(), "models")
        if platform.system() == "Darwin":
            print(f"  {_('Using parakeet-mlx (macOS)')}")
            from parakeet_mlx import from_pretrained
            self.model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v2")
            self.backend, self.device = "mlx", "mps"
        else:
            print(f"  {_('Using NeMo')}")
            import nemo.collections.asr as nemo_asr
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = nemo_asr.models.ASRModel.from_pretrained(self.model_name).to(self.device).eval()
            for p in self.model.parameters():
                p.requires_grad = False
            self.backend = "nemo"
        
        self.is_initialized = True
        print(f"→ {_('Model ready')} ({self.backend}, {self.device}) {time.time() - start:.2f}s")
    
    def transcribe(self, audio_path: str, language: Optional[str] = None, **kwargs) -> str:
        audio_data, _ = sf.read(audio_path)

        if _ != self.sample_rate:
            audio_data = librosa.resample(audio_data, orig_sr=_, target_sr=self.sample_rate)
        
        if self.backend == "nemo":
            with torch.no_grad():
                transcripts = self.model.transcribe([audio_path], batch_size=1, verbose=False, timestamps=False)
                if transcripts and len(transcripts) > 0:
                    # Handle both string and Hypothesis object returns
                    result = transcripts[0]
                    if hasattr(result, 'text'):
                        return result.text
                    elif isinstance(result, str):
                        return result
                    else:
                        return str(result)
                return ""
        return self._transcribe_mlx(audio_data)
    
    def _transcribe_mlx(self, audio_data: np.ndarray) -> str:
        from parakeet_mlx.audio import get_logmel
        import mlx.core as mx
        
        mel = get_logmel(mx.array(audio_data, dtype=mx.float32), self.model.preprocessor_config)
        results = self.model.generate(mel)
        
        return getattr(results[0], "text", "") if results else ""
    
    def get_supported_languages(self) -> list:
        return ['en']


if __name__ == "__main__":
    transcriber = NeMoTranscriber()
    transcriber.initialize()
    
    text = transcriber.transcribe("docs/test.mp3")
    print(f"{_('Transcription result')}: {text}")
    print(f"{_('Backend used')}: {transcriber.backend} ({transcriber.device})")
