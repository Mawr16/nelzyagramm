
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, redirect, url_for, render_template
import puremagic

app = Flask(__name__)
app.secret_key = 'секретный ключ'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///social_network.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = 'static/uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db = SQLAlchemy(app)
friendships = db.Table('friendships',
                       db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
                       db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
                       )


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    friends = db.relationship(
        'User',
        secondary=friendships,
        primaryjoin=(friendships.c.user_id == id),
        secondaryjoin=(friendships.c.friend_id == id),
        backref='friend_of'
    )


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('posts', lazy=True))
    image = db.Column(db.LargeBinary, nullable=True)
    video = db.Column(db.LargeBinary, nullable=True)




with app.app_context():
    db.create_all()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        print(username)
        password = request.form['password']
        print("password", password)
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return "Пользователь с таким именем уже есть."
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/image/<int:post_id>')
def get_image(post_id):
    post = Post.query.get_or_404(post_id)
    if post.image:
        return post.image, 200, {'Content-Type': 'image/jpeg'}
    return '', 404


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        print(username)
        password = request.form['password']
        print('passwordlogin', password)
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('profile'))
        return "Неверный логин или пароль."
    return render_template('login.html')


@app.route('/new_post', methods=['GET', 'POST'])
def new_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        content = request.form['content']

        # Обработка фото
        photo = request.files.get('photo')
        photo_data = None
        if photo and photo.filename:
            photo_data = photo.read()

        # Обработка видео
        video = request.files.get('video')
        video_data = None
        if video and video.filename:
            # Проверка размера (100MB максимум)
            video.seek(0, 2)  # Перемещаемся в конец файла
            size = video.tell()  # Получаем размер
            video.seek(0)  # Возвращаемся в начало

            if size > 100 * 1024 * 1024:  # 100MB
                return "Видео слишком большое! Максимальный размер 100MB.", 400

            video_data = video.read()

        new_post = Post(
            content=content,
            user_id=session['user_id'],
            image=photo_data,
            video=video_data
        )
        db.session.add(new_post)
        db.session.commit()

        return redirect(url_for('profile'))

    return render_template('new_post.html')


@app.route('/video/<int:post_id>')
def get_video(post_id):
    post = Post.query.get_or_404(post_id)
    if post.video:
        return post.video, 200, {'Content-Type': 'video/mp4'}
    return '', 404


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.id.desc()).all()
    return render_template('profile.html', user=user, posts=posts)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)

    if post.user_id != session['user_id']:
        return "Вы не можете удалить чужой пост."
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('profile'))


@app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    post = Post.query.get_or_404(post_id)
    if post.user_id != session['user_id']:
        return "Вы не можете редактировать чужой пост."
    if request.method == 'POST':
        content = request.form['content']
        post.content = content
        db.session.commit()
        return redirect(url_for('profile'))
    return render_template('edit_post.html', post=post)


@app.route('/')
def feed():
    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template('feed.html', posts=posts)


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form['query']
        users = User.query.filter(User.username.ilike(f'%{query}%')).all()
        posts = Post.query.filter(Post.content.ilike(f'%{query}%')).all()
        current_user = None
        if 'user_id' in session:
            current_user = db.session.get(User, session['user_id'])
        return render_template('search_results.html', users=users, posts=posts, query=query, current_user=current_user)
    return render_template('search.html')


@app.route('/add_friend/<int:friend_id>')
def add_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    friend = User.query.get(friend_id)
    if friend and friend != user:
        if friend not in user.friends:
            user.friends.append(friend)
        if user not in friend.friends:
            friend.friends.append(user)
        db.session.commit()
    return redirect(request.referrer or url_for('feed'))


@app.route('/remove_friend/<int:friend_id>')
def remove_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = db.session.get(User, session['user_id'])
    friend = db.session.get(User, friend_id)
    if friend and friend in user.friends:
        user.friends.remove(friend)
        if user in friend.friends:
            friend.friends.remove(user)
        db.session.commit()
    return redirect(request.referrer or url_for('feed'))

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7070, debug=True)
