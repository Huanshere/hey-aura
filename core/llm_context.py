import json
import yaml
import datetime
import ollama
from pathlib import Path
from typing import List, Dict, Any
from openai import OpenAI
from core.i18n import _
from core.get_active_window import get_active_window

cfg = yaml.safe_load(open('config.yaml', encoding='utf-8'))['llm']
HISTORY_FILE = Path('recordings/command_mode_history.json')
msgs: List[Dict[str, Any]] = []
REPOS = {}

def scan():
    """Scan dirs for repos."""
    REPOS.clear()
    for wd in yaml.safe_load(open('config.yaml', encoding='utf-8')).get('repo_watch_directories', []):
        for p in Path(wd).expanduser().iterdir():
            if (p.is_dir() and not p.name.startswith('.') and 
                ((p / '.git').exists() or 
                any((p / f).exists() for f in ['package.json', 'requirements.txt', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py']))):
                REPOS[p.name] = str(p)

def get_sys():
    """Gen system prompt."""
    scan()
    tpl = open('core/prompts/command_mode_sys_prompt.md', encoding='utf-8').read()
    return (tpl.replace('{{Available Repositories}}', "\n".join(f"  - {n}" for n in REPOS.keys()) if REPOS else "")
               .replace('{{Current Window}}', get_active_window())
               .replace('{{Current Time}}', datetime.datetime.now().isoformat(sep=' ', timespec='seconds')))

def load_hist():
    """Load history: last 8 rounds within 2 hours."""
    global msgs
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    
    if not HISTORY_FILE.exists():
        msgs = []
        return
    
    try:
        all_msgs = json.load(open(HISTORY_FILE, 'r', encoding='utf-8'))
    except (json.JSONDecodeError, FileNotFoundError):
        msgs = []
        return
    
    # Keep msgs within 2 hours
    now = datetime.datetime.now()
    filtered = [m for m in all_msgs 
                if datetime.datetime.fromisoformat(m['timestamp']) > now - datetime.timedelta(hours=2)]
    
    # Group into rounds (user + tools + assistant)
    rounds, cur = [], []
    for m in filtered:
        if m['role'] == 'user' and cur:
            rounds.append(cur)
            cur = [m]
        else:
            cur.append(m)
    if cur:
        rounds.append(cur)
    
    # Keep last 8 rounds
    msgs = [m for r in rounds[-8:] for m in r]

def save_hist():
    """Save history."""
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    json.dump(msgs, open(HISTORY_FILE, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def add_msg(role: str, content: str):
    """Add msg with timestamp."""
    msgs.append({
        'role': role,
        'content': content,
        'timestamp': datetime.datetime.now().isoformat()
    })
    save_hist()

def call_llm(prompt=None):
    """Call LLM. Always use system and history by default."""
    m = [{"role": "system", "content": get_sys()}]
    m.extend({"role": msg['role'], "content": msg['content']} for msg in msgs)
    if prompt:
        m.append({"role": "user", "content": prompt})

    # Call Ollama or OpenAI based on config
    if "ollama" in cfg['base_url'].lower():
        result = ollama.chat(model=cfg['model'], messages=m, think=True)['message']['content']
    else:
        result = OpenAI(api_key=cfg['api_key'], base_url=cfg['base_url']).chat.completions.create(
            model=cfg['model'], messages=m, timeout=30).choices[0].message.content
    return result

def get_repo_map():
    return REPOS