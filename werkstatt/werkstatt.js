// Baum-Werkstatt – die Oberfläche. Prüfen, Übersetzen und Speichern macht werkstatt.py mit dem Erzeuger der Firmware,
// im Browser unter Pyodide (HE-9: kein zweiter Erzeuger in JavaScript). Was es an Lichtern, Bausteinen, Anweisungen,
// Liedern gibt und was ein Schlüssel bedeutet, fragt die Seite den Erzeuger und sein Schema (S5) – sie kennt den Baum
// nicht auswendig. Konzept: docs/concepts/offen/baum_werkstatt.md.
"use strict";

const W = { py: null, stand: null, auskunft: null, modus: "eigene", handle: null, dateiname: null, teil: "steckbrief",
  stufe: 1, liste: "on_correct_code", ablauf: null, vorlage: null, start: performance.now(), bereit: null };
const $ = (sel, wurzel = document) => wurzel.querySelector(sel);
const NAMEN_LISTEN = { on_correct_code: "nach dem richtigen Code", on_repeat: "Bestätigen lang", on_power_on: "beim Einstecken" };
const RUHE = { sleep: "schläft", wink: "zwinkert", breathe: "atmet", sparkle: "funkelt", gold: "golden, alles an", dark: "dunkel" };
const NOTE = { stop_show: "beendet die Vorführung (Regel)", stop_then_note: "beendet sie und spielt das Lied",
  skip_to_next: "springt zum nächsten Baustein", skip_to_last: "springt zum letzten Baustein", ignore: "tut nichts" };

// --- Python ------------------------------------------------------------------------------------------------------

function ladestand(text) { $("#ladestand").textContent = text; }

async function pythonLaden() {
  ladestand("Python für den Browser wird geladen …");
  W.py = await loadPyodide();
  ladestand("Erzeuger und Werkstatt werden geladen …");
  const holen = async (pfad) => { const r = await fetch(pfad); if (!r.ok) throw new Error(pfad + ": " + r.status); return r.text(); };
  const [erzeuger, werkstatt, lichter, bib, reg, vorlage] = await Promise.all([holen("daten/erzeuger.py"),
    holen("werkstatt.py"), holen("daten/lichter.json"), holen("daten/liedbibliothek.json"), holen("daten/register.json"),
    holen("daten/vorlage.baum.json")]);
  W.py.FS.mkdirTree("/home/pyodide/werkstatt");
  W.py.FS.writeFile("/home/pyodide/werkstatt/erzeuger.py", erzeuger);
  W.py.FS.writeFile("/home/pyodide/werkstatt/werkstatt.py", werkstatt);
  W.py.globals.set("_lichter", lichter);
  W.py.globals.set("_bib", bib);
  W.py.globals.set("_reg", reg);
  const auskunft = W.py.runPython(`
import sys
sys.path.insert(0, "/home/pyodide/werkstatt")
import erzeuger, werkstatt
werkstatt.einrichten(erzeuger, _lichter, _bib, _reg)`);
  W.auskunft = JSON.parse(auskunft);
  W.vorlage = vorlage;
}

function rufe(name, ...args) {
  const antwort = JSON.parse(W.py.globals.get("werkstatt").aufruf(name, JSON.stringify(args)));
  if ("fehler" in antwort) throw new Error(antwort.fehler);
  return antwort.ok;
}

// --- Hilfen ------------------------------------------------------------------------------------------------------

function el(tag, attr = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attr)) {
    if (k === "text") e.textContent = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v === true) e.setAttribute(k, "");
    else if (v !== false && v != null) e.setAttribute(k, v);
  }
  for (const k of kinder.flat()) if (k != null) e.append(k.nodeType ? k : document.createTextNode(String(k)));
  return e;
}

function holeWert(pfad) {
  let w = W.stand.teile;
  for (const k of pfad) { if (w == null) return undefined; w = w[k]; }
  return w;
}

function alsText(v) { return v === undefined ? "" : typeof v === "string" ? v : JSON.stringify(v); }

function ausText(t) {
  if (t.trim() === "") return undefined;
  try { return JSON.parse(t); } catch { return t; }
}

function aendere(pfad, wert) {
  try {
    W.stand.fehler = wert === undefined ? rufe("loesche", pfad) : rufe("setze", pfad, wert);
    W.stand.teile = rufe("stand").teile;
  } catch (e) { melde(e.message); }
  zeichne();
}

function melde(text) { alert(text); }

function erklaerung(datei, pfad) {
  // datei: heft | ablaeufe | lieder; pfad: ["stage", "idle"] o. ä. – die description aus dem Schema des Erzeugers
  const s = W.auskunft.schema[datei + ".schema.json"];
  let knoten = s;
  for (const k of pfad) {
    if (!knoten) return "";
    if (k.startsWith("$")) knoten = s.$defs[k.slice(1)];
    else knoten = (knoten.properties || {})[k];
  }
  const text = knoten && knoten.description ? knoten.description : "";
  // „nur zum Lesen“ heißt im Schema: für Menschen, der Baum nutzt es nicht – in einem Formular klänge es nach „gesperrt“
  return text.replace(/, nur zum Lesen$/, " – für Menschen, der Baum zeigt ihn nicht");
}

function feldText(pfad, attr = {}) {
  return el("input", { value: alsText(holeWert(pfad)), "data-pfad": pfad.join("."), ...attr,
    onchange: (ev) => aendere(pfad, ausText(ev.target.value)) });
}

function auswahl(pfad, optionen, leer) {
  // optionen: [[wert, beschriftung]]; leer: Beschriftung für „nicht gesetzt“ (dann löschen) oder null
  const jetzt = holeWert(pfad);
  const s = el("select", { "data-pfad": pfad.join("."), onchange: (ev) => {
    const v = ev.target.value;
    aendere(pfad, v === "\u0000" ? undefined : ausText(v));
  } });
  if (leer !== null) s.append(el("option", { value: "\u0000", text: leer }));
  for (const [w, b] of optionen) s.append(el("option", { value: alsText(w), text: b, selected: alsText(w) === alsText(jetzt) }));
  return s;
}

function lichtNamen() {
  const ketten = W.auskunft.garlands || {};
  const namen = W.auskunft.leds.filter((l) => !Object.values(ketten).includes(l.channel)).map((l) => l.name);
  return [...namen.sort((a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))), ...Object.keys(ketten), "star"];
}

function nameVonKanal(kanal) {
  for (const [n, k] of Object.entries(W.auskunft.garlands || {})) if (k === kanal) return n;
  const l = W.auskunft.leds.find((x) => x.channel === kanal);
  return l ? l.name : null;
}

// --- Zeichnen ----------------------------------------------------------------------------------------------------

function zeichne() {
  $("#fehlerzahl").textContent = W.stand.fehler.length || "";
  for (const b of document.querySelectorAll("#reiter button")) b.classList.toggle("an", b.dataset.teil === W.teil);
  for (const s of document.querySelectorAll(".teil")) s.hidden = s.id !== "teil-" + W.teil;
  const ziel = $("#teil-" + W.teil);
  ziel.replaceChildren();
  ({ steckbrief, tage, ablaeufe, lieder, codes, pruefen, baum: aufDenBaum })[W.teil](ziel);
  markiereFehler();
  $("#datei").textContent = W.stand.art === "offiziell" ? "offizielles Heft " + W.stand.ordner
    : (W.dateiname || "mein_baum.baum.json") + " · auf dem Baum: " + W.stand.auf_dem_baum;
}

function markiereFehler() {
  for (const f of W.stand.fehler) {
    const teil = { "heft.json": "heft", "ablaeufe.json": "ablaeufe", "lieder.json": "lieder", codes: "codes" }[f.file] || "heft";
    const wo = (f.where || "").split(" ")[0].replace(/\[(\d+)\]/g, ".$1");
    const pfad = (wo.startsWith(teil) ? wo : teil + "." + wo).replace(/^codes\.codes/, "codes");
    for (const e of document.querySelectorAll("[data-pfad]")) {
      if (e.dataset.pfad === pfad || e.dataset.pfad.startsWith(pfad + ".")) {
        e.classList.add("fehlerhaft");
        e.title = f.text;
      }
    }
  }
}

function steckbrief(ziel) {
  const h = W.stand.teile.heft;
  ziel.append(el("h2", { text: "Steckbrief" }));
  const zeile = (name, eingabe, pfadSchema) => el("div", { class: "feld" }, el("label", { text: name }),
    el("div", {}, eingabe, el("div", { class: "erklaerung", text: erklaerung("heft", pfadSchema) })));
  ziel.append(zeile("Titel", feldText(["heft", "title"], { size: 40 }), ["title"]));
  if (W.stand.art === "baum") {
    const muster = W.auskunft.muster.map((m) => [m.pattern, "E" + m.pattern + " · Code " + m.select_code]);
    ziel.append(zeile("Baummuster", auswahl(["heft", "user_pattern"], muster, null), ["user_pattern"]));
    const m = W.auskunft.muster.find((x) => x.pattern === h.user_pattern);
    const bild = m && "muster/e" + String(m.pattern).padStart(2, "0");
    if (m) ziel.append(el("div", { class: "feld muster" }, el("span"), el("div", {},
      el("img", { src: bild + ".png", alt: "Startbild E" + m.pattern }),
      el("p", { class: "leise", text: "Im Wahlmodus: Schalter " + m.select_code + ", dann Bestätigen. Auf dem Baum liegt "
        + "das Heft unter " + W.stand.auf_dem_baum + "." }),
      el("p", { id: "muster-laden" }, "Das Bild fürs gedruckte Heft: ",
        el("a", { href: bild + ".svg", download: "baummuster_e" + m.pattern + ".svg", text: "SVG" }), " · ",
        el("a", { href: bild + ".png", download: "baummuster_e" + m.pattern + ".png", text: "PNG" })))));
  } else {
    ziel.append(zeile("Wahlmodus", el("code", { text: h.select_code }), ["select_code"]));
    ziel.append(zeile("Startbild", el("code", { text: (h.boot_leds || []).join(" · ") }), ["boot_leds"]));
    ziel.append(el("p", { class: "leise", text: "Code und Startbild eines offiziellen Hefts stehen im Register "
      + "(firmware/basis/register.json); hier nur zur Ansicht." }));
  }
  const wach = el("input", { type: "checkbox", checked: !!h.all_awake, "data-pfad": "heft.all_awake",
    onchange: (ev) => aendere(["heft", "all_awake"], ev.target.checked ? true : undefined) });
  ziel.append(zeile("Von Anfang an wach", wach, ["all_awake"]));
  ziel.append(zeile("Eigene Fortschrittsanzeige", feldText(["heft", "progress_leds"], { size: 60 }), ["progress_leds"]));
  if (h.transitions) {
    ziel.append(el("h3", { text: "Wege" }));
    ziel.append(el("p", { class: "leise", text: "Dieses Heft hat Wege (verzweigen, mehrere Enden). Die Werkstatt "
      + "speichert sie unverändert, zeigt sie in dieser Fassung aber nur als Text." }));
    ziel.append(el("pre", { text: JSON.stringify(h.transitions, null, 1) }));
  }
  if (W.stand.art === "baum") {
    ziel.append(el("h3", { text: "Das gedruckte Heft" }));
    ziel.append(el("p", { id: "vorlagen" }, "Die Werkstatt druckt nichts; dafür gibt es zwei Vorlagen mit Titelseite, "
      + "„So geht es“, den 24 Tagen und der Bedienung des Baums. Für Text: ",
      el("a", { href: "vorlagen/heft_text.odt", download: true, text: ".odt" }), " · ",
      el("a", { href: "vorlagen/heft_text.docx", download: true, text: ".docx" }),
      ". Für freie Gestaltung, je Tag eine Seite: ",
      el("a", { href: "vorlagen/heft_layout.odp", download: true, text: ".odp" }), " · ",
      el("a", { href: "vorlagen/heft_layout.pptx", download: true, text: ".pptx" }), "."));
  }
}

function baumBild() {
  const leds = W.auskunft.leds;
  const xs = leds.map((l) => l.x), ys = leds.map((l) => l.y);
  const minx = Math.min(...xs) - 14, maxx = Math.max(...xs) + 14, maxy = Math.max(...ys) + 34, miny = Math.min(...ys) - 12;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `${minx} 0 ${maxx - minx} ${maxy - miny}`);
  svg.setAttribute("class", "baum");
  const st = W.stand.teile.heft.stages;
  const wach = new Set(), neu = st[W.stufe] ? st[W.stufe].new_led : null;
  for (let i = 1; i <= W.stufe && i < st.length; i++) if (st[i].new_led) wach.add(st[i].new_led);
  const farbe = { red: "#c8323a", "yellow/gold": "#e0b030", yellow: "#f0d040", green: "#3a9a50", blue: "#3a6ad0",
    white: "#f4f4f4", "": "#999" };
  const kreis = (x, y, r, fuell, name, titel) => {
    const c = document.createElementNS(svg.namespaceURI, "circle");
    c.setAttribute("cx", x); c.setAttribute("cy", y); c.setAttribute("r", r); c.setAttribute("fill", fuell);
    c.setAttribute("class", "licht" + (wach.has(name) ? " wach" : "") + (name === neu ? " neu" : ""));
    const t = document.createElementNS(svg.namespaceURI, "title"); t.textContent = titel; c.append(t);
    c.addEventListener("click", () => {
      if (W.stufe >= 1 && W.stufe < st.length) aendere(["heft", "stages", W.stufe, "new_led"], name);
    });
    svg.append(c);
  };
  for (const l of leds) {
    const name = nameVonKanal(l.channel);
    kreis(l.x, maxy - l.y, { "5mm": 4.2, "3mm": 3.2, "1.8mm": 2.4 }[l.size] || 3, farbe[l.color] || "#999", name,
      name + (name !== l.name ? " (" + l.name + ")" : "") + " – " + l.color + ", " + l.where);
  }
  kreis(0, 12, 6, "#e0b030", "star", "der Stern");
  return svg;
}

function tage(ziel) {
  const h = W.stand.teile.heft, st = h.stages, songs = Object.entries(W.auskunft.songs);
  const eigene = Object.keys((W.stand.teile.lieder || {}).own_songs || {});
  ziel.append(el("h2", { text: "Tage" }));
  ziel.append(el("p", { class: "leise", text: "Eine Zeile je Stufe; Stufe 0 ist der Baum vor dem ersten Code. Klick eine "
    + "Zeile an und dann ein Licht im Baum: es kommt an diesem Tag dazu. „wie alle Tage“ nimmt die Vorgabe der ersten Zeile." }));
  const lichter = lichtNamen().map((n) => [n, n === "star" ? "der Stern" : n]);
  const sterne = [["off", "aus"], ["gold", "gold"], ["white", "weiß"],
    ...Array.from({ length: 36 }, (_, i) => [i * 10, i * 10 + "°"])];
  const ruhen = W.auskunft.idle.map((r) => [r, RUHE[r] || r]);
  const noten = [[{ action: "play_song", song: "o_tannenbaum" }, "O Tannenbaum"],
    ...[...eigene, ...songs.map(([n]) => n)].filter((n, i, a) => a.indexOf(n) === i)
      .map((n) => [{ action: "play_song", song: n }, (W.auskunft.songs[n] || n)])];
  const tabelle = el("table", {}, el("tr", {}, ["Stufe", "Titel", "neues Licht", "Stern", "Ruhebild", "Note kurz", "Vorführung"]
    .map((t) => el("th", { text: t }))));
  const zeile = (i, basis, name) => {
    const p = (k) => [...basis, k];
    const knopf = el("button", { class: "leicht", text: "ändern", onclick: (ev) => { ev.stopPropagation(); W.stufe = i; zeichne(); } });
    const vorf = (holeWert(p("on_correct_code")) || (h.defaults || {}).on_correct_code || []).map((b) => b.action).join(" · ");
    return el("tr", { class: (i === null ? "vorgabe" : "") + (i === W.stufe ? " gewaehlt" : ""),
      onclick: () => { if (i !== null) { W.stufe = i; zeichne(); } } },
      el("td", { text: name }), el("td", {}, feldText(p("title"), { size: 12 })),
      el("td", {}, i === 0 || i === null ? "" : auswahl(p("new_led"), lichter, "–")),
      el("td", {}, auswahl(p("star_hue"), sterne, i === null ? "–" : "wie alle Tage")),
      el("td", {}, auswahl(p("idle"), ruhen, i === null ? "–" : "wie alle Tage")),
      el("td", {}, auswahl(p("on_note_short"), noten, i === null ? "nichts" : "wie alle Tage")),
      el("td", {}, el("span", { class: "leise vorschau", text: vorf }), knopf));
  };
  tabelle.append(zeile(null, ["heft", "defaults"], "alle Tage"));
  st.forEach((_, i) => tabelle.append(zeile(i, ["heft", "stages", i], String(i))));
  ziel.append(el("div", { class: "zweispaltig" }, el("div", { class: "baum-spalte" },
    el("h3", { text: "Stufe " + W.stufe }), baumBild()), el("div", { class: "tabelle" }, tabelle)));
  ziel.append(vorfuehrungen(W.stufe));
}

function bausteinFeld(pfadListe, i, b, feld) {
  const sequenzen = Object.keys((W.stand.teile.ablaeufe || {}).sequences || {});
  const lieder = [...Object.keys((W.stand.teile.lieder || {}).own_songs || {}), ...Object.keys(W.auskunft.songs)];
  const setze = (wert) => {
    const neu = holeWert(pfadListe).map((x, j) => j === i ? { ...x, [feld]: wert } : x);
    if (wert === undefined) delete neu[i][feld];
    aendere(pfadListe, neu);
  };
  const wahl = (optionen) => {
    const s = el("select", { onchange: (ev) => setze(ev.target.value === "" ? undefined : ev.target.value) },
      el("option", { value: "", text: "–" }));
    for (const o of optionen) s.append(el("option", { value: o, text: W.auskunft.songs[o] || o, selected: b[feld] === o }));
    return s;
  };
  let eingabe;
  if (feld === "song") eingabe = wahl(lieder);
  else if (feld === "sequence") eingabe = wahl(sequenzen);
  else if (feld === "signal") eingabe = wahl(W.auskunft.signals);
  else if (feld === "until") eingabe = wahl(["end", "day_mark"]);
  else if (feld === "base_frame") eingabe = el("input", { type: "checkbox", checked: !!b.base_frame,
    onchange: (ev) => setze(ev.target.checked ? true : undefined) });
  else eingabe = el("input", { value: alsText(b[feld]), size: 6, onchange: (ev) => setze(ausText(ev.target.value)) });
  return el("label", { title: erklaerung("heft", ["$action", feld]) }, feld + " ", eingabe);
}

function bausteinListe(pfadListe) {
  const liste = holeWert(pfadListe);
  const kasten = el("div", { class: "bausteine", "data-pfad": pfadListe.join(".") });
  if (!Array.isArray(liste)) {
    kasten.append(el("p", { class: "leise" }, "Diese Stufe nimmt die Vorführung aller Tage. ",
      el("button", { class: "leicht", text: "eigene anlegen", onclick: () => {
        const vorgabe = (W.stand.teile.heft.defaults || {})[pfadListe[pfadListe.length - 1]] || [];
        aendere(pfadListe, JSON.parse(JSON.stringify(vorgabe)));
      } })));
    return kasten;
  }
  liste.forEach((b, i) => {
    const art = el("select", { onchange: (ev) => aendere(pfadListe, liste.map((x, j) => j === i ? { action: ev.target.value } : x)) });
    for (const [n, d] of Object.entries(W.auskunft.actions)) art.append(el("option", { value: n, text: n, title: d.description, selected: n === b.action }));
    const note = el("select", { title: "was die Note währenddessen tut",
      onchange: (ev) => {
        const neu = liste.map((x, j) => j === i ? { ...x, on_note: ev.target.value } : x);
        if (ev.target.value === "stop_show") delete neu[i].on_note;
        aendere(pfadListe, neu);
      } });
    for (const n of W.auskunft.on_note) note.append(el("option", { value: n, text: NOTE[n] || n, selected: (b.on_note || "stop_show") === n }));
    const schiebe = (d) => { const neu = [...liste]; const [x] = neu.splice(i, 1); neu.splice(i + d, 0, x); aendere(pfadListe, neu); };
    kasten.append(el("div", { class: "baustein", "data-pfad": pfadListe.concat(i).join(".") }, el("strong", { text: (i + 1) + "." }), art,
      ...(W.auskunft.actions[b.action] ? W.auskunft.actions[b.action].fields : []).map((f) => bausteinFeld(pfadListe, i, b, f)),
      el("label", {}, "Note: ", note),
      el("button", { class: "leicht", text: "↑", disabled: i === 0, onclick: () => schiebe(-1) }),
      el("button", { class: "leicht", text: "↓", disabled: i === liste.length - 1, onclick: () => schiebe(1) }),
      el("button", { class: "leicht", text: "✕", onclick: () => aendere(pfadListe, liste.filter((_, j) => j !== i)) })));
  });
  kasten.append(el("div", {}, el("button", { class: "leicht", text: "+ Baustein",
    onclick: () => aendere(pfadListe, [...liste, { action: "play_signal", signal: "correct" }]) })));
  return kasten;
}

function vorfuehrungen(i) {
  const basis = i === null ? ["heft", "defaults"] : ["heft", "stages", i];
  const kasten = el("div", { class: "karte" }, el("h3", { text: "Stufe " + i + ": Vorführungen" }));
  const reiter = el("div", { class: "leiste" });
  for (const [k, n] of Object.entries(NAMEN_LISTEN)) {
    reiter.append(el("button", { class: k === W.liste ? "" : "leicht", text: n, onclick: () => { W.liste = k; zeichne(); } }));
  }
  kasten.append(reiter, el("p", { class: "erklaerung", text: erklaerung("heft", ["$stage", W.liste]) }));
  kasten.append(bausteinListe([...basis, W.liste]));
  if (Array.isArray(holeWert([...basis, W.liste]))) {
    kasten.append(el("button", { class: "leicht", text: "wie alle Tage", onclick: () => aendere([...basis, W.liste], undefined) }));
  }
  const sequenzen = Object.keys((W.stand.teile.ablaeufe || {}).sequences || {}).map((n) => [n, n]);
  kasten.append(el("div", { class: "feld" }, el("label", { text: "Schrittliste der Stufe" }),
    el("div", {}, auswahl([...basis, "sequence"], sequenzen, "keine"),
      el("div", { class: "erklaerung", text: erklaerung("heft", ["$stage", "sequence"]) }))));
  kasten.append(el("div", { class: "feld" }, el("label", { text: "Liederbuch (Note lang)" }),
    el("div", {}, feldText([...basis, "songbook"], { size: 60 }),
      el("div", { class: "erklaerung", text: erklaerung("heft", ["$stage", "songbook"]) + " – als Liste, z. B. [\"jingle_bells\"]" }))));
  return kasten;
}

function ablaeufe(ziel) {
  const a = W.stand.teile.ablaeufe;
  if (!a.sequences) a.sequences = {};
  const namen = Object.keys(a.sequences);
  if (!namen.includes(W.ablauf)) W.ablauf = namen[0] || null;
  ziel.append(el("h2", { text: "Abläufe" }));
  ziel.append(el("p", { class: "leise", text: "Schrittlisten: was der Baum Schritt für Schritt zeigt – Lichter an und aus, "
    + "warten, Töne, der Stern. Lichter heißen wie auf der Platine (D1 …) oder als Gruppe (RED, TIER_2, TOP …)." }));
  const wahl = el("select", { onchange: (ev) => { W.ablauf = ev.target.value; zeichne(); } });
  for (const n of namen) wahl.append(el("option", { value: n, text: n, selected: n === W.ablauf }));
  ziel.append(el("div", { class: "leiste" }, wahl,
    el("button", { class: "leicht", text: "+ neue Schrittliste", onclick: () => {
      const name = prompt("Name der Schrittliste (klein, ohne Leerzeichen):", "neu");
      if (name) { W.ablauf = name; aendere(["ablaeufe", "sequences", name], [{ op: "set_leds", leds: [] }]); }
    } }),
    W.ablauf ? el("button", { class: "leicht", text: "umbenennen", onclick: () => {
      const neu = prompt("Neuer Name:", W.ablauf);
      if (neu && neu !== W.ablauf) {
        const liste = a.sequences[W.ablauf];
        aendere(["ablaeufe", "sequences", neu], liste);
        aendere(["ablaeufe", "sequences", W.ablauf], undefined);
        W.ablauf = neu; zeichne();
      }
    } }) : null,
    W.ablauf ? el("button", { class: "leicht", text: "löschen", onclick: () => {
      if (confirm("Schrittliste " + W.ablauf + " löschen?")) aendere(["ablaeufe", "sequences", W.ablauf], undefined);
    } }) : null));
  if (!W.ablauf) return;
  const pfad = ["ablaeufe", "sequences", W.ablauf], liste = a.sequences[W.ablauf];
  const tabelle = el("div", { class: "bausteine", "data-pfad": pfad.join(".") });
  liste.forEach((o, i) => {
    const art = el("select", { onchange: (ev) => aendere(pfad, liste.map((x, j) => j === i ? { op: ev.target.value } : x)) });
    for (const [n, d] of Object.entries(W.auskunft.ops)) art.append(el("option", { value: n, text: n, title: d.description, selected: n === o.op }));
    const aendereFeld = (f) => (ev) => {
      const neu = liste.map((x, j) => j === i ? { ...x, [f]: ausText(ev.target.value) } : x);
      if (neu[i][f] === undefined) delete neu[i][f];
      aendere(pfad, neu);
    };
    const LANG = ["ops", "if_pressed", "tones", "notes"];   // geschachtelte Listen: ein breites Textfeld
    const felder = (W.auskunft.ops[o.op] || { fields: [] }).fields.map((f) => el("label", {
      title: erklaerung("ablaeufe", ["$op", f]) }, f + " ", LANG.includes(f)
        ? el("textarea", { class: "liste", onchange: aendereFeld(f) }, alsText(o[f]))
        : el("input", { value: alsText(o[f]), size: f === "leds" ? 22 : 7, onchange: aendereFeld(f) })));
    const schiebe = (d) => { const neu = [...liste]; const [x] = neu.splice(i, 1); neu.splice(i + d, 0, x); aendere(pfad, neu); };
    tabelle.append(el("div", { class: "baustein", "data-pfad": pfad.concat(i).join(".") }, el("strong", { text: (i + 1) + "." }),
      art, ...felder,
      el("button", { class: "leicht", text: "↑", disabled: i === 0, onclick: () => schiebe(-1) }),
      el("button", { class: "leicht", text: "↓", disabled: i === liste.length - 1, onclick: () => schiebe(1) }),
      el("button", { class: "leicht", text: "✕", onclick: () => aendere(pfad, liste.filter((_, j) => j !== i)) })));
  });
  tabelle.append(el("div", {}, el("button", { class: "leicht", text: "+ Anweisung",
    onclick: () => aendere(pfad, [...liste, { op: "wait", ms: 500 }]) })));
  ziel.append(tabelle);
  ziel.append(el("p", { class: "erklaerung", text: "Mehrere Lichter als Liste: [\"D1\", \"D2\"]. Fährt die Maus über eine "
    + "Anweisung oder ein Feld, steht dort, was es tut." }));
}

// --- Lieder ------------------------------------------------------------------------------------------------------

let klang = null;
function hoere(lied) {
  let toene;
  try { toene = rufe("lied_toene", lied); } catch (e) { melde(e.message); return; }
  if (klang) klang.close();
  klang = new AudioContext();
  let t = klang.currentTime + 0.05;
  for (const [von, bis, an, aus] of toene) {
    if (von && an) {
      const o = klang.createOscillator(), g = klang.createGain();
      o.type = "square"; g.gain.value = 0.04;
      o.frequency.setValueAtTime(von, t); o.frequency.linearRampToValueAtTime(bis, t + an / 1000);
      o.connect(g).connect(klang.destination); o.start(t); o.stop(t + an / 1000);
    }
    t += (an + aus) / 1000;
  }
}

function lieder(ziel) {
  const l = W.stand.teile.lieder;
  ziel.append(el("h2", { text: "Lieder" }));
  ziel.append(el("p", { class: "leise", text: "Die Liedbibliothek liegt auf jedem Baum. Welches Lied an welchem Tag "
    + "spielt, steht unter Tage. Anhören spielt das Lied so, wie der Baum es spielt – als einfachen Ton." }));
  const liste = el("table", {}, el("tr", {}, el("th", { text: "Name" }), el("th", { text: "Titel" }), el("th")));
  for (const [n, t] of Object.entries(W.auskunft.songs)) {
    liste.append(el("tr", {}, el("td", {}, el("code", { text: n })), el("td", { text: t }), el("td", {},
      el("button", { class: "leicht", text: "▶ anhören", onclick: () => hoere(JSON.parse(W.py.globals.get("_bib")).songs[n]) }))));
  }
  ziel.append(el("details", {}, el("summary", { text: "Liedbibliothek (" + Object.keys(W.auskunft.songs).length + " Lieder)" }), liste));
  ziel.append(el("h3", { text: "Eigene Lieder" }));
  ziel.append(el("p", { class: "leise", text: "Noten in ABC-Schreibweise, wie in vielen Liedersammlungen im Netz. "
    + "Für ein eigenes Lied steht ein, wer das Heft macht – die Werkstatt lädt nichts hoch, das Lied bleibt in der Baum-"
    + "Datei und auf dem eigenen Baum (eine Einschätzung, keine Rechtsberatung)." }));
  const eigene = (l.own_songs = l.own_songs || {});
  for (const [name, lied] of Object.entries(eigene)) {
    const p = (k) => ["lieder", "own_songs", name, k];
    const karte = el("div", { class: "karte", "data-pfad": "lieder.own_songs." + name }, el("h3", {}, el("code", { text: name })));
    for (const [k, beschr] of [["title", "Titel"], ["ms", "ms je Sechzehntel"], ["key", "Tonart"], ["unit", "Notenlänge (8 = Achtel)"],
      ["transpose", "Halbtöne höher/tiefer"], ["source", "Quelle"], ["rights", "Rechte"]]) {
      karte.append(el("div", { class: "feld" }, el("label", { text: beschr }), feldText(p(k), { size: 40 })));
    }
    karte.append(el("textarea", { "data-pfad": p("abc").join("."), onchange: (ev) => aendere(p("abc"), ev.target.value) },
      lied.abc || ""));
    karte.append(el("div", { class: "leiste" }, el("button", { text: "▶ anhören", onclick: () => hoere(eigene[name]) }),
      el("button", { class: "leicht", text: "löschen", onclick: () => aendere(["lieder", "own_songs", name], undefined) })));
    ziel.append(karte);
  }
  ziel.append(el("button", { class: "leicht", text: "+ eigenes Lied", onclick: () => {
    const name = prompt("Name des Lieds (klein, ohne Leerzeichen):", "unser_lied");
    if (name) aendere(["lieder", "own_songs", name], { title: name, ms: 150, key: "C", abc: "c d e f | g2 g2 |" });
  } }));
  ziel.append(el("h3", { text: "Tagesmarken und Signaltöne" }));
  ziel.append(el("div", { class: "feld" }, el("label", { text: "Tagesmarken" }), el("div", {},
    feldText(["lieder", "day_marks"], { size: 80 }), el("div", { class: "erklaerung", text: erklaerung("lieder", ["day_marks"]) }))));
  ziel.append(el("div", { class: "feld" }, el("label", { text: "Signaltöne" }), el("div", {},
    feldText(["lieder", "signals"], { size: 80 }), el("div", { class: "erklaerung", text: erklaerung("lieder", ["signals"]) }))));
}

// --- Codes und Prüfen --------------------------------------------------------------------------------------------

function codes(ziel) {
  const c = W.stand.teile.codes, offiziell = W.stand.art === "offiziell";
  ziel.append(el("h2", { text: "Codes" }));
  ziel.append(el("p", { class: "leise", text: offiziell
    ? "Die Codes eines offiziellen Hefts kommen aus seinem Inhalt (Türchen, Rätsel) – hier nur zur Ansicht."
    : "Je Tag ein Code, acht Schalter (1 = oben). Die Werkstatt würfelt gültige; ändern kannst du jeden, etwa wenn ein "
      + "Rätsel einen bestimmten Code ergeben soll. Der Bypass (Bestätigen 5 s) springt ans Ende." }));
  const f = (pfad, attr) => offiziell ? el("code", { text: alsText(holeWert(pfad)) }) : feldText(pfad, attr);
  ziel.append(el("div", { class: "feld" }, el("label", { text: "Bypass" }), f(["codes", "bypass"], { size: 10 })));
  ziel.append(el("div", { class: "feld" }, el("label", { text: "Salz" }), f(["codes", "salt"], { size: 10 })));
  if (!offiziell) ziel.append(el("button", { text: "Codes würfeln", onclick: () => {
    if (!confirm("Alle Codes und den Bypass neu würfeln?")) return;
    try { W.stand.fehler = rufe("wuerfle_codes"); W.stand.teile = rufe("stand").teile; } catch (e) { melde(e.message); }
    zeichne();
  } }));
  const t = el("table", { class: "codes" }, el("tr", {}, el("th", { text: "Schritt" }), el("th", { text: "Code" })));
  (c.steps || []).forEach((s, i) => t.append(el("tr", {}, el("td", { text: s.id }),
    el("td", {}, f(["codes", "steps", i, "code"], { size: 10, maxlength: 8 })))));
  ziel.append(t);
  if (offiziell) return;
  const liste = ["Bypass (Bestätigen 5 s): " + c.bypass].concat((c.steps || []).map((s) => "Tag " + s.id + ": " + s.code)).join("\n");
  const kasten = el("textarea", { id: "codeliste", class: "codeliste", readonly: true, rows: 14, text: liste });
  ziel.append(el("h3", { text: "Zum Abschreiben" }), kasten, el("p", {}, el("button", { class: "leicht", text: "Kopieren",
    onclick: async () => { kasten.select(); try { await navigator.clipboard.writeText(liste); } catch { document.execCommand("copy"); } } })));
}

function pruefen(ziel) {
  ziel.append(el("h2", { text: "Prüfen" }));
  const fehler = W.stand.fehler;
  if (!fehler.length) {
    ziel.append(el("p", { text: "Keine Fehler: So kann das Heft auf den Baum." }));
    try {
      const dateien = rufe("erzeugt");
      const groesse = Object.values(dateien).reduce((s, t) => s + new TextEncoder().encode(t).length, 0);
      ziel.append(el("p", { class: "leise", text: "Auf dem Baum: " + Object.keys(dateien).join(", ") + " – zusammen "
        + groesse.toLocaleString("de-DE") + " Byte" + (W.stand.art === "baum" ? ", höchstens "
        + W.auskunft.limit_bytes.toLocaleString("de-DE") : "") + "." }));
    } catch (e) { ziel.append(el("p", { text: e.message })); }
    return;
  }
  ziel.append(el("p", { text: fehler.length + (fehler.length === 1 ? " Fehler" : " Fehler") + " – der Erzeuger der Firmware sagt:" }));
  ziel.append(el("ul", { class: "fehlerliste" }, fehler.map((f) => el("li", {}, el("code", { text: f.file + " " + f.where }), " ", f.text))));
}

// --- Auf den Baum (Aufspielen über USB, baum.js) ------------------------------------------------------------------

const B = { leitung: null, lage: null, lauf: null, fertig: null, meldung: null, ersetzen: false, entfernen: null };

function musterName(ordner) { return "E" + parseInt(ordner.slice(-2), 10); }

function kb(bytes) { return Math.ceil(bytes / 1024).toLocaleString("de-DE") + " kB"; }

function aufDenBaum(ziel) {
  ziel.append(el("h2", { text: "Auf den Baum" }));
  if (W.stand.art !== "baum") {
    ziel.append(el("p", { text: "Offizielle Hefte kommen nur mit der Firmware auf den Baum, nie aus der Werkstatt." }));
    return;
  }
  if (!BaumLeitung.moeglich()) {
    ziel.append(el("div", { class: "karte", id: "kein-serial" }, el("p", { text: "Aufspielen geht mit Chrome oder Edge "
      + "unter Windows und Linux, in Firefox ab Fassung 151 nach einer Zusatzbestätigung. Dieser Browser kann es nicht – "
      + "bearbeiten und speichern geht trotzdem, aufspielen dann in einem der anderen." })));
    return;
  }
  const muster = W.stand.auf_dem_baum;
  const m = W.auskunft.muster.find((x) => x.pattern === parseInt(muster.slice(-2), 10));
  if (W.stand.fehler.length) {
    ziel.append(el("p", { text: "Das Heft hat noch " + W.stand.fehler.length + " Fehler (Reiter Prüfen) – so geht es "
      + "nicht auf den Baum." }));
    return;
  }
  ziel.append(el("ol", {},
    el("li", { text: "Den Baum aus dem Hügel nehmen. Die Buchse im Hügel gibt ihm nur Strom; mit dem Rechner spricht er "
      + "über die kleine Buchse unten am Stamm." }),
    el("li", { text: "Die Note halten und das Kabel vom Rechner dort einstecken. Der Baum bleibt dunkel – sein Programm "
      + "läuft nicht, so nimmt er Dateien an." }),
    el("li", { text: "„Mit dem Baum verbinden“ klicken und den Baum auswählen. Der Browser fragt jedes Mal." })));
  const knopf = B.leitung
    ? el("button", { id: "trennen", class: "leicht", text: "Trennen", disabled: !!B.lauf, onclick: trennen })
    : el("button", { id: "verbinden", text: "Mit dem Baum verbinden", onclick: verbinden });
  ziel.append(el("p", {}, knopf));
  if (B.meldung) ziel.append(el("div", { class: "karte warnung", id: "baum-meldung" }, B.meldung.map((t) => el("p", {}, t))));
  const l = B.lage;
  if (l && B.leitung) {
    ziel.append(el("p", { id: "baum-stand", text: "Auf dem Baum: " + (l.basis ? "Firmware " + l.basis.version
      + ", liest Hefte bis Format " + l.basis.format + ", " : "") + "frei " + kb(l.frei) + "." }));
    if (l.eigene.length) {
      const t = el("table", { id: "baum-hefte" }, el("tr", {}, el("th", { text: "Muster" }), el("th", { text: "Heft" }),
        el("th", { text: "Größe" }), el("th", {})));
      for (const h of l.eigene) {
        const sicher = B.entfernen === h.ordner;
        t.append(el("tr", {}, el("td", { text: musterName(h.ordner) }), el("td", { text: h.titel || "(kein lesbares Heft)" }),
          el("td", { text: kb(h.bytes) }), el("td", {}, el("button", { class: "leicht", "data-ordner": h.ordner,
            disabled: !!B.lauf, text: sicher ? "Wirklich entfernen" : "entfernen", onclick: () => entfernen(h.ordner) }))));
      }
      ziel.append(el("h3", { text: "Eigene Hefte auf dem Baum" }), t);
    } else {
      ziel.append(el("p", { class: "leise", text: "Noch kein eigenes Heft auf dem Baum." }));
    }
    if (l.fehler) {
      ziel.append(el("div", { class: "karte warnung", id: "baum-fehler" }, el("p", { text: l.fehler })));
    } else if (!B.lauf && !B.fertig) {
      if (l.ersetzt && !B.ersetzen) {
        ziel.append(el("div", { class: "karte", id: "baum-frage" },
          el("p", { text: "Unter dem Muster " + musterName(muster) + " liegt schon „" + (l.ersetzt.titel || "ein Heft")
            + "“. Ersetzen? Das Heft beginnt dann am Anfang." }),
          el("p", {}, el("button", { id: "ersetzen", text: "Ersetzen und aufspielen", onclick: () => { B.ersetzen = true; aufspielen(); } }))));
      } else {
        ziel.append(el("p", {}, el("button", { id: "aufspielen", text: "Aufspielen nach " + muster
          + " (Muster " + musterName(muster) + ")", onclick: aufspielen })));
      }
    }
  }
  if (B.lauf) {
    ziel.append(el("p", {}, el("progress", { id: "fortschritt", max: B.lauf.n, value: B.lauf.i })),
      el("p", { class: "leise", text: B.lauf.was }));
  }
  if (B.fertig) {
    ziel.append(el("div", { class: "karte", id: "baum-fertig" },
      el("p", {}, el("strong", { text: "Fertig: " }), "„" + B.fertig.titel + "“ liegt auf dem Baum unter " + muster
        + " und ist nachgelesen."),
      el("p", { text: "Stecker ziehen. Mit beiden Knöpfen einstecken, an den Schaltern " + m.select_code
        + " einstellen, Bestätigen. War das Heft schon gewählt, genügt neu einstecken." })));
  }
}

function baumFehler(e) {
  if (e.art === "abgelehnt") return null;
  if (e.art === "oeffnen") {
    return ["Der Baum ließ sich nicht öffnen (" + e.message + ").",
      /Linux/.test(navigator.userAgent) && !/Android/.test(navigator.userAgent)
        ? "Unter Linux braucht dein Benutzer das Recht auf serielle Geräte: im Terminal sudo usermod -aG dialout $USER, "
          + "dann ab- und wieder anmelden."
        : "Vielleicht hält ein anderes Programm den Baum (etwa Thonny) – es schließen und noch einmal verbinden."];
  }
  if (e.art === "abgebrochen" || e.art === "stumm") {
    return [e.message + (B.lauf ? " Auf dem Baum fehlt jetzt nur dieses Heft – die anderen laufen wie vorher." : ""),
      "Den Baum wieder mit gehaltener Note einstecken, verbinden und noch einmal aufspielen."];
  }
  return [e.message];
}

async function baumLesen() {
  const { aus, fehler } = await B.leitung.ausfuehren(rufe("baum_fragen"));
  if (fehler) throw new BaumFehler("baum", "Der Baum meldet: " + fehler.split("\n").pop());
  B.lage = rufe("baum_lage", aus);
}

async function verbinden() {
  B.meldung = null; B.fertig = null; B.ersetzen = false; B.entfernen = null;
  const leitung = new BaumLeitung();
  try {
    await leitung.verbinden();
    B.leitung = leitung;
    await baumLesen();
  } catch (e) {
    B.meldung = baumFehler(e);
    await leitung.trennen();
    B.leitung = null; B.lage = null;
  }
  zeichne();
}

async function trennen() {
  if (B.leitung) await B.leitung.trennen();
  B.leitung = null; B.lage = null; B.fertig = null; B.meldung = null;
  zeichne();
}

async function befehle(schritte) {
  B.lauf = { i: 0, n: schritte.length, was: "" };
  for (const s of schritte) {
    B.lauf.was = s.was; zeichne();
    const { aus, fehler } = await B.leitung.ausfuehren(s.code);
    if (fehler) throw new BaumFehler("baum", s.was + ": der Baum meldet " + fehler.split("\n").pop());
    if (aus !== s.soll) throw new BaumFehler("baum", s.was + ": der Baum meldet „" + aus + "“ statt „" + s.soll + "“");
    B.lauf.i += 1;
  }
}

async function aufspielen() {
  B.meldung = null; B.fertig = null;
  try {
    await befehle(rufe("aufspielen_schritte"));
    B.lauf = null;
    await baumLesen();
    B.fertig = { titel: W.stand.teile.heft.title };
  } catch (e) {
    B.meldung = baumFehler(e);
    if (e.art === "abgebrochen") { await B.leitung.trennen(); B.leitung = null; B.lage = null; }
  }
  B.lauf = null; B.ersetzen = false;
  zeichne();
}

async function entfernen(ordner) {
  if (B.entfernen !== ordner) { B.entfernen = ordner; zeichne(); return; }
  B.meldung = null; B.fertig = null; B.entfernen = null;
  try {
    await befehle(rufe("entfernen_schritte", ordner));
    B.lauf = null;
    await baumLesen();
  } catch (e) {
    B.meldung = baumFehler(e);
    if (e.art === "abgebrochen") { await B.leitung.trennen(); B.leitung = null; B.lage = null; }
  }
  B.lauf = null;
  zeichne();
}

// --- Öffnen und Speichern ----------------------------------------------------------------------------------------

function neu() {
  try {
    W.stand = rufe("oeffnen_baum", W.vorlage);
    rufe("setze", ["codes", "salt"], rufe("neues_salz"));
    rufe("wuerfle_codes");
    W.stand = rufe("stand");
  } catch (e) { melde(e.message); return; }
  W.handle = null; W.dateiname = "mein_baum.baum.json"; W.stufe = 1;
  zeichne();
}

async function oeffnen() {
  if (window.showOpenFilePicker) {
    try {
      const [handle] = await showOpenFilePicker({ types: [{ description: "Baum-Datei", accept: { "application/json": [".json"] } }] });
      const text = await (await handle.getFile()).text();
      W.stand = rufe("oeffnen_baum", text);
      W.handle = handle; W.dateiname = handle.name; W.stufe = 1; zeichne();
    } catch (e) { if (e.name !== "AbortError") melde(e.message); }
    return;
  }
  $("#dateiwahl").click();
}

async function speichern() {
  let erg;
  try { erg = rufe("speichern"); } catch (e) { melde(e.message); return; }
  if (erg.art === "offiziell") {
    const r = await fetch("api/heft?ordner=" + encodeURIComponent(erg.ordner), { method: "PUT",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dateien: erg.dateien }) });
    const antwort = await r.json();
    melde(antwort.fehler ? "Nicht gespeichert: " + antwort.fehler
      : antwort.geschrieben.length ? "Gespeichert: " + antwort.geschrieben.join(", ") : "Nichts geändert.");
    return;
  }
  if (W.handle && W.handle.createWritable) {
    const w = await W.handle.createWritable(); await w.write(erg.text); await w.close(); return;
  }
  if (window.showSaveFilePicker) {
    try {
      W.handle = await showSaveFilePicker({ suggestedName: W.dateiname || "mein_baum.baum.json",
        types: [{ description: "Baum-Datei", accept: { "application/json": [".json"] } }] });
      W.dateiname = W.handle.name;
      const w = await W.handle.createWritable(); await w.write(erg.text); await w.close(); zeichne(); return;
    } catch (e) { if (e.name === "AbortError") return; }
  }
  const a = el("a", { href: URL.createObjectURL(new Blob([erg.text], { type: "application/json" })),
    download: W.dateiname || "mein_baum.baum.json" });
  a.click();
}

async function offiziellOeffnen(ordner) {
  const d = await (await fetch("api/heft?ordner=" + encodeURIComponent(ordner))).json();
  W.stand = rufe("oeffnen_offiziell", d.ordner, d.familie, d.dateien["heft.json"], d.dateien["ablaeufe.json"],
    d.dateien["lieder.json"], d.codes);
  W.stufe = 1; zeichne();
  return d;
}

// --- Selbstprüfung (?test=1): öffnen, unverändert speichern, übersetzen – für den Test im Browser ------------------

async function selbsttest() {
  const ergebnis = { vorlage: null, hefte: {}, ladezeit_ms: Math.round(W.bereit - W.start), bytes: 0 };
  W.stand = rufe("oeffnen_baum", W.vorlage);
  ergebnis.vorlage = { gleich: rufe("speichern").text === W.vorlage, fehler: W.stand.fehler.length,
    erzeugt: Object.keys(rufe("erzeugt")).length };
  if (W.modus === "alle") {
    for (const h of (await (await fetch("api/hefte")).json()).hefte) {
      const d = await offiziellOeffnen(h.ordner);
      const gespeichert = rufe("speichern").dateien;
      const gleich = Object.entries(gespeichert).every(([n, t]) => d.dateien[n] === t);
      const soll = await (await fetch("api/erzeugt?ordner=" + h.ordner)).json();
      ergebnis.hefte[h.ordner] = { gleich, fehler: W.stand.fehler.length,
        erzeugt_gleich: JSON.stringify(rufe("erzeugt")) === JSON.stringify(soll) };
    }
  }
  for (const r of performance.getEntriesByType("resource")) ergebnis.bytes += r.transferSize || r.encodedBodySize || 0;
  const pre = $("#testergebnis");
  pre.textContent = JSON.stringify(ergebnis);
  pre.hidden = false;
}

// --- Start -------------------------------------------------------------------------------------------------------

async function start() {
  const p = new URLSearchParams(location.search);
  if (p.get("thema")) document.documentElement.dataset.thema = p.get("thema");
  $("#thema").addEventListener("click", () => {
    const dunkel = document.documentElement.dataset.thema === "dunkel"
      || (!document.documentElement.dataset.thema && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.thema = dunkel ? "hell" : "dunkel";
  });
  try {
    const r = await fetch("api/hefte");
    if (r.ok) {
      W.modus = "alle";
      const wahl = $("#offizielle");
      for (const h of (await r.json()).hefte) wahl.append(el("option", { value: h.ordner, text: h.titel }));
      wahl.hidden = false;
      wahl.addEventListener("change", async () => { if (wahl.value) await offiziellOeffnen(wahl.value); wahl.value = ""; });
    }
  } catch { /* öffentliche Fassung: kein Programm dahinter */ }
  $("#modus").textContent = W.modus === "alle" ? "alle Hefte · lokal" : "eigene Hefte";
  try {
    await pythonLaden();
  } catch (e) {
    ladestand("Die Werkstatt konnte nicht laden: " + e.message);
    return;
  }
  W.bereit = performance.now();
  $("#laden").hidden = true;
  $("#werkstatt").hidden = false;
  for (const id of ["neu", "oeffnen", "speichern"]) $("#" + id).disabled = false;
  $("#neu").addEventListener("click", neu);
  $("#oeffnen").addEventListener("click", oeffnen);
  $("#speichern").addEventListener("click", speichern);
  $("#dateiwahl").addEventListener("change", async (ev) => {
    const datei = ev.target.files[0];
    if (!datei) return;
    try { W.stand = rufe("oeffnen_baum", await datei.text()); W.handle = null; W.dateiname = datei.name; W.stufe = 1; zeichne(); }
    catch (e) { melde(e.message); }
    ev.target.value = "";
  });
  for (const b of document.querySelectorAll("#reiter button")) b.addEventListener("click", () => { W.teil = b.dataset.teil; zeichne(); });
  if (p.get("test")) { await selbsttest(); }
  neu();
  if (p.get("teil")) { W.teil = p.get("teil"); }
  if (p.get("heft") && W.modus === "alle") await offiziellOeffnen(p.get("heft"));
  zeichne();
}

start();
