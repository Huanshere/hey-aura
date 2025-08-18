from abc import ABC, abstractmethod
from typing import Optional


class TranscriptionModel(ABC):
    """Base interface for transcription models"""
    
    def __init__(self, model_name: str, **kwargs):
        self.model_name = model_name
        self.is_initialized = False
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the model"""
        pass
    
    @abstractmethod
    def transcribe(self, audio_path: str, language: Optional[str] = None, **kwargs) -> str:
        """
        Transcribe audio file
        
        Args:
            audio_path: Path to audio file
            language: Language code (optional)
            **kwargs: Additional arguments
            
        Returns:
            str: Transcription text
        """
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> list:
        """Get list of supported languages"""
        pass