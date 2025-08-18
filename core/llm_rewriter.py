import yaml
import re
from pathlib import Path
from openai import OpenAI


class LLMRewriter:
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # Use dictation_rewrite config (only applies to dictation mode)
        dictation_config = self.config.get("dictation_rewrite", {})
        self.enabled = dictation_config.get("enabled", False)
        self.hotwords = dictation_config.get("hotwords", [])
        self.client = None
        self.cache = {}
        
        # Use shared LLM config
        if self.enabled:
            llm_config = self.config.get("llm", {})
            api_key = llm_config.get("api_key")
            base_url = llm_config.get("base_url")
            if api_key and base_url:
                self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = llm_config.get("model", "gpt-3.5-turbo")
    
    def rewrite(self, text: str, mode: str = "dictation") -> str:
        """Rewrite text using LLM to fix hotwords and remove disfluencies."""
        if not self.enabled or not self.client:
            return text
        
        # Only rewrite in dictation mode (command mode doesn't need rewriting)
        if mode != "dictation":
            return text
        
        # Check cache
        cache_key = f"{mode}:{text}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Load prompt template
            prompt_path = Path(__file__).parent.parent / "core" / "prompts" / "hotword_rewrite.md"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()

            # Format prompt
            hotwords_str = ", ".join(self.hotwords)
            prompt = prompt_template.format(
                hotwords=hotwords_str,
                user_input=text
            )
            
            # Call LLM with default timeout of 10 seconds
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                timeout=10
            )
            
            raw_result = response.choices[0].message.content.strip()
            
            # Extract and print content from <compare> tags
            compare_match = re.search(r'<compare>(.*?)</compare>', raw_result, re.DOTALL)
            if compare_match:
                think_content = compare_match.group(1).strip()
                print(f"→ think: {think_content}")
            
            # Extract content from <correct> tags
            correct_match = re.search(r'<correct>(.*?)</correct>', raw_result, re.DOTALL)
            result = correct_match.group(1).strip() if correct_match else raw_result
            
            # Cache result (limit cache size)
            self.cache[cache_key] = result
            if len(self.cache) > 100:
                # Remove half of the cache when it gets too large
                keys_to_remove = list(self.cache.keys())[:50]
                for key in keys_to_remove:
                    del self.cache[key]
            
            return result
            
        except Exception as e:
            print(f"LLM rewrite error: {e}")
            return text  # Return original on error


# Singleton instance
_rewriter_instance = None

def get_rewriter() -> LLMRewriter:
    """Get or create the singleton rewriter instance."""
    global _rewriter_instance
    if _rewriter_instance is None:
        _rewriter_instance = LLMRewriter()
    return _rewriter_instance