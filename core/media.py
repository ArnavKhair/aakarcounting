import re
import subprocess
from pathlib import Path
from typing import Optional

import imageio_ffmpeg

_BROWSER_VIDEO_CODECS = {"h264"}
_BROWSER_AUDIO_CODECS = {None, "aac", "mp3"}

_FORMAT_RE = re.compile(r"Input #0,\s*(.+?),\s*from '")
_VIDEO_CODEC_RE = re.compile(r"Stream #\S+.*?: Video:\s*([^\s,(]+)")
_AUDIO_CODEC_RE = re.compile(r"Stream #\S+.*?: Audio:\s*([^\s,(]+)")


def _ffmpeg() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_video(path: Path) -> tuple[str, Optional[str], Optional[str]]:
    result = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    text = result.stderr

    format_match = _FORMAT_RE.search(text)
    if not format_match:
        raise RuntimeError("Could not read video metadata")

    video_match = _VIDEO_CODEC_RE.search(text)
    audio_match = _AUDIO_CODEC_RE.search(text)

    return (
        format_match.group(1),
        video_match.group(1) if video_match else None,
        audio_match.group(1) if audio_match else None,
    )


def is_browser_playable(fmt: str, video_codec: Optional[str],
                        audio_codec: Optional[str]) -> bool:
    return (
        "mp4" in fmt
        and video_codec in _BROWSER_VIDEO_CODECS
        and audio_codec in _BROWSER_AUDIO_CODECS
    )


def create_preview(src: Path, dest: Path, video_codec: Optional[str]) -> Path:
    """Make a browser-playable copy of the video for the line drawing screen.

    The preview only has to be scrubbable, so it is scaled down to 480p and
    encoded at a low quality with the fastest preset. An hour of CCTV is a
    long encode, and a full-resolution transcode of one would take minutes
    for a preview nobody watches closely.
    """
    cmd = [
        _ffmpeg(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(src),
        "-map", "0:v:0",
    ]
    if video_codec == "h264":
        # Already the codec browsers want; only the container needs changing.
        cmd += ["-c:v", "copy"]
    else:
        cmd += [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "30",
            # Cap the height at 480, but never upscale a smaller source.
            "-vf", "scale=-2:'min(480,ih)'",
            "-pix_fmt", "yuv420p",
        ]
    cmd += ["-an", "-movflags", "+faststart", "-y", str(dest)]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        dest.unlink(missing_ok=True)
        detail = result.stderr.strip() or "Could not convert video for preview"
        raise RuntimeError(detail)
    return dest
