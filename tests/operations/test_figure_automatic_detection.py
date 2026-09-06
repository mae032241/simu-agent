"""Synthetic algorithm checks; no paper answers or Agent geometry input."""
import inspect
import io
import ast
import subprocess

import pytest
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo

from curve_figure_evidence.figure_detection import (
    OCRToken, detect_source, detect_raster, fit_axis, parse_number,
)
from curve_figure_evidence import figure_source, figure_detection


def drawing(*, gap=False, crossing=False, near_axis=False, label=False):
    image = Image.new("RGB", (320, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 25, 290, 190), outline="black", width=1)
    for x in (50, 170, 290):
        draw.line((x, 190, x, 196), fill="black")
    for y in (25, 105, 190):
        draw.line((44, y, 50, y), fill="black")
    for x in range(54, 287):
        if not gap or not 145 <= x <= 160:
            y = 185 if near_axis else 60 + (x - 54) // 3
            draw.point((x, y), fill="black" if near_axis else "red")
        if crossing:
            draw.point((x, 138 - (x - 54) // 3), fill="red")
    tokens = []
    if label:
        draw.text((110, 82), "red label", fill="red")
        tokens.append(OCRToken("red label", (110., 82., 165., 94.), "synthetic"))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), tuple(tokens)


def test_public_source_api_has_no_geometry_or_tuning_fields():
    assert tuple(inspect.signature(detect_source).parameters) == ("content",)
    assert "LineTrackingConfig" not in inspect.getsource(detect_source)
    assert tuple(inspect.signature(figure_source.recover_automatic_source).parameters) == ("content",)
    for forbidden in ("bbox", "page", "seed", "axis", "ticks", "threshold", "coverage", "max_gap", "point_count", "parameters"):
        with pytest.raises(TypeError):
            detect_source(b"", **{forbidden: 1})
    tree = ast.parse(inspect.getsource(figure_detection))
    assert not any(isinstance(node, ast.ImportFrom) and node.module and
                   any(word in node.module for word in ("figure_geometry", "ingaas", "worker", "operation", "registry"))
                   for node in ast.walk(tree))


@pytest.mark.parametrize(("text", "expected"), [("−2.5", -2.5), ("1.2×10⁻³", .0012), ("2e+3", 2000), ("10^−2", .01)])
def test_numeric_ocr(text, expected):
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("values,scale", [((0, 5, 10), "linear"), ((1, 10, 100), "log10"), ((10, 5, 0), "linear")])
def test_axis_redundancy_and_direction(values, scale):
    tokens = tuple(OCRToken(str(v), (float(p-4), 200., float(p+4), 210.), "synthetic") for p, v in zip((50, 170, 290), values))
    axis = fit_axis(tokens, "x")
    assert axis.resolved and axis.solutions[0].scale == scale
    assert axis.solutions[0].value_at(170) == pytest.approx(values[1])
    assert not fit_axis(tokens[:2], "x").resolved


def test_axis_ties_and_conflicts_are_unresolved():
    tokens = tuple(OCRToken(str(v), (float(p-4), 200., float(p+4), 210.), "synthetic") for p, v in ((50, 0), (170, 5), (290, 10), (50, 10), (170, 15), (290, 20)))
    assert "axis_multiple_solutions" in fit_axis(tokens, "x").unresolved
    y = tuple(OCRToken(str(v), (10., float(p-4), 20., float(p+4)), "synthetic") for p, v in ((25, -5), (105, 0), (185, 5)))
    assert fit_axis(y, "y").solutions[0].slope > 0
    reverse = tuple(OCRToken(str(v), (10., float(p-4), 20., float(p+4)), "synthetic") for p, v in ((25, 5), (105, 0), (185, -5)))
    assert fit_axis(reverse, "y").solutions[0].slope < 0
    mixed = tuple(OCRToken(text, (float(p-4), 200., float(p+4), 210.), "synthetic") for p, text in ((50, "0 V"), (170, "5 A"), (290, "10 V")))
    assert "axis_unit_conflict" in fit_axis(mixed, "x").unresolved


@pytest.mark.parametrize("options", [{}, {"near_axis": True}, {"gap": True}, {"crossing": True}, {"label": True}])
def test_seedless_paths_real_pixels_masks_and_repeatability(options):
    content, tokens = drawing(**options)
    result = detect_raster(content, tokens)
    assert result.plots and result.paths
    assert result == detect_raster(content, tokens)
    assert len({p.candidate_id for p in result.paths}) == len(result.paths)
    image = Image.open(io.BytesIO(content)).convert("RGB")
    for path in result.paths:
        assert all(image.getpixel((p.x, p.y)) != (255, 255, 255) for p in path.pixels)
        if options.get("gap"):
            assert all(not 145 <= p.x <= 160 for p in path.pixels)
        if options.get("label"):
            assert all(not (110 <= p.x < 165 and 82 <= p.y < 94) for p in path.pixels)
    if options.get("crossing"):
        ids = [p.pixel_id for path in result.paths for p in path.pixels]
        assert len(ids) > len(set(ids))
        assert any(p.shared_group for path in result.paths for p in path.pixels)


def test_blank_image_is_explicitly_unresolved():
    stream = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(stream, format="PNG")
    result = detect_raster(stream.getvalue(), ())
    assert not result.plots and "plot_not_found" in result.unresolved


def test_axis_tokens_need_actual_tick_ink_and_both_directions_work():
    content,_ = drawing()
    tokens = tuple(OCRToken(str(v),(float(p-4),200.,float(p+4),210.),"synthetic")
                   for p,v in ((50,10),(170,5),(290,0)))
    tokens += tuple(OCRToken(str(v),(30.,float(p-4),40.,float(p+4)),"synthetic")
                    for p,v in ((25,165),(105,85),(190,0)))
    result = detect_raster(content,tokens)
    assert all(a.resolved for a in result.plots[0].axes)
    assert all(a.solutions[0].slope<0 for a in result.plots[0].axes)
    misplaced = tuple(OCRToken(t.text,(t.bbox[0]+20,t.bbox[1],t.bbox[2]+20,t.bbox[3]),t.source) for t in tokens[:3])
    assert not detect_raster(content,misplaced).plots[0].axes[0].resolved


def test_black_text_crossing_black_curve_is_a_local_gap():
    content,_ = drawing()
    image = Image.open(io.BytesIO(content)).convert("RGB")
    pixels = image.load()
    for x in range(image.width):
        for y in range(image.height):
            if pixels[x,y] == (255,0,0):
                pixels[x,y] = (0,0,0)
    ImageDraw.Draw(image).text((110,82),"text",fill="black")
    stream = io.BytesIO()
    image.save(stream,format="PNG")
    token = OCRToken("text",(110.,82.,150.,96.),"synthetic")
    result = detect_raster(stream.getvalue(),(token,))
    assert result.paths
    assert all(not (110<=p.x<150 and 82<=p.y<96) for path in result.paths for p in path.pixels)
    assert any(p.x<110 for path in result.paths for p in path.pixels)
    assert any(p.x>150 for path in result.paths for p in path.pixels)


@pytest.mark.parametrize("angle,expected", [(0,(0,0,100,200)), (90,(200,0,0,100)), (180,(100,200,0,0)), (270,(0,100,200,0))])
def test_vector_page_render_rotation_and_transform(monkeypatch, angle, expected):
    commands = []
    def command(argv):
        commands.append(argv)
        if argv[0] == "pdfinfo":
            value = f"Pages: 1\nPage 1 size: 100 x 200 pts\nPage 1 rot: {angle}\nPage 1 MediaBox: 0 0 100 200\nPage 1 CropBox: 0 0 100 200\n"
        elif "-v" in argv:
            value = "synthetic Poppler version"
        else:
            assert argv[0] == "pdftoppm" and "-singlefile" in argv
            size = (200,100) if angle in (90,270) else (100,200)
            Image.new("RGB", size, "white").save(argv[-1]+".png")
            value = ""
        return subprocess.CompletedProcess(argv,0,value.encode(),b"")
    monkeypatch.setattr(figure_source,"_automatic_run",command)
    def no_embedded(*args, **kwargs):
        raise ValueError("PDF page contains no recoverable embedded image")
    monkeypatch.setattr(figure_source,"inspect_pdf_images",no_embedded)
    result = figure_source.recover_automatic_source(b"%PDF-synthetic vector only")
    assert len(result.images) == 1
    frame = result.images[0]
    assert frame.kind == "page_render" and frame.pdf_object is None
    a,b,c,d,e,f = frame.transform
    assert (c,f,a*100+b*200+c,d*100+e*200+f) == pytest.approx(expected)
    assert frame.coordinate_space == "unrotated_page_top_left_points"
    assert all(argv[argv.index("-f")+1] == "1" for argv in commands if "-f" in argv)


def test_ocr_missing_and_environment_failure_are_distinct(monkeypatch):
    content,_ = drawing()
    monkeypatch.setattr(figure_detection.shutil,"which",lambda _:None)
    first = detect_source(content)
    assert "ocr_dependency_unavailable:tesseract" in first.unresolved
    assert first == detect_source(content)
    assert first.detections[0].paths
    metadata = PngInfo()
    metadata.add_text("synthetic revision", "same pixels, distinct source")
    stream = io.BytesIO()
    Image.open(io.BytesIO(content)).save(stream,format="PNG",pnginfo=metadata)
    changed = detect_source(stream.getvalue())
    assert changed.source_sha256 != first.source_sha256
    assert changed.detections[0].paths[0].candidate_id != first.detections[0].paths[0].candidate_id
    assert changed.detections[0].overlay == first.detections[0].overlay
    def failure(argv):
        raise RuntimeError("broken renderer")
    monkeypatch.setattr(figure_source,"_automatic_run",failure)
    with pytest.raises(RuntimeError,match="broken renderer"):
        detect_source(b"%PDF-broken environment")


def test_ocr_cli_adapter_is_structured_and_restricted(monkeypatch):
    from curve_figure_evidence import figure_dependencies
    content,_ = drawing()
    monkeypatch.setattr(figure_detection.shutil,"which",lambda _:"/synthetic/tesseract")
    monkeypatch.setattr(figure_dependencies, "RUNTIME_CONTRACT", {
        "executables": {"tesseract": "/synthetic/tesseract"},
        "ocr": {"model_path": "/synthetic/model/eng.traineddata"},
    })
    monkeypatch.setattr(figure_dependencies, "verify_ocr", lambda _: "synthetic tesseract version")
    calls=[]
    def run(argv, **kwargs):
        calls.append(argv)
        output = b"synthetic tesseract version" if "--version" in argv else b"left\ttop\twidth\theight\ttext\n10\t20\t8\t12\t-5\n"
        return subprocess.CompletedProcess(argv,0,output,b"")
    monkeypatch.setattr(figure_detection.subprocess,"run",run)
    tokens,reasons,version = figure_detection._ocr(content)
    assert tokens == (OCRToken("-5", (10.,20.,18.,32.), "synthetic tesseract version"),)
    assert not reasons
    assert calls[-1][-8:] == ["--tessdata-dir", "/synthetic/model", "-l", "eng", "--psm", "11", "-c", "tessedit_create_tsv=1"]


def test_unrecoverable_input_and_generic_byte_budget():
    assert figure_source.recover_automatic_source(b"not an image").unresolved
    result = figure_source.recover_automatic_source(b"x"*(figure_source.AUTOMATIC_MAX_SOURCE_BYTES+1))
    assert result.unresolved == ("source_byte_budget",) and not result.images


def _tick_fixture(*, shifted=False, units=False):
    image = Image.new("RGB", (320,240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50,25,290,190),outline="black")
    tokens=[]
    for x,value,unit in ((70,0,"V"),(170,5,"A"),(270,10,"V")):
        draw.line((x,190,x,196),fill="black")
        center=x+2 if shifted else x
        tokens.append(OCRToken(str(value),(center-4.,200.,center+4.,210.),"synthetic"))
        if units:
            tokens.append(OCRToken(unit,(x+5.,200.,x+13.,210.),"synthetic"))
    stream=io.BytesIO();image.save(stream,format="PNG")
    return stream.getvalue(),tuple(tokens)


def test_g2_tick_fit_uses_actual_ink_not_shifted_ocr_center():
    content,tokens=_tick_fixture(shifted=True)
    axis=detect_raster(content,tokens).plots[0].axes[0]
    assert axis.resolved
    assert [axis.solutions[0].value_at(x) for x in (70,170,270)] == pytest.approx((0,5,10))
    assert tuple(p for p,v in axis.solutions[0].ticks) == (70,170,270)


def test_g2_separate_unit_tokens_cannot_hide_conflict():
    content,tokens=_tick_fixture(units=True)
    axis=detect_raster(content,tokens).plots[0].axes[0]
    assert not axis.resolved and "axis_unit_conflict" in axis.unresolved


def test_g2_multiple_tick_matches_preserve_ambiguity():
    content,tokens=_tick_fixture()
    image=Image.open(io.BytesIO(content)).convert("RGB")
    draw=ImageDraw.Draw(image)
    for x in (70,170,270):
        draw.line((x+2,190,x+2,196),fill="black")
    stream=io.BytesIO();image.save(stream,format="PNG")
    axis=detect_raster(stream.getvalue(),tokens).plots[0].axes[0]
    assert not axis.resolved and "axis_tick_association_ambiguous" in axis.unresolved
    assert all(len(positions)==2 for token,positions in axis.tick_bindings)


def test_g2_adjacent_units_associate_but_uncertain_layout_is_unresolved():
    content,tokens=_tick_fixture(units=True)
    consistent=tuple(OCRToken("V" if t.text=="A" else t.text,t.bbox,t.source) for t in tokens)
    axis=detect_raster(content,consistent).plots[0].axes[0]
    assert axis.resolved and axis.solutions[0].unit=="V"
    ambiguous=consistent+(OCRToken("A",(80.,200.,88.,210.),"synthetic"),)
    assert "axis_unit_association_ambiguous" in detect_raster(content,ambiguous).plots[0].axes[0].unresolved


@pytest.mark.parametrize("defect", [None,"mixed_unit","broken_exponent"])
def test_g2_scientific_tick_tokens_and_separate_exponent_units(defect):
    content,_=_tick_fixture()
    tokens=[]
    for index,(x,label) in enumerate(((70,"1e15"),(170,"1×10^16"),(270,"10¹⁷"))):
        if defect=="broken_exponent" and index==2:
            label="10^x"
        unit="cm⁻²" if defect=="mixed_unit" and index==1 else "cm⁻³"
        tokens.append(OCRToken(label,(x-12.,200.,x+12.,210.),"synthetic CLI TSV"))
        tokens.append(OCRToken(unit,(x+13.,200.,x+33.,210.),"synthetic CLI TSV"))
    axis=detect_raster(content,tuple(tokens)).plots[0].axes[0]
    if defect:
        assert not axis.resolved and not axis.solutions
        reason="axis_unit_conflict" if defect=="mixed_unit" else "axis_insufficient_ticks"
        assert reason in axis.unresolved
    else:
        assert axis.resolved and len(axis.solutions)==1
        solution=axis.solutions[0]
        assert solution.scale=="log10" and solution.unit=="cm⁻³"
        assert tuple(p for p,v in solution.ticks)==(70,170,270)
        assert tuple(solution.value_at(p) for p in (70,170,270))==pytest.approx((1e15,1e16,1e17))


@pytest.mark.parametrize("thickness", [3,5,8])
def test_g2_empty_thick_frame_has_no_path_but_independent_nearby_line_survives(thickness):
    image=Image.new("RGB",(320,240),"white")
    draw=ImageDraw.Draw(image)
    draw.rectangle((50,25,290,190),outline="black",width=thickness)
    stream=io.BytesIO();image.save(stream,format="PNG")
    empty=detect_raster(stream.getvalue(),())
    assert len(empty.plots)==1 and not empty.paths
    y=25+thickness+1
    draw.line((65,y,275,y),fill="black")
    stream=io.BytesIO();image.save(stream,format="PNG")
    nearby=detect_raster(stream.getvalue(),())
    assert len(nearby.plots)==1 and nearby.paths
    assert all(p.y==y for path in nearby.paths for p in path.pixels)


@pytest.mark.parametrize("angle,origin", [(0,(0,0)),(90,(0,0)),(180,(10,20)),(270,(10,20))])
def test_g2_real_poppler_media_box_differs_from_crop_box(angle,origin):
    # Ordinary synthetic vector PDF, no external PDF construction dependency.
    stream=b"99 49 2 2 re f\n"
    x0,y0=origin
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",
             b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
             f"<< /Type /Page /Parent 2 0 R /MediaBox [{x0} {y0} {x0+200} {y0+100}] /CropBox [50 25 150 75] /Rotate {angle} /Resources << >> /Contents 4 0 R >>".encode(),
             b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"endstream"]
    pdf=b"%PDF-1.4\n"; offsets=[0]
    for number,obj in enumerate(objects,1):
        offsets.append(len(pdf));pdf+=f"{number} 0 obj\n".encode()+obj+b"\nendobj\n"
    start=len(pdf)
    pdf+=b"xref\n0 5\n0000000000 65535 f \n"+b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
    pdf+=f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    result=figure_source.recover_automatic_source(pdf)
    assert len(result.images)==1 and result.images[0].kind=="page_render"
    frame=result.images[0]
    assert frame.media_box==(x0,y0,x0+200,y0+100)
    assert frame.crop_box==(50,25,150,75)
    image=Image.open(io.BytesIO(frame.content)).convert("RGB")
    ink=[(x,y) for y in range(image.height) for x in range(image.width) if max(image.getpixel((x,y)))<110]
    center=(sum(x for x,y in ink)/len(ink),sum(y for x,y in ink)/len(ink))
    a,b,c,d,e,f=frame.transform
    x,y=100-x0,y0+100-50
    assert (a*x+b*y+c,d*x+e*y+f)==pytest.approx(center,abs=1)
