"use strict";

/* Countries smaller than this (steradians, about 4000 km²) also get a dot, so
   Singapore or Malta can be clicked without zooming in. Measured on the globe,
   not on screen, so a phone does not turn half the world into dots. */
const DOT_BELOW_AREA = 1e-4;
const DOT_RADIUS = 3;
const SAVE_DELAY_MS = 600;
const PROJECTION_KEY = "weltenbummler.projection";
const REGION_KEY = "weltenbummler.region";
/* "person" value of the family view, which colours a country by how many have been there */
const ALL = "all";
const HEAT_LEVELS = 5;

/* Each projection comes with the outline it is fitted to and filled with. */
const PROJECTIONS = {
  /* Equal-area, so Africa is as large as it really is. */
  equalEarth: () => ({ projection: d3.geoEqualEarth(), frame: { type: "Sphere" } }),
  /* The UN emblem: azimuthal equidistant around the North Pole, cut off
     before Antarctica would wrap around the rim. */
  un: () => ({
    projection: d3.geoAzimuthalEquidistant().rotate([0, -90]).clipAngle(150),
    frame: { type: "Sphere" },
  }),
  /* Mercator runs to infinity at the poles, so it is cut at 58°S / 84°N. */
  mercator: () => ({
    projection: d3.geoMercator(),
    frame: d3.geoGraticule().extentMajor([[-180, -58], [180, 84]]).outline(),
    clip: true,
  }),
};

function stored(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function store(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: the choice just does not survive a reload */
  }
}

const state = {
  me: null,
  users: [],
  person: null, // the user whose map is shown
  country: null, // the country in the detail panel
  editing: false, // the note is open in the textarea rather than shown as text
  projection: PROJECTIONS[stored(PROJECTION_KEY)] ? stored(PROJECTION_KEY) : "equalEarth",
  /* "world" counts countries; "us" splits the USA into its states and counts those */
  region: stored(REGION_KEY) === "us" ? "us" : "world",
  countries: [],
  states: [],
  byId: new Map(),
};

const svg = d3.select("#map");
const zoomLayer = svg.append("g");
const $ = (id) => document.getElementById(id);

const person = () => state.users.find((u) => u.id === state.person);
const isAll = () => state.person === ALL;
const canEdit = () => !isAll() && (state.me.admin || state.person === state.me.id);
const visitorsOf = (id) => state.users.filter((u) => id in u.visits);
/* Countries are "DEU", states "US-CA"; each region counts only its own kind. */
const isState = (id) => id.startsWith("US-");
const inRegion = (id) => isState(id) === (state.region === "us");
const regionVisits = (u) => Object.keys(u.visits).filter(inRegion);
const unit = (n) => (state.region === "us" ? (n === 1 ? "Staat" : "Staaten") : n === 1 ? "Land" : "Länder");
const everyCountry = () => new Set(state.users.flatMap(regionVisits));
const countryName = (id) => state.byId.get(id)?.properties.name ?? id;

/* The flag emoji is spelled with the two regional-indicator letters of the
   ISO code. Natural Earth has no code (-99) for a few disputed areas. */
function flag(id) {
  const iso = state.byId.get(id)?.properties.iso ?? "";
  if (!/^[A-Z]{2}$/.test(iso)) return "";
  return String.fromCodePoint(...[...iso].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

/* Notes are plain text; anything that looks like a web address becomes a link.
   Built from text nodes, never innerHTML, so a note cannot inject markup. */
function renderNote(element, note) {
  element.replaceChildren();
  for (const part of note.split(/(https?:\/\/[^\s<>"]+[^\s<>".,;:!?)\]])/)) {
    if (/^https?:\/\//.test(part)) {
      const a = document.createElement("a");
      a.href = part;
      a.textContent = part.replace(/^https?:\/\//, "").replace(/\/$/, "");
      a.target = "_blank";
      a.rel = "noopener";
      element.append(a);
    } else if (part) {
      element.append(document.createTextNode(part));
    }
  }
}

async function api(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-Requested-With": "weltenbummler" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("logged out");
  }
  if (!response.ok) throw new Error(`${method} ${url}: ${response.status}`);
  return response.status === 204 ? null : response.json();
}

/* ---------- people and their lists ---------- */

function renderPeople() {
  const list = $("people");
  /* most countries first: a little competition is half the fun */
  const ranked = [...state.users].sort(
    (a, b) => regionVisits(b).length - regionVisits(a).length || a.name.localeCompare(b.name, "de"),
  );
  const entry = (id, name, n) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.user = id;
    button.append(name);
    const count = document.createElement("span");
    count.className = "count";
    count.textContent = n;
    button.append(count);
    if (id === state.person) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => selectPerson(id));
    li.append(button);
    return li;
  };
  list.replaceChildren(
    entry(ALL, "Alle", everyCountry().size),
    ...ranked.map((u) => entry(u.id, u.name, regionVisits(u).length)),
  );
}

function renderVisits() {
  const all = isAll();
  const p = all ? null : person();
  const byName = (a, b) => countryName(a).localeCompare(countryName(b), "de");
  /* the family list puts the countries most of us have seen first */
  const ids = all
    ? [...everyCountry()].sort((a, b) => visitorsOf(b).length - visitorsOf(a).length || byName(a, b))
    : regionVisits(p).sort(byName);
  const owner = all ? "Alle" : p.name;
  $("list-title").textContent = `${owner}: ${ids.length} ${unit(ids.length)}`;
  $("visits").replaceChildren(
    ...ids.map((id) => {
      const li = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "link country-name";
      const icon = document.createElement("span");
      icon.className = "flag";
      icon.textContent = flag(id);
      icon.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = countryName(id);
      button.append(icon, label);
      button.addEventListener("click", () => openCountry(id));
      li.append(button);
      if (all) {
        const who = document.createElement("p");
        const visitors = visitorsOf(id);
        who.textContent = visitors.length === state.users.length ? "alle" : visitors.map((u) => u.name).join(", ");
        li.append(who);
      } else if (p.visits[id]) {
        const note = document.createElement("p");
        renderNote(note, p.visits[id]);
        li.append(note);
      }
      return li;
    }),
  );
}

function heat(id) {
  return Math.min(visitorsOf(id).length, HEAT_LEVELS);
}

function paintMap() {
  const all = isAll();
  const visits = all ? {} : person().visits;
  const shapes = zoomLayer
    .selectAll(".country, .dot")
    .classed("visited", (d) => d.id in visits)
    .classed("selected", (d) => d.id === state.country);
  for (let level = 1; level <= HEAT_LEVELS; level++) {
    shapes.classed(`heat-${level}`, (d) => all && heat(d.id) === level);
  }
  renderLegend();
}

function renderLegend() {
  const legend = $("legend");
  legend.hidden = !isAll();
  if (legend.hidden) return;
  const levels = Math.min(state.users.length, HEAT_LEVELS);
  legend.replaceChildren(
    ...Array.from({ length: levels }, (_, i) => {
      const item = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.className = `heat-${i + 1}`;
      const n = i + 1;
      const label = n === state.users.length ? "alle" : n === levels && n < state.users.length ? `${n}+` : `${n}`;
      item.append(swatch, label);
      return item;
    }),
  );
}

function render() {
  renderPeople();
  renderVisits();
  paintMap();
  renderDetail();
}

function selectPerson(id) {
  flushNote();
  state.person = id;
  state.editing = false;
  render();
}

/* ---------- detail panel ---------- */

let saveTimer = null;

function renderDetail() {
  const panel = $("detail");
  const id = state.country;
  panel.hidden = id === null;
  if (id === null) return;
  $("detail-name").textContent = `${flag(id)} ${countryName(id)}`.trim();
  if (isAll()) {
    renderFamilyDetail(id);
    return;
  }
  const p = person();
  const visited = id in p.visits;
  const editable = canEdit();
  const saved = p.visits[id] ?? "";
  const editing = editable && visited && state.editing;
  $("detail-toggle").hidden = !editable;
  $("detail-visited").checked = visited;
  $("detail-who").textContent = p.id === state.me.id ? "Hier war ich" : `Hier war ${p.name}`;
  const note = $("detail-note");
  note.hidden = !editing;
  if (document.activeElement !== note) note.value = saved;
  const text = $("detail-text");
  text.hidden = editing || (editable && !saved);
  if (!visited) text.textContent = `${p.name} war noch nicht hier.`;
  else if (saved) renderNote(text, saved);
  else text.textContent = `${p.name} war hier.`;
  const edit = $("detail-edit");
  edit.hidden = !editable || !visited || editing;
  edit.textContent = saved ? "Notiz bearbeiten" : "Notiz hinzufügen";
  $("detail-status").textContent = "";
}

function renderFamilyDetail(id) {
  for (const hidden of ["detail-toggle", "detail-note", "detail-edit"]) $(hidden).hidden = true;
  const text = $("detail-text");
  text.hidden = false;
  const visitors = visitorsOf(id);
  if (visitors.length === 0) {
    text.textContent = "Hier war noch niemand.";
  } else {
    text.replaceChildren(
      ...visitors.map((u) => {
        const line = document.createElement("span");
        line.className = "visitor";
        const name = document.createElement("strong");
        name.textContent = u.name;
        line.append(name);
        if (u.visits[id]) {
          const note = document.createElement("span");
          renderNote(note, u.visits[id]);
          line.append(note);
        }
        return line;
      }),
    );
  }
  $("detail-status").textContent = "";
}

function status(message) {
  $("detail-status").textContent = message;
}

async function openCountry(id) {
  flushNote();
  state.country = id;
  state.editing = false;
  const p = person();
  /* the first click on a grey country marks it, so the common case stays one click */
  if (canEdit() && !(id in p.visits)) {
    state.editing = true;
    /* a state implies the country, so the world map stays consistent */
    if (isState(id) && !("USA" in p.visits)) await setVisited("USA", true);
    await setVisited(id, true);
    $("detail-note").focus();
  } else {
    render();
  }
}

function closeDetail() {
  flushNote();
  state.country = null;
  render();
}

async function setVisited(id, visited) {
  const p = person();
  try {
    if (visited) {
      await api("PUT", `/api/users/${p.id}/visits/${id}`, { note: p.visits[id] ?? "" });
      p.visits[id] = p.visits[id] ?? "";
    } else {
      await api("DELETE", `/api/users/${p.id}/visits/${id}`);
      delete p.visits[id];
    }
    render();
  } catch (e) {
    render();
    status("Speichern ging nicht, bitte nochmal.");
    console.error(e);
  }
}

async function saveNote(userId, id, note) {
  const p = state.users.find((u) => u.id === userId);
  try {
    await api("PUT", `/api/users/${userId}/visits/${id}`, { note });
    p.visits[id] = note;
    renderVisits();
    if (state.person === userId && state.country === id) status("Gespeichert");
  } catch (e) {
    status("Speichern ging nicht, bitte nochmal.");
    console.error(e);
  }
}

/* Saving belongs to the user and country it was typed for, even if the
   panel has moved on by the time the timer fires. */
let pending = null;

function scheduleNote() {
  pending = { userId: state.person, id: state.country, note: $("detail-note").value };
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushNote, SAVE_DELAY_MS);
}

function flushNote() {
  clearTimeout(saveTimer);
  if (pending === null) return;
  const { userId, id, note } = pending;
  pending = null;
  saveNote(userId, id, note);
}

$("detail-note").addEventListener("input", scheduleNote);
$("detail-note").addEventListener("blur", flushNote);
$("detail-edit").addEventListener("click", () => {
  state.editing = true;
  renderDetail();
  $("detail-note").focus();
});
$("detail-visited").addEventListener("change", (event) => {
  const id = state.country;
  const note = person().visits[id];
  if (!event.target.checked && note && !confirm(`${countryName(id)} entfernen? Die Notiz geht dabei verloren.`)) {
    event.target.checked = true;
    return;
  }
  pending = null;
  clearTimeout(saveTimer);
  setVisited(id, event.target.checked);
});
document.querySelector("#detail .close").addEventListener("click", closeDetail);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.country !== null) closeDetail();
});
window.addEventListener("beforeunload", flushNote);

/* ---------- map ---------- */

function draw() {
  const { width, height } = svg.node().getBoundingClientRect();
  if (!width || !height) return;
  const { projection, frame, clip } = PROJECTIONS[state.projection]();
  projection.fitExtent([[8, 8], [width - 8, height - 8]], frame);
  const path = d3.geoPath(projection);
  if (clip) projection.clipExtent(path.bounds(frame));

  zoomLayer.selectAll("*").remove();
  zoomLayer.append("path").attr("class", "sphere").attr("d", path(frame));
  zoomLayer.append("path").attr("class", "graticule").attr("d", path(d3.geoGraticule10()));

  /* in the USA view the country gives way to its states */
  const features =
    state.region === "us" ? [...state.countries.filter((c) => c.id !== "USA"), ...state.states] : state.countries;
  const shapes = zoomLayer
    .append("g")
    .selectAll("path")
    .data(features)
    .join("path")
    .attr("class", "country")
    .attr("d", path);

  const small = features.filter((d) => d3.geoArea(d) < DOT_BELOW_AREA && path.centroid(d).every(Number.isFinite));
  const dots = zoomLayer
    .append("g")
    .selectAll("circle")
    .data(small)
    .join("circle")
    .attr("class", "dot")
    .attr("r", DOT_RADIUS)
    .attr("cx", (d) => path.centroid(d)[0])
    .attr("cy", (d) => path.centroid(d)[1]);

  for (const sel of [shapes, dots]) {
    sel
      .on("click", (_, d) => openCountry(d.id))
      .append("title")
      .text((d) => d.properties.name);
  }

  const zoom = d3
    .zoom()
    .scaleExtent([1, 12])
    .translateExtent([[0, 0], [width, height]])
    .on("zoom", (event) => {
      zoomLayer.attr("transform", event.transform);
      /* keep the dots the same size on screen */
      dots.attr("r", DOT_RADIUS / event.transform.k);
    });
  svg.call(zoom).call(zoom.transform, state.region === "us" ? usView(path, width, height) : d3.zoomIdentity);
  paintMap();
}

/* Zoom onto the lower 48 and mainland Alaska. Alaska's whole outline would not
   do: the Aleutians cross the date line and stretch the box around the world. */
function usView(path, width, height) {
  const lower48 = state.states.filter((s) => s.id !== "US-AK" && s.id !== "US-HI");
  /* points around mainland Alaska; several, since most projections bend the meridians */
  const alaska = [[-168, 54], [-168, 60], [-168, 66], [-160, 72], [-141, 71], [-130, 54]];
  const corners = [...lower48.flatMap((s) => path.bounds(s)), ...alaska.map(path.projection())].filter(
    (p) => p && p.every(Number.isFinite),
  );
  const [x0, x1] = d3.extent(corners, (p) => p[0]);
  const [y0, y1] = d3.extent(corners, (p) => p[1]);
  const k = Math.min(12, 0.9 / Math.max((x1 - x0) / width, (y1 - y0) / height));
  return d3.zoomIdentity
    .translate(width / 2, height / 2)
    .scale(k)
    .translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
}

function setRegion(region) {
  flushNote();
  state.region = region;
  state.country = null;
  state.editing = false;
  store(REGION_KEY, region);
  $("region").setAttribute("aria-pressed", String(region === "us"));
  draw();
  render();
}

function setProjection(name) {
  state.projection = name;
  store(PROJECTION_KEY, name);
  document.querySelectorAll("[data-projection]").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.projection === name));
  });
  draw();
}

/* ---------- start ---------- */

Promise.all([fetch("/static/countries.json").then((r) => r.json()), api("GET", "/api/data")]).then(
  ([topology, data]) => {
    state.countries = topojson.feature(topology, topology.objects.countries).features;
    state.states = topojson.feature(topology, topology.objects.states).features;
    state.byId = new Map([...state.countries, ...state.states].map((c) => [c.id, c]));
    state.me = data.me;
    state.users = data.users;
    state.person = data.me.id;
    document.querySelectorAll("[data-projection]").forEach((b) => {
      b.addEventListener("click", () => setProjection(b.dataset.projection));
    });
    $("region").addEventListener("click", () => setRegion(state.region === "us" ? "world" : "us"));
    $("region").setAttribute("aria-pressed", String(state.region === "us"));
    setProjection(state.projection);
    new ResizeObserver(draw).observe(svg.node());
    render();
    window.weltenbummler = { state };
  },
);
