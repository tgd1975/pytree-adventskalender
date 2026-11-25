---
redirect_from: /FAQ.html
---
# Häufige Fragen

Steht deine Frage nicht dabei oder klemmt etwas, dann schreib ein
[Issue](https://github.com/tgd1975/pytree-adventskalender/issues/new/choose).

## Einrichten

### Windows warnt vor der Installationsdatei

Beim Herunterladen meldet der Browser womöglich, die Datei werde nicht häufig heruntergeladen. Dann bei der Datei auf
**…** und **Beibehalten** klicken (fragt Edge noch einmal: **Mehr anzeigen**, **Trotzdem beibehalten**). Beim
Doppelklick meldet Windows „Der Computer wurde durch Windows geschützt“: **Weitere Informationen**, dann **Trotzdem
ausführen**. Was die Datei tut, steht in ihren ersten Zeilen.

### VS Code ist schon auf meinem Rechner

Die Installationsdatei legt ein eigenes VS Code in einen eigenen Ordner, deines bleibt, wie es ist. Du kannst die
Erweiterung auch in dein VS Code holen: `pytree-adventskalender-….vsix` unter
[Releases](https://github.com/tgd1975/pytree-adventskalender/releases/latest) laden, dann in VS Code links auf das
Symbol mit den vier Kästchen, oben **…** und **Aus VSIX installieren** (englisch **Install from VSIX**). Python holst
du dann wie im nächsten Abschnitt.

### VS Code meldet „Python fehlt noch“

Hast du die Installationsdatei benutzt, starte VS Code über das Symbol **Der schlafende Baum**. Ein anderes VS Code
auf dem Rechner kennt das mitgebrachte Python nicht.

Ohne Installationsdatei führt der Knopf **Werkstatt einrichten** in der Meldung zum Schritt **Python**. Dort startet
**Python installieren** den passenden Befehl im Terminal. Unter Windows danach VS Code ganz schließen, wieder öffnen
und **Python suchen** drücken.

### VS Code will, dass ich mich anmelde

Das ist Copilot, die KI in VS Code. Für den Adventskalender brauchst du kein Konto. Im großen Fenster beim ersten
Start unten rechts **Continue without Signing In** wählen; später **Sign In** (**Anmelden**) einfach übergehen und den
Chat rechts mit dem **×** schließen. Eine KI, die mitschreibt, nimmt dir genau das Knobeln ab, bei dem du Python
lernst. Deshalb schaltet der Schritt **Einstellungen** sie in der Werkstatt aus; mit der Installationsdatei ist sie
von Anfang an aus.

### VS Code zeigt „Get started“ oder „Make it yours“

Das ist die Einführung von VS Code selbst: Farben, Schrift und was es sonst kann. Für den Adventskalender brauchst du
sie nicht, schließ sie einfach. Durch alles, was der Kalender braucht, führt die Erweiterung selbst mit **Werkstatt
einrichten**.

### VS Code zeigt „Restricted Mode“

Dann vertraut VS Code der Werkstatt noch nicht, und die Erweiterung kann deine Programme nicht starten. Unten links
auf **Restricted Mode** klicken (deutsch **Eingeschränkter Modus**), dann **Trust** (**Vertrauen**). Die Dateien in
der Werkstatt hat die Erweiterung selbst angelegt.

### Linux: VS Code als Flatpak

Ein VS Code aus Flathub sieht das Python des Systems nur über Umwege. Nimm VS Code als `.deb` von
[code.visualstudio.com](https://code.visualstudio.com/), als Snap oder über die Installationsdatei.

### Ohne Baum mitmachen

Dafür gibt es die Erweiterung in einer Fassung mit dem [Baum am Bildschirm](index.md#der-baum-am-bildschirm). Er steht
in VS Code neben deinem Programm und wird bedient wie der echte: Stecker, acht Schalter, zwei Knöpfe. Zwischen den
beiden Fassungen kannst du jederzeit wechseln; deine Lösungen und dein Fortschritt in VS Code bleiben. Jeder Baum
merkt sich aber seinen eigenen Stand, auch der am Bildschirm. Was einer noch nicht kennt, gibst du ihm der Reihe nach
ein; die Codes stehen in VS Code bei jedem gelösten Türchen.

## Unterwegs

### Was ist wo in VS Code?

- **Ganz links** steht eine schmale Leiste mit Symbolen. Das **Bäumchen** ist der Adventskalender, das Blatt-Symbol
  ganz oben der **Explorer** mit den Dateien deiner Werkstatt. Ein Klick öffnet den Bereich, ein zweiter klappt ihn zu.
- **Daneben** steht, was zum Symbol gehört, beim Bäumchen die 24 Türchen: ⭐ ist gelöst, 🔒 geht auf, sobald das
  vorige gelöst ist. Oben in dieser Spalte öffnet das Buch-Symbol das Heft als PDF, unter **…** gibt es die
  **Startseite** mit allen Türchen.
- **In der Mitte** steht die Aufgabe des Türchens mit **▶ Ausprobieren** und **✔ Prüfen**, weiter unten die Tipps,
  der Code des Tages und die Knöpfe zum vorigen und nächsten Türchen.
- **Rechts** ist deine Datei, etwa `loesung_02.py`. Hier schreibst du dein Programm. Ausprobieren und Prüfen speichern
  sie vorher selbst.
- **Unten** liegt das **Terminal**. Dort läuft dein Programm, wenn du Ausprobieren drückst, und dort stehen seine
  Ausgaben und die Meldungen von Python.
- **Ganz unten links** zeigt 🎄 mit einer Zahl, wie viele Türchen du gelöst hast. Ein Klick darauf öffnet das nächste.

Über jeder Spalte stehen Reiter, einer je offene Datei oder Seite; das **×** am Reiter schließt sie.

### Wo liegt meine Arbeit?

Im Ordner **Adventskalender** unter **Dokumente**, je Türchen ein Ordner `tuer_01` bis `tuer_24` mit deiner
`loesung_01.py` bis `loesung_24.py`. Die gehören dir: Kein Update überschreibt sie.

### Es gibt eine neue Fassung

Führ die Installationsdatei noch einmal aus, oder lade die neue `.vsix` und installier sie wie oben. Deine Lösungen
und dein Fortschritt bleiben. Welche Fassung du hast, siehst du in VS Code unter **Erweiterungen → Der schlafende
Baum**. Was sich geändert hat, steht bei den
[Releases](https://github.com/tgd1975/pytree-adventskalender/releases).

### Ich will an einem anderen Rechner weitermachen

Nimm den ganzen Ordner **Adventskalender** mit und leg ihn dort unter **Dokumente** ab, solange VS Code geschlossen
ist. Der Fortschritt steckt in einer Datei darin und kommt mit.

### Mein Programm hört nicht auf

Hört eine Schleife nie auf, etwa weil sich in ihr nichts an der Bedingung ändert, läuft dein Programm nach
**Ausprobieren** im Terminal immer weiter. Klick ins **Terminal** und drück **Strg+C**, das hält es an. Prüfen hält ein
solches Programm selbst an und sagt dir, dass es an einer Schleife hängt.

### Der Knopf Prüfen tut nichts

Öffne **Terminal → Neues Terminal**. Ist die Werkstatt offen, steht es schon im Ordner **Adventskalender**. Dort
prüft zum Beispiel `python pruefer.py tuer_06` (unter Linux `python3`) Türchen 6 wie der Knopf und zeigt auch den Code
des Tages.

### Prüfen lehnt meine Lösung ab, obwohl sie stimmt

Dann ist vielleicht das Prüfgerät zu streng. Schreib ein Issue mit der Nummer des Türchens und deinem Code, dann wird
es nachgebessert. Dasselbe gilt, wenn es etwas durchlässt, das nicht stimmen kann.

## Issues

Für ein Issue brauchst du ein kostenloses Konto bei GitHub. Issues sind für alle lesbar. Bildschirmfotos kannst du
direkt ins Textfeld ziehen.
