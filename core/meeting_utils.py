import datetime

from core.i18n import _
from core.meeting.audio_processor import MeetingAudioProcessor
from core.meeting.transcription_processor import MeetingTranscriptionProcessor
from core.meeting.meeting_exporter import save_meeting_results


class MeetingRecorder:
    """Utility class for continuous meeting audio recording and transcription."""
    
    def __init__(self, voice_transcriber):
        """Initialize MeetingRecorder."""
        self.transcriber_ref = voice_transcriber
        self.audio_processor = MeetingAudioProcessor(voice_transcriber)
        self.transcription_processor = MeetingTranscriptionProcessor(voice_transcriber, self.audio_processor)
        self.meeting_mode = False
        self.meeting_stopping = False
        self.meeting_thread = None
        self.meeting_start_time = None
    
    def toggle_meeting_recording(self):
        """Toggle meeting recording mode."""
        if not self.meeting_mode:
            self.start_meeting_recording()
        else:
            self.stop_meeting_recording()
    
    def start_meeting_recording(self):
        """Start meeting recording."""
        if self.meeting_mode:
            return
        
        print(_("→ 💡 Starting meeting recording..."))
        self.meeting_mode = True
        self.meeting_start_time = datetime.datetime.now()
        self.transcription_processor.clear_transcripts()
        self.transcriber_ref.keyboard_handler.disable_all_listeners()
        if hasattr(self.transcriber_ref, 'fn_listener') and self.transcriber_ref.fn_listener:
            self.transcriber_ref.fn_listener.disable_all_listeners()
        try:
            self.transcriber_ref.tray.set_status("recording")
            self.transcriber_ref.tray.update_meeting_menu(True)
        except Exception:
            pass
        self.meeting_thread = self.audio_processor.start_audio_recording()
        self.transcription_processor.start_transcription_processing()
    
    def stop_meeting_recording(self):
        """Stop meeting recording and save results."""
        if not self.meeting_mode:
            return
        
        print(_("⏹️ Stopping meeting recording..."))
        self.meeting_stopping = True
        self.audio_processor.stop_audio_recording()
        self.meeting_mode = False
        if self.meeting_thread and self.meeting_thread.is_alive():
            print(_("→ Waiting for microphone recording thread..."))
            self.meeting_thread.join(timeout=8)  # Increased timeout for safer cleanup
            if self.meeting_thread.is_alive():
                print(_("→ Warning: Recording thread did not terminate cleanly"))
                # Force cleanup to prevent resource leaks
                import gc
                gc.collect()
        self.transcription_processor.wait_for_transcription_completion()
        try:
            transcripts = self.transcription_processor.get_transcripts()
            final_audio = self.audio_processor.get_recorded_audio()
            save_meeting_results(self.transcriber_ref, self.meeting_start_time, transcripts, final_audio)
            print(_("✅ Meeting recording saved"))
        except Exception as e:
            print(_("❌ Error saving meeting results: {}").format(e))
        self.meeting_stopping = False
        self.audio_processor.cleanup_resources()
        try:
            self.transcriber_ref.keyboard_handler.enable_all_listeners()
            if hasattr(self.transcriber_ref, 'fn_listener') and self.transcriber_ref.fn_listener:
                self.transcriber_ref.fn_listener.enable_all_listeners()
        except Exception as e:
            print(_("→ Error re-enabling keyboard listeners: {}").format(e))
        try:
            self.transcriber_ref.tray.set_status("idle")
            self.transcriber_ref.tray.update_meeting_menu(False)
        except Exception: 
            pass
    
    def cleanup_resources(self):
        """Cleanup all resources."""
        # Ensure we're not in recording mode
        if self.meeting_mode:
            self.stop_meeting_recording()
        
        # Clean up audio processor
        self.audio_processor.cleanup_resources()
        
        # Clean up transcription processor
        if hasattr(self, 'transcription_processor'):
            self.transcription_processor.cleanup_resources()
        
        # Force cleanup
        import gc
        gc.collect()