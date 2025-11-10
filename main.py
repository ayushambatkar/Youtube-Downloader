from typing import List, Dict, Any
from pathlib import Path
import base64
import streamlit as st
from yt_dlp_helper import YouTubeDownloader

st.title("🎬 Ad Free YouTube Downloader")

downloader = YouTubeDownloader()

# Initialize session state
if "formats" not in st.session_state:
    st.session_state.formats = []
if "url" not in st.session_state:
    st.session_state.url = ""
if "audio_selected" not in st.session_state:
    st.session_state.audio_selected = None
if "video_selected" not in st.session_state:
    st.session_state.video_selected = None
if "is_playlist" not in st.session_state:
    st.session_state.is_playlist = False
if "playlist_summary" not in st.session_state:
    st.session_state.playlist_summary = None

def _mime_from_ext(ext: str) -> str:
    ext = (ext or "").lower()
    return {
        "mp4": "video/mp4",
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "webm": "video/webm",
        "mkv": "video/x-matroska",
        "wav": "audio/wav",
        "aac": "audio/aac",
        "opus": "audio/opus",
    }.get(ext, "application/octet-stream")

def classify_formats(formats: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    # Prefer entries with known filesize and avoid webm for simpler mp4 merging
    audio = [
        f for f in formats
        if f.get("acodec") and f.get("acodec") != "none"
        and (f.get("vcodec") in (None, "none"))
        and f.get("filesize") is not None
        and f.get("ext") != "webm"
    ]
    video = [
        f for f in formats
        if f.get("vcodec") and f.get("vcodec") != "none"
        and f.get("filesize") is not None
        and f.get("ext") != "webm"
    ]
    return {"audio": audio, "video": video}

def human_label_audio(f: Dict[str, Any]) -> str:
    abr = f.get("abr") or f.get("asr") or "?"
    ext = f.get("ext")
    fmt_id = f.get("format_id")
    size = f.get("filesize") or f.get("filesize_approx") or 0
    acodec = f.get("acodec")
    return f"{size/1024/1024:.2f} MB | .{ext}"

def human_label_video(f: Dict[str, Any]) -> str:
    height = f.get("height") or "?"
    fps = f.get("fps") or "?"
    vbr = f.get("vbr") or f.get("tbr") or "?"
    size = f.get("filesize") or f.get("filesize_approx") or 0
    quality = f.get("height")
    ext = f.get("ext")
    fmt_id = f.get("format_id")
    res = f.get("resolution") or f"{height}p"
    return f"{quality}p | {size/1024/1024:.2f} MB | .{ext}"

with st.form("fetch_form"):
    st.session_state.url = st.text_input("Enter video or playlist URL", value=st.session_state.url)
    fetch_btn = st.form_submit_button("Fetch Formats")
    if fetch_btn and st.session_state.url.strip():
        with st.spinner("Fetching formats... Please wait ⏳"):
            try:
                # First fetch metadata to detect playlist
                meta = downloader.get_video_metadata(st.session_state.url.strip())
                st.session_state.is_playlist = bool(meta.get("entries"))
                if st.session_state.is_playlist:
                    st.info(f"Playlist detected with {len(meta.get('entries', []))} videos. Use 'Analyze Playlist Sizes' below for aggregate size estimates.")
                    # For playlists we don't immediately list formats (too many calls); defer until analysis
                    st.session_state.formats = []
                else:
                    st.session_state.formats = downloader.list_formats(st.session_state.url.strip())
                    st.success(f"Found {len(st.session_state.formats)} formats")
            except Exception as e:
                st.error(f"Error fetching formats: {e}")

formats = st.session_state.formats

def aggregate_playlist_sizes(url: str) -> Dict[str, Any]:
    """Compute total sizes for common video heights and audio bitrates across a playlist.

    For each target video height (360/480/720/1080), sum per-video best stream up to that height,
    adding an audio track size if the selected video format is video-only.
    For audio bitrates (64/128/160/192/256/320 kbps), sum best audio stream up to that bitrate per video (fallback to max available if lower not found).
    """
    meta = downloader.get_video_metadata(url)
    entries = meta.get("entries", [])
    target_heights = [360, 480, 720, 1080]
    target_audio_abrs = [64, 128, 160, 192, 256, 320]
    video_totals = {h: 0 for h in target_heights}
    audio_totals = {a: 0 for a in target_audio_abrs}
    per_video_cache = []
    for idx, entry in enumerate(entries, start=1):
        vid_url = entry.get("webpage_url") or entry.get("url")
        if not vid_url:
            continue
        try:
            fmts = downloader.list_formats(vid_url)
        except Exception:
            continue
        # Separate audio/video
        audio_fmts = [f for f in fmts if f.get("acodec") and f.get("acodec") != "none" and (f.get("vcodec") in (None, "none")) and f.get("filesize")]
        video_fmts = [f for f in fmts if f.get("vcodec") and f.get("vcodec") != "none" and f.get("filesize")]
        # Sort by height ascending
        video_fmts_sorted = sorted(video_fmts, key=lambda f: (f.get("height") or 0))
        audio_fmts_sorted = sorted(audio_fmts, key=lambda f: (f.get("abr") or f.get("tbr") or 0))
        per_video_cache.append({"url": vid_url, "video_formats": len(video_fmts_sorted), "audio_formats": len(audio_fmts_sorted)})
        # Video aggregation
        for h in target_heights:
            # pick best format with height <= h else highest available
            candidates = [f for f in video_fmts_sorted if (f.get("height") or 0) <= h]
            chosen = candidates[-1] if candidates else (video_fmts_sorted[-1] if video_fmts_sorted else None)
            if not chosen:
                continue
            v_size = chosen.get("filesize") or chosen.get("filesize_approx") or 0
            # If video-only add best audio (prefer m4a) size
            if chosen.get("acodec") in (None, "none"):
                # pick bestaudio <= arbitrary high abr (we just choose highest abr, prefer m4a)
                audio_candidates = [a for a in audio_fmts_sorted if a.get("ext") == "m4a"] or audio_fmts_sorted
                if audio_candidates:
                    best_audio = audio_candidates[-1]
                    a_size = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0
                else:
                    a_size = 0
            else:
                a_size = 0
            video_totals[h] += v_size + a_size
        # Audio aggregation
        for a in target_audio_abrs:
            abr_candidates = [f for f in audio_fmts_sorted if (f.get("abr") or f.get("tbr") or 0) <= a]
            chosen_a = abr_candidates[-1] if abr_candidates else (audio_fmts_sorted[-1] if audio_fmts_sorted else None)
            if not chosen_a:
                continue
            audio_size = chosen_a.get("filesize") or chosen_a.get("filesize_approx") or 0
            audio_totals[a] += audio_size
    return {
        "video_totals_mb": {h: round(video_totals[h]/1024/1024, 2) for h in target_heights},
        "audio_totals_mb": {a: round(audio_totals[a]/1024/1024, 2) for a in target_audio_abrs},
        "entries_count": len(entries),
        "details": per_video_cache,
    }

# Playlist analysis trigger
if st.session_state.is_playlist:
    if st.button("Analyze Playlist Sizes"):
        with st.spinner("Analyzing playlist formats across all videos... This may take a while."):
            try:
                st.session_state.playlist_summary = aggregate_playlist_sizes(st.session_state.url.strip())
                st.success("Playlist size aggregation complete.")
            except Exception as e:
                st.error(f"Failed to analyze playlist: {e}")

if st.session_state.playlist_summary:
    summary = st.session_state.playlist_summary
    st.subheader("📦 Playlist Aggregate Size Estimates")
    st.caption(f"Across {summary['entries_count']} videos. Video sizes include audio when original format lacked it.")
    col_v, col_a = st.columns(2)
    with col_v:
        st.markdown("**Video (target max height)**")
        for h, mb in summary["video_totals_mb"].items():
            st.write(f"Up to {h}p: {mb} MB total")
    with col_a:
        st.markdown("**Audio (target max bitrate)**")
        for a, mb in summary["audio_totals_mb"].items():
            st.write(f"Up to {a} kbps: {mb} MB total")
    with st.expander("Per-video format counts"):
        for row in summary["details"]:
            st.write(f"{row['url']}: {row['video_formats']} video fmts, {row['audio_formats']} audio fmts")

if formats and not st.session_state.is_playlist:
    classified = classify_formats(formats)
    tabs = st.tabs(["🎵 Audio", "🎥 Video"])

    # Audio Tab
    with tabs[0]:
        audio_list = classified["audio"]
        if audio_list:
            audio_labels = [human_label_audio(f) for f in audio_list]
            default_index = 0 if st.session_state.audio_selected is None else next((i for i, f in enumerate(audio_list) if f.get("format_id") == st.session_state.audio_selected), 0)
            chosen_audio = st.radio("Select Audio Format", audio_labels, index=default_index, key="audio_radio")
            # Map back to format_id
            chosen_audio_idx = audio_labels.index(chosen_audio)
            st.session_state.audio_selected = audio_list[chosen_audio_idx].get("format_id")
            if st.button("Download Audio"):
                fmt_id = st.session_state.audio_selected
                try:
                    with st.spinner("Downloading audio..."):
                        info = downloader.download_format(st.session_state.url.strip(), fmt_id)
                    file_path = Path(info["filepath"])  # server-side temp output
                    file_name = file_path.name
                    # Read into memory so we can delete server copy
                    try:
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                    finally:
                        try:
                            file_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    st.success(f"Ready: {info['title']} ({info['ext']})")
                    mime = _mime_from_ext(info.get("ext"))
                    # Try to auto-trigger download via data URL as well
                    b64 = base64.b64encode(file_bytes).decode()
                    download_id = "audio_auto_dl"
                    # Escape braces in JS for f-string by doubling them
                    st.markdown(
                        (
                            f'<a id="{download_id}" href="data:{mime};base64,{b64}" download="{file_name}" style="display:none;">download</a>'
                            f'<script>setTimeout(function(){{document.getElementById("{download_id}")?.click();}}, 50);</script>'
                        ),
                        unsafe_allow_html=True,
                    )
                    # Fallback clickable button
                    st.download_button(
                        label="Download file",
                        data=file_bytes,
                        file_name=file_name,
                        mime=mime
                    )
                except Exception as e:
                    st.error(f"Audio download failed: {e}")
        else:
            st.info("No standalone audio formats found.")

    # Video Tab
    with tabs[1]:
        video_list = classified["video"]
        if video_list:
            video_labels = [human_label_video(f) for f in video_list]
            default_index = 0 if st.session_state.video_selected is None else next((i for i, f in enumerate(video_list) if f.get("format_id") == st.session_state.video_selected), 0)
            chosen_video = st.radio("Select Video Format", video_labels, index=default_index, key="video_radio")
            chosen_video_idx = video_labels.index(chosen_video)
            selected_video = video_list[chosen_video_idx]
            st.session_state.video_selected = selected_video.get("format_id")
            if st.button("Download Video"):
                fmt_id = st.session_state.video_selected
                try:
                    with st.spinner("Downloading video..."):
                        # If the selected format is video-only, merge with bestaudio (prefer m4a for mp4 compatibility)
                        if (selected_video.get("acodec") in (None, "none")):
                            selector = f"{fmt_id}+bestaudio[ext=m4a]/bestaudio"
                        else:
                            selector = fmt_id
                        info = downloader.download_format(st.session_state.url.strip(), selector)
                    file_path = Path(info["filepath"])  # server-side temp output
                    file_name = file_path.name
                    # Read into memory so we can delete server copy
                    try:
                        with open(file_path, "rb") as f:
                            file_bytes = f.read()
                    finally:
                        try:
                            file_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    st.success(f"Ready: {info['title']} ({info['ext']})")
                    mime = _mime_from_ext(info.get("ext"))
                    b64 = base64.b64encode(file_bytes).decode()
                    download_id = "video_auto_dl"
                    st.markdown(
                        (
                            f'<a id="{download_id}" href="data:{mime};base64,{b64}" download="{file_name}" style="display:none;">download</a>'
                            f'<script>setTimeout(function(){{document.getElementById("{download_id}")?.click();}}, 50);</script>'
                        ),
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        label="Download file",
                        data=file_bytes,
                        file_name=file_name,
                        mime=mime
                    )
                except Exception as e:
                    st.error(f"Video download failed: {e}")
        else:
            st.info("No video formats found.")

else:
    st.info("Enter a URL and click 'Fetch Formats' to list available download options.")
