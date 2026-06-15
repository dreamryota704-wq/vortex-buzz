"""
UTM URL builder and bio link note generator.
"""
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from datetime import datetime
from pathlib import Path


def build_utm_url(base_url: str, platform: str, video_id: str, topic: str, funnel_name: str) -> str:
    """
    Build a URL with UTM tracking parameters appended.

    Args:
        base_url: The landing page base URL (e.g. https://example.com/lp)
        platform: Traffic source platform (tiktok, youtube, instagram, etc.)
        video_id: Unique video identifier (YYYYMMDD_HHMMSS format)
        topic: Video topic / keyword (e.g. 副業, 退職代行)
        funnel_name: Funnel identifier from funnels.yaml (e.g. fukugyo_lp)

    Returns:
        Full URL string with UTM parameters
    """
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query, keep_blank_values=True)

    utm_params = {
        "utm_source": platform,
        "utm_medium": "short_video",
        "utm_campaign": funnel_name,
        "utm_content": video_id,
        "utm_term": topic,
    }

    # Merge existing params with UTM params (UTM takes precedence)
    merged = {}
    for k, v in existing_params.items():
        merged[k] = v[0] if len(v) == 1 else v
    merged.update(utm_params)

    query_string = urlencode(merged, doseq=True)
    new_parsed = parsed._replace(query=query_string)
    return urlunparse(new_parsed)


def generate_bio_link_note(
    account: str,
    video_id: str,
    utm_url: str,
    topic: str,
    base_dir: Path = None,
) -> Path:
    """
    Append a bio link update note to output/{account}/bio_links.txt.

    Args:
        account: Account identifier (e.g. account_A)
        video_id: Video identifier
        utm_url: Full UTM-tagged URL
        topic: Video topic
        base_dir: Base directory of buzz_system (defaults to this file's parent's parent)

    Returns:
        Path to the bio_links.txt file
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent

    output_dir = base_dir / "output" / account
    output_dir.mkdir(parents=True, exist_ok=True)

    bio_links_file = output_dir / "bio_links.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    note = (
        f"[{timestamp}] 動画ID: {video_id}\n"
        f"  設定するURL: {utm_url}\n"
        f"  トピック: {topic}\n"
        f"{'-' * 60}\n"
    )

    with open(bio_links_file, "a", encoding="utf-8") as f:
        f.write(note)

    return bio_links_file
