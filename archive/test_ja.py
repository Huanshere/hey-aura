import os
import time
import torch
import torchaudio
import tempfile

# Windows only

# 设置 HuggingFace 缓存目录
os.environ["HF_HUB_CACHE"] = os.path.join(os.getcwd(), "models")

def to_16k_mono(in_path: str) -> tuple:
    """将音频转换为16kHz单声道"""
    wav, sr = torchaudio.load(in_path)
    if wav.dim() == 2 and wav.size(0) > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if sr != 16000:
        wav = torchaudio.functional.resample(wav, sr, 16000)
    return wav, 16000

def save_wav(wav: torch.Tensor, sr: int, out_path: str):
    """保存音频文件"""
    torchaudio.save(out_path, wav, sr)

def transcribe_whisper(audio_path: str, model_name: str = "large-v3", repeat: int = 2):
    """使用 Whisper 进行转写，支持 large-v3 和 large-v3-turbo"""
    print(f"\n===== Whisper {model_name} 转写 =====")
    
    from faster_whisper import WhisperModel
    model = WhisperModel(
        model_name,
        device="cuda" if torch.cuda.is_available() else "cpu",
        compute_type="int8_float16" if torch.cuda.is_available() else "int8",
        download_root="./models"
    )
    
    results = []
    for i in range(repeat):
        print(f"\n第{i+1}次转录开始（Whisper {model_name}）...")
        start = time.time()
        segments, _ = model.transcribe(audio_path, beam_size=5, language="ja")
        text = "".join(segment.text for segment in segments)
        end = time.time()
        print(f"第{i+1}次转录用时：{end-start:.2f} 秒")
        print("转录结果：", text)
        results.append(text)
    
    return results[-1]  # 返回最后一次结果

def transcribe_parakeet(audio_path: str, repeat: int = 2):
    """使用 Parakeet 进行转写"""
    print("\n===== Parakeet TDT-CTC 转写 =====")
    
    import nemo.collections.asr as nemo_asr
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    print("正在加载 Parakeet 模型...")
    model = nemo_asr.models.ASRModel.from_pretrained(
        model_name="nvidia/parakeet-tdt_ctc-0.6b-ja"
    ).to(device)
    
    results = []
    for i in range(repeat):
        print(f"\n第{i+1}次转录开始（Parakeet）...")
        start = time.time()
        outputs = model.transcribe([audio_path])
        text = outputs[0] if isinstance(outputs[0], str) else getattr(outputs[0], "text", str(outputs[0]))
        end = time.time()
        print(f"第{i+1}次转录用时：{end-start:.2f} 秒")
        print("转录结果：", text[:100] + "..." if len(text) > 100 else text)
        results.append(text)
    
    return results[-1]  # 返回最后一次结果

def transcribe_reazonspeech(audio_path: str, repeat: int = 2):
    """使用 ReazonSpeech 进行转写"""
    print("\n===== ReazonSpeech 转写 =====")
    
    from reazonspeech.nemo.asr import load_model, transcribe, audio_from_path
    
    print("正在加载 ReazonSpeech 模型...")
    model = load_model()
    audio = audio_from_path(audio_path)
    
    results = []
    for i in range(repeat):
        print(f"\n第{i+1}次转录开始（ReazonSpeech）...")
        start = time.time()
        ret = transcribe(model, audio)
        text = ret.text
        end = time.time()
        print(f"第{i+1}次转录用时：{end-start:.2f} 秒")
        print("转录结果：", text[:100] + "..." if len(text) > 100 else text)
        results.append(text)
    
    return results[-1]  # 返回最后一次结果

def main():
    input_audio = "ja2.wav"
    output_file = "transcript_results.txt"
    
    # 预处理音频文件为16kHz单声道
    print("预处理音频文件...")
    wav, sr = to_16k_mono(input_audio)
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    save_wav(wav, sr, temp_file.name)
    temp_path = temp_file.name
    
    try:
        # 四个模型的转写结果
        results = {}
        
        # Whisper Large-v3 转写
        try:
            results["Whisper Large-v3"] = transcribe_whisper(temp_path, model_name="large-v3", repeat=2)
            # 释放内存
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
        except Exception as e:
            print(f"Whisper Large-v3 转写失败: {e}")
            results["Whisper Large-v3"] = "转写失败"
        
        # Whisper Large-v3-turbo 转写
        print("\n开始 Whisper Large-v3-turbo 转写...")
        try:
            results["Whisper Large-v3-turbo"] = transcribe_whisper(temp_path, model_name="large-v3-turbo", repeat=2)
            print("Whisper Large-v3-turbo 转写完成")
        except Exception as e:
            print(f"Whisper Large-v3-turbo 转写失败: {e}")
            import traceback
            traceback.print_exc()
            results["Whisper Large-v3-turbo"] = "转写失败"
        
        # Parakeet 转写
        try:
            results["Parakeet TDT-CTC"] = transcribe_parakeet(temp_path, repeat=2)
        except Exception as e:
            print(f"Parakeet 转写失败: {e}")
            results["Parakeet TDT-CTC"] = "转写失败"
        
        # ReazonSpeech 转写
        try:
            results["ReazonSpeech"] = transcribe_reazonspeech(temp_path, repeat=2)
        except Exception as e:
            print(f"ReazonSpeech 转写失败: {e}")
            results["ReazonSpeech"] = "转写失败"
        
        # 保存结果到文件
        print(f"\n正在保存结果到 {output_file}...")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("===== 四模型音频转写结果 =====\n")
            f.write(f"音频文件: {input_audio}\n")
            f.write(f"转写时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for model_name, text in results.items():
                f.write(f"【{model_name}】\n")
                f.write(text + "\n")
                f.write("-" * 50 + "\n\n")
        
        print(f"结果已保存到 {output_file}")
        
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_path)
        except:
            pass

if __name__ == "__main__":
    # 处理 Windows 信号兼容性
    import sys, signal
    if sys.platform == "win32" and not hasattr(signal, "SIGKILL"):
        signal.SIGKILL = signal.SIGTERM
    
    main()