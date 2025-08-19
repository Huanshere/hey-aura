from .base import TranscriptionModel

def create_transcriber(model_type: str) -> TranscriptionModel:
    """Create transcriber instance based on model type"""
    import os
    
    # Check if it's a local whisper model path
    if os.path.exists(model_type) and "whisper" in model_type:
        from .whisper_ import WhisperTranscriber
        return WhisperTranscriber(model_type)
    # Check if it's a HuggingFace repo path (contains whisper but not local)
    elif "whisper" in model_type.lower() and "/" in model_type and not os.path.exists(model_type):
        from .whisper_ import WhisperTranscriber
        return WhisperTranscriber(model_type)
    elif model_type.startswith("whisper-"):
        # Handle whisper model variants, e.g. whisper-large-v3-turbo -> large-v3-turbo
        from .whisper_ import WhisperTranscriber
        whisper_model = model_type.replace("whisper-", "")
        return WhisperTranscriber(whisper_model)
    elif model_type == "parakeet":
        from .parakeet import NeMoTranscriber
        return NeMoTranscriber()
    elif model_type == "funasr":
        from .funasr_ import FunASRTranscriber
        return FunASRTranscriber("iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch")
    else:
        raise ValueError(f"Unsupported model type: {model_type}. Options: whisper-large-v3-turbo, whisper-large-v3, parakeet, funasr, HuggingFace whisper repo path, or local whisper model path")


__all__ = ['TranscriptionModel', 'create_transcriber']