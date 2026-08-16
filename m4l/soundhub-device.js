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
var OUT_MATCH = 2;     // outlet 2: BPM-matched suggestion / push result

var OUT_PUSH = 3;      // outlet 3: push result (JSON contract string)

// ---- configuration (override via messages: rpc / market / token / key) ----
var config = {
  rpc: "https://sepolia.base.org",
  chainId: "0x14a34", // 84532 (Base Sepolia)
  market: "0x396d6ad9D5EA19eE56318624b05bC6EEEa2d1F5C",
  token: "0x37a6B3aD766ffb98673290A634490C8bF952DB2F",
  key: "",            // testnet private key (hex, 0x-prefixed)
  backend: "http://127.0.0.1:8000", // SoundHub backend for assets/recommend
  bridge: "http://127.0.0.1:8765", // local `snd serve` bridge for the push button
  libraryDir: "",     // Ableton User Library (default: ~/Music/Ableton/User Library)
  maxItems: 50,
  pushProject: "",    // project name for push (default: current Live set name)
  pushBranch: "main", // branch to commit the push to
  pushMessage: ""     // commit message (default: "snd push")
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

// Fetch an asset via the backend and import it into the Live User Library:
//   1. GET /api/assets/{id}/token          -> { token, filename, format, ... }
//   2. GET /api/assets/{id}/download64     -> { data: <base64>, ... }
//   3. decode base64 -> write bytes to <libraryDir>/SoundHub/<filename>
//   4. refresh Live's file browser so the file shows up
function loadAssetById(listingId, name) {
  var url = config.backend + "/api/assets/" + listingId + "/token";
  httpGet(url, function (ok, text) {
    if (!ok) {
      out(OUT_STATUS, "Token request failed: " + text);
      return;
    }
    var meta;
    try { meta = JSON.parse(text); } catch (e) { meta = null; }
    if (!meta || !meta.token) {
      out(OUT_STATUS, "No download token returned");
      return;
    }
    var dl = config.backend + "/api/assets/" + listingId + "/download64?token=" + meta.token;
    out(OUT_STATUS, "Importing \"" + (meta.name || ("asset #" + listingId)) + "\"\u2026");
    httpGet(dl, function (ok2, text2) {
      if (!ok2) {
        out(OUT_STATUS, "Import failed: " + text2);
        return;
      }
      var payload;
      try { payload = JSON.parse(text2); } catch (e) { payload = null; }
      if (!payload || !payload.data) {
        out(OUT_STATUS, "Import failed: no payload");
        return;
      }
      var bytes = base64ToBytes(payload.data);
      var filename = (payload.filename || ("asset_" + listingId)).replace(/[^a-zA-Z0-9._-]/g, "_");
      var path = (config.libraryDir || "~/Music/Ableton/User Library") + "/SoundHub/" + filename;
      writeBytes(path, bytes);
      refreshBrowser();
      out(OUT_STATUS, "Saved " + path + " \u2014 open the Live browser (F5 if needed), SoundHub folder.");
    });
  });
}

// Decode a base64 string into an array of byte values (0-255).
function base64ToBytes(b64) {
  var chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  var lut = {};
  for (var i = 0; i < 64; i++) lut[chars.charAt(i)] = i;
  b64 = b64.replace(/[^A-Za-z0-9+/=]/g, "");
  var out = [];
  var buf = 0, bits = 0;
  for (var j = 0; j < b64.length; j++) {
    if (b64.charAt(j) === "=") break;
    buf = (buf << 6) | lut[b64.charAt(j)];
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out.push((buf >> bits) & 0xff);
    }
  }
  return out;
}

// Write bytes to disk via the Max `file` object (allowed in M4L; `shell` is
// blocked inside Live). The filebox is created by the patch.
function writeBytes(path, bytes) {
  var fb;
  try { fb = this.patcher.getnamed("filebox"); } catch (e) { fb = null; }
  if (!fb) {
    out(OUT_STATUS, "filebox not found in patch \u2014 add a `file @name filebox` object.");
    return;
  }
  fb.message("open", path, "write");
  var k;
  for (k = 0; k < bytes.length; k++) fb.message("writebyte", bytes[k]);
  fb.message("close");
}

// Ask Live's file browser to refresh so the new file shows up. `refresh` is
// best-effort; fall back to telling the user to hit F5.
function refreshBrowser() {
  var bb;
  try { bb = this.patcher.getnamed("browserbox"); } catch (e) { bb = null; }
  if (bb) {
    try { bb.message("refresh"); } catch (e) { /* browser may not support it */ }
  }
}

// ---- buying ----------------------------------------------------------------
// The actual purchase (approve SND -> market.buy -> escrow) happens in the
// web app with the user's wallet (WalletConnect / browser extension). The
// device's third button loads the suggested asset through the backend's
// signed-token endpoint so the loop can be tested end-to-end. A future
// version signs the escrow tx inside M4L (EIP-1559) or via a relayer.

// ---- loading assets into the Live project -----------------------------------

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

// ---- push current export (via the local snd bridge) ------------------------
// M4L can't run `shell` (blocked inside Live) and httprequest mangles binary
// multipart, so the button posts a tiny JSON payload to the local `snd serve`
// bridge, which runs the full snd push pipeline (preflight -> atomic upload
// -> review session) and returns the stable contract.

function pushCurrentExport() {
  var path = currentSongPath();
  if (!path) {
    out(OUT_STATUS, "Push failed: save the Live set first (no .als path yet).");
    return;
  }
  var payload = {
    target: path,
    project: config.pushProject || songName(),
    branch: config.pushBranch || "main",
    message: config.pushMessage || "snd push"
  };
  out(OUT_STATUS, "Pushing “" + payload.project + "” to SoundHub…");
  httpPostJson(config.bridge + "/push", payload, function (ok, text) {
    if (!ok) {
      out(OUT_STATUS, "Push failed (bridge unreachable? run `snd serve`): " + text);
      return;
    }
    var res;
    try { res = JSON.parse(text); } catch (e) { res = null; }
    if (!res || !res.ok) {
      out(OUT_STATUS, "Push failed: " + (res && res.error ? res.error : text));
      out(OUT_PUSH, text);
      return;
    }
    out(OUT_STATUS, "✓ pushed commit #" + res.commit_id + " · " + res.file_count + " file(s)");
    out(OUT_MATCH, res.review_url ? "review: " + res.review_url : "fast push (no review — add master audio next time)");
    out(OUT_PUSH, JSON.stringify(res));
  });
}

// POST a JSON body to a URL (text responses).
function httpPostJson(url, obj, cb) {
  if (!http) http = this.patcher.apply(this.patcher, ["httprequest"]);
  http.text = JSON.stringify(obj);
  http.method = 1; // POST
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

function currentSongPath() {
  try {
    var s = new LiveAPI(this.patcher, "live_set");
    var p = s.get("current_song_path");
    return (typeof p === "string" && p.length > 0) ? p : "";
  } catch (e) {
    return "";
  }
}

function songName() {
  try {
    var s = new LiveAPI(this.patcher, "live_set");
    var n = s.get("current_song_name");
    return (typeof n === "string" && n.length > 0) ? n : "Live set";
  } catch (e) {
    return "Live set";
  }
}

// ---- inlets ---------------------------------------------------------------

function bang() {
  // `bang` from the load button: re-read catalog
  loadCatalog();
}

function msg_int(v) {
  // 0 = refresh catalog, 1 = suggest for current BPM, 2 = load suggested asset,
  // 3 = push current export
  if (v === 0) loadCatalog();
  else if (v === 1) suggestForBpm(readBpm());
  else if (v === 2) loadAssetById(pendingId >= 0 ? pendingId : 1, "suggested_asset");
  else if (v === 3) pushCurrentExport();
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
// key <privkey>, backend <url>, libraryDir <path>, bridge <url>,
// pushProject <name>, pushBranch <name>, pushMessage <text>
function rpc(v) { config.rpc = v; postln("rpc -> " + v); }
function market(v) { config.market = v; postln("market -> " + v); }
function token(v) { config.token = v; postln("token -> " + v); }
function key(v) { config.key = v; postln("key set (testnet only)"); }
function backend(v) { config.backend = v; postln("backend -> " + v); }
function libraryDir(v) { config.libraryDir = v; postln("libraryDir -> " + v); }
function bridge(v) { config.bridge = v; postln("bridge -> " + v); }
function pushProject(v) { config.pushProject = v; postln("pushProject -> " + v); }
function pushBranch(v) { config.pushBranch = v; postln("pushBranch -> " + v); }
function pushMessage(v) { config.pushMessage = v; postln("pushMessage -> " + v); }
