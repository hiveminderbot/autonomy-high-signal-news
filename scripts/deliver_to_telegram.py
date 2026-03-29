#!/usr/bin/env python3
"""
Generate high-signal briefing and deliver to Telegram.

This script:
1. Fetches fresh content from tier-1 sources
2. Generates the briefing
3. Sends formatted output to Telegram
4. Logs delivery status

Environment:
- TELEGRAM_BOT_TOKEN: Bot token for authentication
- TELEGRAM_CHAT_ID: Target chat ID (defaults to user's home channel)
"""

import os
import sys
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Bot
from telegram.constants import ParseMode

# Config
OUTPUT_DIR = Path(__file__).parent.parent / "output"
DB_PATH = Path(__file__).parent.parent / "news.db"

def get_env_or_fail(var_name):
    """Get environment variable or exit."""
    value = os.environ.get(var_name)
    if not value:
        print(f"ERROR: {var_name} not set")
        sys.exit(1)
    return value

def run_pipeline():
    """Run the full pipeline: fetch -> extract -> generate."""
    print("=" * 50)
    print("High-Signal News Pipeline")
    print("=" * 50)
    print()
    
    # Step 1: Fetch
    print("[1/3] Fetching fresh content...")
    result = subprocess.run(
        [sys.executable, "scripts/fetch_high_signal.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    if result.returncode != 0:
        print(f"Fetch failed: {result.stderr}")
        return None
    print(result.stdout)
    
    # Step 2: Extract (skip if no new articles to extract)
    print("[2/3] Skipping extraction (using available content)...")
    # Extraction is slow and rate-limited; we'll use titles/URLs for the briefing
    
    # Step 3: Generate
    print("[3/3] Generating briefing...")
    result = subprocess.run(
        [sys.executable, "scripts/generate_high_signal_briefing.py"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    if result.returncode != 0:
        print(f"Generation failed: {result.stderr}")
        return None
    print(result.stdout)
    
    # Find the generated file
    today = datetime.now().strftime('%Y-%m-%d')
    briefing_file = OUTPUT_DIR / f"briefing-high-signal-{today}.md"
    
    if not briefing_file.exists():
        print(f"ERROR: Briefing file not found: {briefing_file}")
        return None
    
    return briefing_file

def format_for_telegram(content: str) -> str:
    """Format markdown content for Telegram."""
    # Telegram has a 4096 char limit for messages
    # If content is too long, we'll truncate with a link to full version
    
    # Remove horizontal rules (they don't render well)
    content = content.replace('---', '')
    
    # Clean up excessive newlines
    while '\n\n\n' in content:
        content = content.replace('\n\n\n', '\n\n')
    
    return content

def truncate_for_telegram(content: str, max_len: int = 3500) -> str:
    """Truncate content to fit Telegram limits while keeping structure."""
    if len(content) <= max_len:
        return content
    
    # Find a good break point (end of a section)
    lines = content.split('\n')
    truncated = []
    current_len = 0
    
    for line in lines:
        if current_len + len(line) + 1 > max_len - 100:  # Leave room for truncation notice
            break
        truncated.append(line)
        current_len += len(line) + 1
    
    truncated.append(f"\n...\n\n*[Full briefing available in vault]*")
    return '\n'.join(truncated)

async def send_to_telegram(briefing_file: Path):
    """Send the briefing to Telegram."""
    # Get Telegram credentials
    token = get_env_or_fail('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '8557318240')  # Default to user's home channel
    
    # Read briefing
    with open(briefing_file) as f:
        content = f.read()
    
    # Format for Telegram
    formatted = format_for_telegram(content)
    message = truncate_for_telegram(formatted)
    
    # Initialize bot
    bot = Bot(token=token)
    
    # Send message
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False  # Allow link previews
        )
        print(f"✅ Delivered to Telegram ({chat_id})")
        return True
    except Exception as e:
        print(f"❌ Failed to send: {e}")
        return False

async def main():
    """Main entry point."""
    print(f"[{datetime.now().isoformat()}] Starting delivery pipeline")
    print()
    
    # Run pipeline
    briefing_file = run_pipeline()
    if not briefing_file:
        print("Pipeline failed, aborting")
        sys.exit(1)
    
    print(f"Briefing generated: {briefing_file}")
    print()
    
    # Send to Telegram
    success = await send_to_telegram(briefing_file)
    
    if success:
        print()
        print("=" * 50)
        print("Delivery complete!")
        print("=" * 50)
    else:
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
