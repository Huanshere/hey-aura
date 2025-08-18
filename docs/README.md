<div align="center">
  <img src="/docs/logo.png" alt="Hey Aura" height="250">
  
  ### Every Word Heard, Every Wish Served
  
  <p align="center">
    <b>No typing, just speaking. Local execution, complete privacy.</b>
  </p>
  
  <p align="center">
    <a href="README.md"> English</a> | <a href="../README.md"> 中文</a> | <a href="README_ja.md"> 日本語</a>
  </p>
</div>


## 🚀 Three Scenarios That Transform Your Workflow

| 📹 **No More Meeting Chaos** | 🎙️ **Writing as Natural as Speaking** | 🤖 **Control Your Computer with Voice** |
|---|---|---|
| Real-time transcription + AI summarization, focus on communication instead of note-taking | Voice input in any text field - emails, documents, code comments | "Open project" "Search materials" "Debug code" - just speak and it executes |
| ![meeting-gif](https://github.com/user-attachments/assets/3214a31c-a5ae-49dc-a6a3-70f19c0ca2f8) | ![dictation-gif](https://github.com/user-attachments/assets/9ec004e4-3864-4b74-8d2a-e143919c230a) | ![command-gif](https://github.com/user-attachments/assets/e2944fa4-19e4-4974-9b5a-4bb928e64d82) |

## ⚡ Core Advantages

**3x faster** voice input | **<0.5s** recognition latency | **100%** local privacy | **$0** usage cost

| Feature | Hey Aura | Cloud Services |
|---------|----------|---------------|
| **Response Speed** | ⚡️ < 0.5s | 🐢 > 1s |
| **Recognition Accuracy** | 🎯 Whisper/Parakeet ➕ hotword recognition | 😬 Generic models |
| **Extensibility** | 🌬️ Add whatever you want | 😬 Limited functionality |
| **Command System** | ✨ Control computer | 😬 Basic text operations |
| **Privacy Protection** | 🔒 Completely local | 🤔 Audio upload |
| **Usage Cost** | 🆓 $0 | 💰 Monthly $10+ |

<details>
<summary><b>Why is Hey Aura so fast and accurate?</b> 🚀</summary>

### 1. 🎤 Professional Audio Preprocessing
- **Silero VAD**: Real-time voice activity detection, precise voice segment extraction, avoiding invalid silence processing
- **Audio denoising**: Adaptive spectral subtraction denoising, eliminating background noise, improving recognition accuracy
- **Dynamic gain**: LUFS standard loudness normalization, ensuring consistent audio quality

### 2. ⚡ Hardware Acceleration Optimization
- **Windows CUDA**: Leverage NVIDIA GPU parallel computing, 10x inference speed improvement
- **macOS MLX**: Apple Silicon exclusive optimization, fully utilizing M-series chip performance
- **Model quantization**: INT8/FP16 precision optimization, 50% memory reduction, 2x speed improvement

### 3. 🎯 Optimized Model Selection
- **Scenario adaptation**: Configurable models suitable for your language scenarios, higher accuracy
- **English only**: Parakeet model, no hallucinations, best accuracy
- **Multilingual**: Whisper Turbo or community fine-tuned versions, targeted optimization

### 4. 🧠 Agentic Hotword Intelligent Correction
- **Phonetic matching**: Based on phonetic similarity rather than simple text replacement, understanding pronunciation intent
- **Context awareness**: Combined with semantic information for intelligent judgment, accurate recognition of proper nouns
- **Real-time correction**: Post-processing to correct ASR hallucinations, removing stutters and filler words

> The combination of these four technologies enables Hey Aura to achieve millisecond response and professional-grade accuracy

</details>

## Quick Start

### Prerequisites

<details>
<summary><b>🪟 Windows GPU Users</b> (CUDA installation required)</summary>

1. Download and install [CUDA Toolkit 12.6](https://developer.download.nvidia.com/compute/cuda/12.6.0/local_installers/cuda_12.6.0_560.76_windows.exe) and [CUDNN 9.3.0](https://developer.download.nvidia.com/compute/cudnn/9.3.0/local_installers/cudnn_9.3.0_windows.exe)
2. Add `C:\Program Files\NVIDIA\CUDNN\v9.3\bin\12.6` to system PATH and **restart computer**

</details>

<details>
<summary><b>🍎 macOS Users</b> (System permissions configuration required)</summary>

1. Open **System Preferences** → **Privacy & Security**
2. Add Terminal to **Accessibility** and **Input Monitoring**
3. Restart Terminal after authorization
4. (Optional) For recording system audio in meeting mode: **[View BlackHole configuration guide →](docs/macos-audio-setup.md)**

</details>

### ⚡ Method 1: One-Click Package - Start Using in 1 Minute

#### Choose Your Platform

[![Windows CUDA Download](https://img.shields.io/badge/Windows%20GPU-CUDA-green?style=for-the-badge&logo=nvidia&logoColor=white)](https://drive.google.com/file/d/1JKaHEOGVLa5XuCQD_jzg-hOCPDrLvvkB/view?usp=sharing)
![Windows CPU Download](https://img.shields.io/badge/Windows%20CPU-Coming%20Soon-blue?style=for-the-badge&logo=windows&logoColor=white)
[![macOS Download](https://img.shields.io/badge/macOS-M%20Series%20Chips-black?style=for-the-badge&logo=apple&logoColor=white)](https://drive.google.com/file/d/1I4lVpWf0Gsb6XL7AHaDYZZA9CEvIPHrd/view?usp=sharing)

#### Download → Run → Speak, it's that simple

> Windows: Double-click `Start_Windows.bat`

> macOS users need to run `chmod +x Start_MacOS.command` in terminal for first-time permission, then double-click to run

> First-time environment loading will be slow, please wait patiently for about a minute; the package includes the `whisper-large-v3-turbo` model. To use other models, modify `config.yaml` and restart the application - it will auto-download during startup.

### Method 2: Source Code Installation

```bash
# 1. Environment setup
conda create -n hey-aura python=3.10
conda activate hey-aura

# 2. Windows GPU users need to pre-install CUDA version PyTorch
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
# Windows CPU and Mac users can ignore this, torch will auto-install in next step

# 3. Clone and install
git clone https://github.com/Huanshere/hey-aura.git
cd hey-aura
pip install -e .

# 4. (Optional) Additional ASR backends (faster-whisper/mlx-whisper already installed by default)
# pip install funasr             # zh and en, low resource
# pip install parakeet-mlx       # MacOS parakeet en only

## nemo parakeet installation on windows is complex ⬇️
# set PYTHONUTF8=1
# set PYTHONIOENCODING=utf-8
# chcp 65001 >NUL
# python -m pip install "nemo_toolkit[asr]"
# pip install cuda-python==12.3

# 5. Start application
# Mac users need to add IDE to the above privacy and security permissions
python app.py
```

## 🎯 Getting Started with Hey Aura

### 👋 First time using? Try this:

1. Open Notepad or any text editor
2. Hold **Fn key (Mac)** or **Ctrl+Win (Windows)**
3. Say: "Hey Aura is amazing"
4. Release the key

See the text? 🎉 You've mastered it!

---

## Core Features

<details>
<summary><b>📹 Meeting Mode</b> - Automatic recording, real-time transcription, AI summarization, let you focus on the meeting itself.</summary>

### How to Use

**Right-click tray** → **Start Recording** → **End Recording** → **AI Summary**

- **Trigger**: System tray right-click menu
- **Function**: Simultaneously record microphone and system audio
- **Output**:
  - Audio file (MP3)
  - Real-time transcription text
  - AI intelligent summary
- **Save location**: `recordings/meetings/` directory

### macOS System Audio Recording Configuration

System audio recording requires configuring BlackHole virtual audio device

👉 [**View detailed configuration guide**](docs/macos-audio-setup.md)

### Output Files

After meeting recording completion, the following will be generated in `recordings/meetings/` directory:

1. **Audio file** - `meeting_YYYYMMDD_HHMMSS.mp3`
2. **Transcription text** - `meeting_YYYYMMDD_HHMMSS.txt`
3. **AI summary** - Included in transcription text file

### Use Cases

- Important meeting records
- Online course recording
- Interview recording
- Any scenario requiring audio recording and transcription

</details>

<details>
<summary><b>🎙️ Dictation Mode</b> - Convert speech to text in real-time, supports any input field. Uses Agentic hotword technology with proper noun recognition accuracy far exceeding traditional solutions.</summary>

### 🎯 Core Features

**Press to speak, release to convert**
- Hold shortcut key (Windows: Ctrl+Win / macOS: Fn) to start voice input
- Speak naturally, supports long sentences, pauses, thinking
- Release key to automatically complete transcription and paste at current cursor position

### 🚀 Smart Hotword Feature

Hey Aura innovatively adopts **Agentic hotword correction**, currently the most accurate speech recognition optimization technology.

**How it works:**
- 📝 **Intelligent phonetic matching**: Based on phonetic similarity rather than simple text replacement, understanding what you really want to say
- 🧠 **Semantic context analysis**: Combined with contextual semantic information for intelligent judgment and correction of recognition results
- 🎯 **Precise proper noun recognition**: Recognition accuracy for technical terms, brand names, personal names and other proper nouns far exceeds traditional solutions
- ✨ **Intelligent optimization processing**: Automatically removes stutters, filler words (uh, ah, um, etc.), making text more fluent and professional

**Usage example:**

When you say: "I want to use Claude Code to refactor this code, uh, that Anthropic tool"

- **Traditional ASR output**: I want to use cloud code to refactor this code uh that and topic tool
- **Hey Aura output**: I want to use Claude Code to refactor this code, that Anthropic tool

### 📋 Configure Hotwords

Configure your commonly used proper nouns in `config.yaml`:

```yaml
dictation_rewrite:
  enabled: true  # Enable smart rewriting
  hotwords:      # Add your proper nouns
    - Claude Code
    - Anthropic
    - ChatGPT
    - OpenAI
```

### Shortcuts

- **macOS**: `Fn` key
- **Windows**: `Ctrl+Win` key

### Use Cases

- Writing emails, code comments, chat messages
- Any scenario requiring text input
- Voice input during long document writing

</details>

<details>
<summary><b>🤖 Command Mode</b> - Control your computer with voice: open apps, search materials, execute automation. Supports custom command extensions.</summary>

Command mode directly controls desktop workflows through voice, maintaining focus and improving efficiency.

### Shortcuts

- **macOS**: `Fn+Control` key
- **Windows**: `Win+Alt` key

### Core Tools

#### 🔍 Ask Tool - Intelligent Q&A
**Function:** Send voice questions to AI services for queries

**Usage examples:**
- *"Help me ask about Python dictionary best practices"*
- System automatically opens Perplexity and submits query

**Configurable services:** ChatGPT, Claude, Perplexity, Kimi, Deepseek

#### 💻 Cursor with Claude Code - Code Assistant
**Function:** Identify local Git projects and integrate with Cursor + Claude Code

**Core capabilities:**

1. **Open project in Cursor**
   - Automatically scan Git projects in configured directories
   - Voice command: *"Help me open hey-aura"*

2. **Claude Code execution**
   - Voice command: *"Help me update Readme"*
   - Directly call Claude Code in Cursor for modifications

3. **Workflow integration**
   - Voice command: *"Help me open hey-aura and modify config file"*
   - Auto open with Cursor + Claude Code execution

**macOS configuration:**
1. Install Claude Code plugin in Cursor and right-click the CC icon in top right - configure key binding
2. Set Claude Code activation shortcut to `Option + C`

**Windows configuration:**
Install claude code in wsl, later will launch through `wsl claude` in cli

#### 📧 N8N Workflow Integration - Automated Task Execution
**Function:** Trigger N8N workflows through voice to implement complex automation tasks

**Existing demo: Email reading and reply**
   - Voice command: *"Any new emails today?"*
   - Automatically trigger N8N workflow to get recent emails
   - Aura helps you summarize and print in command line
   
**Configure in config.yaml:**
```yaml
n8n:
   username: "your_n8n_basic_credential"
   password: "your_n8n_basic_credential"
   get_emails_url: "your_n8n_webhook_url"
```

#### ✍️ Custom Tools

Command mode allows you to add any workflows

📖 **[View how to create custom tools →](docs/custom-tools.md)**

### Use Cases

- "Help me search for Python tutorials"
- "Open hey-aura project"  
- In Cursor: "Help me modify the Readme"
- Control computer, open apps, execute tasks

</details>

## ⚙️ Configure AI Services

Hey Aura needs an AI service to understand your commands.

### 🎯 Fastest Way (Recommended for beginners)

1. Visit [groq.com](https://groq.com) → Register → Get free API Key
2. Edit `config.yaml`:
   ```yaml
   llm:
     api_key: gsk_your_key  # ← Only need to change this
     # Keep other configs as default
   ```
3. Done! Start using!

> ✅ **Why choose Groq:** Free + Fast + No credit card required

### 🎤 ASR Speech Recognition Models

Hey Aura uses `whisper-large-v3-turbo` model by default, providing the best balance of speed and accuracy.

#### Model Performance Comparison

| Model | Scenario | Win GPU | Mac MLX | CPU | Accuracy | Memory | Language |
|------|------|---------|---------|-----|--------|------|------|
| **Parakeet** | English only | 130ms | 150ms | 🐢 | 🤩 | 3GB | English only |
| **Whisper V3 Turbo** | General recommended | 400ms | 1.2s | 🐢 | 😊 | 1.1GB | Multilingual |
| **Community fine-tuned Turbo** | Specific language | 400ms | 1.2s | 🐢 | 😊 | 1.1GB | Multilingual |
| **FunASR** | Resource limited | 150ms | ❌ | 1.5s | 😐 | 800MB | Chinese |
| **Whisper V3** | Minor languages | 600ms | 1.5s | 🐢 | 🚀 | 2.5GB | 100+ |

#### Selection Recommendations
- **English only**: `parakeet` provides best performance and accuracy
- **Single language mainly**: `whisper-large-v3-turbo` (default) or community fine-tuned versions
- **Limited device performance**: `funasr` lowest resource usage
- **Minor languages**: `whisper-large-v3` most comprehensive support

Configure in `config.yaml`:
```yaml
asr:
  # Options: whisper-large-v3, whisper-large-v3-turbo, parakeet, funasr, hf_model_url, local_model_dir
  model: whisper-large-v3-turbo  
  language: zh  # Language code (zh, en, ja, auto, etc.)
```

📖 **[View advanced configuration →](docs/advanced-config.md)** Including more LLM options, hotwords, multilingual, etc.


## 🗓️ Planned Features

- [ ] **Wake word activation** - Hands-free voice activation
- [ ] **Voice output** - TTS voice reply functionality
- [ ] **Computer Use** - Automated desktop operations
- [ ] **Memory module** - Personalized memory system
- [ ] **Meeting assistant** - Real-time problem detection and answering
- [ ] **Windows animated icon** - Jellyfish animation port
- [ ] **Claude Code SDK** - Code automation integration
- [ ] **Browser control** - StageHand integration

## ⚠️ Current Known Limitations

1. **Clipboard override**: Dictation mode output directly fills the clipboard, overwriting previous clipboard content. Recommend saving important clipboard content before use.

2. **ASR model hallucination**: Whisper and FunASR may hallucinate on extremely short audio, well-limited by VAD algorithm; Parakeet model completely avoids hallucinations, recommended for English-only scenarios.

3. **Windows dictation mode only outputs 'v'**: This is due to ASR recognition being too fast (lol). The dictation mode Ctrl key hasn't been released when recognition completes and pastes via Ctrl+V. Just manually perform Ctrl+V paste again.

4. **Mac external keyboard cannot trigger**: May be due to key mapping, will be fixed later.

## 💭 Why Build Hey Aura

> After watching "Her", I realized: We type 8 hours a day but forget that speaking is the most natural way of communication.
> 
> The AI era shouldn't still be trapped in text boxes.

Hey Aura isn't perfect, but it's trying hard to understand every word you say.

## Acknowledgments

https://github.com/tez3998/loopback-capture-sample Windows system audio recording