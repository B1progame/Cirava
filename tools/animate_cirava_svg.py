from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET


SRC = Path(r"C:\Users\bslid.BENJI-PC\Downloads\trace (2).svg")
OUT = Path("public/cirava-logo-animated.svg")
SVG_NS = "http://www.w3.org/2000/svg"
DURATION = "10.5s"
ET.register_namespace("", SVG_NS)


def q(name: str) -> str:
    return f"{{{SVG_NS}}}{name}"


def animate_rect(rect: ET.Element, *, x: str, y: str, width: str, height: str,
                 x_values: str, values: str, key_times: str, key_splines: str,
                 y_values: str | None = None, height_values: str | None = None) -> None:
    rect.set("x", x)
    rect.set("y", y)
    rect.set("width", width)
    rect.set("height", height)
    a = ET.SubElement(rect, q("animate"), {
        "attributeName": "x",
        "dur": DURATION,
        "repeatCount": "indefinite",
        "values": x_values,
        "keyTimes": key_times,
        "keySplines": key_splines,
        "calcMode": "spline",
        "begin": "0s",
        "fill": "freeze",
    })
    a.set("data-svgator-channel", "mask.x")
    if y_values and y_values != ";".join([y] * len(key_times.split(";"))):
        ay = ET.SubElement(rect, q("animate"), {
            "attributeName": "y", "dur": DURATION, "repeatCount": "indefinite",
            "values": y_values, "keyTimes": key_times, "keySplines": key_splines,
            "calcMode": "spline", "begin": "0s", "fill": "freeze",
            "data-svgator-channel": "mask.y",
        })
    if height_values and height_values != ";".join([height] * len(key_times.split(";"))):
        ah = ET.SubElement(rect, q("animate"), {
            "attributeName": "height", "dur": DURATION, "repeatCount": "indefinite",
            "values": height_values, "keyTimes": key_times, "keySplines": key_splines,
            "calcMode": "spline", "begin": "0s", "fill": "freeze",
            "data-svgator-channel": "mask.height",
        })
    aw = ET.SubElement(rect, q("animate"), {
        "attributeName": "width",
        "dur": DURATION,
        "repeatCount": "indefinite",
        "values": values,
        "keyTimes": key_times,
        "keySplines": key_splines,
        "calcMode": "spline",
        "begin": "0s",
        "fill": "freeze",
    })
    aw.set("data-svgator-channel", "mask.width")


def make_mask(mask_id: str, values: str, key_times: str, key_splines: str,
              *, x: str, y: str, height: str, x_values: str | None = None,
              y_values: str | None = None, height_values: str | None = None) -> ET.Element:
    mask = ET.Element(q("mask"), {"id": mask_id, "maskUnits": "userSpaceOnUse",
                                   "x": "0", "y": "0", "width": "872", "height": "871"})
    rect = ET.SubElement(mask, q("rect"), {"fill": "white"})
    animate_rect(rect, x=x, y=y, width=values.split(";")[0], height=height,
                 x_values=x_values or ";".join([x] * len(key_times.split(";"))),
                 values=values, key_times=key_times, key_splines=key_splines,
                 y_values=y_values, height_values=height_values)
    return mask


def main() -> None:
    root = ET.parse(SRC).getroot()
    paths = list(root.findall(q("path")))
    assert len(paths) == 39, f"Unexpected source path count: {len(paths)}"

    # Source order is preserved. These indices are the traced artwork's existing
    # visual families; no path geometry or paint is rewritten.
    family_by_index = {}
    for i in [2, 3, 4, 5, 6, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]:
        family_by_index[i] = "blue"
    for i in [7, 8, 9, 10, 11, 12]:
        family_by_index[i] = "green"
    for i in [25, 26, 27, 28, 29]:
        family_by_index[i] = "yellow"
    for i in [30, 31, 35, 36]:
        family_by_index[i] = "red-body"
    for i in [32, 33, 34]:
        family_by_index[i] = "red-arrow"
    background_indices = {1, 37, 38, 39}

    out_root = ET.Element(root.tag, root.attrib)
    out_root.set("role", "img")
    out_root.set("aria-label", "Cirava logo")
    out_root.set("data-svgator-motion", "native-mask-reveal")
    defs = ET.SubElement(out_root, q("defs"))

    # Premium ease-in-out segments. Hold the blue arrow for 2 seconds, reveal
    # green -> blue top -> yellow -> red body -> red arrow, hold the red arrow
    # for 0.5 seconds, then reverse the same route back to the blue arrow.
    spline5 = "0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1"
    spline4 = "0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1;0.4 0 0.2 1"
    spline7 = spline5 + ";0.4 0 0.2 1;0.4 0 0.2 1"
    masks = {
        "blue": make_mask("mask-blue", "140;140;140;140;650;650;140;140", "0;0.190476;0.214286;0.285714;0.357143;0.847619;0.923810;1", spline7,
                           x="365", y="280", height="315",
                           x_values="365;365;365;365;100;100;365;365",
                           y_values="280;280;280;280;145;145;280;280",
                           height_values="315;315;315;315;430;430;315;315"),
        "green": make_mask("mask-green", "0;0;300;300;0", "0;0.214286;0.285714;0.923810;1", spline4,
                            x="95", y="330", height="300"),
        "yellow": make_mask("mask-yellow", "0;0;310;310;0;0", "0;0.428571;0.500000;0.771429;0.847619;1", spline5,
                             x="480", y="305", height="380"),
        "red-body": make_mask("mask-red-body", "0;0;390;390;0;0", "0;0.500000;0.571429;0.695238;0.771429;1", spline5,
                          x="365", y="410", height="285"),
        "red-arrow": make_mask("mask-red-arrow", "0;0;390;390;0;0", "0;0.571429;0.619048;0.650000;0.695238;1", spline5,
                          x="365", y="410", height="285"),
    }
    # The traced blue artwork has one tiny overlap above the arrow's left
    # shoulder. Keep that overlap masked only during the opening arrow state;
    # it fades out before the larger blue ribbon is revealed.
    arrow_overlap = ET.SubElement(masks["blue"], q("rect"), {
        "x": "350", "y": "275", "width": "35", "height": "65", "fill": "black"
    })
    ET.SubElement(arrow_overlap, q("animate"), {
        "attributeName": "opacity", "dur": DURATION, "repeatCount": "indefinite",
        "values": "1;1;0;0;1;1",
        "keyTimes": "0;0.190476;0.342857;0.847619;0.923810;1",
        "keySplines": spline5, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-overlap"
    })
    # Start with only the blue triangular head. The tail cutout moves away
    # from the head, revealing the tail from its base downward, then returns
    # during the reverse half of the loop.
    arrow_tail = ET.SubElement(masks["blue"], q("rect"), {
        "x": "365", "y": "385", "width": "160", "height": "210", "fill": "black"
    })
    ET.SubElement(arrow_tail, q("animate"), {
        "attributeName": "y", "dur": DURATION, "repeatCount": "indefinite",
        "values": "385;385;595;595;385",
        "keyTimes": "0;0.190476;0.214286;0.923810;1",
        "keySplines": spline4, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-tail.y"
    })
    ET.SubElement(arrow_tail, q("animate"), {
        "attributeName": "height", "dur": DURATION, "repeatCount": "indefinite",
        "values": "210;210;0;0;210",
        "keyTimes": "0;0.190476;0.214286;0.923810;1",
        "keySplines": spline4, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-tail.height"
    })
    # Widen the opening only across the arrow shoulders so the original left
    # and right corners are included without exposing the upper blue overlap.
    shoulder_band = ET.SubElement(masks["blue"], q("rect"), {
        "x": "340", "y": "345", "width": "200", "height": "85", "fill": "white"
    })
    ET.SubElement(shoulder_band, q("animate"), {
        "attributeName": "opacity", "dur": DURATION, "repeatCount": "indefinite",
        "values": "1;1;0;0;1;1",
        "keyTimes": "0;0.190476;0.214286;0.357143;0.847619;1",
        "keySplines": spline5, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-shoulders"
    })
    # Re-apply the tail cutout after the shoulder selection so the opening
    # contains the triangular head only, without a blue strip underneath it.
    tail_overlay = ET.SubElement(masks["blue"], q("rect"), {
        "x": "365", "y": "385", "width": "160", "height": "210", "fill": "black"
    })
    ET.SubElement(tail_overlay, q("animate"), {
        "attributeName": "y", "dur": DURATION, "repeatCount": "indefinite",
        "values": "385;385;595;595;385",
        "keyTimes": "0;0.190476;0.214286;0.923810;1",
        "keySplines": spline4, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-tail-overlay.y"
    })
    ET.SubElement(tail_overlay, q("animate"), {
        "attributeName": "height", "dur": DURATION, "repeatCount": "indefinite",
        "values": "210;210;0;0;210",
        "keyTimes": "0;0.190476;0.214286;0.923810;1",
        "keySplines": spline4, "calcMode": "spline", "begin": "0s", "fill": "freeze",
        "data-svgator-channel": "mask.arrow-tail-overlay.height"
    })
    for m in masks.values():
        defs.append(m)

    # Put the original paths in a definition so the animated layer can reuse the
    # exact traced geometry without rewriting or duplicating path data.
    artwork = ET.SubElement(defs, q("g"), {"id": "cirava-artwork"})
    for i, path in enumerate(paths, 1):
        p = deepcopy(path)
        p.set("id", f"trace-path-{i:02d}")
        artwork.append(p)

    # Animated layer keeps source element order exactly and masks only the logo
    # families. Background/frame paths remain visible throughout.
    animated = ET.SubElement(out_root, q("g"), {"id": "animated-logo", "class": "animated-layer"})
    for i in range(1, 40):
        ref = ET.SubElement(animated, q("use"), {"href": f"#trace-path-{i:02d}"})
        family = family_by_index.get(i)
        if family:
            ref.set("mask", f"url(#mask-{family})")

    # Native SVGator-style metadata documents the authored timeline without
    # changing the source art or introducing a visible guide/helper element.
    metadata = ET.SubElement(out_root, q("metadata"), {"data-svgator": "true"})
    metadata.text = "duration=10500;iterations=0;direction=1;native=mask.x+mask.width;ease=cubic-bezier(0.4,0,0.2,1);red-arrow-hold=500ms"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(out_root).write(OUT, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
