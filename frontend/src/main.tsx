import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import maplibregl from "maplibre-gl";
import * as echarts from "echarts";
import "maplibre-gl/dist/maplibre-gl.css";
import "./style.css";
import logo from "./logo.svg";
import { listTrips, getTrip, upload, explain, deleteTrip } from "./api";
import type { Trip, Finding } from "./types";

const fmt = (n: number | null | undefined, unit = "") =>
  n == null
    ? "—"
    : `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })}${unit}`;
const escapeHtml = (value: string) => value.replace(/[&<>"']/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
}[character]!));
const findingIcon = (category: string) => category.includes("speed") ? "S" : category.includes("acceleration") ? "+" : category.includes("braking") ? "−" : category.includes("direction") || category.includes("wrong_way") ? "↻" : category.includes("road") ? "!" : "•";
const directionBearing = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) => {
  const lat1 = a.lat * Math.PI / 180, lat2 = b.lat * Math.PI / 180;
  const deltaLon = (b.lon - a.lon) * Math.PI / 180;
  return (Math.atan2(Math.sin(deltaLon) * Math.cos(lat2), Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLon)) * 180 / Math.PI + 360) % 360;
};
function MapView({ trip, selected, onSelect, cursorIndex }: { trip: Trip; selected: Finding | null; onSelect: (finding: Finding) => void; cursorIndex: number | null }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const markers = React.useRef<Map<string, HTMLElement>>(new Map());
  const mapRef = React.useRef<maplibregl.Map | null>(null);
  const cursorMarker = React.useRef<maplibregl.Marker | null>(null);
  useEffect(() => {
    if (!ref.current || !trip.points?.length) return;
    const coords = trip.points.map((p) => [p.lon, p.lat] as [number, number]);
    const arrowFeatures = trip.points.slice(1).flatMap((point, index) => {
      const previous = trip.points![index];
      const gap = point.time && previous.time ? (Date.parse(point.time) - Date.parse(previous.time)) / 1000 : 0;
      if (gap > 15 * 60) return [];
      // Map bearings use 0° = north; the arrow glyph points east at 0°.
      return [{ type: "Feature" as const, properties: { bearing: directionBearing(previous, point) - 90 }, geometry: {
        type: "Point" as const, coordinates: [(previous.lon + point.lon) / 2, (previous.lat + point.lat) / 2],
      } }];
    });
    const matchedSegments = trip.matched_segments?.length
      ? trip.matched_segments.map((segment) => segment.map((p) => [p.lon, p.lat] as [number, number]))
      : [(trip.matched_points || []).map((p) => [p.lon, p.lat] as [number, number])];
    const referenceCoords = (trip.reference_points || []).map((p) => [p.lon, p.lat] as [number, number]);
    const map = new maplibregl.Map({
      container: ref.current,
      style:
        import.meta.env.VITE_MAP_STYLE_URL ||
        "https://tiles.openfreemap.org/styles/dark",
      center: coords[0],
      zoom: 13,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => {
      map.addSource("track", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "LineString", coordinates: coords },
        },
      });
      map.addLayer({
        id: "track",
        type: "line",
        source: "track",
        paint: {
          "line-color": "#22D3EE",
          "line-width": 2,
          "line-opacity": 0.55,
          "line-dasharray": [2, 2],
        },
      });
      map.addSource("track-points", { type: "geojson", data: { type: "FeatureCollection", features: trip.points!.map((point, index) => ({
        type: "Feature", properties: { index }, geometry: { type: "Point", coordinates: [point.lon, point.lat] },
      })) } });
      map.addLayer({ id: "track-points", type: "circle", source: "track-points", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 2, 14, 4],
        "circle-color": "#22D3EE", "circle-stroke-color": "#07111f", "circle-stroke-width": 1,
        "circle-opacity": 0.9,
      } });
      map.addSource("direction-arrows", { type: "geojson", data: { type: "FeatureCollection", features: arrowFeatures } });
      map.addLayer({ id: "direction-arrows", type: "symbol", source: "direction-arrows", minzoom: 9, layout: {
        "text-field": "➤", "text-size": ["interpolate", ["linear"], ["zoom"], 9, 10, 14, 16],
        "text-rotate": ["get", "bearing"], "text-rotation-alignment": "map", "text-allow-overlap": false,
      }, paint: { "text-color": "#67E8F9", "text-halo-color": "#07111f", "text-halo-width": 1.5 } });
      if (referenceCoords.length > 1) {
        map.addSource("reference", { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: referenceCoords } } });
        map.addLayer({ id: "reference", type: "line", source: "reference", paint: { "line-color": "#A78BFA", "line-width": 2, "line-opacity": 0.4, "line-dasharray": [2, 3] } });
      }
      if (matchedSegments.some((segment) => segment.length > 1)) {
        map.addSource("matched", { type: "geojson", data: { type: "Feature", properties: {}, geometry: { type: "MultiLineString", coordinates: matchedSegments.filter((segment) => segment.length > 1) } } });
        map.addLayer({ id: "matched", type: "line", source: "matched", paint: { "line-color": "#60A5FA", "line-width": 5, "line-opacity": 0.95 } });
      }
      map.moveLayer("track-points");
      map.moveLayer("direction-arrows");
      const bounds = coords.reduce(
        (b, c) => b.extend(c),
        new maplibregl.LngLatBounds(coords[0], coords[0]),
      );
      map.fitBounds(bounds, { padding: 55 });
      markers.current.clear();
      trip.findings.forEach((finding) => {
        const point = trip.points?.[Math.min(finding.start_index, coords.length - 1)];
        if (!point) return;
        const element = document.createElement("button");
        element.className = `anomaly-marker ${finding.severity}`;
        element.textContent = findingIcon(finding.category);
        element.title = `${finding.title} (${finding.severity})`;
        element.setAttribute("aria-label", element.title);
        element.onclick = (event) => { event.stopPropagation(); onSelect(finding); };
        new maplibregl.Marker({ element, anchor: "center" }).setLngLat([point.lon, point.lat])
          .setPopup(new maplibregl.Popup({ offset: 18 }).setHTML(`<strong>${finding.title}</strong><br><span>${Math.round(finding.confidence * 100)}% confidence</span>`)).addTo(map);
        markers.current.set(finding.id, element);
      });
    });
    return () => { cursorMarker.current?.remove(); cursorMarker.current = null; mapRef.current = null; map.remove(); };
  }, [trip]);
  useEffect(() => { markers.current.forEach((element, id) => element.classList.toggle("active", id === selected?.id)); }, [selected]);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || cursorIndex == null || !trip.points?.[cursorIndex]) return;
    const point = trip.points[cursorIndex];
    const previous = cursorIndex > 0 ? trip.points[cursorIndex - 1] : null;
    let speed: number | null = point.speed_kmh ?? null;
    if (speed == null && previous?.time && point.time) {
      const dt = (Date.parse(point.time) - Date.parse(previous.time)) / 1000;
      if (dt > 0) {
        const R = 6371e3, la1 = previous.lat * Math.PI / 180, la2 = point.lat * Math.PI / 180;
        const dla = (point.lat - previous.lat) * Math.PI / 180, dlo = (point.lon - previous.lon) * Math.PI / 180;
        const a = Math.sin(dla / 2) ** 2 + Math.cos(la1) * Math.cos(la2) * Math.sin(dlo / 2) ** 2;
        speed = 2 * R * Math.asin(Math.sqrt(a)) / dt * 3.6;
      }
    }
    const html = `<strong>Track point ${cursorIndex + 1}</strong><br><span>${point.time ? new Date(point.time).toLocaleString() : "No timestamp"}${speed == null ? "" : `<br>${speed.toFixed(1)} km/h`}${point.location ? `<br>${escapeHtml(point.location)}` : ""}${point.ignition ? `<br>ACC: ${escapeHtml(point.ignition)}` : ""}</span>`;
    if (!cursorMarker.current) {
      const element = document.createElement("div"); element.className = "timeline-cursor";
      cursorMarker.current = new maplibregl.Marker({ element, anchor: "center" }).setPopup(new maplibregl.Popup({ offset: 16 }));
    }
    cursorMarker.current.setLngLat([point.lon, point.lat]).getPopup().setHTML(html);
    if (!cursorMarker.current.getElement().isConnected) cursorMarker.current.addTo(map);
    if (!cursorMarker.current.getPopup().isOpen()) cursorMarker.current.togglePopup();
    if (!map.getBounds().contains([point.lon, point.lat])) map.easeTo({ center: [point.lon, point.lat], duration: 350 });
  }, [cursorIndex, trip]);
  return <div className="map" ref={ref} />;
}
function Timeline({ trip, onPoint }: { trip: Trip; onPoint: (index: number) => void }) {
  const ref = React.useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current || !trip.points) return;
    const chart = echarts.init(ref.current);
    const speeds = trip.points.map((p, i, a) => {
      if (p.speed_kmh != null) return p.speed_kmh;
      if (!i || !p.time || !a[i - 1].time) return null;
      const dt = (Date.parse(p.time) - Date.parse(a[i - 1].time!)) / 1000;
      const R = 6371e3,
        la1 = (a[i - 1].lat * Math.PI) / 180,
        la2 = (p.lat * Math.PI) / 180,
        dl = ((p.lon - a[i - 1].lon) * Math.PI) / 180,
        dla = ((p.lat - a[i - 1].lat) * Math.PI) / 180;
      const x =
        Math.sin(dla / 2) ** 2 +
        Math.cos(la1) * Math.cos(la2) * Math.sin(dl / 2) ** 2;
      return ((2 * R * Math.asin(Math.sqrt(x))) / dt) * 3.6;
    });
    chart.setOption({
      backgroundColor: "transparent",
      grid: { left: 45, right: 18, top: 20, bottom: 30 },
      xAxis: {
        type: "category",
        data: speeds.map((_, i) => i),
        axisLabel: { color: "#64748b" },
        axisLine: { lineStyle: { color: "#26344a" } },
      },
      yAxis: {
        type: "value",
        name: "km/h",
        nameTextStyle: { color: "#94a3b8" },
        axisLabel: { color: "#64748b" },
        splitLine: { lineStyle: { color: "#1e293b" } },
      },
      tooltip: { trigger: "axis" },
      series: [
        {
          data: speeds,
          type: "line",
          showSymbol: false,
          smooth: 0.25,
          lineStyle: { color: "#60a5fa", width: 2 },
          areaStyle: { color: "rgba(96,165,250,.08)" },
        },
      ],
    });
    chart.on("click", (event) => { if (typeof event.dataIndex === "number") onPoint(event.dataIndex); });
    chart.on("updateAxisPointer", (event: any) => {
      const value = event.axesInfo?.[0]?.value;
      if (value != null) onPoint(Number(value));
    });
    const resize = () => chart.resize();
    addEventListener("resize", resize);
    return () => {
      removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [trip]);
  return <div className="timeline" ref={ref} />;
}
function App() {
  const [trips, setTrips] = useState<Trip[]>([]),
    [active, setActive] = useState<Trip | null>(null),
    [selected, setSelected] = useState<Finding | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [mode, setMode] = useState("car"),
    [page, setPage] = useState<"analysis" | "samples" | "guide" | "settings">("analysis"),
    [samplePacks, setSamplePacks] = useState<any>(null),
    [health, setHealth] = useState<any>(null);
  const [cursorIndex, setCursorIndex] = useState<number | null>(null);
  const refresh = () => listTrips().then(setTrips);
  useEffect(() => {
    refresh();
    fetch("/api/sample-packs").then((r) => r.json()).then(setSamplePacks).catch(() => setSamplePacks({ cities: [] }));
    fetch("/api/health").then((r) => r.json()).then(setHealth).catch(() => setHealth({ status: "unavailable" }));
    const i = setInterval(refresh, 4000);
    return () => clearInterval(i);
  }, []);
  async function open(t: Trip) {
    setPage("analysis");
    setActive(await getTrip(t.id));
    setSelected(null);
    setCursorIndex(null);
  }
  async function waitForAnalysis(id: string) {
    for (let attempt = 0; attempt < 45; attempt++) {
      const trip = await getTrip(id);
      setActive(trip);
      if (trip.status === "complete" || trip.status === "failed") return trip;
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    throw new Error("Analysis is still processing; it will remain in Recent Tracks.");
  }
  async function analyzeSample(city: string, sample: any) {
    setBusy(true);
    try {
      const response = await fetch(`/api/sample-packs/${city}/${sample.file}`);
      if (!response.ok) throw new Error("Sample download failed");
      const file = new File([await response.blob()], sample.file, { type: "application/gpx+xml" });
      const result = await upload(file, sample.mode);
      setMessage("Sample analysis queued");
      setPage("analysis");
      await waitForAnalysis(result.id);
      await refresh();
    } catch (error) { setMessage(String(error)); }
    finally { setBusy(false); }
  }
  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    try {
      const r = await upload(f, mode);
      setMessage("Analysis queued");
      await waitForAnalysis(r.id);
      await refresh();
    } catch (x) {
      setMessage(String(x));
    } finally {
      setBusy(false);
    }
  }
  async function ask() {
    if (!active) return;
    setBusy(true);
    try {
      const r = await explain(active.id);
      setMessage(r.text);
    } catch (x) {
      setMessage(String(x));
    } finally {
      setBusy(false);
    }
  }
  async function removeAnalysis() {
    if (!active) return;
    if (!window.confirm(`Delete “${active.name}” and all of its analysis data? This cannot be undone.`)) return;
    setBusy(true);
    try {
      await deleteTrip(active.id);
      setTrips((current) => current.filter((trip) => trip.id !== active.id));
      setActive(null);
      setSelected(null);
      setCursorIndex(null);
      setMessage("Analysis deleted");
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <img src={logo} />
          <div>
            <b>GPX Inspector</b>
            <span>Mobility intelligence</span>
          </div>
        </div>
        <nav>
          <button className={`nav ${page === "analysis" ? "active" : ""}`} onClick={() => setPage("analysis")}>Analysis</button>
          <button className={`nav ${page === "samples" ? "active" : ""}`} onClick={() => setPage("samples")}>Samples</button>
          <button className={`nav ${page === "guide" ? "active" : ""}`} onClick={() => setPage("guide")}>User Guide</button>
          <button className={`nav ${page === "settings" ? "active" : ""}`} onClick={() => setPage("settings")}>Settings</button>
        </nav>
        <div className="history">
          <label>RECENT TRACKS</label>
          {trips.map((t) => (
            <button
              key={t.id}
              className={`trip ${active?.id === t.id ? "on" : ""}`}
              onClick={() => open(t)}
            >
              <i className={`dot ${t.status}`} />
              <span>
                {t.name}
                <small>
                  {t.mode} · {t.status}
                </small>
              </span>
            </button>
          ))}
        </div>
        <div className="privacy">
          Coordinates are sent to the configured Valhalla matching service.
        </div>
      </aside>
      <main>
        {page === "samples" ? (
          <>
            <header><div><span className="eyebrow">DEMO DATA</span><h1>Jabodetabek sample catalog</h1></div></header>
            <section className="samplegrid">
              {samplePacks?.cities?.map((city: any) => (
                <article key={city.id} className="samplecity">
                  <span className="eyebrow">{city.name.toUpperCase()}</span>
                  <h2>{city.name} scenarios</h2>
                  {city.scenarios.map((sample: any) => (
                    <div className="sample" key={sample.file}>
                      <div><b>{sample.name}</b><p>{sample.description}</p><small>{sample.mode}</small></div>
                      <div className="sampleactions">
                        <a href={`/api/sample-packs/${city.id}/${sample.file}`}>Download</a>
                        <button disabled={busy} onClick={() => analyzeSample(city.id, sample)}>Analyze</button>
                      </div>
                    </div>
                  ))}
                </article>
              ))}
            </section>
          </>
        ) : page === "guide" ? (
          <>
            <header><div><span className="eyebrow">DOCUMENTATION</span><h1>How to use GPX Inspector</h1></div></header>
            <section className="guidegrid">
              <article><span>01</span><div><h2>Upload a track</h2><p>Open Analysis, choose the correct transport mode, then upload a GPX or supported vehicle-history CSV. CSV-reported speed is preserved for analysis.</p></div></article>
              <article><span>02</span><div><h2>Wait for processing</h2><p>The worker calculates local metrics and asks Valhalla to match the coordinates against OpenStreetMap roads.</p></div></article>
              <article><span>03</span><div><h2>Read the map</h2><p>The cyan line is the recorded track. Colored icon points show where findings begin. Click an icon to select its evidence.</p></div></article>
              <article><span>04</span><div><h2>Interpret findings</h2><p>Severity describes impact while confidence describes evidence quality. Review values and thresholds before drawing conclusions.</p></div></article>
              <article><span>05</span><div><h2>Use demo samples</h2><p>Open Samples to download a Jabodetabek GPX or analyze it immediately with its predefined transport mode.</p></div></article>
              <article><span>06</span><div><h2>Export and explain</h2><p>Download PDF, CSV, or GeoJSON. Qwen explains existing deterministic findings without changing their scores.</p></div></article>
            </section>
            <section className="guidelegend"><h2>Map icons</h2><div><b>S</b> Speed</div><div><b>+</b> Acceleration</div><div><b>−</b> Braking</div><div><b>↻</b> Direction</div><div><b>!</b> Off road</div></section>
          </>
        ) : page === "settings" ? (
          <>
            <header><div><span className="eyebrow">CONFIGURATION</span><h1>Settings and service status</h1></div></header>
            <section className="settingsgrid">
              <article><span className="eyebrow">ANALYSIS API</span><h2>{health?.status === "ok" ? "Online" : "Unavailable"}</h2><p>Host endpoint: http://localhost:8010</p></article>
              <article><span className="eyebrow">LOCAL EXPLANATION MODEL</span><h2>{health?.model || "qwen3:14b"}</h2><p>Existing host Ollama; no model installation is performed.</p></article>
              <article><span className="eyebrow">MAP MATCHING</span><h2>Local Valhalla</h2><p>Sumatra OpenStreetMap routing data is downloaded once and retained in Docker storage.</p></article>
              <article><span className="eyebrow">RULE PRESETS</span><h2>Fixed and versioned</h2><p>Car, motorcycle, bicycle, and pedestrian modes are supported.</p></article>
            </section>
          </>
        ) : (
          <>
        <header>
          <div>
            <span className="eyebrow">ANALYSIS WORKSPACE</span>
            <h1>{active?.name || "Inspect a vehicle track"}</h1>
          </div>
          <div className="upload">
            {active && (
              <button className="danger" disabled={busy} onClick={removeAnalysis}>
                Delete analysis
              </button>
            )}
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option>car</option>
              <option>motorcycle</option>
              <option>bicycle</option>
              <option>foot</option>
            </select>
            <label className="primary">
              {busy ? "Working…" : "Upload GPX / CSV"}
              <input
                type="file"
                accept=".gpx,.csv,application/gpx+xml,text/csv"
                hidden
                onChange={onFile}
              />
            </label>
          </div>
        </header>
        <div className="mobile-trips">
          <label htmlFor="mobile-trip-select">Recent analysis</label>
          <select id="mobile-trip-select" value={active?.id || ""} onChange={(event) => {
            const trip = trips.find((item) => item.id === event.target.value);
            if (trip) open(trip);
          }}>
            <option value="" disabled>Select a saved track</option>
            {trips.map((trip) => <option value={trip.id} key={trip.id}>{trip.name} — {trip.mode}</option>)}
          </select>
        </div>
        {!active ? (
          <section className="empty">
            <img src={logo} />
            <h2>See movement differently.</h2>
            <p>
              Upload a GPX file or Indonesian vehicle-history CSV to compare its recorded path with OpenStreetMap
              roads and reveal unusual movement.
            </p>
            <div className="steps">
              <b>01 Upload</b>
              <b>02 Match roads</b>
              <b>03 Inspect findings</b>
            </div>
          </section>
        ) : (
          <>
            <section className="metrics">
              <article>
                <span>RAW DISTANCE</span>
                <strong>{fmt(active.raw_distance_m / 1000, " km")}</strong>
                <small>Geodesic track</small>
              </article>
              <article>
                <span>MATCHED DISTANCE</span>
                <strong>
                  {active.matched_distance_m
                    ? fmt(active.matched_distance_m / 1000, " km")
                    : "Unavailable"}
                </strong>
                <small>OSM road network</small>
              </article>
              <article>
                <span>MAXIMUM SPEED</span>
                <strong>{fmt(active.max_speed_kmh, " km/h")}</strong>
                <small>From timestamps</small>
              </article>
              <article>
                <span>FINDINGS</span>
                <strong>{active.findings.length}</strong>
                <small>
                  {
                    active.findings.filter((f) =>
                      ["high", "critical"].includes(f.severity),
                    ).length
                  }{" "}
                  high priority
                </small>
              </article>
              <article>
                <span>REFERENCE ROUTE</span>
                <strong>
                  {active.route_distance_m
                    ? fmt(active.route_distance_m / 1000, " km")
                    : "Unavailable"}
                </strong>
                <small>OSM endpoint route</small>
              </article>
            </section>
            {active.error && <div className="warning">⚠ {active.error}</div>}
            <section className="workspace">
              <div className="mapwrap">
                <MapView trip={active} selected={selected} onSelect={setSelected} cursorIndex={cursorIndex} />
                <div className="legend">
                  <span className="raw">Recorded points</span>
                  <span className="direction">Travel direction</span>
                  <span className="match">Road-snapped trace</span>
                  <span className="reference">Endpoint-only comparison</span>
                  <span className="anom">Anomaly</span>
                </div>
              </div>
              <div className="findings">
                <div className="panelhead">
                  <div>
                    <span className="eyebrow">EVIDENCE</span>
                    <h2>Detected findings</h2>
                  </div>
                  <button onClick={ask}>Explain with Qwen</button>
                </div>
                <div className="findinglist">
                  {active.findings.length === 0 ? (
                    <p className="muted">
                      No findings under the fixed {active.mode} preset.
                    </p>
                  ) : (
                    active.findings.map((f) => (
                      <button
                        key={f.id}
                        onClick={() => setSelected(f)}
                        className={`finding ${selected?.id === f.id ? "selected" : ""}`}
                      >
                        <span className={`badge ${f.severity}`}>
                          {f.severity}
                        </span>
                        <b>{f.title}</b>
                        <small>
                          {fmt(f.measured_value, f.unit ? " " + f.unit : "")} ·{" "}
                          {Math.round(f.confidence * 100)}% confidence
                        </small>
                      </button>
                    ))
                  )}
                </div>
                {selected && (
                  <div className="evidence">
                    <h3>{selected.title}</h3>
                    <p>{selected.explanation}</p>
                    <dl>
                      <dt>Measured</dt>
                      <dd>
                        {fmt(
                          selected.measured_value,
                          selected.unit ? " " + selected.unit : "",
                        )}
                      </dd>
                      <dt>Threshold</dt>
                      <dd>
                        {fmt(
                          selected.threshold,
                          selected.unit ? " " + selected.unit : "",
                        )}
                      </dd>
                      <dt>Confidence</dt>
                      <dd>{Math.round(selected.confidence * 100)}%</dd>
                    </dl>
                  </div>
                )}
              </div>
            </section>
            <section className="chartbox">
              <div className="panelhead">
                <div>
                  <span className="eyebrow">TRACK PROFILE</span>
                  <h2>Speed timeline</h2>
                </div>
                <div className="exports">
                  <a href={`/api/trips/${active.id}/exports/pdf`}>PDF</a>
                  <a href={`/api/trips/${active.id}/exports/csv`}>CSV</a>
                  <a href={`/api/trips/${active.id}/exports/geojson`}>
                    GeoJSON
                  </a>
                </div>
              </div>
              <Timeline trip={active} onPoint={setCursorIndex} />
            </section>
          </>
        )}
          </>
        )}
        {message && (
          <div className="toast" onClick={() => setMessage("")}>
            <button>×</button>
            <p>{message}</p>
          </div>
        )}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
