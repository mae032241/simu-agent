"""Bounded recovery of one exact raster or embedded PDF figure image."""

from __future__ import annotations

import hashlib
import io
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, __version__ as PILLOW_VERSION


MAX_IMAGE_PIXELS = 25_000_000
MAX_PDF_IMAGES_PER_PAGE = 32

# Automatic source contract v1. Callers cannot override these budgets.
AUTOMATIC_MAX_PAGES = 8
AUTOMATIC_MAX_TOTAL_PIXELS = 24_000_000
AUTOMATIC_MAX_SIDE = 1600
AUTOMATIC_DPI = 120
AUTOMATIC_MAX_SOURCE_BYTES = 64_000_000
AUTOMATIC_SOURCE_POLICY = (
    "automatic-source-v2", "pages=8", "total_pixels=24000000",
    "canonical_max_side=1600", "requested_render_dpi=120", "source_bytes=64000000",
    "per_image_pixels=25000000", "embedded_per_page=32", "command_timeout_seconds=60",
)


@dataclass(frozen=True, slots=True)
class AutomaticImage:
    content: bytes
    image_sha256: str
    kind: str
    page: int | None
    width: int
    height: int
    # Affine maps original coordinates to canonical pixel coordinates.
    transform: tuple[float, float, float, float, float, float]
    coordinate_space: str
    rotation: int
    tool: str
    tool_version: str
    pdf_object: tuple[int, int] | None = None
    requested_dpi: int | None = None
    media_box: tuple[float, float, float, float] | None = None
    crop_box: tuple[float, float, float, float] | None = None


@dataclass(frozen=True, slots=True)
class AutomaticRecovery:
    source_sha256: str
    images: tuple[AutomaticImage, ...]
    unresolved: tuple[str, ...]
    provenance: tuple[str, ...] = AUTOMATIC_SOURCE_POLICY


def _automatic_run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Environment/process failures are errors, never scientific no-figure results."""
    try:
        result = subprocess.run(command, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"automatic source tool failed: {command[0]}") from error
    if result.returncode:
        raise RuntimeError(f"automatic source tool failed: {command[0]}: {result.stderr[-512:]!r}")
    return result


def _automatic_image(content: bytes, *, kind: str, page: int | None,
                     transform: tuple[float, float, float, float, float, float],
                     coordinate_space: str, rotation: int, tool: str,
                     tool_version: str, pdf_object: tuple[int, int] | None = None,
                     media_box: tuple[float, float, float, float] | None = None,
                     crop_box: tuple[float, float, float, float] | None = None) -> AutomaticImage:
    with Image.open(io.BytesIO(content)) as raw:
        if raw.width * raw.height > MAX_IMAGE_PIXELS:
            raise ValueError("automatic_image_pixel_budget")
        image = raw.convert("RGB")
        factor = min(1., AUTOMATIC_MAX_SIDE / max(image.size))
        size = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
        sx, sy = size[0] / image.width, size[1] / image.height
        if size != image.size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        a, b, c, d, e, f = transform
        canonical = _png_bytes(image)
        return AutomaticImage(canonical, _sha256(canonical), kind, page, *size,
                              (a*sx, b*sx, c*sx, d*sy, e*sy, f*sy), coordinate_space,
                              rotation, tool, tool_version, pdf_object,
                              AUTOMATIC_DPI if kind == "page_render" else None,
                              media_box, crop_box)


def recover_automatic_source(content: bytes) -> AutomaticRecovery:
    """Sequential bounded recovery from a raw document, without page/object hints."""
    source_hash = _sha256(content)
    if len(content) > AUTOMATIC_MAX_SOURCE_BYTES:
        return AutomaticRecovery(source_hash, (), ("source_byte_budget",))
    if not content.startswith(b"%PDF-"):
        try:
            frame = _automatic_image(content, kind="raster", page=None,
                transform=(1., 0., 0., 0., 1., 0.), coordinate_space="original_raster_pixels",
                rotation=0, tool="Pillow", tool_version=PILLOW_VERSION)
        except (OSError, ValueError, Image.DecompressionBombError):
            return AutomaticRecovery(source_hash, (), ("raster_unrecoverable_or_pixel_budget",))
        return AutomaticRecovery(source_hash, (frame,), ())
    images: list[AutomaticImage] = []
    unresolved: list[str] = []
    pixels = 0
    with tempfile.TemporaryDirectory(prefix="scid-auto-source-") as directory:
        root = Path(directory)
        path = root / "source.pdf"
        path.write_bytes(content)
        info = _automatic_run(["pdfinfo", str(path)]).stdout.decode("utf8", errors="replace")
        match = re.search(r"Pages:\s+(\d+)", info)
        if not match:
            raise RuntimeError("pdfinfo returned no page count")
        pages = int(match[1])
        if pages > AUTOMATIC_MAX_PAGES:
            unresolved.append("source_page_budget")
        versions = {}
        for tool in ("pdfimages", "pdftoppm"):
            result = _automatic_run([tool, "-v"])
            versions[tool] = (result.stdout + result.stderr).decode("utf8").splitlines()[0] + f"; Pillow {PILLOW_VERSION}"
        for page in range(1, min(pages, AUTOMATIC_MAX_PAGES) + 1):
            metadata = _automatic_run(["pdfinfo", "-f", str(page), "-l", str(page), "-box", str(path)]).stdout.decode("utf8")
            boxes = {}
            for name in ("MediaBox", "CropBox"):
                match = re.search(name + r":\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)", metadata)
                if not match:
                    raise RuntimeError("pdfinfo returned incomplete page boxes")
                boxes[name] = tuple(map(float, match.groups()))
            rotation = re.search(r"(?:Page\s+\d+\s+rot|Page rot):\s+(\d+)", metadata)
            if not rotation:
                raise RuntimeError("pdfinfo returned incomplete page geometry")
            # pdftoppm without -cropbox renders MediaBox. Page size can describe
            # CropBox and must never determine this mapping. The coordinate space
            # is relative to this explicit MediaBox's unrotated top-left origin.
            x0, y0, x1, y1 = boxes["MediaBox"]
            width, height = x1-x0, y1-y0
            if width <= 0 or height <= 0:
                raise RuntimeError("pdfinfo returned an invalid MediaBox")
            angle = int(rotation[1]) % 360
            if angle not in (0, 90, 180, 270):
                unresolved.append("unsupported_page_rotation")
                continue
            # Original PDF points measured from the unrotated top-left of MediaBox.
            transforms = {0: (1.,0.,0.,0.,1.,0.), 90:(0.,-1.,height,1.,0.,0.),
                          180:(-1.,0.,width,0.,-1.,height), 270:(0.,1.,0.,-1.,0.,width)}
            prefix = root / "page"
            _automatic_run(["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", str(AUTOMATIC_MAX_SIDE), "-r", str(AUTOMATIC_DPI), "-png", str(path), str(prefix)])
            rendered = (root / "page.png").read_bytes()
            with Image.open(io.BytesIO(rendered)) as img:
                sx = img.width / (height if angle in (90,270) else width)
                sy = img.height / (width if angle in (90,270) else height)
            a,b,c,d,e,f = transforms[angle]
            page_frames = [_automatic_image(rendered, kind="page_render", page=page,
                transform=(a*sx,b*sx,c*sx,d*sy,e*sy,f*sy), coordinate_space="unrotated_page_top_left_points",
                rotation=angle, tool="pdftoppm", tool_version=versions["pdftoppm"],
                media_box=boxes["MediaBox"], crop_box=boxes["CropBox"])]
            try:
                embedded = inspect_pdf_images(path, page=page)
            except ValueError as error:
                if str(error) == "PDF page contains no recoverable embedded image":
                    embedded = ()
                elif any(term in str(error) for term in ("limit", "budget", "masks or image forms")):
                    unresolved.append("embedded_image_unsupported_or_budget")
                    embedded = ()
                else:
                    raise RuntimeError("embedded recovery failed") from error
            for item in embedded:
                page_frames.append(_automatic_image(item.content, kind="embedded_image", page=page,
                    transform=(1.,0.,0.,0.,1.,0.), coordinate_space="embedded_object_pixels",
                    rotation=0, tool="pdfimages", tool_version=versions["pdfimages"],
                    pdf_object=(item.pdf_object_id, item.pdf_object_generation)))
            for frame in page_frames:
                pixels += frame.width * frame.height
                if pixels > AUTOMATIC_MAX_TOTAL_PIXELS:
                    return AutomaticRecovery(source_hash, tuple(images), tuple(sorted(set(unresolved + ["source_pixel_budget"]))))
                images.append(frame)
    return AutomaticRecovery(source_hash, tuple(images), tuple(sorted(set(unresolved))))


@dataclass(frozen=True, slots=True)
class RecoveredFigureImage:
    content: bytes
    width: int
    height: int
    image_sha256: str
    recovery_tool: str = "Pillow"
    recovery_tool_version: str = PILLOW_VERSION
    page: int | None = None
    document_image_index: int | None = None
    page_image_index: int | None = None
    pdf_object_id: int | None = None
    pdf_object_generation: int | None = None

    def public_metadata(self, *, local_path: str) -> dict[str, object]:
        value: dict[str, object] = {
            "local_path": local_path,
            "media_type": "image/png",
            "width": self.width,
            "height": self.height,
            "recovered_image_sha256": self.image_sha256,
            "recovery_tool": self.recovery_tool,
            "recovery_tool_version": self.recovery_tool_version,
            "access": "read_only",
            "cache": "run_local",
        }
        if self.page is not None:
            value.update(
                {
                    "page": self.page,
                    "document_image_index": self.document_image_index,
                    "page_image_index": self.page_image_index,
                    "pdf_object_id": self.pdf_object_id,
                    "pdf_object_generation": self.pdf_object_generation,
                }
            )
        return value


@dataclass(frozen=True, slots=True)
class _PdfImageRow:
    page: int
    document_image_index: int
    page_image_index: int
    width: int
    height: int
    object_id: int
    object_generation: int


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _png_bytes(image: Image.Image) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=False, compress_level=9)
    return stream.getvalue()


def _canonical_raster(path: Path) -> tuple[bytes, int, int]:
    try:
        with Image.open(path) as source:
            source.verify()
        with Image.open(path) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise ValueError("source image exceeds the bounded pixel budget")
            width, height = source.width, source.height
            content = _png_bytes(source.convert("RGB"))
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError("source is not a valid bounded raster image") from error
    return content, width, height


def _run(command: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=max(1, min(60, timeout_seconds)),
        )
    except FileNotFoundError as error:
        raise ValueError("pdfimages is not installed") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("PDF image recovery timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")[-2048:]
        raise ValueError(f"PDF image recovery failed: {detail}")
    return completed


def _pdf_rows(path: Path, *, page: int, timeout_seconds: int) -> tuple[_PdfImageRow, ...]:
    completed = _run(["pdfimages", "-list", str(path)], timeout_seconds=timeout_seconds)
    rows: list[_PdfImageRow] = []
    page_index = 0
    for line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 12 or not fields[0].isdigit() or fields[2] != "image":
            continue
        row_page = int(fields[0])
        if row_page != page:
            continue
        rows.append(
            _PdfImageRow(
                page=row_page,
                document_image_index=int(fields[1]),
                page_image_index=page_index,
                width=int(fields[3]),
                height=int(fields[4]),
                object_id=int(fields[10]),
                object_generation=int(fields[11]),
            )
        )
        page_index += 1
    if not rows:
        raise ValueError("PDF page contains no recoverable embedded image")
    if len(rows) > MAX_PDF_IMAGES_PER_PAGE:
        raise ValueError("PDF page exceeds the embedded-image count limit")
    if any(row.width * row.height > MAX_IMAGE_PIXELS for row in rows):
        raise ValueError("PDF page contains an image above the pixel budget")
    return tuple(rows)


def _pdfimages_version(*, timeout_seconds: int) -> str:
    completed = _run(["pdfimages", "-v"], timeout_seconds=timeout_seconds)
    value = (completed.stdout + completed.stderr).decode(
        "utf-8", errors="replace"
    ).strip().splitlines()
    if not value:
        raise ValueError("pdfimages did not report its version")
    return f"{value[0][:192]}; Pillow {PILLOW_VERSION}"


def inspect_pdf_images(
    path: Path, *, page: int, timeout_seconds: int = 60
) -> tuple[RecoveredFigureImage, ...]:
    """Recover all ordinary embedded images on one exact PDF page as canonical PNG."""

    rows = _pdf_rows(path, page=page, timeout_seconds=timeout_seconds)
    recovery_version = _pdfimages_version(timeout_seconds=timeout_seconds)
    with tempfile.TemporaryDirectory(prefix="scid-pdf-images-") as raw_directory:
        prefix = Path(raw_directory) / "image"
        _run(
            [
                "pdfimages",
                "-f",
                str(page),
                "-l",
                str(page),
                "-png",
                str(path),
                str(prefix),
            ],
            timeout_seconds=timeout_seconds,
        )
        paths = tuple(sorted(Path(raw_directory).glob("image-*.png")))
        if len(paths) != len(rows):
            raise ValueError(
                "PDF page uses masks or image forms unsupported by this bounded extractor"
            )
        images: list[RecoveredFigureImage] = []
        for row, image_path in zip(rows, paths, strict=True):
            content, width, height = _canonical_raster(image_path)
            if (width, height) != (row.width, row.height):
                raise ValueError("recovered PDF image dimensions differ from its object table")
            images.append(
                RecoveredFigureImage(
                    content=content,
                    width=width,
                    height=height,
                    image_sha256=_sha256(content),
                    recovery_tool="pdfimages+Pillow",
                    recovery_tool_version=recovery_version,
                    page=row.page,
                    document_image_index=row.document_image_index,
                    page_image_index=row.page_image_index,
                    pdf_object_id=row.object_id,
                    pdf_object_generation=row.object_generation,
                )
            )
    return tuple(images)


def inspect_figure_source(
    path: Path,
    *,
    media_type: str,
    page: int | None = None,
    timeout_seconds: int = 60,
) -> tuple[RecoveredFigureImage, ...]:
    normalized = media_type.split(";", 1)[0].strip().lower()
    if normalized == "application/pdf":
        if page is None:
            raise ValueError("PDF figure inspection requires an exact page")
        return inspect_pdf_images(path, page=page, timeout_seconds=timeout_seconds)
    if normalized not in {"image/png", "image/jpeg", "image/webp"}:
        raise ValueError("figure source media type is unsupported")
    if page is not None:
        raise ValueError("raster figure inspection does not accept a PDF page")
    content, width, height = _canonical_raster(path)
    return (
        RecoveredFigureImage(
            content=content,
            width=width,
            height=height,
            image_sha256=_sha256(content),
        ),
    )


def inspect_figure_source_bytes(
    content: bytes,
    *,
    media_type: str,
    page: int | None = None,
    timeout_seconds: int = 60,
) -> tuple[RecoveredFigureImage, ...]:
    suffix = ".pdf" if media_type.split(";", 1)[0].strip().lower() == "application/pdf" else ".img"
    with tempfile.TemporaryDirectory(prefix="scid-figure-source-") as directory:
        path = Path(directory) / f"source{suffix}"
        path.write_bytes(content)
        return inspect_figure_source(
            path,
            media_type=media_type,
            page=page,
            timeout_seconds=timeout_seconds,
        )


__all__ = [
    "RecoveredFigureImage",
    "inspect_figure_source",
    "inspect_figure_source_bytes",
    "inspect_pdf_images",
]
