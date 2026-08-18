# SoundHub × FL Studio

FL Studio integration is the **shared VST3 companion panel** in [`../vst3/`](../vst3/)
plus the local **SoundHub Agent** (`snd agent`, see `../backend/snd_cli.py`).

Why not a deeper integration: FL Studio's Python MIDI scripting is an API for
**hardware MIDI controllers** (translating commands between a device and FL
Studio), not a general service-integration platform. It is fine for trigger
actions (export/push) but not for building SoundHub on top of it. VST3 gives
the plugin transport/tempo/parameters, not `.flp` internals — so the panel is
a storefront + review/publish companion, and smart diff is built from the
exported `SOUNDHUB-MANIFEST.json` (via `snd push`), not from parsing the
closed project format inside the host.

Flow:

```text
FL Studio (SoundHub.vst3)
  → localhost SoundHub Agent (127.0.0.1:8765)
  → snd push pipeline → project + master + stems + manifest → review
```

See [`../docs/daw-integration-vst3.md`](../docs/daw-integration-vst3.md) for
the full architecture and capability table.
