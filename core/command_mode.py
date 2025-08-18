import re
import yaml
from core.i18n import _
from core.get_active_window import get_active_window
from core.tools import ask_web_llm
from core.tools.email import respond_to_email, get_emails
from core.llm_context import load_hist, add_msg, call_llm, get_repo_map

cfg = yaml.safe_load(open('config.yaml', encoding='utf-8'))
ask = getattr(ask_web_llm, cfg.get('web_llm', 'chatgpt'), ask_web_llm.chatgpt)

TOOLS = ['get_emails']
CMDS = ['say', 'ask', 'claude_code', 'respond_to_email']

def parse(text):
    return [(m[0].strip(), m[1].strip()) for m in re.findall(r"<(\w+)>(.*?)</\1>", text, re.DOTALL)]

def parse_think(text):
    match = re.search(r"<think>(.*?)</think>", text, re.DOTALL)
    return match.group(1).strip() if match else None

def exec_tool(name, args):
    return get_emails() if name == 'get_emails' else print(f"→ {_('Unknown tool')}: {name}")

def exec_cmd(cmd, args):
    if cmd == 'say':
        print(f"→ Aura: {args}")
        return True
    elif cmd == 'ask':
        ask(args)
        return True
    elif cmd == 'claude_code':
        parts = [p.strip() for p in args.split('|')]
        proj, txt = parts[0] if parts else "", parts[1] if len(parts) > 1 else None
        
        if not proj:
            from core.tools.claude_code import execute_claude_in_current_cursor as exec_cursor
            ok = exec_cursor(txt)
            print(f"→ {_('Executing in current Cursor window' if ok else 'Current window is not Cursor, cannot execute')}: {txt}" if ok else "")
            return ok
        
        repo = get_repo_map()
        if proj not in repo:
            print(f"→ {_('Repo')} '{proj}' {_('not found')}. {_('Available')}: {', '.join(repo.keys()) or _('None')}")
            return False
        
        try:
            from core.tools.claude_code import open_cursor_with_claude
            open_cursor_with_claude(repo[proj], txt)
            print(f"→ {_('Opening project')} {proj}" + (f" {_('and input')}: {txt}" if txt else ""))
            return True
        except Exception as e:
            print(f"→ {_('Open failed')}: {e}")
            return False
    elif cmd == 'respond_to_email':
        parts = [p.strip() for p in args.split('|')]
        if len(parts) >= 2:
            respond_to_email(parts[0], '|'.join(parts[1:]))
            print(f"→ {_('Email responded')}: {'|'.join(parts[1:])}")
            return True
        print(f"→ {_('Invalid send_email format')}: {args}")
        return False
    print(f"→ {_('Unknown command')}: {cmd}")
    return False

def command_mode(prompt):
    load_hist()
    win = get_active_window()
    print(f"→ <{cfg['llm']['model']}>: {prompt[:20]}{'...' if len(prompt) > 20 else ''} [{_('Current Window')}: {win}]")
    add_msg('user', prompt)

    for retry in range(2):
        resp = call_llm().strip()
        print(f"→ {_('LLM Raw Response')}: {repr(resp)}")

        # Extract and print think content
        think_content = parse_think(resp)
        if think_content:
            print(f"→ {_('Thinking')}: {think_content}")

        calls = parse(resp)
        if not calls:
            print(f"→ {_('Format error, retry')} {retry+1}/2")
            continue

        # Separate tool calls and command calls
        tools = [(n, a) for n, a in calls if n in TOOLS][:3]
        cmds = [(n, a) for n, a in calls if n in CMDS]

        tool_exec = False
        for t_name, t_args in tools:
            print(f"→ {_('Executing tool')}: {t_name}")
            res = exec_tool(t_name, t_args)
            if res is not None:
                add_msg('user', f"Tool result from {t_name}: {res}")
                tool_exec = True

        if tool_exec:
            # If tool was executed, call LLM again to get next command
            resp = call_llm().strip()
            print(f"→ {_('LLM Response after tools')}: {repr(resp)}")
            
            # Extract and print think content after tools
            think_content = parse_think(resp)
            if think_content:
                print(f"→ {_('Thinking')}: {think_content}")
            
            cmds = [(n, a) for n, a in parse(resp) if n in CMDS]

        if not cmds:
            print(f"→ {_('Error: No command found in response')}, {_('retry')} {retry+1}/2")
            continue

        if len(cmds) > 1:
            print(f"→ {_('Error: Multiple commands found, using first one')}")

        c_name, c_args = cmds[0]
        print(f"→ {_('Executing command')}: {c_name}")

        # Execute the main command, return if successful
        if exec_cmd(c_name, c_args):
            add_msg('assistant', resp)
            return
        print(f"→ {_('Command execution failed')}, {_('retry')} {retry+1}/2")

    # All retries failed
    print(f"→ {_('Multiple attempts failed')}")

if __name__ == '__main__':
    command_mode("What's going on with my emails?")