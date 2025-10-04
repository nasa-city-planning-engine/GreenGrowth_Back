from werkzeug.security import generate_password_hash, check_password_hash
from models import db


# Define the User model
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    location = db.Column(db.String(256), nullable=False)
    messages = db.relationship(
        "Message", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>"

    ## Password methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    ## CRUD methods
    def user_register(username, email, password, location=None):
        # check uniqueness properly using filter_by or by comparing the column
        if User.query.filter_by(username=username).first() is not None:
            return None  # Username already exists

        if User.query.filter_by(email=email).first() is not None:
            return None  # Email already exists

        # store into the 'location' column defined on the model
        new_user = User(username=username, email=email, location=location)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        return new_user

    @staticmethod
    def sign_In(username, password):
        # User authentication
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            return user

        return None

    def user_Update(self, new_username=None, new_email=None, new_ubication=None):
        # User data update
        if new_username:
            self.username = new_username
        if new_email:
            self.email = new_email
        if new_ubication:
            self.ubication = new_ubication

        db.session.commit()

    def user_Delete(self):
        # User deletion
        db.session.delete(self)
        db.session.commit()
