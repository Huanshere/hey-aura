import os, platform, time, numpy as np, soundfile as sf
from typing import Optional
from core.transcription.base import TranscriptionModel
from core.i18n import _
import opencc
import re

# Mapping between model names and their MLX Hub paths
MLX_MAP = {"large-v3-turbo": "mlx-community/whisper-large-v3-turbo", "large-v3": "mlx-community/whisper-large-v3-mlx"}

class MLXTranscriptionInfo:
    def __init__(self, lang: str, prob: float = 1.0, dur: float = 0.0):
        self.language, self.language_probability, self.duration = lang, prob, dur

class WhisperTranscriber(TranscriptionModel):
    def __init__(self, model: str = "large-v3-turbo", **kw):
        super().__init__(model, **kw)
        self.model = None
        self.sys = platform.system()
        # Initialize OpenCC converter for traditional to simplified Chinese
        self.t2s_converter = opencc.OpenCC('t2s')
        
        if self.sys == "Windows":
            import torch
            cuda = torch.cuda.is_available()
            self.dev = kw.get('device', 'cuda' if cuda else 'cpu')
            self.comp = kw.get('compute_type', 'float16' if cuda else 'int8')
            self.root = kw.get('download_root', './models')
            print(f"  → {_('Device')}: {self.dev}, {_('Compute')}: {self.comp}")
            if os.path.exists(model): self.model_name = model
        else:
            self.path = model if os.path.exists(model) else kw.get('model_path', MLX_MAP.get(model, model))
            print(f"  → {_('Local') if os.path.exists(model) else _('HF')}: {self.path}")
            self._warm = False
            self.mlx = None
    
    def initialize(self) -> None:
        if self.is_initialized: return
        
        print(f"  → {_('Initializing')}: {self.model_name} on {self.sys}")
        t = time.time()
        
        if self.sys == "Windows":
            from faster_whisper import WhisperModel
            self.model = WhisperModel(self.model_name, device=self.dev, compute_type=self.comp, download_root=self.root)
        else:
            # Set up HuggingFace cache directory
            os.environ["HF_HUB_CACHE"] = os.path.join(os.getcwd(), "models")
            os.makedirs(os.environ["HF_HUB_CACHE"], exist_ok=True)
            import mlx_whisper
            self.mlx = mlx_whisper
            
            # Warm up the model with a test audio
            print(f"  → {_('Warming up')}: {self.path}")
            tmp = "tmp_warm.wav"
            sr, dur = 16000, 0.1
            sf.write(tmp, np.sin(2*np.pi*440*np.linspace(0, dur, int(sr*dur), False))*0.1, sr)
            
            try: self.mlx.transcribe(tmp, path_or_hf_repo=self.path, word_timestamps=False)
            finally: os.path.exists(tmp) and os.remove(tmp)
            
            self._warm = True
        
        self.is_initialized = True
        print(f"  → {_('Whisper Ready in')} {time.time()-t:.2f}s")
    
    def detect_hallucination(self, text: str) -> str:
        """Detect and remove hallucinations (repeated characters > 15 times)"""
        # Pattern to match any character repeated 15+ times
        pattern = r'(.)\1{14,}'
        # Replace repeated characters with single instance
        cleaned = re.sub(pattern, r'\1', text)
        return cleaned
    
    def transcribe(self, path: str, language: Optional[str] = None, **kw) -> str:
        # Support both 'language' and 'lang' parameter names for compatibility
        lang = language or kw.get('lang')
        
        # Convert 'auto' to None for automatic language detection
        if lang == 'auto':
            lang = None
        
        if self.sys == "Windows":
            seg, _ = self.model.transcribe(path, beam_size=kw.get('beam_size', 5), language=lang)
            text = "".join(s.text for s in seg)
            # Convert to simplified Chinese for any Chinese variant
            if lang and (lang == 'zh' or lang.startswith('zh')):
                text = self.t2s_converter.convert(text)
            # Remove hallucinations before returning
            return self.detect_hallucination(text)
        
        result = self.mlx.transcribe(path, path_or_hf_repo=self.path, word_timestamps=False, language=lang)["text"]
        # Convert to simplified Chinese for any Chinese variant
        if lang and (lang == 'zh' or lang.startswith('zh')):
            result = self.t2s_converter.convert(result)
        # Remove hallucinations before returning
        return self.detect_hallucination(result)
    
    def get_supported_languages(self) -> list: return ['*']

if __name__ == "__main__":
    t = WhisperTranscriber()
    t.initialize()
    print(f"→ {_('Test result')}: {t.transcribe('docs/test.mp3')}")