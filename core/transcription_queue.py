import queue
import threading
import time
import uuid
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from core.i18n import _


@dataclass
class TranscriptionTask:
    task_id: str
    audio_path: str
    language: Optional[str]
    callback: Callable[[str, str], None]
    error_callback: Optional[Callable[[str, Exception], None]] = None
    kwargs: Dict[str, Any] = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None: self.created_at = time.time()
        if self.kwargs is None: self.kwargs = {}


class TranscriptionQueue:
    def __init__(self, transcriber, max_workers=5, max_queue_size=50):
        self.transcriber = transcriber
        self.max_workers = max_workers
        self.task_queue = queue.Queue(maxsize=max_queue_size)
        self.active_tasks = {}
        self.workers = []
        self.running = False
        self.stats = {'total_tasks': 0, 'completed_tasks': 0, 'failed_tasks': 0, 'queue_size': 0}
        self.stats_lock = threading.Lock()
        self.transcribe_lock = threading.Lock()
        
    def start(self):
        if self.running: return
        print(_("→ Starting transcription service..."))
        self.running = True
        
        for i in range(self.max_workers):
            w = threading.Thread(target=self._worker_thread, name=f"TranscriptionWorker-{i+1}", daemon=True)
            w.start()
            self.workers.append(w)
        print(_("✅ Transcription service ready"))
    
    def stop(self, timeout=10):
        if not self.running: return
        print(_("🔄 Stopping transcription service..."))
        self.running = False
        
        for _tmp in range(self.max_workers):
            try: self.task_queue.put(None, timeout=1)
            except queue.Full: pass
        
        for w in self.workers:
            w.join(timeout=timeout)
            if w.is_alive(): print(_("⚠️ Worker thread did not stop gracefully: {}").format(w.name))
        
        self.workers.clear()
        print(_("✅ Transcription service stopped"))
    
    def submit_task(self, audio_path: str, callback: Callable[[str, str], None], 
                   language: Optional[str] = None, 
                   error_callback: Optional[Callable[[str, Exception], None]] = None,
                   **kwargs) -> str:
        if not self.running: raise RuntimeError("Transcription queue is not running")
        
        task_id = str(uuid.uuid4())
        task = TranscriptionTask(task_id=task_id, audio_path=audio_path, language=language,
                               callback=callback, error_callback=error_callback, kwargs=kwargs)
        
        try:
            self.task_queue.put(task, timeout=1)
            with self.stats_lock:
                self.stats['total_tasks'] += 1
                self.stats['queue_size'] = self.task_queue.qsize()
            return task_id
        except queue.Full:
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        with self.stats_lock:
            stats = self.stats.copy()
            stats['queue_size'] = self.task_queue.qsize()
            stats['active_tasks'] = len(self.active_tasks)
            stats['running'] = self.running
        return stats
    
    def _worker_thread(self):
        wname = threading.current_thread().name
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None: break
                self._process_task(task, wname)
            except queue.Empty: continue
            except Exception as e:
                print(_("❌ Worker thread error: {} - {}").format(wname, e))
                import traceback
                traceback.print_exc()
        
        print(_("→ Transcription worker stopped: {}").format(wname))
    
    def _process_task(self, task: TranscriptionTask, wname: str):
        tid = task.task_id[:8]
        t0 = time.time()
        
        try:
            self.active_tasks[task.task_id] = {'task': task, 'worker': wname, 'start_time': t0}
            
            with self.transcribe_lock:
                result = self.transcriber.transcribe(task.audio_path, language=task.language, **task.kwargs)
            
            dt = time.time() - t0
            print(_("✅ Transcription completed in {:.2f}s").format(dt))
            
            if task.callback:
                try: task.callback(task.task_id, result)
                except Exception as e: print(_("❌ Callback error for task: {}... - {}").format(tid, e))
            
            with self.stats_lock: self.stats['completed_tasks'] += 1
                
        except Exception as e:
            dt = time.time() - t0
            print(_("❌ Transcription failed: {}... in {:.2f}s - {}").format(tid, dt, e))
            
            if task.error_callback:
                try: task.error_callback(task.task_id, e)
                except Exception as ce: print(_("❌ Error callback failed for task: {}... - {}").format(tid, ce))
            
            with self.stats_lock: self.stats['failed_tasks'] += 1
                
        finally:
            self.active_tasks.pop(task.task_id, None)
            with self.stats_lock: self.stats['queue_size'] = self.task_queue.qsize()


class AsyncTranscriptionManager:
    def __init__(self, transcriber, max_workers=2):
        self.queue = TranscriptionQueue(transcriber, max_workers=max_workers)
        self.pending_results = {}
        self.result_lock = threading.Lock()
        
    def start(self): self.queue.start()
    def stop(self): self.queue.stop()
    
    def transcribe_async(self, audio_path: str, language: Optional[str] = None, **kwargs) -> str:
        def success_cb(task_id: str, result: str):
            with self.result_lock: self.pending_results[task_id] = {'success': True, 'result': result}
        
        def error_cb(task_id: str, error: Exception):
            with self.result_lock: self.pending_results[task_id] = {'success': False, 'error': error}
        
        return self.queue.submit_task(audio_path=audio_path, language=language,
                                    callback=success_cb, error_callback=error_cb, **kwargs)
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> str:
        t0 = time.time()
        
        while True:
            with self.result_lock:
                if task_id in self.pending_results:
                    res = self.pending_results.pop(task_id)
                    return res['result'] if res['success'] else exec('raise res["error"]')
            
            if timeout and (time.time() - t0) > timeout:
                raise TimeoutError(f"Transcription task {task_id[:8]}... timed out")
            
            time.sleep(0.1)
    
    def transcribe_sync(self, audio_path: str, language: Optional[str] = None, 
                       timeout: Optional[float] = 30, **kwargs) -> str:
        return self.get_result(self.transcribe_async(audio_path, language, **kwargs), timeout)
    
    def get_stats(self) -> Dict[str, Any]: return self.queue.get_stats()
