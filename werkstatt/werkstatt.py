"""Die Baum-Werkstatt ohne Oberfläche: ein Heft öffnen, ändern, prüfen, speichern und für den Baum übersetzen (Konzept
docs/concepts/offen/baum_werkstatt.md, „Wie die Werkstatt gebaut ist“).

Läuft unverändert im Browser (Pyodide) und am Rechner (CPython) – so prüfen die Tests am Rechner genau den Code, den
die Seite ausführt. Geprüft und übersetzt wird nur mit dem Erzeuger (firmware/erzeuger.py), nie mit nachgebauten Regeln
(HE-9). Was die Werkstatt braucht, bekommt sie hinein: den Erzeuger als Modul, die Lichter, die Liedbibliothek und das
Register – kein Zugriff auf Dateien.

Ein Heft liegt hier als die Daten, die man schreibt, in vier Teilen: heft (heft.json), ablaeufe (ablaeufe.json),
lieder (lieder.json) und codes. Eine Baum-Datei (ein eigenes Heft, S6) hat dieselben Teile unter heft, sequences,
songs und codes; ein offizielles Heft hat sie als drei Dateien im Repository, seine Codes kommen aus dem Inhalt des
Hefts und sind hier nur zu lesen. Gespeichert wird immer gleich geschrieben – json.dumps mit zwei Leerzeichen, Umlaute
als Zeichen, ein Zeilenumbruch am Ende –, so bleibt eine Datei Byte für Byte gleich, wenn man sie unverändert speichert.

Die Oberfläche (werkstatt.js) ruft die Funktionen unten mit JSON-Texten auf und bekommt JSON-Texte zurück.
"""
import hashlib
import json
import random
import re

VORGABE_STUFEN = 25
STUECK = 1024              # Bytes einer Datei je Befehl an den Baum
RESERVE_BLOECKE = 4        # was das Dateisystem des Baums beim Kopieren für Ordner und Verwaltung braucht (geschätzt)
NAME_EIGEN = re.compile(r"^muster_[0-9][0-9]$")

# Was die Werkstatt den Baum fragt (Aufspielen, Schritt 3): Fassung und Format der Basis (S3), die eigenen Hefte mit
# Titel und Größe, der freie Platz – und ob sein Programm gelaufen ist. Im Wartungsmodus endet main.py, bevor es die
# Steuerung anlegt; ein unterbrochenes Programm hinterlässt STEUERUNG unter den Namen der REPL, und sein Watchdog
# startet den Baum gleich neu. Läuft auf dem Baum (MicroPython), Antwort eine Zeile JSON.
BAUM_LESEN = """import os, json
def _w():
  b = None
  try:
    with open('basis.json') as f:
      b = json.load(f)
  except Exception:
    pass
  e = []
  try:
    namen = sorted(os.listdir('eigene'))
  except OSError:
    namen = []
  for n in namen:
    p = 'eigene/' + n
    g = 0
    try:
      for d in os.listdir(p):
        g += os.stat(p + '/' + d)[6]
    except OSError:
      continue
    t = None
    try:
      with open(p + '/heft.json') as f:
        t = json.load(f).get('title')
    except Exception:
      pass
    e.append([n, t, g])
  s = os.statvfs('/')
  print(json.dumps({'basis': b and {'format': b.get('format', 1), 'version': b.get('version')}, 'eigene': e,
                    'block': s[0], 'frei': s[0] * s[3], 'laeuft': 'STEUERUNG' in globals()}))
_w()
del _w
"""


def _text(daten):
    return json.dumps(daten, ensure_ascii=False, indent=2) + "\n"


class Werkstatt:
    def __init__(self, erzeuger, lichter, bibliothek, register):
        self.E = erzeuger
        self.lichter = lichter
        self.bibliothek = bibliothek
        self.register = register
        self.art = None            # "baum" oder "offiziell"
        self.ordner = None         # bei einem offiziellen Heft sein Ordner im Repository
        self.familie = None
        self.datei = None          # Baum-Datei: das ganze Dokument (format, heft, sequences, songs, codes)
        self.teile = {}            # heft, ablaeufe, lieder, codes

    # --- öffnen ---------------------------------------------------------------------------------------------------

    def oeffnen_baum(self, text):
        """Eine Baum-Datei (mein_baum.baum.json): ein eigenes Heft in einer Datei."""
        doc = json.loads(text)
        for k in ("heft", "sequences", "songs", "codes"):
            if k not in doc:
                raise ValueError("keine Baum-Datei: %s fehlt" % k)
        self.art, self.ordner, self.familie, self.datei = "baum", None, None, doc
        self.teile = {"heft": doc["heft"], "ablaeufe": {"sequences": doc["sequences"]}, "lieder": doc["songs"],
                      "codes": doc["codes"]}
        return self.stand()

    def oeffnen_offiziell(self, ordner, familie, heft_text, ablaeufe_text, lieder_text, codes):
        """Ein offizielles Heft aus dem Repository (nur lokal): seine drei Quelldateien und die Codes aus dem Inhalt."""
        self.art, self.ordner, self.familie, self.datei = "offiziell", ordner, familie, None
        self.teile = {"heft": json.loads(heft_text), "ablaeufe": json.loads(ablaeufe_text) if ablaeufe_text else {},
                      "lieder": json.loads(lieder_text) if lieder_text else {}, "codes": codes}
        self._roh = {"heft": heft_text, "ablaeufe": ablaeufe_text, "lieder": lieder_text}
        return self.stand()

    # --- ändern ---------------------------------------------------------------------------------------------------

    def _ort(self, pfad):
        """(Behälter, Schlüssel) für einen Pfad wie ["heft", "stages", 3, "idle"]."""
        if not pfad or pfad[0] not in self.teile:
            raise KeyError("Pfad %r" % (pfad,))
        if self.art == "offiziell" and pfad[0] == "codes":
            raise ValueError("die Codes eines offiziellen Hefts kommen aus seinem Inhalt")
        if self.art == "offiziell" and pfad[0] == "heft" and len(pfad) > 1 and pfad[1] in ("select_code", "boot_leds"):
            raise ValueError("Code und Startbild eines offiziellen Hefts stehen im Register")
        behaelter = self.teile
        for k in pfad[:-1]:
            behaelter = behaelter[k]
        return behaelter, pfad[-1]

    def setze(self, pfad, wert):
        behaelter, k = self._ort(pfad)
        if isinstance(behaelter, list) and k == len(behaelter):
            behaelter.append(wert)
        else:
            behaelter[k] = wert
        return self.fehler()

    def loesche(self, pfad):
        behaelter, k = self._ort(pfad)
        if isinstance(behaelter, list):
            behaelter.pop(k)
        else:
            behaelter.pop(k, None)
        return self.fehler()

    # --- prüfen und übersetzen ----------------------------------------------------------------------------------

    def _erzeuge(self):
        t = self.teile
        return self.E.erzeuge(t["heft"], t["ablaeufe"], t["lieder"], t["codes"], self.lichter, self.bibliothek,
                              self.register, eigen=self.art == "baum", ordner=self.ordner)

    def fehler(self):
        """Die Fehler des Erzeugers – leer, wenn das Heft so auf den Baum kann."""
        return self._erzeuge()[1]

    def erzeugt(self):
        """{Dateiname: Text} für den Baum (wie beim Zusammenstellen); Fehler als ValueError."""
        dateien, fehler = self._erzeuge()
        if fehler:
            raise ValueError("; ".join("%s %s: %s" % (f["file"], f["where"], f["text"]) for f in fehler))
        return dateien

    def ordner_auf_dem_baum(self):
        """Wohin ein eigenes Heft auf dem Baum kommt: eigene/muster_<nn> nach seinem Baummuster (S1)."""
        return "eigene/muster_%02d" % self.teile["heft"]["user_pattern"]

    # --- speichern ----------------------------------------------------------------------------------------------

    def speichern(self):
        """Baum-Datei: {"art": "baum", "text"}; offizielles Heft: {"art": "offiziell", "dateien": {Name: Text}} – nur
        die Dateien, die es gab oder die jetzt etwas enthalten."""
        if self.art == "baum":
            doc = self.datei
            doc["heft"], doc["sequences"] = self.teile["heft"], self.teile["ablaeufe"]["sequences"]
            doc["songs"], doc["codes"] = self.teile["lieder"], self.teile["codes"]
            return {"art": "baum", "text": _text(doc)}
        dateien = {"heft.json": _text(self.teile["heft"])}
        for teil, name in (("ablaeufe", "ablaeufe.json"), ("lieder", "lieder.json")):
            if self._roh[teil] is not None or self.teile[teil]:
                dateien[name] = _text(self.teile[teil])
        return {"art": "offiziell", "ordner": self.ordner, "familie": self.familie, "dateien": dateien}

    # --- Codes eines eigenen Hefts ------------------------------------------------------------------------------

    def _vergeben(self):
        besetzt = set()
        for b in self.register.get("base", []):
            besetzt |= self._beide(int(b["code"], 2))
        for h in self.register["official"] + self.register["user"]:
            besetzt |= self._beide(int(h["select_code"], 2))
        return besetzt

    def _beide(self, c):
        return {c, self.E.gedreht(c)}

    def wuerfle_codes(self, zufall=None):
        """Neue Codes für alle Schritte und einen neuen Bypass, gültig nach den Regeln des Erzeugers (S6); das Salz
        bleibt. Nur eigene Hefte."""
        if self.art != "baum":
            raise ValueError("die Codes eines offiziellen Hefts kommen aus seinem Inhalt")
        r = zufall or random.Random()
        besetzt = self._vergeben()
        sym = [c for c in range(256) if self.E.gedreht(c) == c and c not in besetzt and c not in (0, 255)]
        bypass = r.choice(sym)
        besetzt |= {bypass}
        ids = [s["id"] for s in self.teile["codes"].get("steps", [])] or list(range(1, VORGABE_STUFEN))
        frei = [c for c in range(1, 255) if bin(c).count("1") in (3, 4, 5)]
        schritte = []
        for sid in ids:
            while True:
                c = r.choice(frei)
                if not self._beide(c) & besetzt:
                    break
            besetzt |= self._beide(c)
            schritte.append({"id": sid, "code": format(c, "08b")})
        self.teile["codes"]["bypass"] = format(bypass, "08b")
        self.teile["codes"]["steps"] = schritte
        return self.fehler()

    @staticmethod
    def neues_salz(zufall=None):
        r = zufall or random.Random()
        return "".join("%02x" % r.randrange(256) for _ in range(4))

    # --- Auskunft und Lieder ------------------------------------------------------------------------------------

    def auskunft(self):
        """Was die Oberfläche über den Baum wissen muss (S5), dazu die Schemas für die Erklärungen und die Baummuster."""
        a = self.E.auskunft(self.lichter, self.bibliothek)
        a["schema"] = self.E.schema()
        a["muster"] = self.register["user"]
        return a

    def lied_toene(self, lied):
        """[(von_hz, bis_hz, ms_an, ms_aus)] eines Lieds, so wie es der Baum spielt – zum Anhören im Browser."""
        noten = self.E.lied_noten(lied, "Lied")
        return [list(t) for t in self.E.lied_toene(noten, lied.get("ms", 150), "Lied")]

    # --- Aufspielen (Konzept „Aufspielen aus dem Browser auf den Baum“) -------------------------------------------
    # Die Seite spricht mit dem Baum (Web Serial, raw REPL, baum.js); was sie ihm schickt und was er antworten muss,
    # steht hier – so prüfen es die Tests am Rechner und auf MicroPython.

    def _nur_eigene(self):
        if self.art != "baum":
            raise ValueError("Offizielle Hefte kommen nur mit der Firmware auf den Baum, nie aus der Werkstatt (HE-3).")

    @staticmethod
    def baum_fragen():
        return BAUM_LESEN

    def baum_lage(self, antwort):
        """Was aus der Antwort des Baums auf BAUM_LESEN für dieses Heft folgt: {"fehler"} hält das Aufspielen auf,
        {"ersetzt"} ist die Frage, ob das Heft unter demselben Muster ersetzt werden soll."""
        self._nur_eigene()
        b = json.loads(antwort)
        ordner = self.ordner_auf_dem_baum()
        dateien = self.erzeugt()
        format_heft = json.loads(dateien["heft.json"]).get("format", 1)
        block = b.get("block") or 4096
        eigene = [{"ordner": "eigene/" + n, "titel": titel, "bytes": groesse} for n, titel, groesse in b["eigene"]]
        alt = next((h for h in eigene if h["ordner"] == ordner), None)
        braucht = sum(-(-len(t.encode("utf-8")) // block) * block for t in dateien.values())
        frei = b["frei"] + (-(-alt["bytes"] // block) * block if alt else 0)
        lage = {"basis": b["basis"], "eigene": eigene, "frei": b["frei"], "ordner": ordner, "braucht": braucht,
                "ersetzt": alt, "fehler": None, "laeuft": b.get("laeuft", False)}
        if b.get("laeuft"):
            lage["fehler"] = ("Der Baum läuft – so nimmt er nichts an, und sein Wächter startet ihn gleich neu. Stecker "
                              "ziehen, die Note halten, einstecken (der Baum bleibt dunkel), dann noch einmal verbinden.")
        elif not b["basis"]:
            lage["fehler"] = ("Die Firmware dieses Baums kennt noch keine eigenen Hefte. Eine neuere Firmware gibt es "
                              "nur von dem, der den Baum gebaut hat.")
        elif b["basis"]["format"] < format_heft:
            lage["fehler"] = ("Dieses Heft ist im Format %d geschrieben, der Baum liest Hefte bis Format %d. Eine "
                              "neuere Firmware gibt es nur von dem, der den Baum gebaut hat."
                              % (format_heft, b["basis"]["format"]))
        elif braucht + RESERVE_BLOECKE * block > frei:
            lage["fehler"] = ("Auf dem Baum ist zu wenig Platz: frei %d kB, das Heft braucht %d kB. Ein anderes "
                              "eigenes Heft entfernen, dann noch einmal." % (frei // 1024, -(-braucht // 1024)))
        return lage

    def aufspielen_schritte(self):
        """Die Befehle an den Baum, der Reihe nach: [{"was", "code", "soll"}] – soll ist die Ausgabe, die der Baum
        liefern muss (ohne Zeilenende); jede Fehlerausgabe bricht ab. Zuerst geht die alte heft.json, dann der Rest des
        Ordners samt Stand (ein aufgespieltes Heft beginnt am Anfang); die neuen Dateien werden geschrieben und
        nachgelesen (SHA-256), heft.json als heft.neu und erst ganz am Ende umbenannt (S8). Bricht das Kopieren ab, ist
        unter dem Muster kein Heft – nie ein halbes oder ein Gemisch aus altem und neuem."""
        self._nur_eigene()
        ordner = self.ordner_auf_dem_baum()
        dateien = self.erzeugt()
        schritte = [{"was": "Platz machen unter %s" % ordner, "soll": "ok", "code": (
            "import os\n"
            "for p in ('eigene', %r):\n"
            "  try:\n    os.mkdir(p)\n  except OSError:\n    pass\n"
            "for n in ['heft.json'] + sorted(os.listdir(%r)):\n"
            "  try:\n    os.remove(%r + '/' + n)\n  except OSError:\n    pass\n"
            "print('ok' if os.listdir(%r) == [] else os.listdir(%r))\n") % (ordner, ordner, ordner, ordner, ordner)}]
        reihe = sorted(n for n in dateien if n != "heft.json") + ["heft.json"]
        for nr, name in enumerate(reihe, 1):
            inhalt = dateien[name].encode("utf-8")
            ziel = ordner + "/" + ("heft.neu" if name == "heft.json" else name)
            was = "%s kopieren (%d von %d)" % (name, nr, len(reihe))
            schritte.append({"was": was, "soll": "", "code": "_f = open(%r, 'wb')\n" % ziel})
            for i in range(0, len(inhalt), STUECK):
                schritte.append({"was": was, "soll": "", "code": "_f.write(%r)\n" % inhalt[i:i + STUECK]})
            schritte.append({"was": was, "soll": "", "code": "_f.close()\ndel _f\n"})
            schritte.append({"was": "%s nachlesen" % name, "soll": hashlib.sha256(inhalt).hexdigest(), "code": (
                "import hashlib, binascii\n"
                "_h = hashlib.sha256()\n"
                "with open(%r, 'rb') as _f:\n"
                "  while True:\n"
                "    _b = _f.read(512)\n"
                "    if not _b:\n      break\n"
                "    _h.update(_b)\n"
                "print(binascii.hexlify(_h.digest()).decode())\n"
                "del _h, _b, _f\n") % ziel})
        schritte.append({"was": "heft.json freigeben", "soll": " ".join(sorted(dateien)), "code": (
            "import os\n"
            "os.rename(%r, %r)\n"
            "print(' '.join(sorted(os.listdir(%r))))\n") % (ordner + "/heft.neu", ordner + "/heft.json", ordner)})
        return schritte

    @staticmethod
    def entfernen_schritte(ordner):
        """Ein eigenes Heft vom Baum nehmen: zuerst heft.json (dann ist es nicht mehr da), dann den Rest, den Ordner."""
        if not (ordner.startswith("eigene/") and NAME_EIGEN.match(ordner[len("eigene/"):])):
            raise ValueError("kein Ordner eines eigenen Hefts: %r" % ordner)
        return [{"was": "%s entfernen" % ordner, "soll": "ok", "code": (
            "import os\n"
            "for n in ['heft.json'] + sorted(os.listdir(%r)):\n"
            "  try:\n    os.remove(%r + '/' + n)\n  except OSError:\n    pass\n"
            "os.rmdir(%r)\n"
            "print('ok')\n") % (ordner, ordner, ordner)}]

    def stand(self):
        return {"art": self.art, "ordner": self.ordner, "familie": self.familie, "teile": self.teile,
                "fehler": self.fehler(), "auf_dem_baum": self.ordner_auf_dem_baum() if self.art == "baum" else None}


# --- Aufrufe aus der Oberfläche: JSON hinein, JSON heraus ---------------------------------------------------------

_W = [None]


def einrichten(erzeuger, lichter_text, bibliothek_text, register_text):
    _W[0] = Werkstatt(erzeuger, json.loads(lichter_text), json.loads(bibliothek_text), json.loads(register_text))
    return json.dumps(_W[0].auskunft(), ensure_ascii=False)


def aufruf(name, argumente_text):
    """Ein Aufruf der Oberfläche: Name der Methode und ihre Argumente als JSON-Liste; Antwort als JSON
    {"ok": Ergebnis} oder {"fehler": Text}."""
    try:
        ergebnis = getattr(_W[0], name)(*json.loads(argumente_text))
        return json.dumps({"ok": ergebnis}, ensure_ascii=False)
    except Exception as e:                   # die Oberfläche zeigt es an; die Werkstatt bleibt bedienbar
        return json.dumps({"fehler": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False)
