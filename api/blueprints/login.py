from flask import Blueprint, render_template

login_blueprint = Blueprint("login_blueprint", __name__, template_folder="templates")

@login_blueprint.route("/login")
def login():
    return render_template("login.html")