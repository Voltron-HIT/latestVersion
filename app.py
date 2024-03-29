import pymongo
import bcrypt
import pandas as pd
import collections
import smsConfig
import emailConfig
import re
import subprocess
from bson import Binary
from functools import wraps
from datetime import datetime, date
from itsdangerous import SignatureExpired, URLSafeTimedSerializer
from twilio.rest import Client
from flask import Flask, render_template, url_for, request, session, redirect, flash
from flask_mail import Mail,Message

app = Flask(__name__)
app.config.from_pyfile('config.cfg')
app.config['SECRET_KEY'] = b'b\x18&\xc1\xcf&\xbe\xbb\x8c\xfcBZ\xfd\xa4\x93N\xbe\xcdFoS%N\xb7q\xca\xd6X\xc0\x9a?\xec\x10oP\x08'

mail = Mail(app)

s = URLSafeTimedSerializer('GOMOGOMONO...')

salt = b'$2b$11$Za4hFNuzn3Rvw7gLnUVZCu'

newpassword = None
dbEmail = ""
postSession = ""
nameSession = ""
idSession , idToken = ("", "")
sess = {"logged_in":False}

#one-time MongoDB connection
client = pymongo.MongoClient("mongodb+srv://blessedmahuni:eureka@blessed-sjzrr.mongodb.net/JobApplication?retryWrites=true")
db = client['mongo']

#Unrouted functions
def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if sess['logged_in'] is True:
            return f(*args, **kwargs)
        else:
            return redirect(url_for('login'))

    return wrap

def smss(sendTo):
	'''uses one phone number for a free trail, function used in other functions as a extra feature'''
	account_sid = smsConfig.accountSID
	auth_token = smsConfig.authToken
	client = Client(account_sid, auth_token)
	message = client.messages.create(body='Hello there!',from_=smsConfig.twilioNumber,to='+263784428853')
	return message.sid


@app.route('/', methods=('GET', 'POST'))
@app.route('/home', methods=('GET', 'POST'))
def home():
    global postSession
    postSession = ""
    status = None
    post = ""
    app.jinja_env.globals.update(zip=zip)

    depts = db.Vacancies.find({}, {'department':'1'})
    departments, totals, vac = ([], [], [])

    for i in depts:
        departments.append(i['department'])
    departments = list(set(departments)).copy()

    for i in departments:
        totals.append(db.Vacancies.find({'department':i}).count())
    
    if request.method == 'POST':
        department = request.form.get('department')
        post = db.Vacancies.find({'department':department})
    else:
        post = db.Vacancies.find()

    for i in post:
        position = i['post']
        minimum_requirements = i['minimum requirements']
        responsibilities = i['responsibilities']
        deadline = i['deadline']
        apply_url = url_for('test', token = position, _external = False)
        description = i['post description']

        current = datetime.now()

        if current < deadline:
            status = "Active Vacancy"
            vac.append((position, minimum_requirements, responsibilities, apply_url, description))
        else:
            status = "Expired Vacancy"
   
    return render_template('index.html', post=vac,depts=departments, totals=totals )

@app.route('/humanResourceHome')
@login_required
def humanResourceHome():
    global postSession
    postSession = ""
    status = None
    post = db.Vacancies.find()
    vac = []

    for i in post:
        position = i['post']
        minimum_requirements = i['minimum requirements']
        responsibilities = i['responsibilities']
        deadline = i['deadline']
        add_url = url_for('temporary', token = position, _external = False)
        edit_url = url_for('edit', token = position, _external = False)
        fullList_url = url_for('fullList', token = position, _external = False)
        description = i['post description']
        current = datetime.now()

        if current < deadline:
            status = "Active Vacancy"
        else:
            status = "Expired Vacancy"

        vac.append((position, minimum_requirements, responsibilities, deadline, status, add_url, edit_url, fullList_url, description ))

    return render_template('hr.html', post=vac)

@app.route('/addVacancy', methods=('GET', 'POST'))
def addVacancy():

    if request.method == 'POST':
        post = request.form.get('post')
        description = request.form.get('post description')
        department = request.form.get('department')
        requirements = (request.form.get('requirement')).split("\r\n")
        responsibilities = (request.form.get('responsibilities')).split("\r\n")

        dateOfDeadline = request.form.get('deadline')

        deadlineDate = dateOfDeadline.split("-")

        c = []

        for i in deadlineDate:
            c.append(int(i))

        deadline = datetime(c[0], c[1], c[2], 11, 59, 59)
        db.Vacancies.insert({"post":post, "post description":description,  "department":department, "deadline":deadline, "minimum requirements":requirements, "responsibilities":responsibilities})
        flash('New Vacancy Successfully Added')
        return redirect(url_for('humanResourceHome'))
    return render_template('addvacancy.html')

@app.route('/shortlist', methods=('GET', 'POST'))
def shortlist():
    global nameSession
    nameSession = ""

    app.jinja_env.globals.update(zip=zip)
    post = postSession
    query = db.applicants.find({"post":post, "$or": [{"status":"new"}, {"status":"reserved"}]})

    applicants, x, accepted, aApplicants, aIDs, ids = ([], [], [], [], [], [])

    for i in query:
        applicants.append(i['name'])
        aIDs.append(i['National_id'])

    for i in range(len(applicants)):
        x.append(i)

    query = db.applicants.find({'post':post, 'status':'shortlist'})

    
    for i in query:
        accepted.append(i['email'])
        aApplicants.append(i['name'])
        ids.append(i['National_id'])

    if request.method == 'POST':
        for i in x:
            if request.form.get(str(i)) == 'shortlist':
                name = applicants[i]
                db.applicants.update({"name":name}, {"$set":{"status":"shortlist"}})
            if request.form.get(str(i)) == 'denied':
                name = applicants[i]
                db.applicants.update({"name":name}, {"$set":{"status":"denied"}})

        #sending emails for rejection and acceptance

        return redirect(url_for('shortlist'))
    return render_template('shortlist.html', x=x, y=applicants, z=aIDs,  accepted=accepted, aApplicants=aApplicants, ids=ids)

@app.route('/resetPassword')
def resetPassword():
    global newpassword

    if newpassword != None:
       #Hashing new password
       newpassword = (bcrypt.hashpw(newpassword.encode('utf-8'), salt)).decode('utf-8')
       db.Credentials.update_one({"_id":dbEmail}, {"$set":{"password":newpassword}})
       newpassword = None
       return redirect(url_for('login'))
    return render_template('resetpassword.html')

@app.route('/passwordRecovery', methods = ['GET','POST'])
def passwordRecovery():
	'''verifies the email adress and sent the password '''
	email = ""
	if request.method == 'POST':
		email = request.form['email']
	token = s.dumps(email, salt = 'emailRecovery')
	return redirect(url_for('sending',token = token , _external = False))

@app.route('/sending/<token>')
def sending(token):
    '''this function sends a message to that email to get a new password, can use username which will be used to fetch the email address if it exists in the database '''

    global dbEmail
    email = s.loads(token, salt = 'emailRecovery')
    token = s.dumps(email, salt='emailToLink')
    dbEmail = email

    link = url_for('forgotPassword', token = token , _external = True)
    msg = Message('Email Verification', sender='achidzix',recipients=[email])
    msg.body = "User associated with the HIT HR account has intiated a request to recover user password.\nTo complete password recover process, click the following link to enter new password \n{} \n\nFor your account protection, this link will expire after 24 hours.\n\nBest regards\nHIT\n\nhttps://www.hit.ac.zw/".format(link)
    mail.send(msg)
    return "Email has been sent to user emal address {}".format(email)

@app.route('/forgotPassword/<token>')
def forgotPassword(token):
	'''this runs from the link sent to the email address'''
	try:
		email = s.loads(token,salt='emailToLink', max_age = 3600)

	except SignatureExpired:
		return "Link Timed Out"
	return render_template('newpassword.html')

@app.route('/test/<token>')
def test(token):
	'''keeps track of all the posts clicked for application or for editing vacancy'''
	global postSession
	postSession = token
	return redirect(url_for('apply'))

@app.route('/temporary/<token>')
def temporary(token):
	'''keeps track of all the posts clicked for application or for editing vacancy'''
	global postSession
	postSession = token
	return redirect(url_for('shortlist'))

@app.route('/edit/<token>')
def edit(token):
	'''keeps track of all the posts clicked for application or for editing vacancy'''
	global postSession
	postSession = token
	return redirect(url_for('editVacancy'))

@app.route('/fullList/<token>')
def fullList(token):
	'''keeps track of all the posts clicked for application or for editing vacancy'''
	global postSession
	postSession = token
	return redirect(url_for('applicantList'))

@app.route('/cv/<token>/<idToken>/<postToken>')
def cv(token, idToken, postToken):
    global nameSession
    nameSession = token
    global idSession
    idSession = idToken
    global postSession
    postSession = postToken

    return redirect(url_for('viewCV'))

@app.route('/newPasswordEntry', methods=('GET', 'POST'))
def newPasswordEntry():

    global newpassword
    if request.method == 'POST':
        newpassword = request.form.get('newpassword2')
        return redirect(url_for('resetPassword'))
    return render_template('newpassword.html')


@app.route('/apply', methods=('GET', 'POST'))
def apply():
    if request.method == 'POST':

        name =  '''{} {}'''.format(request.form.get('firstname'),request.form.get('surname'))
        contacts = '''{} , {} , {}  '''.format(request.form.get('phone1'), request.form.get('phone2'), request.form.get('address'))
        email = request.form.get('email')
        sex = request.form.get('sex')

        current = date.today()
        dateOfBirth = request.form.get('DOB')
        cd = current.strftime('%Y, %m, %d')
        currentDate = cd.split(",")
        dob = dateOfBirth.split("-")
        c = []
        d = []

        for i in currentDate:
            c.append(int(i))
        for i in dob:
            d.append(int(i))

        #dynamic entry of age
        age = int((date(c[0], c[1], c[2]) - date(d[0], d[1], d[2])).days / 365)

        #qualifications

        qualifications = ""
        institution = ""
        workexperience = ""
        file = request.files.get('cv')

        cv = Binary(bytes(file.read()))

        if cv != "" or cv is not None:
            comments = "CV & Certificates attached"
        else:
            comments = "CV not attached"

        for i in range(1, int(request.form.get('numberOfQualifications')) + 1):
            qualifications += "{}. ".format(str(i)) + request.form.get('qualification{}'.format(i)) + ". "
            institution += "{}. ".format(str(i)) + request.form.get('awardingInstitute{}'.format(i)) + ". "
        for i in range(1, int(request.form.get('numberOfWorkExperiences')) + 1):
            workexperience += "{}. Worked at {} as {} since {}. ".format(i, request.form.get('organisation{}'.format(i)), request.form.get('position{}'.format(i)), request.form.get('timeframe{}'.format(i)) )

            user = db.applicants.find_one({'National_id':request.form.get('nationalid'), 'post':postSession})

            if user is None :
                db.applicants.insert({'name':name, 'contact details':contacts, 'sex':sex, 'age':age,'National_id':request.form.get('nationalid'), 'academic qualifications':qualifications, 'awarding institute':institution, 'work experience':workexperience, 'curriculum vitae':cv, 'comments':comments, 'status':'new'
                , 'post':postSession, 'email':email})
                flash('Application For Vacancy Was Successful')
            else:
                flash('Application For Vacancy Already Exists')
                return redirect(url_for('home'))
    return render_template('applicationform.html')

@app.route('/print')
def print():
    data, keys, values = ([], [], [])
    user = None
    fullList = ""

    if postSession == '':
        user = db.applicants.find({})
    else:
        user = db.applicants.find({"post":postSession})
    
    if user is not None:
        for i in user:
            keys = list(i.keys())
            values = list(i.values())
            dictionary = dict(zip(values, keys))

            data.append(collections.OrderedDict(map(reversed, dictionary.items())))

        df = pd.DataFrame(data)
        df = df.drop(["_id", "curriculum vitae", "status", "email", "awarding institute", "post"], axis=1)
        df.index += 1
        pd.set_option("max_colwidth", 1000)
        df.style.set_properties( **{'width': '1500px'})

        fullList = df.to_html(classes="table table-striped table-hover")

    path, file = ('','')
    if postSession == '':
        path = 'templates/applicantList/fullList/applicantlist.html'
        file = 'applicantList/fullList/applicantlist.html'
    else:
        path = 'templates/applicantList/asPerJobList/applicantlist.html'
        file = 'applicantList/asPerJobList/applicantlist.html'

    with open(path, 'w') as myfile:
        myfile.write('''{% extends "list.html" %}
                        {% block title %} Full Applicant List {% endblock %}
                        <img src="../static/img/hitlogo1.png" alt=""> {% block heading %} <span>   Applicant List  </span>
                        <button class="nav-bar btn" style="color: gold;" onclick="print()" target="_blank"><b>Print List</b></button></a> {% endblock %}
                        {% block content %}
                        ''')
        myfile.write(fullList)
        myfile.write('{% endblock %}')

    return render_template(file)

@app.route('/applicantList')
def applicantList():
    data= []
    user = None
    count = []
    cv_url = []

    app.jinja_env.globals.update(zip=zip)
    if postSession == '':
        user = db.applicants.find({})
    else:
        user = db.applicants.find({"post":postSession})

    for i in user:
        dictionary = []
        values = []
        values = list(i.values())
        dictionary = values.copy()
        
        cv_url.append(url_for('cv', token = values[1], idToken = values[5], postToken = values[-2] , _external = False))
        
        data.append(dictionary)
        count.append(len(data))

    return render_template("list.html", table=data, count=count, cvs=cv_url )

@app.route('/login', methods=('GET', 'POST'))
def login():
    '''verifies entered credentials with that in the database'''
    error_message = ""

    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.hashpw(request.form['password'].encode('utf-8'), salt)
        user = db.Credentials.find_one({'username': username})

        if user != None :
            dbUsername = user['username']
            dbPassword = bytes(user['password'].encode('utf-8'))

            if username != dbUsername or bcrypt.hashpw(request.form['password'].encode('utf-8'), password) != dbPassword:
                error_message = 'Invalid Credentials. Please try again.'
            else:
                sess['logged_in'] = True
                return redirect(url_for('humanResourceHome'))
        else:
            error_message = 'Invalid Credentials. Please try again.'

    return render_template('login.html', Error_Message=error_message, System_Name="")

@app.route('/editVacancy', methods=('GET', 'POST'))
def editVacancy():

    post = postSession
    query = db.Vacancies.find_one({"post":post})

    posts = []
    posts.extend((query['post'], query['post description'], query['department'], "\r\n".join(query['minimum requirements']), "\r\n".join(query['responsibilities']), (query['deadline']).date()))

    if request.method == 'POST':

        dateOfDeadline = request.form.get('deadline')

        deadlineDate = dateOfDeadline.split("-")
        c = []

        for i in deadlineDate:
            c.append(int(i))

        deadline = datetime(c[0], c[1], c[2], 11, 59, 59)
        description = request.form.get('post description')
        requirements = (request.form.get('requirement').split('\r\n'))
        responsibilities = (request.form.get('responsibilities').split('\r\n'))

        db.Vacancies.update({"post":post}, {"$set":{"minimum requirements":requirements, "responsibilities":responsibilities, "deadline":deadline}})
        flash('Vacancy Edit Successful ')
        return redirect(url_for('humanResourceHome'))

    return render_template('editvacancy.html', post=posts)

@app.route('/sendNotification', methods=('GET', 'POST'))
def sendNotification():
    post = postSession
    accepted = []    # accepted applicants' emails
    aApplicants = [] # accepted applicants' list

    denied = []      # denied applicants' emails
    dApplicants = [] # denied applicants' list

    if request.method == 'POST':
        time = request.form.get('time')
        query = db.applicants.find({'post':post, 'status':'shortlist'})
        for i in query:
            accepted.append(i['email'])
            aApplicants.append(i['name'])
        query = db.applicants.find({'post':post, 'status':'denied'})
        for i in query:
            denied.append(i['email'])
            dApplicants.append(i['name'])

        #sending to accepted applicants
        for i, j in zip(accepted, aApplicants):
            msg = Message(emailConfig.aSubject.format(post), sender='achidzix',recipients=[i])
            msg.body = emailConfig.aBody.format(j, time)
            mail.send(msg)

        #sending to denied applicants
        for i, j in zip(denied, dApplicants):
            msg = Message(emailConfig.dSubject.format(post), sender='achidzix',recipients=[i])
            msg.body = emailConfig.dBody.format(j, post)
            mail.send(msg)

        db.applicants.delete_many({'post':post, 'status':'denied'})
        flash('Emails Sent Successfully')
    return redirect(url_for('humanResourceHome'))

@app.route('/viewCV', methods=('GET', 'POST'))
def viewCV():
     
    post = postSession
    name = nameSession
    
    nat_id = idSession
    query = db.applicants.find({"name":name, "post":post, "National_id":nat_id})
    file = ''
    for i in query:
        file = (i['curriculum vitae'])


    path = "static/CVs/"
    try:
        with open('{}{}-{}-{}.pdf'.format(path, nameSession, idSession, post), 'xb') as f:
            f.write(file)
       
    except FileExistsError:
        return redirect(url_for('static', filename='CVs/{}-{}-{}.pdf'.format(nameSession, idSession, post)))

    return redirect(url_for('static', filename='CVs/{}-{}-{}.pdf'.format(nameSession, idSession, post)))

@app.route('/CV', methods=('GET', 'POST'))
def CV():

    global nameSession
    nameSession = ""
    global idSession
    idSession = ""

    app.jinja_env.globals.update(zip=zip)

    accepted, cv_url , ids = ([], [], [])
    query = db.applicants.find({'post':postSession, 'status':'shortlist'})
    for i in query:
        accepted.append(i['name'])
        ids.append(i['National_id'])
        cv_url.append(url_for('cv', token = i['name'], idToken = i['National_id'] , _external = False))
    
    return render_template('viewcv.html', names=accepted, ids=ids, cvs=cv_url)
 

@app.route('/adduser')
@login_required
def adduser():
	class Credentials(db.Model):
		__tablename__ = 'credentials'

		id = db.Column(db.Integer, primary_key=True)
		username = db.Column(db.String(60), index=True ,unique=True)
		password = db.Column(db.String(60), index=True)
		email = db.Column(db.String(60), index=True, unique=True)


@app.route('/addvancy')
@login_required
def addvacancy():
	class Vacancy(db.Model):
		__tablename__='vacancy'

		id = db.Column(db.Integer, primary_key=True)
		post = db.Column(db.String(60), index=True ,unique=True)
		department = db.Column(db.String(60), index=True)
		deadline = db.Column(db.String(60), index=True)
		mini_requirements = db.Column(db.String(60), index=True)
		responsibilites = db.Column(db.String(60), index=True)

	   # adjudicator details
		name= db.Column(db.String(60), index=True)
		adju_post=db.Column(db.String(60), index=True)
		intervw_date=db.Column(db.datetime)


@app.route('/logout')
@login_required
def logout():
    sess.clear()
    return redirect(url_for('login'))

#404 page
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
	app.run(debug=True)
