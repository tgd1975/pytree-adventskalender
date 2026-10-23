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

### Linux: VS Code als Flatpak

Ein VS Code aus Flathub sieht das Python des Systems nur über Umwege. Nimm VS Code als `.deb` von
[code.visualstudio.com](https://code.visualstudio.com/), als Snap oder über die Installationsdatei.

## Unterwegs

### Wo liegt meine Arbeit?

Im Ordner **Adventskalender** unter **Dokumente**, je Türchen ein Ordner `tur01` bis `tur24` mit deiner
`loesung.py`. Die gehört dir: Kein Update überschreibt sie.

### Es gibt eine neue Fassung

Führ die Installationsdatei noch einmal aus, oder lade die neue `.vsix` und installier sie wie oben. Deine Lösungen
und dein Fortschritt bleiben. Welche Fassung du hast, siehst du in VS Code unter **Erweiterungen → Der schlafende
Baum**. Was sich geändert hat, steht bei den
[Releases](https://github.com/tgd1975/pytree-adventskalender/releases).

### Ich will an einem anderen Rechner weitermachen

Nimm den ganzen Ordner **Adventskalender** mit und leg ihn dort unter **Dokumente** ab, solange VS Code geschlossen
ist. Der Fortschritt steckt in einer Datei darin und kommt mit.

### Der Knopf Prüfen tut nichts

Öffne **Terminal → Neues Terminal**. Ist die Werkstatt offen, steht es schon im Ordner **Adventskalender**. Dort
prüft zum Beispiel `python pruefer.py tur06` (unter Linux `python3`) Türchen 6 wie der Knopf und zeigt auch den Code
des Tages.

### Prüfen lehnt meine Lösung ab, obwohl sie stimmt

Dann ist vielleicht das Prüfgerät zu streng. Schreib ein Issue mit der Nummer des Türchens und deinem Code, dann wird
es nachgebessert. Dasselbe gilt, wenn es etwas durchlässt, das nicht stimmen kann.

## Issues

Für ein Issue brauchst du ein kostenloses Konto bei GitHub. Issues sind für alle lesbar. Bildschirmfotos kannst du
direkt ins Textfeld ziehen.
