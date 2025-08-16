import os
import uuid
import logging
import matplotlib.pyplot as plt

# Import helper functions from single_compare
from single_compare import detect_valid_data, extract_numeric_headers, _detect_label_column, apply_dark_theme

logging.basicConfig(level=logging.INFO)

GRAPH_FOLDER = os.path.join('static', 'graphs')
os.makedirs(GRAPH_FOLDER, exist_ok=True)


def generate_dual_compare_chart(file_path, param1, param2,
                                min1=None, max1=None,
                                min2=None, max2=None,
                                top_n=10):

    """
    Generates a dual-axis bar chart comparing two parameters side-by-side
    with independent Y-axes.
    Filters rows based on given ranges and removes NaNs in either parameter.
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid data found in file.")

    # Check parameters exist
    for p in [param1, param2]:
        if p not in numeric_df.columns:
            raise ValueError(f"Parameter '{p}' not found in numeric columns.")

    # Detect label column
    label_col = _detect_label_column(df, numeric_df.columns.tolist())
    if label_col is None:
        raise ValueError("No label/identifier column found.")

    # Merge numeric values
    working = df.copy().reset_index(drop=True)
    working[param1] = numeric_df[param1]
    working[param2] = numeric_df[param2]

    # Drop rows with NaN in either
    working = working.dropna(subset=[param1, param2])

    # Apply ranges for param1
    if min1 is not None:
        working = working[working[param1] >= min1]
    if max1 is not None:
        working = working[working[param1] <= max1]

    # Apply ranges for param2
    if min2 is not None:
        working = working[working[param2] >= min2]
    if max2 is not None:
        working = working[working[param2] <= max2]

    if working.empty:
        raise ValueError("No companies found within the specified constraints.")

    # Sort for consistent plotting (optional)
    working = working.sort_values(by=param1, ascending=False)
    
    # Apply top_n cap
    top_n = max(1, min(int(top_n), len(working)))  # clamp to valid range
    working = working.head(top_n)

    # Apply theme
    apply_dark_theme()

    # --- Plot dual-axis bar chart ---
    labels = working[label_col].astype(str).tolist()
    n = len(labels)

    # Wider fig for more labels; cap for sanity
    fig_width = max(10, min(24, 0.7 * n))   # ~0.7 inch per label
    fig, ax1 = plt.subplots(figsize=(fig_width, 6))

    x = range(n)
    color1 = "#00bcd4"
    color2 = "#ff9800"

    ax1.bar([i - 0.2 for i in x], working[param1], width=0.4, color=color1, label=param1)
    ax1.set_ylabel(param1, color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)

    ax2 = ax1.twinx()
    ax2.bar([i + 0.2 for i in x], working[param2], width=0.4, color=color2, label=param2)
    ax2.set_ylabel(param2, color=color2)
    ax2.tick_params(axis='y', labelcolor=color2)

    # Fully vertical labels + extra bottom space so they don’t pile or get cut
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation='vertical', ha='center', fontsize=8)

    plt.title(f"{param1} vs {param2} Comparison")

    # Give labels breathing room AFTER setting ticks
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28 if n <= 12 else 0.36)  # a bit more space when many labels


    filename = f"{uuid.uuid4().hex[:10]}_dual_compare.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()

    logging.info(f"Saved dual compare chart to %s", full_path)
    return filename
