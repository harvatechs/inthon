import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np


def main():
    benchmarks_dir = Path(__file__).parent
    root_dir = benchmarks_dir.parent
    output_dir = root_dir / "docs" / "assets" / "graphs"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Style presets
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Inter", "Segoe UI", "Arial", "DejaVu Sans"]
    plt.rcParams["figure.facecolor"] = "#ffffff"
    plt.rcParams["axes.facecolor"] = "#f8fafc"
    plt.rcParams["axes.edgecolor"] = "#cbd5e1"
    plt.rcParams["axes.linewidth"] = 1.0
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.color"] = "#e2e8f0"
    plt.rcParams["grid.linestyle"] = "--"
    plt.rcParams["grid.linewidth"] = 0.5
    plt.rcParams["xtick.color"] = "#475569"
    plt.rcParams["ytick.color"] = "#475569"
    plt.rcParams["axes.labelcolor"] = "#1e293b"
    plt.rcParams["axes.titlecolor"] = "#0f172a"

    # Color Palette
    colors = {
        "nl": "#94a3b8",  # Slate (Natural Language)
        "json": "#38bdf8",  # Sky Blue (JSON Plan)
        "python": "#3b82f6",  # Royal Blue (Python)
        "inthon": "#10b981",  # Emerald Green (INTHON)
        "success": "#10b981",  # Emerald
        "danger": "#ef4444",  # Rose Red
    }

    # ==========================================
    # 1. Generate Token Efficiency Graph
    # ==========================================
    token_eff_path = benchmarks_dir / "results_token_efficiency.json"
    if token_eff_path.exists():
        with open(token_eff_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tasks = []
        nl_tokens = []
        json_tokens = []
        python_tokens = []
        inthon_tokens = []

        for item in data:
            tasks.append(item["task"].replace("_", " ").title())
            reps = item["representations"]
            nl_tokens.append(reps["natural_language"]["tokens"])
            json_tokens.append(reps["json_plan"]["tokens"])
            python_tokens.append(reps["python"]["tokens"])
            inthon_tokens.append(reps["inthon"]["tokens"])

        x = np.arange(len(tasks))
        width = 0.2

        fig, ax = plt.subplots(figsize=(9, 5))
        rects1 = ax.bar(
            x - 1.5 * width,
            nl_tokens,
            width,
            label="Natural Language",
            color=colors["nl"],
        )
        rects2 = ax.bar(
            x - 0.5 * width,
            json_tokens,
            width,
            label="JSON Tool Plan",
            color=colors["json"],
        )
        rects3 = ax.bar(
            x + 0.5 * width,
            python_tokens,
            width,
            label="Python Code Gen",
            color=colors["python"],
        )
        rects4 = ax.bar(
            x + 1.5 * width,
            inthon_tokens,
            width,
            label="INTHON Layer",
            color=colors["inthon"],
        )

        ax.set_ylabel(
            "Semantics Token Count (Lower is Better)",
            fontsize=11,
            fontweight="semibold",
            labelpad=10,
        )
        ax.set_title(
            "Token Efficiency Comparison across Agent Tasks",
            fontsize=14,
            fontweight="bold",
            pad=15,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(tasks, fontsize=10, fontweight="semibold")
        ax.legend(
            frameon=True, facecolor="#ffffff", edgecolor="#cbd5e1", loc="upper right"
        )

        # Add value labels on top of the bars
        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(
                    f"{height}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#334155",
                )

        autolabel(rects1)
        autolabel(rects2)
        autolabel(rects3)
        autolabel(rects4)

        plt.tight_layout()
        plt.savefig(output_dir / "token_efficiency.png", dpi=300)
        plt.close()
        print("Generated token_efficiency.png")

    # ==========================================
    # 2. Generate Workflow Correctness (Latency) Graph
    # ==========================================
    correctness_path = benchmarks_dir / "results_workflow_correctness.json"
    if correctness_path.exists():
        with open(correctness_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        workflows = []
        latencies = []

        for item in data:
            workflows.append(item["task"].replace("_", " ").title())
            latencies.append(item["duration_ms"])

        fig, ax = plt.subplots(figsize=(8, 4.5))

        # Log scale might be helpful if there's massive variance (e.g. 500ms vs 3ms)
        # But we'll do standard bar with clear visual markings
        bars = ax.barh(workflows, latencies, height=0.5, color=colors["python"])

        ax.set_xlabel(
            "Execution Latency (milliseconds) - Sandboxed Sandbox",
            fontsize=11,
            fontweight="semibold",
            labelpad=10,
        )
        ax.set_title(
            "INTHON Compilation & Runtime Latency",
            fontsize=14,
            fontweight="bold",
            pad=15,
        )

        for bar in bars:
            width = bar.get_width()
            ax.annotate(
                f" {width:.2f} ms",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(3, 0),  # 3 points horizontal offset
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=9,
                fontweight="semibold",
                color="#334155",
            )

        plt.tight_layout()
        plt.savefig(output_dir / "latency.png", dpi=300)
        plt.close()
        print("Generated latency.png")

    # ==========================================
    # 3. Generate Safety Validation Graph
    # ==========================================
    safety_path = benchmarks_dir / "results_safety.json"
    if safety_path.exists():
        with open(safety_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        attacks = []
        blocked_status = []
        error_types = []

        for item in data:
            attacks.append(item["attack"].replace("_", " ").title())
            blocked_status.append(1 if item["blocked"] else 0)
            error_types.append(item.get("error_type", "None"))

        fig, ax = plt.subplots(figsize=(9, 4.5))

        y_pos = np.arange(len(attacks))
        bars = ax.barh(
            y_pos,
            blocked_status,
            height=0.5,
            color=[
                colors["success"] if b == 1 else colors["danger"]
                for b in blocked_status
            ],
        )

        ax.set_yticks(y_pos)
        ax.set_yticklabels(attacks, fontsize=9, fontweight="semibold")
        ax.set_xlabel(
            "Exploit Block Status (1 = Blocked / Secure, 0 = Bypassed)",
            fontsize=11,
            fontweight="semibold",
            labelpad=10,
        )
        ax.set_title(
            "Security Sandbox Attack Resistance", fontsize=14, fontweight="bold", pad=15
        )
        ax.set_xlim(0, 1.2)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(
            ["Bypassed (Fail)", "Successfully Blocked (Pass)"],
            fontsize=10,
            fontweight="semibold",
        )

        for i, bar in enumerate(bars):
            width = bar.get_width()
            err_type = error_types[i]
            label_text = " SECURE " if width == 1 else " COMPROMISED "

            # Label with exception details
            ax.annotate(
                f" {label_text} ({err_type})",
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(5, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=9,
                fontweight="semibold",
                color="#334155",
            )

        plt.tight_layout()
        plt.savefig(output_dir / "safety.png", dpi=300)
        plt.close()
        print("Generated safety.png")


if __name__ == "__main__":
    main()
