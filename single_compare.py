# single_compare.py

import pandas as pd
import matplotlib.pyplot as plt
import os
import uuid

UPLOAD_FOLDER = 'uploads'
GRAPH_FOLDER = 'static/graphs'

# Ensure the folder for saving graphs exists
os.makedirs(GRAPH_FOLDER, exist_ok=True)

def detect_valid_data(file_path):
    """
    Detect the valid header row (with >=2 columns),
    and extract numeric data starting below it.
    """
    if file_path.endswith('.csv'):
        raw_df = pd.read_csv(file_path, header=None)
    else:
        raw_df = pd.read_excel(file_path, header=None)

    for idx, row in raw_df.iterrows():
        if row.dropna().shape[0] >= 2:
            # Try parsing the rows below into numeric
            data = raw_df.iloc[idx + 1:]
            data = data.apply(pd.to_numeric, errors='coerce')
            data = data.dropna(axis=1, how='all').dropna(axis=0, how='all')
            if data.shape[1] >= 2:
                headers = raw_df.iloc[idx]
                data.columns = headers[:data.shape[1]]
                return data.reset_index(drop=True)
    
    return pd.DataFrame()  # return empty if no suitable data found


def get_available_parameters(df):
    """
    Return a list of column names that have numeric values.
    """
    numeric_cols = df.select_dtypes(include=['int', 'float']).columns.tolist()
    return numeric_cols


def get_company_count(df):
    """
    Return the number of companies (rows).
    """
    return df.shape[0]


def generate_single_compare_chart(df, parameter, top_n=10, preference='lower'):
    """
    Generate a bar chart comparing companies by a single parameter.
    Parameters:
        - df: cleaned DataFrame
        - parameter: column name selected
        - top_n: number of companies to display
        - preference: 'lower' or 'higher' value preferred
    """
    if parameter not in df.columns:
        raise ValueError("Parameter not found in DataFrame")

    sorted_df = df.sort_values(by=parameter, ascending=(preference == 'lower'))
    limited_df = sorted_df.head(min(top_n, len(sorted_df)))

    plt.figure(figsize=(10, 6))
    plt.bar(limited_df.index.astype(str), limited_df[parameter], color='skyblue')
    plt.xlabel('Company Index')
    plt.ylabel(parameter)
    plt.title(f'{parameter} Comparison - Top {top_n} ({preference} preferred)')
    plt.xticks(rotation=45)
    plt.tight_layout()

    file_id = str(uuid.uuid4())
    img_path = os.path.join(GRAPH_FOLDER, f'{file_id}.png')
    plt.savefig(img_path)
    plt.close()

    return img_path

