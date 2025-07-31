# app.py
import os
from flask import Flask, render_template,request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from auth import auth_bp, db, User  # imported from auth
from file_handler import read_file


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

    df = read_file(file_path)
    print(df.head())  # For testing purposes

    return "File uploaded and read successfully"

if __name__ == '__main__':
    app.run(debug=True)
