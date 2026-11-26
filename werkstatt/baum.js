// Baum-Werkstatt – die Leitung zum Baum: Web Serial und MicroPythons raw REPL (Konzept
// docs/concepts/erledigt/baum_werkstatt.md, „Aufspielen aus dem Browser auf den Baum“). Was dem Baum geschickt wird und
// was er antworten muss, bestimmt werkstatt.py (aufspielen_schritte, baum_lage); hier nur der Weg dorthin.
//
// raw REPL wie mpremote: Strg-C unterbricht, Strg-A schaltet in den raw REPL (kein Soft-Reset – der startete main.py
// neu, und im Wartungsmodus hielte niemand mehr die Note). Ein Befehl geht als „raw paste“ mit Flusssteuerung des
// Baums; versteht er das nicht, in Stücken von 256 Byte mit kurzer Pause. Antwort: Ausgabe \x04 Fehlerausgabe \x04 >.
"use strict";

const BAUM_USB = [{ usbVendorId: 0x2e8a }];        // Raspberry Pi – MicroPython auf dem RP2350 meldet sich so
const RAW_REPL = "raw REPL; CTRL-B to exit\r\n>";

class BaumFehler extends Error {
  // art: abgelehnt (keinen Baum gewählt), oeffnen (Port lässt sich nicht öffnen), abgebrochen (Kabel, Baum weg),
  // stumm (keine Antwort), baum (der Baum meldet einen Fehler)
  constructor(art, text) { super(text); this.art = art; }
}

class BaumLeitung {
  static moeglich() { return "serial" in navigator; }

  constructor() {
    this.port = null; this.leser = null; this.schreiber = null;
    this.puffer = new Uint8Array(0); this.verloren = null; this.wecker = null; this.paste = null;
  }

  async verbinden() {
    try {
      this.port = await navigator.serial.requestPort({ filters: BAUM_USB });
    } catch (e) {
      throw new BaumFehler("abgelehnt", "Kein Baum gewählt.");
    }
    try {
      await this.port.open({ baudRate: 115200 });
    } catch (e) {
      throw new BaumFehler("oeffnen", e.message);
    }
    this.schreiber = this.port.writable.getWriter();
    this.leser = this.port.readable.getReader();
    this._lesen();
    await this._schreibe("\r\x03\x03");
    await this._pause(300);
    this.puffer = new Uint8Array(0);
    await this._schreibe("\r\x01");
    await this._bis(RAW_REPL, 5000);
  }

  async ausfuehren(code, ms = 15000) {
    const daten = new TextEncoder().encode(code);
    if (this.paste !== false) {
      await this._schreibe(new Uint8Array([5, 65, 1]));
      const a = await this._nimm(2, 3000);
      if (a[0] === 82 && a[1] === 1) { this.paste = true; return this._paste(daten, ms); }
      this.paste = false;
      if (!(a[0] === 82 && a[1] === 0)) await this._bis(">", 3000);   // altes MicroPython: zurück zum Prompt
    }
    for (let i = 0; i < daten.length; i += 256) {
      await this._schreibe(daten.subarray(i, i + 256));
      await this._pause(10);
    }
    await this._schreibe(new Uint8Array([4]));
    const ok = new TextDecoder().decode(await this._nimm(2, 3000));
    if (ok !== "OK") throw new BaumFehler("baum", "Der Baum hat den Befehl nicht angenommen: " + ok);
    return this._antwort(ms);
  }

  async trennen() {
    try { if (this.schreiber && !this.verloren) await this._schreibe("\x02"); } catch { /* schon weg */ }
    try { if (this.leser) { await this.leser.cancel(); this.leser.releaseLock(); } } catch { /* schon weg */ }
    try { if (this.schreiber) this.schreiber.releaseLock(); } catch { /* schon weg */ }
    try { if (this.port) await this.port.close(); } catch { /* schon weg */ }
    this.port = null;
  }

  // --- raw paste und Antwort ---

  async _paste(daten, ms) {
    const f = await this._nimm(2, 3000);
    const fenster = f[0] | (f[1] << 8);
    let rest = fenster;
    for (let i = 0; i < daten.length;) {
      while (this.puffer.length > 0 || rest === 0) {
        const b = (await this._nimm(1, 5000))[0];
        if (b === 1) rest += fenster;
        else if (b === 4) { await this._schreibe(new Uint8Array([4])); throw new BaumFehler("baum", "Der Baum hat das Kopieren abgebrochen."); }
        else throw new BaumFehler("baum", "Unerwartete Antwort des Baums beim Kopieren: " + b);
      }
      const n = Math.min(rest, daten.length - i);
      await this._schreibe(daten.subarray(i, i + n));
      i += n; rest -= n;
    }
    await this._schreibe(new Uint8Array([4]));
    await this._bis("\x04", 5000);
    return this._antwort(ms);
  }

  async _antwort(ms) {
    const dek = new TextDecoder();
    const aus = dek.decode(await this._bis("\x04", ms));
    const fehler = dek.decode(await this._bis("\x04", ms));
    await this._bis(">", ms);
    return { aus: aus.replace(/\r\n/g, "\n").trim(), fehler: fehler.replace(/\r\n/g, "\n").trim() };
  }

  // --- Lesen und Schreiben ---

  async _lesen() {
    try {
      for (;;) {
        const { value, done } = await this.leser.read();
        if (done) break;
        const neu = new Uint8Array(this.puffer.length + value.length);
        neu.set(this.puffer); neu.set(value, this.puffer.length);
        this.puffer = neu;
        if (this.wecker) this.wecker();
      }
    } catch (e) { this.verloren = e; }
    this.verloren = this.verloren || new Error("Verbindung geschlossen");
    if (this.wecker) this.wecker();
  }

  async _schreibe(daten) {
    if (typeof daten === "string") daten = new TextEncoder().encode(daten);
    try { await this.schreiber.write(daten); }
    catch (e) { this.verloren = this.verloren || e; throw new BaumFehler("abgebrochen", "Die Verbindung zum Baum ist abgebrochen."); }
  }

  _pause(ms) { return new Promise((r) => setTimeout(r, ms)); }

  async _warte(bedingung, ms) {
    const ende = performance.now() + ms;
    for (;;) {
      const r = bedingung();
      if (r !== null) return r;
      if (this.verloren) throw new BaumFehler("abgebrochen", "Die Verbindung zum Baum ist abgebrochen.");
      const bleibt = ende - performance.now();
      if (bleibt <= 0) throw new BaumFehler("stumm", "Der Baum antwortet nicht.");
      await new Promise((r2) => { this.wecker = r2; setTimeout(r2, Math.min(bleibt, 100)); });
      this.wecker = null;
    }
  }

  _nimm(n, ms) {
    return this._warte(() => {
      if (this.puffer.length < n) return null;
      const t = this.puffer.slice(0, n); this.puffer = this.puffer.slice(n); return t;
    }, ms);
  }

  _bis(muster, ms) {
    const m = new TextEncoder().encode(muster);
    return this._warte(() => {
      const p = this.puffer;
      for (let i = 0; i + m.length <= p.length; i++) {
        let gleich = true;
        for (let j = 0; j < m.length; j++) if (p[i + j] !== m[j]) { gleich = false; break; }
        if (gleich) { const t = p.slice(0, i); this.puffer = p.slice(i + m.length); return t; }
      }
      return null;
    }, ms);
  }
}
