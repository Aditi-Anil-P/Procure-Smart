import os
import uuid
import logging
import matplotlib.pyplot as plt
import numpy as np

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
    """
    Weighted comparison of up to 5 parameters with user-defined weights.
    Filters by per-parameter min/max and optional global score range.
    """
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

    # Scale each parameter and compute weighted score
    all_scores = []
    for idx, p in enumerate(params):
        reverse = (preferences[idx] == "lower")
        scaled = scale(working[p].tolist(), reverse=reverse)
        weighted = [s * weights[idx] for s in scaled]
        all_scores.append(weighted)

    # Aggregate weighted scores
    working["WeightedScore"] = np.sum(all_scores, axis=0)

    # Apply global weighted score filter
    if min_score is not None:
        working = working[working["WeightedScore"] >= min_score]
    if max_score is not None:
        working = working[working["WeightedScore"] <= max_score]

    if working.empty:
        raise ValueError("No companies remain after applying weighted score constraints.")

    # Sort by score and take top N
    working = working.sort_values(by="WeightedScore", ascending=False)
    working = working.head(top_n)

    # --- Plot ---
    apply_dark_theme()
    labels = working[label_col].astype(str).tolist()
    scores = working["WeightedScore"].tolist()

    fig_width = max(10, min(24, 0.7 * len(labels)))
    fig, ax = plt.subplots(figsize=(fig_width, 6))

    ax.bar(labels, scores, color="#4caf50")
    ax.set_ylabel("Weighted Score")
    ax.set_title("Weighted Parameter Comparison")
    plt.xticks(rotation=90)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28 if len(labels) <= 12 else 0.36)

    filename = f"{uuid.uuid4().hex[:10]}_weighted_compare.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()

    logging.info("Saved weighted compare chart to %s", full_path)
    return filename






