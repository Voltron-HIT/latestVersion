from flask import Flask, render_template, redirect, url_for, request, session
from binascii import b2a_hex
from datetime import datetime

import bcrypt
import pymongo
import re


app = Flask(__name__)
client = pymongo.MongoClient("mongodb://theophilus:chidi18@ds153380.mlab.com:53380/mongo")
db = client['mongo']
sess = {"logged_in":False}
salt = b'$2b$11$Za4hFNuzn3Rvw7gLnUVZCu'


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if sess['logged_in'] is True:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrap


@app.route('/control/login', methods=('GET', 'POST'))
def controlLogin():

    error_message = ""

    if request.method == 'POST':
        username = request.form.get('username')
        password = bcrypt.hashpw(request.form['password'].encode('utf-8'), salt)


        user = db.Admin.find_one({'username': username})

        if user != None :
            dbUsername = user['username']
            dbPassword = bytes(user['password'].encode('utf-8'))

            if username != dbUsername or bcrypt.hashpw(request.form['password'].encode('utf-8'), password) != dbPassword:
                error_message = 'Invalid Credentials. Please try again.'

            else:
                sess['logged_in'] = True
                return redirect(url_for('controlHome'))
        else:
            error_message = 'Invalid Credentials. Please try again.'



    return render_template('admin_login.html', Error_Message=error_message, System_Name="")


@app.route('/control/logout')
def controlLogout():
    sess.clear()
    return redirect(url_for('controlLogin'))

@app.route('/control/home')
def controlHome():
    app.jinja_env.globals.update(zip=zip)
    app.jinja_env.globals.update(join=str.join)

    posts = db.Vacancies.find() #query : vacancies
    active = 0
    expired = 0
    archived = 0

    for i in posts:
        if i['deadline'] < datetime.now():
            expired += 1
        else:
            active += 1

    usersRegistered = db.Credentials.find().count() #query : users
    applicants = db.applicants.find().count()  #query : applicants
    online = db.Credentials.find({"active":"True"}).count()

    activeUsers = db.Credentials.find({"active":"True"})
    uactive, email = ([], [])

    for i in activeUsers:
        uactive.append(i['username'])
        email.append(i['_id'])

    post = db.applicants.find({}, {'post':'1'})
    posts, totals, vac = ([], [], [])
    p = ""
    t = ""
    for i in post:
        posts.append(i['post'])
    posts = list(set(posts)).copy()

    for i in posts:

        if posts.index(i) == 0:
            p += i
            t += str(db.applicants.find({'post':i}).count())
        else :
            p += " " + i
            t += " " + str(db.applicants.find({'post':i}).count())




    return render_template('true_admin.html' ,active=active, expired=expired, archived=archived, uRegistered=usersRegistered, uOnline=online,  applicants=applicants, uactive=uactive, email=email, posts=p, totals=t)

@app.route('/control/addUser', methods=('GET', 'POST'))
def controlAddUser():

    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')

        db.Credentials.insert_one({'_id':email, 'username':username})
        return redirect(url_for('controlHome'))

@app.route('/control/changePassword', methods=('GET', 'POST'))
def controlChangePassword():

    if request.method == 'POST':
        oldPassword = request.form['current-password']#bcrypt.hashpw(request.form.get('current-password'), salt)
        dbPassword = db.Admin.find_one({'password': oldPassword})
        if oldPassword != None:
            temp = request.form['repeat-new-password']
            newPassword = (bcrypt.hashpw(temp.encode('utf-8'), salt)).decode('utf-8')
            db.Admin.update_one({'password':oldPassword}, {'$set':{'password':newPassword}})
        return redirect(url_for('controlHome'))
    return redirect(url_for('controlHome'))


if __name__ == '__main__':
    app.run(debug = True)
