from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import os
from sqlalchemy import orm
from random import randint


# Each Flask web application contains a secret key which used to sign session cookies
# for protection against cookie data tampering. It's very important that an attacker
# doesn't know the value of this secret key.
# See https://flask.palletsprojects.com/en/2.0.x/tutorial/deploy/#configure-the-secret-key

# See https://stackoverflow.com/questions/34902378/where-do-i-get-a-secret-key-for-flask
# for different methods to generate a random string
API_KEY = 'any-secret-key-you-choose'
DB_URL = 'sqlite:///users.db'

app = Flask(__name__)

app.config['SECRET_KEY'] = API_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)  # Instantiate the database passing the app to it

# Flask-Login
# https://flask-login.readthedocs.io/en/latest/
# YouTube video: https://www.youtube.com/watch?v=2dEM-s3mRLE
# Example: https://gist.github.com/bkdinoop/6698956
login_manager = LoginManager()  # Instantiate the Flask Login extension

# # Specify the default login URL in the Flask-Login
# login_manager.login_view = 'login'
# login_manager.login_message = u"Please log in to access this page."
# login_manager.setup_app(app)

login_manager.init_app(app)  # Initialise the manager passing the app to it


# CREATE TABLE IN DB
class User(UserMixin, db.Model):
    """
    To make implementing the user class easier, we inherit from UserMixin, which provides
    default implementations for all of these properties and methods.
    These are used internally by Flask Login to keep track of users and their state

    You can access these using, for example, "current_user.is_authenticated"

    is_authenticated
        This property should return True if the user is authenticated, i.e. they have provided
        valid credentials. (Only authenticated users will fulfill the criteria of login_required.)
    is_active
        This property should return True if this is an active user - in addition to being
        authenticated, they also have activated their account, not been suspended, or any
        condition your application has for rejecting an account. Inactive accounts may not log
        in (without being forced of course).
    is_anonymous
        This property should return True if this is an anonymous user. (Actual users should
        return False instead.)
    get_id()
        This method must return a unicode that uniquely identifies this user, and can be used to
        load the user from the user_loader callback. Note that this must be a unicode - if the
        ID is natively an int or some other type, you will need to convert it to unicode.
        Note that the primary key column must be named "id" for this function to work.
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(1000))
    name = db.Column(db.String(100))


# Create the database file and tables
with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    """
    This callback is used to reload the user object from the user ID stored in the session.
    It connects the abstract user that Flask Login uses with the actual users in the model
    It should take the unicode ID of a user, and return the corresponding user object.

    It should return None (not raise an exception) if the ID is not valid.
    (In that case, the ID will manually be removed from the session and processing will continue.)

    :param user_id: unicode user ID
    :return: user object
    """
    # return User.query.get(int(user_id))  # Deprecated

    with app.app_context():
        return db.session.get(entity=User, ident=user_id)


#   =======================================
#                  ROUTES
#   =======================================

@app.route('/')
def home():
    return render_template("index.html")


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Create a user and get the values from the HTML form
        user = User()
        user.name = request.form['name']
        user.email = request.form['email']
        password = request.form['password']

        # Check if the email is already registered
        if User.query.filter_by(email=user.email).first():
            flash(f"User {user.email} already exists!", 'info')
            flash("Log in instead.")
            return render_template("login.html")

        # Salting and Hashing Passwords
        # https://werkzeug.palletsprojects.com/en/1.0.x/utils/#module-werkzeug.security
        # Supported Hashing Algorithms
        # https://docs.python.org/3/library/hashlib.html
        #
        #  |   Always available |  Most platforms |
        #  ----------------------------------------
        #  | * md5              |  sha3_224       |
        #  | * sha1             |  sha3_256       |
        #  |   sha224           |  sha3_384       |
        #  |   sha256           |  sha3_512       |
        #  |   sha384           |  shake_128      |
        #  |   sha512           |  shake_256      |
        #  |   blake2b          |                 |
        #  |   blake2s          |                 |
        #    * DO NOT USE - vulnerable to attack
        salt_length = randint(16, 32)
        user.password = generate_password_hash(
            password,
            method='pbkdf2:sha3_512:100000',
            salt_length=salt_length
        )

        # Save the user in the database
        db.session.add(user)
        db.session.commit()

        # Log in and authenticate the user after adding details to database.
        login_user(user)
        flash('Logged in successfully.', 'info')
        return redirect(url_for('secrets', username=user.name))
    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Get the email value from the HTML form and find the user in the database
        email = request.form['email']
        password = request.form['password']

        # Make sure the user exists
        try:
            user = User.query.filter_by(email=email).first()
        except orm.exc.NoResultFound:
            # SQLAlchemy.orm exception
            flash(f"User {email} not found!", 'error')
            flash(f"Try again.")
            print(f"SQLAlchemy.orm exception: User {email} not found!")
            return render_template("login.html")

        if user:
            # Check the hashed password in the database against the input password
            if check_password_hash(pwhash=user.password, password=password):
                # Log in and authenticate the user
                login_user(user)

                # Flash Messages will show on the page that is redirected to (redirect only, not render_template)
                # as long as the HTML is coded of course.
                # See flash.html which is included in other html pages: {% include 'flash.html' %}
                #   optional category: 'message', 'info', 'warning'. 'error'
                flash('Logged in successfully.', 'info')

                # Warning: You MUST validate the value of the next parameter.
                # If you do not, your application will be vulnerable to open redirects.
                #   Example: A logged out user enters the URL: http://127.0.0.1:5008/secrets
                #   /secrets is protected, so the user is redirected to the login page:
                #   http://127.0.0.1:5008/login?next=%2Fsecrets
                #   Once the user has logged in, we redirect to where they wanted to go using the "next" attribute
                # TODO: Handle the "next" parameter

                return redirect(url_for('secrets', username=user.name))
            else:
                flash(f'Incorrect Password for {email}', 'error')
                flash(f"Try again.")
                return render_template("login.html")
        else:
            flash(f"User {email} not found!", 'error')
            flash(f"Try again.")
            print(f"User {email} not found!")
            return render_template("login.html")

    return render_template("login.html")


@app.route('/secrets')
@login_required
def secrets():
    return render_template("secrets.html", username=current_user.name)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# @app.route('/download/<path:filename>')
# @login_required
# def download(filename):
#     # This is a secure way to serve files from a folder, such as static files or uploads.
#     # Uses safe_join() to ensure the path coming from the client is not maliciously crafted
#     # to point outside the specified directory
#     # Note that this method does not prevent anyone with the link to the file from downloading it.
#     return send_from_directory(
#         directory='static/files',
#         filename=filename,
#         as_attachment=True,
#     )


# This is much more secure than the above method.
# The link never displays a URL to the file, and the user cannot access /download because there is no GET method
#     http://192.168.56.101:5008/download - Method Not Allowed
#     http://192.168.56.101:5008/download/cheat_sheet.pdf - Not Found
@app.route('/download', methods=['POST'])
@login_required
def download():
    filename = request.form['filename']
    # This is a secure way to serve files from a folder, such as static files or uploads.
    # Uses safe_join() to ensure the path coming from the client is not maliciously crafted
    # to point outside the specified directory
    return send_from_directory(
        directory='static/files',
        path=filename,
        as_attachment=True,
    )


if __name__ == "__main__":
    # Localhost
    app.run(host='127.0.0.1', port=5008, debug=True)

    # # For VBox Host Only
    # app.run(host='192.168.56.101', port=5008, debug=True)  # Using VBox Host Only IP
