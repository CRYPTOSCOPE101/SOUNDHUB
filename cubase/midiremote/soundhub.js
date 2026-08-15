// SoundHub × Cubase — MIDI Remote API script (prototype).
//
// Steinberg's MIDI Remote API is ES5 JavaScript and has NO file or HTTP
// access (HTTP/IPC is explicitly blocked). It cannot open sockets or read
// files, so this script's job is to stream the *project context* Cubase
// gives us out over MIDI, where the external SoundHub panel (../panel/)
// listens and drives the marketplace UI.
//
// What the API exposes (verified against the v1.3 reference):
//   - tempo changes  → transport.mTimeDisplay.mOnChangeTempoBPM callback
//   - running state  → transport.mValue.mStart (value binding)
//   - metronome      → transport.mValue.mMetronomeActive (value binding)
//
// The script maps these onto MIDI CCs the panel polls:
//   CC 20 (ch 0): tempo, scaled 40-240 BPM → 0-127
//   CC 21 (ch 0): 1 while transport is running, else 0
//   CC 22 (ch 0): 1 while metronome is active, else 0
//
// Install:
//   1. Cubase → Studio → Studio Setup → MIDI Remote → right-click the info
//      line → activate Scripting Tools → Open MIDI Remote Script Directory
//   2. Copy this file to  <that dir>/SoundHub/soundhub.js
//   3. Reload scripts; assign it to a (virtual) MIDI port pair.
//   4. Open the SoundHub panel (../panel/index.html), point it at that port.

var midiremote_api = require('midiremote_api_v1')

// --------------------------------------------------------------------------
// 1. DRIVER SETUP
// --------------------------------------------------------------------------

var deviceDriver = midiremote_api.makeDeviceDriver(
    'SoundHub', 'SoundHubPanel', 'SoundHub contributors')

var midiInput = deviceDriver.mPorts.makeMidiInput('SoundHub In')
var midiOutput = deviceDriver.mPorts.makeMidiOutput('SoundHub Out')

deviceDriver.makeDetectionUnit()
    .detectPortPair(midiInput, midiOutput)
    .expectInputNameEquals('SoundHub In')
    .expectOutputNameEquals('SoundHub Out')

// --------------------------------------------------------------------------
// 2. SURFACE LAYOUT — custom value variables streamed over MIDI
// --------------------------------------------------------------------------

deviceDriver.mSurface.makeBlindPanel(0, 0, 6, 6)

var tempoVar = deviceDriver.mSurface.makeCustomValueVariable('SoundHub Tempo')
var runningVar = deviceDriver.mSurface.makeCustomValueVariable('SoundHub Transport Running')
var metronomeVar = deviceDriver.mSurface.makeCustomValueVariable('SoundHub Metronome')

tempoVar.mMidiBinding
    .setInputPort(midiInput)
    .setOutputPort(midiOutput)
    .bindToControlChange(0, 20) // channel 0, CC 20

runningVar.mMidiBinding
    .setInputPort(midiInput)
    .setOutputPort(midiOutput)
    .bindToControlChange(0, 21) // channel 0, CC 21

metronomeVar.mMidiBinding
    .setInputPort(midiInput)
    .setOutputPort(midiOutput)
    .bindToControlChange(0, 22) // channel 0, CC 22

// --------------------------------------------------------------------------
// 3. HOST MAPPING
// --------------------------------------------------------------------------

var page = deviceDriver.mMapping.makePage('SoundHub')
var transport = page.mHostAccess.mTransport

// Tempo arrives as a callback (not a bindable value). Scale 40-240 → 0-127.
var TEMPO_MIN = 40
var TEMPO_MAX = 240
transport.mTimeDisplay.mOnChangeTempoBPM = function (activeDevice, tempoBPM) {
    var clamped = Math.min(TEMPO_MAX, Math.max(TEMPO_MIN, tempoBPM))
    var scaled = Math.round(((clamped - TEMPO_MIN) / (TEMPO_MAX - TEMPO_MIN)) * 127)
    tempoVar.setProcessValue(activeDevice, scaled)
}

// Running / metronome are ordinary host values → direct bindings.
page.makeValueBinding(runningVar, transport.mValue.mStart)
page.makeValueBinding(metronomeVar, transport.mValue.mMetronomeActive)
