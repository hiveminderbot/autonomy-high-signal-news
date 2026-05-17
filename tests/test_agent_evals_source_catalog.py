import json
from pathlib import Path


CATALOG_PATH = Path(__file__).resolve().parents[1] / "sources" / "sources-ai.json"


def test_agent_evals_sources_are_integrated_with_validated_feed_urls():
    catalog = json.loads(CATALOG_PATH.read_text())
    feeds = {source["name"]: source for source in catalog["rss_feeds"]}

    assert catalog["metadata"]["source_count"] == 15

    metr = feeds["METR Updates"]
    assert metr["url"] == "https://metr.substack.com/feed"
    assert metr["type"] == "rss"
    assert metr["quality_score"] >= 9
    assert "agent evaluation" in metr["focus"].lower()
    assert "invalid https://metr.org/blog/rss.xml" in metr["notes"]

    epoch = feeds["Epoch AI Brief"]
    assert epoch["url"] == "https://epochai.substack.com/feed"
    assert epoch["type"] == "rss"
    assert epoch["quality_score"] >= 9
    assert "benchmark" in epoch["focus"].lower()
    assert "invalid https://epoch.ai/blog/rss.xml" in epoch["notes"]
