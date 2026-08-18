// SoundHub × Cubase — panel logic.
//
// Uses the Web MIDI API (Chrome/Edge) to read the CCs emitted by
// cubase/midiremote/soundhub.js, and the SoundHub backend for ranked
// recommendations. Tempo is only sent when Cubase reports a change, so the
// BPM input is the source of truth until the first CC 20 arrives.

"use strict";

const backendInput = document.getElementById("backend");
const bpmInput = document.getElementById("bpm");
const suggestBtn = document.getElementById("suggest");
const midiSelect = document.getElementById("midi");
const connectBtn = document.getElementById("connect");
const transportTag = document.getElementById("transport");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

let midiAccess = null;
let inputPort = null;

// --- Web MIDI --------------------------------------------------------------

async function initMidi() {
  if (!navigator.requestMIDIAccess) {
    status("Web MIDI not supported — use Chrome/Edge. BPM is manual.");
    return;
  }
  try {
    midiAccess = await navigator.requestMIDIAccess();
  } catch (err) {
    status("MIDI access denied: " + err);
    return;
  }
  refreshPorts();
  midiAccess.onstatechange = refreshPorts;
}

function refreshPorts() {
  midiSelect.innerHTML = "";
  const inputs = [...midiAccess.inputs.values()].filter((p) =>
    /soundhub/i.test(p.name)
  );
  if (inputs.length === 0) {
    midiSelect.innerHTML = '<option value="">— no SoundHub port —</option>';
    return;
  }
  for (const p of inputs) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.name;
    midiSelect.appendChild(opt);
  }
}

function connectPort() {
  if (inputPort) {
    inputPort.onmidimessage = null;
    inputPort = null;
  }
  if (!midiAccess || !midiSelect.value) {
    status("No MIDI port selected.");
    return;
  }
  inputPort = midiAccess.inputs.get(midiSelect.value);
  if (inputPort) {
    inputPort.onmidimessage = onMidiMessage;
    status("Listening on " + inputPort.name);
  }
}

function onMidiMessage(msg) {
  const [statusByte, data1, data2] = msg.data;
  const cc = statusByte & 0x0f === 0 && (statusByte & 0xf0) === 0xb0;
  if (!cc) return;
  if (data1 === 20) {
    // tempo, scaled 40-240 → 0-127 by soundhub.js
    const bpm = Math.round(40 + (data2 / 127) * 200);
    bpmInput.value = bpm;
    transportTag.textContent = "tempo: " + bpm + " BPM";
  } else if (data1 === 21) {
    transportTag.textContent = "transport: " + (data2 > 0 ? "▶ running" : "■ stopped");
  } else if (data1 === 22) {
    transportTag.textContent = "metronome: " + (data2 > 0 ? "on" : "off");
  }
}

// --- Backend ----------------------------------------------------------------

async function recommend() {
  const backend = backendInput.value.replace(/\/$/, "");
  const bpm = Number(bpmInput.value) || 128;
  status("Requesting recommendations for " + bpm + " BPM…");
  try {
    const res = await fetch(
      `${backend}/api/assets/recommend?bpm=${bpm}`
    );
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    render(data.items || []);
    status(`OK — ${(data.items || []).length} matches @ ${bpm} BPM`);
  } catch (err) {
    status("Recommend failed: " + err + " (is the backend running?)");
  }
}

function render(items) {
  resultsEl.innerHTML = "";
  if (items.length === 0) {
    resultsEl.innerHTML = '<div class="card">No matches for this BPM.</div>';
    return;
  }
  for (const it of items) {
    const card = document.createElement("div");
    card.className = "card";
    const meta = [it.genre, it.license, it.format].filter(Boolean).join(" · ");
    card.innerHTML = `
      <div>
        <div class="name"></div>
        <div class="meta"></div>
      </div>
      <div class="price"></div>`;
    card.querySelector(".name").textContent = it.name || "Unnamed asset";
    card.querySelector(".meta").textContent = meta || "—";
    card.querySelector(".price").textContent = (it.price ?? "?") + " SND";
    resultsEl.appendChild(card);
  }
}

function status(text) {
  statusEl.textContent = text;
}

// --- wire up ----------------------------------------------------------------

suggestBtn.addEventListener("click", recommend);
connectBtn.addEventListener("click", connectPort);
initMidi();
