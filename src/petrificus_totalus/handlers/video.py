"""CDR handler for video containers: MP4/MOV, Matroska (MKV), AVI, WebM.

Disarms by fully decoding every video, audio, and text-based subtitle stream
and re-encoding it through a lossless intermediate, then decoding back into
the original container and codecs.

Streams that are neither video, audio, nor a text-based subtitle codec (data
streams, attachments, image-based subtitles such as PGS/VobSub/DVB) are
logged and dropped. Container-level metadata and chapters are dropped as well.
"""

import logging
from pathlib import Path

import ffmpeg

from .._registry import detect_mime_type, register_handler

logger = logging.getLogger("petrificus-totalus")

# Maps the sniffed MIME type to the ffmpeg muxer name used to write the
# final output back in the original container format.
_CONTAINER_MUXERS = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/x-matroska": "matroska",
    "video/x-msvideo": "avi",
    "video/webm": "webm",
}

# ffprobe codec_name -> ffmpeg encoder name, for codecs where they differ.
# Codecs not listed here are assumed to have an encoder of the same name.
_VIDEO_ENCODERS = {
    "h264": "libx264",
    "hevc": "libx265",
    "vp8": "libvpx",
    "vp9": "libvpx-vp9",
}
# Used only when the source stream doesn't report its own bitrate to reuse.
_FALLBACK_VIDEO_BIT_RATE = "2M"

_AUDIO_ENCODERS = {
    "mp3": "libmp3lame",
    "vorbis": "libvorbis",
    "opus": "libopus",
}
_LOSSLESS_AUDIO_ENCODERS = {"flac", "alac", "wavpack"}
# Used only when the source stream doesn't report its own bitrate to reuse.
# Kept under libopus's 256kbps ceiling so the fallback doesn't blow up on the
# one common encoder that would reject a higher default outright.
_FALLBACK_AUDIO_BIT_RATE = "192k"

# Subtitle codecs that carry plain text (as opposed to pre-rendered bitmap
# subtitles like PGS/VobSub/DVB), which is what can round-trip through the
# ASS intermediate.
_TEXT_SUBTITLE_CODECS = {"subrip", "ass", "ssa", "mov_text", "webvtt", "text"}

_INTERMEDIATE_VIDEO_CODEC = "ffv1"
_INTERMEDIATE_AUDIO_CODEC = "flac"
_INTERMEDIATE_SUBTITLE_CODEC = "ass"
_INTERMEDIATE_MUXER = "matroska"


def _video_output_kwargs(index: int, stream: dict) -> dict:
    encoder = _VIDEO_ENCODERS.get(stream["codec_name"], stream["codec_name"])
    return {
        f"c:v:{index}": encoder,
        f"b:v:{index}": stream.get("bit_rate", _FALLBACK_VIDEO_BIT_RATE),
    }


def _audio_output_kwargs(index: int, stream: dict) -> dict:
    encoder = _AUDIO_ENCODERS.get(stream["codec_name"], stream["codec_name"])
    kwargs = {f"c:a:{index}": encoder}
    if encoder not in _LOSSLESS_AUDIO_ENCODERS:
        kwargs[f"b:a:{index}"] = stream.get("bit_rate", _FALLBACK_AUDIO_BIT_RATE)
    return kwargs


def _subtitle_output_kwargs(index: int, stream: dict) -> dict:
    return {f"c:s:{index}": stream["codec_name"]}


def disarm(input_path: Path, output_path: Path) -> None:
    mime_type = detect_mime_type(input_path)
    muxer = _CONTAINER_MUXERS[mime_type]

    streams = ffmpeg.probe(str(input_path))["streams"]
    video_streams = [s for s in streams if s["codec_type"] == "video"]
    audio_streams = [s for s in streams if s["codec_type"] == "audio"]
    text_subtitle_streams = [
        s
        for s in streams
        if s["codec_type"] == "subtitle" and s["codec_name"] in _TEXT_SUBTITLE_CODECS
    ]

    kept = video_streams + audio_streams + text_subtitle_streams
    kept_indexes = {s["index"] for s in kept}
    for stream in streams:
        if stream["index"] not in kept_indexes:
            logger.warning(
                f"{input_path}: stream {stream['index']} "
                f"(type={stream['codec_type']}, codec={stream.get('codec_name')}) "
                "is not video, audio, or a text subtitle codec -- dropping it"
            )

    intermediate = output_path.parent / f"{output_path.name}.tmp.mkv"
    try:
        intermediate_kwargs = {
            "map_metadata": "-1",
            "map_chapters": "-1",
            "format": _INTERMEDIATE_MUXER,
        }
        if video_streams:
            intermediate_kwargs["c:v"] = _INTERMEDIATE_VIDEO_CODEC
        if audio_streams:
            intermediate_kwargs["c:a"] = _INTERMEDIATE_AUDIO_CODEC
        if text_subtitle_streams:
            intermediate_kwargs["c:s"] = _INTERMEDIATE_SUBTITLE_CODEC

        source = ffmpeg.input(str(input_path))
        mapped = [source[str(s["index"])] for s in kept]
        logger.debug(f"{input_path}: intermediate {intermediate}")
        ffmpeg.output(*mapped, str(intermediate), **intermediate_kwargs).run(
            overwrite_output=True, quiet=True
        )

        final_kwargs = {"map_metadata": "-1", "map_chapters": "-1", "format": muxer}
        for index, stream in enumerate(video_streams):
            final_kwargs.update(_video_output_kwargs(index, stream))
        for index, stream in enumerate(audio_streams):
            final_kwargs.update(_audio_output_kwargs(index, stream))
        for index, stream in enumerate(text_subtitle_streams):
            final_kwargs.update(_subtitle_output_kwargs(index, stream))

        rebuilt = ffmpeg.input(str(intermediate))
        remapped = [rebuilt[str(i)] for i in range(len(kept))]
        logger.debug(f"{input_path}: encoding final output {output_path} ({muxer})")
        ffmpeg.output(*remapped, str(output_path), **final_kwargs).run(
            overwrite_output=True, quiet=True
        )
    finally:
        intermediate.unlink(missing_ok=True)


register_handler(
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/x-msvideo",
    "video/webm",
)(disarm)
