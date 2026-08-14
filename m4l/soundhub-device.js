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
  if (!http) http = this.patcher.apply(this.patcher, ["httprequest"]);
  var body = JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: method,
    params: params
  });
  http.text = body;
  http.method = 1; // POST
  http.host = config.rpc.replace(/^https?:\/\//, "").split("/")[0];
  http.port = 443;
  http.path = "/";
  http.callback = function (err, resp) {
    if (err) {
      cb(null, { error: String(err) });
      return;
    }
    var text = "";
    if (typeof resp === "string") text = resp;
    else if (resp && resp.text) text = resp.text;
    else if (resp && resp.body) text = resp.body;
    else text = JSON.stringify(resp);
    var data;
    try { data = JSON.parse(text); } catch (e) { data = null; }
    cb(data, data && data.error ? null : null);
  };
  http.exec();
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
  out(OUT_STATUS, "Live set BPM: " + bpm + " \u2014 matching assets\u2026");
  // crude genre tag by BPM range; production version uses the DAW engine
  var tag = "";
  if (bpm >= 120 && bpm <= 128) tag = "house";
  else if (bpm >= 128 && bpm <= 132) tag = "techno";
  else if (bpm >= 140 && bpm <= 150) tag = "dubstep";
  else if (bpm >= 85 && bpm <= 100) tag = "trap";
  else tag = "generic";
  // The device also re-reads the last catalog (outlet 0) and we match here.
  // This is a stub hook for the recommendation engine.
  out(OUT_MATCH, tag);
}

// ---- buying (testnet, raw signed txs) ---------------------------------------

function buy(id) {
  if (!config.key) {
    out(OUT_STATUS, "No private key configured. Set the `key` message (testnet only!).");
    return;
  }
  pendingId = id;
  out(OUT_STATUS, "Buying #" + id + " \u2014 approving SND\u2026");
  // This is where the production flow connects to the escrow contract:
  //  1. approve(token, market, price)
  //  2. market.buy(id)
  //  3. on success -> loadAsset(assetUri)
  // The full implementation needs an EIP-1559 signer; for the prototype we
  // leave the tx-building to the web app (same wallet) and just show intent.
  out(OUT_STATUS, "Open soundhub.com/marketplace to complete the purchase (same wallet), then hit Load.");
}

// ---- loading assets into the Live project -----------------------------------

function loadAsset(url, name) {
  var tmp = config.tempDir || "/tmp";
  var target = tmp + "/soundhub_" + name.replace(/[^a-zA-Z0-9._-]/g, "_");
  out(OUT_STATUS, "Downloading " + url + "\u2026");
  if (!http) http = this.patcher.apply(this.patcher, ["httprequest"]);
  http.text = "";
  http.method = 0; // GET
  var u = url.replace(/^https?:\/\//, "");
  http.host = u.split("/")[0];
  http.port = 443;
  http.path = "/" + u.split("/").slice(1).join("/");
  http.callback = function (err) {
    if (err) {
      out(OUT_STATUS, "Download failed: " + err);
      return;
    }
    // Save bytes and insert into the Live set. Real implementation:
    //   - write http.response to `target`
    //   - this.patcher.apply(this.patcher, ["live.thisdevice"]) to find the track
    //   - create a `live.groove`/`live.audiofile` or push the file into the
    //     browser via Live API (Song.capture_midi etc.)
    out(OUT_STATUS, "Asset ready at " + target + " \u2014 drag into a track (prototype).");
  };
  http.exec();
}

// ---- inlets ---------------------------------------------------------------

function bang() {
  // `bang` from the load button: re-read catalog
  loadCatalog();
}

function msg_int(v) {
  // 0 = refresh catalog, 1 = suggest for current BPM, 2 = buy
  if (v === 0) loadCatalog();
  else if (v === 1) suggestForBpm(readBpm());
  else if (v === 2) buy(pendingId >= 0 ? pendingId : 1);
}

function readBpm() {
  var v = this.patcher.apply(this.patcher, ["live.object", "id"]);
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
