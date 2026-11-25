---
kopfbild: /assets/titel/strahlender-baum.svg
kopfbild_text: Der Baum lacht unter einem strahlenden Stern, daneben die kleine Schlange.
---
<!-- ERZEUGT von aufgaben/werkzeug/baue_seite.py --heft 3_strahlend im Repo pytree – nicht von Hand ändern, dort ändern und neu bauen. -->
# Der strahlende Baum

*Band 3 des Python-Adventskalenders.*

Der Baum ist wach, und er kann mehr, als in seinem Bauplan steht: Du hast ihm im letzten Advent Kunststücke beigebracht.

In der Himmelswerkstatt werden Bäume nach Plänen gebaut, und die Pläne sind alt. Jeden Tag bis zum Heiligen Abend zeichnest du an neuen, in Python: für die Kerze, die Lichterkette, den Stern, das Herz und den ganzen Baum. Jeden Plan, den du fertig hast, zeigt dein Baum am eigenen Leib.

Was in den ersten beiden Heften stand, kannst du schon. Neu sind Klassen und Objekte, Türchen für Türchen.

**Vor dir steht der Baum, und das dritte Heft hat dich hierher geschickt? Dann bist du hier genau richtig.**

## Die Werkstatt einrichten

Am einfachsten geht es mit einer Installationsdatei. Sie holt VS Code, Python und die Erweiterung für dieses Heft in einen eigenen
Ordner. Administratorrechte braucht es dafür nicht, und die Werkstätten der letzten Jahre bleiben, wie sie sind.

- **Windows:**
  [installieren-strahlender-baum-windows.cmd](https://github.com/tgd1975/pytree-adventskalender/releases/latest/download/installieren-strahlender-baum-windows.cmd)
  herunterladen und doppelklicken. Warnt Windows: **Weitere Informationen**, dann **Trotzdem ausführen**.
- **Linux:**
  [installieren-strahlender-baum-ubuntu.sh](https://github.com/tgd1975/pytree-adventskalender/releases/latest/download/installieren-strahlender-baum-ubuntu.sh)
  herunterladen, mit **Strg+Alt+T** ein Terminal öffnen, `bash Downloads/installieren-strahlender-baum-ubuntu.sh` eintippen und
  **Enter** drücken.

Danach startest du VS Code mit dem Symbol **Der strahlende Baum** auf dem Desktop. Wie es weitergeht, zeigt dir die
Erweiterung. Gibt es im Dezember eine neue Fassung, führst du die Installationsdatei einfach noch einmal aus. Deine
Lösungen und dein Fortschritt bleiben.

Von Hand geht es auch: Die Erweiterung `pytree-strahlender-baum-….vsix` liegt unter
[Releases](https://github.com/tgd1975/pytree-adventskalender/releases) beim neuesten Release „Der strahlende Baum“ bei den **Assets**, dazu braucht
es [VS Code](https://code.visualstudio.com/). Was die Installationsdateien genau tun, steht in ihren ersten Zeilen.

Läuft unter Windows und Linux.

## Den Baum auf das dritte Heft stellen

Ein Baum kann auf jedem Heft der Reihe stehen. Bevor du den ersten Code eingibst: Stecker ziehen, beide Knöpfe
halten und wieder einstecken, bis die Lichterketten abwechselnd blinken. Schalter auf `00100000`, **Bestätigen**.
Jedes Heft behält dabei seinen eigenen Stand. So sieht der Baum aus, wenn er auf dem dritten Heft steht:

<img src="../assets/startbild/strahlender-baum.svg" alt="Startbild: beide Lichterketten, dazu drei rote Lichter: rechts in der dritten Etage, rechts in der vierten und ganz oben an der Spitze." width="264" height="358">

## Der Baum am Bildschirm

Ohne Baum geht es auch: Die Erweiterung gibt es in einer Fassung, die den Baum mitbringt. Er steht in VS Code neben
deinem Programm, mit denselben acht Schaltern und zwei Knöpfen wie der echte. Du stellst den Code des Tages mit der
Maus ein, drückst **Bestätigen**, und er antwortet mit Licht und Ton.

<img src="../assets/baum-am-bildschirm/strahlender-baum.png" alt="Ein Fenster von VS Code: links die Lösungsdatei eines Türchens, rechts der Baum am Bildschirm im Startbild dieses Hefts; darunter Stecker, acht Schalter und die Knöpfe Bestätigen und Note." width="720" height="369">

[pytree-strahlender-baum-simulator.vsix](https://github.com/tgd1975/pytree-adventskalender/releases/latest/download/pytree-strahlender-baum-simulator.vsix) herunterladen, dann in VS Code: **Erweiterungen → … → Aus VSIX installieren** (englisch
**Install from VSIX**). VS Code und Python müssen dafür schon da sein, selbst installiert oder mit einer
Installationsdatei von oben. Hast du die Erweiterung schon, ersetzt diese Fassung sie; deine Lösungen und dein
Fortschritt bleiben. Das Heft liegt als PDF darin, am Tor der Werkstatt öffnet es der Knopf **Das Heft lesen**. Eine
Installationsdatei holt immer die Fassung ohne Baum: Führst du später eine noch einmal aus, installierst du danach
diese Datei neu.

## Ein Blick in Türchen 3 – Jedes Stück weiß sein Licht

So sieht ein Türchen aus: ein Beispiel aus „Was du heute lernst“, darunter der erste Auftrag und daneben, was dein Programm dann ausgibt.

<div class="probe">
<pre>class Stern:&#10;  def __init__(self, farbe):&#10;    self.farbe = farbe&#10;&#10;oben = Stern(<span class="str">"gold"</span>)&#10;print(oben.farbe)</pre>
<div class="zwei"><p>Schreib den Bauplan <code>Kerze</code> mit einem <code>__init__</code>, das <code>licht</code> bekommt. Jede neue Kerze merkt sich ihr Licht in <code>self.licht</code> und ist aus: <code>self.an = False</code>. Bau <code>Kerze(7)</code> und <code>Kerze(15)</code> und gib beide aus:</p><pre class="aus">Kerze 7, an: False&#10;Kerze 15, an: False</pre></div>
</div>

## Zum Weitergeben

Der Flyer zeigt auf einer Seite A4, was der strahlende Baum ist – zum Verschicken oder Ausdrucken.
Die Flyer der anderen Hefte stehen auf der [Startseite](../#flyer-zum-weitergeben).

<div class="flyer flyer-einzeln">
<a class="flyer-karte" href="../flyer/strahlender-baum.pdf" download="flyer-strahlender-baum.pdf">
  <img src="../flyer/strahlender-baum.webp" alt="" width="440" height="622" loading="lazy">
  <span class="flyer-name">Der strahlende Baum</span>
  <span class="flyer-art">PDF · eine Seite A4</span>
</a>
</div>

## Wenn etwas klemmt

Klemmt etwas, ist etwas unklar oder hast du eine Idee, schreib auf GitHub ein
[Issue](https://github.com/tgd1975/pytree-adventskalender/issues/new/choose), so heißen dort die Meldungen.
