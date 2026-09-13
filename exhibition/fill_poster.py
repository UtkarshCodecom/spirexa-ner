"""Fills the AIC Hub A0 poster template with SPIREXA project content.

Edits by shape NAME (for blank bullet placeholders) or by exact CURRENT TEXT
(for header/labelled fields), and only ever rewrites run.text — never
paragraph.text — so the template's fonts, sizes and colors survive untouched.
"""

from pptx import Presentation
from pptx.util import Inches, Pt

SRC = "A0_poster_template.pptx"
OUT = "A0_Poster_SPIREXA.pptx"
ASSETS = "/Users/utkarsh/Desktop/ml/.docxbuild/assets26"


def set_text(shape, new_text):
    """Rewrites a shape's visible text via its first run, preserving formatting."""
    if shape is None or not shape.has_text_frame:
        print(f"  WARNING: shape not found for text: {new_text[:50]!r}")
        return False
    tf = shape.text_frame
    if not tf.paragraphs or not tf.paragraphs[0].runs:
        tf.paragraphs[0].text = new_text
        return True
    tf.paragraphs[0].runs[0].text = new_text
    for r in tf.paragraphs[0].runs[1:]:
        r.text = ""
    for p in tf.paragraphs[1:]:
        for r in p.runs:
            r.text = ""
    return True


def by_name(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


def set_bullet(slide, shp_name, text):
    """Like set_text, but for the section bullet placeholders: these ship
    with zero run formatting (an empty <a:p/>), so they silently inherit
    the master's default text size -- too large for the template's tight
    0.62in row spacing, which is what caused wrapped bullets to overlap
    the next bullet below them. Setting an explicit size fixes that."""
    shape = by_name(slide, shp_name)
    if not set_text(shape, text):
        return
    run = shape.text_frame.paragraphs[0].runs[0]
    run.font.size = Pt(16)
    run.font.name = "Calibri"




def by_text(slide, text):
    for sh in slide.shapes:
        if sh.has_text_frame and sh.text_frame.text.strip() == text:
            return sh
    return None


def fit_picture(slide, path, box, pad=0.06):
    """Adds an image centered inside (left, top, width, height), in inches,
    preserving its aspect ratio rather than stretching it to fill the box."""
    from PIL import Image

    left, top, w, h = box
    iw, ih = Image.open(path).size
    box_ratio, img_ratio = w / h, iw / ih
    if img_ratio > box_ratio:
        draw_w = w - 2 * pad
        draw_h = draw_w / img_ratio
    else:
        draw_h = h - 2 * pad
        draw_w = draw_h * img_ratio
    x = left + (w - draw_w) / 2
    y = top + (h - draw_h) / 2
    slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(draw_w), Inches(draw_h))


def check(shape, option_text):
    """Marks one specific '□ Option' as '☑ Option', leaving any other
    options in the same text box (e.g. a shared checkbox line) untouched."""
    if shape is None or not shape.has_text_frame:
        print(f"  WARNING: checkbox shape not found for: {option_text!r}")
        return
    full = shape.text_frame.text
    target = f"□ {option_text}"
    if target not in full:
        print(f"  WARNING: checkbox option text not found: {option_text!r} in {full!r}")
        return
    set_text(shape, full.replace(target, f"☑ {option_text}"))


pres = Presentation(SRC)

# Delete slide 1 (the "how to fill this template" instructions) -- not part
# of the actual submission.
xml_slides = pres.slides._sldIdLst
slides = list(xml_slides)
xml_slides.remove(slides[0])

slide = pres.slides[0]

# ---------------------------------------------------------------- header --
by_text(slide, "2-DAY STARTUP EXHIBITION CUM FUNDING OPPORTUNITIES EVENT")
set_text(by_text(slide, "2-DAY STARTUP EXHIBITION CUM FUNDING OPPORTUNITIES EVENT"),
         "AIC HUB 2026 – STUDENT PROJECT, PROTOTYPE & INNOVATION EXHIBITION")
set_text(by_text(slide, "19ᵗʰ – 20ᵗʰ June, 2026"), "14th September, 2026")
set_text(by_text(slide, "IIIT Allahabad"), "IIIT Allahabad")
set_text(by_text(slide, "STARTUP / INNOVATION / PROJECT TITLE"),
         "SPIREXA — AI Landslide Early Warning System")
set_text(by_name(slide, "Text 13"), "Team SPIREXA  ·  SIH 2026, PS 26001")
set_text(by_name(slide, "Text 14"),
         "Founder / Team Lead: Utkarsh & Team")
# Text 16/17 are template-original content we never intended to touch, but
# at their template-given width both already wrap to 2 lines on their own
# (17 chars in a 3.1in box; 85 chars of checkbox options in an 11.9in box).
# Tighten the inter-option spacing and widen the row to keep it to 1 line.
set_text(by_name(slide, "Text 16"), "IIITA:")
set_text(by_name(slide, "Text 17"),
         "□ Incubated Startup  □ Student Startup  □ Student Innovation  □ Alumni Startup")
by_name(slide, "Text 17").width = Inches(15)
check(by_name(slide, "Text 17"), "Student Innovation")
set_text(by_name(slide, "Text 19"), "SPIREXA")

# --------------------------------------------------- 01 PROBLEM / NEED ----
bullets_01 = [
    "North-East India suffers frequent, high-fatality landslides every monsoon — roads, homes and lifeline infrastructure are cut off for days.",
    "Monitoring today is reactive: action is taken only after a slope has already failed, not before.",
    "One landslide at NHPC's Teesta-V station (Sikkim, Aug 2024) alone caused a loss of Rs 327 crore.",
    "329 deaths are recorded in the historical landslide events we studied for this project.",
    "There is no region-specific, daily-updating early warning system for the North-East today.",
]
for shp_name, text in zip(["Shape 27", "Shape 29", "Shape 31", "Shape 33", "Shape 35"], bullets_01):
    set_bullet(slide, shp_name, text)
set_text(by_name(slide, "Text 37"), "Rs 327 crore lost in a single landslide — NHPC Teesta-V, Sikkim, Aug 2024")

# --------------------------------------------- 02 MOTIVATION / OPPORTUNITY -
bullets_02 = [
    "Five satellite missions (rainfall, soil moisture, terrain, vegetation, radar) are now free and queryable in real time via Google Earth Engine.",
    "NASA's own global warning system, LHASA, proves that satellite data + machine learning is a viable approach at scale.",
    "IIT Mandi has already proven low-cost ground sensors work in Indian mountain terrain, at ~Rs 1 lakh per site.",
    "Smart India Hackathon Problem Statement 26001 explicitly calls for exactly this: an AI-based early warning system for NER.",
    "No existing system combines region-specific ML, live satellite data, and field-level sensing in one platform.",
]
for shp_name, text in zip(["Shape 45", "Shape 47", "Shape 49", "Shape 51", "Shape 53"], bullets_02):
    set_bullet(slide, shp_name, text)
set_text(by_name(slide, "Text 43"), "Why now: free satellite data + proven ML approach + a validated hardware precedent")
set_text(by_name(slide, "Text 55"),
         "The building blocks already exist: free satellite data, a proven "
         "ML approach, a validated low-cost sensor design. No one has combined them for NER yet.")

# ----------------------------------------------- 03 PROPOSED SOLUTION -----
bullets_03 = [
    "Give SPIREXA any coordinate and any date in the North-East — it returns a landslide risk percentage in about 10 seconds.",
    "A live GIS dashboard tracks 311 known danger spots across all 8 North-Eastern states, recalculated every day.",
    "Automated alerts are generated in 9 regional languages, ready for SMS delivery to basic phones.",
    "An offline-capable field app lets officers report hazards with no network signal.",
]
for shp_name, text in zip(["Shape 63", "Shape 65", "Shape 67", "Shape 69"], bullets_03):
    set_bullet(slide, shp_name, text)

# ------------------------------------------------------- 04 HOW IT WORKS --
set_text(by_name(slide, "Text 79"), "Satellites + Sensor")
set_text(by_name(slide, "Text 82"), "17 Features → ML")
set_text(by_name(slide, "Text 85"), "Risk Score")
set_text(by_name(slide, "Text 88"), "Alert Issued")
set_text(by_name(slide, "Text 90"),
         "Pipeline: 5 satellites + ground sensor → 17 features → Random "
         "Forest → risk % → alert, end-to-end in about 10 seconds.")

# --------------------------------------------------- 05 PROTOTYPE/PRODUCT -
set_text(by_name(slide, "Text 96"), "Screenshots of the live system — not mockups.")
# Text 98's placeholder caption is wider than the hero image placed over it
# below (image is aspect-fit and narrower than the box), so it would peek
# out on both sides if left as is. The image speaks for itself; clear it.
set_text(by_name(slide, "Text 98"), "")

# ---------------------------------------------- 06 KEY FEATURES/INNOVATION-
bullets_06 = [
    "Trained on 318 real, documented NER landslides (2007–2025) — not a generic global model.",
    "We caught a reporting bias: the model had learned “near roads” meant risk, not “steep and wet” — which under-warns remote villages.",
    "Terrain is read across a 300 m neighbourhood, not one point — coordinates usually mark where debris stopped, not the failure site.",
    "USGS slope-stability physics is combined with machine learning, not either alone.",
    "Works offline, and alerts render in 9 regional languages automatically.",
]
for shp_name, text in zip(["Shape 110", "Shape 112", "Shape 114", "Shape 116", "Shape 118"], bullets_06):
    set_bullet(slide, shp_name, text)
set_text(by_name(slide, "Text 120"),
         "What sets SPIREXA apart: region-specific training data, physics-"
         "informed features, and a caught-and-corrected reporting bias.")

# ------------------------------------------------- 07 APPLICATIONS/IMPACT -
bullets_07 = [
    "District administrations get a daily ranked watch-list instead of a phone call after the slope has already gone.",
    "Remote villages receive warnings in their own language, on basic phones, with no internet required.",
    "Road and power authorities see exactly which assets sit below an at-risk slope.",
    "Field officers get an offline reporting tool that syncs automatically when signal returns.",
]
for shp_name, text in zip(["Shape 128", "Shape 130", "Shape 132", "Shape 134"], bullets_07):
    set_bullet(slide, shp_name, text)
set_text(by_name(slide, "Text 136"),
         "From district control rooms to individual field officers — one "
         "system, ranked by urgency, in a language people actually read.")

# --------------------------------------- 08 CURRENT STATUS & FUTURE PLAN --
bullets_08 = [
    "Working today: satellite pipeline, ML model, GIS dashboard, prediction API, 9-language alerts, offline field app.",
    "In progress: an Arduino ground-sensor node feeding live rainfall and soil readings into the same dashboard.",
    "Planned: SMS gateway integration — message logic is ready, only a paid account is missing.",
    "Planned: a validation partnership with GSI or a state disaster management authority.",
]
for shp_name, text in zip(["Shape 144", "Shape 146", "Shape 148", "Shape 150"], bullets_08):
    set_bullet(slide, shp_name, text)
set_text(by_name(slide, "Text 152"), "Software\nworking")
set_text(by_name(slide, "Text 155"), "Sensor\nnetwork")
set_text(by_name(slide, "Text 158"), "Official\nadoption")

# ------------------------------------------- 09 DEMO / SUPPORTING MATERIAL-
# The individual link fields (video/deck/brochure/patent/media/demo-req) are
# genuinely blank for us right now -- honest to leave them for on-site fill-in
# rather than fabricate links that don't exist. The one field we DO have a
# real answer for is the callout box, which we point at the GitHub repo.
set_text(by_name(slide, "TextBox 260"),
         "github.com/UtkarshCodecom/spirexa-ner — full source, live dashboard demo, and the Arduino sensor code")

# ------------------------------------------ 10 KEY METRICS / ACHIEVEMENTS -
set_text(by_name(slide, "TextBox 268"), "Users / customers:")
set_text(by_name(slide, "TextBox 271"), "Pilot / deployment:")
set_text(by_name(slide, "TextBox 274"), "Revenue / grant:")
set_text(by_name(slide, "TextBox 277"), "TRL / stage:")
set_text(by_name(slide, "TextBox 280"), "Awards:")
set_text(by_name(slide, "TextBox 283"), "Validation data:")
set_text(by_name(slide, "TextBox 286"),
         "0.933 ROC-AUC (5-fold cross-validated)  ·  87% of 318 real historical landslides "
         "flagged in advance  ·  311 hotspots monitored daily  ·  TRL-4 (validated in a "
         "simulated / lab environment, not yet field-deployed)")

# ---------------------------------------------------- footer: contact -----
set_text(by_name(slide, "Text 162"), "GitHub:")
set_text(by_name(slide, "Shape 163"), "github.com/UtkarshCodecom/spirexa-ner")
set_text(by_name(slide, "Shape 167"), "yushkarsh@gmail.com")

# ---------------------------------------------------- footer: looking for -
check(by_name(slide, "Text 179"), "Mentorship")
check(by_name(slide, "Text 180"), "Technology Partnership")
check(by_name(slide, "Text 181"), "Pilot / Deployment Opportunities")

set_text(by_name(slide, "Text 188"), "#SPIREXA")

# ------------------------------------------------------------- images -----
fit_picture(slide, f"{ASSETS}/architecture2.png", (11.83, 11.2, 9.44, 3.47))
# Section 05's big hero-image slot (Shape 97) still showed its placeholder
# icon + "Insert high-quality photos..." text -- only the 4 small thumbnails
# below it had been filled. Cover it with the flagship dashboard screenshot.
fit_picture(slide, f"{ASSETS}/dashboard_full.png", (11.83, 25.77, 9.44, 3.3))
fit_picture(slide, f"{ASSETS}/dashboard_full.png", (11.98, 29.77, 1.6, 0.92))
fit_picture(slide, f"{ASSETS}/map_clean.png", (14.36, 29.77, 1.6, 0.92))
fit_picture(slide, f"{ASSETS}/iot_node.png", (16.74, 29.77, 1.6, 0.92))
fit_picture(slide, f"{ASSETS}/risk_triangle.png", (19.12, 29.77, 1.6, 0.92))
fit_picture(slide, "/Users/utkarsh/Desktop/ml/exhibition/qr_github.png", (9.9, 41.33, 3.65, 3.05))
set_text(by_name(slide, "Text 173"), "QR CODE — scan for the live project & source code")

pres.save(OUT)
print("saved", OUT)
