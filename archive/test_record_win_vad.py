import os
import math
from datetime import datetime
from collections import deque

import numpy as np
import soundcard as sc
import soundfile as sf
from scipy.signal import resample_poly
import torch

# ===================== 可调参数 =====================
SESSION_PREFIX = "session"               # 会话文件名前缀
OUT_DIR = "recordings"                   # 输出根目录
SAMPLE_RATE = 48000                      # 主录音采样率
VAD_SAMPLE_RATE = 16000                  # VAD 采样率（Silero：8k/16k；此处用 16k）
CHUNK_DUR = 0.05                         # 主录音处理块时长（秒），可不与 VAD 帧对齐
VAD_THRESHOLD = 0.5                      # 人声概率阈值（0~1）
END_SILENCE_SEC = 1.0                    # 结束判定静音时长（秒）
PRE_PAD_SEC = 0.20                       # 片段前缓冲（秒）
POST_PAD_SEC = 0.20                      # 片段后缓冲（秒）
PROB_SMOOTH_WIN = 5                      # VAD 概率滑动平均窗口（单位：帧）
AUDIO_SUBTYPE = "PCM_16"                 # 保存位深
# ===================================================

def load_silero_vad():
    torch.set_num_threads(1)
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        trust_repo=True,
        force_reload=False
    )
    model.eval()
    return model

def to_mono_float32(x: np.ndarray) -> np.ndarray:
    if x.ndim == 2 and x.shape[1] > 1:
        return x.mean(axis=1).astype(np.float32, copy=False)
    elif x.ndim == 2:
        return x[:, 0].astype(np.float32, copy=False)
    else:
        return x.astype(np.float32, copy=False)

def rational_resample(x: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    g = math.gcd(src_sr, dst_sr)
    up = dst_sr // g
    down = src_sr // g
    y = resample_poly(x, up, down)
    return y.astype(np.float32, copy=False)

class SegmentWriter:
    """人声分段文件的开启、写入、关闭（实时写盘，按主采样率写）"""
    def __init__(self, base_dir: str, sr: int, channels: int):
        self.base_dir = base_dir
        self.sr = sr
        self.channels = channels
        self.cur_sf = None
        self.cur_path = None
        self.seg_idx = 0
        os.makedirs(self.base_dir, exist_ok=True)

    def start(self, pre_chunks):
        if self.cur_sf is not None:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.seg_idx += 1
        fname = f"speech_{ts}_{self.seg_idx:04d}.wav"
        self.cur_path = os.path.join(self.base_dir, fname)
        self.cur_sf = sf.SoundFile(self.cur_path, mode="w",
                                   samplerate=self.sr,
                                   channels=self.channels,
                                   subtype=AUDIO_SUBTYPE)
        for c in pre_chunks:
            self.cur_sf.write(c)
        print(f"[VAD] ▶️  开始段落：{os.path.basename(self.cur_path)}")

    def write(self, chunk):
        if self.cur_sf is not None:
            self.cur_sf.write(chunk)

    def close_with_postpad(self, post_chunks, postpad_chunks):
        if self.cur_sf is None:
            return
        for i in range(min(postpad_chunks, len(post_chunks))):
            self.cur_sf.write(post_chunks[i])
        self.cur_sf.flush()
        self.cur_sf.close()
        print(f"[VAD] ⏹️  结束段落：{os.path.basename(self.cur_path)}")
        self.cur_sf = None
        self.cur_path = None

def main():
    session_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = os.path.join(OUT_DIR, f"{SESSION_PREFIX}_{session_tag}")
    seg_dir = os.path.join(session_dir, "segments")
    os.makedirs(seg_dir, exist_ok=True)

    full_path = os.path.join(session_dir, f"{SESSION_PREFIX}_{session_tag}.wav")

    # ======= 派生参数（主采样率粒度） =======
    CHUNK_FRAMES = max(1, int(round(SAMPLE_RATE * CHUNK_DUR)))
    PRE_CHUNKS = max(1, int(math.ceil(PRE_PAD_SEC / CHUNK_DUR)))
    POST_CHUNKS = max(1, int(math.ceil(POST_PAD_SEC / CHUNK_DUR)))

    # ======= VAD 帧参数（严格 512/256） =======
    VAD_WIN = 512 if VAD_SAMPLE_RATE == 16000 else 256          # 每帧采样点
    VAD_FRAME_DUR = VAD_WIN / float(VAD_SAMPLE_RATE)            # 每帧时长（秒）
    END_SILENCE_FRAMES = max(1, int(math.ceil(END_SILENCE_SEC / VAD_FRAME_DUR)))

    speaker = sc.default_speaker()
    mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
    print(f"[INFO] Loopback 设备: {speaker.name}")
    print(f"[INFO] 主录音采样率: {SAMPLE_RATE} Hz；VAD 采样率: {VAD_SAMPLE_RATE} Hz，帧长: {VAD_WIN} 点（{VAD_FRAME_DUR*1000:.1f} ms）")
    print(f"[INFO] 输出目录：{session_dir}")
    print(f"[INFO] END_SILENCE_FRAMES = {END_SILENCE_FRAMES}（≈{END_SILENCE_FRAMES*VAD_FRAME_DUR:.2f}s）")
    print(f"[INFO] 退出请按 Ctrl+C")

    print("[INFO] 正在加载 Silero VAD 模型 ...")
    model = load_silero_vad()
    print("[INFO] 模型已就绪。")

    # 运行时状态
    in_speech = False
    silence_frames_run = 0                        # 连续静音帧计数（VAD 帧级）
    pre_buffer = deque(maxlen=PRE_CHUNKS)         # 主块级前向缓冲（用于片段起始回放）
    post_silence_buffer = []                      # 主块级后缓冲（片段结束时选取写入）
    prob_hist_frames = deque(maxlen=PROB_SMOOTH_WIN)  # VAD 概率平滑窗口（帧级）

    vad16k_buf = np.zeros(0, dtype=np.float32)    # VAD 侧 16k 累积缓冲
    full_sf = None
    seg_writer = None

    try:
        with mic.recorder(samplerate=SAMPLE_RATE) as rec:
            while True:
                data = rec.record(numframes=CHUNK_FRAMES)   # [frames, channels], float32
                if data is None or len(data) == 0:
                    continue

                # 第一次拿到数据后，创建主文件和分段写入器
                if full_sf is None:
                    channels = data.shape[1] if (data.ndim == 2) else 1
                    full_sf = sf.SoundFile(full_path, mode="w",
                                           samplerate=SAMPLE_RATE,
                                           channels=channels,
                                           subtype=AUDIO_SUBTYPE)
                    seg_writer = SegmentWriter(seg_dir, SAMPLE_RATE, channels)

                # 主录音：持续写入整段
                full_sf.write(data)

                # ---- VAD：把当前主块转为 16k 并入缓冲，然后按 512 帧逐帧前向 ----
                mono = to_mono_float32(data)                                  # -> [N]
                vad_chunk = rational_resample(mono, SAMPLE_RATE, VAD_SAMPLE_RATE)
                if vad_chunk.size:
                    vad16k_buf = np.concatenate([vad16k_buf, vad_chunk])

                chunk_has_speech = False
                frames_this_chunk = 0

                # 按固定帧长喂模型（每帧 len = VAD_WIN）
                while vad16k_buf.size >= VAD_WIN:
                    frame = vad16k_buf[:VAD_WIN]
                    vad16k_buf = vad16k_buf[VAD_WIN:]

                    with torch.no_grad():
                        # TorchScript 要求最后一维长度为 VAD_WIN；1D 张量即可
                        prob = float(model(torch.from_numpy(frame), VAD_SAMPLE_RATE).item())

                    prob_hist_frames.append(prob)
                    avg_prob = sum(prob_hist_frames) / len(prob_hist_frames)
                    is_speech_frame = (avg_prob >= VAD_THRESHOLD)
                    frames_this_chunk += 1
                    if is_speech_frame:
                        chunk_has_speech = True
                        silence_frames_run = 0
                    else:
                        silence_frames_run += 1

                # ---- 用帧级统计驱动块级切段逻辑（写盘仍以主块为单位） ----
                pre_buffer.append(data)

                if not in_speech:
                    if chunk_has_speech:
                        seg_writer.start(list(pre_buffer))
                        seg_writer.write(data)
                        in_speech = True
                        post_silence_buffer.clear()
                else:
                    if chunk_has_speech:
                        # 刚才有缓存的静音主块，视为误判，补回去
                        if post_silence_buffer:
                            for ch in post_silence_buffer:
                                seg_writer.write(ch)
                            post_silence_buffer.clear()
                        seg_writer.write(data)
                    else:
                        # 当前主块内没有任何“语音帧”
                        post_silence_buffer.append(data)
                        # 当累计静音帧达到阈值（≈1s）则收尾
                        if silence_frames_run >= END_SILENCE_FRAMES:
                            seg_writer.close_with_postpad(post_silence_buffer, POST_CHUNKS)
                            in_speech = False
                            silence_frames_run = 0
                            post_silence_buffer.clear()

    except KeyboardInterrupt:
        print("\n[INFO] 收到中断，正在安全退出 ...")
    finally:
        if full_sf is not None:
            # 若还有未关闭的段落，按规则收尾
            if in_speech and seg_writer is not None:
                seg_writer.close_with_postpad(post_silence_buffer, POST_CHUNKS)
            full_sf.flush()
            full_sf.close()

    print(f"[DONE] 整段录音已保存：{full_path}")
    print(f"[DONE] 人声片段保存在：{seg_dir}")  

if __name__ == "__main__":
    main()
