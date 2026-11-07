# microWakeWords V9

V9 contains complete schema-v4 Tater wake-word packages. Each published word
has one canonical `.wake-bundle.json`, an ESPHome-only MWW manifest, the MWW,
OWW, NWW-CNN, and NWW-GRU detector models, and a per-word
`.boundary.tflite` wake-end model.

The boundary model is detector-independent and lets Tater preserve speech that
starts immediately after the wake word. V8 and earlier folders remain intact
for existing installations.
