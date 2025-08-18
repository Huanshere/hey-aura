
<div align="center">
  <img src="/docs/logo.png" alt="Hey Aura" height="250">
  
  ### 声音即指令，文字即思想
  
  <p align="center">
    <b>不打字，只动嘴。本地运行，完全隐私。</b>
  </p>
  
  <p align="center">
    <a href="docs/README.md"> English</a> | <a href="README.md"> 中文</a> | <a href="docs/README_ja.md"> 日本語</a>
  </p>
</div>


## 🚀 三个场景，改变你的工作方式

| 📹 **会议不再手忙脚乱** | 🎙️ **写作像说话一样自然** | 🤖 **用声音控制电脑** |
|---|---|---|
| 实时转录 + AI 总结，让你专注于交流而非记录 | 任何输入框都能语音输入，邮件、文档、代码注释 | "打开项目" "搜索资料" "调试代码" - 说出来就能执行 |
| ![meeting-gif](https://github.com/user-attachments/assets/3c66d947-9bab-49ae-9f01-e017949796be) | ![dictation-gif](https://github.com/user-attachments/assets/607412bf-627d-4a7d-b676-fb02ed18dca0) | ![command-gif](https://github.com/user-attachments/assets/c620f2f6-663c-4d6c-b421-7f8b53cf9136) |

## ⚡ 核心优势

**3倍速** 语音输入效率 | **<0.5秒** 识别延迟 | **100%** 本地隐私 | **$0** 使用成本

| 特性 | Hey Aura | 云端服务 |
|---------|----------|---------------|
| **响应速度** | ⚡️ < 0.5s | 🐢 > 1s |
| **识别精度** | 🎯 Whisper/Parakeet ➕ 热词识别 | 😬 通用模型 |
| **可扩展性** | 🌬️ 想加什么加什么 | 😬 功能有限 |
| **命令系统** | ✨ 操控电脑 | 😬 基础文本操作 |
| **隐私保护** | 🔒 完全本地 | 🤔 音频上传 |
| **使用成本** | 🆓 $0 | 💰 月费 $10+ |

<details>
<summary><b>看看为什么 Hey Aura 又快又准？</b> 🚀</summary>

### 1. 🎤 专业音频预处理
- **Silero VAD**：实时语音活动检测，精准提取语音片段，避免无效静音处理
- **音频降噪**：自适应谱减法降噪，消除背景噪音，提升识别准确率
- **动态增益**：LUFS 标准响度归一化，确保音频质量一致性

### 2. ⚡ 硬件加速优化
- **Windows CUDA**：利用 NVIDIA GPU 并行计算，推理速度提升 10x
- **macOS MLX**：Apple Silicon 专属优化，充分发挥 M 系列芯片性能
- **模型量化**：INT8/FP16 精度优化，内存占用减少 50%，速度提升 2x

### 3. 🎯 模型优化选择
- **场景适配**：可配置适合你语言场景的模型，准确度更高
- **纯英文**：Parakeet 模型，无幻觉，最佳准确率
- **多语言**：Whisper Turbo 或社区微调版，针对性优化

### 4. 🧠 Agentic 热词智能纠正
- **音标匹配**：基于音标相似度而非简单文本替换，理解发音意图
- **上下文感知**：结合语义信息智能判断，准确识别专有名词
- **实时修正**：后处理纠正 ASR 幻觉，去除口吃和语气词

> 这四项技术的结合，让 Hey Aura 实现了毫秒级响应和专业级准确率

</details>

## 快速开始

### 前置准备

<details>
<summary><b>🪟 Windows GPU 用户</b>（需要安装 CUDA）</summary>

1. 点击下载并安装 [CUDA Toolkit 12.6](https://developer.download.nvidia.com/compute/cuda/12.6.0/local_installers/cuda_12.6.0_560.76_windows.exe) 和 [CUDNN 9.3.0](https://developer.download.nvidia.com/compute/cudnn/9.3.0/local_installers/cudnn_9.3.0_windows.exe)
2. 添加 `C:\Program Files\NVIDIA\CUDNN\v9.3\bin\12.6` 到系统 PATH 并**重启计算机**

</details>

<details>
<summary><b>🍎 macOS 用户</b>（需要配置系统权限）</summary>

1. 打开 **系统偏好设置** → **隐私与安全性**
2. 在 **辅助功能** 和 **输入监控** 中添加终端
3. 授权后重启终端
4. （可选）如需在会议模式中录制系统音频：**[查看配置Blackhole指南 →](docs/macos-audio-setup.md)**

</details>

### ⚡ 方式一：一键整合包 1 分钟开始使用

#### 选择你的平台

[![Windows CUDA下载](https://img.shields.io/badge/Windows%20GPU-CUDA-green?style=for-the-badge&logo=nvidia&logoColor=white)](https://drive.google.com/file/d/1JKaHEOGVLa5XuCQD_jzg-hOCPDrLvvkB/view?usp=sharing)
![Windows CPU下载](https://img.shields.io/badge/Windows%20CPU-稍后推出-blue?style=for-the-badge&logo=windows&logoColor=white)
[![macOS下载](https://img.shields.io/badge/macOS-M系列芯片-black?style=for-the-badge&logo=apple&logoColor=white)](https://drive.google.com/file/d/1I4lVpWf0Gsb6XL7AHaDYZZA9CEvIPHrd/view?usp=sharing)

#### 下载 → 运行 → 说话，就这么简单

> Windows 双击运行 `Start_Windows.bat`

> macOS 用户首次运行需在终端执行 `chmod +x Start_MacOS.command` 赋予权限 然后双击运行

> 首次运行环境加载会较慢，请耐心等待一分钟；整合包打包了 `whisper-large-v3-turbo` 模型，如需使用其他模型请修改 `config.yaml` 并重新启动应用，会在启动时自动下载。

### 方式二：源码安装

```bash
# 1. 环境准备
conda create -n hey-aura python=3.10
conda activate hey-aura

# 2. Windows GPU 用户需要提前安装 Cuda 版本 PyTorch
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
# Windows CPU 和 Mac 用户可以忽略，会在下一步自动安装 torch

# 3. 克隆并安装
git clone https://github.com/Huanshere/hey-aura.git
cd hey-aura
pip install -e .

# 4.（可选）额外 ASR 后端 (已默认安装 faster-whisper/mlx-whisper)
# pip install funasr             # zh and en, low resource
# pip install parakeet-mlx       # MacOS parakeet en only

## nemo parakeet on windows 安装较为麻烦 ⬇️
# set PYTHONUTF8=1
# set PYTHONIOENCODING=utf-8
# chcp 65001 >NUL
# python -m pip install "nemo_toolkit[asr]"
# pip install cuda-python==12.3

# 5. 启动应用
# Mac 用户需要将 IDE 添加进上述隐私与安全性权限中
python app.py
```

## 🎯 开始使用 Hey Aura

### 👋 第一次使用？试试这个：

1. 打开记事本或任何文本编辑器
2. 按住 **Fn 键（Mac）** 或 **Ctrl+Win（Windows）**
3. 说："Hey Aura 真是太棒了"
4. 松开按键

看到文字了吗？🎉 你已经学会了！

---

## 核心功能

<details>
<summary><b>📹 会议模式</b> - 自动录音、实时转录、AI 总结，让你专注会议本身。</summary>

### 如何使用

**右键托盘** → **开始录音** → **结束录音** → **AI 总结**

- **触发**：系统托盘右键菜单
- **功能**：同时录制麦克风和系统音频
- **输出**：
  - 音频文件（MP3）
  - 实时转录文本
  - AI 智能总结
- **保存位置**：`recordings/meetings/` 目录

### macOS 系统音频录制配置

系统音频录制需要配置 BlackHole 虚拟音频设备

👉 [**查看详细配置指南**](docs/macos-audio-setup.md)

### 输出文件

会议录制完成后，会在 `recordings/meetings/` 目录生成：

1. **音频文件** - `meeting_YYYYMMDD_HHMMSS.mp3`
2. **转录文本** - `meeting_YYYYMMDD_HHMMSS.txt`
3. **AI 总结** - 包含在转录文本文件中

### 使用场景

- 重要会议记录
- 在线课程录制
- 访谈录音
- 任何需要音频记录和转录的场景

</details>

<details>
<summary><b>🎙️ 听写模式</b> - 将语音实时转换为文字，支持任何输入框。采用 Agentic 热词技术，专有名词识别准确率远超传统方案。</summary>

### 🎯 核心特点

**即按即说，释放即转**
- 按住快捷键（Windows: Ctrl+Win / macOS: Fn）开始语音输入
- 自然说话，支持长句、停顿、思考
- 释放按键后自动完成转录并粘贴到当前光标位置

### 🚀 智能热词功能

Hey Aura 创新性地采用了 **Agentic 热词纠正**，这是目前最准确的语音识别优化技术。

**工作原理：**
- 📝 **音标智能匹配**：基于音标相似度而非简单的文本替换，理解您真正想说的内容
- 🧠 **语义上下文分析**：结合上下文语义信息，智能判断并纠正识别结果
- 🎯 **专有名词精准识别**：对技术术语、品牌名称、人名等专有名词的识别准确率远超传统方案
- ✨ **智能优化处理**：自动去除口吃、语气词（呃、啊、嗯等），让文本更加流畅专业

**使用示例：**

当你说："我想用 Claude Code 重构这段代码，呃，就是那个 Anthropic 的工具"

- **传统 ASR 输出**：我想用 cloud code 重构这段代码呃就是那个 and topic 的工具
- **Hey Aura 输出**：我想用 Claude Code 重构这段代码，就是那个 Anthropic 的工具

### 📋 配置热词

在 `config.yaml` 中配置您常用的专有名词：

```yaml
dictation_rewrite:
  enabled: true  # 启用智能改写
  hotwords:      # 添加您的专有名词
    - Claude Code
    - Anthropic
    - ChatGPT
    - OpenAI
```

### 快捷键

- **macOS**: `Fn` 键
- **Windows**: `Ctrl+Win` 键

### 使用场景

- 写邮件、代码注释、聊天消息
- 任何需要文字输入的场景
- 长文档编写时的语音输入

</details>

<details>
<summary><b>🤖 命令模式</b> - 用语音控制电脑：打开应用、搜索资料、执行自动化。支持自定义命令扩展。</summary>

命令模式通过语音直接控制桌面工作流，保持专注，提高效率。

### 快捷键

- **macOS**: `Fn+Control` 键
- **Windows**: `Win+Alt` 键

### 核心工具

#### 🔍 Ask 工具 - 智能问答
**功能：** 将语音问题发送至 AI 服务进行查询

**使用示例：**
- *"帮我问一下 Python 字典的最佳实践"*
- 系统自动打开 Perplexity 并提交查询

**可配置服务：** ChatGPT、Claude、Perplexity、Kimi 、Deepseek

#### 💻 Cursor with Claude Code - 代码助手
**功能：** 识别本地 Git 项目并与 Cursor + Claude Code 集成

**核心能力：**

1. **在 Cursor 中打开项目**
   - 自动扫描配置目录中的 Git 项目
   - 语音命令：*"帮我打开 hey-aura"*

2. **Claude Code 执行**
   - 语音命令：*"帮我更新 Readme"*
   - 在 Cursor 中直接调用 Claude Code 执行修改

3. **工作流集成**
   - 语音命令：*"帮我打开 hey-aura 并修改配置文件"*
   - 自动用 Cursor 打开 + Claude Code 执行

**macOS 配置：**
1. 在 Cursor 中安装 Claude Code 插件并右键右上角 CC 图标 - 配置键绑定
2. 将 Claude Code 激活快捷键设置为 `Option + C`

**Windows 配置：**
在 wsl 中安装 claude code，后续将通过 cli 中的 `wsl claude` 启动

#### 📧 N8N 工作流集成 - 自动化任务执行
**功能：** 通过语音触发 N8N 工作流，实现复杂的自动化任务

**现有 demo：Email 读取和回复**
   - 语音命令：*"今天有什么新的邮件吗"*
   - 自动触发 N8N 工作流，获取最近的邮件
   - Aura 帮你总结 打印在命令行
   
**在 config.yaml 中配置：**
```yaml
n8n:
   username: "your_n8n_basic_credential"
   password: "your_n8n_basic_credential"
   get_emails_url: "your_n8n_webhook_url"
```

#### ✍️ 自定义工具

命令模式可以任意添加你的工作流

📖 **[查看如何创建自定义工具 →](docs/custom-tools.md)**

### 使用场景

- "帮我搜索 Python 教程"
- "打开 hey-aura 项目"  
- 在 Cursor 中 "帮我修改一下 Readme"
- 控制电脑、打开应用、执行任务

</details>

## ⚙️ 配置 AI 服务

Hey Aura 需要一个 AI 服务来理解你的命令。

### 🎯 最快速的方式（推荐新手）

1. 访问 [groq.com](https://groq.com) → 注册 → 获取免费 API Key
2. 编辑 `config.yaml`：
   ```yaml
   llm:
     api_key: gsk_你的密钥  # ← 只需要改这里
     # 其他配置保持默认即可
   ```
3. 完成！开始使用吧

> ✅ **选择 Groq 的理由：** 免费 + 速度快 + 无需信用卡

### 🎤 ASR 语音识别模型

Hey Aura 默认使用 `whisper-large-v3-turbo` 模型，提供速度和准确性的最佳平衡。

#### 模型性能对比

| 模型 | 场景 | Win GPU | Mac MLX | CPU | 准确度 | 内存 | 语言 |
|------|------|---------|---------|-----|--------|------|------|
| **Parakeet** | 纯英文 | 130ms | 150ms | 🐢 | 🤩 | 3GB | 仅英文 |
| **Whisper V3 Turbo** | 通用推荐 | 400ms | 1.2s | 🐢 | 😊 | 1.1GB | 多语言 |
| **社区微调 Turbo** | 特定语言 | 400ms | 1.2s | 🐢 | 😊 | 1.1GB | 多语言 |
| **FunASR** | 资源受限 | 150ms | ❌ | 1.5s | 😐 | 800MB | 中文 |
| **Whisper V3** | 小语种 | 600ms | 1.5s | 🐢 | 🚀 | 2.5GB | 100+ |

#### 选择建议
- **纯英文**：`parakeet` 提供最佳性能和准确性
- **单一语言为主**：`whisper-large-v3-turbo`（默认）或社区微调版
- **设备性能有限**： `funasr` 资源占用最低
- **小语种**：`whisper-large-v3` 支持最全面

在 `config.yaml` 中配置：
```yaml
asr:
  # 可选: whisper-large-v3, whisper-large-v3-turbo, parakeet, funasr, hf_model_url, local_model_dir
  model: whisper-large-v3-turbo  
  language: zh  # 语言代码 (zh, en, ja, auto 等)
```

📖 **[查看高级配置 →](docs/advanced-config.md)** 包含更多 LLM 选项、热词、多语言等


## 🗓️ 计划功能

- [ ] **唤醒词激活** - 免按键语音唤醒
- [ ] **语音输出** - TTS 语音回复功能
- [ ] **Computer Use** - 自动化桌面操作
- [ ] **Memory 模块** - 个性化记忆系统
- [ ] **会议助手** - 实时难题检测与解答
- [ ] **Windows 动画图标** - 水母动画移植
- [ ] **Claude Code SDK** - 代码自动化集成
- [ ] **浏览器控制** - StageHand 集成

## ⚠️ 当前已知不足

1. **粘贴板覆盖**：听写模式的输出会直接填充到粘贴板，覆盖之前粘贴板中的内容
，建议在使用前保存重要的粘贴板内容

2. **ASR 模型幻觉问题**：Whisper 和 FunASR 在极短音频上可能会产生幻觉，已通过 VAD 算法进行了较好的限制；Parakeet 模型完全不会产生幻觉，推荐纯英文场景使用

3. **Windows 上听写模式只输出了 v**：这是由于 ASR 识别过快导致的（笑），听写模式按键 Ctrl 还未来得及释放，就已经识别完成并通过 Ctrl+V 进行粘贴导致的。这时候手动再进行一次 Ctrl+V 粘贴即可。

4. **Mac 外接键盘无法触发**：可能是键位原因，会在之后修复。

## 💭 为什么做 Hey Aura

> 看完《Her》，我意识到：我们每天打字 8 小时，却忘了说话才是最自然的交流方式。
> 
> AI 时代不该还困在文本框里。

Hey Aura 不完美，但它在努力理解你说的每一句话。

## 致谢

https://github.com/tez3998/loopback-capture-sample windows 系统音频录制