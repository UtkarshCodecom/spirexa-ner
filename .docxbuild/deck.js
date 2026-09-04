const pptxgen = require("pptxgenjs");
const A = __dirname + "/assets/";

// ---- palette: earth + monsoon, matched to the SIH template's navy ----
const NAVY = "1F3864";
const NAVY_SOFT = "3A5A8C";
const BLUE = "2E75B6";       // template footer
const INK = "1A1A1A";
const MUTED = "5B6770";
const LINE = "D4DCE6";
const PAPER = "F5F8FB";
const EARTH = "B4632F";      // roads / terrain accent
const EARTH_BG = "FDF4EE";
const GREEN = "15803D";
const GREEN_BG = "EDF7F0";
const RED = "DC2626";
const RED_BG = "FCECEC";
const AMBER = "CA8A04";
const AMBER_BG = "FEF6E0";

const TITLE_FONT = "Cambria";
const BODY = "Calibri";

const W = 13.333, H = 7.5;
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "404 The Optimistics";
pres.title = "Slope Watch — SIH 26001";

// ---------- shared chrome ----------
function chrome(slide, pageNo, titleText) {
  slide.background = { color: "FFFFFF" };

  // team badge (oval, top-left) — mirrors the SIH deck convention
  slide.addShape(pres.ShapeType.ellipse, {
    x: 0.22, y: 0.13, w: 1.42, h: 0.66,
    fill: { color: "FFFFFF" }, line: { color: NAVY, width: 1.4 },
  });
  slide.addText("404 The\nOptimistics", {
    x: 0.22, y: 0.13, w: 1.42, h: 0.66, isTextBox: true,
    align: "center", valign: "middle", fontSize: 10, color: NAVY,
    fontFace: BODY, lineSpacing: 12, margin: 0,
  });

  // SIH logo (from the official template package)
  slide.addImage({ path: A + "sih_logo.png", x: 11.42, y: 0.12, w: 1.72, h: 0.74 });

  if (titleText) {
    slide.addText(titleText, {
      x: 1.75, y: 0.16, w: 9.55, h: 0.68, isTextBox: true,
      align: "center", valign: "middle",
      fontSize: 30, bold: true, color: NAVY, fontFace: TITLE_FONT, margin: 0,
    });
  }

  // template footer
  slide.addShape(pres.ShapeType.rect, {
    x: 0, y: 7.06, w: W, h: 0.44, fill: { color: BLUE },
  });
  slide.addText("@SIH Idea submission- Template", {
    x: 4.4, y: 7.06, w: 4.5, h: 0.44, isTextBox: true,
    align: "center", valign: "middle", fontSize: 11, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
  slide.addText(String(pageNo), {
    x: 12.5, y: 7.06, w: 0.6, h: 0.44, isTextBox: true,
    align: "right", valign: "middle", fontSize: 11, bold: true, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
}

// a titled content card
function card(slide, { x, y, w, h, fill = PAPER, border = LINE }) {
  slide.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.06,
    fill: { color: fill }, line: { color: border, width: 1 },
  });
}

function cardHead(slide, text, { x, y, w, color = NAVY }) {
  slide.addText(text, {
    x, y, w, h: 0.3, isTextBox: true,
    fontSize: 13, bold: true, color, fontFace: BODY, margin: 0, valign: "middle",
  });
}

function bullets(slide, items, opts) {
  slide.addText(
    items.map((t, i) => ({
      text: t,
      options: { bullet: { indent: 14 }, breakLine: i !== items.length - 1 },
    })),
    {
      isTextBox: true, fontSize: opts.fontSize || 11.5, color: INK, fontFace: BODY,
      paraSpaceAfter: opts.space === undefined ? 5 : opts.space, valign: "top",
      lineSpacing: opts.lineSpacing || 15, margin: 0, ...opts,
    }
  );
}

function statTile(slide, { x, y, w, value, label, color }) {
  slide.addText(value, {
    x, y, w, h: 0.46, isTextBox: true, align: "center",
    fontSize: 27, bold: true, color, fontFace: BODY, margin: 0,
  });
  slide.addText(label, {
    x, y: y + 0.44, w, h: 0.34, isTextBox: true, align: "center",
    fontSize: 9.5, color: MUTED, fontFace: BODY, margin: 0,
  });
}

/* ============================ SLIDE 1 — TITLE ============================ */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };

  // full-bleed map on the right, faded — the product itself as the hero image
  s.addImage({ path: A + "map_clean.png", x: 7.15, y: 0.0, w: 6.18, h: 7.5, transparency: 12 });
  s.addShape(pres.ShapeType.rect, { x: 7.15, y: 0, w: 0.9, h: 7.5, fill: { color: "FFFFFF", transparency: 28 } });

  s.addImage({ path: A + "sih_logo.png", x: 0.55, y: 0.42, w: 2.5, h: 1.07 });

  s.addText("SMART INDIA HACKATHON 2025", {
    x: 0.55, y: 1.72, w: 6.6, h: 0.42, isTextBox: true,
    fontSize: 19, bold: true, color: NAVY_SOFT, fontFace: TITLE_FONT, margin: 0, charSpacing: 1,
  });

  s.addText("Slope Watch", {
    x: 0.55, y: 2.16, w: 6.6, h: 0.86, isTextBox: true,
    fontSize: 50, bold: true, color: NAVY, fontFace: TITLE_FONT, margin: 0,
  });
  s.addText("AI-based early warning and landslide risk monitoring for the North Eastern Region", {
    x: 0.55, y: 3.0, w: 6.3, h: 0.6, isTextBox: true,
    fontSize: 14, italic: true, color: MUTED, fontFace: BODY, margin: 0,
  });

  const rows = [
    ["Problem Statement ID", "26001"],
    ["Problem Statement Title", "AI-Based Early Warning and Landslide Risk Monitoring System in NER"],
    ["Theme", "Disaster Management"],
    ["PS Category", "Software"],
    ["Team ID", "< enter your Team ID >"],
    ["Team Name (Registered on portal)", "404 The Optimistics"],
  ];
  let y = 3.78;
  rows.forEach(([k, v]) => {
    const tall = v.length > 55;
    s.addText(k, {
      x: 0.55, y, w: 2.32, h: 0.3, isTextBox: true,
      fontSize: 10.5, bold: true, color: NAVY, fontFace: BODY, margin: 0, valign: "top",
    });
    s.addText(v, {
      x: 2.92, y, w: 4.0, h: tall ? 0.56 : 0.3, isTextBox: true,
      fontSize: 10.5, color: v.startsWith("<") ? RED : INK, fontFace: BODY, margin: 0, valign: "top",
    });
    y += tall ? 0.56 : 0.42;
  });

  s.addShape(pres.ShapeType.rect, { x: 0, y: 7.06, w: W, h: 0.44, fill: { color: BLUE } });
  s.addText("@SIH Idea submission- Template", {
    x: 4.4, y: 7.06, w: 4.5, h: 0.44, isTextBox: true,
    align: "center", valign: "middle", fontSize: 11, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
  s.addText("1", {
    x: 12.5, y: 7.06, w: 0.6, h: 0.44, isTextBox: true,
    align: "right", valign: "middle", fontSize: 11, bold: true, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
  s.addNotes("Working system, not a concept. Live risk for 311 hotspots across all 8 NER states, validated against 318 real landslides.");
}

/* ========================= SLIDE 2 — IDEA / SOLUTION ===================== */
{
  const s = pres.addSlide();
  chrome(s, 2, "IDEA / PROPOSED SOLUTION");

  // hero: the running product
  s.addImage({ path: A + "dashboard_full.png", x: 5.62, y: 1.02, w: 7.5, h: 5.0 });
  s.addText("Live dashboard — running today, not a mockup", {
    x: 5.62, y: 6.04, w: 7.5, h: 0.26, isTextBox: true,
    align: "center", fontSize: 9.5, italic: true, color: MUTED, fontFace: BODY, margin: 0,
  });

  card(s, { x: 0.3, y: 1.02, w: 5.12, h: 1.72, fill: PAPER });
  cardHead(s, "What it does", { x: 0.48, y: 1.12, w: 4.8 });
  bullets(s, [
    "Give it any coordinate and date — it returns a landslide risk percentage in about 10 seconds.",
    "311 known hotspots across all eight NER states are re-scored every day from live satellite data.",
  ], { x: 0.48, y: 1.44, w: 4.78, h: 1.22, fontSize: 11.5 });

  card(s, { x: 0.3, y: 2.86, w: 5.12, h: 1.62, fill: PAPER });
  cardHead(s, "How it addresses the problem", { x: 0.48, y: 2.96, w: 4.8 });
  bullets(s, [
    "Replaces reactive manual reporting with a daily, automatic forecast.",
    "GIS map shows which roads and villages sit below a slope at risk.",
    "Alerts reach officials and citizens in nine regional languages.",
  ], { x: 0.48, y: 3.28, w: 4.78, h: 1.12, fontSize: 11, space: 3 });

  card(s, { x: 0.3, y: 4.6, w: 5.12, h: 1.44, fill: EARTH_BG, border: EARTH });
  cardHead(s, "What makes it different", { x: 0.48, y: 4.7, w: 4.8, color: EARTH });
  bullets(s, [
    "Trained on 318 real NER landslides — not a generic global model.",
    "We found and removed a data bias that would have under-warned remote villages.",
    "Works offline: cached maps and queued field reports for no-signal areas.",
  ], { x: 0.48, y: 5.0, w: 4.78, h: 0.98, fontSize: 10.5, space: 2 });

  // proof strip
  const stats = [
    ["318", "real landslides\ntrained on", NAVY],
    ["0.933", "accuracy\n(ROC-AUC)", GREEN],
    ["87%", "past events\ncaught", GREEN],
    ["9", "languages\nsupported", NAVY],
  ];
  stats.forEach(([v, l, c], i) =>
    statTile(s, { x: 0.32 + i * 1.28, y: 6.14, w: 1.24, value: v, label: l, color: c })
  );
  s.addNotes("Lead with: this runs. Every number on this slide comes from the working system.");
}

/* ======================= SLIDE 3 — TECHNICAL APPROACH ==================== */
{
  const s = pres.addSlide();
  chrome(s, 3, "TECHNICAL APPROACH");

  s.addText("Methodology and process of implementation", {
    x: 0.3, y: 0.94, w: 12.7, h: 0.28, isTextBox: true,
    fontSize: 12.5, bold: true, color: NAVY, fontFace: BODY, margin: 0,
  });
  s.addImage({ path: A + "architecture.png", x: 0.42, y: 1.22, w: 9.2, h: 3.95 });

  // technologies column
  card(s, { x: 9.78, y: 1.22, w: 3.24, h: 3.95, fill: PAPER });
  cardHead(s, "Technologies used", { x: 9.96, y: 1.32, w: 2.9 });
  const tech = [
    ["Data", "Google Earth Engine\nOpenStreetMap Overpass"],
    ["AI / ML", "Python 3.12 · scikit-learn\nRandom Forest, 400 trees"],
    ["Backend", "REST API · alert engine\nnine-language renderer"],
    ["Frontend", "Vector SVG GIS map\nno tile server — works offline"],
    ["Offline", "Service Worker + IndexedDB"],
  ];
  let ty = 1.66;
  tech.forEach(([k, v]) => {
    s.addText(k, {
      x: 9.96, y: ty, w: 2.9, h: 0.22, isTextBox: true,
      fontSize: 10.5, bold: true, color: EARTH, fontFace: BODY, margin: 0,
    });
    s.addText(v, {
      x: 9.96, y: ty + 0.21, w: 2.9, h: 0.42, isTextBox: true,
      fontSize: 10, color: INK, fontFace: BODY, margin: 0, lineSpacing: 12.5,
    });
    ty += 0.7;
  });

  // grounding + the model internals
  card(s, { x: 0.3, y: 5.32, w: 6.34, h: 1.6, fill: GREEN_BG, border: GREEN });
  cardHead(s, "Built on two proven operational models", { x: 0.48, y: 5.4, w: 6.0, color: GREEN });
  bullets(s, [
    "NASA LHASA — susceptibility modulated by rainfall triggers, fed to a tree ensemble. LHASA v2 uses the same family of algorithm we do.",
    "USGS infinite-slope factor of safety — a physics calculation included as one of our 17 features.",
  ], { x: 0.48, y: 5.7, w: 6.0, h: 1.1, fontSize: 10.5, space: 3 });

  card(s, { x: 6.82, y: 5.32, w: 6.2, h: 1.6, fill: PAPER });
  cardHead(s, "Inside the model", { x: 7.0, y: 5.4, w: 5.8 });
  bullets(s, [
    "400 decision trees vote; the share voting “landslide” is the risk percentage.",
    "Terrain sampled over a 300 m window — reported coordinates mark where debris stopped, not where the slope failed.",
  ], { x: 7.0, y: 5.7, w: 5.84, h: 1.1, fontSize: 10.5, space: 3 });

  s.addNotes("If asked why not deep learning: 318 events is far too few; NASA's operational LHASA v2 also uses trees.");
}

/* ==================== SLIDE 4 — FEASIBILITY AND VIABILITY ================ */
{
  const s = pres.addSlide();
  chrome(s, 4, "FEASIBILITY AND VIABILITY");

  // feasibility
  card(s, { x: 0.3, y: 1.0, w: 4.12, h: 2.05, fill: GREEN_BG, border: GREEN });
  cardHead(s, "Feasibility — already proven", { x: 0.48, y: 1.09, w: 3.8, color: GREEN });
  bullets(s, [
    "Runs end-to-end today on a laptop — no GPU, no cloud bill.",
    "All satellite data is free for non-commercial use.",
    "Full rebuild takes 12 minutes; daily refresh takes 4.",
    "Uses existing infrastructure — no hardware needed to start.",
  ], { x: 0.48, y: 1.42, w: 3.78, h: 2.2, fontSize: 10.5, space: 4 });

  // challenges
  card(s, { x: 4.6, y: 1.0, w: 4.12, h: 2.05, fill: RED_BG, border: RED });
  cardHead(s, "Risks and challenges", { x: 4.78, y: 1.09, w: 3.8, color: RED });
  bullets(s, [
    "Location data: only 20 of 318 records have exact coordinates.",
    "Satellite lag makes this a daily forecast, not minute-by-minute.",
    "Soil moisture and radar do not exist before 2015.",
    "Alert fatigue if warnings fire too often.",
  ], { x: 4.78, y: 1.42, w: 3.78, h: 2.2, fontSize: 10.5, space: 4 });

  // strategies
  card(s, { x: 8.9, y: 1.0, w: 4.12, h: 2.05, fill: AMBER_BG, border: AMBER });
  cardHead(s, "How we overcome them", { x: 9.08, y: 1.09, w: 3.8, color: AMBER });
  bullets(s, [
    "Partner with GSI for the field-validated inventory — their data is the single biggest available gain.",
    "Ground sensors (LoRa, solar) add local precision where deployed.",
    "60% alert threshold plus a 12-hour cooldown prevents fatigue.",
    "System degrades gracefully — a dead sensor never breaks it.",
  ], { x: 9.08, y: 1.42, w: 3.78, h: 2.2, fontSize: 10.5, space: 4 });

  // the bias story, as the viability proof
  card(s, { x: 0.3, y: 3.28, w: 12.72, h: 3.62, fill: "FFFFFF", border: LINE });
  cardHead(s, "Why our numbers can be trusted — we broke our own model to fix it", { x: 0.5, y: 3.38, w: 8.6 });
  s.addImage({ path: A + "bias_fix.png", x: 0.5, y: 3.76, w: 7.5, h: 2.95 });

  s.addText([
    { text: "Adding road data pushed accuracy to 0.953. It was a bug.\n", options: { bold: true, color: NAVY, breakLine: true } },
    { text: "Landslides get recorded when someone notices them — near roads. Our comparison points sat 10× farther away, so the model learned “near a road” instead of “steep and saturated”. Deployed, it would have told remote villages they were safe.\n\n", options: { breakLine: true } },
    { text: "We matched the sampling, accuracy fell to 0.933, and rainfall became the top factor — exactly what the science predicts.", options: { bold: true, color: GREEN } },
  ], {
    x: 8.2, y: 3.9, w: 4.62, h: 2.7, isTextBox: true,
    fontSize: 11, color: INK, fontFace: BODY, margin: 0, lineSpacing: 15,
  });

  s.addNotes("This is the strongest point in the deck. A team that was not checking would have reported the higher number.");
}

/* ====================== SLIDE 5 — IMPACT AND BENEFITS ==================== */
{
  const s = pres.addSlide();
  chrome(s, 5, "IMPACT AND BENEFITS");

  s.addImage({ path: A + "hindcast.png", x: 0.34, y: 1.0, w: 6.3, h: 2.72 });
  s.addImage({ path: A + "importance.png", x: 6.86, y: 1.0, w: 6.16, h: 2.72 });

  // impact on people
  card(s, { x: 0.3, y: 3.9, w: 6.34, h: 3.02, fill: PAPER });
  cardHead(s, "Impact on the target audience", { x: 0.5, y: 3.99, w: 6.0 });
  const impacts = [
    ["District administrations", "A daily ranked watch-list instead of waiting for a phone call after the slope has already gone."],
    ["Remote villages", "Warnings in Mizo, Khasi, Meitei, Assamese and five more — on basic phones, no internet needed."],
    ["Field officers", "Works with no signal: cached risk map, and hazard reports that queue and upload later."],
    ["Road authorities", "Highway and local-road layers show which routes sit below a slope at risk."],
  ];
  let iy = 4.32;
  impacts.forEach(([k, v]) => {
    s.addText(k, {
      x: 0.5, y: iy, w: 2.06, h: 0.56, isTextBox: true,
      fontSize: 10.5, bold: true, color: EARTH, fontFace: BODY, margin: 0, valign: "top",
    });
    s.addText(v, {
      x: 2.6, y: iy, w: 3.86, h: 0.56, isTextBox: true,
      fontSize: 10, color: INK, fontFace: BODY, margin: 0, valign: "top", lineSpacing: 12.5,
    });
    iy += 0.64;
  });

  // benefits
  card(s, { x: 6.86, y: 3.9, w: 6.16, h: 3.02, fill: GREEN_BG, border: GREEN });
  cardHead(s, "Benefits", { x: 7.06, y: 3.99, w: 5.8, color: GREEN });
  const bens = [
    ["Social", "Warns the isolated villages a road-biased model would have missed. 329 deaths are recorded in the events we studied."],
    ["Economic", "Free satellite data, no GPU, no hardware to begin. Pre-emptive slope repair costs a fraction of rebuilding a highway."],
    ["Environmental", "Flags slopes destabilised by unplanned hill-cutting, using vegetation loss and radar change."],
  ];
  let by = 4.32;
  bens.forEach(([k, v]) => {
    s.addText(k, {
      x: 7.06, y: by, w: 1.5, h: 0.78, isTextBox: true,
      fontSize: 10.5, bold: true, color: GREEN, fontFace: BODY, margin: 0, valign: "top",
    });
    s.addText(v, {
      x: 8.5, y: by, w: 4.34, h: 0.78, isTextBox: true,
      fontSize: 10, color: INK, fontFace: BODY, margin: 0, valign: "top", lineSpacing: 12.5,
    });
    by += 0.86;
  });

  s.addNotes("Every landslide in the left chart really happened. The model scored them without ever seeing them in training.");
}

/* ==================== SLIDE 6 — RESEARCH AND REFERENCES ================== */
{
  const s = pres.addSlide();
  chrome(s, 6, "RESEARCH AND REFERENCES");

  card(s, { x: 0.3, y: 1.0, w: 6.34, h: 2.32, fill: PAPER });
  cardHead(s, "Scientific basis", { x: 0.5, y: 1.09, w: 6.0 });
  bullets(s, [
    "NASA LHASA — Landslide Hazard Assessment for Situational Awareness (global nowcasting; v2 uses gradient-boosted trees).",
    "USGS shallow-landslide model — infinite-slope factor of safety under rainfall infiltration.",
    "GSI — National Landslide Susceptibility Mapping and the Bhukosh / Bhusanket inventories.",
    "NRSC Landslide Atlas of India, 1998–2022.",
  ], { x: 0.5, y: 1.42, w: 6.0, h: 2.1, fontSize: 10.5, space: 5 });

  card(s, { x: 6.86, y: 1.0, w: 6.16, h: 2.32, fill: PAPER });
  cardHead(s, "Data sources", { x: 7.06, y: 1.09, w: 5.8 });
  bullets(s, [
    "NASA GPM IMERG v07 — rainfall, 30-minute cadence.",
    "NASA SMAP L4 — surface and root-zone soil moisture.",
    "USGS SRTM — 30 m elevation and slope.",
    "NASA MODIS MOD13Q1 — vegetation index.",
    "ESA Copernicus Sentinel-1 — C-band radar.",
    "OpenStreetMap — 46,087 NER road segments.",
    "NASA Global Landslide Catalog — 318 NER events, 2007–2025.",
  ], { x: 7.06, y: 1.42, w: 5.8, h: 2.1, fontSize: 10.5, space: 2 });

  card(s, { x: 0.3, y: 3.52, w: 12.72, h: 1.5, fill: EARTH_BG, border: EARTH });
  cardHead(s, "Honest scope — what is built, and what is designed", { x: 0.5, y: 3.6, w: 8.0, color: EARTH });
  s.addText([
    { text: "Built and running:  ", options: { bold: true, color: GREEN } },
    { text: "satellite ingestion · ML model with cross-validated hindcast · GIS dashboard · prediction API and CLI · alert engine · nine-language messages · offline map cache and field-report queue.\n", options: { breakLine: true } },
    { text: "Designed, not yet built:  ", options: { bold: true, color: EARTH } },
    { text: "SMS gateway delivery (message rendering is done; only a billable account is missing) · IoT ground sensors · satellite-imagery CNN.", options: {} },
  ], {
    x: 0.5, y: 3.92, w: 12.3, h: 0.96, isTextBox: true,
    fontSize: 10.5, color: INK, fontFace: BODY, margin: 0, lineSpacing: 14,
  });

  const kpis = [
    ["318", "landslides\ntrained on", NAVY], ["0.933", "ROC-AUC\ncross-validated", GREEN],
    ["87%", "past events\ncaught", GREEN], ["311", "hotspots\nscored daily", NAVY],
    ["17", "features from\n6 data sources", NAVY], ["9", "regional\nlanguages", NAVY],
  ];
  kpis.forEach(([v, l, c], i) =>
    statTile(s, { x: 0.42 + i * 2.09, y: 5.36, w: 1.96, value: v, label: l, color: c })
  );

  s.addNotes("Close on scope honesty — it reads as rigour, and it pre-empts the 'is this actually built?' question.");
}

pres.writeFile({ fileName: "/Users/utkarsh/Desktop/ml/SIH_26001_SlopeWatch.pptx" })
  .then(f => console.log("written:", f));
