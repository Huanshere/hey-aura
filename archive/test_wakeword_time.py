from openwakeword.model import Model
import numpy as np
import wave
import time
from pydub import AudioSegment
import tempfile
import gc

def test_without_reset(audio_file, num_tests=5):
    """不重置模型，连续测试多次"""
    print("\n" + "="*60)
    print("测试1: 不重置模型，连续测试")
    print("="*60)
    
    # 创建一个模型实例
    model = Model(wakeword_models=["core/hey_aura.onnx"])
    
    # 准备音频数据
    audio = AudioSegment.from_mp3(audio_file)
    audio = audio.set_frame_rate(16000).set_channels(1)
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
        temp_wav_path = temp_wav.name
        audio.export(temp_wav_path, format="wav")
    
    with wave.open(temp_wav_path, 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
        audio_data = np.frombuffer(frames, dtype=np.int16)
    
    frame_size = 1280
    results = []
    
    for test_num in range(num_tests):
        start_time = time.time()
        max_confidence = 0
        
        # 逐帧检测
        for i in range(0, len(audio_data) - frame_size, frame_size):
            frame = audio_data[i:i + frame_size]
            prediction = model.predict(frame)
            
            for wakeword, confidence in prediction.items():
                if confidence > max_confidence:
                    max_confidence = confidence
        
        inference_time = time.time() - start_time
        results.append(max_confidence)
        
        print(f"第 {test_num+1} 次测试: 置信度 = {max_confidence:.4f}, 推理时间 = {inference_time:.3f}秒")
    
    return results

def test_with_reset(audio_file, num_tests=5):
    """每次都重置模型后测试"""
    print("\n" + "="*60)
    print("测试2: 每次重置模型后测试")
    print("="*60)
    
    # 准备音频数据（只需要准备一次）
    audio = AudioSegment.from_mp3(audio_file)
    audio = audio.set_frame_rate(16000).set_channels(1)
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
        temp_wav_path = temp_wav.name
        audio.export(temp_wav_path, format="wav")
    
    with wave.open(temp_wav_path, 'rb') as wav:
        frames = wav.readframes(wav.getnframes())
        audio_data = np.frombuffer(frames, dtype=np.int16)
    
    frame_size = 1280
    results = []
    
    for test_num in range(num_tests):
        # 重置模型
        reset_start = time.time()
        model = None
        gc.collect()
        model = Model(wakeword_models=["core/hey_aura.onnx"])
        reset_time = time.time() - reset_start
        
        # 推理
        inference_start = time.time()
        max_confidence = 0
        
        for i in range(0, len(audio_data) - frame_size, frame_size):
            frame = audio_data[i:i + frame_size]
            prediction = model.predict(frame)
            
            for wakeword, confidence in prediction.items():
                if confidence > max_confidence:
                    max_confidence = confidence
        
        inference_time = time.time() - inference_start
        results.append(max_confidence)
        
        print(f"第 {test_num+1} 次测试: 置信度 = {max_confidence:.4f}, 重置时间 = {reset_time:.3f}秒, 推理时间 = {inference_time:.3f}秒")
    
    return results

def compare_results(results_no_reset, results_with_reset):
    """比较两种方法的结果"""
    print("\n" + "="*60)
    print("结果对比分析")
    print("="*60)
    
    print("\n不重置模型的置信度变化:")
    print(f"  值: {[f'{r:.4f}' for r in results_no_reset]}")
    print(f"  平均值: {np.mean(results_no_reset):.4f}")
    print(f"  标准差: {np.std(results_no_reset):.4f}")
    print(f"  最大值: {max(results_no_reset):.4f}")
    print(f"  最小值: {min(results_no_reset):.4f}")
    
    print("\n每次重置模型的置信度变化:")
    print(f"  值: {[f'{r:.4f}' for r in results_with_reset]}")
    print(f"  平均值: {np.mean(results_with_reset):.4f}")
    print(f"  标准差: {np.std(results_with_reset):.4f}")
    print(f"  最大值: {max(results_with_reset):.4f}")
    print(f"  最小值: {min(results_with_reset):.4f}")
    
    # 判断模型是否有"记忆效应"
    print("\n" + "="*60)
    print("结论:")
    
    # 检查不重置模型时是否出现置信度下降
    if results_no_reset[0] > 0.3 and all(r < 0.1 for r in results_no_reset[1:]):
        print("❌ 模型存在严重的状态累积问题！第一次检测后置信度急剧下降。")
        print("   必须在每次检测前重置模型。")
    elif np.std(results_no_reset) > 0.1:
        print("⚠️ 模型存在轻微的状态累积问题，置信度有波动。")
        print("   建议在每次检测前重置模型。")
    else:
        print("✅ 模型状态管理良好，连续检测结果稳定。")
    
    # 检查重置是否有效
    if np.std(results_with_reset) < 0.01:
        print("✅ 模型重置有效，每次检测结果高度一致。")
    else:
        print("⚠️ 即使重置模型，结果仍有一定波动。")
    
    print("="*60)

# 主程序
if __name__ == "__main__":
    test_file = "hey-aura.mp3"
    
    print("🚀 开始模型重置效果验证测试...")
    print(f"测试文件: {test_file}")
    
    # 测试1: 不重置模型
    results_no_reset = test_without_reset(test_file, num_tests=5)
    
    # 等待一下，确保资源释放
    time.sleep(1)
    
    # 测试2: 每次重置模型
    results_with_reset = test_with_reset(test_file, num_tests=5)
    
    # 对比分析
    compare_results(results_no_reset, results_with_reset)
    
    # 可视化（如果有matplotlib）
    try:
        import matplotlib.pyplot as plt
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # 左图：不重置模型
        ax1.plot(range(1, len(results_no_reset)+1), results_no_reset, 'r-o', linewidth=2, markersize=8)
        ax1.set_xlabel('测试次数')
        ax1.set_ylabel('置信度')
        ax1.set_title('不重置模型 - 连续测试')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylim([0, 1])
        
        # 右图：每次重置模型
        ax2.plot(range(1, len(results_with_reset)+1), results_with_reset, 'g-o', linewidth=2, markersize=8)
        ax2.set_xlabel('测试次数')
        ax2.set_ylabel('置信度')
        ax2.set_title('每次重置模型 - 测试')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim([0, 1])
        
        plt.suptitle('模型重置效果对比', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plt.savefig('model_reset_comparison.png', dpi=100)
        plt.show()
        
        print("\n📊 对比图表已保存为 'model_reset_comparison.png'")
    except ImportError:
        pass