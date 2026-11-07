<div align="center">
  <a href="https://taterassistant.com">
    <img src="images/tater-wake-words-logo.png" alt="Tater Wake Words" width="460"/>
  </a>
</div>

<p align="center">
  <a href="https://taterassistant.com">
    <img alt="Visit Tater Assistant" src="https://img.shields.io/badge/Tater%20Assistant-Visit%20Website-F28C28?style=for-the-badge&logo=googlechrome&logoColor=white" />
  </a>
</p>

# Tater Wake Words

Tater wake-word catalog for Tater Native satellites.

This repo stores ready-to-use wake-word packages. New V9 packages contain:

- `.wake-bundle.json` schema-v4 Tater metadata for MWW, OWW, NWW-CNN, NWW-GRU, and wake-boundary models
- `.esphome.json` ESPHome-compatible microWakeWord metadata
- `.tflite` microWakeWord models
- `.oww.onnx` openWakeWord models
- `.nww.cnn.onnx` NanoWakeWord CNN models
- `.nww.gru.onnx` NanoWakeWord GRU models
- `.boundary.tflite` per-word wake-end boundary models shared by every Tater detector mode
- `wake_word_manifest.json` for bundle and engine catalog discovery

The historical catalog folders are seeded from the original Tater wake-word collection:

- `microWakeWordsV1`
- `microWakeWordsV2`
- `microWakeWordsV3`

New issue-generated wake words are added to `microWakeWordsV9`. Versions 1–8
remain available for existing installations; V8 keeps the earlier schema-v3
bundle layout without a wake-boundary model.

## Use A Wake Word

Use a V9 `.wake-bundle.json` URL in Tater. The same package supplies MWW, OWW,
NWW-CNN, NWW-GRU, MWW+OWW, or MWW+NWW according to the selected detector mode,
plus the wake-boundary model used to preserve speech immediately after the wake
word. For ESPHome's `micro_wake_word`, use the matching `.esphome.json` URL.

Example:

```text
https://raw.githubusercontent.com/TaterTotterson/Tater-Wake-Words/main/microWakeWordsV9/hey_tater.wake-bundle.json
```

Tater downloads the bundle and only the model files needed by each satellite.

The catalog manifest exposes verified views for:

- **microWakeWord**
- **openWakeWord**
- **NanoWakeWord** with CNN and GRU architectures
- **Dual Wake Word**
- **Wake Boundary**
- **Wake Word Bundle**

V9 entries are listed only after the bundle and all five model files pass
filename, size, and SHA-256 validation. Older catalog entries remain listed in
their original formats.

## Request A Wake Word

Open an issue with a title in this format:

```text
mww: hey potato
```

Only issues whose title starts with `mww:` are handled by automation.

When the Apple trainer watcher completes successfully, it adds the canonical
bundle, ESPHome MWW JSON, MWW TFLite, OWW ONNX, NWW CNN ONNX, NWW GRU ONNX,
and wake-boundary TFLite to `microWakeWordsV9`. It then updates the catalog
manifest, comments with all artifact links, and closes the issue. Issue
processing is handled by the independent watcher on the training Mac.

## License

Original code, metadata, and model artifacts produced and published by this
project are available under the [MIT License](LICENSE).

Historical model assets and third-party components remain subject to any
applicable source licenses and are not relicensed where the project does not
hold those rights. Wake-word phrases may contain third-party names or
trademarks; inclusion in this catalog does not grant rights to use them.

## Trademarks

The Tater name and logo are governed by the [Tater Trademark Policy](TRADEMARKS.md).
