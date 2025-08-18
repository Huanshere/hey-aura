import os, time, soundfile as sf, librosa, tempfile
from typing import Optional
from core.transcription.base import TranscriptionModel
from core.i18n import _

class FunASRTranscriber(TranscriptionModel):
    def __init__(self, model: str = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch", **kw):
        super().__init__(model, **kw)
        self.model = None
        self.sr = 16000
    
    def initialize(self) -> None:
        if self.is_initialized: return
        
        print(f"→ {_('Initializing')}: {self.model_name}")
        t = time.time()
        
        os.environ["MODELSCOPE_CACHE"] = os.path.join(os.getcwd(), "models")
        os.makedirs(os.environ["MODELSCOPE_CACHE"], exist_ok=True)
        
        from funasr import AutoModel
        self.model = AutoModel(model=self.model_name, disable_pbar=True, disable_update=True)
        
        self.is_initialized = True
        print(f"→ {_('Ready')} {time.time()-t:.2f}s")
    
    def transcribe(self, path: str, language: Optional[str] = None, **kw) -> str:
        audio, _ = sf.read(path)
        r = self.model.generate(input=audio, is_final=True)
        return r[0]["text"] if r and len(r) > 0 and "text" in r[0] else ""
    
    def get_supported_languages(self) -> list: return ['zh']

if __name__ == "__main__":
    t = FunASRTranscriber()
    t.initialize()
    
    audio, sr = librosa.load("docs/test.mp3", sr=16000)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        sf.write(tmp.name, audio, sr, format='WAV')
        print(f"{_('Result')}: {t.transcribe(tmp.name)}")