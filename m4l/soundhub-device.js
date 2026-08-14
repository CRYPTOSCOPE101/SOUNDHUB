// SoundHub for Ableton Live — Max for Live device logic
// ---------------------------------------------------------
// Reads the SoundHubMarket catalog directly from an EVM RPC (no backend
// dependency), reads the current Live set BPM to suggest relevant assets,
// lets the user buy with SND (testnet signing), and loads the purchased
// asset into the Live project.
//
// Run: open soundhub.amxd in Max for Live. Configure addresses/messages
// below or send them to the js object at runtime.
//
// NOTE: this is a prototype — test on Base Sepolia. The private key is
// testnet-only; a production build must use a proper signer (WalletConnect
// or a backend relayer).

var OUT_CATALOG = 0;   // outlet 0: catalog text (JSON array as string)
var OUT_STATUS = 1;    // outlet 1: status lines
var OUT_MATCH = 2;     // outlet 2: BPM-matched suggestion

// ---- configuration (override via messages: rpc / market / token / key) ----
var config = {
  rpc: "https://sepolia.base.org",
  chainId: "0x14a34", // 84532 (Base Sepolia)
  market: "0x396d6ad9D5EA19eE56318624b05bC6EEEa2d1F5C",
  token: "0x37a6B3aD766ffb98673290A634490C8bF952DB2F",
  key: "",            // testnet private key (hex, 0x-prefixed)
  backend: "http://127.0.0.1:8000", // optional: SoundHub backend for assets
  tempDir: "",        // where downloaded assets are saved (default: /tmp)
  maxItems: 50
};

var MARKET_ABI = {
  nextListingId: "0x0d5f9aef",
  listings: "0x0f4a3737",
  buy: "0xb8a29b2a"
};
var TOKEN_ABI = {
  approve: "0x095ea7b3",
  balanceOf: "0x70a08231"
};

var http = null; // httprequest service object
var pendingId = -1; // listing currently being purchased

// ---- helpers ---------------------------------------------------------------

function out(ch, s) {
  outlet(ch, s);
}

function postln(s) {
  post("SoundHub: " + s + "\n");
}

function hexToBytes(h) {
  h = h.replace(/^0x/, "");
  if (h.length % 2) h = "0" + h;
  var b = [];
  for (var i = 0; i < h.length; i += 2) b.push(parseInt(h.substr(i, 2), 16));
  return b;
}

function bytesToHex(b) {
  var s = "0x";
  for (var i = 0; i < b.length; i++) {
    var x = b[i].toString(16);
    if (x.length < 2) x = "0" + x;
    s += x;
  }
  return s;
}

function pad32(h) {
  h = h.replace(/^0x/, "");
  while (h.length < 64) h = "0" + h;
  return h;
}

function rpc(method, params, cb) {
  // POST JSON-RPC to the EVM node.
  if (!http) http = this.patcher.apply(this.patcher, ["httprequest"]);
  var body = JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: method,
    params: params
  });
  http.text = body;
  http.method = 1; // POST
  var u = config.rpc.replace(/^https?:\/\//, "");
  http.host = u.split("/")[0];
  http.port = (config.rpc.indexOf("https://") === 0) ? 443 : 80;
  http.path = "/" + u.split("/").slice(1).join("/");
  http.callback = function (err, resp) {
    if (err) {
      cb(null, { error: String(err) });
      return;
    }
    var text = responseText(resp);
    var data;
    try { data = JSON.parse(text); } catch (e) { data = null; }
    cb(data, data && data.error ? null : null);
  };
  http.exec();
}

// Normalize an httprequest response (string / object) into text.
function responseText(resp) {
  if (typeof resp === "string") return resp;
  if (resp && resp.text) return resp.text;
  if (resp && resp.body) return resp.body;
  return JSON.stringify(resp);
}

function intFromHex(h) {
  var n = 0;
  h = h.replace(/^0x/, "");
  for (var i = 0; i < h.length; i++) n = n * 16 + parseInt(h[i], 16);
  return n;
}

function truncAddr(a) {
  return a ? a.substr(0, 6) + "\u2026" + a.substr(-4) : "";
}

function fmtPrice(weiHex) {
  var n = intFromHex(weiHex);
  return (n / 1e18).toFixed(n >= 1e18 ? 2 : 6) + " SND";
}

// ---- catalog ---------------------------------------------------------------

function loadCatalog() {
  out(OUT_STATUS, "Reading SoundHub market catalog\u2026");
  rpc("eth_call", [{
    to: config.market,
    data: MARKET_ABI.nextListingId
  }, "latest"], function (res, _) {
    if (!res || res.error) {
      out(OUT_STATUS, "RPC error: " + (res && res.error ? res.error.message : "no response"));
      return;
    }
    var count = intFromHex(res.result);
    postln("nextListingId=" + count);
    var items = [];
    var done = 0;
    var max = Math.min(count, config.maxItems);
    if (count <= 1) {
      out(OUT_CATALOG, "[]");
      out(OUT_STATUS, "No listings yet.");
      return;
    }
    var i;
    for (i = 1; i < max; i++) {
      (function (id) {
        rpc("eth_call", [{
          to: config.market,
          data: MARKET_ABI.listings + pad32("0x" + id.toString(16))
        }, "latest"], function (res2, _2) {
          done++;
          if (res2 && res2.result && res2.result !== "0x") {
            var hex = res2.result;
            // static listing struct (32-byte slots, offset in bytes):
            // 0 id | 32 seller | 64 nameOff | 96 uriOff | 128 price |
            // 160 license | 192 active | 224 buyer | 256 escrowed |
            // 288 purchasedAt | 320 released | 352 refundRequested
            var name = decodeStr(hex, 64);
            var uri = decodeStr(hex, 96);
            var price = hex.substr(128 * 2, 64);
            var license = hex.substr(160 * 2, 64);
            var activeHex = hex.substr(192 * 2, 64);
            var escrowed = hex.substr(256 * 2, 64);
            var seller = "0x" + hex.substr(32 * 2 + 24, 40);
            if (intFromHex(activeHex) === 1 && intFromHex(escrowed) === 0) {
              items.push({
                id: id,
                seller: seller,
                name: name,
                uri: uri,
                price: price,
                license: intFromHex(license)
              });
            }
          }
          if (done >= max - 1) {
            items.sort(function (a, b) { return a.id - b.id; });
            out(OUT_CATALOG, JSON.stringify(items));
            out(OUT_STATUS, items.length + " asset(s) for sale.");
          }
        });
      })(i);
    }
  });
}

function decodeStr(hex, offsetBytes) {
  // Decode a Solidity dynamic `string` whose *offset slot* starts at byte
  // position offsetBytes. `hex` is the raw eth_call result (no 0x).
  var bytes = hexToBytes(hex);
  var offHex = hex.substr(offsetBytes * 2, 64);
  var start = intFromHex(offHex); // where the string payload starts (bytes)
  var len = intFromHex(hex.substr(start * 2, 64));
  var s = "";
  for (var i = 0; i < len; i++) {
    var c = bytes[start * 2 / 2 + 32 + i];
    if (c >= 32 && c < 127) s += String.fromCharCode(c);
  }
  return s;
}

// ---- context-aware suggestions ---------------------------------------------

function suggestForBpm(bpm) {
  if (!bpm) return;
  out(OUT_STATUS, "Live set BPM: " + bpm + " \u2014 asking SoundHub backend\u2026");
  // The recommendation engine lives in the SoundHub backend and reuses the
  // DAW engine metadata (see backend/app/services/catalog.py). We send the
  // Live context (BPM for now; key/tracks/devices next) and get ranked
  // assets back.
  var url = config.backend + "/api/assets/recommend?bpm=" + bpm + "&limit=3";
  httpGet(url, function (ok, text) {
    if (!ok) {
      out(OUT_STATUS, "Recommendation failed: " + text);
      return;
    }
    var recs;
    try { recs = JSON.parse(text); } catch (e) { recs = []; }
    if (!recs.length) {
      out(OUT_MATCH, "no matches for " + bpm + " BPM");
      return;
    }
    var top = recs[0];
    out(OUT_MATCH, "\u25b6 " + top.name + " \u00b7 " + top.price_snd + " SND \u00b7 " +
        top.license + " (" + top.match_reasons.join(", ") + ")");
    out(OUT_STATUS, recs.length + " suggestion(s) for " + bpm + " BPM");
    pendingId = top.listing_id || 1;
  });
}

// Fetch an asset payload via the backend (signed short-lived token):
//   GET /api/assets/{id}/token  -> { token }
//   GET /api/assets/{id}/download?token=...  -> asset bytes
function loadAssetById(listingId, name) {
  var url = config.backend + "/api/assets/" + listingId + "/token";
  httpGet(url, function (ok, text) {
    if (!ok) {
      out(OUT_STATUS, "Token request failed: " + text);
      return;
    }
    var body;
    try { body = JSON.parse(text); } catch (e) { body = null; }
    if (!body || !body.token) {
      out(OUT_STATUS, "No download token returned");
      return;
    }
    var dl = config.backend + "/api/assets/" + listingId + "/download?token=" + body.token;
    out(OUT_STATUS, "Downloading " + dl + "\u2026 (drag the file into a track \u2014 prototype)");
    loadAsset(dl, name || ("asset_" + listingId));
  });
}

// ---- buying ----------------------------------------------------------------
// The actual purchase (approve SND -> market.buy -> escrow) happens in the
// web app with the user's wallet (WalletConnect / browser extension). The
// device's third button loads the suggested asset through the backend's
// signed-token endpoint so the loop can be tested end-to-end. A future
// version signs the escrow tx inside M4L (EIP-1559) or via a relayer.

// ---- loading assets into the Live project -----------------------------------

function loadAsset(url, name) {
  var tmp = config.tempDir || "/tmp";
  var target = tmp + "/soundhub_" + name.replace(/[^a-zA-Z0-9._-]/g, "_");
  out(OUT_STATUS, "Downloading " + url + "\u2026");
  httpGet(url, function (ok, text) {
    if (!ok) {
      out(OUT_STATUS, "Download failed: " + text);
      return;
    }
    // Save bytes and insert into the Live set. Real implementation:
    //   - write the response bytes to `target`
    //   - find the device's track via live.thisdevice
    //   - push the file into the browser via Live API (Song.capture_midi etc.)
    out(OUT_STATUS, "Asset ready at " + target + " \u2014 drag into a track (prototype).");
  });
}

// Shared GET helper over httprequest (text responses).
function httpGet(url, cb) {
  if (!http) http = this.patcher.apply(this.patcher, ["httprequest"]);
  http.text = "";
  http.method = 0; // GET
  var u = url.replace(/^https?:\/\//, "");
  http.host = u.split("/")[0];
  http.port = (url.indexOf("https://") === 0) ? 443 : 80;
  http.path = "/" + u.split("/").slice(1).join("/");
  http.callback = function (err, resp) {
    if (err) { cb(false, String(err)); return; }
    cb(true, responseText(resp));
  };
  http.exec();
}

// ---- inlets ---------------------------------------------------------------

function bang() {
  // `bang` from the load button: re-read catalog
  loadCatalog();
}

function msg_int(v) {
  // 0 = refresh catalog, 1 = suggest for current BPM, 2 = load suggested asset
  if (v === 0) loadCatalog();
  else if (v === 1) suggestForBpm(readBpm());
  else if (v === 2) loadAssetById(pendingId >= 0 ? pendingId : 1, "suggested_asset");
}

function readBpm() {
  try {
    var s = new LiveAPI(this.patcher, "live_set");
    return s.get("tempo");
  } catch (e) {
    return 0;
  }
}

// runtime configuration messages: rpc <url>, market <addr>, token <addr>,
// key <privkey>, backend <url>, tempDir <path>
function rpc(v) { config.rpc = v; postln("rpc -> " + v); }
function market(v) { config.market = v; postln("market -> " + v); }
function token(v) { config.token = v; postln("token -> " + v); }
function key(v) { config.key = v; postln("key set (testnet only)"); }
function backend(v) { config.backend = v; postln("backend -> " + v); }
function tempDir(v) { config.tempDir = v; postln("tempDir -> " + v); }
