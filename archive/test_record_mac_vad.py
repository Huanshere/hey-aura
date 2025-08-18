#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS 13+ ScreenCaptureKit → WAV 分片 → 读取分片做 Silero VAD
当检测到“说话 -> 结束后 ≥1s 静默”时，实时保存语音片段到 segments/，程序持续运行直至 Ctrl+C。

依赖：
  pip install -U pyobjc pyobjc-framework-ScreenCaptureKit numpy torch silero-vad soundfile
"""

import os, sys, time, threading, queue, argparse
from datetime import datetime

import numpy as np
import objc
from Foundation import NSObject, NSDate, NSRunLoop
from ScreenCaptureKit import (
    SCShareableContent, SCContentFilter, SCStream, SCStreamConfiguration
)
try:
    from ScreenCaptureKit import SCStreamOutputTypeAudio as AUDIO_OUT_TYPE
except Exception:
    from ScreenCaptureKit import SCStreamOutputType as _SCType
    AUDIO_OUT_TYPE = _SCType.Audio

from AVFoundation import (
    AVAssetWriter, AVAssetWriterInput, AVMediaTypeAudio, AVFileTypeWAVE
)
from CoreMedia import (
    CMSampleBufferGetPresentationTimeStamp,
    CMSampleBufferGetNumSamples,
    CMTimeMakeWithSeconds
)

import torch
import soundfile as sf  # <<< 新增：用它读取 WAVE_EXTENSIBLE

kAudioFormatLinearPCM = 1819304813

def _spin_runloop(step_s=0.02):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(step_s))

# -------------------- 简单重采样（线性插值）到 16k --------------------
def resample_linear(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """x: float32 mono in [-1,1]"""
    if sr_in == sr_out or x.size == 0:
        return x.astype(np.float32, copy=False)
    ratio = sr_out / float(sr_in)
    n_out = int(np.floor(x.size * ratio))
    xp = np.arange(x.size, dtype=np.float32)
    fp = x.astype(np.float32, copy=False)
    xnew = np.linspace(0, x.size - 1, n_out, dtype=np.float32)
    y = np.interp(xnew, xp, fp).astype(np.float32, copy=False)
    return y

# -------------------- VAD 片段器 --------------------
class SileroVADSegmenter:
    def __init__(self, threshold=0.5, sr=16000, min_silence_ms=1000, pad_ms=100,
                 window_size=512, out_dir="segments"):
        self.sr = int(sr)
        self.threshold = float(threshold)
        self.min_silence_samples = int(self.sr * (min_silence_ms/1000.0))
        self.pad_samples = int(self.sr * (pad_ms/1000.0))
        self.window_size = int(window_size)
        self.out_dir = out_dir
        os.makedirs(self.out_dir, exist_ok=True)

        torch.set_num_threads(1)
        try:
            from silero_vad import load_silero_vad
            self.model = load_silero_vad(onnx=False)
        except Exception:
            self.model, _ = torch.hub.load('snakers4/silero-vad', 'silero_vad', onnx=False)

        # 状态
        self.triggered = False
        self.silence_run = 0
        self.pre_roll = bytearray()
        self.seg_buf = bytearray()
        self.tail_buf = bytearray()
        self._float_resid = np.empty(0, dtype=np.float32)
        self._int16_resid = bytearray()
        self.idx = 0

    @staticmethod
    def _float_to_int16_bytes(x: np.ndarray) -> bytes:
        x = np.clip(x, -1.0, 1.0)
        return (x * 32767.0).astype(np.int16).tobytes()

    def _write_wav_16k(self, pcm_bytes: bytes, path: str):
        import wave
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm_bytes)

    def _reset(self):
        self.triggered = False
        self.silence_run = 0
        self.seg_buf.clear()
        self.tail_buf.clear()

    def _on_segment_complete(self):
        if not self.seg_buf:
            self._reset(); return ""
        if len(self.tail_buf) > 0:
            keep = min(self.pad_samples, len(self.tail_buf)//2)
            if keep > 0:
                self.seg_buf.extend(self.tail_buf[:keep*2])
            self.tail_buf.clear()
        fn = f"seg_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{self.idx:06d}.wav"
        fp = os.path.join(self.out_dir, fn)
        self._write_wav_16k(self.seg_buf, fp)
        dur = len(self.seg_buf)/(2*self.sr)
        print(f"💾 Saved segment: {fp} ({dur:.2f}s)")
        self.idx += 1
        self._reset()
        return fp

    def push_samples(self, f32: np.ndarray, i16_bytes: bytes):
        if f32.size == 0: return
        self._float_resid = np.concatenate([self._float_resid, f32])
        self._int16_resid.extend(i16_bytes)

        W = self.window_size
        B = W*2
        while (self._float_resid.shape[0] >= W) and (len(self._int16_resid) >= B):
            chunk_f = self._float_resid[:W]; self._float_resid = self._float_resid[W:]
            chunk_b = self._int16_resid[:B]; del self._int16_resid[:B]
            with torch.no_grad():
                p = self.model(torch.from_numpy(chunk_f), self.sr).item()

            if p >= self.threshold:
                if not self.triggered:
                    if self.pre_roll:
                        self.seg_buf.extend(self.pre_roll); self.pre_roll.clear()
                    self.triggered = True; self.silence_run = 0
                if self.tail_buf:
                    self.seg_buf.extend(self.tail_buf); self.tail_buf.clear()
                self.seg_buf.extend(chunk_b)
            else:
                if not self.triggered:
                    self.pre_roll.extend(chunk_b)
                    max_bytes = self.pad_samples*2
                    extra = len(self.pre_roll) - max_bytes
                    if extra > 0: del self.pre_roll[:extra]
                else:
                    self.tail_buf.extend(chunk_b)
                    self.silence_run += W
                    if self.silence_run >= self.min_silence_samples:
                        self._on_segment_complete()

    def flush(self):
        if self.seg_buf:
            self._on_segment_complete()

# -------------------- 写 WAV 分片 --------------------
class ChunkedWavWriter(NSObject):
    def initWithParams_(self, params):
        self = objc.super(ChunkedWavWriter, self).init()
        if self is None: return None
        self.params = params
        self.w = None
        self.ai = None
        self.on = False
        self.samples_in_chunk = 0
        self.chunk_idx = 0
        os.makedirs(self.params["chunks_dir"], exist_ok=True)
        return self

    def _open_writer(self, first_sb):
        fname = f"chunk_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}_{self.chunk_idx:06d}.wav"
        self.current_path = os.path.join(self.params["chunks_dir"], fname)
        url = objc.lookUpClass("NSURL").fileURLWithPath_(self.current_path)

        self.w, e = AVAssetWriter.alloc().initWithURL_fileType_error_(url, AVFileTypeWAVE, None)
        if e: raise RuntimeError(f"Writer create error: {e}")

        settings = {
            "AVFormatIDKey": kAudioFormatLinearPCM,
            "AVSampleRateKey": self.params["capture_sr"],
            "AVNumberOfChannelsKey": self.params["capture_ch"],
            "AVLinearPCMBitDepthKey": 16,
            "AVLinearPCMIsFloatKey": False,
            "AVLinearPCMIsBigEndianKey": False,
            "AVLinearPCMIsNonInterleaved": False,
        }
        self.ai = AVAssetWriterInput.alloc().initWithMediaType_outputSettings_(AVMediaTypeAudio, settings)
        self.ai.setExpectsMediaDataInRealTime_(True)
        if self.w.canAddInput_(self.ai): self.w.addInput_(self.ai)
        else: raise RuntimeError("Can't add audio input to AVAssetWriter")

        if not self.w.startWriting():
            raise RuntimeError(f"Writer start failed: {self.w.error()}")

        self.w.startSessionAtSourceTime_(CMSampleBufferGetPresentationTimeStamp(first_sb))
        self.on = True
        self.samples_in_chunk = 0

    def _close_writer_async(self):
        if not self.on: return
        self.ai.markAsFinished()
        path = self.current_path
        self.on = False
        # 完成写入后把文件路径放到队列交给 VAD
        self.w.finishWritingWithCompletionHandler_(lambda: self.params["queue"].put(path))
        self.chunk_idx += 1
        self.w = None
        self.ai = None
        self.current_path = None
        self.samples_in_chunk = 0

    def stream_didOutputSampleBuffer_ofType_(self, stream, sb, out_type):
        if out_type != AUDIO_OUT_TYPE:
            return
        if not self.on:
            self._open_writer(sb)

        if self.ai is not None and self.ai.isReadyForMoreMediaData():
            ok = self.ai.appendSampleBuffer_(sb)
            if ok:
                n = CMSampleBufferGetNumSamples(sb)
                self.samples_in_chunk += int(n)
                if self.samples_in_chunk >= self.params["chunk_samples"]:
                    self._close_writer_async()

    def finish(self):
        self._close_writer_async()

# -------------------- VAD 工作线程：读分片（用 soundfile） --------------------
class VADWorker(threading.Thread):
    def __init__(self, in_queue: queue.Queue, segments_dir: str,
                 threshold: float, min_silence_ms: int, pad_ms: int,
                 window: int, vad_sr: int, keep_chunks: bool):
        super().__init__(daemon=True)
        self.q = in_queue
        self.keep_chunks = keep_chunks
        self.vad_sr = vad_sr
        self.vad = SileroVADSegmenter(threshold=threshold, sr=vad_sr,
                                      min_silence_ms=min_silence_ms, pad_ms=pad_ms,
                                      window_size=window, out_dir=segments_dir)
        self._stop = threading.Event()
        self._printed_info = False

    def stop(self):
        self._stop.set()

    def run(self):
        print("🎧 VAD worker started; waiting for chunks...")
        while not self._stop.is_set() or not self.q.empty():
            try:
                path = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self.process_one_chunk(path)
            except Exception as e:
                print(f"[VAD] process error on {path}: {e}")
            finally:
                if not self.keep_chunks:
                    try: os.remove(path)
                    except Exception: pass
                self.q.task_done()
        # flush
        self.vad.flush()
        print("🎧 VAD worker stopped.")

    def process_one_chunk(self, path: str):
        # 用 soundfile 读取（支持 WAVE_EXTENSIBLE；dtype='float32' 直接得到 -1..1）
        # 做一个小重试，避免极偶发的文件写入延迟
        last_err = None
        for _ in range(3):
            try:
                data, sr = sf.read(path, dtype='float32', always_2d=True)
                break
            except Exception as e:
                last_err = e
                time.sleep(0.05)
        if last_err and 'data' not in locals():
            raise last_err

        if data.size == 0:
            return

        if not self._printed_info:
            print(f"🔊 chunk opened: {os.path.basename(path)} sr={sr}, shape={data.shape} (frames, channels)")
            self._printed_info = True

        # 下混为单声道
        f32_mono = data.mean(axis=1).astype(np.float32, copy=False)

        # 重采样到 VAD 采样率
        f32_rs = resample_linear(f32_mono, sr_in=sr, sr_out=self.vad_sr)

        # 生成对应 int16 bytes 用于写盘
        i16_rs_bytes = (np.clip(f32_rs, -1, 1) * 32767.0).astype(np.int16).tobytes()

        # 喂给 VAD（内部窗口推进）
        self.vad.push_samples(f32_rs, i16_rs_bytes)

# -------------------- 组合：启动采集 + 启动 VAD worker --------------------
def start_pipeline(args):
    # 1) 启动 VAD worker
    q = queue.Queue(maxsize=256)
    worker = VADWorker(q, args.segments_dir, args.threshold,
                       args.min_silence_ms, args.pad_ms,
                       args.window, args.vad_sr, args.keep_chunks)
    worker.start()

    # 2) ScreenCaptureKit 枚举
    box = {"ok": 0, "c": None, "e": None}
    def _cb(c, e):
        box["ok"] = 1; box["c"] = c; box["e"] = e
    SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, _cb
    )
    st = time.time()
    while not box["ok"]:
        _spin_runloop(0.02)
        if time.time() - st > 5: break
    if box["e"]:
        worker.stop(); worker.join()
        raise RuntimeError(box["e"])
    content = box["c"]
    displays = content.displays()
    if not displays:
        worker.stop(); worker.join()
        raise RuntimeError("No display available.")
    dsp = displays[0]

    # 3) 过滤器与配置
    flt = SCContentFilter.alloc().initWithDisplay_includingApplications_exceptingWindows_(
        dsp, content.applications(), []
    )
    cfg = SCStreamConfiguration.alloc().init()
    cfg.setCapturesAudio_(True)
    cfg.setCaptureMicrophone_(False)
    cfg.setExcludesCurrentProcessAudio_(bool(args.exclude_self))
    cfg.setSampleRate_(args.capture_sr)     # 常见 48000
    cfg.setChannelCount_(args.capture_ch)   # 常见 2
    cfg.setWidth_(64); cfg.setHeight_(64)
    cfg.setMinimumFrameInterval_(CMTimeMakeWithSeconds(1, 1000))
    if hasattr(cfg, "setQueueDepth_"): cfg.setQueueDepth_(1)

    # 4) 分片写入对象
    params = {
        "chunks_dir": args.chunks_dir,
        "chunk_samples": int(args.capture_sr * (args.chunk_ms/1000.0)),
        "capture_sr": args.capture_sr,
        "capture_ch": args.capture_ch,
        "queue": q,
    }
    out = ChunkedWavWriter.alloc().initWithParams_(params)

    # 5) 启动 SCStream
    stream = SCStream.alloc().initWithFilter_configuration_delegate_(flt, cfg, None)
    ok, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(out, AUDIO_OUT_TYPE, None, None)
    if not ok or err is not None:
        worker.stop(); worker.join()
        raise RuntimeError(f"addStreamOutput failed: ok={ok}, err={err}")

    started = {"ok": 0, "e": None}
    stream.startCaptureWithCompletionHandler_(lambda e: started.update(ok=1, e=e))
    while not started["ok"]:
        _spin_runloop(0.02)
    if started["e"]:
        worker.stop(); worker.join()
        raise RuntimeError(f"startCapture error: {started['e']}")

    print("✅ ScreenCaptureKit audio capture started.")
    print(f"   capture_sr={args.capture_sr}, capture_ch={args.capture_ch}, chunk_ms={args.chunk_ms}")
    print(f"   VAD: sr={args.vad_sr}, threshold={args.threshold}, min_silence_ms={args.min_silence_ms}, "
          f"pad_ms={args.pad_ms}, window={args.window}")
    print(f"   chunks dir:   {os.path.abspath(args.chunks_dir)}")
    print(f"   segments dir: {os.path.abspath(args.segments_dir)}")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            _spin_runloop(0.05)
    except KeyboardInterrupt:
        print("\n⏹ Stopping capture...")
    finally:
        stopped = {"ok": 0}
        stream.stopCaptureWithCompletionHandler_(lambda e: stopped.update(ok=1))
        while not stopped["ok"]:
            _spin_runloop(0.02)
        out.finish()
        q.join()
        worker.stop()
        worker.join()
        print("Bye.")

# -------------------- CLI --------------------
def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="ScreenCaptureKit -> WAV chunks -> Silero VAD stream splitter")
    p.add_argument("--chunks_dir", type=str, default="chunks")
    p.add_argument("--segments_dir", type=str, default="segments")
    p.add_argument("--keep_chunks", action="store_true", help="保留 chunk 文件（默认处理完就删除）")

    # 采集与切片
    p.add_argument("--capture_sr", type=int, default=48000, help="采集端采样率（常见 48000）")
    p.add_argument("--capture_ch", type=int, default=2, help="采集端声道（1 或 2）")
    p.add_argument("--chunk_ms", type=int, default=1000, help="每个 WAV 分片的时长（毫秒）")
    p.add_argument("--exclude_self", type=str, default="true", help="排除本进程音频（true/false）")

    # VAD 参数
    p.add_argument("--vad_sr", type=int, default=16000, choices=[8000,16000], help="VAD 使用的采样率")
    p.add_argument("--threshold", type=float, default=0.5, help="VAD 概率阈值")
    p.add_argument("--min_silence_ms", type=int, default=1000, help="静默判段阈值（毫秒）")
    p.add_argument("--pad_ms", type=int, default=100, help="片段前后 padding（毫秒）")
    p.add_argument("--window", type=int, default=512, help="VAD 推理窗口（样本，16k 推荐 512/1024/1536）")

    args = p.parse_args()
    args.exclude_self = str(args.exclude_self).lower() in ("1","true","yes","y","t")
    return args

if __name__ == "__main__":
    args = parse_args()
    start_pipeline(args)
