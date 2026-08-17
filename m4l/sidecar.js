#!/usr/bin/env node
// SoundHub native sidecar — push the current Live set to SoundHub without
// an external `snd serve` process.
//
// Max 8.5+ ships a Node.js runtime for the `node.script` object, so this
// script runs INSIDE the device: it reads the .als from disk, builds a
// real multipart body and posts it to the SoundHub backend. No separate
// bridge process to start, no `shell` (blocked in Live), no binary-mangling
// `httprequest`.
//
// The same code doubles as a plain CLI, which is how the test suite drives
// it (and how you can use it from a terminal):
//
//     node sidecar.js push --target ./Track_v12.als --project "artist-track" \
//         --api http://127.0.0.1:8000 --token <token> --json
//
// When loaded inside Max (node.script), the device sends a `push <json>`
// message and the result comes back on the object's outlet.
//
// Contract (same as `snd push --json`):
//     {"ok": true, "project_id", "branch", "commit_id", "version_id",
//      "session_id", "share_token", "review_url", "uploaded",
//      "deduplicated"}
//     {"ok": false, "error": "…"}
//
// Note on the manifest: the backend re-parses every pushed DAW file itself
// (smart diff / tree analysis), so the sidecar does not need the Python
// parsers — the .als travels as-is and the server extracts the structure.

"use strict";

var fs = require("fs");
var path = require("path");
var http = require("http");
var https = require("https");
var crypto = require("crypto");

var DAW_EXTS = [".als", ".rpp", ".flp", ".cpr"];
var ALLOWED_AUDIO = ["wav", "mp3", "flac", "ogg", "aif", "aiff", "m4a"];
var ALLOWED_STEM_AUDIO = ["wav", "mp3", "flac", "aif", "aiff", "m4a", "ogg"];
var DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024; // 2 GiB, mirrors backend config
var MAX_UPLOAD_SIZE = Number(process.env.SOUNDHUB_MAX_UPLOAD_SIZE || DEFAULT_MAX_UPLOAD_SIZE);

function CliError(message) {
  this.message = message;
  this.name = "CliError";
}
CliError.prototype = Object.create(Error.prototype);
CliError.prototype.constructor = CliError;

// ---- preflight ------------------------------------------------------------

function statOrThrow(p) {
  try {
    return fs.statSync(p);
  } catch (e) {
    throw new CliError("Not found: " + p);
  }
}

function checkSize(p, st) {
  if (st.size > MAX_UPLOAD_SIZE) {
    throw new CliError("File too large: " + p + " (" + st.size + " bytes > " + MAX_UPLOAD_SIZE + " max)");
  }
}

function isAlsReadable(data) {
  // Same magic checks as the backend's detect_format: gzip (real .als files
  // are gzip-compressed XML) or a raw <LiveSet document.
  if (data.length >= 2 && data[0] === 0x1f && data[1] === 0x8b) return true;
  var head = data.slice(0, 4096).toString("latin1");
  return head.indexOf("<LiveSet") !== -1;
}

function preflightTarget(target) {
  var st = statOrThrow(target);
  if (st.isDirectory()) return "dir";
  var ext = path.extname(target).toLowerCase();
  if (DAW_EXTS.indexOf(ext) === -1) {
    throw new CliError(
      "Unsupported project file type '" + ext + "' — expected one of: " + DAW_EXTS.join(", ")
    );
  }
  checkSize(target, st);
  var data = fs.readFileSync(target);
  if (!isAlsReadable(data)) {
    throw new CliError("Cannot read " + target + " as a DAW project file — the file looks corrupt or truncated");
  }
  return "file";
}

function preflightAudio(p, allowed, kind) {
  var st = statOrThrow(p);
  if (!st.isFile()) throw new CliError(kind + " file not found: " + p);
  var ext = path.extname(p).slice(1).toLowerCase();
  if (allowed.indexOf(ext) === -1) {
    throw new CliError("Unsupported " + kind + " audio format '" + ext + "'. Allowed: " + allowed.join(", "));
  }
  checkSize(p, st);
}

function preflightStemsDir(dir) {
  var st = statOrThrow(dir);
  if (!st.isDirectory()) throw new CliError("Stems directory not found: " + dir);
  var out = [];
  var names;
  try {
    names = fs.readdirSync(dir).sort();
  } catch (e) {
    throw new CliError("Stems directory not found: " + dir);
  }
  names.forEach(function (fn) {
    var full = path.join(dir, fn);
    var s = fs.statSync(full);
    if (!s.isFile()) return;
    var ext = path.extname(fn).slice(1).toLowerCase();
    if (ALLOWED_STEM_AUDIO.indexOf(ext) === -1) return;
    checkSize(full, s);
    out.push(full);
  });
  if (!out.length) {
    throw new CliError(
      "No audio stems found in " + dir + " (allowed: " + ALLOWED_STEM_AUDIO.join(", ") + ")"
    );
  }
  return out;
}

// ---- http helpers ---------------------------------------------------------

function httpRequest(method, url, headers, body) {
  return new Promise(function (resolve, reject) {
    var parsed = new URL(url);
    var lib = parsed.protocol === "https:" ? https : http;
    var req = lib.request(
      {
        hostname: parsed.hostname,
        port: parsed.port || (parsed.protocol === "https:" ? 443 : 80),
        path: parsed.pathname + parsed.search,
        method: method,
        headers: headers,
      },
      function (res) {
        var chunks = [];
        res.on("data", function (c) {
          chunks.push(c);
        });
        res.on("end", function () {
          resolve({ status: res.statusCode, text: Buffer.concat(chunks).toString("utf8") });
        });
      }
    );
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function httpJson(method, url, token, jsonBody) {
  var headers = {};
  if (token) headers.Authorization = "Bearer " + token;
  var body = null;
  if (jsonBody !== undefined) {
    body = JSON.stringify(jsonBody);
    headers["Content-Type"] = "application/json";
  }
  return httpRequest(method, url, headers, body).then(function (res) {
    var data = null;
    try {
      data = JSON.parse(res.text || "null");
    } catch (e) {
      data = null;
    }
    if (res.status >= 400) {
      var detail = data && data.detail ? JSON.stringify(data.detail) : res.text;
      throw new CliError("HTTP " + res.status + ": " + detail);
    }
    return data;
  });
}

function findProject(api, token, name) {
  var needle = String(name).trim().toLowerCase();
  return httpJson("GET", api + "/api/projects", token).then(function (rows) {
    var i;
    for (i = 0; i < (rows || []).length; i++) {
      var p = rows[i] || {};
      if (
        String(p.name || "").trim().toLowerCase() === needle ||
        String(p.id) === String(name).trim()
      ) {
        return p;
      }
    }
    return null;
  });
}

function createProject(api, token, name) {
  return httpJson("POST", api + "/api/projects", token, {
    name: name,
    description: "pushed via sidecar",
  });
}

// ---- multipart ------------------------------------------------------------

function buildMultipart(fields, fileEntries) {
  var boundary = "----sidecar" + crypto.randomBytes(12).toString("hex");
  var parts = [];
  fields.forEach(function (kv) {
    var key = kv[0];
    var value = String(kv[1]);
    parts.push(
      Buffer.from(
        "--" + boundary + "\r\n" +
        'Content-Disposition: form-data; name="' + key + '"\r\n\r\n' +
        value + "\r\n",
        "utf8"
      )
    );
  });
  fileEntries.forEach(function (fe) {
    parts.push(
      Buffer.from(
        "--" + boundary + "\r\n" +
        'Content-Disposition: form-data; name="' + fe.field + '"; filename="' + fe.name + '"\r\n' +
        "Content-Type: application/octet-stream\r\n\r\n",
        "utf8"
      )
    );
    parts.push(fe.data);
    parts.push(Buffer.from("\r\n", "utf8"));
  });
  parts.push(Buffer.from("--" + boundary + "--\r\n", "utf8"));
  return {
    body: Buffer.concat(parts),
    contentType: "multipart/form-data; boundary=" + boundary,
  };
}

// ---- push pipeline (shared by CLI and node.script) -------------------------

async function runPush(opts) {
  var api = opts.api;
  var token = opts.token || "";
  if (!api) throw new CliError("no api url (--api or SOUNDHUB_API_URL)");
  if (!opts.target) throw new CliError("no target file/dir");

  var target = path.resolve(opts.target);
  var kind = preflightTarget(target);

  var root;
  var projectFiles;
  if (kind === "dir") {
    root = target;
    projectFiles = [];
    var walk = function (dir) {
      var names = fs.readdirSync(dir).sort();
      names.forEach(function (fn) {
        if (fn === ".DS_Store" || fn === "Thumbs.db" || fn === ".git" || fn === ".svn" || fn === "__pycache__" || fn.charAt(0) === ".") return;
        var full = path.join(dir, fn);
        var st = fs.statSync(full);
        if (st.isDirectory()) {
          walk(full);
          return;
        }
        if (DAW_EXTS.indexOf(path.extname(fn).toLowerCase()) !== -1) {
          checkSize(full, st);
          projectFiles.push(full);
        }
      });
    };
    walk(root);
    if (!projectFiles.length) {
      throw new CliError("No project files found in " + root + " (expected .als/.rpp/.flp/.cpr)");
    }
  } else {
    root = path.dirname(target) || ".";
    projectFiles = [target];
  }

  // review materials
  var audioPath = opts.audio ? path.resolve(opts.audio) : null;
  if (audioPath) preflightAudio(audioPath, ALLOWED_AUDIO, "Master");
  var stemFiles = opts.stems ? preflightStemsDir(path.resolve(opts.stems)) : [];
  if ((audioPath || stemFiles.length) && !audioPath) {
    throw new CliError("Review mode requires --audio (the master) — stems attach to the master version");
  }

  var projectName = opts.project || path.basename(root.replace(/[\\/]+$/, "")) || "SoundHub project";

  var projectPromise;
  if (opts.project) {
    projectPromise = findProject(api, token, opts.project).then(function (found) {
      if (found) return found;
      if (/^\d+$/.test(String(opts.project).trim())) return found; // numeric id: let the server 404
      return createProject(api, token, opts.project);
    });
  } else {
    projectPromise = createProject(api, token, projectName);
  }

  return projectPromise.then(function (project) {
    if (!project || !project.id) {
      return Promise.reject(new CliError("Project not found: " + opts.project));
    }
    var fields = [
      ["message", opts.message || "snd push"],
      ["branch", opts.branch || "main"],
    ];
    if (opts.round) fields.push(["round", String(opts.round)]);

    var files = projectFiles.map(function (p) {
      return {
        field: "files",
        name: path.relative(root, p).split(path.sep).join("/"),
        data: fs.readFileSync(p),
      };
    });
    if (audioPath) {
      files.push({ field: "audio", name: path.basename(audioPath), data: fs.readFileSync(audioPath) });
    }
    stemFiles.forEach(function (p) {
      files.push({ field: "stems", name: path.basename(p), data: fs.readFileSync(p) });
    });

    var mp = buildMultipart(fields, files);
    return httpRequest(
      "POST",
      api + "/api/projects/" + project.id + "/push",
      {
        Authorization: "Bearer " + token,
        "Content-Type": mp.contentType,
      },
      mp.body
    ).then(function (res) {
      var data = null;
      try {
        data = JSON.parse(res.text || "null");
      } catch (e) {
        data = null;
      }
      if (res.status >= 400) {
        var detail = data && data.error ? data.error : res.text;
        throw new CliError(detail || ("HTTP " + res.status));
      }
      return data;
    });
  });
}

// ---- CLI mode --------------------------------------------------------------

function parseCli(argv) {
  var opts = { flags: {} };
  var i = 0;
  var arg;
  function value(flag) {
    if (i + 1 >= argv.length) throw new CliError(flag + " needs a value");
    return argv[++i];
  }
  while (i < argv.length) {
    arg = argv[i];
    if (arg === "--api") opts.api = value("--api");
    else if (arg === "--token") opts.token = value("--token");
    else if (arg === "--target") opts.target = value("--target");
    else if (arg === "--project") opts.project = value("--project");
    else if (arg === "--branch") opts.branch = value("--branch");
    else if (arg === "--message") opts.message = value("--message");
    else if (arg === "--audio") opts.audio = value("--audio");
    else if (arg === "--stems") opts.stems = value("--stems");
    else if (arg === "--round") opts.round = Number(value("--round"));
    else if (arg === "--json") opts.flags.json = true;
    else if (arg.charAt(0) === "-") throw new CliError("Unknown option: " + arg);
    else if (!opts.target) opts.target = arg;
    else throw new CliError("Unexpected argument: " + arg);
    i++;
  }
  return opts;
}

function cliMain(argv) {
  var opts;
  try {
    opts = parseCli(argv);
  } catch (e) {
    console.error("error: " + e.message);
    return 1;
  }
  return runPush(opts)
    .then(function (result) {
      if (opts.flags.json) {
        console.log(JSON.stringify(result, null, 2));
      } else {
        console.log("✓ pushed — commit #" + result.commit_id + " · " + (result.file_count || "?") + " files · " + result.branch);
        if (result.review_url) console.log("  review: " + result.review_url);
      }
      return 0;
    })
    .catch(function (e) {
      var msg = e && e.message ? e.message : String(e);
      if (opts.flags.json) {
        console.log(JSON.stringify({ ok: false, error: msg }));
      } else {
        console.error("error: " + msg);
      }
      return 1;
    });
}

// ---- node.script mode ------------------------------------------------------
// Max calls `push <json>`; the sidecar posts to the backend and sends the
// contract back through the object's outlet (outlet is provided by Max's
// node.script runtime — polyfilled as a no-op when run outside Max).

function nodeScriptPush(jsonPayload) {
  var opts;
  try {
    opts = JSON.parse(jsonPayload || "{}");
  } catch (e) {
    return sendResult({ ok: false, error: "bad JSON payload: " + e });
  }
  runPush(opts).then(
    function (res) {
      sendResult(res);
    },
    function (e) {
      sendResult({ ok: false, error: e && e.message ? e.message : String(e) });
    }
  );
}

function sendResult(obj) {
  if (typeof outlet === "function") {
    outlet(0, JSON.stringify(obj));
  } else if (typeof max === "object" && max && typeof max.outlet === "function") {
    max.outlet(0, JSON.stringify(obj));
  }
}

if (require.main === module) {
  cliMain(process.argv.slice(2)).then(function (code) {
    process.exit(code);
  });
} else {
  // Exposed for node.script (and require() from tests).
  module.exports = {
    push: nodeScriptPush,
    runPush: runPush,
    preflightTarget: preflightTarget,
    CliError: CliError,
  };
}
