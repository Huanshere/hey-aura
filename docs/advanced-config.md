# 高级配置指南

## 完整配置示例

```yaml
# LLM 配置 - 用于命令模式和智能改写
llm:
  model: moonshotai/kimi-k2-instruct  # 模型名称
  base_url: https://api.groq.com/openai/v1  # API 端点或 "ollama"
  api_key: your_api_key_here  # API 密钥

# ASR 语音识别配置
asr:
  model: whisper-large-v3-turbo  # 支持多种模型
  language: zh  # 语言代码 (zh, en, ja, auto 等)

# 界面语言设置
ui_language: auto  # 选项: auto, en, zh, ja

# Web LLM 服务选择 - 用于 Ask 工具
web_llm: pplx  # 选项: chatgpt, claude, kimi, deepseek, pplx

# 项目监视目录 - 用于扫描 github 项目给 Cursor 打开
repo_watch_directories:
  - "~/Desktop"

# LLM 智能改写配置 - 听写模式文本优化
dictation_rewrite:
  enabled: true  # 启用听写模式的智能改写功能
  hotwords:      # 需要保持准确的专有名词和术语
    - ChatGPT
    - Anthropic
    - Claude Code
    - OpenAI

# N8N 工作流集成配置 - 用于邮件等自动化任务
n8n:
  username: your_n8n_basic_credential  # N8N 基础认证用户名
  password: your_n8n_basic_credential  # N8N 基础认证密码
  get_emails_url: your_n8n_webhook_url  # 获取邮件的 webhook URL
  respond_to_email_url: your_n8n_webhook_url  # 回复邮件的 webhook URL
```

## 配置项详细说明

### LLM 配置
- **model**: 支持 Ollama 本地模型或云端 API 模型
- **base_url**: 本地 Ollama 或兼容 OpenAI 的 API 端点
- **api_key**: 使用云端服务时需要

### ASR 配置
- **model**: 多种语音识别模型可选
  - `"whisper-large-v3"` - 最全面语言支持
  - `"whisper-large-v3-turbo"` - 速度优化版本
  - `"parakeet"` - 纯英文最佳性能
  - `"funasr"` - 资源占用最低
  - 自定义 HuggingFace 模型链接
  - 本地模型路径
- **language**: 目标语言代码

支持使用 HuggingFace 上或本地的 faster-whisper 或 mlx-whisper 格式模型。

### LLM 智能改写配置
- **enabled**: 是否启用听写模式的智能改写功能
- **hotwords**: 需要保持准确识别的专有名词列表

智能改写功能通过大模型根据音标相似性进行文本优化，比传统 ASR 热词方式更加智能化和准确，特别是对专有名词的识别准确率显著优于现有听写软件。

### 多语言支持
- **界面多语言**：支持多语言界面，当前支持 en, zh, ja, 可自动检测系统语言
- **语音识别**：ASR 部分（如 Whisper）支持世界上大部分语言
- **AI 理解**：主流大模型支持多种语言的理解和生成
- **扩展性**：采用 BABEL 进行多语言管理


## LLM 配置选项

### 选项 A: Groq（推荐新手）
免费额度充足，速度快，无需信用卡：
```yaml
llm:
  model: moonshotai/kimi-k2-instruct
  base_url: https://api.groq.com/openai/v1
  api_key: gsk_xxx  # 从 groq.com 获取
```

### 选项 B: OpenAI 兼容服务
支持任何 OpenAI 兼容的 API 服务：
```yaml
llm:
  model: gpt-4o  # 模型名称
  base_url: https://api.openai.com/v1  # API 端点
  api_key: sk_xxx  # 你的 API Key
```

### 选项 C: 本地 AI（高级用户）
如果你想完全离线运行：
```yaml
llm:
  base_url: ollama
  model: qwen3:8b
```
需要先安装 [Ollama](https://ollama.com) 并下载模型：
```bash
# 安装 Ollama 后运行
ollama run qwen3:8b
```

## 🎵 专业级音频预处理

### 处理管道

| 阶段 | 技术 | 场景 | 效果 |
|------|------|------|------|
| **设备选择** | AudioDeviceSelector | 多设备环境 | 😊 自动优选 |
| **语音检测** | Silero VAD | 长停顿/噪音 | 😊 精准提取 |
| **降噪处理** | noisereduce | 环境噪音 | 😐 背景消除 |
| **音量归一** | 智能增益 | 音量变化 | 😊 响度优化 |
| **动态压缩** | Tanh + 限幅 | 音量突变 | 😐 防止失真 |

### 设备选择策略

自动分析并按优先级选择音频设备：
1. 📱 外置专业麦克风
2. 💻 系统内置麦克风
3. 🎧 耳机麦克风（优先级较低）
4. 🔇 自动排除虚拟设备

提示：在连接到 AirPods 后仍会优先调用 MacBook 麦克风，避免切换对 AirPods 正在播放的音频造成影响

### 智能语音检测与音频增强

- **语音提取**：采用 Silero VAD 精准提取有效语音片段，适用于长时间停顿、嘈杂环境、断续语音、混合音频等复杂场景
- **降噪算法**：基于 noisereduce 库的谱减法降噪，自适应 FFT 窗口大小（128-2048），有效消除环境噪音、背景对话、电子噪音
- **音量控制**：LUFS 标准响度归一化（目标 -23.0 LUFS）+ Tanh 动态压缩，自动适应小声说话、距离变化、音量突变