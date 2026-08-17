// Unit tests for the scriptable parts of soundhub-device.js.
// Run: node m4l/test-device.js   (no dependencies)
//
// The device runs inside Max (outlet/post/max/LiveAPI); here we stub those
// globals and exercise the pure helpers plus the LiveAPI context reader.

const assert = require("assert");

// --- Max stubs ---------------------------------------------------------------
global.outlet = () => {};
global.post = () => {};
global.max = { getenv: () => "" };

// Scripted LiveAPI: live_set.tempo = 128, two tracks, track 0 has a "Vital"
// device, track 1 has a "Serum" device.
class FakeLiveAPI {
  constructor(patcher, path) {
    this.path = path;
  }
  get(key) {
    if (this.path === "live_set") return ["128"]; // tempo
    if (this.path.indexOf("devices") !== -1) {
      const m = /tracks (\d+) devices/.exec(this.path);
      const names = { 0: "Vital", 1: "Serum" };
      return [names[m ? m[1] : "0"] || "Plugin"];
    }
    return "";
  }
  getcount(key) {
    if (this.path === "live_set tracks") return 2;
    if (key === "devices") return 1;
    return 0;
  }
}
global.LiveAPI = FakeLiveAPI;

const dev = require("./soundhub-device.js");

// --- expandPath ----------------------------------------------------------------
global.max = { getenv: () => "/home/user" };
assert.strictEqual(dev.expandPath("~/Music"), "/home/user/Music");
assert.strictEqual(dev.expandPath("~"), "/home/user");
assert.strictEqual(dev.expandPath("/abs/path"), "/abs/path");
assert.strictEqual(dev.expandPath(""), "");

// --- normalizeDevices -----------------------------------------------------------
assert.deepStrictEqual(dev.normalizeDevices(["  Vital ", "Serum", "", "Vital", null]), ["Serum", "Vital"]);
assert.deepStrictEqual(dev.normalizeDevices(["Zebra", "Alpha", "Mid"], 2), ["Alpha", "Mid"]);

// --- readSetContext ------------------------------------------------------------
// devices come back sorted (stable URLs regardless of Live API traversal order)
const ctx = dev.readSetContext();
assert.strictEqual(ctx.bpm, 128);
assert.deepStrictEqual(ctx.devices, ["Serum", "Vital"]);
// dedupe: same device twice on one track is collapsed
class DupLiveAPI {
  constructor(patcher, path) {
    this.path = path;
  }
  get(key) {
    if (this.path === "live_set") return ["96"];
    if (this.path.indexOf("devices") !== -1) return ["Serum"];
    return "";
  }
  getcount(key) {
    if (this.path === "live_set tracks") return 2;
    if (key === "devices") return 2;
    return 0;
  }
}
global.LiveAPI = DupLiveAPI;
const dup = dev.readSetContext();
assert.strictEqual(dup.bpm, 96);
assert.deepStrictEqual(dup.devices, ["Serum"]);

// --- buildRecommendUrl ----------------------------------------------------------
const url = dev.buildRecommendUrl("http://127.0.0.1:8000", { bpm: 128, devices: ["Vital", "Serum"] }, 3);
assert.ok(url.startsWith("http://127.0.0.1:8000/api/assets/recommend?"), url);
assert.ok(url.includes("bpm=128"), url);
assert.ok(url.includes("devices=Serum%2CVital"), url); // sorted before encoding
assert.ok(url.includes("limit=3"), url);

const url2 = dev.buildRecommendUrl("http://x", { bpm: 120, devices: [], genre: "techno", key: "A minor" }, 5);
assert.ok(url2.includes("genre=techno"), url2);
assert.ok(url2.includes("key=A%20minor"), url2);
assert.ok(url2.includes("limit=5"), url2);

// special characters (& + / brackets unicode) survive encoding
const url4 = dev.buildRecommendUrl("http://x", { bpm: 128, devices: ["Vital & Co", "Синт++", "Max (M4L)"] }, 3);
assert.ok(url4.includes("Vital%20%26%20Co"), url4);
assert.ok(url4.includes("%D0%A1%D0%B8%D0%BD%D1%82%2B%2B"), url4);
assert.ok(url4.includes("Max%20(M4L)"), url4);

// bpm-less, device-less context omits both params entirely
const url3 = dev.buildRecommendUrl("http://x", { bpm: 0, devices: [] }, 3);
assert.ok(!url3.includes("bpm="), url3);
assert.ok(!url3.includes("devices="), url3);

// empty set (no tracks) still yields a valid bpm-only URL
class EmptyLiveAPI {
  constructor(patcher, path) {
    this.path = path;
  }
  get(key) {
    if (this.path === "live_set") return ["100"];
    return "";
  }
  getcount(key) {
    if (this.path === "live_set tracks") return 0;
    return 0;
  }
}
global.LiveAPI = EmptyLiveAPI;
const emptyCtx = dev.readSetContext();
assert.strictEqual(emptyCtx.bpm, 100);
assert.deepStrictEqual(emptyCtx.devices, []);
const emptyUrl = dev.buildRecommendUrl("http://x", emptyCtx, 3);
assert.ok(emptyUrl.includes("bpm=100"), emptyUrl);
assert.ok(!emptyUrl.includes("devices="), emptyUrl);

console.log("M4L device tests passed ✓");
