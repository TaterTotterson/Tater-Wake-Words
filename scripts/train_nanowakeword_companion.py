#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType


def load_nanowakeword_stage(trainer_dir: Path) -> ModuleType:
    trainer_root = trainer_dir.resolve()
    module_path = trainer_root / "nanowakeword_stage.py"
    if not module_path.is_file():
        raise RuntimeError(
            f"The macOS trainer does not include NanoWakeWord support: {module_path}"
        )
    spec = importlib.util.spec_from_file_location("tater_nanowakeword_stage", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load NanoWakeWord stage: {module_path}")
    module = importlib.util.module_from_spec(spec)
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(trainer_root))
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
    return module


def train_companion(
    *,
    phrase: str,
    safe_word: str,
    architecture: str,
    trainer_dir: Path,
    data_dir: Path,
    trained_dir: Path,
) -> Path:
    stage = load_nanowakeword_stage(trainer_dir)
    data_dir = data_dir.resolve()
    trained_dir = trained_dir.resolve()
    personal_dir = data_dir / "personal_samples"
    negative_dir = data_dir / "negative_samples"
    generated_positive_dir = data_dir / "generated_samples"
    personal_dir.mkdir(parents=True, exist_ok=True)
    negative_dir.mkdir(parents=True, exist_ok=True)

    command, cwd, environment, staging_dir = stage.prepare_nanowakeword_stage(
        phrase=phrase,
        safe_word=safe_word,
        architecture=architecture,
        data_dir=data_dir,
        generated_positive_dir=generated_positive_dir,
        personal_dir=personal_dir,
        negative_dir=negative_dir,
        environ=os.environ,
        log=lambda line: print(line, flush=True),
    )
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd), env=environment, check=True)
    return stage.publish_nanowakeword_artifacts(
        staging_dir=staging_dir,
        trained_dir=trained_dir,
        safe_word=safe_word,
        phrase=phrase,
        architecture=architecture,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train and publish a NanoWakeWord model into a Tater wake bundle."
    )
    parser.add_argument("--phrase", required=True)
    parser.add_argument("--safe-word", required=True)
    parser.add_argument("--architecture", choices=("cnn", "gru"), required=True)
    parser.add_argument("--trainer-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--trained-dir", type=Path, required=True)
    args = parser.parse_args()

    bundle = train_companion(
        phrase=args.phrase,
        safe_word=args.safe_word,
        architecture=args.architecture,
        trainer_dir=args.trainer_dir,
        data_dir=args.data_dir,
        trained_dir=args.trained_dir,
    )
    print(
        f"Published NanoWakeWord {args.architecture.upper()} into bundle: {bundle}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
