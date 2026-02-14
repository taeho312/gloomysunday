import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# 프로젝트의 절대 경로 확보
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'archive-secret-key-999'

# Heroku 환경변수(DATABASE_URL)가 있으면 그것을 쓰고, 없으면 로컬 SQLite를 사용합니다.
# 이는 추후 SQLite에서 Postgres로 전환할 때 매우 유용합니다.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'db.sqlite'))
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 불필요한 경고 메시지 방지
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static/uploads')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- 데이터베이스 모델 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_edited = db.Column(db.Boolean, default=False, nullable=True) # [해결] image_4b1ec8 에러 방지
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

class Invite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    target_username = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), nullable=False)
    is_used = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 일반 유저 경로 ---
@app.route('/')
def index():
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('index.html', posts=posts, now=datetime.utcnow())

@app.route('/post', methods=['POST'])
@login_required
def post():
    if current_user.is_blocked:
        flash('작성 권한이 박탈되었습니다.')
        return redirect(url_for('index'))
    content = request.form.get('content')
    if content:
        new_post = Post(content=content, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.is_edited or post.user_id != current_user.id:
        flash('이미 수정되었거나 권한이 없습니다.')
        return redirect(url_for('index'))
    
    if (datetime.utcnow() - post.date_posted).total_seconds() > 1800:
        flash('30분이 경과하여 수정할 수 없습니다.')
        return redirect(url_for('index'))

    if request.method == 'POST':
        post.content = request.form.get('content')
        post.is_edited = True
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('index.html', edit_post=post, posts=Post.query.all(), now=datetime.utcnow())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and not user.is_blocked and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('입주민 정보가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        invite_code = request.form.get('invite_code')
        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('register'))
        invite = Invite.query.filter_by(target_username=username, code=invite_code, is_used=False).first()
        if not invite:
            flash('세대 고유 번호가 올바르지 않습니다.')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        invite.is_used = True
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- 관리자 전용 경로 ---
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('index'))
    users = User.query.all()
    invites = Invite.query.all()
    return render_template('admin.html', users=users, invites=invites)

@app.route('/admin/add_invite', methods=['POST'])
@login_required
def add_invite():
    if not current_user.is_admin: return redirect(url_for('index'))
    target_name = request.form.get('target_name')
    new_code = request.form.get('new_code')
    if target_name and new_code:
        db.session.add(Invite(target_username=target_name, code=new_code))
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_invite/<int:invite_id>')
@login_required
def delete_invite(invite_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    invite = Invite.query.get_or_404(invite_id)
    db.session.delete(invite)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/block_user/<int:user_id>')
@login_required
def block_user(user_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.username != '백정현':
        user.is_blocked = not user.is_blocked
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_post/<int:post_id>')
@login_required
def delete_post(post_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    post = Post.query.get_or_404(post_id)
    post.content = "<p style='color: #444; font-style: italic;'>관리자에 의해 퇴거된 입주민입니다.</p>"
    post.is_edited = True
    db.session.commit()
    return redirect(url_for('index'))

# --- 서버 실행 및 초기화 ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Invite.query.filter_by(target_username='백정현').first():
            db.session.add(Invite(target_username='백정현', code='0000'))
            db.session.commit()
    app.run(debug=True)