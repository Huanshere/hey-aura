# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hey Aura is a privacy-focused voice transcription application with real-time speech-to-text functionality. It operates entirely locally with no cloud dependencies for transcription, supporting both dictation and intelligent command processing modes.

## Development Commands

### Running the Application
```bash
# Standard launch
python app.py

# Platform-specific launchers
# Windows: Start_Windows.bat
# macOS: Start_MacOS.command
```

### Testing and Diagnostics
```bash
# System health check for VAD, ASR, and LLM components
python doctor.py
```

## Architecture Overview

### Core Components Architecture

1. **VoiceTranscriber** (`app.py`): Main orchestrator class that coordinates all components
   - Handles parallel initialization of VAD and ASR models
   - Manages audio recording lifecycle with thread safety
   - Coordinates between different operating modes

2. **Audio Processing Pipeline** (`core/audio_utils.py`):
   - `SileroVAD`: Voice Activity Detection for speech segment extraction
   - `AudioEnhancer`: Noise reduction and audio preprocessing
   - `AudioDeviceSelector`: Smart device selection for optimal recording

3. **Transcription Engine** (`core/transcription/`):
   - Factory pattern with abstract base class (`TranscriptionModel`)
   - Multiple backend support:
     - Whisper: faster-whisper (Windows) / MLX-whisper (macOS)
     - FunASR: Chinese-specific ASR
     - Parakeet: NeMo-based English transcription
   - Dynamic model loading based on configuration

4. **Input/Output Management**:
   - `ClipboardInjector` (`core/keyboard_utils.py`): Cross-platform text injection
   - `KeyboardEventHandler`: Global hotkey management
   - `FnKeyListener`: macOS-specific Fn key detection using Quartz

5. **Command Processing** (`core/command_mode.py`):
   - LLM integration via Ollama or OpenAI-compatible APIs
   - Dynamic repository scanning for context awareness
   - Active window detection for context-aware responses
   - XML-style tool calling system with extensible tool framework

6. **System Integration**:
   - `TrayAnimator`: Cross-platform system tray with animated status
   - `macos_tray.py`: Native macOS tray implementation using PyObjC
   - Platform-specific keyboard handling (Windows/Linux vs macOS)

7. **Meeting Recording System** (`core/meeting/`):
   - `MeetingRecorder`: Orchestrates meeting recording with system sound capture
   - `system_recorder_mac.py`/`system_recorder_win.py`: Platform-specific system audio recording
   - `audio_processor.py`: Audio processing and enhancement for meeting recordings
   - `transcription_processor.py`: Batch transcription of meeting audio
   - `meeting_exporter.py`: Export meeting transcripts and summaries

### Key Design Patterns

- **Factory Pattern**: Transcription model creation based on configuration
- **Observer Pattern**: Audio processing pipeline with VAD feedback
- **Strategy Pattern**: Platform-specific implementations for keyboard/tray
- **Command Pattern**: Tool system in command mode

### Configuration System

The application uses `config.yaml` for configuration:
- `asr`: Model and language settings for transcription
- `llm`: LLM configuration for command mode (Ollama or OpenAI-compatible)
- `web_llm`: Web-based LLM selection (claude, chatgpt, kimi, etc.)
- `repo_watch_directories`: Directories to scan for repository context
- `ui_language`: Interface language ('auto', 'en', 'zh') with automatic system detection
- `dictation_rewrite`: Configuration for LLM-based text rewriting in dictation mode

I18n
**Usage in Code**:
- Import translation function: `from core.i18n import _`
- Mark strings for translation: `_("Text to translate")`
- Automatic language detection based on system locale
- Runtime language switching support

### Threading and Concurrency

- Parallel model initialization (VAD + ASR) at startup
- Thread-safe audio recording with locks and proper cleanup
- Daemon threads for keyboard listeners and tray management
- Graceful shutdown handling with stream cleanup

### Platform-Specific Features

**macOS**:
- Native Fn key detection using Quartz event taps
- PyObjC-based system tray integration
- Application activation policy management

**Windows**:
- Global keyboard hooks using pynput
- Standard system tray implementation

### Audio Processing Pipeline Flow

1. Audio capture via sounddevice with low-latency configuration
2. Real-time VAD processing for speech detection
3. Audio enhancement (noise reduction, normalization)
4. Speech segment extraction with configurable padding
5. Transcription via selected ASR backend
6. Output routing (dictation vs command processing)

### Command Mode Tool System

Located in `core/tools/`, extensible tool framework supports:
- Web-based LLM interactions
- Repository context integration
- Active window awareness
- Custom tool development through inheritance

### Error Handling and Reliability

- Comprehensive audio device error handling with fallback
- Stream cleanup on device switching/disconnection
- Thread lifecycle management with timeouts
- Configuration validation with default fallbacks

### Model Backend Support

**ASR Model Types**:
- `whisper-large-v3`, `whisper-large-v3-turbo`: Standard Whisper models
- `funasr`: Chinese-optimized ASR backend
- `parakeet-mlx`: English ASR for Apple Silicon
- HuggingFace repository names (e.g., `Huan69/whisper-large-v3-turbo-cantonese-yue-english-ct2`)
- Local model folder paths

**Platform-Specific Optimizations**:
- Windows: `faster-whisper` backend with CUDA support
- macOS: `mlx-whisper` for Apple Silicon optimization
- Automatic backend selection based on platform detection

### Important File Locations

- `config.yaml`: Main configuration file
- `doctor.py`: System diagnostic tool for health checking
- `test_stage.py`: Individual component testing
- `docs/test.mp3`: Audio test file for ASR validation
- `locales/`: Translation files directory with `.pot`, `.po`, and `.mo` files
- `Start_Windows.bat` (Windows) / `Start_MacOS.command` (macOS): Platform launchers
- `babel.cfg`: Babel configuration for i18n extraction
- `recordings/`: Directory for saved recordings (meetings and push-to-talk)

代码规则:
尽量使用Kiss原则,减少注释的量,减少进行错误处理的代码,并且如果不是必要就不要使用class进行封装。