import time
from urllib.parse import quote_plus
import webbrowser
from pynput.keyboard import Key, Controller
from core.keyboard_utils import ClipboardInjector

def pplx(query: str):
    url = f"https://www.perplexity.ai/search?q={quote_plus(query)}"
    webbrowser.open(url)

def _open_and_paste(url: str, query: str):
    injector = ClipboardInjector()
    webbrowser.open(url)
    time.sleep(5)
    injector.type(query)
    time.sleep(0.5)
    kbd = Controller()
    kbd.press(Key.enter)
    kbd.release(Key.enter)

def chatgpt(query: str):
    _open_and_paste("https://chatgpt.com", query)

def claude(query: str):
    _open_and_paste("https://claude.ai/new", query)

def kimi(query: str):
    _open_and_paste("https://www.kimi.com/new", query)

def deepseek(query: str):
    _open_and_paste("https://chat.deepseek.com/", query)

if __name__ == "__main__":
    pplx("Tesla delivery volume comparison between 2025 and 2024")