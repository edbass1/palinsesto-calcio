/* Contatore visite, senza account e senza chiave.
   Abacus (https://jasoncameron.dev/abacus/) accetta un hit anonimo e restituisce il numero.
   Non ha finestre temporali: una chiave per giorno (da mezzanotte, ora di Roma) più il totale.
   «Ultime 24 ore» = giorno di calendario in corso; «ultima settimana» = 7 giorni;
   «ultimo mese» = 30 giorni. Chiavi: palinsesto-AAAA-MM-GG e palinsesto-totale.
   Per cambiare servizio: BASE, NS, PREFISSO. */
(function (root) {
  "use strict";
  var BASE = "https://abacus.jasoncameron.dev";
  var NS = "edbass1.github.io";
  var PREFISSO = "palinsesto";
  var cfg = { timeout: 4000, riprova: 11000, riprovaErrore: 400, cacheMs: 15 * 60 * 1000, bloccoMs: 20000 };
  var K_GIORNO = "visite-giorno";
  var K_SESSIONE = "visite-sessione";
  var K_CACHE = "visite-cache";
  var K_BLOCCO = "visite-blocco";

  function giornoRoma(data) {
    try {
      var fmt = new Intl.DateTimeFormat("en-CA", {
        timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit"
      });
      var y, m, d;
      if (fmt.formatToParts) {
        fmt.formatToParts(data).forEach(function (p) {
          if (p.type === "year") y = p.value;
          else if (p.type === "month") m = p.value;
          else if (p.type === "day") d = p.value;
        });
        if (y && m && d) {
          if (m.length < 2) m = "0" + m;
          if (d.length < 2) d = "0" + d;
          return y + "-" + m + "-" + d;
        }
      }
      var s = fmt.format(data);
      var mch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
      if (mch) return mch[1] + "-" + mch[2] + "-" + mch[3];
    } catch (e) {}
    return "";
  }

  function sposta(iso, delta) {
    var p = iso.split("-");
    var t = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + delta));
    var mo = t.getUTCMonth() + 1, g = t.getUTCDate();
    return t.getUTCFullYear() + "-" + (mo < 10 ? "0" : "") + mo + "-" + (g < 10 ? "0" : "") + g;
  }

  function numero(n) {
    return typeof n === "number" && n >= 0 && n === n && n !== Infinity;
  }

  function somme(mappa, oggi) {
    var h24 = mappa[oggi] || 0, sett = 0, mese = 0, i, g, n;
    for (i = 0; i < 30; i++) {
      g = sposta(oggi, -i);
      n = mappa[g] || 0;
      mese += n;
      if (i < 7) sett += n;
    }
    return { h24: h24, sett: sett, mese: mese, totale: mappa.totale || 0 };
  }

  function vaContato(s) {
    if (!s || !s.oggi || !s.puoSalvare || s.blocco) return false;
    if (s.giornoSalvato === s.oggi || s.sessioneSalvata === s.oggi) return false;
    return true;
  }

  function cacheValida(c, oggi, ora) {
    if (!c || c.oggi !== oggi || typeof c.t !== "number") return false;
    if (!numero(c.h24) || !numero(c.sett) || !numero(c.mese) || !numero(c.totale)) return false;
    return ora - c.t <= cfg.cacheMs;
  }

  function chiaveGiorno(iso) { return PREFISSO + "-" + iso; }
  function chiaveTotale() { return PREFISSO + "-totale"; }
  function urlDi(azione, chiave) {
    return BASE + "/" + azione + "/" + encodeURIComponent(NS) + "/" + encodeURIComponent(chiave);
  }

  function attesa(ms) {
    return new Promise(function (ok) { setTimeout(ok, ms); });
  }

  /* scrive=true è un hit: si riprova solo sul 429 (non applicato). Un GET si riprova anche se cade. */
  function chiedi(url, scrive, tentativo) {
    tentativo = tentativo || 0;
    if (!root.fetch) return Promise.reject(new Error("fetch"));
    var ctrl = typeof root.AbortController === "function" ? new root.AbortController() : null;
    var timer = setTimeout(function () { try { if (ctrl) ctrl.abort(); } catch (e) {} }, cfg.timeout);
    var opts = { method: "GET", cache: "no-store" };
    if (ctrl) opts.signal = ctrl.signal;
    return root.fetch(url, opts).then(function (r) {
      clearTimeout(timer);
      if (r.status === 404) return 0;
      if (r.status === 429 && tentativo < 1) {
        return attesa(cfg.riprova).then(function () { return chiedi(url, scrive, 1); });
      }
      if (!scrive && r.status >= 500 && tentativo < 1) {
        return attesa(cfg.riprovaErrore).then(function () { return chiedi(url, scrive, 1); });
      }
      if (!r.ok) throw new Error("http");
      return r.json().then(function (j) {
        if (!j || !numero(j.value)) throw new Error("valore");
        return j.value;
      });
    }, function (err) {
      clearTimeout(timer);
      if (!scrive && tentativo < 1) return attesa(cfg.riprovaErrore).then(function () { return chiedi(url, scrive, 1); });
      throw err;
    });
  }

  function leggi(store, k) {
    try { return store.getItem(k); } catch (e) { return null; }
  }
  function scrivi(store, k, v) {
    try { store.setItem(k, v); return true; } catch (e) { return false; }
  }
  function puo(store) {
    try { var t = "visite-prova"; store.setItem(t, "1"); store.removeItem(t); return true; } catch (e) { return false; }
  }

  function fmt(n) {
    try { return n.toLocaleString("it-IT"); } catch (e) { return String(n); }
  }

  function mostra(el, n) {
    if (!numero(n.h24) || !numero(n.sett) || !numero(n.mese) || !numero(n.totale)) return;
    var map = { "24": n.h24, "7": n.sett, "30": n.mese, "t": n.totale };
    ["24", "7", "30", "t"].forEach(function (k) {
      var s = el.querySelector('[data-v="' + k + '"]');
      if (s) s.textContent = fmt(map[k]);
    });
    el.hidden = false;
  }

  function copia(o) {
    var r = {}, k;
    if (!o) return r;
    for (k in o) if (Object.prototype.hasOwnProperty.call(o, k) && numero(o[k])) r[k] = o[k];
    return r;
  }
  function leggiCache() {
    try { return JSON.parse(leggi(root.localStorage, K_CACHE) || "null"); } catch (e) { return null; }
  }
  function salvaCache(n, oggi) {
    scrivi(root.localStorage, K_CACHE, JSON.stringify({
      t: Date.now(), oggi: oggi, h24: n.h24, sett: n.sett, mese: n.mese, totale: n.totale,
      giorni: n.giorni || {}
    }));
  }
  function segna(oggi) {
    scrivi(root.localStorage, K_GIORNO, oggi);
    scrivi(root.sessionStorage, K_SESSIONE, oggi);
  }
  function bloccoAttivo() {
    var ora = Date.now();
    var b = parseInt(leggi(root.localStorage, K_BLOCCO) || leggi(root.sessionStorage, K_BLOCCO) || "", 10);
    return !!b && ora - b < cfg.bloccoMs;
  }
  function mettiBlocco() {
    var v = String(Date.now());
    if (!scrivi(root.localStorage, K_BLOCCO, v)) scrivi(root.sessionStorage, K_BLOCCO, v);
  }

  function stato(oggi) {
    return {
      oggi: oggi,
      giornoSalvato: leggi(root.localStorage, K_GIORNO),
      sessioneSalvata: leggi(root.sessionStorage, K_SESSIONE),
      puoSalvare: puo(root.localStorage) || puo(root.sessionStorage),
      blocco: bloccoAttivo()
    };
  }

  /* I giorni già passati non cambiano più. Al massimo 30 richieste per finestra di 10 secondi:
     quelle in più (di solito il giorno più vecchio) arrivano subito dopo e correggono il mese. */
  function finestre(oggi, noto, giorniCache, giaRichieste) {
    var giorni = [], i, budget = Math.max(1, 30 - (giaRichieste || 0));
    for (i = 0; i < 30; i++) giorni.push(sposta(oggi, -i));
    var fissi = {}, coda = [];
    if (noto) fissi.totale = noto.totale; else coda.push("totale");
    giorni.forEach(function (g, idx) {
      if (idx === 0 && noto) fissi[g] = noto.h24;
      else if (idx > 0 && giorniCache && numero(giorniCache[g])) fissi[g] = giorniCache[g];
      else coda.push(g);
    });
    var subito = coda.slice(0, budget), dopo = coda.slice(budget);
    var rimandati = {};
    dopo.forEach(function (k) { rimandati[k] = true; });
    function valore(extra, k) {
      if (extra && extra[k] !== undefined) return extra[k];
      if (fissi[k] !== undefined) return fissi[k];
      return 0;
    }
    function applica(extra) {
      var mappa = { totale: valore(extra, "totale") }, salvati = {};
      giorni.forEach(function (g) {
        mappa[g] = valore(extra, g);
        if (!rimandati[g] || (extra && extra[g] !== undefined)) salvati[g] = mappa[g];
      });
      var s = somme(mappa, oggi);
      s.giorni = salvati;
      if (!numero(s.h24) || !numero(s.sett) || !numero(s.mese) || !numero(s.totale)) throw new Error("somme");
      return s;
    }
    function scarica(lista) {
      return Promise.all(lista.map(function (k) {
        var url = k === "totale" ? urlDi("get", chiaveTotale()) : urlDi("get", chiaveGiorno(k));
        return chiedi(url, false).then(function (n) { return { k: k, n: n }; });
      })).then(function (coppie) {
        var extra = {};
        coppie.forEach(function (c) { extra[c.k] = c.n; fissi[c.k] = c.n; rimandati[c.k] = false; });
        return extra;
      });
    }
    return scarica(subito).then(function (extra) {
      var s = applica(extra);
      if (dopo.length) s.dopo = scarica(dopo).then(function () { return applica(null); });
      return s;
    });
  }

  function avvia() {
    var el = root.document.getElementById("visite");
    if (!el || !root.fetch) return;
    var oggi = giornoRoma(new Date());
    if (!oggi) return;
    var cache = leggiCache();
    var fresca = cacheValida(cache, oggi, Date.now());
    var giorniCache = cache && cache.giorni;
    if (cache && cache.oggi === oggi && numero(cache.h24)) mostra(el, cache);
    var contare = vaContato(stato(oggi));
    if (contare) mettiBlocco();
    var lavoro;
    if (!contare && fresca) return;
    if (contare && fresca) {
      lavoro = Promise.all([
        chiedi(urlDi("hit", chiaveTotale()), true),
        chiedi(urlDi("hit", chiaveGiorno(oggi)), true)
      ]).then(function () {
        segna(oggi);
        var giorni = copia(giorniCache);
        giorni[oggi] = cache.h24 + 1;
        return { h24: cache.h24 + 1, sett: cache.sett + 1, mese: cache.mese + 1, totale: cache.totale + 1, giorni: giorni };
      });
    } else if (contare) {
      lavoro = Promise.all([
        chiedi(urlDi("hit", chiaveTotale()), true),
        chiedi(urlDi("hit", chiaveGiorno(oggi)), true)
      ]).then(function (vals) {
        segna(oggi);
        return finestre(oggi, { h24: vals[1], totale: vals[0] }, giorniCache, 2);
      });
    } else {
      lavoro = finestre(oggi, null, giorniCache, 0);
    }
    function pubblicato(n) {
      mostra(el, n);
      salvaCache(n, oggi);
      if (n.dopo) n.dopo.then(pubblicato).catch(function () {});
    }
    lavoro.then(pubblicato).catch(function () {});
  }

  if (root.document && root.document.getElementById) {
    try { avvia(); } catch (e) {}
  }

  var api = {
    cfg: cfg, giornoRoma: giornoRoma, sposta: sposta, somme: somme,
    vaContato: vaContato, cacheValida: cacheValida, chiedi: chiedi,
    chiaveGiorno: chiaveGiorno, chiaveTotale: chiaveTotale, urlDi: urlDi
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

if (typeof module !== "undefined" && require.main === module) {
  var assert = require("assert");
  var V = module.exports;
  var chiamate = 0;
  var passo = "";
  function ko(err) { console.error(err); process.exit(1); }
  function rispondo(stato, valore) {
    return Promise.resolve({
      status: stato, ok: stato >= 200 && stato < 300,
      json: function () { return Promise.resolve({ value: valore }); }
    });
  }
  try {
    assert.strictEqual(V.giornoRoma(new Date("2026-10-25T23:30:00Z")), "2026-10-26");
    assert.strictEqual(V.giornoRoma(new Date("2026-10-25T22:30:00Z")), "2026-10-25");
    assert.strictEqual(V.sposta("2026-10-25", -1), "2026-10-24");
    assert.strictEqual(V.sposta("2026-03-01", -1), "2026-02-28");
    assert.strictEqual(V.sposta("2026-01-01", -1), "2025-12-31");
    assert.strictEqual(V.sposta("2024-03-01", -1), "2024-02-29");
    var oggi = "2026-10-25";
    var m = { totale: 100 };
    m[oggi] = 2;
    m[V.sposta(oggi, -1)] = 3;
    m[V.sposta(oggi, -6)] = 1;
    m[V.sposta(oggi, -7)] = 4;
    m[V.sposta(oggi, -29)] = 5;
    m[V.sposta(oggi, -30)] = 9;
    var s = V.somme(m, oggi);
    assert.strictEqual(s.h24, 2);
    assert.strictEqual(s.sett, 6);
    assert.strictEqual(s.mese, 15);
    assert.strictEqual(s.totale, 100);
    assert.strictEqual(V.vaContato({ oggi: oggi, giornoSalvato: null, sessioneSalvata: null, puoSalvare: true, blocco: false }), true);
    assert.strictEqual(V.vaContato({ oggi: oggi, giornoSalvato: oggi, sessioneSalvata: null, puoSalvare: true, blocco: false }), false);
    assert.strictEqual(V.vaContato({ oggi: oggi, giornoSalvato: "2026-10-24", sessioneSalvata: oggi, puoSalvare: true, blocco: false }), false);
    assert.strictEqual(V.vaContato({ oggi: oggi, giornoSalvato: null, sessioneSalvata: null, puoSalvare: false, blocco: false }), false);
    assert.strictEqual(V.vaContato({ oggi: oggi, giornoSalvato: "2026-10-24", sessioneSalvata: null, puoSalvare: true, blocco: true }), false);
    assert.strictEqual(V.vaContato({ oggi: "", giornoSalvato: null, sessioneSalvata: null, puoSalvare: true, blocco: false }), false);
    var ora = 1000000;
    assert.strictEqual(V.cacheValida({ t: ora - 1000, oggi: oggi, h24: 1, sett: 1, mese: 1, totale: 1 }, oggi, ora), true);
    assert.strictEqual(V.cacheValida({ t: ora - 16 * 60 * 1000, oggi: oggi, h24: 1, sett: 1, mese: 1, totale: 1 }, oggi, ora), false);
    assert.strictEqual(V.cacheValida({ t: ora - 1000, oggi: "2026-10-24", h24: 1, sett: 1, mese: 1, totale: 1 }, oggi, ora), false);
  } catch (err) { ko(err); }
  V.cfg.riprova = 0;
  V.cfg.riprovaErrore = 0;
  V.cfg.timeout = 50;
  passo = "404";
  globalThis.fetch = function () { return rispondo(404, 0); };
  V.chiedi("https://esempio/manca", false).then(function (n) {
    assert.strictEqual(n, 0);
    chiamate = 0;
    passo = "429";
    globalThis.fetch = function () {
      chiamate += 1;
      if (chiamate === 1) return rispondo(429, 0);
      return rispondo(200, 4);
    };
    return V.chiedi("https://esempio/hit", true);
  }).then(function (n) {
    assert.strictEqual(passo, "429");
    assert.strictEqual(n, 4);
    assert.strictEqual(chiamate, 2);
    chiamate = 0;
    passo = "rete";
    globalThis.fetch = function () {
      chiamate += 1;
      return Promise.reject(new Error("rete"));
    };
    return V.chiedi("https://esempio/hit", true);
  }).then(function () {
    ko(new Error("l'hit non doveva riuscire"));
  }, function (err) {
    if (passo !== "rete") ko(err);
    try { assert.strictEqual(chiamate, 1); } catch (e) { ko(e); }
    chiamate = 0;
    passo = "lento";
    globalThis.fetch = function (url, opts) {
      chiamate += 1;
      return new Promise(function (resolve, reject) {
        if (opts && opts.signal) opts.signal.addEventListener("abort", function () { reject(new Error("abort")); });
      });
    };
    return V.chiedi("https://esempio/lento", false);
  }).then(function () {
    ko(new Error("la lettura lenta doveva fallire"));
  }, function (err) {
    if (passo !== "lento") ko(err);
    try { assert.ok(chiamate >= 1); } catch (e) { ko(e); }
    console.log("visite ok");
  });
}
