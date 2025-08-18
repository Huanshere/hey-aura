import os
import datetime
import numpy as np
import scipy.io.wavfile as wav

from core.i18n import _

class MeetingExporter:
    """Meeting exporter for saving meeting recordings and results."""

    def __init__(self, transcriber_ref):
        # Initialize MeetingExporter
        self.transcriber_ref = transcriber_ref

    def summarize_meeting(self, transcripts):
        """Summarize meeting transcripts."""
        from core.llm_context import cfg, ollama, OpenAI
        with open("core/prompts/summarize_meeting.md", encoding="utf-8") as f:
            prompt_template = f.read()
        prompt = prompt_template.replace('{recording}', transcripts)
        m = [{"role": "user", "content": prompt}]
        
        if "ollama" in cfg['base_url'].lower():
            result = ollama.chat(model=cfg['model'], messages=m, think=True)['message']['content']
        else:
            result = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url']).chat.completions.create(
                model=cfg['model'], messages=m, timeout=30).choices[0].message.content
        return result

    def save_meeting_results(self, meeting_start_time, transcripts, final_audio):
        # Save meeting results (transcripts and audio)
        if not meeting_start_time:
            return

        output_dir = "./recordings/meetings"
        os.makedirs(output_dir, exist_ok=True)

        timestamp = meeting_start_time.strftime("%Y%m%d_%H%M%S")

        # Save transcripts if available
        if transcripts:
            self._save_transcripts(output_dir, timestamp, meeting_start_time, transcripts)

        # Save audio if available
        if final_audio is not None and len(final_audio) > 0:
            self._save_audio(output_dir, timestamp, final_audio)

    def _save_transcripts(self, output_dir, timestamp, meeting_start_time, transcripts):
        # Save transcript text file
        sorted_transcripts = sorted(transcripts, key=lambda x: x['timestamp'])

        transcript_file = f"{output_dir}/meeting_{timestamp}.txt"
        
        # Prepare transcript content
        transcript_content = []
        transcript_content.append(f"Meeting Recording - {meeting_start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        transcript_content.append("=" * 60 + "\n\n")

        # Collect transcripts with source tags
        transcript_text_only = []
        for entry in sorted_transcripts:
            source_tag = "🎤" if entry.get('source') == 'microphone' else "🔊" if entry.get('source') == 'system' else "❓"
            transcript_content.append(f"[{entry['timestamp'].strftime('%H:%M:%S')}] {source_tag} {entry['text']}\n\n")
            transcript_text_only.append(f"[{entry['timestamp'].strftime('%H:%M:%S')}] {entry['text']}")

        transcript_content.append("\n" + "=" * 60 + "\n")
        transcript_content.append(f"End of meeting - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        transcript_content.append(f"\nLegend: 🎤=Microphone, 🔊=System Audio\n")
        
        # First save the transcripts without summary to ensure they're preserved
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write("".join(transcript_content))
        
        print(_("📄 Transcripts saved to: {}").format(transcript_file))
        print(_("  → {} microphone transcripts").format(
            sum(1 for t in sorted_transcripts if t.get('source') == 'microphone')
        ))
        print(_("  → {} system audio transcripts").format(
            sum(1 for t in sorted_transcripts if t.get('source') == 'system')
        ))
        
        # Now try to generate and add summary
        try:
            print(_("📝 Generating meeting summary..."))
            summary_text = self.summarize_meeting("\n".join(transcript_text_only))
            
            # Read the existing content
            with open(transcript_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # Write the file again with summary at the beginning
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(f"<summary>\n\n{summary_text}\n\n</summary>\n\n")
                f.write("=" * 60 + "\n")
                f.write(existing_content)
                
            print(_("✅ Meeting summary generated and added"))
        except Exception as e:
            print(_(f"⚠️ Failed to generate summary: {e}"))
            # Transcripts are already saved, so no action needed

    def _save_audio(self, output_dir, timestamp, final_audio):
        # Save audio file (WAV and MP3)
        wav_file = f"{output_dir}/meeting_{timestamp}_temp.wav"
        mp3_file = f"{output_dir}/meeting_{timestamp}.mp3"

        # Write WAV file
        wav.write(
            wav_file,
            self.transcriber_ref.sr,
            (np.clip(final_audio, -1.0, 1.0) * 32767).astype(np.int16)
        )

        # Convert to MP3
        self.convert_to_mp3(wav_file, mp3_file)

        # Remove temporary WAV file
        os.unlink(wav_file)

        print(_("🎵 Audio saved to: {}").format(mp3_file))

    def convert_to_mp3(self, wav_path, mp3_path):
        # Convert WAV to MP3 with quality level 2
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(str(wav_path))
        audio.export(str(mp3_path), format="mp3", parameters=["-q:a", "2"])