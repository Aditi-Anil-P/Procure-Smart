# app.py
import os
from flask import Flask, render_template,request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from auth import auth_bp, db, User  # imported from auth
from file_handler import read_file
from single_compare import generate_single_compare_chart, detect_valid_data


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.secret_key = 'secret'

db.init_app(app)
app.register_blueprint(auth_bp)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    if 'name' in session:
        return render_template('dashboard.html',user={'name': session['name']})
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['csv_file']
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)
    session['uploaded_file_path'] = file_path
    df = read_file(file_path)
    print(df.head())  # For testing purposes
    return redirect('/single_compare')

@app.route('/single_compare', methods=['GET', 'POST'])
def single_compare():
    file_path = session.get('uploaded_file_path')  

    if not file_path:
        return "No uploaded file found in session."  

    if request.method == 'POST':
        parameter = request.form['parameter']  
        preference = request.form['preference']  # 'higher' or 'lower'

        try:
            df, numeric_df = detect_valid_data(file_path)  
            chart_path = generate_single_compare_chart(df, numeric_df, parameter, preference=preference)
            return render_template('result.html', chart_path=chart_path)
        except Exception as e:
            return f"Error processing chart: {str(e)}"


    return render_template('single_compare.html')


if __name__ == '__main__':
    app.run(debug=True)
