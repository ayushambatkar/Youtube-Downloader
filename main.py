import streamlit as st
import yt_dlp
import os
import re

st.title("🎬 YouTube Downloader with Progress")

url = st.text_input("Enter YouTube video URL")

quality = st.selectbox(
    "Select quality:",
    ["Best video (MP4)", "Medium video (MP4)", "Audio only (MP3)"]
)

if st.button("Download"):
    if not url:
        st.error("Please enter a URL.")
    else:
        st.info("Preparing download...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress_hook(d):
            if d["status"] == "downloading":
                percent_raw = d.get("_percent_str", "0.0%")
                percent_clean = re.sub(r"\x1B\[[0-9;]*[A-Za-z]", "", percent_raw)  # strip color codes
                percent = re.sub(r"[^\d.]", "", percent_clean) or "0.0"
                progress = float(percent) / 100
                progress_bar.progress(progress)
                # status_text.text(
                #     f"Downloading: {percent} ({d['_speed_str']} at {d['_eta_str']} ETA)"
                # )
            elif d["status"] == "finished":
                progress_bar.progress(1.0)
                status_text.text("Processing...")

        # Choose formats
        if quality == "Best video (MP4)":
            ydl_opts = {
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "quiet": True,
                "outtmpl": "download.%(ext)s",
                "progress_hooks": [progress_hook],
            }
        elif quality == "Medium video (MP4)":
            ydl_opts = {
                "format": "bv*[height<=720]+ba/b[height<=720]",
                "merge_output_format": "mp4",
                "quiet": True,
                "outtmpl": "download.%(ext)s",
                "progress_hooks": [progress_hook],
            }
        else:  # MP3
            ydl_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "outtmpl": "download.%(ext)s",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "progress_hooks": [progress_hook],
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_ext = "mp3" if quality == "Audio only (MP3)" else "mp4"
                file_name = f"download.{file_ext}"

            with open(file_name, "rb") as f:
                data = f.read()

            st.success("✅ Download complete!")
            st.download_button(
                label="Click here to save to your device",
                data=data,
                file_name=f"{info.get('title', 'video')}.{file_ext}",
                mime="audio/mpeg" if file_ext == "mp3" else "video/mp4",
            )

        except Exception as e:
            st.error(f"❌ Error: {e}")

        finally:
            # cleanup
            for ext in ("mp4", "mp3"):
                if os.path.exists(f"download.{ext}"):
                    os.remove(f"download.{ext}")

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: gray;'>"
    "Afloatwont "
    "| " \
    "2025"
    "</p>",
    unsafe_allow_html=True
)