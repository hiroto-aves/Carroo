from flask import Blueprint, render_template, request, redirect, url_for, session
import sqlite3
import os
from .database import DATABASE_PATH

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE username = ? AND password = ?", (username, password))
        result = cursor.fetchone()
        conn.close()

        if result:
            session['user_id'] = username
            session['role'] = result[0]
            if session['role'] == 'admin':
                return redirect(url_for('views.admin_dashboard'))
            else:
                return redirect(url_for('views.register_job'))
        else:
            error = 'ユーザー名またはパスワードが間違っています。'
            return render_template('auth/login.html', error=error)
    
    return render_template('auth/login.html')