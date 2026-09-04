const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  PageBreak, LevelFormat, Footer, PageNumber,
} = require("docx");

const NAVY = "1F3A5F";
const ACCENT = "0F6B52";
const GREY = "5A6B62";
const RULE = "C9D3CC";
const BAND = "EEF3EF";

const CONTENT_WIDTH = 9360; // Letter, 1" margins

// ---------- helpers ----------
const gap = (n = 120) => new Paragraph({ spacing: { after: n }, children: [] });

const h1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 60 },
    children: [new TextRun({ text, bold: true, size: 32, color: NAVY, font: "Calibri" })],
  });

const h2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 260, after: 100 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 4 } },
    children: [new TextRun({ text, bold: true, size: 26, color: NAVY, font: "Calibri" })],
  });

const body = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: opts.after ?? 120, line: 276 },
    indent: opts.indent ? { left: 360 } : undefined,
    children: [new TextRun({ text, size: 21, font: "Calibri", color: "222222", ...opts.run })],
  });

// A question heading — numbered, bold, coloured.
const question = (n, text) =>
  new Paragraph({
    spacing: { before: 280, after: 80 },
    keepNext: true,
    children: [
      new TextRun({ text: `Q${n}.  `, bold: true, size: 22, color: ACCENT, font: "Calibri" }),
      new TextRun({ text, bold: true, size: 22, color: "1A1A1A", font: "Calibri" }),
    ],
  });

// The answer, indented under its question.
const answer = (text) =>
  new Paragraph({
    spacing: { after: 100, line: 276 },
    indent: { left: 360 },
    children: [new TextRun({ text, size: 21, font: "Calibri", color: "222222" })],
  });

// A short line the speaker can say verbatim.
const sayThis = (text) =>
  new Paragraph({
    spacing: { before: 60, after: 180, line: 276 },
    indent: { left: 360 },
    border: { left: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 8 } },
    children: [
      new TextRun({ text: "Say it like this:  ", bold: true, size: 19, color: ACCENT, font: "Calibri" }),
      new TextRun({ text, italics: true, size: 21, color: "333333", font: "Calibri" }),
    ],
  });

const bullet = (text) =>
  new Paragraph({
    numbering: { reference: "dots", level: 0 },
    spacing: { after: 70, line: 276 },
    children: [new TextRun({ text, size: 21, font: "Calibri", color: "222222" })],
  });

const cell = (text, { bold = false, header = false, width, color } = {}) =>
  new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: header ? { type: ShadingType.CLEAR, fill: BAND, color: "auto" } : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: [
      new Paragraph({
        spacing: { after: 0, line: 264 },
        children: [
          new TextRun({
            text,
            bold: bold || header,
            size: header ? 19 : 20,
            color: color || (header ? NAVY : "222222"),
            font: "Calibri",
          }),
        ],
      }),
    ],
  });

const table = (headers, rows, widths) =>
  new Table({
    columnWidths: widths,
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      left: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      right: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: RULE },
    },
    rows: [
      new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => cell(h, { header: true, width: widths[i] })),
      }),
      ...rows.map(
        (r) =>
          new TableRow({
            children: r.map((c, i) =>
              cell(c, { width: widths[i], bold: i === 0 })
            ),
          })
      ),
    ],
  });

// ---------- content ----------
const children = [];

// Title block
children.push(
  new Paragraph({
    spacing: { after: 40 },
    children: [new TextRun({ text: "SMART INDIA HACKATHON  ·  PROBLEM STATEMENT 26001", size: 18, color: ACCENT, bold: true, font: "Calibri", characterSpacing: 30 })],
  }),
  new Paragraph({
    spacing: { after: 100 },
    children: [new TextRun({ text: "Slope Watch — Question & Answer Preparation", bold: true, size: 40, color: NAVY, font: "Calibri" })],
  }),
  new Paragraph({
    spacing: { after: 220 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY, space: 6 } },
    children: [new TextRun({ text: "AI-based early warning and landslide risk monitoring for the North Eastern Region", size: 22, color: GREY, italics: true, font: "Calibri" })],
  })
);

children.push(
  body("This document has every question we expect to be asked, with an answer written the way you would actually say it out loud. Read the first two pages before you present. The rest is for looking things up.", { after: 100 }),
  body("Three rules while answering:"),
  bullet("If you do not know, say so, then say how you would find out. Guessing is what loses marks."),
  bullet("Give the number first, then the explanation. Judges want the figure."),
  bullet("If a question exposes a weakness, agree with it and explain what you would do about it."),
  gap(160)
);

// ---- Section: the three leads ----
children.push(h1("Part 1 — The three points to lead with"));
children.push(body("If you get one uninterrupted minute, these are the three things that make the strongest impression. Each one shows that we checked our own work.", { after: 160 }));

children.push(h2("Point 1 — We found a mistake in our own system and fixed it"));
children.push(
  body("We added road data to the model and our accuracy went up nicely. It looked like a success. It was actually a bug."),
  body("Here is what happened. To train the model we need examples of places where a landslide happened, and examples of places where one did not. Nobody publishes a list of places where nothing happened, so we generate those ourselves by picking nearby spots at random."),
  body("The problem is that landslides only get written down when somebody notices them. A slope that falls onto a highway makes the news. An identical slope that falls in remote forest is never recorded. So our recorded landslides were sitting an average of 243 metres from a road, while our randomly chosen safe spots were 2,542 metres away."),
  body("The model spotted that shortcut. Instead of learning \"steep wet slopes are dangerous\", it learned \"places near roads are dangerous\". If we had launched that, it would have told remote villages they were safe when they were not. Those villages are exactly who this problem statement is about."),
  body("We fixed it by making sure our safe examples sit at a similar distance from roads as the real landslides. Our accuracy went down from 0.953 to 0.933, and rainfall became the most important factor, which is what the science says it should be."),
  sayThis("Our accuracy dropped when we fixed this, and that is the point. A team that was not checking would have reported the higher number.")
);

children.push(h2("Point 2 — We chose a simpler AI on purpose, and proved it was the right call"));
children.push(
  body("The obvious question is why we did not use deep learning, since that is what everyone talks about."),
  body("The answer is that deep learning needs an enormous amount of data. It has millions of internal settings to tune. We have 318 recorded landslides. Give a system with millions of settings only a few hundred examples and it memorises the answers instead of learning the pattern. It looks brilliant in testing and fails in the real world."),
  body("We used a Random Forest instead. Think of it as 400 separate flowcharts, each asking yes-or-no questions like \"has more than 150 mm of rain fallen in the last week?\" and \"is the slope steeper than 25 degrees?\" All 400 vote, and the share voting yes becomes the risk percentage."),
  body("We are not guessing here. NASA runs a global landslide warning system called LHASA, and its current version uses the same family of method, not deep learning. We also tested that exact alternative ourselves and our approach scored very slightly better."),
  sayThis("Deep learning on satellite photos is good for finding landslides that already happened. We are predicting ones that have not happened yet, and before a slope fails the photograph looks completely normal.")
);

children.push(h2("Point 3 — We say our biggest weakness before anyone asks"));
children.push(
  body("Our biggest limitation is not the AI. It is the quality of the location data we trained on."),
  body("Every landslide record comes with a note about how precise its location is. Only 20 of our 318 records are exact. Ninety-six of them are only accurate to somewhere between 25 and 50 kilometres."),
  body("That matters because if a record says a landslide happened somewhere within 50 kilometres of a town, the coordinates we are given might point at a flat valley floor when the real landslide was on a steep ridge far away. We then teach the model that flat ground is dangerous, which is wrong."),
  body("The proof is in our own results. Landslides with exact coordinates are caught far more often than vague ones. So the fastest way to improve this system is better location data, not a cleverer algorithm."),
  body("That data exists. The Geological Survey of India has a field inventory checked by real geologists. We found the exact map layers on the government portal, but the bulk download option is switched off, so we could not get it. That is a permissions problem, not a technical one."),
  sayThis("If anyone here can help us get access to the GSI field-validated inventory, that single thing would improve this system more than anything else we could build.")
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- Section: the AI ----
children.push(h1("Part 2 — Questions about the AI"));

let n = 1;
children.push(question(n++, "What exactly does your AI do?"));
children.push(
  answer("You give it a place and a date. It gives back a percentage — how likely a landslide is there, then. That is the whole job."),
  answer("Behind that, it looks at seventeen pieces of information about that spot: how much rain has fallen over the last day, three days, week, fortnight and month; how wet the soil already is; how steep the ground is; how much vegetation is on it; and whether radar shows the surface has changed recently.")
);

children.push(question(n++, "How did you train it?"));
children.push(
  answer("We collected 318 real landslides across all eight North Eastern states from 2007 to 2025, each with a location and a date. For every one we also generated two comparison points nearby on ordinary days when nothing happened."),
  answer("For all 946 of those points we pulled the satellite readings for that exact place and date. That gave us a table. The model studies the table and works out for itself which combinations of rain, slope and wetness came before landslides."),
  answer("Nobody wrote the rules. We never told it rain matters. It discovered that on its own, which is why we were pleased when rainfall came out as the single most important factor.")
);

children.push(question(n++, "How do you know it actually works and is not just memorising?"));
children.push(
  answer("We use a method called cross-validation. We split the data into five groups, train the model on four of them and ask it to predict the fifth, then rotate so every group gets its turn. Every score we quote comes from a model that had never seen that particular case."),
  answer("We also ran what is called a hindcast. For each of the 318 real landslides we asked what the model would have said the day before it happened. It flagged 277 of them, which is 87 percent."),
  sayThis("The strongest evidence is that we caught ourselves. We found a flaw that was inflating our score and we fixed it, even though it made our number look worse.")
);

children.push(question(n++, "Why not deep learning or a neural network?"));
children.push(
  answer("Because we only have 318 examples. Deep learning typically needs tens of thousands. With this little data it would memorise rather than learn."),
  answer("NASA's own operational landslide system uses the same type of method we did, not deep learning. And we tested the main alternative ourselves — it scored 0.9295 against our 0.9329, so ours was marginally better."),
  answer("If we ever get the full government inventory of around 80,000 landslides, deep learning becomes worth trying. It is a question of data volume, not fashion.")
);

children.push(question(n++, "Can it warn about a place where a landslide has never happened before?"));
children.push(
  answer("The model itself can. Give it any coordinate and date and it will score it from the terrain and weather. It does not need that place to be in its training data. Our live prediction tool does exactly this."),
  answer("Our map currently watches 311 known past landslide sites, because that gives a sensible watch list to start with. Expanding to cover the whole region on a grid is a computing task, not a research one. At one-kilometre spacing that is roughly 250,000 points, which our system could work through in a few hours."),
  answer("We would rather say this plainly than be caught out by it.")
);

children.push(question(n++, "What about the 13 percent you miss?"));
children.push(
  answer("Forty-one of our 318 records scored below 50 percent. When we looked into why, a lot of it is bad location data rather than bad prediction — if the record points at the wrong hillside, the model is being tested on the wrong place."),
  answer("We also deliberately built the system to over-warn rather than under-warn. Missing a landslide can cost lives. A false alarm costs an inspection visit. Given that choice we lean towards catching more.")
);

children.push(question(n++, "How many false alarms does it give?"));
children.push(
  answer("Roughly one in four of our high-risk flags turns out to be a false alarm. We know alert fatigue is a real danger — if people stop believing the warnings, the system is worthless."),
  answer("So we designed against it. We only send an alert above 60 percent risk, which is higher than the 50 percent we use to colour the map. We do not repeat an alert for the same place within 12 hours unless the situation has actually got worse.")
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- Section: data ----
children.push(h1("Part 3 — Questions about the data"));

children.push(question(n++, "Where does your satellite data come from?"));
children.push(
  answer("Five sources, all accessed free through Google Earth Engine:"),
  bullet("Rainfall from NASA's GPM mission, updated every 30 minutes"),
  bullet("Soil moisture from NASA's SMAP satellite, updated every three hours"),
  bullet("Ground shape and slope from SRTM, a radar survey flown in 2000"),
  bullet("Vegetation cover from MODIS, updated every 16 days"),
  bullet("Surface radar from Sentinel-1, which can see through cloud"),
  answer("That last one matters more than it sounds. The North East is under monsoon cloud for months, and ordinary cameras in space are blind exactly when the risk is highest. Radar is not."),
  answer("We also use OpenStreetMap for the road network, but that is a map database, not a satellite. Be careful to say five satellite sources plus OpenStreetMap, not six satellites.")
);

children.push(question(n++, "How fresh is the data? Is this really real time?"));
children.push(
  answer("Honestly, it is a daily forecast rather than a minute-by-minute one. Rainfall data arrives about a day behind. Soil moisture is about three hours behind. The radar satellite only passes overhead every six to twelve days."),
  answer("We hit this problem directly. Our first version used a rainfall dataset that is more accurate historically but arrives weeks late. Recent landslides were scoring only 30 to 40 percent because the rain that caused them was not in the data yet. Switching to a faster source fixed it."),
  answer("For true minute-by-minute warning you need sensors on the ground, which is our next phase.")
);

children.push(question(n++, "Half your data is missing soil moisture. Does that not break it?"));
children.push(
  answer("The soil moisture satellite only launched in 2015 and the radar satellite in late 2014, so for landslides before then that measurement genuinely does not exist. We fill those gaps with the typical value rather than throw the record away, because the rainfall and slope information is still useful."),
  answer("It makes older records weaker, not wrong. And it only affects training. Any prediction we make today has complete data.")
);

children.push(question(n++, "Your terrain data is from the year 2000. Is that not out of date?"));
children.push(
  answer("Yes, and it is a fair criticism. The elevation survey was flown once in 2000 and has never been updated, so any hill cutting done since then is not in it. Unplanned hill cutting is one of the biggest causes of landslides in this region, so that is a genuine gap."),
  answer("What partly covers it is the Sentinel-1 radar. We compare the last 12 days against the previous year, so ground that has recently been disturbed still shows up as a change even though our elevation map is old.")
);

children.push(question(n++, "How is this different from what the government already has?"));
children.push(
  answer("We are not claiming to beat them, and we borrowed their methods deliberately. NASA's structure and the US Geological Survey's slope stability equation are both built into our system, and we say so openly."),
  answer("The gaps we fill are practical. NASA's global system is coarse and not tuned to this region's geology or rainfall. The Geological Survey of India's mapping is mostly fixed zoning that does not change day to day. Ours is trained on North East landslides specifically, updates daily, and comes with the delivery layer — regional language alerts and offline reporting — that a purely scientific product does not include.")
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- Section: sensors ----
children.push(h1("Part 4 — Questions about ground sensors"));
children.push(
  body("Our working system runs entirely on satellite data. Ground sensors are our next phase — designed and costed, but not yet deployed. Be honest about that. The most important thing to get across is this:", { after: 100 }),
  sayThis("The model works on satellite data alone. Sensors make it more precise where they are installed. They are not something the system depends on, so a broken sensor does not break anything.")
);

children.push(h2("Which sensors and why"));
children.push(
  table(
    ["Sensor", "What it measures", "Why we need it"],
    [
      ["Soil moisture probe", "How wet the soil is, at two or three depths", "Our satellite reading covers an 11 km square. A buried probe gives the true local figure"],
      ["Water pressure sensor", "Water pressure inside the soil", "This is the exact value our stability equation currently has to assume"],
      ["Tilt sensor", "Whether the slope is moving", "Slopes creep slowly before they collapse. This is the real early warning sign"],
      ["Rain gauge", "Rainfall in millimetres", "Gives the true local rainfall instead of a regional average"],
      ["Crack meter", "Whether a crack is widening", "Cheapest and most direct sign that ground is pulling apart"],
    ],
    [1900, 2900, 4560]
  ),
  gap(140),
  body("The controller is an ESP32 board. The important choice is the radio: we use LoRa, not a mobile SIM. LoRa reaches over ten kilometres without any mobile tower, which is the whole point in remote hills where there is no signal. Power comes from a solar panel and a rechargeable battery."),
  body("Roughly four to six thousand rupees per sensor station, plus about eight thousand for one receiving station that can serve many of them.")
);

children.push(h2("The practical objections"));
children.push(body("These are the questions that catch teams out. Each one has a real answer.", { after: 140 }));

children.push(question(n++, "Will birds peck at it? Will animals damage it?"));
children.push(
  answer("The box is sealed and mounted on a metal pole, and the cables run inside steel tubing so nothing can chew through them."),
  answer("Honestly though, birds are not the main worry in this region. Monkeys and elephants are. That is why the enclosure locks rather than just clips shut, and the pole is set in concrete rather than pushed into the ground.")
);

children.push(question(n++, "What happens in heavy rain? Will water get in?"));
children.push(
  answer("The enclosure is rated IP67, which means sealed against water, and every cable enters through a waterproof gland. The circuit board also gets a protective coating."),
  answer("There is a detail here worth mentioning because it shows we have thought about it. A completely sealed box is actually worse. Day and night temperature swings pull moisture in and then condense it inside. So the box needs a special vent that lets water vapour out but not liquid in.")
);

children.push(question(n++, "What about lightning?"));
children.push(
  answer("A real risk on hilltops during monsoon. We fit surge protection and proper earthing, and use cheap sacrificial fuses that blow first and can be replaced for a few rupees. Where the slope allows, we avoid mounting on the very top of a ridge.")
);

children.push(question(n++, "The solar panel will not charge under monsoon cloud."));
children.push(
  answer("This is the hardest genuine constraint, and we would not pretend otherwise. Our answer is to oversize the panel three to five times what the average calculation suggests, use a bigger battery, and have the station sleep most of the time — it wakes every fifteen minutes, takes a reading, and shuts down again."),
  answer("We design for at least two weeks of running with no sun at all.")
);

children.push(question(n++, "There is no mobile network in those hills."));
children.push(
  answer("Correct, and that is exactly why we chose LoRa radio instead of a mobile SIM. The sensor talks to a receiving station up to ten kilometres away, and only that one receiving station needs a connection to the internet."),
  answer("If even that link is down, each sensor stores its readings and sends them when the link comes back.")
);

children.push(question(n++, "Somebody will steal it."));
children.push(
  answer("Probably, if we do it badly. We use components with little resale value, and the tilt sensor doubles as a tamper alarm — if somebody removes the unit, we know immediately."),
  answer("But the honest answer is that technology alone does not solve theft. It is solved by the village owning the system. If people understand that the box is what warns them before their homes are buried, they protect it themselves.")
);

children.push(question(n++, "What if the landslide destroys your sensor?"));
children.push(
  answer("Then it has done its job. A sensor going silent is itself information."),
  answer("Every station sends a regular heartbeat signal. If that stops, and the last tilt reading showed the ground moving, we treat that as a confirmed landslide rather than a fault. The final message a sensor sends before it is destroyed is the most valuable one it will ever send."),
  sayThis("We design for the sensor being destroyed, because on an unstable slope that is a likely outcome, not an accident.")
);

children.push(question(n++, "Who maintains these once you have gone?"));
children.push(
  answer("A fair challenge, and one that kills a lot of sensor projects. We design each station to run unattended for six to twelve months, but beyond that it needs a district-level owner with a budget."),
  answer("We would say plainly that a sensor network without a maintenance commitment becomes electronic waste within two years. That is why we made the satellite system work on its own first, and treat sensors as an enhancement rather than the foundation.")
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// ---- Section: practical ----
children.push(h1("Part 5 — Practical questions"));

children.push(question(n++, "What does it cost to run?"));
children.push(
  answer("Almost nothing at present. The satellite data is free for non-commercial use. The model trains on an ordinary laptop in about a minute. Updating the risk for all 311 locations takes about four minutes."),
  answer("The real costs come later: text message charges, and more satellite computing if we expand to cover the whole region on a grid.")
);

children.push(question(n++, "How do people actually get warned?"));
children.push(
  answer("Three ways. District officers see the live map. Alerts go out automatically to a messaging channel. And for villagers with no smartphone, text messages, which work on basic phones with no internet at all."),
  answer("We generate the alert text in nine languages of the region, chosen automatically by state. Mizoram gets Mizo, Meghalaya gets Khasi, Manipur gets Meitei, and so on."),
  answer("The text message part is ready but not connected, because sending real messages needs a paid account we did not want to set up casually.")
);

children.push(question(n++, "Can we trust translations you have not had checked?"));
children.push(
  answer("You should not, and our system does not ask you to. Every language except English is marked as unchecked, and unchecked languages are always sent together with the English version, so the reader always has one version we know is correct."),
  answer("Getting a word like \"severe\" wrong in a warning could send somebody the wrong way. Once a native speaker confirms a language, we change one setting and it stops being paired with English.")
);

children.push(question(n++, "What works when there is no internet?"));
children.push(
  answer("Two separate things. Reading: the app saves a copy of the map and the latest risk levels on the phone, so it still opens with no signal. It clearly shows that you are looking at the last saved version."),
  answer("Writing: a field officer can report a crack or a blocked road, with a photo and location, and it saves on the phone straight away. When the signal comes back it uploads by itself. We tested this by cutting the connection mid-submission — nothing was lost.")
);

children.push(question(n++, "What would you do with three more months?"));
children.push(
  answer("In order: get the Geological Survey field inventory, which would improve accuracy more than anything else we could build. Expand from 311 watched sites to covering the whole region. Add the new NISAR satellite, which can detect slopes creeping before they fail. Get the nine translations checked by native speakers. And install the first ten sensor stations at the highest-risk sites.")
);

// ---- Numbers card ----
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1("Part 6 — Numbers to remember"));
children.push(body("If you remember nothing else, remember these.", { after: 160 }));

children.push(
  table(
    ["Figure", "What it is"],
    [
      ["318", "Real landslides we trained on, across all eight states, 2007 to 2025"],
      ["0.933", "Our accuracy score. Above 0.9 is considered strong; 0.5 would be random guessing"],
      ["87%", "Share of past landslides the model would have flagged in advance"],
      ["17", "Pieces of information the model looks at for each place"],
      ["311", "Locations we currently monitor every day"],
      ["9", "Languages our alerts are written in"],
      ["329", "Deaths recorded in the landslides we studied"],
      ["10 seconds", "Time to produce a risk score for any place and date"],
    ],
    [1700, 7660]
  ),
  gap(200)
);

children.push(
  body("A note on the accuracy figure. When we say 0.933, we mean that if you picked one real landslide and one safe location at random, the model would score the landslide higher 93 times out of 100. It is not the same as saying it is right 93 percent of the time.", { after: 120 })
);

children.push(
  new Paragraph({
    spacing: { before: 300 },
    border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 8 } },
    children: [
      new TextRun({
        text: "Every figure in this document was taken from the working system. If you are asked something not covered here, say you do not know and offer to follow up. That answer never loses marks.",
        size: 19, italics: true, color: GREY, font: "Calibri",
      }),
    ],
  })
);

// ---------- document ----------
const doc = new Document({
  creator: "404 The Optimistics",
  title: "Slope Watch — Q&A Preparation",
  description: "Question and answer preparation for SIH problem statement 26001",
  numbering: {
    config: [
      {
        reference: "dots",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 260 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "Slope Watch  ·  Q&A Preparation  ·  Page ", size: 17, color: GREY, font: "Calibri" }),
                new TextRun({ children: [PageNumber.CURRENT], size: 17, color: GREY, font: "Calibri" }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync("/Users/utkarsh/Desktop/ml/SlopeWatch_QA_Preparation.docx", buf);
  console.log("written:", buf.length, "bytes");
});
