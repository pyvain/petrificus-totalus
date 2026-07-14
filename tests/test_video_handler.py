import io
import json
import subprocess
from pathlib import Path

import ffmpeg
import pytest
from PIL import Image

from petrificus_totalus import disarm_file, iter_supported_mime_types
from petrificus_totalus._registry import detect_mime_type


def _probe_streams(path: Path) -> list[dict]:
    return ffmpeg.probe(str(path))["streams"]


def _codec_names(path: Path, codec_type: str) -> list[str]:
    return [s["codec_name"] for s in _probe_streams(path) if s["codec_type"] == codec_type]


def _first_frame_pixel(path: Path, xy: tuple[int, int] = (10, 10)) -> tuple[int, int, int]:
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(path),
            "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1",
        ],  # fmt: skip
        check=True,
        capture_output=True,
        timeout=30,
    )
    with Image.open(io.BytesIO(result.stdout)) as frame:
        return frame.convert("RGB").getpixel(xy)


def _extract_srt_text(path: Path, stream_index: int = 0) -> str:
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-map", f"0:s:{stream_index}", "-f", "srt", "pipe:1"],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return result.stdout.decode()


def test_iter_supported_mime_types_includes_mp4(tmp_path: Path, make_video):
    src = make_video(tmp_path / "clip.mp4")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_iter_supported_mime_types_includes_mkv(tmp_path: Path, make_video):
    src = make_video(tmp_path / "clip.mkv", video_codec="libx264", audio_codec="flac")
    assert detect_mime_type(src) in iter_supported_mime_types()


def test_mp4_roundtrip_preserves_container_video_and_audio_codecs(
    tmp_path: Path, make_video
):
    src = make_video(tmp_path / "clip.mp4", video_codec="libx264", audio_codec="aac")
    mime_before = detect_mime_type(src)

    result, _ = disarm_file(src)

    assert result == src
    assert detect_mime_type(result) == mime_before
    assert _codec_names(result, "video") == ["h264"]
    assert _codec_names(result, "audio") == ["aac"]


def test_mkv_roundtrip_preserves_container_video_and_audio_codecs(
    tmp_path: Path, make_video
):
    src = make_video(tmp_path / "clip.mkv", video_codec="libx264", audio_codec="flac")

    disarm_file(src)

    assert detect_mime_type(src) == "video/x-matroska"
    assert _codec_names(src, "video") == ["h264"]
    assert _codec_names(src, "audio") == ["flac"]


def test_avi_roundtrip_preserves_container_video_and_audio_codecs(
    tmp_path: Path, make_video
):
    src = make_video(tmp_path / "clip.avi", video_codec="mpeg4", audio_codec="mp3")

    disarm_file(src)

    assert detect_mime_type(src) == "video/x-msvideo"
    assert _codec_names(src, "video") == ["mpeg4"]
    assert _codec_names(src, "audio") == ["mp3"]


def test_webm_roundtrip_preserves_container_video_and_audio_codecs(
    tmp_path: Path, make_video
):
    src = make_video(tmp_path / "clip.webm", video_codec="libvpx-vp9", audio_codec="libopus")

    disarm_file(src)

    assert detect_mime_type(src) == "video/webm"
    assert _codec_names(src, "video") == ["vp9"]
    assert _codec_names(src, "audio") == ["opus"]


def test_video_roundtrip_preserves_pixel_values_losslessly(tmp_path: Path, make_video):
    src = make_video(tmp_path / "clip.mp4", video_codec="libx264", color="red", audio_codec=None)
    before = _first_frame_pixel(src)

    disarm_file(src)

    assert _first_frame_pixel(src) == before


def test_video_roundtrip_preserves_subtitle_text(tmp_path: Path, make_video):
    src = make_video(
        tmp_path / "clip.mkv",
        video_codec="libx264",
        audio_codec="flac",
        subtitles=("Hello", "World"),
        subtitle_codec="srt",
    )
    before = _extract_srt_text(src)
    assert "Hello" in before

    disarm_file(src)

    assert _codec_names(src, "subtitle") == ["subrip"]
    after = _extract_srt_text(src)
    assert "Hello" in after
    assert "World" in after


def test_video_disarm_drops_unconvertible_stream_and_logs_warning(
    tmp_path: Path, make_video, caplog
):
    src = make_video(tmp_path / "clip.mkv", video_codec="libx264", audio_codec="flac")
    with_attachment = tmp_path / "with_attachment.mkv"
    font_file = tmp_path / "fake_font.ttf"
    font_file.write_bytes(b"not a real font, just attachment payload")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(src),
            "-c", "copy", "-attach", str(font_file),
            "-metadata:s:t", "mimetype=application/x-font-ttf",
            str(with_attachment),
        ],  # fmt: skip
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert "attachment" in [s["codec_type"] for s in _probe_streams(with_attachment)]

    with caplog.at_level("WARNING", logger="petrificus-totalus"):
        disarm_file(with_attachment)

    assert "attachment" in caplog.text
    assert "attachment" not in [s["codec_type"] for s in _probe_streams(with_attachment)]
    assert _codec_names(with_attachment, "video") == ["h264"]
    assert _codec_names(with_attachment, "audio") == ["flac"]


def test_disarm_file_writes_video_to_explicit_output_path(tmp_path: Path, make_video):
    src = make_video(tmp_path / "in" / "clip.mp4")
    dst = tmp_path / "out" / "clip.mp4"

    result, _ = disarm_file(src, dst)

    assert result == dst
    assert dst.is_file()
    assert src.is_file()  # original untouched
    assert _codec_names(dst, "video") == ["h264"]


def test_video_disarm_transcodes_rather_than_copies_when_codecs_already_match(
    tmp_path: Path, make_video, monkeypatch
):
    """A source already encoded as FFV1/FLAC has the same codec on both sides
    of both ffmpeg calls disarm() makes (input -> intermediate and
    intermediate -> final both stay FFV1/FLAC in that case). The CDR
    guarantee -- that the output is rebuilt from decoded samples rather than
    copied bytes -- depends on ffmpeg actually decoding and re-encoding here
    rather than silently taking a "the codec already matches" shortcut. This
    spies on every ffmpeg subprocess disarm() launches and inspects its
    stream-mapping log: ffmpeg reports a real transcode as
    "codec (native) -> codec (encoder)" and a stream copy as plain "(copy)".
    If a future ffmpeg version (or a future change to this handler) ever
    introduced such a shortcut, this test would start seeing "(copy)" and
    fail.
    """
    src = make_video(tmp_path / "clip.mkv", video_codec="ffv1", audio_codec="flac")

    captured_stderr: list[bytes] = []
    real_popen = subprocess.Popen

    def spy_popen(args, **kwargs):
        process = real_popen(args, **kwargs)
        if args[0] == "ffmpeg":
            real_communicate = process.communicate

            def spy_communicate(*a, **kw):
                out, err = real_communicate(*a, **kw)
                if err:
                    captured_stderr.append(err)
                return out, err

            process.communicate = spy_communicate
        return process

    monkeypatch.setattr(subprocess, "Popen", spy_popen)

    disarm_file(src)

    assert len(captured_stderr) == 2  # input->intermediate, intermediate->final
    # Match on the "Stream #N:M -> #N:M" mapping lines directly, not on the
    # codec name -- a "(copy)" line never mentions the codec at all, so
    # filtering by codec name would silently exclude exactly the lines this
    # test needs to catch.
    mapping_lines = [
        line
        for chunk in captured_stderr
        for line in chunk.decode(errors="replace").splitlines()
        if "Stream #0:" in line and "->" in line
    ]
    # Both passes carry a video and an audio stream, so 2 lines each.
    assert len(mapping_lines) == 4
    assert not any("(copy)" in line for line in mapping_lines)
    assert all("(native) ->" in line for line in mapping_lines)
