"""Der Erzeuger: prüft ein Heft und übersetzt es für den Baum (Konzept docs/concepts/erledigt/zustandsautomat.md, Teil 3
„Was der Baum lädt“, Teil 4 „Auf dem Rechner: der Erzeuger“, Schnittstellen S2 bis S6).

Ein eigenständiges Stück Python (S4): nur die Standardbibliothek, kein Zugriff auf Dateien. Was er braucht, bekommt
er als Daten, und er gibt Daten zurück – die Dateien für den Baum oder eine Liste von Fehlern, jeder mit Datei, Stelle
und Text. Lesen und Schreiben besorgt, wer ihn aufruft: firmware/zusammenstellen.py für die offiziellen Hefte, die
Baum-Werkstatt im Browser (Pyodide) für ein eigenes. Dieselbe Eingabe gibt Byte für Byte dieselbe Ausgabe.

    erzeuge(heft, ablaeufe, lieder, codes, lichter=…, bibliothek=…, register=…, eigen=False)
        → ({Dateiname: Text}, [Fehler])          die Dateien eines Hefts auf dem Baum: heft.json, ablaeufe.json,
                                                  lieder.json, codes.json
    bibliothek_fuer_den_baum(bibliothek, lichter) → (Text, [Fehler])   liedbibliothek.json bei der Basis
    auskunft(lichter, bibliothek)                → was es gibt: Lichter, Gruppen, Bausteine, Anweisungen, Lieder (S5)
    schema()                                     → die JSON-Schemas der Quelldateien, jeder Schlüssel mit Erklärung

Die Schlüssel sind englisch (Konzept, „Wie die Dateien geschrieben sind“), der Code deutsch wie die Firmware.
"""
import hashlib
import json
import re

FORMAT = 1                      # das Format der Hefte, das diese Basis liest (S3)
GRENZE_EIGEN = 32768            # Byte: so groß dürfen die vier Dateien eines eigenen Hefts auf dem Baum zusammen sein
                                # (S4; Nutzer 2026-11-17: 32 KiB, am Baum in Schritt 6 nachmessen – das größte offizielle,
                                # Heft 1, hat 16 349 Byte)

# --- Grenzen des Summers und des Spielers ---------------------------------------------------------------------
LIED_HZ = (500, 2100)           # Lieder: C5 … C7 mit Luft (D-6)
TON_HZ = (400, 3200)            # Einzeltöne in Schrittlisten
SIGNAL_HZ = (200, 4000)         # Signaltöne: dürfen tiefer brummen (der Anlasser von Eingeschneit, 300 Hz)
TON_MS = 3000                   # kein einzelner Ton länger (FW-4: der Summer nie dauerhaft an)
FOLGE_MS = 60000                # keine Tonfolge länger
LEGATO = 0.9                    # jeder Ton klingt so viel seiner Dauer, der Rest ist still

# --- Das Byte-Format des Spielers (firmware/basis/spieler.py) -------------------------------------------------
ZEIGE, HELL, STERN, BLENDE, TON, PAUSE, FERTIG, TASTER, SONST, DIP, WUNSCH, SPIELE, STERN_FEIN, FLACKERN = range(14)
WEISS, GOLD, AUS, V_GRUND = 0xFFFF, 0xFFFE, 0xFFFD, 255
LEVEL_GRUND = 0xFFFF            # STERN_FEIN: Grundhelligkeit des Sterns


class Fehler(Exception):
    def __init__(self, stelle, text):
        super().__init__("%s: %s" % (stelle, text))
        self.stelle, self.text = stelle, text


# --- Töne -------------------------------------------------------------------------------------------------------

_HALBTON = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_NAMEN = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B")


def _midi(note):
    halb = _HALBTON[note[0]]
    rest = note[1:]
    if rest[:1] == "#":
        halb, rest = halb + 1, rest[1:]
    elif rest[:1] == "b":
        halb, rest = halb - 1, rest[1:]
    return 12 * (int(rest) + 1) + halb


def hz(note):
    """'A4' → 440.0, 'F#5', 'Bb6'; Zahlen werden durchgereicht, 'R' → 0 (wie musik/basis/liederbuch.py)."""
    if not isinstance(note, str):
        return note
    if note == "R":
        return 0
    return 440.0 * 2 ** ((_midi(note) - 69) / 12)


def _ganz_hz(note, stelle):
    try:
        return round(hz(note))
    except (KeyError, ValueError, IndexError, TypeError):
        raise Fehler(stelle, "Note %r gibt es nicht (z. B. \"C6\", \"F#5\", \"Bb6\", \"R\" für eine Pause)" % (note,))


_QUINTEN = "FCGDAEB"
_DUR = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5}
_MOLL = {"Am": 0, "Em": 1, "Bm": 2, "F#m": 3, "Dm": -1, "Gm": -2, "Cm": -3, "Fm": -4}


def _vorzeichen(tonart):
    n = {**_DUR, **_MOLL}[tonart]
    return {t: 1 for t in _QUINTEN[:n]} if n >= 0 else {t: -1 for t in _QUINTEN[::-1][:-n]}


def abc_noten(noten, tonart="C", einheit=8, schritte=0, stelle="abc"):
    """ABC → [(Note, Sechzehntel)] wie abc() in musik/basis/liederbuch.py (dort steht, was verstanden wird)."""
    if tonart not in _DUR and tonart not in _MOLL:
        raise Fehler(stelle, "Tonart %r unbekannt" % (tonart,))
    vorz = _vorzeichen(tonart)
    toene, takt, gebunden = [], {}, False
    for m in re.finditer(r"(\|+|:|\[|\]|\(|\))|([\^_=]*)([A-Ga-gz])([',]*)(\d*)(/*)(\d*)(>?)(-?)", noten):
        if m.group(1):
            if "|" in m.group(1):
                takt = {}
            continue
        acc, note, okt, zaehler, striche, nenner, punkt, bogen = m.groups()[1:]
        dauer = int(zaehler or 1) / (int(nenner) if nenner else 2 ** len(striche))
        dauer *= 16 / einheit
        if punkt:
            dauer *= 1.5
        if toene and toene[-1][2]:
            dauer /= 2
        if note == "z":
            name = "R"
        else:
            stamm = note.upper()
            if acc:
                takt[stamm] = {"^": 1, "^^": 2, "_": -1, "__": -2, "=": 0}[acc]
            halb = takt.get(stamm, vorz.get(stamm, 0))
            oktave = 4 + note.islower() + okt.count("'") - okt.count(",")
            midi = 12 * (oktave + 1) + _HALBTON[stamm] + halb + schritte
            name = "%s%d" % (_NAMEN[midi % 12], midi // 12 - 1)
        if gebunden and toene and toene[-1][0] == name:
            toene[-1][1] += dauer
        else:
            toene.append([name, dauer, bool(punkt)])
        gebunden = bool(bogen)
    aus = []
    for name, dauer, _ in toene:
        if dauer != int(dauer):
            raise Fehler(stelle, "Dauer %s ist kein Vielfaches eines Sechzehntels" % dauer)
        aus.append((name, int(dauer)))
    return aus


def lied_noten(lied, stelle):
    """[(Note, Sechzehntel)] eines Lieds der Bibliothek oder eines eigenen Lieds (abc oder notes)."""
    if "abc" in lied:
        return abc_noten(lied["abc"], lied.get("key", "C"), lied.get("unit", 8), lied.get("transpose", 0), stelle)
    if "notes" in lied:
        return [(n["note"], n["len"]) for n in lied["notes"]]
    raise Fehler(stelle, "ein Lied braucht abc oder notes")


def lied_toene(noten, ms, stelle, bereich=LIED_HZ, tempo=1, anzahl=None, schluss=None):
    """[(von_hz, bis_hz, ms_an, ms_aus)] wie bis 0.6.1 musik/basis/export_firmware.py; tempo und schluss wie melodie() von
    Heft 2."""
    noten = list(noten if anzahl is None else noten[:anzahl])
    if schluss:
        noten[-1] = (noten[-1][0], schluss)
    aus = []
    for note, einheiten in noten:
        dauer = einheiten * ms if tempo == 1 else round(einheiten * ms / tempo)
        f = _ganz_hz(note, stelle)
        if not f:
            aus.append((0, 0, 0, dauer))
            continue
        if not bereich[0] <= f <= bereich[1]:
            raise Fehler(stelle, "%s = %d Hz liegt außerhalb dessen, was der Summer kann (%d … %d Hz, D-6) – "
                                 "transpose ändern" % (note, f, bereich[0], bereich[1]))
        an = round(dauer * LEGATO)
        aus.append((f, f, an, dauer - an))
    return aus


def ton_folge(toene, stelle, bereich=TON_HZ):
    """Anweisung tones/tone und Signale: je Ton {note, ms[, gap]} oder {from_hz, to_hz, ms} → Tupel des Spielers.
    Ein Ton mit note klingt LEGATO seiner Dauer, ohne gap; mit gap genau ms und danach gap ms Pause."""
    aus = []
    for i, t in enumerate(toene):
        wo = "%s, Ton %d" % (stelle, i + 1)
        if not isinstance(t, dict):
            raise Fehler(wo, "ein Ton ist ein Objekt mit note und ms oder from_hz, to_hz und ms")
        ms = t.get("ms")
        if not isinstance(ms, int) or isinstance(ms, bool) or ms < 0:
            raise Fehler(wo, "ms fehlt – jeder Ton braucht eine Dauer (FW-4)")
        if "from_hz" in t:
            a, b = t["from_hz"], t.get("to_hz")
            for f in (a, b):
                if not isinstance(f, int) or not bereich[0] <= f <= bereich[1]:
                    raise Fehler(wo, "Frequenz %r außerhalb %d … %d Hz" % (f, bereich[0], bereich[1]))
            aus.append((a, b, ms, 0))
            continue
        f = _ganz_hz(t.get("note"), wo)
        if f and not bereich[0] <= f <= bereich[1]:
            raise Fehler(wo, "%s = %d Hz außerhalb %d … %d Hz" % (t.get("note"), f, bereich[0], bereich[1]))
        if "gap" in t:
            aus.append((f, f, ms, t["gap"]) if f else (0, 0, 0, ms + t["gap"]))
        elif not f:
            aus.append((0, 0, 0, ms))
        else:
            an = round(ms * LEGATO)
            aus.append((f, f, an, ms - an))
    for von, _, an, _ in aus:
        if von and not an:
            raise Fehler(stelle, "Ton ohne Dauer (FW-4)")
        if an > TON_MS:
            raise Fehler(stelle, "ein Ton von %d ms – höchstens %d (FW-4)" % (an, TON_MS))
    if sum(an + aus_ for _, _, an, aus_ in aus) > FOLGE_MS:
        raise Fehler(stelle, "Tonfolge länger als %d ms" % FOLGE_MS)
    return aus


# --- Lichter und Gruppen ---------------------------------------------------------------------------------------

FARBE = {"red": "RED", "yellow": "YELLOW", "yellow/gold": "YELLOW", "green": "GREEN", "blue": "BLUE", "white": "WHITE",
         "warm white": "WHITE"}
GROESSE = {"1.8mm": "SIZE_1_8MM", "3mm": "SIZE_3MM", "5mm": "SIZE_5MM"}
GRUPPEN = ("RED", "YELLOW", "GREEN", "BLUE", "WHITE", "SIZE_1_8MM", "SIZE_3MM", "SIZE_5MM", "TOP", "TIER_1", "TIER_2",
           "TIER_3", "TIER_4", "LEFT", "RIGHT", "GARLAND_LOW", "GARLAND_HIGH", "HEART", "ALL", "AWAKE", "NEW")


class Lichter:
    """Die Lichter des Baums aus der Beschreibung, die das Zusammenstellen aus firmware/board.py zieht:
    {"leds": [{"name", "channel", "color", "size", "x", "y", "where"}], "channels": 24, "progress": [Kanal oder None]}.
    Eine Lichterkette (mehrere LEDs an einem Kanal) zählt als ein Licht: GARLAND_LOW, GARLAND_HIGH."""

    def __init__(self, daten):
        self.daten = daten
        self.leds = {d["name"]: d for d in daten["leds"]}
        self.kanaele = daten["channels"]
        je_kanal = {}
        for d in daten["leds"]:
            je_kanal.setdefault(d["channel"], []).append(d)
        self.je_kanal = je_kanal
        ketten = sorted((k for k, v in je_kanal.items() if len(v) > 1), key=lambda k: self._hoehe(k))
        self.ketten = {"GARLAND_LOW": ketten[0], "GARLAND_HIGH": ketten[1]} if len(ketten) == 2 else {}
        self.gruppen = self._gruppen()

    def _hoehe(self, k):
        v = self.je_kanal[k]
        return sum(d["y"] for d in v) / len(v), k

    def _seite(self, k):
        v = self.je_kanal[k]
        return sum(d["x"] for d in v) / len(v)

    def _gruppen(self):
        g = {n: set() for n in GRUPPEN if n not in ("AWAKE", "NEW")}
        for k, v in self.je_kanal.items():
            d = v[0]
            g[FARBE[d["color"]]].add(k)
            g[GROESSE[d["size"]]].add(k)
            wo = d["where"]
            if wo.startswith("Etage "):
                g["TIER_%s" % wo[6]].add(k)
            else:
                g["TOP"].add(k)
            seite = self._seite(k)
            if seite < 0:
                g["LEFT"].add(k)
            elif seite > 0:
                g["RIGHT"].add(k)
            g["ALL"].add(k)
        for name, k in self.ketten.items():
            g[name].add(k)
        g["HEART"].add(self.leds["D22"]["channel"])
        return {n: sorted(v) for n, v in g.items()}

    def kanal(self, name, stelle):
        """Ein Licht beim Namen der Platine (\"D22\") oder eine Lichterkette → Kanal."""
        if name in self.ketten:
            return self.ketten[name]
        if name in self.leds:
            return self.leds[name]["channel"]
        raise Fehler(stelle, "Licht %r gibt es nicht (Namen wie auf der Platine, \"D1\" … \"D30\", oder "
                             "GARLAND_LOW, GARLAND_HIGH)" % (name,))

    def name(self, kanal):
        """Kanal → Name: eine Lichterkette heißt GARLAND_LOW/HIGH, sonst der Name ihrer LED."""
        for n, k in self.ketten.items():
            if k == kanal:
                return n
        return self.je_kanal[kanal][0]["name"]

    def menge(self, namen, stelle, within=None, stand=None):
        """Namen und Gruppen → sortierte Liste der Kanäle. AWAKE und NEW setzt erst der Baum ein (stand)."""
        if not isinstance(namen, list):
            raise Fehler(stelle, "leds ist eine Liste von Lichtern und Gruppen")
        aus = set()
        for n in namen:
            if n in self.gruppen:
                aus |= set(self.gruppen[n])
            elif n in ("AWAKE", "NEW"):
                if stand is None:
                    raise Fehler(stelle, "%s hängt vom Stand ab und geht hier nicht" % n)
                aus |= set(stand[n])
            else:
                aus.add(self.kanal(n, stelle))
        if within is not None:
            aus &= set(self.menge([within], stelle, stand=stand))
        return sorted(aus)


def wort(kanaele):
    w = 0
    for k in kanaele:
        w |= 1 << k
    return w


# --- Schrittlisten → Spielerformat ----------------------------------------------------------------------------

def _u16(x, stelle):
    if isinstance(x, bool) or not isinstance(x, int) or not 0 <= x <= 0xFFFF:
        raise Fehler(stelle, "%r passt nicht (ganze Zahl 0 … 65535)" % (x,))
    return x.to_bytes(2, "big")


def _hue(x, stelle, fein=False):
    if x == "gold":
        return GOLD
    if x == "white":
        return WEISS
    if x == "off":
        return AUS
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not 0 <= x < 360:
        raise Fehler(stelle, "Farbton %r – 0 … 359, \"gold\", \"white\" oder \"off\"" % (x,))
    if fein:
        return int(round(x * 100)) % 36000
    if x != int(x):
        raise Fehler(stelle, "Farbton %r – ganze Zahl" % (x,))
    return int(x)


OPS = {
    "set_leds": "genau diese Lichter an, alle anderen aus",
    "leds_on": "diese Lichter dazu an",
    "leds_off": "diese Lichter aus",
    "brightness": "alle Lichter gemeinsam heller oder dunkler, 1.0 = Grundhelligkeit",
    "star": "der Stern in diesem Farbton, gold, white oder off; level die Helligkeit 0 … 1, ohne Angabe die Grundhelligkeit des Sterns",
    "star_fade": "der Stern blendet weich von einem Farbton zum anderen",
    "tone": "ein Ton mit Dauer; er klingt, während die nächsten Anweisungen laufen",
    "tones": "eine Tonfolge; läuft wie tone",
    "sweep": "ein gleitender Ton",
    "signal": "ein Signalton; die Schrittliste wartet, bis er aus ist – mit background läuft sie gleich weiter",
    "wait": "warten",
    "wait_tone": "warten, bis der Ton aus ist",
    "wait_button": "bis zu so lange auf Bestätigen warten, dabei blinken Lichter; if_pressed nur, wenn gedrückt",
    "show_switches": "die acht DIP-Schalter auf acht Lichtern zeigen",
    "request": "das Wunschkonzert: so viele Schalter an, diese Stufe in ihrer Fassung für die Vorstellung",
    "flicker": "Lichter gehen zufällig an und aus – die einzige Anweisung, die würfelt",
    "run_sequence": "eine andere Schrittliste einfügen",
    "repeat": "Kurzform: die Anweisungen in ops so oft hintereinander",
    "blink": "Kurzform: diese Lichter blinken",
    "chase": "Kurzform: Lauflicht, ein Licht nach dem anderen",
    "morse": "Kurzform: diese Lichter morsen den Text",
    "song_with_leds": "die ersten Töne eines Lieds, auf Wunsch wechseln dazu die Lichter; mit background läuft die Schrittliste neben dem Lied weiter",
}
_OP_FELDER = {
    "set_leds": {"leds", "within"}, "leds_on": {"leds", "within"}, "leds_off": {"leds", "within"},
    "brightness": {"factor"}, "star": {"hue", "level"}, "star_fade": {"from", "to", "ms"},
    "tone": {"note", "ms", "gap"}, "tones": {"tones"}, "sweep": {"from_hz", "to_hz", "ms"},
    "signal": {"signal", "background"},
    "wait": {"ms"}, "wait_tone": set(), "wait_button": {"timeout_ms", "blink", "alt_blink", "period_ms", "if_pressed"},
    "show_switches": {"ms", "live", "leds"}, "request": {"timeout_ms", "settle_ms", "default", "blink", "alt_blink",
                                                         "period_ms"},
    "flicker": {"leds", "ms", "step_ms", "density", "tick", "end"}, "run_sequence": {"sequence", "show"},
    "repeat": {"times", "ops"}, "blink": {"leds", "times", "on_ms", "off_ms"}, "chase": {"leds", "ms", "notes"},
    "morse": {"leds", "text"}, "song_with_leds": {"song", "count", "tempo", "leds", "end", "background"},
}
MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
    "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
}
MORSE_MS = 120
TICK = ({"from_hz": 2093, "to_hz": 2093, "ms": 12},)


class Uebersetzer:
    """Übersetzt Schrittlisten in das Byte-Format des Spielers. Die Tonfolgen kommen in eine Tabelle (TOENE), eine
    Liste nennt sie mit ihrer Nummer."""

    def __init__(self, lichter, lieder, signale, sequenzen, stufen_nr, grundwort=None):
        self.lichter = lichter
        self.lieder = lieder            # Name → [(Note, Sechzehntel)], ms (Bibliothek und eigene)
        self.signale = signale          # Name → Tonfolge (Tupel des Spielers)
        self.sequenzen = sequenzen      # Name → Liste von Anweisungen (Quelle)
        self.stufen_nr = stufen_nr      # Name einer Schrittliste → Nummer der Stufe (für SPIELE)
        self.grundwort = grundwort      # so beginnt jede Liste, wenn das Heft ein Grundbild hat (base_frame)
        self.toene = []
        self.fertig = {}

    def ton_nr(self, folge, stelle):
        folge = tuple(tuple(t) for t in folge)
        if folge not in self.toene:
            if len(self.toene) == 255:
                raise Fehler(stelle, "mehr als 255 Tonfolgen")
            self.toene.append(folge)
        return self.toene.index(folge)

    def liste(self, name, stelle=None, tiefe=0):
        if name in self.fertig:
            return self.fertig[name]
        if name not in self.sequenzen:
            raise Fehler(stelle or "ablaeufe.json", "Schrittliste %r gibt es nicht" % (name,))
        if tiefe > 8:
            raise Fehler(stelle or name, "Schrittlisten rufen sich im Kreis")
        b = self._ops(self.sequenzen[name], "sequences.%s" % name, self.grundwort, tiefe)[0]
        self.fertig[name] = bytes(b)
        return self.fertig[name]

    def _ops(self, ops, stelle, w, tiefe):
        if not isinstance(ops, list):
            raise Fehler(stelle, "eine Schrittliste ist eine Liste von Anweisungen")
        b = bytearray()
        for i, op in enumerate(ops):
            teil, w = self._op(op, "%s[%d]" % (stelle, i), w, tiefe)
            b += teil
        return b, w

    def _op(self, op, stelle, w, tiefe):
        if not isinstance(op, dict) or "op" not in op:
            raise Fehler(stelle, "jede Anweisung nennt ihr op")
        art = op["op"]
        if art not in _OP_FELDER:
            raise Fehler(stelle, "Anweisung %r gibt es nicht" % (art,))
        zu_viel = set(op) - _OP_FELDER[art] - {"op"}
        if zu_viel:
            raise Fehler(stelle, "%s kennt %s nicht" % (art, ", ".join(sorted(zu_viel))))
        stelle = "%s (%s)" % (stelle, art)
        b = bytearray()
        L = self.lichter

        def zeige(neu):
            b.append(ZEIGE)
            b.extend(neu.to_bytes(3, "big"))
            return neu

        def ton(folge):
            b.extend((TON, self.ton_nr(folge, stelle)))

        if art in ("set_leds", "leds_on", "leds_off"):
            neu = wort(L.menge(op.get("leds", []), stelle, op.get("within")))
            if art != "set_leds" and w is None:
                raise Fehler(stelle, "nach Warten auf Taster oder einer anderen Schrittliste ist nicht bekannt, was "
                                     "leuchtet – erst set_leds")
            w = zeige(neu if art == "set_leds" else (w | neu if art == "leds_on" else w & ~neu))
        elif art == "brightness":
            p = round(op.get("factor", 1.0) * 100)
            if not 0 <= p <= 255:
                raise Fehler(stelle, "factor 0 … 2.55")
            b += bytes((HELL, p))
        elif art == "star":
            hue, level = op.get("hue"), op.get("level")
            fein = (isinstance(hue, float) and hue != int(hue)) or (
                level is not None and abs(level * 100 - round(level * 100)) > 1e-9)
            if fein:                    # Überblendungen von Heft 1: Farbton und Helligkeit mit Nachkommastellen
                b.append(STERN_FEIN)
                h = _hue(hue, stelle) if hue in ("gold", "white", "off") else _hue(hue, stelle, fein=True)
                b += _u16(h, stelle)
                b += _u16(LEVEL_GRUND if level is None else int(round(level * 10000)), stelle)
            else:
                b.append(STERN)
                b += _u16(_hue(hue, stelle), stelle)
                if level is not None and not 0 <= level <= 1:
                    raise Fehler(stelle, "level 0 … 1")
                b.append(V_GRUND if level is None else int(round(level * 100)))
        elif art == "star_fade":
            b.append(BLENDE)
            b += _u16(_hue(op.get("from"), stelle), stelle) + _u16(_hue(op.get("to"), stelle), stelle)
            b += _u16(op.get("ms", 0), stelle)
        elif art == "tone":
            ton(ton_folge([{k: op[k] for k in ("note", "ms", "gap") if k in op}], stelle))
        elif art == "tones":
            ton(ton_folge(op.get("tones", []), stelle))
        elif art == "sweep":
            ton(ton_folge([{"from_hz": op.get("from_hz"), "to_hz": op.get("to_hz"), "ms": op.get("ms")}], stelle))
        elif art == "signal":
            name = op.get("signal")
            if name not in self.signale:
                raise Fehler(stelle, "Signalton %r gibt es nicht" % (name,))
            ton(self.signale[name])
            if not op.get("background"):
                b.append(FERTIG)
        elif art == "wait":
            b.append(PAUSE)
            b += _u16(op.get("ms"), stelle)
        elif art == "wait_tone":
            b.append(FERTIG)
        elif art == "wait_button":
            if op.get("period_ms", 500) <= 0:
                raise Fehler(stelle, "period_ms: Takt über 0 ms")
            b.append(TASTER)
            b += _u16(op.get("timeout_ms"), stelle) + _u16(op.get("period_ms", 500), stelle)
            b += wort(L.menge(op.get("blink", []), stelle)).to_bytes(3, "big")
            b += wort(L.menge(op.get("alt_blink", []), stelle)).to_bytes(3, "big")
            w = None
            if "if_pressed" in op:
                innen, _ = self._ops(op["if_pressed"], stelle + ".if_pressed", None, tiefe)
                b.append(SONST)
                b += _u16(len(innen), stelle)
                b += innen
        elif art == "show_switches":
            kanaele = [L.kanal(n, stelle) for n in op.get("leds", [])]
            if len(kanaele) != 8:
                raise Fehler(stelle, "leds: genau acht Lichter, Schalter 1 zuerst")
            b.append(DIP)
            b += _u16(op.get("ms"), stelle)
            b += bytes((1 if op.get("live", True) else 0, self.ton_nr(ton_folge(TICK, stelle), stelle)))
            b += bytes(kanaele)
            w = None
        elif art == "request":
            if op.get("period_ms", 500) <= 0:
                raise Fehler(stelle, "period_ms: Takt über 0 ms")
            b.append(WUNSCH)
            b += _u16(op.get("timeout_ms"), stelle) + _u16(op.get("settle_ms", 1500), stelle)
            b.append(op.get("default", 2))
            b += _u16(op.get("period_ms", 500), stelle)
            b += wort(L.menge(op.get("blink", []), stelle)).to_bytes(3, "big")
            b += wort(L.menge(op.get("alt_blink", []), stelle)).to_bytes(3, "big")
            b.append(self.ton_nr(ton_folge(TICK, stelle), stelle))
            w = None
        elif art == "flicker":
            schritt = op.get("step_ms", [40, 104])
            dichte = op.get("density", 0.5)
            tick = op.get("tick", 0)
            b.append(FLACKERN)
            b += wort(L.menge(op.get("leds", []), stelle)).to_bytes(3, "big")
            b += _u16(op.get("ms"), stelle) + _u16(schritt[0], stelle) + _u16(schritt[1] - schritt[0], stelle)
            b += bytes((round(dichte * 100), round(tick * 100), 1 if op.get("end", "on") == "on" else 0,
                        self.ton_nr(ton_folge(TICK, stelle), stelle)))
            w = None
        elif art == "run_sequence":
            name = op.get("sequence")
            if op.get("show"):
                if name not in self.stufen_nr:
                    raise Fehler(stelle, "show: %r ist keine Schrittliste einer Stufe" % (name,))
                b += bytes((SPIELE, self.stufen_nr[name]))
            else:
                if name not in self.sequenzen:
                    raise Fehler(stelle, "Schrittliste %r gibt es nicht" % (name,))
                b += self._ops(self.sequenzen[name], "sequences.%s" % name, w, tiefe + 1)[0]
            w = None
        elif art == "repeat":
            for _ in range(op.get("times", 1)):
                teil, w = self._ops(op.get("ops", []), stelle + ".ops", w, tiefe)
                b += teil
        elif art == "blink":
            neu = wort(L.menge(op.get("leds", []), stelle))
            if w is None:
                raise Fehler(stelle, "blink braucht ein bekanntes Bild davor (set_leds)")
            for _ in range(op.get("times", 3)):
                zeige(w & ~neu)
                b.append(PAUSE)
                b += _u16(op.get("off_ms", 200), stelle)
                zeige(w | neu)
                b.append(PAUSE)
                b += _u16(op.get("on_ms", 200), stelle)
            w = w | neu
        elif art == "chase":
            noten = op.get("notes")
            ms = op.get("ms", 200)
            for j, n in enumerate(op.get("leds", [])):
                w = zeige(wort([L.kanal(n, stelle)]))
                if noten:
                    ton(ton_folge([{"note": noten[j % len(noten)], "ms": ms * 3 // 4, "gap": 0}], stelle))
                b.append(PAUSE)
                b += _u16(ms, stelle)
        elif art == "morse":
            ziel = wort(L.menge(op.get("leds", []), stelle))
            if w is None:
                raise Fehler(stelle, "morse braucht ein bekanntes Bild davor (set_leds)")
            for z in op.get("text", "").upper():
                for p in MORSE.get(z, ""):
                    dauer = MORSE_MS * (1 if p == "." else 3)
                    zeige(w | ziel)
                    ton(ton_folge([{"note": "G6", "ms": dauer, "gap": 0}], stelle))
                    b.append(PAUSE)
                    b += _u16(dauer, stelle)
                    zeige(w & ~ziel)
                    b.append(PAUSE)
                    b += _u16(MORSE_MS, stelle)
                b.append(PAUSE)
                b += _u16(MORSE_MS * 2, stelle)
            w = zeige(w)
        elif art == "song_with_leds":
            name = op.get("song")
            if name not in self.lieder:
                raise Fehler(stelle, "Lied %r gibt es nicht (Liedbibliothek oder own_songs)" % (name,))
            noten, ms = self.lieder[name]
            anzahl = op.get("count", len(noten))
            if not 1 <= anzahl <= len(noten):
                raise Fehler(stelle, "%s hat %d Töne, nicht %d" % (name, len(noten), anzahl))
            toene = lied_toene(noten, ms, stelle, tempo=op.get("tempo", 1), anzahl=anzahl, schluss=op.get("end"))
            leds = op.get("leds")
            if leds is None:
                ton(toene)
                if not op.get("background"):
                    b.append(FERTIG)
            else:
                stufen = _etagen([n for n, _ in noten[:anzahl]]) if leds == "tier" else None
                for j, t in enumerate(toene):
                    if t[0]:
                        if stufen:
                            w = zeige(wort(L.menge(["TIER_%d" % min(4, stufen[t[0]]) if stufen[t[0]] <= 4 else "TOP"],
                                                    stelle)))
                        else:
                            bild = leds[j % len(leds)]
                            w = zeige(wort(L.menge(bild if isinstance(bild, list) else [bild], stelle)))
                        ton((t,))
                    b.append(PAUSE)
                    b += _u16(t[2] + t[3], stelle)
        return b, w


def _etagen(noten):
    """Note → Etage nach ihrer Höhe im Stück: der tiefste Ton Etage 1, der höchste die oberste (höchstens 5 = Spitze).
    Wie _etagen() von Heft 2, je Frequenz."""
    hoehen = sorted({round(hz(n)) for n in noten if n != "R"})
    stufen = min(len(hoehen), 5)
    return {h: 1 + (round(i * (stufen - 1) / (len(hoehen) - 1)) if len(hoehen) > 1 else 0) for i, h in enumerate(hoehen)}


# --- Die Listen einer Stufe: Verweise und Dauer ---------------------------------------------------------------------

LAENGE = (4, 2, 4, 7, 2, 3, 1, 11, 3, 13, 15, 2, 5, 14)   # Byte je Schritt, wie spieler.LAENGE
ABFRAGE_MS, DIP_MS, BLENDE_MS = 10, 20, 30                  # wie spieler.py


def _u16_aus(d, i):
    return d[i] << 8 | d[i + 1]


def schritte(liste):
    """(Art, Stelle) je Schritt einer Liste im Spielerformat, auch die in einem SONST-Block."""
    i = 0
    while i < len(liste):
        yield liste[i], i
        i += LAENGE[liste[i]]


def pruefe_verweise(liste, nr, stuecke):
    """SPIELE n und WUNSCH (mit seinem Standard und allen wählbaren Nummern 1 … 8): jede Nummer gibt es, und ihre
    Vorstellung wartet nicht und spielt nicht selbst weiter – so kann nichts sich selbst aufrufen. stuecke: je Stufe
    1 … n (Liste, Vorstellung oder None). Wie der Erzeuger von Heft 2 bis Schritt 2."""
    for art, i in schritte(liste):
        if art == SPIELE:
            ziele = [liste[i + 1]]
        elif art == WUNSCH:
            ziele = [liste[i + 5]] + list(range(1, min(8, len(stuecke)) + 1))
        else:
            continue
        for ziel in ziele:
            if not 1 <= ziel <= len(stuecke) or ziel == nr or stuecke[ziel - 1][0] is None:
                raise Fehler("Stufe %d" % nr, "spielt Nummer %d" % ziel)
            eins, vor = stuecke[ziel - 1]
            if any(a in (SPIELE, WUNSCH, TASTER) for a, _ in schritte(vor or eins)):
                raise Fehler("Stufe %d" % nr, "die Vorstellung von %d wartet oder spielt selbst weiter" % ziel)


def dauer(liste, toene, stuecke, t=0, ton_ende=0):
    """(Zeit am Ende der Schritte, Ende der letzten Tonfolge) in ms – ohne Druck und ohne Änderung am Schalter, wie in
    der Vorstellung. Flackern zählt mit seiner Mindestdauer."""
    i = 0
    while i < len(liste):
        art = liste[i]
        if art == BLENDE:
            ms = _u16_aus(liste, i + 5)
            n = max(1, ms // BLENDE_MS)
            t += n * (ms // n)
        elif art == TON:
            ton_ende = t + sum(an + aus for _, _, an, aus in toene[liste[i + 1]])
        elif art == PAUSE:
            t += _u16_aus(liste, i + 1)
        elif art == FERTIG:
            t = max(t, ton_ende)
        elif art == TASTER:
            ms = _u16_aus(liste, i + 1)
            t += -(-ms // ABFRAGE_MS) * ABFRAGE_MS
        elif art == SONST:
            i += _u16_aus(liste, i + 1)
        elif art == DIP:
            ms = _u16_aus(liste, i + 1)
            t += -(-ms // DIP_MS) * DIP_MS if liste[i + 3] else ms
        elif art == FLACKERN:
            t += _u16_aus(liste, i + 4)
        elif art in (WUNSCH, SPIELE):
            if art == WUNSCH:
                t += -(-_u16_aus(liste, i + 1) // ABFRAGE_MS) * ABFRAGE_MS
            ziel = liste[i + 5] if art == WUNSCH else liste[i + 1]
            eins, vor = stuecke[ziel - 1]
            t, ton_ende = dauer(vor or eins, toene, stuecke, t, ton_ende)
        i += LAENGE[art]
    return t, ton_ende


def laenge(liste, toene, stuecke):
    t, ton_ende = dauer(liste, toene, stuecke)
    return max(t, ton_ende)


# --- Lieder für den Baum ------------------------------------------------------------------------------------------

def lied_kompakt(noten, ms, stelle, bereich=LIED_HZ):
    """Ein Lied mit zwei Byte je Ton wie die Klasse Lied der Basis: {"ms", "hz": Tabelle, "t": Hex (Index, Sechzehntel)}.
    Der Baum rechnet daraus dieselben Töne wie lied_toene()."""
    lied_toene(noten, ms, stelle, bereich)          # prüft Tonumfang und Noten
    tabelle, daten = [0], bytearray()
    for note, einheiten in noten:
        f = _ganz_hz(note, stelle)
        if f not in tabelle:
            tabelle.append(f)
        if not 0 < einheiten < 256:
            raise Fehler(stelle, "%s: Dauer %d Sechzehntel (1 … 255)" % (note, einheiten))
        daten += bytes((tabelle.index(f), einheiten))
    if len(tabelle) > 255:
        raise Fehler(stelle, "mehr als 255 verschiedene Töne")
    return {"ms": ms, "hz": tabelle, "t": daten.hex()}


def an_aus(dauer):
    """LEGATO wie round(dauer * 0.9) in Python (auf die gerade Zahl gerundet) – ganzzahlig, damit MicroPython dasselbe
    rechnet."""
    q, r = divmod(dauer * 9, 10)
    an = q + (1 if r > 5 or (r == 5 and q % 2 == 1) else 0)
    return an, dauer - an


def bibliothek_fuer_den_baum(bibliothek):
    """(Text der liedbibliothek.json bei der Basis, [Fehler]): alle Lieder kompakt, der Bergkönig in Takten."""
    fehler, lieder = [], {}
    for name in sorted(bibliothek.get("songs", {})):
        lied = bibliothek["songs"][name]
        stelle = "liedbibliothek.json: songs.%s" % name
        try:
            if "parts" in lied:
                lieder[name] = {"ms": lied.get("ms"), "parts": {
                    teil: [[[_ganz_hz(n["note"], stelle), n["len"]] for n in takt] for takt in takte]
                    for teil, takte in sorted(lied["parts"].items())}}
            else:
                lieder[name] = lied_kompakt(lied_noten(lied, stelle), lied["ms"], stelle)
        except Fehler as f:
            fehler.append(_fehler("liedbibliothek.json", f))
    return _json({"format": FORMAT, "songs": lieder}), fehler


# --- Schlüssel und Bausteine --------------------------------------------------------------------------------------

HEFT_SCHLUESSEL = {
    "$schema": "Verweis auf das Schema dieser Datei, für den Editor (VS Code); der Baum braucht ihn nicht",
    "format": "Nummer des Formats, in dem die Datei geschrieben ist; steigt, sobald ein Heft etwas enthalten kann, das "
              "eine ältere Basis nicht kennt (S3)",
    "title": "Name des Hefts, nur zum Lesen",
    "select_code": "Stellung der acht Schalter im Wahlmodus, Schalter 1 zuerst; nur offizielle Hefte, aus dem Register",
    "boot_leds": "die drei Lichter des Startbilds; nur offizielle Hefte, aus dem Register",
    "user_pattern": "nur eigene Hefte: die Nummer des Baummusters E1 … E16; Code und Startbild setzt der Erzeuger ein",
    "all_awake": "der Baum ist von Stufe 0 an ganz wach: alle Lichter gehören zum Ruhebild",
    "progress_leds": "eigene Fortschrittsanzeige: je Stufe n ≥ 1 das Licht, das für sie steht, oder \"bottom_up\"; ohne "
                     "Angabe die Anzeige der Basis",
    "defaults": "Felder einer Stufe, die für alle Stufen gelten, die sie nicht selbst nennen",
    "stages": "die Stufen der Geschichte, der erste Eintrag ist Stufe 0; in der Reihe 25",
    "transitions": "nur für Hefte mit Wegen: die Schritte der Geschichte; ohne Angabe die Reihe",
}
STUFE_SCHLUESSEL = {
    "title": "Name der Vorführung dieser Stufe (Kunststück, Teil), nur zum Lesen",
    "new_led": "das Licht, das auf dieser Stufe dazukommt (Name von der Platine, GARLAND_LOW, GARLAND_HIGH)",
    "star_hue": "Farbe des Sterns: Farbton 0 … 359, \"gold\", \"white\" oder \"off\"",
    "idle": "das Ruhebild: sleep, wink, breathe, sparkle, gold, dark",
    "on_power_on": "was nach der Fortschrittsanzeige kommt (Einstecken, Schlummer, Test-Reset, Bypass): Bausteine",
    "sequence": "die Schrittliste dieser Stufe (Tagesspezial, Kunststück, Teil) aus ablaeufe.json",
    "show_sequence": "ihre Fassung für die Vorstellung, wenn sie anders ist; ohne Angabe sequence",
    "on_correct_code": "die Vorführung nach dem richtigen Code, der auf diese Stufe führt: Bausteine",
    "on_repeat": "was Bestätigen lang auf dieser Stufe zeigt; ohne Angabe on_correct_code ohne den Piep, auf Stufe 0 "
                 "on_power_on",
    "on_note_short": "was Note kurz im Ruhebild spielt: ein Baustein, meist play_song – oder eine Vorführung (Liste "
                     "von Bausteinen), in der replay_correct_code für die Vorführung nach dem Code steht, der zuletzt "
                     "gegangen wurde (die Python-Hefte); ein Lied oder Signalton am Ende spielt danach im Ruhebild",
    "songbook": "das Liederbuch der Stufe: die Lieder, die Note lang reihum spielt",
}
SCHRITT_SCHLUESSEL = {
    "id": "Nummer des Schritts, 1 … 254; aus ihr und dem Code entsteht der Prüfwert",
    "from": "von welcher Stufe der Schritt weggeht (Nummer in stages)",
    "to": "wohin er führt (Nummer in stages)",
    "on_correct_code": "eigene Vorführung dieses Schritts; ohne Angabe die der Ziel-Stufe",
    "bypass_target": "true an dem Schritt, dessen Ziel der Bypass ansteuert (ein Ende)",
}
BAUSTEINE = {
    "play_signal": ({"signal"}, "ein Signalton: der des Hefts, sonst der der Basis"),
    "play_song": ({"song", "until"}, "ein Lied; until: \"end\" (ganz) oder \"day_mark\" (bis zur Marke der Stufe)"),
    "power_on": (set(), "die wachen Lichter gehen der Reihe nach an, der Stern in der Farbe der Stufe, ein Zweiklang"),
    "wake_up": ({"song"}, "Luft holen, das neue Licht blinkt dreimal, der Stern blendet zur Farbe der Stufe, das Lied "
                          "bis zur Marke (ohne song O Tannenbaum)"),
    "reveal_new_led": (set(), "kurz dunkel, die bisherigen Lichter wieder an, das neue blinkt dreimal; ist der Stern "
                              "das Neue, blendet er ein"),
    "run_stage_sequence": ({"base_frame"}, "die Schrittliste, die die Stufe unter sequence nennt"),
    "run_sequence": ({"sequence", "base_frame"}, "eine bestimmte Schrittliste"),
    "run_all_sequences": ({"rounds", "base_frame", "gap_ms"}, "die Schrittlisten aller gegangenen Schritte in ihrer "
                                                               "Fassung für die Vorstellung, hintereinander"),
    "dance_to_song": ({"song"}, "die Lichter folgen der Tonhöhe des Lieds, der Stern funkelt dazu"),
    "finale": (set(), "das Finale: von unten nach oben, die Spitze zuletzt, der Stern golden, das ganze O Tannenbaum"),
}
NOCHMAL = "replay_correct_code"  # nur in on_note_short als Liste: die Vorführung nach dem letzten Code, mit Piep
NOCHMAL_TEXT = ("nur in on_note_short als Liste: die Vorführung nach dem Code, der zuletzt gegangen wurde, mit ihrem "
                "Piep (am Baum eingesetzt, je nach Schritt)")
STERN_LICHT = -1                # new_led und progress_leds: der Stern als Licht einer Stufe (ZE-A1)
NOTE = ("stop_show", "stop_then_note", "skip_to_next", "skip_to_last", "ignore")
RUHE = ("sleep", "wink", "breathe", "sparkle", "gold", "dark")


def _fehler(datei, f):
    return {"file": datei, "where": f.stelle, "text": f.text}


def _json(daten):
    return json.dumps(daten, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def code_wert(text, stelle):
    if not isinstance(text, str) or len(text) != 8 or set(text) - {"0", "1"}:
        raise Fehler(stelle, "%r – acht Ziffern 0/1, Schalter 1 zuerst" % (text,))
    return int(text, 2)


def gedreht(code):
    """Bitfolge umgekehrt und invertiert (der Schalter von der anderen Seite gelesen), wie pruefung.gedreht."""
    r = 0
    for i in range(8):
        r = (r << 1) | ((code >> i) & 1)
    return r ^ 0xFF


def _beide(codes):
    return set(codes) | {gedreht(c) for c in codes}


def pruefwert(salz, schritt, code):
    return hashlib.sha256(salz + bytes((schritt, code))).digest()[:4].hex()


# --- Ein Heft ------------------------------------------------------------------------------------------------------

def erzeuge(heft, ablaeufe, lieder, codes, lichter, bibliothek, register, eigen=False, ordner=None):
    """Prüft ein Heft und übersetzt es. Rückgabe ({Dateiname: Text}, [Fehler]); bei Fehlern keine Dateien.

    heft, ablaeufe, lieder: der Inhalt von heft.json, ablaeufe.json, lieder.json (bzw. der Schlüssel heft, sequences
    und songs einer Baum-Datei); codes: {"salt", "bypass", "steps": [{"id", "code"}]}; lichter: die Beschreibung der
    Platine; bibliothek: die Liedbibliothek; register: firmware/basis/register.json; eigen: ein eigenes Heft (S2);
    ordner: der Ordner eines offiziellen Hefts (prüft Code und Startbild gegen das Register)."""
    fehler = []
    try:
        L = Lichter(lichter)
    except (KeyError, IndexError, TypeError) as e:
        return {}, [{"file": "lichter", "where": "", "text": "Beschreibung der Lichter unvollständig: %r" % (e,)}]
    lieder = lieder or {}
    ablaeufe = ablaeufe or {}

    def versuche(datei, f, *args):
        try:
            return f(*args)
        except Fehler as e:
            fehler.append(_fehler(datei, e))
            return None

    # Lieder: Bibliothek und eigene; ein eigenes geht in einem eigenen Heft vor (S8)
    alle_lieder = {}
    for name, lied in bibliothek.get("songs", {}).items():
        if "parts" not in lied:
            alle_lieder[name] = (lambda n=name, l=lied: (lied_noten(l, "liedbibliothek.json: " + n), l["ms"]))
    eigene = {}
    for name, lied in (lieder.get("own_songs") or {}).items():
        stelle = "own_songs.%s" % name
        if name in bibliothek.get("songs", {}) and not eigen:
            fehler.append({"file": "lieder.json", "where": stelle, "text": "den Namen hat schon ein Lied der "
                                                                           "Liedbibliothek"})
            continue
        k = versuche("lieder.json", lied_kompakt, versuche("lieder.json", lied_noten, lied, stelle) or [], lied.get("ms", 0),
                     stelle)
        if k is not None:
            eigene[name] = k
            alle_lieder[name] = (lambda l=lied, s=stelle: (lied_noten(l, s), l["ms"]))
    noten_cache = {}

    def noten(name):
        if name not in noten_cache:
            noten_cache[name] = alle_lieder[name]()
        return noten_cache[name]

    # Signaltöne: die der Basis aus der Bibliothek, die des Hefts überschreiben sie (S7)
    signale = {}
    for quelle, datei in ((bibliothek.get("signals", {}), "liedbibliothek.json"), (lieder.get("signals") or {}, "lieder.json")):
        for name, sig in quelle.items():
            folge = versuche(datei, ton_folge, sig.get("tones", []), "signals.%s" % name, SIGNAL_HZ)
            if folge is not None:
                signale[name] = folge

    zu_viel = set(heft) - set(HEFT_SCHLUESSEL)
    for k in sorted(zu_viel):
        fehler.append({"file": "heft.json", "where": k, "text": "den Schlüssel gibt es nicht"})
    if heft.get("format", FORMAT) != FORMAT:
        fehler.append({"file": "heft.json", "where": "format", "text": "Format %r – diese Basis liest %d" %
                                                                         (heft.get("format"), FORMAT)})

    # Wahlmodus und Startbild (S2)
    select, boot = None, None
    if eigen:
        for k in ("select_code", "boot_leds"):
            if k in heft:
                fehler.append({"file": "heft.json", "where": k, "text": "ein eigenes Heft nennt nur user_pattern"})
        muster = {h["pattern"]: h for h in register["user"]}
        nr = heft.get("user_pattern")
        if nr not in muster:
            fehler.append({"file": "heft.json", "where": "user_pattern", "text": "1 … 16"})
        else:
            select = code_wert(muster[nr]["select_code"], "register")
            boot = [L.kanal(n, "register") for n in muster[nr]["boot_leds"]]
    else:
        if "user_pattern" in heft:
            fehler.append({"file": "heft.json", "where": "user_pattern", "text": "nur eigene Hefte"})
        select = versuche("heft.json", code_wert, heft.get("select_code"), "select_code")
        boot = versuche("heft.json", lambda: [L.kanal(n, "boot_leds") for n in heft.get("boot_leds", [])])
        eintrag = next((h for h in register["official"] if h["folder"] == ordner), None) if ordner else None
        if ordner and (eintrag is None or eintrag["select_code"] != heft.get("select_code")
                       or eintrag["boot_leds"] != heft.get("boot_leds")):
            fehler.append({"file": "heft.json", "where": "select_code, boot_leds", "text": "stehen so nicht im Register "
                                                                                           "(firmware/basis/register.json)"})
        andere = [h for h in register["official"] if h["folder"] != ordner]
        if select is not None and any(int(h["select_code"], 2) in _beide([select]) for h in andere):
            fehler.append({"file": "heft.json", "where": "select_code", "text": "gehört schon einem anderen Heft"})

    # Stufen
    stufen_quelle = heft.get("stages") or []
    defaults = heft.get("defaults") or {}
    if len(stufen_quelle) != 25 and "transitions" not in heft:
        fehler.append({"file": "heft.json", "where": "stages", "text": "in der Reihe 25 Stufen (0 … 24), nicht %d" %
                                                                        len(stufen_quelle)})
    elif not 2 <= len(stufen_quelle) <= 255:
        fehler.append({"file": "heft.json", "where": "stages", "text": "2 … 255 Stufen, nicht %d" % len(stufen_quelle)})
    stufen = []
    for s, eintrag in enumerate(stufen_quelle):
        for k in sorted(set(eintrag) | set(defaults)):
            if k not in STUFE_SCHLUESSEL:
                fehler.append({"file": "heft.json", "where": "stages[%d].%s" % (s, k), "text": "den Schlüssel gibt es "
                                                                                                "nicht"})
        st = dict(defaults)
        st.update(eintrag)
        stufen.append(st)
    sequenzen = dict(ablaeufe.get("sequences") or {})
    stufen_nr = {st["sequence"]: s for s, st in enumerate(stufen) if st.get("sequence")}

    # Schrittlisten
    grund = ablaeufe.get("base_frame")
    grundwort = None
    if grund is not None:
        grundwort = versuche("ablaeufe.json", lambda: wort(L.menge(grund.get("leds", []), "base_frame")))
    lieder_noten = {}
    for n in alle_lieder:
        try:
            lieder_noten[n] = noten(n)
        except Fehler as e:
            fehler.append(_fehler("liedbibliothek.json", e))
    u = Uebersetzer(L, lieder_noten, signale, sequenzen, stufen_nr, grundwort)
    listen = {}
    for name in sorted(sequenzen):
        b = versuche("ablaeufe.json", u.liste, name)
        if b is not None:
            listen[name] = b.hex()

    # Verweise der Schrittlisten von Stufe zu Stufe (spiele, Wunschkonzert)
    stuecke = []
    for st in stufen[1:]:
        eins, vor = st.get("sequence"), st.get("show_sequence")
        stuecke.append((bytes.fromhex(listen[eins]) if eins in listen else None,
                        bytes.fromhex(listen[vor]) if vor in listen else None))
    while stuecke and stuecke[-1][0] is None:
        stuecke.pop()
    for nr, (eins, vor) in enumerate(stuecke, 1):
        for liste_ in (eins, vor):
            if liste_ is not None:
                versuche("ablaeufe.json", pruefe_verweise, liste_, nr, stuecke)

    # Tagesmarken
    marken = lieder.get("day_marks") or {}

    def marke(song, s, stelle):
        if song not in marken:
            raise Fehler(stelle, "für %r gibt es keine Tagesmarken (lieder.json, day_marks)" % song)
        reihe = marken[song]
        if len(reihe) != len(stufen) or not all(isinstance(x, int) and x >= 0 for x in reihe):
            raise Fehler(stelle, "day_marks.%s: je Stufe eine ganze Zahl" % song)
        if reihe[s] > len(noten(song)[0]):
            raise Fehler(stelle, "day_marks.%s: %d Töne, das Lied hat %d" % (song, reihe[s], len(noten(song)[0])))
        return reihe[s]

    marken_genutzt = set()

    def baustein(b, s, stelle, st):
        if not isinstance(b, dict) or b.get("action") not in BAUSTEINE:
            raise Fehler(stelle, "Baustein %r gibt es nicht (%s)" % (b.get("action") if isinstance(b, dict) else b,
                                                                    ", ".join(BAUSTEINE)))
        art = b["action"]
        felder = BAUSTEINE[art][0]
        for k in sorted(set(b) - felder - {"action", "on_note"}):
            raise Fehler(stelle, "%s kennt %s nicht" % (art, k))
        if b.get("on_note", "stop_show") not in NOTE:
            raise Fehler(stelle, "on_note: %s" % ", ".join(NOTE))
        aus = {"action": art}
        if "on_note" in b:
            aus["on_note"] = b["on_note"]
        if art == "play_signal":
            if b.get("signal") not in signale:
                raise Fehler(stelle, "Signalton %r gibt es nicht" % (b.get("signal"),))
            aus["signal"] = b["signal"]
        elif art in ("play_song", "wake_up", "dance_to_song"):
            song = b.get("song", "o_tannenbaum")
            if song not in alle_lieder:
                raise Fehler(stelle, "Lied %r gibt es nicht (Liedbibliothek oder own_songs)" % (song,))
            aus["song"] = song
            if art == "wake_up" or b.get("until") == "day_mark":
                marke(song, s, stelle)                 # geprüft hier, nachgeschlagen am Baum (heft.anzahl)
                aus["until"] = "day_mark"
                marken_genutzt.add(song)
            elif art == "play_song" and b.get("until", "end") != "end":
                raise Fehler(stelle, "until: \"end\" oder \"day_mark\"")
        elif art == "run_stage_sequence":
            if not st.get("sequence"):
                raise Fehler(stelle, "die Stufe nennt keine sequence")
            aus = {"action": "run_stage_sequence", **({"on_note": b["on_note"]} if "on_note" in b else {})}
            if b.get("base_frame"):
                aus["base_frame"] = True
        elif art == "run_sequence":
            if b.get("sequence") not in listen:
                raise Fehler(stelle, "Schrittliste %r gibt es nicht" % (b.get("sequence"),))
            aus["sequence"] = b["sequence"]
            if b.get("base_frame"):
                aus["base_frame"] = True
        elif art == "run_all_sequences":
            aus["rounds"] = b.get("rounds", 1)
            aus["gap_ms"] = b.get("gap_ms", 0)
            if b.get("base_frame"):
                aus["base_frame"] = True
        return aus

    def liste(werte, s, stelle, st):
        if not isinstance(werte, list):
            raise Fehler(stelle, "eine Liste von Bausteinen")
        return [baustein(b, s, "%s[%d]" % (stelle, i), st) for i, b in enumerate(werte)]

    def note_kurz(wert, s, stelle, st):
        """on_note_short: ein Baustein oder eine Vorführung; in ihr steht replay_correct_code für die Vorführung nach
        dem Code, der zuletzt gegangen wurde (Nutzer 2026-11-24). In der Reihe hat Stufe 0 keinen Code davor. Endet die
        Vorführung mit play_song oder play_signal, spielt das am Baum nach ihrem Ende im Ruhebild (main._musik)."""
        if not isinstance(wert, list):
            return baustein(wert, s, stelle, st)
        if not wert:
            raise Fehler(stelle, "eine leere Vorführung – ohne on_note_short tut die Note nichts")
        aus = []
        for i, b in enumerate(wert):
            hier = "%s[%d]" % (stelle, i)
            if isinstance(b, dict) and b.get("action") == NOCHMAL:
                if set(b) - {"action"}:
                    raise Fehler(hier, "%s kennt %s nicht" % (NOCHMAL, ", ".join(sorted(set(b) - {"action"}))))
                if s == 0 and heft.get("transitions") is None:
                    raise Fehler(hier, "%s: vor Stufe 0 gibt es keinen Code" % NOCHMAL)
                aus.append({"action": NOCHMAL})
            else:
                aus.append(baustein(b, s, hier, st))
        return aus


    neue = []
    baum_stufen = []
    for s, st in enumerate(stufen):
        stelle = "stages[%d]" % s
        bs = {}
        try:
            if s and "new_led" in st:
                k = STERN_LICHT if st["new_led"] == "star" else L.kanal(st["new_led"], stelle + ".new_led")
                if k in neue:
                    raise Fehler(stelle + ".new_led", "das Licht kommt schon auf Stufe %d dazu" % (neue.index(k) + 1))
                bs["new_led"] = k
                neue.append(k)
            elif s and not heft.get("all_awake"):
                raise Fehler(stelle, "new_led fehlt")
            hue = st.get("star_hue", "off")
            if hue == "off":
                bs["star_hue"] = None
            elif hue in ("gold", "white"):
                bs["star_hue"] = hue
            else:
                _hue(hue, stelle + ".star_hue")
                bs["star_hue"] = hue
            ruhe = st.get("idle", "dark")
            if ruhe not in RUHE:
                raise Fehler(stelle + ".idle", "%r – %s" % (ruhe, ", ".join(RUHE)))
            bs["idle"] = ruhe
            for k in ("sequence", "show_sequence"):
                if st.get(k):
                    if st[k] not in listen:
                        raise Fehler("%s.%s" % (stelle, k), "Schrittliste %r gibt es nicht" % st[k])
                    bs[k] = st[k]
            bs["on_power_on"] = liste(st.get("on_power_on", []), s, stelle + ".on_power_on", st)
            if s:
                if "on_correct_code" not in st:
                    raise Fehler(stelle, "on_correct_code fehlt")
                bs["on_correct_code"] = liste(st["on_correct_code"], s, stelle + ".on_correct_code", st)
            if "on_repeat" in st:
                bs["on_repeat"] = liste(st["on_repeat"], s, stelle + ".on_repeat", st)
            elif s:
                bs["on_repeat"] = ohne_piep(bs["on_correct_code"])
            else:
                bs["on_repeat"] = bs["on_power_on"]
            if st.get("on_note_short") is not None:
                bs["on_note_short"] = note_kurz(st["on_note_short"], s, stelle + ".on_note_short", st)
            buch = st.get("songbook", [])
            for name in buch:
                if name not in alle_lieder:
                    raise Fehler(stelle + ".songbook", "Lied %r gibt es nicht" % (name,))
            bs["songbook"] = list(buch)
        except Fehler as e:
            fehler.append(_fehler("heft.json", e))
        baum_stufen.append(bs)

    # Fortschrittsanzeige
    fortschritt = None
    if "progress_leds" in heft:
        p = heft["progress_leds"]
        if p == "bottom_up":
            fortschritt = sorted(range(L.kanaele), key=L._hoehe)
            fortschritt = [k for k in sorted(range(L.kanaele), key=lambda k: (L._hoehe(k)[0], L._seite(k), k))]
        elif isinstance(p, list):
            fortschritt = []
            for n in p:
                fortschritt.append(STERN_LICHT if n == "star" else versuche("heft.json", L.kanal, n, "progress_leds"))
        else:
            fehler.append({"file": "heft.json", "where": "progress_leds", "text": "eine Liste oder \"bottom_up\""})

    # Schritte der Geschichte: in der Reihe Schritt n von Stufe n − 1 auf n, mit Wegen aus transitions (ZB-43)
    wege = heft.get("transitions") is not None
    schritte_aus, bypass_ende, abstand = None, len(stufen) - 1, None
    try:
        schritte_aus, bypass_ende, abstand = _wege(heft.get("transitions"), stufen, liste, ohne_piep)
    except Fehler as e:
        fehler.append(_fehler("heft.json", e))

    # Codes (S6) – nur gegen Schritte, die selbst stimmen; sonst wäre jeder Code ein Folgefehler
    codes_aus = None
    if schritte_aus is not None:
        gruppen = {}
        for t in schritte_aus:
            gruppen.setdefault(t["from"], []).append(t["id"])
        try:
            codes_aus = _codes(codes, [t["id"] for t in schritte_aus], list(gruppen.values()), register, select)
        except Fehler as e:
            fehler.append(_fehler("codes", e))

    if fehler:
        return {}, fehler
    baum_heft = {
        "format": FORMAT,
        "title": heft.get("title", ""),
        "select_code": select,
        "boot_leds": boot,
        "all_awake": bool(heft.get("all_awake")),
        "progress": fortschritt,
        "stages": baum_stufen,
        "signals": {n: folge_hex(f) for n, f in sorted(signale.items())},
    }
    # was sich ableiten lässt, steht nicht da: on_repeat = on_correct_code ohne Piep, ein wachsendes Liederbuch als Zahl
    buch = max((st.get("songbook", []) for st in baum_stufen), key=len)
    knapp = []
    for s, st in enumerate(baum_stufen):
        e = dict(st)
        if e.get("on_repeat") == (e.get("on_power_on", []) if s == 0 else ohne_piep(e.get("on_correct_code", []))):
            del e["on_repeat"]
        if e.get("songbook") and e["songbook"] == buch[:len(e["songbook"])]:
            e["songbook"] = len(e["songbook"])
        knapp.append(e)
    if buch:
        baum_heft["songbook"] = buch
    baum_heft["defaults"], stufen_kurz = _verdichte(knapp)
    # je Stufe ein Text statt Objekte: der Baum liest nur die Stufe, die er gerade braucht (heft.py, Schritt 5)
    baum_heft["stages"] = [json.dumps(st, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                           for st in stufen_kurz]
    if marken_genutzt:                  # einmal je Lied statt in jeder Vorführung: so gleichen sich die Stufen
        baum_heft["day_marks"] = {n: marken[n] for n in sorted(marken_genutzt)}
    if wege:                                   # in der Reihe rechnet heft.py die Schritte selbst
        baum_heft["transitions"] = schritte_aus
        baum_heft["bypass_end"] = bypass_ende
        baum_heft["distance"] = abstand
    dateien = {
        "ablaeufe.json": _json({"tones": [folge_hex(f) for f in u.toene], "sequences": listen,
                                "base_frame": grundwort, "gap_ms": ablaeufe.get("gap_ms", 0)}),
        "lieder.json": _json({"songs": eigene}),
        "codes.json": _json(codes_aus),
        "heft.json": _json(baum_heft),           # zuletzt: ohne lesbare heft.json ist das Heft nicht da (S8)
    }
    groesse = sum(len(t.encode("utf-8")) for t in dateien.values())
    if eigen and groesse > GRENZE_EIGEN:
        return {}, [{"file": "heft", "where": "", "text": "für den Baum zu groß: %d Byte, höchstens %d "
                     "(Arbeitsspeicher des Baums)" % (groesse, GRENZE_EIGEN)}]
    return dateien, []


def _verdichte(stufen):
    """(defaults, stages) für den Baum: Was die meisten Stufen gleich haben, steht einmal in defaults; eine Stufe nennt
    nur, was davon abweicht, und unter "-" die Felder, die sie nicht hat. Spart Flash und vor allem Arbeitsspeicher –
    sonst stünde jede Vorführung 25-mal im Speicher (Schritt 5). heft.py setzt es beim Lesen wieder zusammen."""
    def text(v):
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    vorgabe = {}
    for k in sorted({k for st in stufen for k in st}):
        zahl = {}
        for st in stufen:
            if k in st:
                zahl[text(st[k])] = zahl.get(text(st[k]), 0) + 1
        bester = max(sorted(zahl.items()), key=lambda x: x[1])
        if bester[1] >= 2:
            vorgabe[k] = json.loads(bester[0])
    aus = []
    for st in stufen:
        e = {k: v for k, v in st.items() if k not in vorgabe or text(v) != text(vorgabe[k])}
        fehlt = sorted(k for k in vorgabe if k not in st)
        if fehlt:
            e["-"] = fehlt
        aus.append(e)
    return vorgabe, aus


def folge_hex(folge):
    """Eine Tonfolge [(von_hz, bis_hz, ms_an, ms_aus)] für den Baum: je Ton vier Zahlen zu zwei Byte, hexadezimal –
    als Bytes braucht sie am Baum ein Zehntel des Speichers einer Liste aus Listen (Schritt 5)."""
    return "".join("%04x%04x%04x%04x" % tuple(t) for t in folge)


def folge_lesen(text):
    """Umkehrung von folge_hex: [(von_hz, bis_hz, ms_an, ms_aus)]."""
    b = bytes.fromhex(text)
    return [tuple(int.from_bytes(b[i + 2 * j:i + 2 * j + 2], "big") for j in range(4)) for i in range(0, len(b), 8)]


def ohne_piep(werte):
    """Was B lang zeigt, wenn eine Stufe nichts Eigenes nennt: die Vorführung ohne den Piep (play_signal correct)."""
    return [b for b in werte if not (b.get("action") == "play_signal" and b.get("signal") == "correct")]


def stufe_ganz(vorgabe, roh, s, buch):
    """Eine Stufe der heft.json für den Baum, wieder ganz – wie heft.Heft.stufe(s) sie liefert: defaults darunter, "-"
    entfernt, on_repeat abgeleitet, wo er fehlt, songbook als Zahl ausgeschrieben (der Anfang von buch)."""
    d = dict(vorgabe)
    d.update(json.loads(roh) if isinstance(roh, str) else roh)
    for k in d.pop("-", []):
        d.pop(k, None)
    if "on_repeat" not in d:
        d["on_repeat"] = d.get("on_power_on", []) if s == 0 else ohne_piep(d.get("on_correct_code", []))
    if isinstance(d.get("songbook"), int):
        d["songbook"] = buch[:d["songbook"]]
    return d


def heft_ganz(baum_heft):
    """Eine heft.json für den Baum in der ausgeschriebenen Form, wie sie bis Schritt 5 auf dem Baum lag: jede Stufe
    ganz, die Tagesmarke als count, run_stage_sequence als run_sequence mit dem Namen, Signaltöne als Listen. Für
    Tests und Werkzeuge, die die Daten lesen; der Baum selbst braucht die knappe Form (Arbeitsspeicher)."""
    h = dict(baum_heft)
    marken = h.pop("day_marks", {})

    def ganz(b, s, st):
        b = dict(b)
        if b.get("until") == "day_mark":
            del b["until"]
            b["count"] = marken[b["song"]][s]
        if b["action"] == "run_stage_sequence":
            b["action"], b["sequence"] = "run_sequence", st["sequence"]
        return b

    stufen = stufen_des_baums(baum_heft)
    for s, st in enumerate(stufen):
        for k in ("on_power_on", "on_correct_code", "on_repeat"):
            if k in st:
                st[k] = [ganz(b, s, st) for b in st[k]]
        if isinstance(st.get("on_note_short"), list):
            st["on_note_short"] = [b if b["action"] == NOCHMAL else ganz(b, s, st) for b in st["on_note_short"]]
        elif "on_note_short" in st:
            st["on_note_short"] = ganz(st["on_note_short"], s, st)
    h["stages"] = stufen
    h.pop("defaults", None)
    h.pop("songbook", None)
    h["signals"] = {n: [list(t) for t in folge_lesen(x)] for n, x in h["signals"].items()}
    return h


def stufen_des_baums(baum_heft):
    """Alle Stufen einer heft.json für den Baum, wieder ganz."""
    return [stufe_ganz(baum_heft.get("defaults", {}), roh, s, baum_heft.get("songbook", []))
            for s, roh in enumerate(baum_heft["stages"])]


def _wege(quelle, stufen, liste, ohne_piep):
    """([Schritt], Ziel des Bypass, Abstand je Stufe oder None). Ein Schritt: {"id", "from", "to"} und, wenn er eine
    eigene Vorführung hat, "on_correct_code" und "on_repeat" (ohne den Piep). Ohne quelle die Reihe."""
    n = len(stufen)
    if quelle is None:
        return [{"id": i, "from": i - 1, "to": i} for i in range(1, n)], n - 1, None
    if not isinstance(quelle, list) or not quelle:
        raise Fehler("transitions", "eine Liste von Schritten")
    aus, ids, ziel_bypass = [], set(), []
    for i, t in enumerate(quelle):
        stelle = "transitions[%d]" % i
        if not isinstance(t, dict):
            raise Fehler(stelle, "ein Schritt: {\"id\", \"from\", \"to\"}")
        for k in sorted(set(t) - set(SCHRITT_SCHLUESSEL)):
            raise Fehler("%s.%s" % (stelle, k), "den Schlüssel gibt es nicht")
        sid, von, nach = t.get("id"), t.get("from"), t.get("to")
        if not isinstance(sid, int) or isinstance(sid, bool) or not 1 <= sid <= 254 or sid in ids:
            raise Fehler(stelle + ".id", "eine Zahl 1 … 254, jede nur einmal")
        for k, v in (("from", von), ("to", nach)):
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v < n:
                raise Fehler("%s.%s" % (stelle, k), "eine Stufe 0 … %d" % (n - 1))
        ids.add(sid)
        schritt = {"id": sid, "from": von, "to": nach}
        if "on_correct_code" in t:
            schritt["on_correct_code"] = liste(t["on_correct_code"], nach, stelle + ".on_correct_code", stufen[nach])
            schritt["on_repeat"] = ohne_piep(schritt["on_correct_code"])
        elif nach == 0:
            raise Fehler(stelle, "ein Schritt zurück auf Stufe 0 braucht eine eigene on_correct_code")
        if t.get("bypass_target"):
            ziel_bypass.append(nach)
        aus.append(schritt)
    weg_von = {}
    for t in aus:
        weg_von.setdefault(t["from"], []).append(t["to"])
    abstand = [None] * n
    abstand[0], offen = 0, [0]
    while offen:
        s = offen.pop(0)
        for z in weg_von.get(s, []):
            if abstand[z] is None:
                abstand[z] = abstand[s] + 1
                offen.append(z)
    nie = [s for s in range(n) if abstand[s] is None]
    if nie:
        raise Fehler("transitions", "kein Weg führt auf Stufe %s" % ", ".join(str(s) for s in nie))
    enden = [s for s in range(n) if s not in weg_von]
    if not enden:
        raise Fehler("transitions", "kein Ende: von jeder Stufe geht ein Schritt weg")
    if len(ziel_bypass) != 1 or ziel_bypass[0] not in enden:
        raise Fehler("transitions", "genau ein Schritt mit bypass_target, und sein Ziel ist ein Ende (%s)"
                     % ", ".join(str(s) for s in enden))
    return sorted(aus, key=lambda t: t["id"]), ziel_bypass[0], abstand


def _codes(codes, ids_soll, gruppen, register, select):
    """Prüfwerte: je Schritt sha256(salz + schritt + code), der Bypass mit Schritt 0. ids_soll: die Schritte der
    Geschichte; gruppen: je Stufe die Schritte, die von ihr weggehen – ihre Codes müssen sich unterscheiden, auch
    gedreht."""
    if not isinstance(codes, dict):
        raise Fehler("codes", "{\"salt\", \"bypass\", \"steps\"}")
    try:
        salz = bytes.fromhex(codes.get("salt", ""))
    except ValueError:
        raise Fehler("codes.salt", "hexadezimal")
    if not salz:
        raise Fehler("codes.salt", "fehlt")
    bypass = code_wert(codes.get("bypass"), "codes.bypass")
    if gedreht(bypass) != bypass:
        raise Fehler("codes.bypass", "muss symmetrisch sein – gedreht gelesen derselbe Code")
    schritte = codes.get("steps", [])
    ids = [s.get("id") for s in schritte]
    if ids_soll == list(range(1, len(ids_soll) + 1)):
        if ids != ids_soll:
            raise Fehler("codes.steps", "je Schritt 1 … %d ein Eintrag, der Reihe nach" % len(ids_soll))
    elif sorted(i for i in ids if isinstance(i, int)) != sorted(ids_soll) or len(ids) != len(ids_soll):
        raise Fehler("codes.steps", "je Schritt der Geschichte ein Eintrag (%s)" % ", ".join(map(str, sorted(ids_soll))))
    werte = [code_wert(s.get("code"), "codes.steps[%d]" % i) for i, s in enumerate(schritte)]
    code_von = dict(zip(ids, werte))
    basis = {int(b["code"], 2) for b in register.get("base", [])}
    wahl = {int(h["select_code"], 2) for h in register["official"] + register["user"]}
    for i, c in enumerate(werte + [bypass]):
        stelle = "codes.bypass" if i == len(werte) else "codes.steps[%d]" % i
        if c in _beide(basis):
            raise Fehler(stelle, "%08d gehört der Basis (Register, MD-79)" % int(bin(c)[2:]))
        if c in _beide(wahl):
            raise Fehler(stelle, "%s ist ein Code des Wahlmodus" % format(c, "08b"))
    for i, a in enumerate(werte):
        for j in range(i + 1, len(werte)):
            b = werte[j]
            if b != a and b in _beide([a]):
                raise Fehler("codes.steps[%d]" % j, "gedreht gelesen gleich dem Code von Schritt %d" % ids[i])
    for gruppe in gruppen:                       # an einer Gabelung: jeder Weg mit eigenem Code (Regel 9)
        for i, a in enumerate(gruppe):
            for b in gruppe[i + 1:]:
                if code_von[b] in _beide([code_von[a]]):
                    raise Fehler("codes.steps", "Schritt %d und %d gehen von derselben Stufe weg und haben denselben Code"
                                 % (a, b))
    hoechste = max(ids_soll) if ids_soll else 0
    return {"salt": salz.hex(), "bypass": pruefwert(salz, 0, bypass),
            "steps": [pruefwert(salz, i, code_von[i]) if i in code_von else "" for i in range(1, hoechste + 1)]}


# --- Auskunft und Schema (S5) -------------------------------------------------------------------------------------

def auskunft(lichter, bibliothek):
    """Was die Werkstatt über den Baum wissen muss: die Lichter mit Farbe, Größe und Lage, die Gruppen, die Bausteine,
    die Anweisungen, die Lieder der Bibliothek mit Titel und die Signaltöne der Basis."""
    L = Lichter(lichter)
    return {
        "format": FORMAT,
        "limit_bytes": GRENZE_EIGEN,
        "leds": [{k: d[k] for k in ("name", "channel", "color", "size", "x", "y", "where")} for d in lichter["leds"]],
        "garlands": dict(L.ketten),
        "groups": {n: [L.name(k) for k in v] for n, v in sorted(L.gruppen.items())},
        "actions": {n: {"fields": sorted(f), "description": t} for n, (f, t) in BAUSTEINE.items()},
        "on_note": list(NOTE),
        "ops": {n: {"fields": sorted(_OP_FELDER[n]), "description": OPS[n]} for n in OPS},
        "idle": list(RUHE),
        "songs": {n: s["title"] for n, s in sorted(bibliothek.get("songs", {}).items())},
        "signals": sorted(bibliothek.get("signals", {})),
    }


def schema():
    """JSON-Schemas der Quelldateien: heft.json, ablaeufe.json, lieder.json. Jeder Schlüssel mit description."""
    baustein = {"type": "object", "required": ["action"], "properties": {
        "action": {"enum": sorted(BAUSTEINE), "description": "der Baustein: " + "; ".join(
            "%s – %s" % (n, t) for n, (_, t) in sorted(BAUSTEINE.items()))},
        "on_note": {"enum": list(NOTE), "description": "was die Note tut, solange dieser Baustein läuft"},
        "signal": {"type": "string", "description": "Name des Signaltons"},
        "song": {"type": "string", "description": "Name eines Lieds der Liedbibliothek oder aus own_songs"},
        "until": {"enum": ["end", "day_mark"], "description": "ganz oder bis zur Marke der Stufe"},
        "sequence": {"type": "string", "description": "Name einer Schrittliste aus ablaeufe.json"},
        "base_frame": {"type": "boolean", "description": "vom Grundbild aus beginnen (base_frame in ablaeufe.json)"},
        "rounds": {"type": "integer", "description": "so oft hintereinander"},
        "gap_ms": {"type": "integer", "description": "so lange das Grundbild zwischen zwei Schrittlisten"},
    }, "additionalProperties": False}
    liste = {"type": "array", "items": {"$ref": "#/$defs/action"}}
    nochmal = {"type": "object", "required": ["action"], "additionalProperties": False,
               "properties": {"action": {"const": NOCHMAL, "description": NOCHMAL_TEXT}}}
    note_kurz = {"anyOf": [{"$ref": "#/$defs/action"},
                           {"type": "array", "items": {"anyOf": [{"$ref": "#/$defs/action"}, nochmal]}}]}
    stufe = {"type": "object", "additionalProperties": False, "properties": {
        k: ({"$ref": "#/$defs/actions"} if k in ("on_power_on", "on_correct_code", "on_repeat")
            else note_kurz if k == "on_note_short"
            else {"type": "array", "items": {"type": "string"}} if k == "songbook" else {})
        | {"description": t} for k, t in STUFE_SCHLUESSEL.items()}}
    heft = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "heft.json – was ein Heft dem Baum vorgibt",
        "type": "object", "additionalProperties": False,
        "properties": {k: {"description": t} for k, t in HEFT_SCHLUESSEL.items()},
        "$defs": {"action": baustein, "actions": liste, "stage": stufe},
    }
    heft["properties"]["stages"] |= {"type": "array", "items": {"$ref": "#/$defs/stage"}}
    heft["properties"]["defaults"] |= {"$ref": "#/$defs/stage"}
    schritt = {"type": "object", "required": ["id", "from", "to"], "additionalProperties": False, "properties": {
        k: ({"$ref": "#/$defs/actions"} if k == "on_correct_code" else {"type": "boolean"} if k == "bypass_target"
            else {"type": "integer"}) | {"description": t} for k, t in SCHRITT_SCHLUESSEL.items()}}
    heft["$defs"]["transition"] = schritt
    heft["properties"]["transitions"] |= {"type": "array", "items": {"$ref": "#/$defs/transition"}}
    op = {"type": "object", "required": ["op"], "properties": {"op": {"enum": sorted(OPS), "description": "die "
          "Anweisung: " + "; ".join("%s – %s" % (n, t) for n, t in sorted(OPS.items()))}}}
    for felder in _OP_FELDER.values():
        for f in sorted(felder):                       # sortiert: sonst je Lauf eine andere Reihenfolge
            op["properties"].setdefault(f, {"description": _FELD.get(f, f)})
    ablaeufe = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ablaeufe.json – die Schrittlisten eines Hefts",
        "type": "object", "additionalProperties": False,
        "properties": {
            "$schema": {"description": HEFT_SCHLUESSEL["$schema"]},
            "sequences": {"type": "object", "description": "die Schrittlisten mit Namen",
                          "additionalProperties": {"type": "array", "items": {"$ref": "#/$defs/op"}}},
            "base_frame": {"type": "object", "description": "das Grundbild: so beginnt eine Schrittliste mit "
                                                            "base_frame (Lichter an, Stern gold)"},
            "gap_ms": {"type": "integer", "description": "in der Vorstellung so lange das Grundbild zwischen zwei "
                                                         "Schrittlisten"},
        },
        "$defs": {"op": op},
    }
    lied = {"type": "object", "properties": {
        "title": {"description": "der Titel, wie er im Heft steht"},
        "ms": {"description": "das Tempo: Millisekunden je Sechzehntel"},
        "abc": {"description": "die Noten in ABC, wie in der Quelle"},
        "key": {"description": "die Tonart des ABC"},
        "unit": {"description": "die Notenlänge, in der das ABC zählt (8 = Achtel)"},
        "transpose": {"description": "um so viele Halbtöne verschieben"},
        "notes": {"description": "statt abc: die Töne einzeln, je Ton note und len (Sechzehntel)"},
        "source": {"description": "woher die Noten sind"},
        "rights": {"description": "warum das Lied gemeinfrei ist – bei eigenen Liedern steht ein, wer das Heft macht"},
    }}
    lieder = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "lieder.json – was ein Heft an Tönen selbst mitbringt",
        "type": "object", "additionalProperties": False,
        "properties": {
            "$schema": {"description": HEFT_SCHLUESSEL["$schema"]},
            "own_songs": {"type": "object", "additionalProperties": lied, "description": "eigene Fassungen und "
                          "Melodien, die nur dieses Heft hat; je Eintrag wie ein Lied der Bibliothek"},
            "day_marks": {"type": "object", "description": "je Lied, das mit den Tagen wächst: bis zum wievielten Ton "
                          "es auf welcher Stufe spielt"},
            "signals": {"type": "object", "description": "die Signaltöne des Hefts mit Namen, je Ton note oder "
                        "from_hz/to_hz und ms; ein Name der Basis überschreibt deren Ton"},
        },
    }
    return {"heft.schema.json": heft, "ablaeufe.schema.json": ablaeufe, "lieder.schema.json": lieder}


_FELD = {
    "leds": "Lichter und Gruppen (Namen von der Platine, RED, TIER_2 …)", "within": "nur die Lichter dieser Gruppe",
    "factor": "1.0 = Grundhelligkeit", "hue": "Farbton 0 … 359, gold, white, off", "level": "Helligkeit 0 … 1",
    "from": "Farbton am Anfang", "to": "Farbton am Ende", "ms": "Dauer in Millisekunden", "note": "Note wie C6",
    "gap": "Pause nach dem Ton in ms", "tones": "die Töne der Folge", "from_hz": "Frequenz am Anfang",
    "to_hz": "Frequenz am Ende", "signal": "Name des Signaltons", "background": "nicht auf das Ende warten",
    "timeout_ms": "so lange höchstens warten", "blink": "diese Lichter blinken dabei",
    "alt_blink": "im Wechsel mit diesen", "period_ms": "Takt des Blinkens", "if_pressed": "Anweisungen nur, wenn "
    "gedrückt wurde", "live": "Änderungen sofort zeigen", "settle_ms": "so lange ohne Änderung, dann gilt die Stellung",
    "default": "diese Stufe, wenn nichts geändert wurde", "step_ms": "[kürzester, längster] Abstand zweier Bilder",
    "density": "Anteil der Lichter, die je Bild an sind", "tick": "Anteil der Bilder mit einem Tick",
    "end": "wie es endet: on (alle an) oder off; bei song_with_leds: Dauer des letzten Tons",
    "sequence": "Name einer Schrittliste", "show": "in ihrer Fassung für die Vorstellung, vom Grundbild aus",
    "times": "so oft", "ops": "die Anweisungen", "on_ms": "an", "off_ms": "aus", "notes": "je Licht ein Ton",
    "text": "der Text", "song": "Name eines Lieds", "count": "so viele Töne", "tempo": "so viel schneller",
}
