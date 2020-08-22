import threading
import os
import subprocess
import time

from BabyMonitor.lib import motion_detector
from BabyMonitor.lib import noise_detector
from BabyMonitor.lib import dht_detector
from BabyMonitor.lib import utils


class ThreadManager(threading.Thread):

    def __init__(self):

        threading.Thread.__init__(self)

        self.name = str(self.__class__.__name__)
        self.do_record = False
        self.record_state = False
        self.is_merged = False

        self.log_manager = utils.LogManager(self.name)
        self.media_dir = os.path.abspath("../media")

        self.motion_detector = motion_detector.MotionDetector(do_convert=False, do_record=self.do_record)
        self.motion_detector.use_other_to_record = True
        # self.motion_detector.start()

        self.noise_detector = noise_detector.NoiseDetector(do_convert=False, do_record=self.do_record)
        self.noise_detector.use_other_to_record = True
        # self.noise_detector.start()

        self.dht_detector = dht_detector.DhtDetector()
        # self.dht_detector.start()

        self.fill_do_record()

    def __del__(self):
        self.motion_detector.join()
        self.noise_detector.join()
        self.dht_detector.join()

    def fill_do_record(self):
        self.motion_detector.do_record = self.do_record
        self.noise_detector.do_record = self.do_record

    def switch_record_state(self):
        self.do_record = not self.do_record
        self.fill_do_record()

    def get_record_path_name(self):
        return os.path.join(self.media_dir, utils.get_timestamp())

    def merge_video_and_audio(self, video_file="", audio_file="", output_file=""):
        # ffmpeg -i video.mp4 -i audio.wav -c:v copy -c:a aac output.mp4
        # ffmpeg -i input.avi -c:v libx264 -crf 19 -preset slow -c:a aac -b:a 192k -ac 2 out.mp4

        try:
            if video_file and audio_file and output_file:
                self.log_manager.log("Merging audio and video files...")

                lst_cmd = []
                lst_cmd.append("ffmpeg")
                lst_cmd.append("-i {0}".format(video_file))
                lst_cmd.append("-i {0}".format(audio_file))
                # lst_cmd.append("-c:v copy")

                # H.264 codec
                lst_cmd.append("-c:v libx264")
                lst_cmd.append("-crf 19")
                lst_cmd.append("-preset slow")

                lst_cmd.append("-c:a aac")

                lst_cmd.append("-b:a 192k")
                lst_cmd.append("-ac 2")
                lst_cmd.append(output_file)


                cmd = " ".join(lst_cmd)
                p = subprocess.Popen(cmd, shell=True)
                (output, err) = p.communicate()

                for file_ in [video_file, audio_file]:
                    if os.path.exists(file_):
                        p.wait()
                        os.remove(file_)

        except subprocess.CalledProcessError:
            self.log_manager.log("Error converting merging files!")


        pass

    def merge_data(self):

        self.record_state = self.noise_detector.detect_noise or self.motion_detector.detect_motion
        self.motion_detector.force_recording = self.record_state
        self.noise_detector.force_recording = self.record_state
        output_file = ""

        if self.record_state:
            dict_dht_data = self.dht_detector.get_data()
            self.motion_detector.video_text = "Temp: {0} deg. C  | Hum: {1}%".format(dict_dht_data["temp"],
                                                                                     dict_dht_data["hum"])

            if not (self.motion_detector.current_file and self.noise_detector.current_file):
                record_file_name = self.get_record_path_name()
                dir_name = os.path.dirname(record_file_name)
                base_name = os.path.basename(record_file_name)

                video_file = os.path.join(dir_name, f".{base_name}_video.avi")
                audio_file = os.path.join(dir_name, f".{base_name}_audio.wav")
                output_file = f"{record_file_name}.mp4"

                self.motion_detector.current_file = video_file
                self.noise_detector.current_file = audio_file
                self.is_merged = False

        if not self.is_merged and self.noise_detector.last_file and self.motion_detector.last_file and self.motion_detector.saved and self.noise_detector.saved:
            self.merge_video_and_audio(self.motion_detector.last_file, self.noise_detector.last_file, output_file)

            self.is_merged = True

    # def run(self):
    #
    #     self.motion_detector.start()
    #     self.noise_detector.start()
    #     self.dht_detector.start()
    #     self.is_merged = False
    #
    #     while True:
    #         self.merge_data()
    #         time.sleep(.5)


def main():

    thread_manage = ThreadManager()
    time.sleep(1)
    thread_manage.start()

# main()
