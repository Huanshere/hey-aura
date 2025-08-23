import yaml
import re
from pathlib import Path
from openai import OpenAI

_config = None
_client = None
_cache = {}

def _load_config():
    global _config, _client
    if _config is not None:
        return
    
    with open("config.yaml", 'r', encoding='utf-8') as f:
        _config = yaml.safe_load(f)
    
    dictation_config = _config.get("dictation_rewrite", {})
    enabled = dictation_config.get("enabled", False)
    
    if enabled:
        llm_config = _config.get("llm", {})
        api_key = llm_config.get("api_key")
        base_url = llm_config.get("base_url")
        if api_key and base_url:
            _client = OpenAI(api_key=api_key, base_url=base_url)

def rewrite_text(text: str, mode: str = "dictation") -> str:
    _load_config()
    
    dictation_config = _config.get("dictation_rewrite", {})
    enabled = dictation_config.get("enabled", False)
    
    if not enabled or not _client or mode != "dictation":
        return text
    
    cache_key = f"{mode}:{text}"
    if cache_key in _cache:
        return _cache[cache_key]
    
    try:
        prompt_path = Path(__file__).parent / "prompts" / "hotword_rewrite.md"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()

        hotwords = dictation_config.get("hotwords", [])
        hotwords_str = ", ".join(hotwords)
        prompt = prompt_template.format(hotwords=hotwords_str, user_input=text)
        
        llm_config = _config.get("llm", {})
        model = llm_config.get("model", "gpt-3.5-turbo")
        
        response = _client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            timeout=10
        )
        
        raw_result = response.choices[0].message.content.strip()
        
        compare_match = re.search(r'<compare>(.*?)</compare>', raw_result, re.DOTALL)
        if compare_match:
            think_content = compare_match.group(1).strip()
            print(f"→ think: {think_content}")
        
        correct_match = re.search(r'<correct>(.*?)</correct>', raw_result, re.DOTALL)
        result = correct_match.group(1).strip() if correct_match else raw_result
        
        _cache[cache_key] = result
        if len(_cache) > 100:
            keys_to_remove = list(_cache.keys())[:50]
            for key in keys_to_remove:
                del _cache[key]
        
        return result
        
    except Exception as e:
        print(f"LLM rewrite error: {e}")
        return text