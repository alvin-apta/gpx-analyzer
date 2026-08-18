const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "GPX Inspector";
pptx.subject = "GPX track analysis application overview";
pptx.title = "GPX Inspector";
pptx.company = "GPX Inspector";
pptx.lang = "en-US";
pptx.theme = {
  headFontFace: "Aptos Display",
  bodyFontFace: "Aptos",
  lang: "en-US",
};
pptx.defineSlideMaster({
  title: "DARK",
  background: { color: "070B14" },
  objects: [
    { rect: { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: "22D3EE" }, line: { color: "22D3EE" } } },
    { text: { text: "GPX INSPECTOR", options: { x: 0.4, y: 0.18, w: 2.2, h: 0.25, fontFace: "Aptos", fontSize: 9, bold: true, color: "64748B", charSpacing: 1.5, margin: 0 } } },
    { text: { text: "Mobility intelligence", options: { x: 10.7, y: 7.1, w: 2.1, h: 0.2, fontSize: 8, color: "64748B", align: "right", margin: 0 } } },
  ],
  slideNumber: { x: 12.85, y: 7.08, color: "64748B", fontSize: 8 },
});

const C = { bg: "070B14", panel: "0D1422", card: "121C2D", line: "26344A", text: "F1F5F9", muted: "94A3B8", cyan: "22D3EE", blue: "60A5FA", violet: "A78BFA", green: "34D399", yellow: "FACC15", orange: "FB923C", red: "F87171" };
const svg = fs.readFileSync(path.join(__dirname, "../frontend/src/logo.svg"), "utf8");
const logoData = `data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`;

function slide(title, kicker) {
  const s = pptx.addSlide("DARK");
  if (kicker) s.addText(kicker.toUpperCase(), { x: 0.55, y: 0.68, w: 4, h: 0.25, fontSize: 10, bold: true, color: C.cyan, charSpacing: 1.5, margin: 0 });
  s.addText(title, { x: 0.55, y: 1.02, w: 11.8, h: 0.55, fontSize: 28, bold: true, color: C.text, margin: 0, breakLine: false });
  return s;
}
function card(s, x, y, w, h, title, body, accent = C.cyan) {
  s.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: C.card }, line: { color: C.line, width: 1 } });
  s.addShape(pptx.ShapeType.rect, { x, y, w: 0.05, h, fill: { color: accent }, line: { color: accent } });
  s.addText(title, { x: x + 0.22, y: y + 0.18, w: w - 0.4, h: 0.3, fontSize: 15, bold: true, color: C.text, margin: 0 });
  s.addText(body, { x: x + 0.22, y: y + 0.62, w: w - 0.4, h: h - 0.78, fontSize: 10.5, color: C.muted, breakLine: false, valign: "top", margin: 0.02, paraSpaceAfterPt: 7, bullet: body.includes("\n") ? { type: "bullet" } : undefined });
}
function arrow(s, x, y, w, color = C.cyan) {
  s.addShape(pptx.ShapeType.chevron, { x, y, w, h: 0.34, fill: { color, transparency: 15 }, line: { color, transparency: 20 } });
}

// 1. Title
{
  const s = pptx.addSlide();
  s.background = { color: C.bg };
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 7.5, fill: { color: C.bg }, line: { color: C.bg } });
  s.addShape(pptx.ShapeType.arc, { x: 7.4, y: -1.2, w: 7, h: 7, adjustPoint: 0.23, rotate: 18, fill: { color: C.bg, transparency: 100 }, line: { color: C.cyan, transparency: 55, width: 3 } });
  s.addShape(pptx.ShapeType.arc, { x: 8.5, y: -0.2, w: 5.3, h: 5.3, adjustPoint: 0.23, rotate: 25, fill: { color: C.bg, transparency: 100 }, line: { color: C.blue, transparency: 55, width: 2 } });
  s.addImage({ data: logoData, x: 0.7, y: 0.8, w: 1.05, h: 1.05 });
  s.addText("GPX Inspector", { x: 0.7, y: 2.15, w: 7.7, h: 0.85, fontSize: 42, bold: true, color: C.text, margin: 0 });
  s.addText("Understand where movement becomes unusual.", { x: 0.72, y: 3.15, w: 7.4, h: 0.45, fontSize: 20, color: C.cyan, margin: 0 });
  s.addText("A local, dark-themed web application for GPX road matching, movement anomaly detection, interactive evidence, and exportable reports.", { x: 0.72, y: 3.85, w: 6.5, h: 1.0, fontSize: 15, color: C.muted, breakLine: false, margin: 0 });
  s.addText("APPLICATION OVERVIEW", { x: 0.72, y: 6.75, w: 3, h: 0.25, fontSize: 9, bold: true, color: "64748B", charSpacing: 2, margin: 0 });
}

// 2. Problem and outcome
{
  const s = slide("From GPS points to explainable evidence", "The problem");
  card(s, 0.6, 1.9, 3.7, 3.8, "Raw GPX is noisy", "Sparse points\nGPS jumps\nUnclear road alignment\nHard-to-read speed changes", C.red);
  arrow(s, 4.6, 3.55, 0.7);
  card(s, 5.6, 1.9, 3.2, 3.8, "GPX Inspector", "Secure upload\nOSM road matching\nDeterministic rules\nConfidence and evidence", C.cyan);
  arrow(s, 9.1, 3.55, 0.7, C.violet);
  card(s, 10.05, 1.9, 2.7, 3.8, "Clear output", "Map locations\nSpeed timeline\nHuman explanation\nPortable reports", C.green);
}

// 3. Workflow
{
  const s = slide("A simple analyst workflow", "How it works");
  const items = [
    ["1", "Upload", "Choose vehicle mode and upload GPX."],
    ["2", "Match", "Compare raw GPS with OSM road geometry."],
    ["3", "Detect", "Apply fixed, mode-aware anomaly rules."],
    ["4", "Inspect", "Link timeline points and findings to the map."],
    ["5", "Export", "Download PDF, CSV, or GeoJSON."],
  ];
  items.forEach((it, i) => {
    const x = 0.55 + i * 2.5;
    s.addShape(pptx.ShapeType.ellipse, { x, y: 2.2, w: 0.65, h: 0.65, fill: { color: i === 4 ? C.violet : C.cyan }, line: { color: C.bg, width: 2 } });
    s.addText(it[0], { x, y: 2.36, w: 0.65, h: 0.2, align: "center", bold: true, fontSize: 14, color: C.bg, margin: 0 });
    s.addText(it[1], { x, y: 3.1, w: 2.0, h: 0.35, fontSize: 16, bold: true, color: C.text, margin: 0 });
    s.addText(it[2], { x, y: 3.6, w: 2.0, h: 1.1, fontSize: 11, color: C.muted, breakLine: false, margin: 0 });
    if (i < 4) s.addShape(pptx.ShapeType.line, { x: x + 0.7, y: 2.52, w: 1.7, h: 0, line: { color: C.line, width: 2, beginArrowType: "none", endArrowType: "triangle" } });
  });
}

// 4. Analysis capabilities
{
  const s = slide("What the application analyzes", "Capabilities");
  card(s, 0.55, 1.75, 3.85, 1.45, "Distance comparison", "Raw GPX, road-matched, straight-line, and reference-route distance.", C.blue);
  card(s, 4.73, 1.75, 3.85, 1.45, "Speed behavior", "Maximum speed, speeding, sudden acceleration, and braking.", C.orange);
  card(s, 8.9, 1.75, 3.85, 1.45, "Direction behavior", "Sharp heading changes and possible wrong-way movement.", C.violet);
  card(s, 0.55, 3.55, 3.85, 1.45, "Road position", "Sustained off-road movement and map-match confidence.", C.red);
  card(s, 4.73, 3.55, 3.85, 1.45, "Data quality", "Impossible speed, GPS jumps, sparse samples, and missing timestamps.", C.yellow);
  card(s, 8.9, 3.55, 3.85, 1.45, "Explainability", "Measured values, fixed thresholds, severity, confidence, and evidence.", C.green);
  s.addText("Indicators support investigation; they are not legal proof.", { x: 0.6, y: 5.65, w: 7, h: 0.3, fontSize: 11, italic: true, color: C.muted, margin: 0 });
}

// 5. Interactive UI
{
  const s = slide("Evidence stays connected to location", "Interactive experience");
  s.addShape(pptx.ShapeType.roundRect, { x: 0.55, y: 1.7, w: 7.1, h: 4.5, fill: { color: "0A111D" }, line: { color: C.line } });
  for (let i = 0; i < 7; i++) s.addShape(pptx.ShapeType.line, { x: 0.9, y: 2.0 + i * 0.55, w: 6.35, h: i % 2 ? -0.25 : 0.18, line: { color: "26344A", width: 1 } });
  s.addShape(pptx.ShapeType.line, { x: 1.0, y: 5.5, w: 5.8, h: -2.75, line: { color: C.cyan, width: 2, dash: "dash" } });
  s.addShape(pptx.ShapeType.line, { x: 1.1, y: 5.4, w: 5.6, h: -2.6, line: { color: C.blue, width: 4 } });
  [[2.2,4.85,C.orange,"S"],[4.1,3.95,C.red,"!"],[5.9,3.15,C.violet,"↻"]].forEach(([x,y,color,t]) => { s.addShape(pptx.ShapeType.ellipse,{x,y,w:.42,h:.42,fill:{color},line:{color:"FFFFFF",width:1.2}});s.addText(t,{x,y:y+.1,w:.42,h:.16,align:"center",fontSize:9,bold:true,color:"FFFFFF",margin:0}); });
  card(s, 8.0, 1.7, 4.75, 1.2, "Map finding icons", "Click a severity-colored icon to open the corresponding evidence.", C.red);
  card(s, 8.0, 3.15, 4.75, 1.2, "Timeline-to-map cursor", "Hover or click speed data to locate the exact raw GPX point.", C.blue);
  card(s, 8.0, 4.6, 4.75, 1.2, "Mobile-friendly", "Bottom navigation, stacked panels, larger touch targets, and safe-area support.", C.green);
}

// 6. Architecture
{
  const s = slide("Local-first, containerized architecture", "Technical design");
  const nodes = [
    [0.65, 2.3, 2.0, "React + MapLibre", C.cyan],
    [3.25, 2.3, 2.0, "FastAPI", C.blue],
    [5.85, 1.55, 2.0, "Redis worker", C.orange],
    [5.85, 3.15, 2.0, "PostGIS", C.green],
    [8.45, 1.55, 2.0, "Valhalla / OSM", C.violet],
    [8.45, 3.15, 2.0, "Local qwen3:14b", C.red],
    [11.05, 2.3, 1.7, "Exports", C.yellow],
  ];
  nodes.forEach(([x,y,w,label,color]) => { s.addShape(pptx.ShapeType.roundRect,{x,y,w,h:.85,fill:{color:C.card},line:{color,width:2},radius:.08});s.addText(label,{x:x+.08,y:y+.28,w:w-.16,h:.22,fontSize:12,bold:true,color:C.text,align:"center",margin:0}); });
  [[2.65,2.72,.55,0],[5.25,2.72,.55,-.75],[5.25,2.72,.55,.85],[7.85,1.97,.55,0],[7.85,3.57,.55,0],[10.45,2.72,.55,0]].forEach(([x,y,w,h])=>s.addShape(pptx.ShapeType.line,{x,y,w,h,line:{color:C.line,width:2,endArrowType:"triangle"}}));
  s.addText("Docker Compose manages the web, API, worker, database, and cache. Ollama remains an existing host service.", { x: 0.7, y: 5.4, w: 11.8, h: 0.5, fontSize: 12, color: C.muted, align: "center", margin: 0 });
}

// 7. Demo
{
  const s = slide("A five-minute product demo", "Suggested walkthrough");
  const steps = [
    ["01", "Open Samples", "Choose a dense Jabodetabek route."],
    ["02", "Analyze", "Watch the worker match and score the track."],
    ["03", "Explore", "Select a finding and inspect its map icon."],
    ["04", "Scrub speed", "Point from the timeline back to the map."],
    ["05", "Explain & export", "Ask Qwen, then download a report."],
  ];
  steps.forEach((item, i) => {
    const y = 1.65 + i * 0.95;
    s.addText(item[0], { x: 0.7, y, w: 0.7, h: 0.35, fontSize: 18, bold: true, color: C.cyan, margin: 0 });
    s.addText(item[1], { x: 1.6, y, w: 2.3, h: 0.3, fontSize: 16, bold: true, color: C.text, margin: 0 });
    s.addText(item[2], { x: 4.0, y: y + 0.02, w: 7.7, h: 0.3, fontSize: 12, color: C.muted, margin: 0 });
    s.addShape(pptx.ShapeType.line, { x: 0.7, y: y + 0.55, w: 11.5, h: 0, line: { color: C.line, width: 1 } });
  });
}

// 8. Close
{
  const s = pptx.addSlide();
  s.background = { color: C.bg };
  s.addImage({ data: logoData, x: 5.85, y: 1.0, w: 1.6, h: 1.6 });
  s.addText("GPX Inspector", { x: 2, y: 3.0, w: 9.3, h: 0.65, fontSize: 36, bold: true, color: C.text, align: "center", margin: 0 });
  s.addText("From recorded movement to explainable evidence.", { x: 2, y: 3.85, w: 9.3, h: 0.4, fontSize: 18, color: C.cyan, align: "center", margin: 0 });
  s.addText("Local app: http://localhost:3010", { x: 3.7, y: 5.35, w: 5.9, h: 0.3, fontSize: 12, color: C.muted, align: "center", margin: 0 });
}

pptx.writeFile({ fileName: path.join(__dirname, "GPX-Inspector-Presentation.pptx") });
