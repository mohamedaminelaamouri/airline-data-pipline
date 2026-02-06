from __future__ import annotations

import argparse
from datetime import datetime


def main() -> None:
    parser = argparse.ArgumentParser(prog="yno_ml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train", help="Train model (sklearn) from CSV and write a versioned run")
    t.add_argument("--data", type=str, default="data/Airline_Delay_Cause_Cpt.csv")
    t.add_argument("--out-root", type=str, default="models/runs")
    t.add_argument("--backend", type=str, default="sklearn", choices=["sklearn"])
    t.add_argument("--target-threshold", type=float, default=0.20)
    t.add_argument("--min-recall", type=float, default=0.90)
    t.add_argument("--sample-weight", type=str, default="sqrt_flights", choices=["none", "flights", "sqrt_flights"])

    a = sub.add_parser("alert", help="Score a (year, month) and write alerts CSV")
    a.add_argument("--year", type=int, required=True)
    a.add_argument("--month", type=int, required=True)
    a.add_argument("--cutoff", type=float, default=0.20)
    a.add_argument("--history", type=str, default="data/Airline_Delay_Cause_Cpt.csv")
    a.add_argument("--run-dir", type=str, default="")
    a.add_argument("--out", type=str, default="reports/alerts_latest.csv")
    a.add_argument("--webhook-url", type=str, default="", help="Optional: POST a JSON summary to this URL")

    c = sub.add_parser("compare", help="Train sklearn backend and write metrics CSV")
    c.add_argument("--data", type=str, default="data/Airline_Delay_Cause_Cpt.csv")
    c.add_argument("--out", type=str, default="reports/backend_comparison.csv")
    c.add_argument("--out-root", type=str, default="models/runs")
    c.add_argument("--backends", type=str, default="sklearn")
    c.add_argument("--target-threshold", type=float, default=0.20)
    c.add_argument("--min-recall", type=float, default=0.90)
    c.add_argument("--sample-weight", type=str, default="sqrt_flights", choices=["none", "flights", "sqrt_flights"])

    args = parser.parse_args()

    if args.cmd == "train":
        import json

        from .multi_train import MultiTrainConfig, train_and_save

        out_dir = train_and_save(
            backend=str(args.backend),
            data_path=str(args.data),
            out_root=str(args.out_root),
            cfg=MultiTrainConfig(
                target_threshold=float(args.target_threshold),
                min_recall=float(args.min_recall),
                sample_weight=str(args.sample_weight),
            ),
        )
        print("OK: training done")
        print("Run:", str(out_dir))

        metrics_path = out_dir / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            cutoff = metrics.get("cutoff", {}).get("thr")
            if cutoff is not None:
                print("Recommended cutoff:", cutoff)
        return

    if args.cmd == "alert":
        from pathlib import Path

        import pandas as pd

        from .alerting import score_month_to_csv
        from .notify import WebhookNotification, post_webhook_json

        run_dir = Path(args.run_dir) if args.run_dir else None
        out_path = score_month_to_csv(
            year=int(args.year),
            month=int(args.month),
            cutoff=float(args.cutoff),
            history_csv=str(args.history),
            run_dir=run_dir,
            out_csv=str(args.out),
        )
        print("OK: scoring done")
        print("Output:", str(out_path))

        if str(args.webhook_url).strip():
            df = pd.read_csv(out_path)
            payload = {
                "type": "yno_ml_alerts",
                "generated_at": datetime.now().isoformat(),
                "year": int(args.year),
                "month": int(args.month),
                "cutoff": float(args.cutoff),
                "run_dir": str(run_dir) if run_dir else "",
                "n_rows": int(len(df)),
                "n_alerts": int((df.get("prediction", 0) == 1).sum()) if "prediction" in df.columns else None,
                "top10": df.head(10).to_dict(orient="records"),
            }
            post_webhook_json(WebhookNotification(url=str(args.webhook_url).strip()), payload)
            print("OK: webhook sent")
        return

    if args.cmd == "compare":
        from .compare import CompareConfig, compare_backends
        from .multi_train import MultiTrainConfig

        backends = tuple([b.strip() for b in str(args.backends).split(",") if b.strip()])
        out_path = compare_backends(
            CompareConfig(
                data_path=str(args.data),
                out_root=str(args.out_root),
                out_csv=str(args.out),
                backends=backends,
                train_cfg=MultiTrainConfig(
                    target_threshold=float(args.target_threshold),
                    min_recall=float(args.min_recall),
                    sample_weight=str(args.sample_weight),
                ),
            )
        )
        print("OK: comparison written")
        print("Output:", str(out_path))
        return


if __name__ == "__main__":
    main()
