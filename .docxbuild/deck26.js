const pptxgen = require("pptxgenjs");
const A = __dirname + "/assets26/";

const NAVY = "1F3864", BLUE = "2E75B6", INK = "1A1A1A", MUTED = "5B6770";
const LINE = "D4DCE6", PAPER = "F5F8FB";
const EARTH = "B45309", EARTH_BG = "FEF7EE";
const GREEN = "1E6B52", GREEN_BG = "EFF7F3";
const RED = "B03A2E", RED_BG = "FBEEEC";
const AMBER = "92670A", AMBER_BG = "FEF6E0";
const SERIF = "Times New Roman", BODY = "Calibri";
const W = 13.333;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "404 The Optimistics";
pres.title = "SPIREXA - SIH 26001";

function chrome(s, page, title) {
  s.background = { color: "FFFFFF" };
  s.addImage({ path: A + "logo_full.png", x: 0.26, y: 0.22, w: 2.14, h: 0.4 });
  s.addImage({ path: A + "sih_logo26.png", x: 11.5, y: 0.08, w: 1.66, h: 0.78 });
  s.addText(title, {
    x: 2.6, y: 0.1, w: 8.7, h: 0.68, isTextBox: true, align: "center", valign: "middle",
    fontSize: 28, bold: true, color: NAVY, fontFace: SERIF, margin: 0,
  });
  s.addShape(pres.ShapeType.rect, { x: 0, y: 7.06, w: W, h: 0.44, fill: { color: BLUE } });
  s.addText("@SIH Idea submission- Template", {
    x: 4.4, y: 7.06, w: 4.5, h: 0.44, isTextBox: true, align: "center", valign: "middle",
    fontSize: 11, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
  s.addText(String(page), {
    x: 12.5, y: 7.06, w: 0.6, h: 0.44, isTextBox: true, align: "right", valign: "middle",
    fontSize: 11, bold: true, color: "FFFFFF", fontFace: BODY, margin: 0,
  });
}

const card = (s, o) => s.addShape(pres.ShapeType.roundRect, {
  x: o.x, y: o.y, w: o.w, h: o.h, rectRadius: 0.05,
  fill: { color: o.fill || PAPER }, line: { color: o.border || LINE, width: 1 },
});
const head = (s, t, o) => s.addText(t, {
  x: o.x, y: o.y, w: o.w, h: 0.28, isTextBox: true, valign: "middle",
  fontSize: o.size || 12.5, bold: true, color: o.color || NAVY, fontFace: BODY, margin: 0,
});
const bullets = (s, items, o) => s.addText(
  items.map((t, i) => ({ text: t, options: { bullet: { indent: 13 }, breakLine: i !== items.length - 1 } })),
  { isTextBox: true, fontSize: o.fontSize || 10.5, color: INK, fontFace: BODY, valign: "top",
    paraSpaceAfter: o.space === undefined ? 4 : o.space, lineSpacing: o.lineSpacing || 14, margin: 0, ...o }
);
const stat = (s, o) => {
  s.addText(o.value, { x: o.x, y: o.y, w: o.w, h: 0.42, isTextBox: true, align: "center",
    fontSize: o.size || 24, bold: true, color: o.color, fontFace: BODY, margin: 0 });
  s.addText(o.label, { x: o.x, y: o.y + 0.4, w: o.w, h: 0.34, isTextBox: true, align: "center",
    fontSize: 9, color: MUTED, fontFace: BODY, margin: 0, lineSpacing: 11 });
};

/* ================= SLIDE 1 - TEMPLATE LAYOUT, UNCHANGED ================= */
{
  const s = pres.addSlide();
  s.background = { color: "FFFFFF" };
  s.addShape(pres.ShapeType.hexagon, {
    x: 6.19, y: 0.93, w: 5.07, h: 5.64,
    fill: { color: "F2F2F2" }, line: { color: "F2F2F2", width: 0 }, rotate: 90,
  });
  s.addImage({ path: A + "sih_brain.png", x: 7.5, y: 1.88, w: 3.5, h: 3.75 });
  s.addImage({ path: A + "sih_logo26.png", x: 10.7, y: 0.0, w: 2.46, h: 1.16 });
  s.addText("SMART INDIA HACKATHON 2026", {
    x: 0.36, y: 0.12, w: 11.33, h: 0.8, isTextBox: true, align: "center", valign: "middle",
    fontSize: 40, bold: true, color: NAVY, fontFace: SERIF, margin: 0,
  });
  s.addText("TITLE PAGE", {
    x: 1.36, y: 1.05, w: 9.33, h: 0.6, isTextBox: true, align: "center", valign: "middle",
    fontSize: 28, bold: true, color: "000000", fontFace: SERIF, margin: 0,
  });
  const rows = [
    ["Problem Statement ID - ", "26001"],
    ["Problem Statement Title- ", "AI-Based Early Warning and Landslide Risk Monitoring System in NER"],
    ["Theme- ", "Disaster Management"],
    ["PS Category- ", "Software"],
    ["Team ID- ", "< enter your Team ID >"],
    ["Team Name (Registered on portal) - ", "404 The Optimistics"],
  ];
  s.addText(
    rows.map(([k, v], i) => ([
      { text: k, options: { bold: true, color: "000000", bullet: { indent: 18 } } },
      { text: v, options: { bold: true, color: v.startsWith("<") ? "C00000" : NAVY, breakLine: i !== rows.length - 1 } },
    ])).flat(),
    { x: 0.36, y: 2.15, w: 6.3, h: 4.6, isTextBox: true, valign: "top",
      fontSize: 15, fontFace: "Arial", margin: 0, paraSpaceAfter: 13, lineSpacing: 21 }
  );
  s.addNotes("SPIREXA. A working system, not a concept: live risk for 311 hotspots across all 8 NER states, validated against 318 real landslides.");
}

/* ========================== SLIDE 2 - IDEA ========================== */
{
  const s = pres.addSlide();
  chrome(s, 2, "IDEA / PROPOSED SOLUTION");

  card(s, { x: 0.28, y: 0.9, w: 5.2, h: 1.12, fill: RED_BG, border: RED });
  head(s, "The cost of no warning", { x: 0.46, y: 0.96, w: 4.9, color: RED });
  s.addText([
    { text: "Rs 327 crore", options: { bold: true, color: RED, fontSize: 13.5 } },
    { text: "  lost in one landslide - NHPC Teesta-V, Sikkim, Aug 2024.\n", options: { breakLine: true } },
    { text: "329 lives", options: { bold: true, color: RED, fontSize: 13.5 } },
    { text: "  lost in the landslides we studied.", options: {} },
  ], { x: 0.46, y: 1.26, w: 4.86, h: 0.7, isTextBox: true, fontSize: 10.5, color: INK, fontFace: BODY, margin: 0, lineSpacing: 14 });

  card(s, { x: 0.28, y: 2.14, w: 5.2, h: 1.5 });
  head(s, "What SPIREXA does", { x: 0.46, y: 2.2, w: 4.9 });
  bullets(s, [
    "Tell it any place and any date - it returns a landslide risk percentage.",
    "311 known danger spots across all eight NER states, re-checked every day.",
    "The map shows which roads and villages sit below a slope at risk.",
  ], { x: 0.46, y: 2.5, w: 4.86, h: 1.08, fontSize: 10.5, space: 4 });

  card(s, { x: 0.28, y: 3.76, w: 5.2, h: 1.56, fill: EARTH_BG, border: EARTH });
  head(s, "Why ours is different", { x: 0.46, y: 3.82, w: 4.9, color: EARTH });
  bullets(s, [
    "Learned from 318 real landslides in the North East, not a global average.",
    "We caught a flaw that would have wrongly told remote villages they were safe.",
    "Warns in 9 local languages, and keeps working where there is no signal.",
  ], { x: 0.46, y: 4.12, w: 4.86, h: 1.14, fontSize: 10.5, space: 4 });

  s.addImage({ path: A + "pyramid.png", x: 5.66, y: 0.9, w: 3.42, h: 2.83 });
  s.addImage({ path: A + "risk_triangle.png", x: 5.8, y: 3.94, w: 3.14, h: 2.52 });

  s.addImage({ path: A + "dashboard_full.png", x: 9.24, y: 0.9, w: 3.82, h: 2.55 });
  s.addText("The live dashboard, running today", {
    x: 9.24, y: 3.48, w: 3.82, h: 0.22, isTextBox: true, align: "center",
    fontSize: 9, italic: true, color: MUTED, fontFace: BODY, margin: 0,
  });

  card(s, { x: 9.24, y: 3.82, w: 3.82, h: 2.64, fill: GREEN_BG, border: GREEN });
  head(s, "Where things stand today", { x: 9.42, y: 3.88, w: 3.5, color: GREEN });
  const now = [["41", "spots at high risk right now"], ["311", "spots watched every day"],
               ["87%", "of past landslides it would have caught"], ["9", "languages it warns in"]];
  let ny = 4.24;
  now.forEach(([v, l]) => {
    s.addText(v, { x: 9.42, y: ny, w: 0.86, h: 0.4, isTextBox: true, align: "right",
      fontSize: 19, bold: true, color: GREEN, fontFace: BODY, margin: 0 });
    s.addText(l, { x: 10.4, y: ny + 0.06, w: 2.54, h: 0.34, isTextBox: true,
      fontSize: 9.8, color: INK, fontFace: BODY, margin: 0, valign: "top", lineSpacing: 11.5 });
    ny += 0.55;
  });

  s.addNotes("Open with the money and the lives. Then say: this runs today, you can try it live.");
}

/* ==================== SLIDE 3 - TECHNICAL APPROACH ==================== */
{
  const s = pres.addSlide();
  chrome(s, 3, "TECHNICAL APPROACH");

  s.addText("How it works, end to end", {
    x: 0.3, y: 0.86, w: 9.0, h: 0.24, isTextBox: true,
    fontSize: 12, bold: true, color: NAVY, fontFace: BODY, margin: 0,
  });
  s.addImage({ path: A + "architecture2.png", x: 0.3, y: 1.12, w: 9.06, h: 3.76 });

  card(s, { x: 9.52, y: 1.12, w: 3.52, h: 3.76 });
  head(s, "Technologies used", { x: 9.7, y: 1.18, w: 3.2 });
  const tech = [
    ["Satellite data", "Google Earth Engine - five NASA\nand ESA satellite feeds"],
    ["Mapping", "OpenStreetMap road network"],
    ["AI / ML", "Python, scikit-learn\nRandom Forest classifier"],
    ["Backend", "Prediction API, alert engine,\nnine-language message system"],
    ["Frontend / GIS", "Vector map with zoom\nno tile server, works offline"],
    ["Hardware (Phase 2)", "ESP32 board, soil moisture,\ntemperature, humidity, tilt"],
  ];
  let ty = 1.5;
  tech.forEach(([k, v]) => {
    s.addText(k, { x: 9.7, y: ty, w: 3.2, h: 0.2, isTextBox: true,
      fontSize: 10.2, bold: true, color: EARTH, fontFace: BODY, margin: 0 });
    s.addText(v, { x: 9.7, y: ty + 0.2, w: 3.2, h: 0.38, isTextBox: true,
      fontSize: 9.6, color: INK, fontFace: BODY, margin: 0, lineSpacing: 12 });
    ty += 0.565;
  });

  card(s, { x: 0.3, y: 5.04, w: 9.06, h: 1.88, fill: GREEN_BG, border: GREEN });
  head(s, "Working prototype - ground sensor node (Phase 2 demo)", { x: 0.48, y: 5.1, w: 8.7, color: GREEN });
  s.addImage({ path: A + "iot_node.png", x: 0.48, y: 5.4, w: 8.7, h: 1.42 });

  card(s, { x: 9.52, y: 5.04, w: 3.52, h: 1.88, fill: PAPER });
  head(s, "The one idea behind it", { x: 9.7, y: 5.1, w: 3.2 });
  s.addText([
    { text: "400 decision trees each vote yes or no. ", options: {} },
    { text: "The share voting yes is the risk percentage.", options: { bold: true, color: NAVY } },
  ], { x: 9.7, y: 5.42, w: 3.2, h: 0.66, isTextBox: true,
       fontSize: 10, color: INK, fontFace: BODY, margin: 0, lineSpacing: 13 });
  s.addText("We read the slope across a 300 m area, because reported landslide coordinates mark where the debris stopped, not where the slope broke.", {
    x: 9.7, y: 6.1, w: 3.2, h: 0.76, isTextBox: true,
    fontSize: 9.4, color: MUTED, fontFace: BODY, margin: 0, lineSpacing: 12,
  });

  s.addNotes("The sensor node is a demo unit for Phase 2, clearly labelled. The satellite model already works without it.");
}

/* ================= SLIDE 4 - FEASIBILITY AND VIABILITY ================= */
{
  const s = pres.addSlide();
  chrome(s, 4, "FEASIBILITY AND VIABILITY");

  card(s, { x: 0.28, y: 0.9, w: 4.16, h: 2.02, fill: GREEN_BG, border: GREEN });
  head(s, "Feasibility - already proven", { x: 0.46, y: 0.96, w: 3.9, color: GREEN });
  bullets(s, [
    "Runs today on a laptop. No GPU, no cloud bill.",
    "All satellite data is free for non-commercial use.",
    "A full daily update takes about four minutes.",
    "Sensor node about Rs 5,000. IIT Mandi proved Rs 1 lakh units work at 60 sites.",
  ], { x: 0.46, y: 1.26, w: 3.88, h: 1.58, fontSize: 9.8, space: 3 });

  card(s, { x: 4.58, y: 0.9, w: 4.16, h: 2.02, fill: RED_BG, border: RED });
  head(s, "Challenges and risks", { x: 4.76, y: 0.96, w: 3.9, color: RED });
  bullets(s, [
    "Only 20 of our 318 records have exact locations.",
    "Satellite timing makes this a daily forecast, not minute-by-minute.",
    "Soil moisture and radar data do not exist before 2015.",
    "Field hardware faces rain, lightning, animals and theft.",
  ], { x: 4.76, y: 1.26, w: 3.88, h: 1.58, fontSize: 9.8, space: 3 });

  card(s, { x: 8.88, y: 0.9, w: 4.16, h: 2.02, fill: AMBER_BG, border: AMBER });
  head(s, "How we overcome them", { x: 9.06, y: 0.96, w: 3.9, color: AMBER });
  bullets(s, [
    "Partner with GSI for their surveyed landslide records - our single biggest gain.",
    "Ground sensors give minute-level truth where satellites cannot.",
    "Sealed enclosure, surge protection, solar sized for 14 sunless days.",
    "A dead sensor never breaks the system - satellites keep running.",
  ], { x: 9.06, y: 1.26, w: 3.88, h: 1.58, fontSize: 9.8, space: 3 });

  card(s, { x: 0.28, y: 3.04, w: 5.12, h: 3.86, fill: PAPER });
  head(s, "Proven before us - and how we go further", { x: 0.46, y: 3.11, w: 4.8 });
  s.addText([
    { text: "IIT Mandi", options: { bold: true, color: NAVY } },
    { text: " (Dr K. V. Uday, Dr Varun Dutt) runs an AI landslide warning system at ", options: {} },
    { text: "60 sites in Himachal Pradesh", options: { bold: true } },
    { text: ". Their sensors read soil moisture, rainfall, temperature, humidity and ground movement, and warn up to ", options: {} },
    { text: "3 hours ahead", options: { bold: true } },
    { text: " at over 90% accuracy, for about Rs 1 lakh a unit.\n\n", options: { breakLine: true } },
    { text: "Why this helps us:  ", options: { bold: true, color: GREEN } },
    { text: "it proves the exact sensors we are building work in Indian mountains.\n\n", options: { breakLine: true } },
    { text: "How we go further:  ", options: { bold: true, color: EARTH } },
    { text: "their system watches 60 instrumented points. SPIREXA watches the entire region from orbit, so a new village needs no hardware at all. The two fit together - satellites decide where to look, sensors confirm what is happening there.", options: {} },
  ], { x: 0.46, y: 3.42, w: 4.78, h: 3.36, isTextBox: true, fontSize: 10, color: INK, fontFace: BODY, margin: 0, lineSpacing: 14 });

  card(s, { x: 5.54, y: 3.04, w: 7.5, h: 3.86, fill: "FFFFFF", border: LINE });
  head(s, "Why our numbers can be trusted - we broke our own model to fix it", { x: 5.72, y: 3.11, w: 7.1 });
  s.addImage({ path: A + "bias_fix.png", x: 5.72, y: 3.44, w: 4.42, h: 1.74 });
  s.addText([
    { text: "Adding road data pushed our accuracy to 0.953. It was a bug.\n", options: { bold: true, color: NAVY, breakLine: true } },
    { text: "Landslides only get recorded when somebody notices them - near roads. Our comparison points sat ten times farther away, so the model learned “near a road” instead of “steep and wet”. Released like that, it would have told remote villages they were safe.\n\n", options: { breakLine: true } },
    { text: "We fixed the sampling. Accuracy fell to 0.933 and rainfall became the top factor - exactly what the science says it should be.", options: { bold: true, color: GREEN } },
  ], { x: 5.72, y: 5.3, w: 7.16, h: 1.5, isTextBox: true, fontSize: 9.8, color: INK, fontFace: BODY, margin: 0, lineSpacing: 13 });

  s.addNotes("Credit IIT Mandi properly. They proved the hardware. We add the regional satellite layer they cannot.");
}

/* =================== SLIDE 5 - IMPACT AND BENEFITS =================== */
{
  const s = pres.addSlide();
  chrome(s, 5, "IMPACT AND BENEFITS");

  s.addImage({ path: A + "hindcast.png", x: 0.3, y: 0.9, w: 6.24, h: 2.7 });
  s.addImage({ path: A + "importance.png", x: 6.72, y: 0.9, w: 6.32, h: 2.7 });

  card(s, { x: 0.28, y: 3.76, w: 6.34, h: 3.14, fill: PAPER });
  head(s, "Who it helps", { x: 0.46, y: 3.82, w: 6.0 });
  const imp = [
    ["District officials", "A daily ranked danger list, instead of a phone call after the slope has gone."],
    ["Remote villages", "Warnings in Mizo, Khasi, Meitei, Assamese and five more - on basic phones."],
    ["Field officers", "Works with no signal. Reports save on the phone and upload later."],
    ["Road and power bodies", "Shows which highways and assets sit below a slope at risk."],
  ];
  let iy = 4.14;
  imp.forEach(([k, v]) => {
    s.addText(k, { x: 0.46, y: iy, w: 1.9, h: 0.62, isTextBox: true,
      fontSize: 9.8, bold: true, color: EARTH, fontFace: BODY, margin: 0, valign: "top" });
    s.addText(v, { x: 2.46, y: iy, w: 4.0, h: 0.62, isTextBox: true,
      fontSize: 9.6, color: INK, fontFace: BODY, margin: 0, valign: "top", lineSpacing: 12 });
    iy += 0.68;
  });

  card(s, { x: 6.76, y: 3.76, w: 6.28, h: 3.14, fill: GREEN_BG, border: GREEN });
  head(s, "The benefits", { x: 6.94, y: 3.82, w: 5.9, color: GREEN });
  const ben = [
    ["Social", "Warns the isolated villages a road-biased model would have missed. 329 deaths are recorded in the events we studied."],
    ["Economic", "One Teesta-V style loss was Rs 327 crore. Fixing a slope early costs a fraction of rebuilding."],
    ["Environmental", "Flags slopes weakened by unplanned hill-cutting, using vegetation loss and radar surface change."],
  ];
  let by = 4.14;
  ben.forEach(([k, v]) => {
    s.addText(k, { x: 6.94, y: by, w: 1.3, h: 0.86, isTextBox: true,
      fontSize: 9.8, bold: true, color: GREEN, fontFace: BODY, margin: 0, valign: "top" });
    s.addText(v, { x: 8.3, y: by, w: 4.56, h: 0.86, isTextBox: true,
      fontSize: 9.6, color: INK, fontFace: BODY, margin: 0, valign: "top", lineSpacing: 12 });
    by += 0.92;
  });

  s.addNotes("Every landslide in the left chart really happened. The model scored them without ever seeing them in training.");
}

/* ================= SLIDE 6 - RESEARCH AND REFERENCES ================= */
{
  const s = pres.addSlide();
  chrome(s, 6, "RESEARCH AND REFERENCES");

  card(s, { x: 0.28, y: 0.9, w: 6.34, h: 2.62 });
  head(s, "Prior work we build on", { x: 0.46, y: 0.96, w: 6.0 });
  const refs = [
    ["NASA LHASA - the global landslide warning system we model our design on.", "https://gpm.nasa.gov/landslides/projects.html"],
    ["USGS shallow-landslide model - the slope stability equation we use.", "https://www.usgs.gov/programs/landslide-hazards"],
    ["IIT Mandi AI landslide warning - 60 sites in Himachal Pradesh.", "https://frontiertech.niti.gov.in/story/how-iit-mandis-ai-predicts-landslides-hours-before-they-hit-the-himalayas"],
    ["GSI Bhukosh - India's surveyed landslide records.", "https://bhukosh.gsi.gov.in/Bhukosh/Public"],
    ["NRSC Landslide Atlas of India, 1998-2022.", "https://www.nrsc.gov.in/nrscnew/resources_atlas_landslide.php"],
  ];
  let ry = 1.24;
  refs.forEach(([t, u]) => {
    s.addText(t, { x: 0.46, y: ry, w: 6.0, h: 0.22, isTextBox: true,
      fontSize: 9.6, color: INK, fontFace: BODY, margin: 0, bullet: { indent: 12 } });
    s.addText(u, { x: 0.68, y: ry + 0.2, w: 5.78, h: 0.19, isTextBox: true,
      fontSize: 8, color: BLUE, fontFace: BODY, margin: 0, hyperlink: { url: u } });
    ry += 0.46;
  });

  card(s, { x: 6.76, y: 0.9, w: 6.28, h: 2.62 });
  head(s, "Where our data comes from", { x: 6.94, y: 0.96, w: 5.9 });
  const data = [
    ["NASA GPM - rainfall, updated every 30 minutes.", "gpm.nasa.gov/data/imerg", "https://gpm.nasa.gov/data/imerg"],
    ["NASA SMAP - how wet the soil is.", "smap.jpl.nasa.gov", "https://smap.jpl.nasa.gov/"],
    ["ESA Sentinel-1 - radar that sees through monsoon cloud.", "sentiwiki.copernicus.eu", "https://sentiwiki.copernicus.eu/web/s1-mission"],
    ["OpenStreetMap - the North East road network.", "openstreetmap.org/copyright", "https://www.openstreetmap.org/copyright"],
    ["NHPC Teesta-V loss - Rs 327 crore, August 2024.", "indiatodayne.in - Sikkim landslide, Teesta-V", "https://www.indiatodayne.in/sikkim/story/sikkim-landslide-caused-rs-327-crore-loss-to-teesta-v-project-nhpc-1109891-2024-10-23"],
  ];
  let dy = 1.24;
  data.forEach(([t, label, href]) => {
    s.addText(t, { x: 6.94, y: dy, w: 5.9, h: 0.22, isTextBox: true,
      fontSize: 9.6, color: INK, fontFace: BODY, margin: 0, bullet: { indent: 12 } });
    s.addText(label, { x: 7.16, y: dy + 0.2, w: 5.7, h: 0.19, isTextBox: true,
      fontSize: 8, color: BLUE, fontFace: BODY, margin: 0, hyperlink: { url: href } });
    dy += 0.46;
  });

  card(s, { x: 0.28, y: 3.66, w: 12.76, h: 1.44, fill: EARTH_BG, border: EARTH });
  head(s, "Being straight about scope", { x: 0.46, y: 3.72, w: 8.0, color: EARTH });
  s.addText([
    { text: "Built and running now:  ", options: { bold: true, color: GREEN } },
    { text: "satellite data collection, the AI model with honest testing, the GIS dashboard, live prediction for any point, the alert engine, nine-language messages, and offline use in the field.\n", options: { breakLine: true } },
    { text: "Phase 2, designed and being built:  ", options: { bold: true, color: EARTH } },
    { text: "the ground sensor node, and text-message delivery - the messages are written and ready, only a paid gateway account is missing.", options: {} },
  ], { x: 0.46, y: 4.02, w: 12.4, h: 0.96, isTextBox: true,
       fontSize: 10, color: INK, fontFace: BODY, margin: 0, lineSpacing: 13.5 });

  const k = [["318", "real landslides\nlearned from", NAVY], ["0.933", "accuracy score\nhonestly tested", GREEN],
             ["87%", "of past events\nit would catch", GREEN], ["311", "danger spots\nchecked daily", NAVY],
             ["8", "states\ncovered", NAVY], ["9", "languages\nit warns in", NAVY]];
  k.forEach(([v, l, c], i) => stat(s, { x: 0.4 + i * 2.1, y: 5.34, w: 1.96, value: v, label: l, color: c }));

  s.addNotes("Close on honesty about scope. It reads as rigour and answers the is-this-real question before it is asked.");
}

pres.writeFile({ fileName: "/Users/utkarsh/Desktop/ml/SIH2026_26001_SPIREXA.pptx" })
  .then(f => console.log("written:", f));
