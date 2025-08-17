# app.py
import os
import logging
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from werkzeug.utils import secure_filename
from datetime import datetime

# Import your auth blueprint and login_required decorator from auth.py
# Make sure auth.py defines `auth_bp`, `db`, and `login_required`
from auth import auth_bp, db, login_required

# Import functions from single_compare module (provided below)
from single_compare import (
    detect_valid_data,
    extract_numeric_headers,
    generate_single_compare_chart,
    generate_scatter_plot
)
from dual_compare import generate_dual_compare_chart

from weighted_compare import generate_weighted_compare_chart
# ===== App setup =====
app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace_this_with_a_secure_random_secret'  # keep constant
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Custom Jinja2 filter to get filename from full path
@app.template_filter('basename')
def basename_filter(path):
    if path:
        return os.path.basename(path)
    return ''

# Create folders (project-root relative)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
GRAPH_FOLDER = os.path.join(BASE_DIR, 'static', 'graphs')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GRAPH_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed upload extensions
ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'}

# Register auth blueprint and initialize DB
app.register_blueprint(auth_bp)
db.init_app(app)
with app.app_context():
    db.create_all()

logging.basicConfig(level=logging.INFO)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Chart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("charts", lazy=True))
# ===== Routes =====

@app.route('/', methods=['GET', 'POST'])
def home():
    """
    Home page:
    - GET: show upload form and optional info.
    - POST: upload file (saved to uploads/) and store path in session then show home again
            (feature buttons will redirect to login or dashboard based on auth state).
    """
    if request.method == 'POST':
        # handle upload
        if 'file' not in request.files:
            flash("No file part in request.", "warning")
            return redirect(request.url)

        file = request.files['file']
        if not file or file.filename == '':
            flash("No file selected.", "warning")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Allowed: csv, xls, xlsx", "danger")
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            session['uploaded_file_path'] = file_path
            flash("File uploaded successfully. Now choose a feature (you will be asked to log in if necessary).", "success")
            return redirect(url_for('home'))
        except Exception as e:
            logging.exception("Error saving uploaded file")
            flash(f"Error saving file: {e}", "danger")
            return redirect(request.url)

    # GET: show homepage
    uploaded = session.get('uploaded_file_path')
    return render_template('home.html', uploaded_file=uploaded)


@app.route('/check_login_and_redirect')
def check_login_and_redirect():
    """
    When user clicks a feature after uploading:
    - If not logged in -> go to login page (after login user can go to dashboard).
    - If logged in -> go to dashboard directly.
    """
    if 'email' not in session:
        flash("Please log in to continue.", "info")
        return redirect(url_for('auth.login'))
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
@app.route('/dashboard')
@login_required
def dashboard():
    user_name = session.get('name')
    user_id = session.get('user_id')

    charts = Chart.query.filter_by(user_id=user_id)\
                        .order_by(Chart.created_at.desc())\
                        .limit(3).all()
    latest = [f"/static/graphs/{c.filename}" for c in charts]

    return render_template('dashboard.html',
                           user={'name': user_name},
                           latest_charts=latest)


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('home'))


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """
    Upload route accessible from dashboard (if you want to allow upload from dashboard),
    but since we support upload on home page, this route can be optional.
    Kept for compatibility.
    """
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part in request.", "warning")
            return redirect(request.url)
        file = request.files['file']
        if not file or file.filename == '':
            flash("No file selected.", "warning")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Invalid file type. Allowed: csv, xls, xlsx", "danger")
            return redirect(request.url)
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            session['uploaded_file_path'] = file_path
            flash("File uploaded successfully.", "success")
            return redirect(url_for('single_compare'))
        except Exception as e:
            logging.exception("Error saving uploaded file")
            flash(f"Error saving file: {e}", "danger")
            return redirect(request.url)

    return render_template('upload.html')


# === single_compare route: robust version with validation and error handling ===
@app.route('/single_compare', methods=['GET', 'POST'])
@login_required
def single_compare():
    """
    GET: Show dropdown populated with numeric headers extracted from the uploaded file.
    POST: Validate selection and generate a chart (saved to static/graphs) and show it.
    """
    file_path = session.get('uploaded_file_path')

    # If no file saved in session, ask user to upload
    if not file_path or not os.path.exists(file_path):
        flash("No uploaded file found. Please upload a file first.", "warning")
        return redirect(url_for('home'))

    # Try to read numeric headers for the dropdown (fail gracefully)
    try:
        headers = extract_numeric_headers(file_path)
    except Exception as e:
        logging.exception("Failed to extract headers")
        flash(f"Failed to read uploaded file: {e}", "danger")
        return redirect(url_for('home'))

    if not headers:
        flash("Uploaded file does not contain numeric columns to compare.", "danger")
        return redirect(url_for('home'))

    # POST: user selected parameter & preference -> generate chart
    if request.method == 'POST':
        parameter = request.form.get('parameter')
        preference = request.form.get('preference', 'lower')

    # Bar chart range
    try:
        min_value = float(request.form.get('min_value')) if request.form.get('min_value') else None
    except ValueError:
        min_value = None
    try:
        max_value = float(request.form.get('max_value')) if request.form.get('max_value') else None
    except ValueError:
        max_value = None

    # Scatter range
    try:
        scatter_min = float(request.form.get('scatter_min_value')) if request.form.get('scatter_min_value') else None
    except ValueError:
        scatter_min = None
    try:
        scatter_max = float(request.form.get('scatter_max_value')) if request.form.get('scatter_max_value') else None
    except ValueError:
        scatter_max = None

    try:
        top_n = int(request.form.get('top_n', 10))
    except Exception:
        top_n = 10

    # Decide which button was pressed
    if 'generate_scatter' in request.form:
        try:
            filename = generate_scatter_plot(
                file_path,
                parameter,
                preference=preference,
                min_value=scatter_min,
                max_value=scatter_max
            )
            chart_url = url_for('static', filename=f'graphs/{filename}')
            flash("Scatter plot generated successfully.", "success")
            return render_template('single_compare.html', headers=headers, chart_url=chart_url)
        except Exception as e:
            logging.exception("Error generating scatter plot")
            flash(f"Error generating scatter plot: {e}", "danger")
            return render_template('single_compare.html', headers=headers)

    # Else: generate bar chart
    try:
        filename = generate_single_compare_chart(
            file_path,
            parameter,
            top_n=top_n,
            preference=preference,
            min_value=min_value,
            max_value=max_value
        )
        chart_url = url_for('static', filename=f'graphs/{filename}')
        flash("Bar chart generated successfully.", "success")
        return render_template('single_compare.html', headers=headers, chart_url=chart_url)
    except Exception as e:
        logging.exception("Error generating bar chart")
        flash(f"Error generating bar chart: {e}", "danger")
        return render_template('single_compare.html', headers=headers)

@app.route('/dual_compare', methods=['GET', 'POST'])
@login_required
def dual_compare():
    """
    Dual parameter comparison:
    - GET: show two dropdowns for parameter selection + min/max fields.
    - POST: filter dataset by constraints for both parameters and display chart.
    """
    file_path = session.get('uploaded_file_path')

    if not file_path or not os.path.exists(file_path):
        flash("No uploaded file found. Please upload a file first.", "warning")
        return redirect(url_for('home'))

    try:
        headers = extract_numeric_headers(file_path)
    except Exception as e:
        logging.exception("Failed to extract headers for dual compare")
        flash(f"Failed to read uploaded file: {e}", "danger")
        return redirect(url_for('home'))

    if not headers:
        flash("Uploaded file does not contain numeric columns to compare.", "danger")
        return redirect(url_for('home'))

    chart_url = None

    if request.method == 'POST':
        param1 = request.form.get('parameter1')
        param2 = request.form.get('parameter2')

        # Min/max values for both parameters
        try:
            min1 = float(request.form.get('min1')) if request.form.get('min1') else None
        except ValueError:
            min1 = None
        try:
            max1 = float(request.form.get('max1')) if request.form.get('max1') else None
        except ValueError:
            max1 = None
        try:
            min2 = float(request.form.get('min2')) if request.form.get('min2') else None
        except ValueError:
            min2 = None
        try:
            max2 = float(request.form.get('max2')) if request.form.get('max2') else None
        except ValueError:
            max2 = None

        try:
            top_n = int(request.form.get('top_n', 10))
        except Exception:
            top_n = 10

        try:
            filename = generate_dual_compare_chart(
                file_path,
                param1,
                param2,
                min1=min1, max1=max1,
                min2=min2, max2=max2,
                top_n=top_n
            )
            chart_url = url_for('static', filename=f'graphs/{filename}')
            flash("Dual parameter chart generated successfully.", "success")
        except Exception as e:
            logging.exception("Error generating dual parameter chart")
            flash(f"Error generating dual parameter chart: {e}", "danger")

    return render_template('dual_compare.html', headers=headers, chart_url=chart_url)

@app.route("/weighted_compare", methods=["GET", "POST"])
@login_required
def weighted_compare():
    file_path = session.get("uploaded_file_path")
    if not file_path or not os.path.exists(file_path):
        flash("No uploaded file found. Please upload a file first.", "danger")
        return redirect(url_for("home"))

    try:
        from single_compare import detect_valid_data
        df, numeric_df = detect_valid_data(file_path)
    except Exception as e:
        flash(f"Failed to read uploaded file: {e}", "danger")
        return redirect(url_for("dashboard"))

    headers = numeric_df.columns.tolist() if not numeric_df.empty else []
    if not headers:
        flash("No numeric parameters available in the uploaded file.", "danger")
        return redirect(url_for("dashboard"))

    chart_url = None
    if request.method == "POST":
        try:
            # Number of companies
            top_n = int(request.form.get("top_n", 10))

            # Collect parameter blocks dynamically
            params, weights, prefs, ranges = [], [], [], []

            for i in range(1, min(len(headers), 5) + 1):
                param = request.form.get(f"param{i}")
                if not param:
                    continue  # skip if not selected

                # Default weight = 0 if blank
                try:
                    weight = float(request.form.get(f"weight{i}", 0))
                except ValueError:
                    weight = 0

                # Default preference = higher
                pref = request.form.get(f"pref{i}") or "higher"

                # Default min/max from dataset if blank
                col_data = numeric_df[param].dropna()
                try:
                    min_val = float(request.form.get(f"min{i}")) if request.form.get(f"min{i}") else col_data.min()
                except ValueError:
                    min_val = col_data.min()

                try:
                    max_val = float(request.form.get(f"max{i}")) if request.form.get(f"max{i}") else col_data.max()
                except ValueError:
                    max_val = col_data.max()

                params.append(param)
                weights.append(weight)
                prefs.append(pref)
                ranges.append((min_val, max_val))

            # Advanced options: weighted score constraints
            min_score = request.form.get("min_score")
            max_score = request.form.get("max_score")
            min_score = float(min_score) if min_score else None
            max_score = float(max_score) if max_score else None

            # Generate chart
            chart_file = generate_weighted_compare_chart(
                file_path,
                params=params,
                weights=weights,
                preferences=prefs,
                ranges=ranges,
                top_n=top_n,
                min_score=min_score,
                max_score=max_score
            )
            chart_url = f"/static/graphs/{chart_file}"

        except Exception as e:
            flash(str(e), "danger")

    return render_template(
        "weighted_compare.html",
        headers=headers,
        param_limit=min(len(headers), 5),
        chart_url=chart_url
    )


# ===== Run app =====
if __name__ == '__main__':
    app.run(debug=True)
