"""Deterministic Cartesian candidates, not scientific identities or qualified data.

The only source entry accepts bytes. Token injection belongs to the pure algorithm
API for adapter tests; it is not an Agent tool. All detection policy is versioned
here. Candidates retain ambiguity and never bridge absent pixels.
"""
from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import os
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from PIL import Image, ImageDraw, __version__ as PILLOW_VERSION

from .figure_source import (
    AUTOMATIC_SOURCE_POLICY, AutomaticImage, recover_automatic_source, _png_bytes,
)

DETECTOR_VERSION = "cartesian-candidates-v2"
MAX_PLOTS = 12
MAX_PATHS = 32
MAX_TOKENS = 2048
MAX_AXIS_COMBINATIONS = 64
MAX_LINE_SEGMENTS = 512
POLICY = ("dark<110", "chroma>=60", "long_line>=max(40,side*.12)",
          "axis_residual<=.005", "path_step<=4px", "path_span>=max(30,width*.18)",
          "no_gap_interpolation", "ocr_psm=11", "max_plots=12", "max_paths=32",
          "tick_ink_association=2px", "units=adjacent_baseline_tokens",
          "axis_mask=local_connected_dark_runs")


@dataclass(frozen=True, slots=True)
class OCRToken:
    text: str
    bbox: tuple[float, float, float, float]
    source: str

    def __post_init__(self):
        if len(self.bbox) != 4 or not all(math.isfinite(v) for v in self.bbox):
            raise ValueError("invalid OCR token geometry")
        if self.bbox[2] <= self.bbox[0] or self.bbox[3] <= self.bbox[1]:
            raise ValueError("invalid OCR token extent")


@dataclass(frozen=True, slots=True)
class AxisSolution:
    scale: str
    slope: float
    intercept: float
    residual: float
    ticks: tuple[tuple[float, float], ...]
    unit: str

    def value_at(self, pixel: float) -> float:
        value = self.slope * pixel + self.intercept
        return 10. ** value if self.scale == "log10" else value


@dataclass(frozen=True, slots=True)
class AxisCandidate:
    axis: str
    solutions: tuple[AxisSolution, ...]
    unresolved: tuple[str, ...]
    tick_bindings: tuple[tuple[OCRToken, tuple[float, ...]], ...] = ()

    @property
    def resolved(self) -> bool:
        return len(self.solutions) == 1 and not self.unresolved


@dataclass(frozen=True, slots=True)
class PlotCandidate:
    candidate_id: str
    bbox: tuple[int, int, int, int]
    axes: tuple[AxisCandidate, ...]


@dataclass(frozen=True, slots=True)
class PixelSupport:
    pixel_id: str
    x: int
    y: int
    shared_group: str = ""


@dataclass(frozen=True, slots=True)
class PathCandidate:
    candidate_id: str
    plot_id: str
    color_class: int
    pixels: tuple[PixelSupport, ...]
    unresolved: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RasterDetection:
    source_sha256: str
    detector_version: str
    receipt: str
    plots: tuple[PlotCandidate, ...]
    paths: tuple[PathCandidate, ...]
    tokens: tuple[OCRToken, ...]
    overlay: bytes
    unresolved: tuple[str, ...]
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceDetection:
    source_sha256: str
    detector_version: str
    receipt: str
    images: tuple[AutomaticImage, ...]
    detections: tuple[RasterDetection, ...]
    unresolved: tuple[str, ...]
    provenance: tuple[str, ...] = AUTOMATIC_SOURCE_POLICY


def _identity(source_hash: str, content: object) -> str:
    canonical = json.dumps((source_hash, DETECTOR_VERSION, content), sort_keys=True,
                           ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_number(text: str) -> float | None:
    text = text.strip().replace("−", "-").replace("–", "-")
    text = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)", lambda m: "^" + m[1].translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")), text)
    text = text.replace(" ", "").replace("×", "*").replace("·", "*")
    try:
        if "10^" in text:
            match = re.fullmatch(r"(?:(-?[\d.]+)\*)?10\^([+-]?\d+)", text)
            if not match:
                return None
            value = float(match[1] or 1) * 10. ** int(match[2])
        else:
            value = float(text)
        return value if math.isfinite(value) else None
    except (ValueError, OverflowError):
        return None


def _associate_units(tokens: tuple[OCRToken, ...]) -> tuple[tuple[OCRToken, ...], tuple[str, ...]]:
    """Associate TSV words beside numeric labels, before tick-based filtering."""
    merged = []
    reasons = set()
    owners: dict[OCRToken, int] = {}
    for token in tokens:
        if parse_number(token.text) is None:
            merged.append(token)
            continue
        left, top, right, bottom = token.bbox
        nearby = []
        for other in tokens:
            if other == token or parse_number(other.text) is not None:
                continue
            a,b,c,d = other.bbox
            overlap = min(bottom,d)-max(top,b)
            if 0 <= a-right <= max(bottom-top,d-b) and overlap > 0:
                nearby.append(other)
        if nearby:
            if len(nearby) != 1:
                reasons.add("axis_unit_association_ambiguous")
            for other in nearby:
                a,b,c,d = other.bbox
                if min(bottom,d)-max(top,b) < .5*min(bottom-top,d-b):
                    reasons.add("axis_unit_association_ambiguous")
                owners[other] = owners.get(other,0)+1
            if len(nearby) == 1:
                token = replace(token,text=f"{token.text} {nearby[0].text}")
        merged.append(token)
    if any(count > 1 for count in owners.values()):
        reasons.add("axis_unit_association_ambiguous")
    return tuple(merged), tuple(sorted(reasons))


def fit_axis(tokens: tuple[OCRToken, ...], axis: str) -> AxisCandidate:
    """Fit redundant token alignments; alternatives survive instead of voting them away."""
    if axis not in ("x", "y"):
        raise ValueError("axis must be x or y")
    tokens, association_reasons = _associate_units(tokens)
    if association_reasons:
        return AxisCandidate(axis, (), association_reasons)
    index = 0 if axis == "x" else 1
    groups: dict[float, list[tuple[float, str]]] = {}
    for token in tokens:
        value = parse_number(token.text)
        unit = ""
        if value is None:
            pieces = token.text.rsplit(" ", 1)
            if len(pieces) == 2:
                value, unit = parse_number(pieces[0]), pieces[1]
        if value is not None:
            position = (token.bbox[index] + token.bbox[index+2]) / 2
            groups.setdefault(position, []).append((value, unit))
    positions = sorted(groups)
    if len(positions) < 3:
        return AxisCandidate(axis, (), ("axis_insufficient_ticks",))
    count = math.prod(len(set(groups[p])) for p in positions)
    if count > MAX_AXIS_COMBINATIONS:
        return AxisCandidate(axis, (), ("axis_candidate_budget",))
    solutions = []
    unit_conflict = False
    for choice in itertools.product(*(sorted(set(groups[p])) for p in positions)):
        values = [v for v, _ in choice]
        units = {u for _, u in choice if u}
        if len(units) > 1:
            unit_conflict = True
            continue
        if not (all(a < b for a,b in zip(values,values[1:])) or all(a > b for a,b in zip(values,values[1:]))):
            continue
        for scale in ("linear", "log10"):
            if scale == "log10" and min(values) <= 0:
                continue
            observed = [math.log10(v) for v in values] if scale == "log10" else values
            mp, mv = sum(positions)/len(positions), sum(observed)/len(observed)
            slope = sum((p-mp)*(v-mv) for p,v in zip(positions,observed)) / sum((p-mp)**2 for p in positions)
            intercept = mv - slope*mp
            residual = max(abs(slope*p+intercept-v) for p,v in zip(positions,observed)) / (max(observed)-min(observed))
            if residual <= .005:
                solutions.append(AxisSolution(scale, slope, intercept, residual,
                    tuple(zip(positions, values)), next(iter(units), "")))
    solutions = sorted(set(solutions), key=lambda s:(s.scale,s.slope,s.intercept,s.ticks))
    reasons = ("axis_multiple_solutions",) if len(solutions)>1 else ()
    if not solutions:
        reasons = ("axis_unit_conflict" if unit_conflict else "axis_inconsistent_ticks",)
    return AxisCandidate(axis, tuple(solutions), reasons)


def _long_lines(image: Image.Image, vertical: bool) -> tuple[tuple[int,int,int], ...]:
    width, height = image.size
    major, minor = (height,width) if vertical else (width,height)
    pixels = image.load()
    minimum = max(40, int(major*.12))
    lines = []
    for fixed in range(minor):
        start = None
        for p in range(major+1):
            dark = p < major and max(pixels[fixed,p] if vertical else pixels[p,fixed]) < 110
            if dark and start is None:
                start = p
            elif not dark and start is not None:
                if p-start >= minimum:
                    item = (fixed,start,p-1)
                    if not any(abs(fixed-f)<=2 and abs(start-a)<=3 and abs(p-1-b)<=3 for f,a,b in lines[-8:]):
                        lines.append(item)
                        if len(lines) >= MAX_LINE_SEGMENTS:
                            return tuple(lines)
                start = None
    return tuple(lines)


def _plots(image: Image.Image) -> tuple[tuple[tuple[int,int,int,int], ...], bool]:
    horizontal, vertical = _long_lines(image, False), _long_lines(image, True)
    boxes = set()
    for bottom,left,right in horizontal:
        for x,top,end in vertical:
            if abs(x-left)<=10 and abs(end-bottom)<=10 and right-left>=60 and bottom-top>=45:
                # Rectangle top edge OR multiple genuine ticks beside the vertical edge.
                closed = any(abs(y-top)<=4 and abs(a-x)<=10 and abs(b-right)<=10 for y,a,b in horizontal)
                pixels = image.load()
                ticks = sum(max(pixels[max(0,x-3),y])<110 for y in range(top+5,bottom-5))
                if closed or ticks >= 3:
                    mid_x,mid_y = (x+right)//2,(top+bottom)//2
                    # Normalize duplicate edge detections to the connected ink's
                    # outer extent, without merging across a white separation.
                    boxes.add((_ink_span(image,x,mid_y,False)[0],
                               _ink_span(image,mid_x,top,True)[0],
                               _ink_span(image,right,mid_y,False)[1],
                               _ink_span(image,mid_x,bottom,True)[1]))
    return tuple(sorted(boxes)), max(len(horizontal),len(vertical)) >= MAX_LINE_SEGMENTS


def _ink_span(image: Image.Image, x: int, y: int, vertical: bool) -> tuple[int,int]:
    pixels=image.load()
    position=y if vertical else x
    limit=image.height if vertical else image.width
    if max(pixels[x,y])>=110:
        return position,position
    start=end=position
    def dark(p):
        return max(pixels[x,p] if vertical else pixels[p,y])<110
    while start>0 and dark(start-1):
        start-=1
    while end+1<limit and dark(end+1):
        end+=1
    return start,end


def _axis_ink_mask(image: Image.Image, box: tuple[int,int,int,int]) -> set[tuple[int,int]]:
    left,top,right,bottom=box
    mask=set()
    for x in range(left,right+1):
        for edge in (top,bottom):
            start,end=_ink_span(image,x,edge,True)
            mask.update((x,y) for y in range(start,end+1))
    for y in range(top,bottom+1):
        for edge in (left,right):
            start,end=_ink_span(image,edge,y,False)
            mask.update((x,y) for x in range(start,end+1))
    return mask


def _color(pixel: tuple[int,int,int]) -> int | None:
    if max(pixel) < 110:
        return 0
    if max(pixel)-min(pixel) < 60 or min(pixel)>210:
        return None
    # Six broad hue classes; color is support, never a scientific identity.
    r,g,b = pixel
    return 1 + ((0 if g>=b else 5) if r==max(pixel) else
                (2 if b>=r else 1) if g==max(pixel) else (4 if r>=g else 3))


def _paths(image: Image.Image, box: tuple[int,int,int,int], tokens: tuple[OCRToken,...]):
    left,top,right,bottom = box
    pixels = image.load()
    axis_mask = _axis_ink_mask(image,box)
    masks = [t.bbox for t in tokens if t.bbox[0]<right and t.bbox[2]>left and t.bbox[1]<bottom and t.bbox[3]>top]
    active = []
    finished = []
    budget_hit = False
    for x in range(left+2,right-1):
        column: dict[int,list[list[int]]] = {}
        for y in range(top+2,bottom-1):
            if (x,y) in axis_mask or any(a<=x<c and b<=y<d for a,b,c,d in masks):
                continue
            color = _color(pixels[x,y])
            if color is None:
                continue
            groups = column.setdefault(color,[])
            if groups and y == groups[-1][-1]+1:
                groups[-1].append(y)
            else:
                groups.append([y])
        # Thick vertical components are glyphs/markers, not a resolved line column.
        nodes = [(color,ys) for color,groups in sorted(column.items()) for ys in groups if len(ys)<=8]
        used = set()
        updated = []
        for color,points,ambiguous in active:
            last = points[-1][1]
            slope = points[-1][1]-points[-2][1] if len(points)>1 else 0
            candidates = [(min(abs(y-(last+slope)) for y in ys),i,ys) for i,(c,ys) in enumerate(nodes) if c==color and min(abs(y-last) for y in ys)<=4]
            if not candidates:
                finished.append((color,points,ambiguous))
                continue
            _, i, ys = min(candidates)
            y = min(ys, key=lambda v:(abs(v-(last+slope)),v))
            used.add(i)
            updated.append((color,points+[(x,y)],ambiguous or len(candidates)>1))
        for i,(color,ys) in enumerate(nodes):
            if i not in used and len(updated)<MAX_PATHS:
                updated.append((color,[(x,ys[len(ys)//2])],False))
            elif i not in used:
                budget_hit = True
        active = updated
    finished.extend(active)
    minimum = max(30,int((right-left)*.18))
    return sorted((c,tuple(p),a) for c,p,a in finished if len(p)>=minimum), budget_hit


def _tick_aligned(image: Image.Image, tokens: tuple[OCRToken,...], axis: str,
                  box: tuple[int,int,int,int]) -> tuple[tuple[OCRToken,tuple[float,...]],...]:
    """Require perpendicular ink extending from the detected axis near each label."""
    left,top,right,bottom = box
    pixels = image.load()
    accepted = []
    for token in tokens:
        index = 0 if axis == "x" else 1
        center = round((token.bbox[index]+token.bbox[index+2])/2)
        found = set()
        for position in range(center-2,center+3):
            for direction in (-1,1):
                coordinates = [(position,bottom+direction*d) if axis == "x" else
                               (left+direction*d,position) for d in range(2,5)]
                if all(0<=x<image.width and 0<=y<image.height and max(pixels[x,y])<110 for x,y in coordinates):
                    found.add(float(position))
        if found:
            accepted.append((token,tuple(sorted(found))))
    return tuple(accepted)


def _fit_tick_axis(image: Image.Image, tokens: tuple[OCRToken,...], axis: str,
                   box: tuple[int,int,int,int]) -> AxisCandidate:
    tokens,reasons = _associate_units(tokens)
    if reasons:
        return AxisCandidate(axis,(),reasons)
    # Only numeric labels own tick matches; neighboring words remain OCR anchors.
    numeric = tuple(t for t in tokens if parse_number(t.text) is not None or
                    parse_number(t.text.rsplit(" ",1)[0]) is not None)
    bindings = _tick_aligned(image,numeric,axis,box)
    if math.prod(len(positions) for _,positions in bindings)>MAX_AXIS_COMBINATIONS:
        return AxisCandidate(axis,(),("axis_candidate_budget",),bindings)
    solutions=set()
    failures=set()
    index=0 if axis=="x" else 1
    for choice in itertools.product(*(positions for _,positions in bindings)):
        aligned=[]
        for (token,_),position in zip(bindings,choice):
            bbox=list(token.bbox)
            delta=position-(bbox[index]+bbox[index+2])/2
            bbox[index]+=delta; bbox[index+2]+=delta
            aligned.append(replace(token,bbox=tuple(bbox)))
        candidate=fit_axis(tuple(aligned),axis)
        solutions.update(candidate.solutions)
        failures.update(candidate.unresolved)
    ordered=tuple(sorted(solutions,key=lambda s:(s.scale,s.slope,s.intercept,s.ticks)))
    reasons = ("axis_tick_association_ambiguous",) if any(len(p)>1 for _,p in bindings) else ()
    if len(ordered)>1:
        reasons += ("axis_multiple_solutions",)
    if not ordered:
        reasons = tuple(sorted(set(reasons)|failures))
    return AxisCandidate(axis,ordered,reasons,bindings)


def detect_raster(content: bytes, tokens: tuple[OCRToken,...]) -> RasterDetection:
    """Pure raster/token adapter boundary; not an externally writable geometry request."""
    source_hash = hashlib.sha256(content).hexdigest()
    tokens = tuple(sorted(set(tokens),key=lambda t:(t.bbox,t.text,t.source)))
    reasons = []
    if len(tokens)>MAX_TOKENS:
        tokens = tokens[:MAX_TOKENS]
        reasons.append("ocr_token_budget")
    with Image.open(io.BytesIO(content)) as source:
        if source.width*source.height>2_560_000:
            raise ValueError("detector canonical pixel budget exceeded")
        image = source.convert("RGB")
    boxes,line_budget_hit = _plots(image)
    if line_budget_hit:
        reasons.append("line_candidate_budget")
    if len(boxes)>MAX_PLOTS:
        reasons.append("plot_candidate_budget")
    plots, paths = [], []
    for box in boxes[:MAX_PLOTS]:
        left,top,right,bottom = box
        x_tokens = tuple(t for t in tokens if left-8 <= (t.bbox[0]+t.bbox[2])/2 <= right+8 and bottom <= t.bbox[1] <= bottom+35)
        y_tokens = tuple(t for t in tokens if top-8 <= (t.bbox[1]+t.bbox[3])/2 <= bottom+8 and left-65 <= t.bbox[2] <= left)
        axes = (_fit_tick_axis(image,x_tokens,"x",box),
                _fit_tick_axis(image,y_tokens,"y",box))
        plot_id = _identity(source_hash, (box, [asdict(a) for a in axes]))
        plots.append(PlotCandidate(plot_id,box,axes))
        raw_paths,path_budget_hit = _paths(image,box,tokens)
        if path_budget_hit or len(raw_paths)>MAX_PATHS:
            reasons.append("path_candidate_budget")
        for color, points, ambiguous in raw_paths[:MAX_PATHS]:
            supports = tuple(PixelSupport(_identity(source_hash,("pixel",x,y)),x,y) for x,y in points)
            unresolved = ("identity_unbound",) + (("path_junction_ambiguous",) if ambiguous else ())
            if points[0][0] > left+2 or points[-1][0] < right-2:
                unresolved += ("path_partial_visible_support",)
            if not all(axis.resolved for axis in axes):
                unresolved += ("axes_unresolved",)
            paths.append(PathCandidate(_identity(source_hash,(plot_id,color,points)), plot_id,color,supports,unresolved))
    counts: dict[str,int] = {}
    for path in paths:
        for pixel in path.pixels:
            counts[pixel.pixel_id] = counts.get(pixel.pixel_id,0)+1
    paths = [replace(path,pixels=tuple(replace(p,shared_group=p.pixel_id if counts[p.pixel_id]>1 else "") for p in path.pixels),
        unresolved=tuple(sorted(set(path.unresolved+(("path_junction_ambiguous",) if any(counts[p.pixel_id]>1 for p in path.pixels) else ()))))) for path in paths]
    paths = [replace(path,candidate_id=_identity(source_hash,asdict(replace(path,candidate_id="")))) for path in paths]
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    for index,plot in enumerate(plots):
        draw.rectangle(plot.bbox,outline=(0,150,230),width=1)
        draw.text((plot.bbox[0]+3,plot.bbox[1]+3),f"P{index+1}",fill=(0,150,230))
    for index,path in enumerate(paths):
        for p in path.pixels:
            draw.point((p.x,p.y),fill=(255,0,220))
        p = path.pixels[len(path.pixels)//2]
        draw.text((p.x,p.y+3),f"L{index+1}",fill=(0,120,150))
    for token in tokens:
        draw.rectangle(token.bbox,outline=(230,170,0))
    if not plots:
        reasons.append("plot_not_found")
    elif not paths:
        reasons.append("path_not_found")
    receipt = _identity(source_hash,([asdict(p) for p in plots],[asdict(p) for p in paths],[asdict(t) for t in tokens],sorted(set(reasons)),POLICY,PILLOW_VERSION))
    return RasterDetection(source_hash,DETECTOR_VERSION,receipt,tuple(plots),tuple(paths),tokens,
                           _png_bytes(overlay),tuple(sorted(set(reasons))),POLICY+(f"Pillow {PILLOW_VERSION}",))


def _ocr(content: bytes) -> tuple[tuple[OCRToken,...], tuple[str,...], str]:
    from .figure_dependencies import RUNTIME_CONTRACT, ocr_command, verify_ocr
    executable = RUNTIME_CONTRACT["executables"].get("tesseract")
    if executable is None:
        return (), ("ocr_dependency_unavailable:tesseract",), "tesseract unavailable"
    version = verify_ocr(RUNTIME_CONTRACT)
    environment = {**os.environ, "OMP_NUM_THREADS": "1", "OMP_THREAD_LIMIT": "1"}
    environment.pop("TESSDATA_PREFIX", None)
    # The installed, compiled contract fixes the executable and adapter; no caller flags.
    with tempfile.TemporaryDirectory(prefix="scid-ocr-") as directory:
        path = Path(directory)/"image.png"
        path.write_bytes(content)
        try:
            result = subprocess.run(ocr_command(RUNTIME_CONTRACT, path),capture_output=True,check=True,timeout=60,
                env=environment)
        except (OSError,subprocess.SubprocessError) as error:
            raise RuntimeError("OCR executable failed") from error
    tokens = []
    for row in csv.DictReader(io.StringIO(result.stdout.decode()),delimiter="\t"):
        if row.get("text", "").strip() and int(row["width"])>0 and int(row["height"])>0:
            x,y,w,h = (float(row[k]) for k in ("left","top","width","height"))
            tokens.append(OCRToken(row["text"],(x,y,x+w,y+h),version))
    return tuple(tokens), (), version


def detect_source(content: bytes) -> SourceDetection:
    """Raw source only: no page, object, scientific labels, geometry or tuning."""
    recovery = recover_automatic_source(content)
    detections = []
    unresolved = list(recovery.unresolved)
    for frame in recovery.images:
        tokens,reasons,version = _ocr(frame.content)
        result = detect_raster(frame.content,tokens)
        # Rebind candidates to the document plus frame, never a hidden image identity.
        binding = _identity(recovery.source_sha256,(frame.image_sha256,frame.page,frame.kind,frame.pdf_object))
        plot_ids = {p.candidate_id:_identity(binding,asdict(p)) for p in result.plots}
        plots = tuple(replace(p,candidate_id=plot_ids[p.candidate_id]) for p in result.plots)
        paths = tuple(replace(p,candidate_id=_identity(binding,asdict(p)),plot_id=plot_ids[p.plot_id],
            unresolved=tuple(sorted(set(p.unresolved+(("text_mask_unavailable",) if reasons else ())))),
            pixels=tuple(replace(v,pixel_id=_identity(binding,(v.x,v.y)),shared_group=_identity(binding,(v.x,v.y)) if v.shared_group else "") for v in p.pixels)) for p in result.paths)
        detections.append(replace(result,source_sha256=recovery.source_sha256,plots=plots,paths=paths,
            receipt=_identity(binding,(result.receipt,version,reasons)),
            unresolved=tuple(sorted(set(result.unresolved+reasons))),provenance=result.provenance+(version,)))
        unresolved.extend(reasons)
    receipt = _identity(recovery.source_sha256,([d.receipt for d in detections],
        [asdict(replace(f,content=b"")) | {"content":""} for f in recovery.images], sorted(set(unresolved)),recovery.provenance))
    return SourceDetection(recovery.source_sha256,DETECTOR_VERSION,receipt,recovery.images,
                           tuple(detections),tuple(sorted(set(unresolved))))
