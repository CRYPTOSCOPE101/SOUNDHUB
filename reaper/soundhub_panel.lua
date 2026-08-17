-- SoundHub for REAPER — project push + review comments panel
-- ===========================================================
-- ReaScript (Lua) mirror of the Max for Live device: the same DAW bridge
-- contract (`snd serve` on :8765), one action to push the current REAPER
-- project as a versioned commit, one to pull the open review comments into
-- the console.
--
-- Install: copy to your REAPER Scripts folder, Actions → Show action list →
-- New action → Load reascript. Bind keys, or add to a toolbar.
--
-- Config (edit below, or call the exported setter from another script):
--   bridge       = "http://127.0.0.1:8765"  -- local `snd serve` bridge
--   backend      = "http://127.0.0.1:8000"  -- SoundHub backend (comments)
--   shareToken   = ""                       -- /r/<token> part of the review link
--   projectName  = ""                       -- SoundHub project (default: .rpp name)
--   branch       = "main"

local cfg = {
  bridge      = "http://127.0.0.1:8765",
  backend     = "http://127.0.0.1:8000",
  shareToken  = "",
  projectName = "",
  branch      = "main",
  message     = "snd push",
}

local function log(msg)
  reaper.ShowConsoleMsg("[SoundHub] " .. msg .. "\n")
  reaper.UpdateArrange()
end

-- ---- tiny JSON string extraction (the snd contract is flat enough) --------

local function json_field(text, key)
  local s = text:match('"' .. key .. '"%s*:%s*"([^"]*)"')
  if s then return s end
  local n = text:match('"' .. key .. '"%s*:%s*(%-?%d+)')
  if n then return n end
  if text:match('"' .. key .. '"%s*:%s*true') then return "true" end
  if text:match('"' .. key .. '"%s*:%s*false') then return "false" end
  return nil
end

local function json_bool(text, key)
  return json_field(text, key) == "true"
end

-- ---- HTTP: reaper.URL_Get (async, built-in — no LuaSocket needed) --------
-- reaper.URL_Get(url, callback) runs the request in the background and calls
-- callback(data, status) when it lands (data is the response body string).
-- We render straight into the console from the callback — no defer dance.

local function url_get(url, on_done)
  -- reaper.URL_Get fires its callback on the main thread; we reschedule
  -- through reaper.defer so the script context stays alive until the
  -- response lands (REAPER finalizes an action when its defer chain ends).
  local function cb(data, status)
    local ok = type(status) == "number" and status >= 200 and status < 300
    if data == nil then data = "" end
    reaper.defer(function()
      local good, err = pcall(on_done, ok, data)
      if not good then
        reaper.ShowConsoleMsg("[SoundHub] error: " .. tostring(err) .. "\n")
      end
    end)
  end
  local _, err = reaper.URL_Get(url, cb)
  if err and err ~= 0 then
    reaper.defer(function() on_done(false, "URL_Get failed: " .. tostring(err)) end)
  end
end

-- ---- push the current project ---------------------------------------------
-- Pushes run through the `snd` CLI (full preflight + local manifest, same
-- contract the M4L sidecar uses). REAPER has no sync POST from ReaScript,
-- so the CLI is the natural transport here — the bridge /push stays for the
-- M4L device and for anyone who prefers the JSON bridge.

local function push_current_project()
  local path = reaper.GetProjectPath()
  local name = reaper.GetProjectName(0)
  if name == "" then
    log("push failed: save the project first (untitled project has no .rpp path yet)")
    return
  end
  local full = path .. name
  log("pushing " .. full .. " …")

  local project = (cfg.projectName ~= "" and cfg.projectName or name:gsub("%.rpp$", ""))
  local ok, exit = reaper.ExecProcess(
    'cd "' .. path .. '" && snd push "' .. full
    .. '" --project "' .. project
    .. '" --branch "' .. cfg.branch .. '" --json', 0)
  ok = ok or ""
  if exit == 0 and ok:find('"ok"%s*:%s*true') then
    local cid = ok:match('"commit_id"%s*:%s*(%d+)') or "?"
    log("✓ pushed commit #" .. cid .. " · review: "
      .. (ok:match('"review_url"%s*:%s*"([^"]*)"') or "fast push (no review)"))
    return
  end
  log("snd CLI unavailable or failed — run `snd login` once, then:\n  cd backend && ./snd push \"" .. full .. "\"")
end

-- ---- load open review comments --------------------------------------------

local function load_comments()
  if cfg.shareToken == "" then
    log("no share token — set cfg.shareToken (the /r/<token> part of the review link)")
    return
  end
  local url = cfg.backend .. "/api/sessions/public/" .. cfg.shareToken .. "/requests/export?format=markdown"
  log("loading open review comments…")
  url_get(url, function(ok, body)
    if not ok then
      log("load comments failed: " .. body)
      return
    end
    local count = body:match("· (%d+) active")
    if count == nil then
      log("load comments failed: unexpected response (wrong token?)")
      return
    end
    reaper.ShowConsoleMsg("\n" .. body .. "\n")
    log(count == "0" and "No open review comments. 🎉" or count .. " open comment(s) — see above")
  end)
end

-- ---- config setter (callable from other scripts / toolbar buttons) --------

function extensions.snd_set_config(key, value)
  if cfg[key] ~= nil then cfg[key] = value end
end

-- ---- entry point -----------------------------------------------------------
-- First arg decides the mode so one script can serve two toolbar buttons:
--   "push" (default) — push the current project (via the snd CLI)
--   "comments"       — pull open review comments into the console

local mode = ({...})[1] or "push"
if mode == "comments" then
  load_comments()
  -- the URL_Get callback defers the render, which keeps the script alive
  -- until the response arrives (an empty defer chain would finalize it)
  reaper.defer(function() end)
else
  push_current_project()
end
