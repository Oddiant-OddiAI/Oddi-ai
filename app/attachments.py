"""Normalize user uploads into provider-neutral text, image and audio inputs.

Office files and source/text formats are extracted locally, so any routed text
model can use them. Images and audio remain binary and are sent only to models
whose adapter advertises the matching input capability.
"""

from __future__ import annotations

import csv
import email
import html
import io
import json
import mimetypes
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import cv2
import numpy as np
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader


MAX_UPLOAD_BYTES = 64 * 1024 * 1024
MAX_EXTRACTED_CHARS_PER_FILE = 160_000
MAX_EXTRACTED_CHARS_TOTAL = 320_000
MAX_ARCHIVE_ENTRIES = 100
MAX_ARCHIVE_EXPANDED_BYTES = 32 * 1024 * 1024
MAX_VIDEO_FRAMES = 10
MAX_ROUTED_IMAGE_BYTES = 12 * 1024 * 1024

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json",
    ".jsonl", ".ndjson", ".xml", ".html", ".htm", ".xhtml", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".conf", ".log", ".sql", ".py",
    ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".go", ".rs", ".php",
    ".rb", ".swift", ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1",
    ".css", ".scss", ".less", ".tex", ".env", ".properties", ".diff",
    ".patch", ".graphql", ".proto", ".dockerfile", ".makefile", ".lock",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".aiff", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".wmv", ".3gp", ".flv"}


class AttachmentReadError(ValueError):
    """A user upload could not be safely normalized for AI input."""


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._hidden += 1
        elif not self._hidden and tag.lower() in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._hidden:
            self._hidden -= 1
        elif not self._hidden and tag.lower() in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._hidden and data.strip():
            self.parts.append(data)


def _get_bytes(upload: Any) -> bytes:
    stream = getattr(upload, "stream", upload)
    try:
        stream.seek(0)
        data = stream.read(MAX_UPLOAD_BYTES + 1)
        stream.seek(0)
    except Exception as exc:
        raise AttachmentReadError("The uploaded file could not be read.") from exc
    if len(data) > MAX_UPLOAD_BYTES:
        raise AttachmentReadError("Files larger than 64 MB are not supported yet.")
    if not data:
        raise AttachmentReadError("The uploaded file is empty.")
    return data


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            decoded = data.decode(encoding)
            if decoded.count("\ufffd") <= max(2, len(decoded) // 1000):
                return decoded
        except (UnicodeDecodeError, LookupError):
            continue
    raise AttachmentReadError("The file is not readable text or a supported document format.")


def _clip(text: str, filename: str) -> str:
    text = str(text or "").strip()
    if len(text) > MAX_EXTRACTED_CHARS_PER_FILE:
        text = text[:MAX_EXTRACTED_CHARS_PER_FILE] + f"\n[Content from {filename} was shortened at 160,000 characters.]"
    return text


def _html_text(data: bytes) -> str:
    parser = _VisibleText()
    parser.feed(_decode_text(data))
    return html.unescape(" ".join(" ".join(parser.parts).split()))


def _docx_text(data: bytes) -> str:
    document = Document(io.BytesIO(data))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            values = [cell.text.strip() for cell in row.cells]
            if any(values):
                parts.append(" | ".join(values))
    for section in document.sections:
        for area in (section.header, section.footer):
            parts.extend(p.text.strip() for p in area.paragraphs if p.text.strip())
    return "\n".join(parts)


def _spreadsheet_text(data: bytes) -> str:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for sheet in workbook.worksheets:
        parts.append(f"--- Sheet: {sheet.title} ---")
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if value is None else str(value) for value in row]
            while cells and not cells[-1]:
                cells.pop()
            if any(cells):
                parts.append(" | ".join(cells))
    workbook.close()
    return "\n".join(parts)


def _pptx_text(data: bytes) -> str:
    presentation = Presentation(io.BytesIO(data))
    parts = []
    for number, slide in enumerate(presentation.slides, 1):
        parts.append(f"--- Slide {number} ---")
        for shape in slide.shapes:
            value = getattr(shape, "text", "")
            if value and value.strip():
                parts.append(value.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _package_images(data: bytes, filename: str, folder_prefix: str) -> list[dict[str, Any]]:
    images = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [name for name in archive.namelist() if name.startswith(folder_prefix) and Path(name).suffix.lower() in IMAGE_EXTENSIONS]
            for member in members[:12]:
                mime = mimetypes.guess_type(member)[0] or "image/jpeg"
                images.append(_image_input(archive.read(member), mime, f"{filename} · {Path(member).name}"))
    except zipfile.BadZipFile:
        return []
    return images


def _pdf_text(data: bytes, filename: str) -> tuple[str, list[dict[str, Any]]]:
    reader = PdfReader(io.BytesIO(data))
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(f"--- Page {i + 1} ---\n{value}" for i, value in enumerate(page_text) if value)
    pages_to_render = {index for index, value in enumerate(page_text) if not value}
    for index, page in enumerate(reader.pages):
        try:
            if list(page.images):
                pages_to_render.add(index)
        except Exception:
            pass
    if not pages_to_render:
        return text, []

    # Scanned/image-only pages need page images. PyMuPDF is declared in
    # requirements.txt; keep a clear error if an environment has not installed it.
    try:
        import fitz
    except ImportError as exc:
        if text:
            return text + "\n[Some PDF pages contain scanned or embedded visual content that could not be rendered for AI visual reading.]", []
        raise AttachmentReadError(
            f"{filename} appears to be a scanned PDF. Install PyMuPDF to enable page-image reading."
        ) from exc

    images = []
    pdf = fitz.open(stream=data, filetype="pdf")
    try:
        for page_number, page in enumerate(pdf):
            if page_number not in pages_to_render:
                continue
            if page_number >= 12:
                break
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
            images.append({
                "bytes": pixmap.tobytes("jpeg"),
                "mimetype": "image/jpeg",
                "filename": f"{filename} · page {page_number + 1}",
            })
    finally:
        pdf.close()
    if not images and not text:
        raise AttachmentReadError(f"No readable pages were found in {filename}.")
    if images:
        text += f"\n[Pages {', '.join(str(index + 1) for index in sorted(pages_to_render)[:len(images)])} contain scanned or embedded visual content and are attached as images.]"
    return text, images


def _xml_package_text(data: bytes, member: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml_data = archive.read(member)
    root = ElementTree.fromstring(xml_data)
    return "\n".join(value.strip() for value in root.itertext() if value and value.strip())


def _rtf_text(data: bytes) -> str:
    source = _decode_text(data)
    source = re.sub(r"\\'[0-9a-fA-F]{2}", " ", source)
    source = re.sub(r"\\(?:par|line|tab)\b", "\n", source)
    source = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", source)
    source = source.replace("{", " ").replace("}", " ")
    return " ".join(source.split())


def _image_input(data: bytes, mimetype: str, filename: str) -> dict[str, Any]:
    supported_mimes = {"image/png", "image/jpeg"}
    if mimetype in supported_mimes and len(data) <= 15 * 1024 * 1024:
        return {"bytes": data, "mimetype": mimetype, "filename": filename}
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise AttachmentReadError(f"{filename} is an image format the reader could not decode.")
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest > 2200:
        scale = 2200 / longest
        image = cv2.resize(image, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise AttachmentReadError(f"{filename} could not be converted for visual reading.")
    return {"bytes": encoded.tobytes(), "mimetype": "image/jpeg", "filename": filename}


def _compress_image_batch(images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if sum(len(item.get("bytes") or b"") for item in images) <= MAX_ROUTED_IMAGE_BYTES:
        return images
    for longest, quality in ((1800, 84), (1400, 76), (1000, 68)):
        compressed = []
        for item in images:
            decoded = cv2.imdecode(np.frombuffer(item["bytes"], dtype=np.uint8), cv2.IMREAD_COLOR)
            if decoded is None:
                raise AttachmentReadError(f"{item.get('filename', 'An image')} could not be prepared for provider input.")
            height, width = decoded.shape[:2]
            scale = min(1.0, longest / max(height, width))
            if scale < 1:
                decoded = cv2.resize(decoded, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
            ok, encoded = cv2.imencode(".jpg", decoded, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                raise AttachmentReadError(f"{item.get('filename', 'An image')} could not be prepared for provider input.")
            compressed.append({**item, "bytes": encoded.tobytes(), "mimetype": "image/jpeg"})
        images = compressed
        if sum(len(item["bytes"]) for item in images) <= MAX_ROUTED_IMAGE_BYTES:
            return images
    raise AttachmentReadError("The combined image/video frames are too large for the configured provider input limit.")


def _safe_convert_office(data: bytes, filename: str, target_ext: str) -> bytes:
    soffice = shutil.which("soffice")
    if not soffice:
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidate = os.path.join(program_files, "LibreOffice", "program", "soffice.exe")
        if os.path.isfile(candidate):
            soffice = candidate
    if not soffice:
        raise AttachmentReadError(f"{filename} needs LibreOffice to read this older Office format.")
    source_ext = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory(prefix="oddi-upload-") as temp_dir:
        source_path = os.path.join(temp_dir, "input" + source_ext)
        with open(source_path, "wb") as output:
            output.write(data)
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", target_ext.lstrip("."), "--outdir", temp_dir, source_path],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        converted_path = os.path.join(temp_dir, "input" + target_ext)
        if result.returncode != 0 or not os.path.isfile(converted_path):
            raise AttachmentReadError(f"LibreOffice could not convert {filename} for reading.")
        with open(converted_path, "rb") as converted:
            return converted.read()


def _video_inputs(data: bytes, filename: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    extension = Path(filename).suffix.lower() or ".mp4"
    frames: list[dict[str, Any]] = []
    audios: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="oddi-video-") as temp_dir:
        video_path = os.path.join(temp_dir, "upload" + extension)
        with open(video_path, "wb") as output:
            output.write(data)

        capture = cv2.VideoCapture(video_path)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        duration = total_frames / fps if total_frames else 0.0
        count = min(MAX_VIDEO_FRAMES, max(1, int(duration) + 1))
        if total_frames:
            for i in range(count):
                timestamp = duration * i / max(1, count - 1)
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                height, width = frame.shape[:2]
                if max(height, width) > 1600:
                    scale = 1600 / max(height, width)
                    frame = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))), interpolation=cv2.INTER_AREA)
                encoded_ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
                if encoded_ok:
                    frames.append({
                        "bytes": encoded.tobytes(),
                        "mimetype": "image/jpeg",
                        "filename": f"{filename} · {timestamp:.1f}s",
                        "timestamp": timestamp,
                    })
        capture.release()

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            try:
                import imageio_ffmpeg
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
            except (ImportError, RuntimeError):
                ffmpeg = None
        audio_note = ""
        if ffmpeg:
            audio_path = os.path.join(temp_dir, "audio.mp3")
            result = subprocess.run(
                [ffmpeg, "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k", audio_path],
                capture_output=True,
                timeout=90,
                check=False,
            )
            if result.returncode == 0 and os.path.isfile(audio_path):
                audio_bytes = Path(audio_path).read_bytes()
                if audio_bytes:
                    audios.append({"bytes": audio_bytes, "mimetype": "audio/mpeg", "filename": f"{filename} audio"})
            else:
                audio_note = " (audio track could not be extracted)"
        else:
            audio_note = " (audio transcription is unavailable because FFmpeg is not installed)"

    if not frames:
        raise AttachmentReadError(f"Could not decode any frames from {filename}.")
    note = f"Video: {filename}, {duration:.1f} seconds; {len(frames)} frames sampled in chronological order{audio_note}."
    return frames, audios, note


def _email_text(data: bytes) -> str:
    message = email.message_from_bytes(data)
    parts = [f"Subject: {message.get('subject', '')}", f"From: {message.get('from', '')}"]
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "text" and part.get_content_subtype() in {"plain", "html"}:
                payload = part.get_payload(decode=True) or b""
                content = _html_text(payload) if part.get_content_subtype() == "html" else _decode_text(payload)
                if content.strip():
                    parts.append(content)
    else:
        payload = message.get_payload(decode=True)
        if isinstance(payload, bytes):
            parts.append(_decode_text(payload))
    return "\n".join(parts)


def _extract_one(filename: str, mimetype: str, data: bytes) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    ext = Path(filename).suffix.lower()
    normalized_mime = (mimetype or "").lower().split(";")[0].strip()
    images: list[dict[str, Any]] = []
    audios: list[dict[str, Any]] = []

    if ext in IMAGE_EXTENSIONS or normalized_mime.startswith("image/"):
        actual_mime = normalized_mime if normalized_mime.startswith("image/") else mimetypes.guess_type(filename)[0] or "image/jpeg"
        images.append(_image_input(data, actual_mime, filename))
        return f"[Image attachment: {filename}. The image is attached for visual analysis.]", images, audios

    if ext in AUDIO_EXTENSIONS or normalized_mime.startswith("audio/"):
        actual_mime = normalized_mime if normalized_mime.startswith("audio/") else mimetypes.guess_type(filename)[0] or "audio/mpeg"
        audios.append({"bytes": data, "mimetype": actual_mime, "filename": filename})
        return f"[Audio attachment: {filename}. The audio is attached for listening/transcription.]", images, audios

    if ext in VIDEO_EXTENSIONS or normalized_mime.startswith("video/"):
        video_images, video_audios, note = _video_inputs(data, filename)
        return f"[{note}]", video_images, video_audios

    if ext == ".pdf" or normalized_mime == "application/pdf" or data.startswith(b"%PDF-"):
        text, page_images = _pdf_text(data, filename)
        return text, page_images, audios

    if ext in {".docx", ".docm"} or normalized_mime.endswith("wordprocessingml.document"):
        return _docx_text(data), _package_images(data, filename, "word/media/"), audios

    if ext in {".xlsx", ".xlsm"} or "spreadsheetml" in normalized_mime:
        return _spreadsheet_text(data), _package_images(data, filename, "xl/media/"), audios

    if ext in {".pptx", ".pptm"} or "presentationml.presentation" in normalized_mime:
        return _pptx_text(data), _package_images(data, filename, "ppt/media/"), audios

    if ext == ".doc":
        return _docx_text(_safe_convert_office(data, filename, ".docx")), images, audios

    if ext == ".ppt":
        converted = _safe_convert_office(data, filename, ".pptx")
        return _pptx_text(converted), _package_images(converted, filename, "ppt/media/"), audios

    if ext == ".xls":
        converted = _safe_convert_office(data, filename, ".xlsx")
        return _spreadsheet_text(converted), _package_images(converted, filename, "xl/media/"), audios

    if ext == ".rtf" or normalized_mime == "application/rtf":
        return _rtf_text(data), images, audios

    if ext == ".eml" or normalized_mime == "message/rfc822":
        return _email_text(data), images, audios

    if ext in {".odt", ".ods", ".odp"}:
        return _xml_package_text(data, "content.xml"), _package_images(data, filename, "Pictures/"), audios

    if ext == ".epub":
        parts = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [item for item in archive.infolist() if Path(item.filename).suffix.lower() in {".html", ".htm", ".xhtml"}]
            total = 0
            for entry in entries[:MAX_ARCHIVE_ENTRIES]:
                total += entry.file_size
                if total > MAX_ARCHIVE_EXPANDED_BYTES:
                    raise AttachmentReadError(f"{filename} expands beyond the safe document-reading limit.")
                parts.append(_html_text(archive.read(entry)))
        return "\n\n".join(parts), images, audios

    if ext == ".zip" or normalized_mime in {"application/zip", "application/x-zip-compressed"}:
        parts = []
        total = 0
        supported = TEXT_EXTENSIONS | {".pdf", ".docx", ".xlsx", ".pptx", ".rtf", ".odt"}
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise AttachmentReadError(f"{filename} contains more than {MAX_ARCHIVE_ENTRIES} files.")
            for entry in entries:
                if entry.flag_bits & 1:
                    continue
                total += entry.file_size
                if total > MAX_ARCHIVE_EXPANDED_BYTES:
                    raise AttachmentReadError(f"{filename} expands beyond the safe 32 MB reading limit.")
                member_ext = Path(entry.filename).suffix.lower()
                if member_ext not in supported:
                    continue
                member_data = archive.read(entry)
                member_text, member_images, member_audios = _extract_one(entry.filename, mimetypes.guess_type(entry.filename)[0] or "", member_data)
                parts.append(f"--- Archive file: {entry.filename} ---\n{member_text}")
                images.extend(member_images)
                audios.extend(member_audios)
        if not parts:
            raise AttachmentReadError(f"No supported readable documents were found inside {filename}.")
        return "\n\n".join(parts), images, audios

    if ext in TEXT_EXTENSIONS or normalized_mime.startswith("text/"):
        text = _decode_text(data)
        if ext in {".html", ".htm", ".xhtml"} or normalized_mime == "text/html":
            text = _html_text(data)
        elif ext == ".csv":
            rows = csv.reader(io.StringIO(text))
            text = "\n".join(" | ".join(row) for row in rows)
        elif ext == ".tsv":
            rows = csv.reader(io.StringIO(text), delimiter="\t")
            text = "\n".join(" | ".join(row) for row in rows)
        elif ext in {".json", ".jsonl", ".ndjson"}:
            try:
                value = json.loads(text) if ext == ".json" else text
                text = json.dumps(value, ensure_ascii=False, indent=2) if ext == ".json" else text
            except json.JSONDecodeError:
                pass
        return text, images, audios

    # Some clients send text with an unknown filename suffix. Accept it only
    # when the bytes have no NULs and decode as UTF-8; otherwise fail explicitly.
    if b"\x00" not in data[:4096]:
        try:
            return data.decode("utf-8-sig"), images, audios
        except UnicodeDecodeError:
            pass
    raise AttachmentReadError(f"{filename} ({normalized_mime or 'unknown type'}) is not a supported readable format.")


def read_attachments(uploaded_files: list[Any] | None) -> dict[str, Any]:
    """Read every supplied file and return normalized text and media inputs."""
    all_documents: list[str] = []
    images: list[dict[str, Any]] = []
    audios: list[dict[str, Any]] = []
    names = []
    remaining_chars = MAX_EXTRACTED_CHARS_TOTAL

    for upload in uploaded_files or []:
        filename = Path(str(getattr(upload, "filename", "unnamed-file"))).name or "unnamed-file"
        mimetype = str(getattr(upload, "mimetype", getattr(upload, "content_type", "")) or "")
        try:
            data = _get_bytes(upload)
            text, file_images, file_audios = _extract_one(filename, mimetype, data)
            text = _clip(text, filename)
            if len(text) > remaining_chars:
                text = text[:remaining_chars] + "\n[Further uploaded-file text was shortened to keep the request within the reading limit.]"
                remaining_chars = 0
            else:
                remaining_chars -= len(text)
            all_documents.append(f"===== {filename} =====\n{text}")
            images.extend(file_images)
            audios.extend(file_audios)
            names.append(filename)
        except AttachmentReadError:
            raise
        except Exception as exc:
            raise AttachmentReadError(f"{filename} could not be read: {type(exc).__name__}: {exc}") from exc

    return {
        "documents": "\n\n".join(all_documents),
        "images": _compress_image_batch(images),
        "audios": audios,
        "filenames": names,
    }
