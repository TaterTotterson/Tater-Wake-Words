<p align="center">
  <img src="images/tater-repo-logo.png" alt="Tater" width="460"/>
</p>

# Tater Wake Words

Tater wake-word catalog for Tater Native satellites.

This repo stores ready-to-use microWakeWord model packages:

- `.json` metadata files
- `.tflite` model files
- `wake_word_manifest.json` for app/catalog discovery

The historical catalog folders are seeded from the original Tater wake-word collection:

- `microWakeWordsV1`
- `microWakeWordsV2`
- `microWakeWordsV3`

New issue-generated wake words are added to `microWakeWordsV4`.

## Use A Wake Word

Use the raw GitHub URL for a wake-word JSON file in Tater's satellite settings.

Example:

```text
https://raw.githubusercontent.com/TaterTotterson/Tater-Wake-Words/main/microWakeWordsV1/hey_tater.json
```

Tater Native firmware downloads the JSON and the linked `.tflite` model.

## Request A Wake Word

Open an issue with a title in this format:

```text
mww: hey potato
```

Only issues whose title starts with `mww:` are handled by automation.

When the self-hosted trainer runner completes successfully, it adds the generated `.json` and `.tflite` files, updates the manifest, comments on the issue, and closes it.

## Catalog

Regenerate the manifest locally:

```bash
python3 scripts/generate_wake_word_manifest.py
```

The manifest scans every folder named `microWakeWordsV*`.

## Automation Setup

The issue workflow is event driven. It does not poll GitHub.

It runs when an issue is opened, edited, or reopened. The script exits immediately unless the title starts with `mww:`.

The training job requires a self-hosted macOS ARM64 GitHub Actions runner with the label `tater-wake-words`.

Register the runner from the Mac that has the trainer/cache:

```bash
scripts/setup_self_hosted_runner_macos.sh
```

The default runner setup expects the external SD card mounted at `/Volumes/Untitled` and keeps the large training data off the internal disk:

```text
/Volumes/Untitled/Tater-Wake-Words
/Volumes/Untitled/microWakeWord-Trainer-AppleSilicon
/Volumes/Untitled/tater-wake-tmp
/Volumes/Untitled/actions-runners/tater-wake-words
```

The GitHub workflow uses these repo variables:

```text
TATER_WAKE_EXTERNAL_ROOT=/Volumes/Untitled
TATER_WAKE_TRAINER_DIR=/Volumes/Untitled/microWakeWord-Trainer-AppleSilicon
TATER_WAKE_TMP_ROOT=/Volumes/Untitled/tater-wake-tmp
```

If the external volume is not mounted, the training job fails instead of filling the Mac's internal disk.

By default, generated words are written to `microWakeWordsV4`.
