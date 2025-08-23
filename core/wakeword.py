import os
import gc
import numpy as  np
import warnings
import openwakeword
import logging
warnings.filterwarnings("ignore")
logging.getLogger().setLevel(logging.ERROR)
os.environ["HF_HUB_CACHE"] = os.path.join(os.getcwd(), "models")
openwakeword.utils.download_models()

from openwakeword.model import Model
# threshold can be low to get more false positives
def detect_from_audio(audio_data, sample_rate=16000, threshold=0.3, model_path="core/hey_aura.onnx"):
    try:
        # 初始化模型
        model = Model(wakeword_models=[model_path])
        if not model:
            return False, 0.0
        # 转为int16
        if audio_data.dtype == np.float32:
            audio_data = (np.clip(audio_data, -1.0, 1.0) * 32767).astype(np.int16)
        elif audio_data.dtype != np.int16:
            audio_data = audio_data.astype(np.int16)
        # 只取前1.5秒
        first_1_5_sec = audio_data[:min(int(sample_rate * 1.5), len(audio_data))]
        frame_size = 1280
        max_conf = 0
        for i in range(0, len(first_1_5_sec) - frame_size, frame_size):
            pred = model.predict(first_1_5_sec[i:i+frame_size])
            for _, c in pred.items():
                max_conf = max(max_conf, c)
        del model
        gc.collect()
        return max_conf > threshold, max_conf
    except Exception as e:
        print(f"WakeWord detection error: {e}")
        return False, 0.0

if __name__ == "__main__":
    from pydub import AudioSegment

    # 指定本地MP3文件路径
    mp3_path = "hey-aura.mp3"
    print(f"加载音频文件: {mp3_path}")

    # 读取MP3并转换为16kHz单声道
    audio = AudioSegment.from_mp3(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    samples = np.array(audio.get_array_of_samples())

    # 检测唤醒词
    print("开始检测唤醒词...")
    result, confidence = detect_from_audio(samples, sample_rate=16000, threshold=0.5)
    print(f"检测结果: {'检测到唤醒词' if result else '未检测到唤醒词'}，置信度: {confidence:.4f}")
