
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.ext.hybrid import hybrid_property

from BabyMonitor import db
import datetime

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, unique=True, nullable=False)
    _password = db.Column("password", db.String, nullable=False)

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        """Store the password as a hash for security."""
        self._password = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password, value)

    def __repr__(self):
        return f'<User {self.username}>'

class Detections(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    motion = db.Column(db.Float)
    noise = db.Column(db.Float)

    def __repr__(self):
        return f'<Detection [{self.timestamp}] ' \
               f'motion: {self.motion}, ' \
               f'noise: {self.noise}>'

class WeatherMeasures(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)

    def __repr__(self):
        degree_sign = u"\u2103"
        return f'<WeatherMeasures [{self.timestamp}] ' \
               f'temperature: {self.temperature} {degree_sign}, ' \
               f'humidity: {self.humidity} %>'

class IpClient(db.Model):

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip_address = db.Column(db.String(24))
    expired = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    try_count = db.Column(db.Integer, default=0)

    def is_allow(self):
        return self.expired <= datetime.datetime.now()

    def update_count(self):

        # if self.rbr == 3:
        if self.try_count % 3 == 0:
            self.expired = datetime.datetime.now() + datetime.timedelta(minutes=(self.try_count / 3) * 10)
        self.try_count += 1
        db.session.commit()

    def get_timedelta_expired(self):
        return self.expired - datetime.datetime.now()

    def __repr__(self):
        return f'<IpClient {self.ip_address} expired at {self.expired}>'