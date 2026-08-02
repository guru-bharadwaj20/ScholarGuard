#!/usr/bin/env python
"""Train the real-vs-AI artifact classifier locally on a CUDA GPU.

The repo ships ``colab/train_artifact_classifier.ipynb`` for a free T4. This is
the same recipe (MobileNetV3-small, 224px ImageNet normalization, AdamW +
cosine, class-weighted cross-entropy) as a headless script for a local GPU, with
three differences that matter:

1. **Architecture parity is structural, not manual.** It calls
   ``src.models.artifact_classifier.build_model`` — the very function the
   inference loader uses — so the notebook's "keep the two in sync" warning
   cannot be violated here.
2. **Held-out leakage is excluded.** ``data/clean/`` figures are named
   ``<PMCID>_<figure>.jpg``, and some of those PMCIDs also appear as clean
   controls in the evaluation sets. Training on them and then reporting a
   per-figure false-alarm rate over the same figures is leakage; pass
   ``--exclude-pmcids-from`` (default: both evaluation labels files) to drop
   every figure whose PMCID is under evaluation.
3. **Class imbalance is handled**, since the real and AI classes are collected
   independently and rarely come out the same size.

The checkpoint schema is exactly what ``classify_artifact`` expects:
``state_dict``, ``backbone``, ``input_size``, ``classes``, ``val_accuracy``,
``normalization``. A ``training_report.json`` beside it records the split, the
per-class metrics and the exclusion count.

Example:
    python scripts/train_artifact_classifier.py \
        --real-dir data/clean --ai-dir data/ai_generated_real --epochs 8
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.artifact_classifier import (  # noqa: E402
    CLASSES,
    DEFAULT_WEIGHTS_PATH,
    INPUT_SIZE,
)

logger = logging.getLogger("scholarguard.train")

EXTS = ("*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff", "*.bmp")
MEAN = [0.485, 0.456, 0.406]   # must match artifact_classifier._preprocess
STD = [0.229, 0.224, 0.225]
_PMCID_RE = re.compile(r"(PMC\d+)", re.IGNORECASE)


def list_images(folders: list[str]) -> list[str]:
    paths: list[str] = []
    for folder in folders:
        for ext in EXTS:
            paths.extend(glob.glob(os.path.join(folder, ext)))
    return sorted(paths)


def excluded_pmcids(paths: list[str]) -> set[str]:
    """PMCIDs under evaluation, which must not appear in the training set."""
    ids: set[str] = set()
    for path in paths:
        if not os.path.isfile(path):
            logger.warning("exclusion file not found (ignored): %s", path)
            continue
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for paper in (data["papers"] if isinstance(data, dict) else data):
            if paper.get("paper_id"):
                ids.add(paper["paper_id"].upper())
    return ids


def drop_evaluation_figures(paths: list[str], blocked: set[str]) -> tuple[list[str], int]:
    """Remove figures whose filename carries a PMCID under evaluation."""
    if not blocked:
        return paths, 0
    kept = []
    for path in paths:
        match = _PMCID_RE.search(os.path.basename(path))
        if match and match.group(1).upper() in blocked:
            continue
        kept.append(path)
    return kept, len(paths) - len(kept)


def build_loaders(real_paths, ai_paths, args):
    import torch
    from PIL import Image
    from sklearn.model_selection import train_test_split
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms

    paths = list(real_paths) + list(ai_paths)
    labels = [0] * len(real_paths) + [1] * len(ai_paths)   # 0=real, 1=ai_generated
    tr_p, va_p, tr_y, va_y = train_test_split(
        paths, labels, test_size=args.val_fraction, stratify=labels,
        random_state=args.seed)

    train_tf = transforms.Compose([
        transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(0.1, 0.1),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(MEAN, STD),
    ])

    class FigureDataset(Dataset):
        def __init__(self, paths, labels, tf):
            self.paths, self.labels, self.tf = paths, labels, tf

        def __len__(self):
            return len(self.paths)

        def __getitem__(self, i):
            with Image.open(self.paths[i]) as img:
                return self.tf(img.convert("RGB")), self.labels[i]

    train_dl = DataLoader(FigureDataset(tr_p, tr_y, train_tf),
                          batch_size=args.batch_size, shuffle=True,
                          num_workers=args.workers, drop_last=False)
    val_dl = DataLoader(FigureDataset(va_p, va_y, val_tf),
                        batch_size=max(args.batch_size, 32), shuffle=False,
                        num_workers=args.workers)

    # Class-weighted loss: the two classes are collected independently, so
    # their sizes rarely match and plain CE would drift toward the majority.
    counts = torch.tensor([tr_y.count(0), tr_y.count(1)], dtype=torch.float32)
    weights = counts.sum() / (2.0 * counts.clamp(min=1))
    return train_dl, val_dl, (tr_p, tr_y), (va_p, va_y), weights


def run(args) -> int:
    import torch
    import torch.nn as nn
    from sklearn.metrics import classification_report, confusion_matrix

    from src.models.artifact_classifier import build_model

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda requested but no CUDA device is visible")
    logger.info("device: %s%s", device,
                f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else "")

    blocked = excluded_pmcids(args.exclude_pmcids_from)
    real_paths, dropped = drop_evaluation_figures(list_images(args.real_dir), blocked)
    ai_paths = list_images(args.ai_dir)
    logger.info("real: %d image(s) (%d dropped as PMCIDs under evaluation)",
                len(real_paths), dropped)
    logger.info("ai  : %d image(s)", len(ai_paths))
    if len(real_paths) < 10 or len(ai_paths) < 10:
        raise RuntimeError("need at least 10 images per class to train "
                           f"(real={len(real_paths)}, ai={len(ai_paths)})")

    train_dl, val_dl, (tr_p, tr_y), (va_p, va_y), weights = build_loaders(
        real_paths, ai_paths, args)
    logger.info("train=%d val=%d | class weights real=%.2f ai=%.2f",
                len(tr_p), len(va_p), weights[0].item(), weights[1].item())

    model = build_model(args.backbone, num_classes=len(CLASSES)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=args.weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    crit = nn.CrossEntropyLoss(weight=weights.to(device))

    @torch.no_grad()
    def predict():
        model.eval()
        preds, gts = [], []
        for x, y in val_dl:
            preds += model(x.to(device)).argmax(1).cpu().tolist()
            gts += y.tolist()
        return preds, gts

    history, best_acc, best_state = [], 0.0, None
    for epoch in range(args.epochs):
        model.train()
        running, seen = 0.0, 0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = crit(model(x), y)
            loss.backward()
            opt.step()
            running += loss.item() * x.size(0)
            seen += x.size(0)
        sched.step()
        preds, gts = predict()
        acc = sum(p == g for p, g in zip(preds, gts, strict=True)) / max(1, len(gts))
        history.append({"epoch": epoch + 1, "train_loss": running / max(1, seen),
                        "val_accuracy": acc})
        logger.info("epoch %d/%d  loss=%.4f  val_acc=%.4f",
                    epoch + 1, args.epochs, running / max(1, seen), acc)
        if acc >= best_acc:
            best_acc = acc
            # Keep the BEST epoch, not the last: 8 epochs on a small set can
            # end on a worse one than it passed through.
            best_state = {k: v.detach().cpu().clone()
                          for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    preds, gts = predict()
    matrix = confusion_matrix(gts, preds, labels=[0, 1]).tolist()
    report = classification_report(gts, preds, labels=[0, 1],
                                   target_names=list(CLASSES),
                                   output_dict=True, zero_division=0)
    print("\nconfusion matrix [rows=true, cols=pred] (real, ai_generated):")
    print(f"  {matrix[0]}\n  {matrix[1]}")
    print(classification_report(gts, preds, labels=[0, 1],
                                target_names=list(CLASSES), zero_division=0))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    torch.save({
        "state_dict": model.state_dict(),
        "backbone": args.backbone,
        "input_size": INPUT_SIZE,
        "classes": list(CLASSES),
        "val_accuracy": float(best_acc),
        "normalization": {"mean": MEAN, "std": STD},
    }, args.out)
    logger.info("wrote %s (val_accuracy=%.4f)", args.out, best_acc)

    report_path = os.path.join(os.path.dirname(os.path.abspath(args.out)),
                               "training_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump({
            "backbone": args.backbone,
            "epochs": args.epochs,
            "lr": args.lr,
            "seed": args.seed,
            "device": device,
            "n_real": len(real_paths),
            "n_ai": len(ai_paths),
            "n_real_dropped_as_under_evaluation": dropped,
            "exclusion_sources": args.exclude_pmcids_from,
            "real_dirs": args.real_dir,
            "ai_dirs": args.ai_dir,
            "n_train": len(tr_p),
            "n_val": len(va_p),
            "best_val_accuracy": float(best_acc),
            "confusion_matrix": matrix,
            "classification_report": report,
            "history": history,
            "validation_files": va_p,
        }, fh, indent=2)
    print(f"\nCheckpoint: {args.out}\nReport:     {report_path}")
    print("Inference picks it up automatically at "
          f"{os.path.relpath(DEFAULT_WEIGHTS_PATH)}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--real-dir", nargs="+", default=["data/clean"],
                   help="folders of genuine captured figures (class 'real')")
    p.add_argument("--ai-dir", nargs="+", default=["data/ai_generated_real"],
                   help="folders of generator output (class 'ai_generated'); "
                        "use scripts/generate_ai_figures.py, NOT the synthetic "
                        "stand-ins in data/ai_generated_samples/")
    p.add_argument("--exclude-pmcids-from", nargs="*",
                   default=["data/evaluation_set/labels.json",
                            "data/heldout_packages/labels.json"],
                   help="labels.json files whose PMCIDs must not be trained on")
    p.add_argument("--out", default=DEFAULT_WEIGHTS_PATH)
    p.add_argument("--backbone", default="mobilenet_v3_small",
                   choices=["mobilenet_v3_small", "efficientnet_b0"])
    p.add_argument("--epochs", type=int, default=8)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--val-fraction", type=float, default=0.15)
    p.add_argument("--workers", type=int, default=0,
                   help="DataLoader workers (0 is safest on Windows)")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    return p


def main(argv=None) -> int:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    log = logging.getLogger("scholarguard")
    log.handlers[:] = [handler]
    log.setLevel(logging.INFO)
    return run(build_arg_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
