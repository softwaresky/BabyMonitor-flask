import os
import threading
import time
from functools import wraps

from flask import Flask, render_template, Response, send_file, redirect, url_for, request, session, g
from flask_socketio import SocketIO

from BabyMonitor.models import User, IpClient, Detections, WeatherMeasures

from BabyMonitor.lib.thread_manager import ThreadManager
from BabyMonitor.lib import utils

from BabyMonitor import create_app
from BabyMonitor import db

MEDIA_DIR = os.path.abspath("./media")

app = create_app()
socketio = SocketIO(app, async_mode='threading')

def get_client_ip():
	return request.environ.get('HTTP_X_REAL_IP', request.remote_addr)

@app.before_request
def load_logged_in_user():
	user_id = session.get("user_id")
	g.user = User.query.get(user_id) if user_id is not None else None

def login_required(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		# if 'logged_in' in session:
		if g.user is not None:
			return f(*args, **kwargs)
		else:
			print("You need to login first")
			return redirect(url_for('login'))

	return wrap

@app.route('/home')
@app.route("/")
@login_required
def index():
	# if 'logged_in' not in session:
	# 	return redirect(url_for('login'))

	session["next_url"] = "/"
	return render_template("home.html")

@app.route('/login', methods=['GET', 'POST'])
def login():

	if request.method == 'POST':
		session.pop('logged_in', None)
		session.pop('username', None)

		username = request.form['username']
		password = request.form['password']
		ip_address = get_client_ip()
		error_msg = ""

		user = User.query.filter_by(username=username).first()

		ip_client = IpClient.query.filter_by(ip_address=ip_address).first()
		if not ip_client:
			ip_client = IpClient(ip_address=ip_address)
			db.session.add(ip_client)
			db.session.commit()
			print(f"Insert {ip_client}")

		if user is None:
			error_msg = f"This {username} doesn't exists!"
		elif not user.check_password(password):
			error_msg = "Incorrect password!"

		if error_msg:
			ip_client.update_count()

		if not error_msg and ip_client.is_allow():	# Is logged in
			# ip_client.expired = datetime.datetime.now()
			# ip_client.try_count = 0
			db.session.delete(ip_client)
			db.session.commit()
			print(f"Remove {ip_client}")

			session.clear()
			session["user_id"] = user.id

			return redirect(url_for('index'))

	return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
	session.clear()
	print ("You have been logged out!")
	return redirect(url_for('index'))

@app.route('/record', methods=["GET", "POST"])
@login_required
def record_switch():

	global thread_manager

	if request.method == "GET":
		pass
	if request.method == "POST":
		if request.form:
			if request.form.get('record') == 'Record' or "record" in request.form:
				thread_manager.switch_record_state()

	next_url = session["next_url"] if "next_url" in session else "/"
	return redirect(next_url)

@app.route("/live")
@login_required
def live():
	session["next_url"] = "/live"
	return render_template("live.html")

@app.route('/videostream')
def videostream():
	def gen_video():
		while True:
			frame = thread_manager.motion_detector.get_frame()

			if frame is not None:
				yield (b'--frame\r\n'
					b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

	return Response(
		gen_video(),
		mimetype='multipart/x-mixed-replace; boundary=frame'
	)

@app.route('/archive')
@login_required
def archive():
	session["next_url"] = "/archive"
	return render_template('archive.html')

@app.route('/archive/<string:filename>')
def archive_item(filename):
	name, extension = os.path.splitext(filename)
	type = get_type(filename)
	session["next_url"] = "/archive/{0}".format(filename)
	return render_template('record.html', filename=filename, type=type)

@app.route('/archive/delete/<string:filename>')
def archive_delete(filename):
	os.remove(MEDIA_DIR + "/" + filename)
	return redirect(url_for('archive'))

@app.route('/archive/play/<string:filename>')
def archive_play(filename):
	# return send_file('archive/' + filename)
	return send_file('media/' + filename)

@socketio.on('connect')
def connect():
	print('Client connected')

@socketio.on('disconnect')
def disconnect():
	print('Client disconnected')

def get_type(filename):
	name, extension = os.path.splitext(filename)
	return 'video' if extension in ['.mp4', '.avi'] else 'audio'

def get_records():
	records = []

	for filename in sorted(os.listdir(MEDIA_DIR), reverse=True):
		if not filename.startswith('.'):
			type = get_type(filename)
			size = byte_to_mb(os.path.getsize(MEDIA_DIR + "/" + filename))
			record = {"filename": filename, 'size': size, 'type': type}
			records.append(record)

	return records

def get_record_symbol():
	return "fas fa-circle" if thread_manager.do_record else "far fa-circle"

def byte_to_mb(byte):
	mb = "{:.2f}".format(byte / 1024 / 1024)
	return str(mb) + " MB"


class SoundStreamThread(threading.Thread):
	def __init__(self):
		self.delay = 1
		super(self.__class__, self).__init__()

	def run(self):
		while True:
			sound = thread_manager.noise_detector.get_chunk()
			socketio.emit('sound', {'chunk': sound})
			time.sleep(0.05)

class DhtStreamThread(threading.Thread):
	def __init__(self):
		self.delay = 1
		super(self.__class__, self).__init__()

	def run(self):
		while True:
			dict_data = thread_manager.dht_detector.get_data()
			socketio.emit('dht_data', dict_data)
			time.sleep(0.05)

class DetectorsThread(threading.Thread):

	def __init__(self):
		super(self.__class__, self).__init__()

		self.last_dht_values = (0.0, 0.0) # humidity, temperature
		self.last_det_values = (0.0, 0.0) # motion, noise

	def is_equal_values(self, values1=(), values2=()):

		for i in range(len(values1)):
			if not utils.is_equal(values1[i], values2[i]):
				return False
		return True

	def run(self):

		while True:

			dict_dht_data = thread_manager.dht_detector.get_data()
			current_dht_values = (dict_dht_data["hum"], dict_dht_data["temp"])

			with app.app_context():
				wm = None
				det = None
				if not self.is_equal_values(current_dht_values, self.last_dht_values):

					wm = WeatherMeasures(humidity=current_dht_values[0],
										temperature=current_dht_values[1])
					db.session.add(wm)

				if thread_manager.record_state:
					current_det_values = (thread_manager.motion_detector.value, thread_manager.noise_detector.value)
					if sum(current_det_values) > 0.0 and not self.is_equal_values(current_det_values, self.last_det_values):

						det = Detections(motion=current_det_values[0],
										 noise=current_det_values[1])
						db.session.add(det)

						self.last_det_values = current_det_values

				if wm or det:
					db.session.commit()
					if wm:
						print(f"Insert {wm}")
					if det:
						print(f"Insert {det}")
				pass

			self.last_dht_values = current_dht_values
			time.sleep(0.5)

app.jinja_env.globals.update(get_records=get_records)
app.jinja_env.globals.update(get_record_symbol=get_record_symbol)

thread_manager = ThreadManager()
thread_manager.media_dir = MEDIA_DIR
thread_manager.fill_do_record()
thread_manager.do_record = False
time.sleep(1)
thread_manager.start()

sound_stream_t = SoundStreamThread()
sound_stream_t.start()

dht_stream_t = DhtStreamThread()
dht_stream_t.start()

detector_t = DetectorsThread()
detector_t.start()

if __name__ == '__main__':
	os.environ["PA_ALSA_PLUGHW"] = "1"
	socketio.run(app, log_output=False, host='0.0.0.0', port=7894, debug=True, use_reloader=False)
