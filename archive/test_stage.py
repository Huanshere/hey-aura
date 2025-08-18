import asyncio
import os
from dotenv import load_dotenv

from stagehand import StagehandConfig, Stagehand

# 载入 .env
load_dotenv()

# ==== OpenRouter: 使用 OpenAI 兼容接口 ====
# 多放一个兼容变量名，避免底层 SDK 差异
os.environ.setdefault("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("OPENAI_API_BASE", "https://openrouter.ai/api/v1")

# OpenRouter API Key（放在 .env：OPENROUTER_API_KEY=...）
OPENROUTER_API_KEY = "your key"


async def main():
    # 使用本地模式；model_name 选择一个在 OpenRouter 上可用的、便宜且响应快的模型
    # 注意：本示例操作纯靠浏览器 API，不依赖 LLM；但我们把 LLM 配好以便你后续扩展。
    config = StagehandConfig(
        env="LOCAL",
        model_name="openai/gpt-4.1",     # 你也可以换成 openrouter 支持的其他模型，如 anthropic/claude-3.5-sonnet
        model_api_key=OPENROUTER_API_KEY,
    )

    stagehand = Stagehand(config)

    try:
        print("\nInitializing 🤘 Stagehand (LOCAL mode)...")
        await stagehand.init()

        page = stagehand.page

        # 1) 打开 Google
        await page.goto("https://www.google.com", wait_until="domcontentloaded")

        # 2)（若出现）尽量接受 Cookie 弹窗，忽略失败
        for sel in [
            'button:has-text("I agree")',
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button:has-text("接受全部")',
            'button:has-text("同意")',
        ]:
            try:
                await page.click(sel, timeout=2000)
                break
            except Exception:
                pass

        # 3) 定位搜索框（Google 新旧 UI 可能是 textarea[name="q"] 或 input[name="q"]）
        search_box = page.locator('textarea[name="q"], input[name="q"]').first
        await search_box.wait_for(timeout=10000)

        # 4) 输入关键词并搜索
        await search_box.fill("bitcoin price")
        await search_box.press("Enter")

        # 5) 等待搜索结果加载
        await page.wait_for_load_state("networkidle")

        print("✅ 已在 Google 搜索框输入并执行搜索：bitcoin price")

        # （可选）打印当前页面标题，方便你确认
        print("Page title:", await page.title())

    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        print("\nClosing 🤘 Stagehand...")
        await stagehand.close()


if __name__ == "__main__":
    asyncio.run(main())
