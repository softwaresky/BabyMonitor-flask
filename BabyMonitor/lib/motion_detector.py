import os
import threading
import cv2
import datetime
from collections import deque
import time
import math
import numpy as np
import subprocess

from BabyMonitor.lib import utils


class MotionDetector(threading.Thread):

    def __init__(self, video_capture_source=None, do_record=True, do_convert=True):
        threading.Thread.__init__(self)

        self.name = str(self.__class__.__name__)
        self.log_manager = utils.LogManager(self.name)

        self.media_dir = os.path.abspath("../media")

        self.current_file = ""
        self.last_file = ""
        self.current_frame = None
        self.current_timestamp = time.time()

        self.video = video_capture_source if video_capture_source else self.get_video_capture()
        self.frame_rate = 15
        self.fps = 0
        self.height, self.width = self.get_resolutions()

        self.threshold = 7

        self.do_record = do_record
        self.do_convert = do_convert
        self.video_text = ""
        self.detect_motion = False
        self.writer = None
        self.use_other_to_record = False
        self.force_recording = False
        self.saved = False
        self._value = 0.0

        self.codec = cv2.VideoWriter_fourcc(*'MJPG')

        self.record = []

    def __del__(self):
        self.video.release()

    def start_recording(self):

        if not (self.use_other_to_record and self.current_file):
            self.current_file = os.path.join(self.media_dir, ".{0}.avi".format(utils.get_timestamp()))

        if self.current_file:
            dst_dir = os.path.dirname(self.current_file)

            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            # self.writer = cv2.VideoWriter(self.current_file, self.codec, self.frame_rate, (self.width, self.height))
            self.log_manager.log("Motion detected! Recording...")


    def stop_recording(self):

        self.last_file = self.current_file
        self.current_file = ""
        self.writer = None
        self.record = []

    def is_recording(self):
        # return self.writer is not None
        return len(self.record) > 0 or self.writer is not None

    def save(self, data):

        self.log_manager.log("Saving video...")
        self.saved = False

        if data:

            zero_timestamp = data[0][0]

            writer = cv2.VideoWriter(self.current_file, self.codec, self.frame_rate, (self.width, self.height))
            total_frames_data = int(math.floor((data[-1][0] - zero_timestamp ) * self.frame_rate))
            # print ("Frames: {0} | {1}".format(total_frames_data, len(data)))

            if total_frames_data < len(data):
                time_step = 1 / self.frame_rate

                frame_counter = 0
                timestamp_value = 0

                while timestamp_value <= data[-1][0] - zero_timestamp:
                    closest_timestamp_, frame_data_ = min(data, key=lambda x: abs((x[0]-zero_timestamp) - timestamp_value))
                    writer.write(frame_data_)
                    frame_counter += 1
                    timestamp_value += time_step

                writer.release()

            if self.do_convert:
                self.convert_to_mp4(self.current_file)

            self.saved = True

    def do_recording(self):
        if (self.use_other_to_record and self.force_recording) or (not self.use_other_to_record and self.detect_motion):

            if not self.is_recording():
                self.start_recording()

            self.saved = False
            # self.writer.write(self.current_frame)
            self.record.append((self.current_timestamp, self.current_frame))

        elif self.is_recording():
            if self.writer is not None:
                self.writer.release()

            self.save(self.record)

            # if self.do_convert:
            #     self.convert_to_mp4(self.current_file)

            # self.saved = True

            self.stop_recording()

            self.log_manager.log( "Observing...")

    def convert_to_mp4(self, file_path=""):

        self.log_manager.log("Converting video...")
        try:
            mp4_file = "{0}.mp4".format(os.path.splitext(file_path)[0])
            lst_cmd = []
            lst_cmd.append("ffmpeg")
            lst_cmd.append("-i {}".format(file_path))
            lst_cmd.append("{}".format(mp4_file))

            cmd = " ".join(lst_cmd)
            p = subprocess.Popen(cmd, shell=True)
            (output, err) = p.communicate()

            if os.path.exists(file_path):
                p.wait()
                os.remove(file_path)

            self.current_file = mp4_file

        except subprocess.CalledProcessError:
            self.log_manager.log("Error converting video")


    def get_video_capture(self):

        video = cv2.VideoCapture(0)
        time.sleep(0.5)

        return video

    def get_resolutions(self):

        frame = cv2.cvtColor(self.video.read()[1],cv2.COLOR_RGB2GRAY)
        return frame.shape[0: 2]

    def get_frame(self):
        if self.current_frame is not None:
            ret, jpeg = cv2.imencode('.jpg', self.current_frame)
            return jpeg.tobytes()
        return None

    @property
    def value(self):
        return self._value if self._value > 0.0 else 0.0

    def run(self):

        self.log_manager.log("Observing...")

        deque_observer = deque(maxlen=utils.OBSERVER_LENGTH * self.frame_rate)
        previous_frame = None

        while True:

            grabbed, self.current_frame = self.video.read()
            self.current_timestamp = time.time()

            if not grabbed:
                break

            video_text = "{0} | {1}".format(str(datetime.datetime.now()).split(".")[0], self.video_text)
            cv2.putText(self.current_frame, video_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

            frame_gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
            frame_blur = cv2.GaussianBlur(frame_gray, (21, 21), 0)

            if previous_frame is None:
                previous_frame = frame_blur
                continue

            delta_frame = cv2.absdiff(previous_frame, frame_blur)

            threshold_frame = cv2.threshold(delta_frame, 15, 255, cv2.THRESH_BINARY)[1]

            kernel = np.ones((5, 5), np.uint8)
            dilated_frame = cv2.dilate(threshold_frame, kernel, iterations=4)

            res = dilated_frame.astype(np.uint8)
            motion_percentage = (np.count_nonzero(res) * 100) / res.size

            deque_observer.append(motion_percentage)

            self._value = motion_percentage

            self.detect_motion = sum([x > self.threshold for x in deque_observer]) > 0

            if self.do_record:
                self.do_recording()

            previous_frame = frame_blur

def main():
    md = MotionDetector(do_convert=False)
    md.start()
    pass

# main()