# 自定义Command Mode工具开发指南

想要添加自己的语音命令工具？只需三步：

## 第一步：创建工具函数
在 `core/tools/` 目录下创建您的工具文件：

```python
# core/tools/my_command.py
def my_custom_command(param1: str, param2: str = None):
    """您的自定义工具逻辑"""
    # 实现您的功能
    return result
```

## 第二步：定义工具参数说明
编辑 `core/prompts/command_mode_sys_prompt.md` 的 `<Command>` 栏，添加工具的调用说明：

```python
def my_custom_command(param1: str, param2: str = None):
    # 工具描述：说明这个工具的用途和使用场景
    # 参数说明：
    # - param1: 第一个参数的作用
    # - param2: 可选参数的作用
    # 
    # 使用示例：
    # <my_custom_command>param1_value|param2_value</my_custom_command>
```

## 第三步：注册工具执行逻辑
在 `core/command_mode.py` 中添加工具的处理逻辑：

1. 导入您的工具函数并注册：
```python
from core.tools.my_command import my_custom_command
...
CMDS = [<Exsisting cmds>, my_custom_command]
```

2. 在 `command_mode()` 函数的工具处理部分添加：
```python
elif cmd == 'my_custom_command':
    # 解析参数（使用 | 分隔）
    parts = [p.strip() for p in arg.split('|')]
    param1 = parts[0] if len(parts) > 0 else ""
    param2 = parts[1] if len(parts) > 1 else None
    
    # 调用您的工具
    result = my_custom_command(param1, param2)
    return print(f"→ Command executed: {result}")
```

## 示例：添加一个简单的笔记工具

1. 创建 `core/tools/note.py`：
```python
def save_note(content: str):
    with open("notes.txt", "a", encoding="utf-8") as f:
        f.write(f"{content}\n")
    return
```

2. 在 prompt 的 `<Command>` 中添加说明：
```md
def save_note(content: str):
    # 保存语音笔记到文件
    # Usage: <save_note>note content</save_note>
```

3. 在 command_mode.py 中添加处理：
```python
elif cmd == 'save_note':
    save_note(arg)
    return print(f"→ Note saved")
```

现在您就可以通过语音说"保存笔记：今天天气很好"来使用这个功能了！