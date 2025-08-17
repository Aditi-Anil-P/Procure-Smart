import os
import uuid
import logging
import matplotlib.pyplot as plt
import numpy as np
from chart_utils import cleanup_old_charts

from single_compare import detect_valid_data, _detect_label_column, apply_dark_theme

logging.basicConfig(level=logging.INFO)

GRAPH_FOLDER = os.path.join("static", "graphs")
os.makedirs(GRAPH_FOLDER, exist_ok=True)


def scale(data, reverse=False):
    min_val, max_val = np.nanmin(data), np.nanmax(data)
    if max_val - min_val == 0:
        return [0] * len(data)
    if reverse:
        return [1 - (x - min_val) / (max_val - min_val) for x in data]
    else:
        return [(x - min_val) / (max_val - min_val) for x in data]


def generate_weighted_compare_chart(file_path, params, weights, preferences, ranges,
                                    top_n=10, min_score=None, max_score=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid numeric data found in file.")

    # Validate params
    for p in params:
        if p not in numeric_df.columns:
            raise ValueError(f"Parameter '{p}' not found in file.")

    # Detect label column
    label_col = _detect_label_column(df, numeric_df.columns.tolist())
    if label_col is None:
        raise ValueError("No label/identifier column found.")

    # Prepare working DataFrame
    working = df.copy().reset_index(drop=True)
    for p in params:
        working[p] = numeric_df[p]
    working = working.dropna(subset=params)

    # Apply per-parameter ranges
    for idx, p in enumerate(params):
        min_val, max_val = ranges[idx]
        if min_val is not None:
            working = working[working[p] >= min_val]
        if max_val is not None:
            working = working[working[p] <= max_val]

    if working.empty:
        raise ValueError("No companies satisfy the selected parameter constraints.")

    # Normalize weights
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("Sum of weights must be greater than 0.")
    weights = [w / total_weight for w in weights]

    # Compute weighted score (first pass, full set)
    scores_per_param = []
    for idx, p in enumerate(params):
        reverse = (preferences[idx] == "lower")
        scaled = scale(working[p].tolist(), reverse=reverse)
        weighted = [s * weights[idx] for s in scaled]
        scores_per_param.append(weighted)

    working["WeightedScore"] = np.sum(scores_per_param, axis=0)

    # Apply global weighted score filter
    if min_score is not None:
        working = working[working["WeightedScore"] >= min_score]
    if max_score is not None:
        working = working[working["WeightedScore"] <= max_score]

    if working.empty:
        raise ValueError("No companies remain after applying weighted score constraints.")

    # Sort and truncate
    working = working.sort_values(by="WeightedScore", ascending=False).head(top_n)

    # === Recompute contributions for trimmed set ===
    contribs = []
    for idx, p in enumerate(params):
        reverse = (preferences[idx] == "lower")
        scaled = scale(working[p].tolist(), reverse=reverse)
        weighted = [s * weights[idx] for s in scaled]
        contribs.append(weighted)

    # --- Plot (stacked contributions) ---
    apply_dark_theme()
    labels = working[label_col].astype(str).tolist()

    colors = ["#FF6F61", "#FFD54F", "#4FC3F7", "#81C784", "#BA68C8"]  # bright colors
    fig_width = max(10, min(24, 0.7 * len(labels)))
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    bottom = np.zeros(len(labels))
    for idx, contrib in enumerate(contribs):
        ax.bar(labels, contrib, bottom=bottom,
               color=colors[idx % len(colors)], label=params[idx])
        bottom += contrib

    ax.set_ylabel("Weighted Score")
    ax.set_title("Weighted Parameter Comparison (Stacked by Parameter)")
    plt.xticks(rotation=90)

    # White legend text
    legend = ax.legend(title="Parameters", bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.setp(legend.get_texts(), color="white")
    plt.setp(legend.get_title(), color="white")

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28 if len(labels) <= 12 else 0.36, right=0.82)

    filename = f"{uuid.uuid4().hex[:10]}_weighted_compare.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()
    cleanup_old_charts(limit=3)

    logging.info("Saved weighted compare chart to %s", full_path)
    return filename

