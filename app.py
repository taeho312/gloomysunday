import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'archive-secret-key-999'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'db.sqlite'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

KST = timezone(timedelta(hours=9))

# --- 데이터 모델 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=lambda: datetime.now(KST))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_edited = db.Column(db.Boolean, default=False, nullable=True)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_username = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), nullable=False)
    is_used = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 게시판 및 관리 기능 (BuildError 해결) ---
@app.route('/')
def index():
    posts = Post.query.order_by(Post.date_posted.desc()).all() if current_user.is_authenticated else []
    return render_template('index.html', posts=posts, now=datetime.now(KST))

@app.route('/post', methods=['POST'])
@login_required
def post():
    content = request.form.get('content')
    if content:
        new_post = Post(content=content, user_id=current_user.id, date_posted=datetime.now(KST))
        db.session.add(new_post)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    post = Post.query.get_or_404(post_id)
    post.content = "<p style='color: #444; font-style: italic;'>관리자에 의해 규제된 글입니다.</p>"
    post.is_edited = True
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('index'))
    users = User.query.all()
    invites = Invite.query.all()
    return render_template('admin.html', users=users, invites=invites)

# --- 인증 경로 ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and not user.is_blocked and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('index'))
        flash('정보가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- D'VELO 단지조감도 및 9개 개별 페이지 ---
@app.route('/d-velo')
@login_required
def d_velo():
    return render_template('d_velo_site.html', now=datetime.now(KST))

@app.route('/d-velo/community-lounge')
@login_required
def lounge():
    return render_template('lounge_detail.html', now=datetime.now(KST))

@app.route('/d-velo/101')
@login_required
def b101(): return render_template('b101_detail.html', now=datetime.now(KST))

@app.route('/d-velo/102')
@login_required
def b102(): return render_template('b102_detail.html', now=datetime.now(KST))

@app.route('/d-velo/201')
@login_required
def b201(): return render_template('b201_detail.html', now=datetime.now(KST))

@app.route('/d-velo/202')
@login_required
def b202(): return render_template('b202_detail.html', now=datetime.now(KST))

@app.route('/d-velo/301')
@login_required
def b301(): return render_template('b301_detail.html', now=datetime.now(KST))

@app.route('/d-velo/302')
@login_required
def b302(): return render_template('b302_detail.html', now=datetime.now(KST))

@app.route('/d-velo/401')
@login_required
def b401(): return render_template('b401_detail.html', now=datetime.now(KST))

@app.route('/d-velo/402')
@login_required
def b402(): return render_template('b402_detail.html', now=datetime.now(KST))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Invite.query.filter_by(target_username='백정현').first():
            db.session.add(Invite(target_username='백정현', code='0000'))
            db.session.commit()
    app.run(debug=True)