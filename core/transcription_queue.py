import queue
import threading
import time
from typing import Optional
from core.i18n import _

_task_queue = None
_workers = []
_transcriber = None
_running = False
_transcribe_lock = threading.Lock()

def init(transcriber, max_workers=5):
    global _task_queue, _transcriber, _running, _workers
    
    if _running: return
    
    print(_("→ Starting transcription service..."))
    _task_queue = queue.Queue(maxsize=50)
    _transcriber = transcriber
    _running = True
    
    for i in range(max_workers):
        worker = threading.Thread(
            target=_process_queue,
            daemon=True,
            name=f"TranscriptionWorker-{i+1}"
        )
        worker.start()
        _workers.append(worker)
    
    print(_("✅ Transcription service ready"))

def transcribe(audio_path: str, language: Optional[str] = None, timeout: float = 30, **kwargs) -> str:
    if not _running or not _task_queue:
        with _transcribe_lock:
            return _transcriber.transcribe(audio_path, language=language, **kwargs)
    
    result = {'done': False, 'result': None, 'error': None}
    event = threading.Event()
    
    try:
        _task_queue.put((audio_path, language, kwargs, result, event), timeout=1)
    except queue.Full:
        print(_("⚠️ Queue full, using direct transcription"))
        with _transcribe_lock:
            return _transcriber.transcribe(audio_path, language=language, **kwargs)
    
    if not event.wait(timeout=timeout):
        raise TimeoutError(_("Transcription timeout"))
    
    if result['error']: raise result['error']
    return result['result']

def _process_queue():
    while _running:
        try:
            task = _task_queue.get(timeout=1)
            if task is None: break
            
            audio_path, language, kwargs, result, event = task
            t0 = time.time()
            
            try:
                with _transcribe_lock:
                    result['result'] = _transcriber.transcribe(audio_path, language=language, **kwargs)
                print(_("✅ Transcription completed in {:.2f}s").format(time.time() - t0))
            except Exception as e:
                print(_("❌ Transcription failed in {:.2f}s - {}").format(time.time() - t0, e))
                result['error'] = e
            finally:
                result['done'] = True
                event.set()
                
        except queue.Empty:
            continue
        except Exception as e:
            print(_("❌ Worker thread error: {}").format(e))
    
    print(_("→ Transcription worker stopped: {}").format(threading.current_thread().name))
