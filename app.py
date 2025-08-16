# app.py
import os
import logging
from flask import (
    Flask, render_template, request, redirect, url_for, flash, session
)
from werkzeug.utils import secure_filename

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
def dashboard():
    """
    Dashboard shows name and previously generated charts (if any).
    Also contains a Home button to upload another file.
    """
    user_name = session.get('name')
    # Show last 3 global charts (or per-user charts if you implement user-specific folders)
    graph_dir = GRAPH_FOLDER
    latest = []
    try:
        files = sorted(os.listdir(graph_dir), reverse=True)
        latest = [f'/static/graphs/{f}' for f in files[:3]]
    except FileNotFoundError:
        latest = []

    return render_template('dashboard.html', user={'name': user_name}, latest_charts=latest)


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


# ===== Run app =====
if __name__ == '__main__':
    app.run(debug=True)
