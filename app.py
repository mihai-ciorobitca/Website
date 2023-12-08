from flask import Flask, render_template, request, redirect,\
                  jsonify, url_for, session, Response, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
from tasks_function import get_tasks
from task_function import get_task
from create_function import get_create
from credits_function import get_credits
from flask_mail import Mail, Message
import secrets, re, requests, json
from datetime import datetime, timedelta
import pandas as pd
import os, io
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from random import randint
import urllib.request
import logging, random, smtplib

from email.mime.text import MIMEText

project_folder = os.path.expanduser('~/website')
load_dotenv(os.path.join(project_folder, '.env'))

ADMIN_USERNAME = os.getenv("USERNAME")
ADMIN_PASSWORD = os.getenv("PASSWORD")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.secret_key = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle' : 280}

mail = Mail(app)
db = SQLAlchemy(app)

class ClientsInfo(db.Model):
    username = db.Column(db.String(225), nullable=False, primary_key=True)
    password = db.Column(db.String(255), nullable=False)
    credits  = db.Column(db.Integer)
    email    = db.Column(db.String(255), nullable=False, unique=True)
    status   = db.Column(db.String(255), nullable=False)
    token    = db.Column(db.String(255), nullable=True)
    smtp_server = db.Column(db.String(255))
    smtp_email = db.Column(db.String(255))
    smtp_password = db.Column(db.String(255))
    def __init__(self, username, password, email):
        self.username = username
        self.password = generate_password_hash(password)
        self.credits  = 0
        self.email    = email
        self.status   = "unconfirmed"
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Campaign(db.Model):
    username = db.Column(db.String(255), db.ForeignKey('clients_info.username'), nullable=False)
    campaign_name = db.Column(db.String(255), nullable=False, primary_key=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    recipients = db.Column(db.Text)
    current_recipient = db.Column(db.String(255))
    campaign_status = db.Column(db.String(255), default='stopped')
    next_send = db.Column(db.String(255))
    user = db.relationship('ClientsInfo', backref=db.backref('campaigns', lazy=True))

class TasksInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_name = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(225), nullable=False)
    task_date = db.Column(db.Date)

    def __init__(self, task_name, username, task_date):
        self.task_name = task_name
        self.username = username
        self.task_date = task_date

class TaskTable(db.Model):
    task = db.Column(db.String(225), nullable=False, primary_key=True)
    def __init__(self, task):
        self.task = task

class ClientsTable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False)
    platform = db.Column(db.String(255), nullable=False)
    taskname = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    scraped_emails = db.Column(db.Integer, nullable=True)
    maximum_emails = db.Column(db.Integer, nullable=True)
    download = db.Column(db.String(255), nullable=True)

    def __init__(self, username, platform, taskname, url, scraped_emails=None, maximum_emails=None, download=None):
        self.username = username
        self.platform = platform
        self.taskname = taskname
        self.url = url
        self.scraped_emails = scraped_emails
        self.maximum_emails = maximum_emails
        self.download = download

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']
            # check if the username and email are unique
            user = ClientsInfo.query.filter_by(username=username).first()
            if user:
                return jsonify({"result": "exist-user"})
            user = ClientsInfo.query.filter_by(email=email).first()
            if user:
                return jsonify({"result": "exist-email"})
            # create new user
            new_user = ClientsInfo(username, password, email)
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            return str(e)
        return jsonify({"result": "unconfirmed"})
    return render_template("register.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not username == "" and not password == "":
            if (username, password) == (ADMIN_USERNAME, ADMIN_PASSWORD):
                session['is_admin'] = True
                return jsonify({"result": "admin"})
            user = ClientsInfo.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['username'] = username
                if user.status in ["confirmed", "special"]:
                    return jsonify({"result": "home"})
                else:
                    return jsonify({"result": "unconfirmed"})
            else:
                return jsonify({"result": "error"})
    return render_template("login.html")

@app.route('/home', methods=['GET', 'POST'])
def home():
    try:
        if 'username' in session:
            user = ClientsInfo.query.filter_by(username=session['username']).first()
            if user:
                return render_template('home.html', username=session['username'], credits=credits)
            session.clear()
            return 'User not exists'
        return redirect(url_for('login'))
    except Exception as e:
        return str(e)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if session.get('is_admin', False):
        users = ClientsInfo.query.all()
        return render_template('admin.html', users=users)
    return redirect(url_for('login'))

@app.route('/admin/buy_credits', methods=['POST'])
def buy_credits():
    username = request.form.get('username')
    credits = request.form.get('credits')
    user = ClientsInfo.query.get(username)
    user.credits += int(credits)
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/clear_credits', methods=['POST'])
def clear_credits():
    username = request.form.get('username')
    user = ClientsInfo.query.get(username)
    user.credits = 0
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/delete_account', methods=['POST'])
def delete_account():
    username = request.form.get('username')
    user = ClientsInfo.query.get(username)
    if user:
        db.session.delete(user)
        db.session.commit()
    return redirect('/admin')

@app.route('/admin/update_status', methods=['POST'])
def update_status():
    username = request.form.get('username')
    new_status = request.form.get('status')
    user = ClientsInfo.query.get(username)
    if user:
        user.status = new_status
        db.session.commit()
    return redirect('/admin')

@app.errorhandler(405)
def page_not_allowed(e):
    return render_template('error405.html'), 405

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error404.html'), 404

@app.errorhandler(500)
def under_maintenance(e):
    return render_template('error500.html'), 500

def generate_token(email):
    token = secrets.token_hex(nbytes=16)
    return token

def refund_email(receiver_email, supply, used, refund):
    msg = Message('Refund credits', sender=app.config['MAIL_USERNAME'], recipients=[receiver_email])
    msg.html = render_template('credits.html', supply=supply, used=used, refund=refund)
    mail.send(msg)

def send_email_recover(receiver_email, reset_link):
    msg = Message('Reset password', sender=app.config['MAIL_USERNAME'], recipients=[receiver_email])
    msg.body = f'Click this link to reset your password: {reset_link}'
    mail.send(msg)
    f'Click this link to reset your password: {reset_link}'

@app.route('/recover', methods=['GET', 'POST'])
def recover():
    if request.method == 'POST':
        email = request.form['email']
        user = ClientsInfo.query.filter_by(email=email).first()
        if user:
            # Generate a random token and store it in the user's account
            token = secrets.token_hex(16)
            user.token = token
            db.session.commit()
            session['token'] = token
            send_email_recover(email, f"https://website.com/reset/{token}")#change with website link
            return jsonify({"result": "successful"})
        return jsonify({"result": "failed"})
    return render_template("recover.html")

@app.route('/reset/<string:token>', methods=['GET', 'POST'])
def reset(token):
    if request.method == 'POST':
        user = ClientsInfo.query.filter_by(token=token).first()
        if user:
            new_password = request.form['password']
            user.set_password(new_password)
            user.token = None
            db.session.commit()
            return jsonify({"result": "successful"})
        else:
            return jsonify({"result": "wrong-token"})
    return render_template("reset.html", token=token)

@app.route('/retract', methods=['GET', 'POST'])
def retract():
    if request.method == 'POST':
        if 'username' in session:
            username=session['username']
            user = ClientsInfo.query.filter_by(username=username).first()
            platform_select = request.form['platform-select']
            credits_to_deduct = int(request.form['max-emails'])
              scrape_type   = request.form['scrape-type']
              maximum_emails= request.form['max-emails']
              tasks = get_tasks(user.username)
              name          = f"{{{session['username']}}}{request.form['task-name']}"
              scrape_info = request.form['scrape-info']
              created_tasks = [(task["scrape_info"], task["scrape_type"]) for task in tasks if task["status"] != 'N']
              if (not (scrape_info, scrape_type) in created_tasks) or len(created_tasks) == 0:
                  if get_credits() != 0:
                      get_create(name, scrape_info, scrape_type, maximum_emails)
                      user.credits -= credits_to_deduct
                      db.session.commit()
                      return jsonify({"result": "created", "credits": user.credits}), 200, {'content_type': 'application/json'}
                  return jsonify({"result": "no-credits", "credits": user.credits}), 200, {'content_type': 'application/json'}
              else:
                  return jsonify({"result": "duplicated", "credits": user.credits}), 200, {'content_type': 'application/json'}
        else:
            return jsonify({"result": "not-created", "credits": user.credits}), 200, {'content_type': 'application/json'}
    return redirect(url_for('home'))

@app.route('/retract-continue', methods=['GET', 'POST'])
def retract_continue():
    if request.method == 'POST':
        if 'username' in session:
            username=session['username']
            user = ClientsInfo.query.filter_by(username=username).first()
            if user.status != "special":
                credits_to_deduct = int(request.form['max-emails'])
                scrape_type   = request.form['scrape-type']
                maximum_emails= request.form['max-emails']
                tasks = get_tasks(user.username)
                scrape_info = int(request.form.get('task_id'))
                for task in tasks:
                    if task['id'] == scrape_info:
                        name = task['name']
                        match = re.search(r'\(\d+\)$', name)
                        if match:
                            number = int(match.group(0)[1:-1]) + 1
                            name = re.sub(r'\(\d+\)$', f'({number})', name)
                        else:
                            name += "(1)"
                if get_credits() != 0:
                    get_create(name, scrape_info, scrape_type, maximum_emails)
                    current_date = datetime.today()
                    new_task = TasksInfo(name, session["username"], current_date)
                    user.credits -= credits_to_deduct
                    db.session.add(new_task)
                    db.session.commit()
                    return redirect('/home', code=307)
                return jsonify({"result": "no-credits", "credits": user.credits}), 200, {'content_type': 'application/json'}
        else:
            return jsonify({"result": "not-created", "credits": user.credits}), 200, {'content_type': 'application/json'}
    return redirect(url_for('home'))

@app.route('/tasks_list', methods=['POST'])
def tasks_list():
    username = request.form.get('username')
    tasks = get_tasks(username)
    return render_template('tasks.html', tasks=tasks, username=username)

@app.route('/task_table', methods=['POST'])
def task_table():
    task_id = request.form.get('task_id')
    username = request.form.get('username_id')
    task = get_task(task_id)
    task['user'] = username
    if session.get('is_admin', False):
        task['user'] = "admin"
    info = task["id"]
    tasks = get_tasks(username)
    next_task = next((t for t in tasks
                        if t['scrape_info'] == str(info)), None)
    check = True
    user = ClientsInfo.query.filter_by(username=session['username']).first()
    if next_task is not None or user.status == "special":
        check = False
    if task["status"] == "C" and task["scraped_emails"] < task["maximum_emails"]:
        task_name = TaskTable.query.filter_by(task=task["name"]).first()
        if not task_name:
            user = ClientsInfo.query.filter_by(username=session['username']).first()
            user.credits += task["maximum_emails"] - task["scraped_emails"]
            new_task = TaskTable(task["name"])
            db.session.add(new_task)
            db.session.commit()
            refund_email(user.email, task["maximum_emails"], task["scraped_emails"], task["maximum_emails"] - task["scraped_emails"])
    return render_template('task.html', task=task, username=username, check=check)

@app.route('/continue_task', methods=['POST'])
def continue_task():
    if 'username' in session:
        username=session['username']
        user = ClientsInfo.query.filter_by(username=username).first()
        credits = user.credits
        task_id = request.form.get('task_id')
        task=get_task(task_id)
        return render_template('continue.html', task=task, credits=credits)

if __name__ == '__main__':
    app.run(debug=False)
