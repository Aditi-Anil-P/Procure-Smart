# single_compare.py
import os
import uuid
import logging
import pandas as pd
import matplotlib.pyplot as plt
from chart_utils import save_chart_metadata

logging.basicConfig(level=logging.INFO)

GRAPH_FOLDER = os.path.join('static', 'graphs')
os.makedirs(GRAPH_FOLDER, exist_ok=True)


def detect_valid_data(file_path):
    """
    Read uploaded file (csv/xls/xlsx), detect header row (first row with >=2 non-empty),
    assign headers and return (df, numeric_df).

    numeric_df is a cleaned numeric-only DataFrame (same row alignment as df),
    where common noise is removed:
      - currency symbols (₹ $ € £ ¥), common currency abbreviations (Rs, INR, USD, etc.)
      - commas (thousand separators), percent sign '%' (stripped but NOT converted to fraction)
      - parentheses like (1,200) are converted to -1200
      - excessive spaces / non-breaking spaces removed
    Non-numeric columns remain in `df` unchanged. `numeric_df` will have numeric values (or NaN).
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.csv':
        raw_df = pd.read_csv(file_path, header=None, dtype=object)
    elif ext == '.xls':
        raw_df = pd.read_excel(file_path, header=None, engine='xlrd', dtype=object)
    elif ext == '.xlsx':
        raw_df = pd.read_excel(file_path, header=None, engine='openpyxl', dtype=object)
    else:
        raise ValueError("Unsupported file format.")

    for idx, row in raw_df.iterrows():
        if row.dropna().shape[0] >= 2:
            headers = raw_df.iloc[idx].tolist()
            df = raw_df.iloc[idx + 1:].copy().reset_index(drop=True)

            # assign headers (truncate if header row longer; pad if shorter)
            if len(headers) >= df.shape[1]:
                df.columns = headers[: df.shape[1]]
            else:
                extra = [f"col_{i}" for i in range(len(headers), df.shape[1])]
                df.columns = headers + extra

            # drop columns that are completely empty
            df = df.dropna(axis=1, how='all')

            # Create a cleaned copy (strings normalized) for numeric conversion
            cleaned = df.copy()

            for col in cleaned.columns:
                # convert to str first (object/mixed types)
                s = cleaned[col].astype(str).fillna('').str.strip()

                # remove non-breaking space, trim
                s = s.str.replace('\u00A0', '', regex=False)

                # parentheses to negative e.g. (1,200) -> -1,200
                s = s.str.replace(r'^\((.*)\)$', r'-\1', regex=True)

                # remove currency symbols (₹, $, €, £, ¥) but keep the number
                s = s.str.replace(r'[\u20B9\$€£¥]', '', regex=True)

                # remove common currency abbreviations (Rs, Rs., INR, USD, EUR, GBP, YEN)
                s = s.str.replace(r'\b(Rs|Rs\.|INR|USD|EUR|GBP|YEN)\b', '', regex=True, case=False)

                # remove commas (thousand separators)
                s = s.str.replace(',', '', regex=False)

                # strip percent sign but DO NOT convert to 0-1 (user requested)
                s = s.str.replace('%', '', regex=False)

                # collapse any remaining internal whitespace
                s = s.str.replace(r'\s+', '', regex=True)

                cleaned[col] = s

            # Convert cleaned to numeric where possible. Keep rows aligned with df (we do not drop rows here).
            numeric_df = cleaned.apply(pd.to_numeric, errors='coerce')

            # drop columns that are all-NaN after cleaning (non-numeric columns will be removed here)
            numeric_df = numeric_df.dropna(axis=1, how='all')

            # Return original df (with headers preserved) and numeric_df aligned by row index
            return df.reset_index(drop=True), numeric_df.reset_index(drop=True)

    # nothing valid found
    return pd.DataFrame(), pd.DataFrame()



def extract_numeric_headers(file_path):
    """Return list of numeric column headers for dropdown."""
    df, numeric_df = detect_valid_data(file_path)
    if numeric_df.empty:
        return []
    return numeric_df.columns.tolist()


def _detect_label_column(df, numeric_cols):
    """Heuristic to choose label/name column."""
    keywords = ['name', 'company', 'seller', 'brand', 'product']
    for col in df.columns:
        if isinstance(col, str) and any(k in col.lower() for k in keywords):
            return col
    # first non-numeric
    for col in df.columns:
        if col not in numeric_cols:
            return col
    # fallback
    return df.columns[0] if len(df.columns) > 0 else None

def apply_dark_theme():
    plt.style.use('default')
    plt.rcParams.update({
        "figure.facecolor": "#0d1b2a",
        "axes.facecolor": "#1b263b",
        "axes.edgecolor": "#e0f7fa",
        "axes.labelcolor": "#e0f7fa",
        "axes.titleweight": "bold",
        "axes.titlecolor": "#80d0c7",
        "xtick.color": "#e0f7fa",
        "ytick.color": "#e0f7fa",
        "grid.color": "#e0f7fa",
        "grid.alpha": 0.2,
        "axes.grid": True,
        "figure.autolayout": True
    })



def generate_single_compare_chart(file_path, parameter, top_n=10, preference='lower', min_value=None, max_value=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid data found in file.")

    if parameter not in numeric_df.columns:
        raise ValueError(f"Parameter '{parameter}' not found in numeric columns.")

    # detect label column
    label_col = _detect_label_column(df, numeric_df.columns.tolist())
    if label_col is None:
        raise ValueError("No label/identifier column found to label chart.")

    # Build working df with cleaned numeric parameter
    working = df.copy().reset_index(drop=True)
    working[parameter] = numeric_df[parameter]
    working = working.dropna(subset=[parameter]).copy()

    # Apply min/max range filtering
    if min_value is not None:
        working = working[working[parameter] >= min_value]
    if max_value is not None:
        working = working[working[parameter] <= max_value]
    if working.empty:
        raise ValueError("No companies found within the specified range.")

    # Sort based on preference
    ascending = True if preference == 'lower' else False
    working = working.sort_values(by=parameter, ascending=ascending)

    # Truncate if more than 20 remain
    if len(working) > 20:
        if preference == 'lower':
            working = working.nsmallest(20, parameter)
        else:
            working = working.nlargest(20, parameter)

    # Apply user top_n
    top_n = max(1, min(int(top_n), len(working)))
    top = working.head(top_n)

    # Determine log scale
    vals = top[parameter].astype(float)
    use_log = False
    try:
        if vals.max() / max(vals.min(), 1e-9) > 1000:
            use_log = True
    except Exception:
        pass

    # Apply theme
    apply_dark_theme()

    # Plot
    plt.figure(figsize=(10, 6))
    bar_color = "#00bcd4" if preference == 'lower' else "#ff9800"
    plt.barh(top[label_col].astype(str), vals, color=bar_color, alpha=0.85)
    if use_log:
        plt.xscale('log')
        xlabel = f"{parameter} (log scale)"
    else:
        xlabel = parameter

    plt.xlabel(xlabel)
    plt.ylabel(label_col)
    plt.title(f"{parameter} comparison (top {top_n}) — preference: {preference}")
    plt.gca().invert_yaxis()

    filename = f"{uuid.uuid4().hex[:10]}_{parameter}_{preference}.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()
    save_chart_metadata(filename, limit=3) 

    logging.info(f"Saved chart to %s", full_path)
    return filename

def generate_scatter_plot(file_path, parameter, preference='lower', min_value=None, max_value=None):
    if not os.path.exists(file_path):
        raise FileNotFoundError("Uploaded file not found on server.")

    df, numeric_df = detect_valid_data(file_path)
    if df.empty or numeric_df.empty:
        raise ValueError("No valid data found in file.")

    if parameter not in numeric_df.columns:
        raise ValueError(f"Parameter '{parameter}' not found in numeric columns.")

    # Build working df with cleaned numeric parameter
    working = df.copy().reset_index(drop=True)
    working[parameter] = numeric_df[parameter]
    working = working.dropna(subset=[parameter]).copy()

    # Apply min/max range
    if min_value is not None:
        working = working[working[parameter] >= min_value]
    if max_value is not None:
        working = working[working[parameter] <= max_value]
    if working.empty:
        raise ValueError("No companies found within the specified scatter range.")

    # Sort values based on preference (optional for visual clarity)
    ascending = True if preference == 'lower' else False
    working = working.sort_values(by=parameter, ascending=ascending).reset_index(drop=True)

    # Apply theme
    apply_dark_theme()

    # Scatter plot with index on X-axis
    plt.figure(figsize=(10, 6))
    x_vals = range(len(working))
    y_vals = working[parameter].astype(float)
    point_color = "#80d0c7" if preference == 'lower' else "#ff9800"

    plt.scatter(x_vals, y_vals, color=point_color, alpha=0.85, edgecolor="#e0f7fa", linewidth=0.8, s=80)
    plt.xlabel("Company Index")
    plt.ylabel(parameter)
    plt.title(f"{parameter} Scatter Plot (Preference: {preference})")

    filename = f"{uuid.uuid4().hex[:10]}_{parameter}_scatter.png"
    full_path = os.path.join(GRAPH_FOLDER, filename)
    plt.savefig(full_path, facecolor=plt.gcf().get_facecolor())
    plt.close()
    cleanup_old_charts(limit=3)

    logging.info(f"Saved scatter plot to %s", full_path)
    return filename