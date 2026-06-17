#!/usr/bin/env python3
"""
make_video.py — Single video production CLI.

Usage:
  python make_video.py \
    --account account_A \
    --video input/videos/素材.mp4 \
    --bgm input/bgm/music.mp3 \
    --info "・副業で月10万稼ぐ方法\n・初期費用0円" \
    --topic 副業 \
    --funnel fukugyo_lp
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml

# Ensure buzz_system root is on sys.path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _generate_video_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _make_kenburns_clip(image_path: Path, duration: float):
    """単一画像にランダムなケンバーンズ効果（ズームイン or アウト）を適用"""
    import random
    import numpy as np
    from PIL import Image as PILImage
    from moviepy.editor import ImageClip, VideoClip

    base = ImageClip(str(image_path)).set_duration(duration)
    W, H = base.size
    zoom_in = random.choice([True, False])
    s0, s1 = (1.0, 1.12) if zoom_in else (1.12, 1.0)

    def make_frame(t):
        scale = s0 + (s1 - s0) * (t / duration)
        img = PILImage.fromarray(base.get_frame(t)).resize(
            (int(W * scale), int(H * scale)), PILImage.LANCZOS)
        nw, nh = img.size
        left, top = (nw - W) // 2, (nh - H) // 2
        return np.array(img.crop((left, top, left + W, top + H)))

    c = VideoClip(make_frame, duration=duration)
    c.size = (W, H)
    return c


def _print_summary(video_id, account, topic, funnel, cta_type, hook_text, output_path, utm_url=None):
    """Print a production summary to stdout."""
    click.echo("")
    click.echo("=" * 60)
    click.echo("  動画制作完了")
    click.echo("=" * 60)
    click.echo(f"  動画ID      : {video_id}")
    click.echo(f"  アカウント   : {account}")
    click.echo(f"  トピック     : {topic}")
    click.echo(f"  ファネル     : {funnel}")
    click.echo(f"  CTA種類     : {cta_type}")
    click.echo(f"  フック文     : {hook_text[:40]}{'...' if len(hook_text) > 40 else ''}")
    click.echo(f"  出力先       : {output_path}")
    if utm_url:
        click.echo("")
        click.echo(f"  UTM URL      :")
        click.echo(f"  {utm_url}")
        click.echo("")
        click.echo("  ⚠ プロフィールのリンクをこのURLに更新してください")
    click.echo("=" * 60)
    click.echo("")


@click.command()
@click.option("--account", required=True, help="Account identifier (e.g. account_A)")
@click.option("--video", required=True, type=click.Path(), help="Path to input video file")
@click.option("--bgm", default=None, type=click.Path(), help="Path to BGM audio file")
@click.option("--info", required=True, help="Bullet points for video body (newline or ・ separated)")
@click.option("--topic", required=True, help="Video topic keyword (e.g. 副業)")
@click.option("--funnel", default=None, help="Funnel identifier (defaults to account's default_funnel)")
@click.option("--platform", default="tiktok", help="Publishing platform for UTM (default: tiktok)")
@click.option("--dry-run", is_flag=True, default=False, help="Generate metadata without processing video")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose logging")
def main(account, video, bgm, info, topic, funnel, platform, dry_run, verbose):
    """Generate a short video for TikTok/Reels/Shorts with text overlays and BGM."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, force=True)

    click.echo(f"[make_video] 開始 account={account}, topic={topic}")

    # ── ① Load configs ──────────────────────────────────────────────────────
    accounts_cfg = _load_yaml(BASE_DIR / "config" / "accounts.yaml")
    funnels_cfg = _load_yaml(BASE_DIR / "config" / "funnels.yaml")

    if account not in accounts_cfg.get("accounts", {}):
        click.echo(f"エラー: アカウント '{account}' がconfig/accounts.yamlに見つかりません", err=True)
        click.echo(f"利用可能なアカウント: {', '.join(accounts_cfg.get('accounts', {}).keys())}", err=True)
        sys.exit(1)

    account_cfg = accounts_cfg["accounts"][account]
    funnel = funnel or account_cfg.get("default_funnel")

    if funnel not in funnels_cfg.get("funnels", {}):
        click.echo(f"エラー: ファネル '{funnel}' がconfig/funnels.yamlに見つかりません", err=True)
        sys.exit(1)

    funnel_cfg = funnels_cfg["funnels"][funnel]
    hook_tone = account_cfg.get("hook_tone", "friendly")
    color_filter = account_cfg.get("color_filter", "clean")
    sfx_volume = float(account_cfg.get("sfx_volume", -15))

    # ── Validate input video ─────────────────────────────────────────────────
    video_path = Path(video)
    if not video_path.exists():
        click.echo(f"エラー: 入力動画ファイルが見つかりません: {video_path}", err=True)
        sys.exit(1)

    bgm_path = Path(bgm) if bgm else None
    if bgm_path and not bgm_path.exists():
        click.echo(f"警告: BGMファイルが見つかりません: {bgm_path} — スキップします", err=True)
        bgm_path = None

    # ── ② Determine CTA type ─────────────────────────────────────────────────
    from modules.scheduler import VideoScheduler
    scheduler = VideoScheduler()
    cta_type = scheduler.determine_cta_type(account)
    click.echo(f"[make_video] CTA種類: {cta_type}")

    # ── ③ Generate hook text ──────────────────────────────────────────────────
    from modules.hook_generator import generate_hook, generate_text_points, generate_cta

    knowledge_path = BASE_DIR / "knowledge" / account
    hook_text = generate_hook(
        account_name=account,
        topic=topic,
        hook_tone=hook_tone,
        knowledge_base_path=knowledge_path,
    )
    click.echo(f"[make_video] フック: {hook_text}")

    # ── Parse body points ─────────────────────────────────────────────────────
    body_points = generate_text_points(info)
    click.echo(f"[make_video] ボディポイント数: {len(body_points)}")

    # ── Generate CTA text ─────────────────────────────────────────────────────
    cta_text = generate_cta(account, funnels_cfg, cta_type)

    # ── Generate video ID and output path ────────────────────────────────────
    video_id = _generate_video_id()
    output_dir = BASE_DIR / "output" / account
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_id}.mp4"

    # ── ⑫ Generate UTM URL (only for conversion CTA) ─────────────────────────
    utm_url = None
    if cta_type == "conversion":
        from modules.utm_builder import build_utm_url, generate_bio_link_note
        base_url = funnel_cfg.get("base_url", f"https://example.com/{funnel}")
        utm_url = build_utm_url(
            base_url=base_url,
            platform=platform,
            video_id=video_id,
            topic=topic,
            funnel_name=funnel,
        )
        generate_bio_link_note(account, video_id, utm_url, topic, BASE_DIR)

    # ── Metadata dict ────────────────────────────────────────────────────────
    metadata = {
        "video_id": video_id,
        "account": account,
        "topic": topic,
        "funnel": funnel,
        "platform": platform,
        "cta_type": cta_type,
        "hook_text": hook_text,
        "body_points": body_points,
        "cta_text": cta_text,
        "utm_url": utm_url,
        "hook_tone": hook_tone,
        "color_filter": color_filter,
        "source_video": str(video_path),
        "bgm": str(bgm_path) if bgm_path else None,
        "created_at": datetime.now().isoformat(),
    }

    if dry_run:
        import json
        click.echo("\n[dry-run] メタデータのみ生成 (動画処理はスキップ)")
        click.echo(json.dumps(metadata, ensure_ascii=False, indent=2))
        _print_summary(video_id, account, topic, funnel, cta_type, hook_text, output_path, utm_url)
        return

    # ── ④ Crop vertical → ⑤ Cut → ⑥ Color filter → ⑦-⑪ Overlays+BGM+SFX ──
    try:
        from moviepy.editor import VideoFileClip, CompositeVideoClip
        from modules.video_editor import crop_vertical, cut_to_duration, apply_color_filter, add_bgm, export_video
        from modules.text_overlay import create_hook_overlay, create_body_overlay, create_cta_overlay
        from modules.sfx_engine import add_sfx, get_default_sfx_events

        click.echo("[make_video] 動画読み込み中...")
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        if video_path.suffix.lower() in image_exts:
            import random as _rnd
            click.echo("[make_video] 画像ファイルを検出 → 4〜5枚のケンバーンズ連結動画に変換")

            # 同ディレクトリの全画像を収集
            dummy_names = {"dummy.mp4", "dummy.mp3"}
            all_imgs = []
            for _ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                all_imgs.extend(video_path.parent.glob(f"*{_ext}"))
                all_imgs.extend(video_path.parent.glob(f"*{_ext.upper()}"))
            all_imgs = sorted({
                p for p in all_imgs
                if p.name not in dummy_names and p.stat().st_size > 0
            })
            if not all_imgs:
                all_imgs = [video_path]

            if len(all_imgs) >= 4:
                n = _rnd.randint(4, min(5, len(all_imgs)))
                selected = _rnd.sample(all_imgs, n)
            else:
                selected = all_imgs

            dur_each = 15.0 / len(selected)
            click.echo(f"[make_video] {len(selected)}枚使用 (各{dur_each:.1f}秒): " +
                       ", ".join(p.name for p in selected))

            from moviepy.editor import concatenate_videoclips
            kb_clips = [_make_kenburns_clip(img, dur_each) for img in selected]
            clip = concatenate_videoclips(kb_clips, method="compose")
        else:
            clip = VideoFileClip(str(video_path))

        # ④ Crop to 9:16
        click.echo("[make_video] ④ 縦型クロップ (9:16)...")
        clip = crop_vertical(clip)

        # ⑤ Cut to 15 seconds
        click.echo("[make_video] ⑤ 15秒カット...")
        clip = cut_to_duration(clip, max_seconds=15)
        video_duration = clip.duration

        # ⑥ Apply color filter
        click.echo(f"[make_video] ⑥ カラーフィルター適用: {color_filter}")
        clip = apply_color_filter(clip, color_filter)

        # ⑦ Hook overlay (0–3s)
        click.echo("[make_video] ⑦ フックテキストオーバーレイ...")
        solution = body_points[0] if body_points else None
        hook_clip = create_hook_overlay(hook_text, duration=3.0, font_size=72,
                                        solution_text=solution, topic=topic,
                                        points_count=len(body_points))

        # ⑧ Body text overlay
        click.echo("[make_video] ⑧ ボディテキストオーバーレイ...")
        body_clips = create_body_overlay(body_points, start_time=3.0, font_size=52, video_duration=video_duration)

        # ⑨ CTA overlay
        click.echo("[make_video] ⑨ CTAオーバーレイ...")
        cta_clip = create_cta_overlay(cta_text, start_offset_from_end=3.0, font_size=60, video_duration=video_duration)

        # Composite all overlays
        overlay_clips = [clip]
        if hook_clip:
            overlay_clips.append(hook_clip)
        overlay_clips.extend(body_clips)
        if cta_clip:
            overlay_clips.append(cta_clip)

        if len(overlay_clips) > 1:
            final_clip = CompositeVideoClip(overlay_clips, size=clip.size)
        else:
            final_clip = clip

        # ⑩ Add BGM
        if bgm_path:
            click.echo("[make_video] ⑩ BGM追加...")
            final_clip = add_bgm(final_clip, str(bgm_path), volume_db=-15)

        # ⑪ Add SFX
        click.echo("[make_video] ⑪ SFX追加...")
        sfx_events = get_default_sfx_events(video_duration)
        final_clip = add_sfx(final_clip, events=sfx_events, default_volume_db=sfx_volume)

        # ⑬ Export
        click.echo(f"[make_video] ⑬ 動画エクスポート → {output_path}")
        export_video(final_clip, str(output_path), metadata)

        # Cleanup moviepy objects
        final_clip.close()
        clip.close()

    except ImportError as e:
        click.echo(f"警告: moviepy/PIL が見つかりません。メタデータのみ保存します。\n  {e}", err=True)
        # Save metadata only
        import json
        meta_path = output_dir / f"{video_id}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        click.echo(f"[make_video] メタデータ保存: {meta_path}")
    except Exception as e:
        click.echo(f"エラー: 動画処理に失敗しました: {e}", err=True)
        logger.exception("Video processing failed")
        sys.exit(1)

    # ── ⑮ Print summary ───────────────────────────────────────────────────────
    _print_summary(video_id, account, topic, funnel, cta_type, hook_text, output_path, utm_url)


if __name__ == "__main__":
    main()
