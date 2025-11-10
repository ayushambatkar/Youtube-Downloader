from typing import List, Dict, Any
from pathlib import Path
import yt_dlp


class YouTubeDownloader:
    """
    Handles YouTube/playlist downloads using yt-dlp with
    audio/video mode, quality selection, and output handling.
    """

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self._base_opts = {
            "ffmpeg_location": "C:\\Users\\Ayush\\Downloads\\ffmpeg-2025-11-10-git-133a0bcb13-essentials_build\\ffmpeg-2025-11-10-git-133a0bcb13-essentials_build\\bin\\ffmpeg.exe",  
            "outtmpl": str(self.download_dir / "%(title)s.%(ext)s"),
            "noplaylist": False,
            "quiet": True,
            "merge_output_format": "mp4",
        }

    def _get_format_string(self, mode: str, quality_id: str) -> str:
        """
        Return the appropriate format selector for yt-dlp based on mode and quality.
        """
        if mode == "audio":
            # Example: use bestaudio or a specific bitrate if needed
            return "bestaudio/best"
        elif mode == "video":
            # Map quality ID to yt-dlp selectors
            quality_map = {
                "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
            }
            return quality_map.get(quality_id, "bestvideo+bestaudio/best")
        else:
            raise ValueError(f"Invalid mode: {mode}")
    
    def get_video_metadata(self, url: str) -> Dict[str, Any]:
        """Fetch video metadata without downloading."""
        opts = self._base_opts | {"skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info

    def download(self, url: str, mode: str, quality_id: str) -> Dict[str, Any]:
        """Backward-compatible download using preset quality IDs (video) or generic audio.

        Prefer `download_format` when selecting an explicit format_id from the listed formats.
        """
        format_selector = self._get_format_string(mode, quality_id)
        return self._download_with_format(url, format_selector)

    def download_format(self, url: str, format_id: str) -> Dict[str, Any]:
        """Download using an explicit yt-dlp format_id selected by the user."""
        return self._download_with_format(url, format_id)

    def _download_with_format(self, url: str, format_selector: str) -> Dict[str, Any]:
        opts = self._base_opts | {"format": format_selector}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
        return {
            "title": info.get("title"),
            "ext": info.get("ext"),
            "filepath": filename,
            "duration": info.get("duration"),
            "webpage_url": info.get("webpage_url"),
        }

    def list_formats(self, url: str) -> List[Dict[str, Any]]:
        """Return all available formats for the given URL without downloading."""
        opts = self._base_opts | {"skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info.get("formats", [])


# Example usage (for testing only)
if __name__ == "__main__":
    ytdl = YouTubeDownloader()
    info = ytdl.download(
       "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        mode="video",
        quality_id="720p"
    )
    print(info)
