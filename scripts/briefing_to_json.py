#!/usr/bin/env python3
"""Convert high-signal-news markdown briefing to structured JSON."""
import json
import re
import sys
from pathlib import Path
from datetime import datetime


def parse_briefing(md_path: str) -> dict:
    text = Path(md_path).read_text(encoding="utf-8")
    lines = text.splitlines()

    result = {
        "title": None,
        "date": None,
        "generated_at": None,
        "meta": {},
        "categories": [],
    }

    # Extract title and date from first h1
    title_match = re.search(r"#\s+Daily Briefing\s+-\s+(\d{4}-\d{2}-\d{2})", text)
    if title_match:
        result["date"] = title_match.group(1)
        result["title"] = f"Daily Briefing - {result['date']}"

    # Fallback: High-Signal Briefing format
    if not result["date"]:
        hs_match = re.search(r"#\s+High-Signal Briefing\s+[—-]\s+(\d{4}-\d{2}-\d{2})", text)
        if hs_match:
            result["date"] = hs_match.group(1)
            result["title"] = f"High-Signal Briefing — {result['date']}"

    # Extract meta block (Daily Briefing format)
    meta_match = re.search(
        r"\*\*(\d+) stories\*\* from (\d+) sources\s*\n"
        r"•\s*🔴\s*(\d+) must-read\s*\n"
        r"•\s*🟡\s*(\d+) important\s*\n"
        r"•\s*🟢\s*(\d+) contextual\s*\n"
        r"•\s*⏱️\s*~?(.+?) read",
        text,
    )
    if meta_match:
        result["meta"] = {
            "story_count": int(meta_match.group(1)),
            "source_count": int(meta_match.group(2)),
            "must_read": int(meta_match.group(3)),
            "important": int(meta_match.group(4)),
            "contextual": int(meta_match.group(5)),
            "read_time": meta_match.group(6).strip(),
        }

    # Fallback meta block (High-Signal Briefing format)
    if not result["meta"]:
        hs_meta = re.search(
            r"\*(\d+) high-signal stories from the past week\*",
            text,
        )
        if hs_meta:
            result["meta"] = {
                "story_count": int(hs_meta.group(1)),
                "source_count": 0,
                "must_read": 0,
                "important": 0,
                "contextual": 0,
                "read_time": "",
            }

    # Extract generated timestamp if present
    gen_match = re.search(r"Generated:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC)", text)
    if gen_match:
        result["generated_at"] = gen_match.group(1)

    # Parse categories and stories
    current_category = None
    current_story = None
    i = 0
    while i < len(lines):
        line = lines[i]

        # Category header: ## 🤖 AI
        cat_match = re.match(r"^##\s+(.+)$", line)
        if cat_match and not line.startswith("## "):
            # Actually ## with space
            pass
        if re.match(r"^##\s+(.+)$", line):
            cat_name = re.match(r"^##\s+(.+)$", line).group(1).strip()
            current_category = {
                "name": cat_name,
                "emoji": "",
                "stories": [],
            }
            # Extract emoji if present
            emoji_match = re.match(r"^(\S+)\s+(.*)$", cat_name)
            if emoji_match and len(emoji_match.group(1)) <= 2:
                current_category["emoji"] = emoji_match.group(1)
                current_category["name"] = emoji_match.group(2)
            result["categories"].append(current_category)
            i += 1
            continue

        # Story header: ### 🟢 [title](url)
        story_match = re.match(
            r"^###\s+([🔴🟡🟢])\s+\[(.*?)\]\((.*?)\)", line
        )
        if story_match and current_category is not None:
            priority = story_match.group(1)
            title = story_match.group(2)
            url = story_match.group(3)
            current_story = {
                "priority": priority,
                "priority_label": {"🔴": "must-read", "🟡": "important", "🟢": "contextual"}.get(priority, "unknown"),
                "title": title,
                "url": url,
                "description": "",
                "metadata": {},
            }
            current_category["stories"].append(current_story)
            i += 1
            continue

        # Story metadata lines (stars, forks, language, watchers)
        if current_story is not None:
            meta_line = line.strip()
            if meta_line.startswith("⭐"):
                m = re.search(r"⭐\s*([\d,]+)\s*stars", meta_line)
                if m:
                    current_story["metadata"]["stars"] = int(m.group(1).replace(",", ""))
                m = re.search(r"🍴\s*([\d,]+)\s*forks", meta_line)
                if m:
                    current_story["metadata"]["forks"] = int(m.group(1).replace(",", ""))
                m = re.search(r"📝\s*(\S+)", meta_line)
                if m:
                    current_story["metadata"]["language"] = m.group(1)
                m = re.search(r"👁️\s*([\d,]+)\s*watchers", meta_line)
                if m:
                    current_story["metadata"]["watchers"] = int(m.group(1).replace(",", ""))
                i += 1
                continue
            elif meta_line.startswith("📎"):
                current_story["metadata"]["tag"] = meta_line.replace("📎", "").strip()
                i += 1
                continue
            elif meta_line == "":
                # Empty line — if next line is also a story header or category, end current story
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if re.match(r"^###\s+", next_line) or re.match(r"^##\s+", next_line) or next_line.startswith("---"):
                        current_story = None
                i += 1
                continue
            else:
                # Description text
                if current_story["description"]:
                    current_story["description"] += " " + meta_line
                else:
                    current_story["description"] = meta_line
                i += 1
                continue

        i += 1

    # Compute totals
    total_stories = sum(len(c["stories"]) for c in result["categories"])
    result["summary"] = {
        "total_stories": total_stories,
        "total_categories": len(result["categories"]),
        "must_read_stories": sum(1 for c in result["categories"] for s in c["stories"] if s["priority"] == "🔴"),
        "important_stories": sum(1 for c in result["categories"] for s in c["stories"] if s["priority"] == "🟡"),
        "contextual_stories": sum(1 for c in result["categories"] for s in c["stories"] if s["priority"] == "🟢"),
    }

    return result


def main():
    if len(sys.argv) < 2:
        # Default: find latest briefing in high-signal-news docs/
        docs_dir = Path("/home/exedev/autonomy/labs/high-signal-news/docs")
        briefings = sorted(docs_dir.glob("briefing-*.md"))
        if not briefings:
            print("No briefing files found", file=sys.stderr)
            sys.exit(1)
        md_path = briefings[-1]
    else:
        md_path = Path(sys.argv[1])

    data = parse_briefing(str(md_path))
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
