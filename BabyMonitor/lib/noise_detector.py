import pyaudio
import subprocess
import os
import time
import math
import struct
import threading
import numpy as np
from collections import deque

from BabyMonitor.lib import utils

class NoiseDetector(threading.Thread):

    def __init__(self, do_record=True, do_convert=True):
        threading.Thread.__init__(self)

        self.name = str(self.__class__.__name__)
        self.log_manager = utils.LogManager(self.name)

        self.media_dir = os.path.abspath("../media")

        self.FORMAT = pyaudio.paFloat32
        self.RATE = 48000  # Hz, so samples (bytes) per second
        self.CHUNK_SIZE = 2048  # How many bytes to read from mic each time (stream.read())
        self.CHUNKS_PER_SEC = math.floor(self.RATE / self.CHUNK_SIZE)  # How many chunks make a second? (16.000 bytes/s, each chunk is 1.024 bytes, so 1s is 15 chunks)
        self.CHANNELS = 1
        self.HISTORY_LENGTH = 2  # Seconds of audio cache for prepending to records to prevent chopped phrases (history length + observer length = min record length)

        self.audio = pyaudio.PyAudio()
        self.stream = self.get_stream()
        self.threshold = self.determine_threshold()
        self.chunk = None
        self.detect_noise = False

        self.record = []
        self.do_record = do_record
        self.do_convert = do_convert
        self.force_recording = False
        self.use_other_to_record = False
        self.saved = False

        self._value = 0.0

        self.current_file = ""
        self.last_file = ""
        self.deque_history = deque(maxlen=self.HISTORY_LENGTH * self.CHUNKS_PER_SEC)

    def __del__(self):
        self.stream.close()
        self.audio.terminate()

    def get_stream(self):
        return self.audio.open(format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE, input=True, frames_per_buffer=self.CHUNK_SIZE)

    def determine_threshold(self):

        self.log_manager.log("Determining threshold...")

        lst_res = []
        for x in range(50):
            block = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
            rms = self.get_rms(block)
            lst_res.append(rms)

        threshold = (sum(lst_res) / len(lst_res)) * 1.2

        self.log_manager.log("Setting threshold to: {0}".format(threshold))

        return threshold

    def get_rms(self, block):
        """
        Calculate Root Mean Square (noise level) for audio chunk

        @param bytes block
        @return float
        """
        d = np.frombuffer(block, np.float32).astype(np.float)
        return np.sqrt((d * d).sum() / len(d))

    @property
    def value(self):
        return self._value if self._value > self.threshold else 0.0

    def start_recording(self):

        if not (self.use_other_to_record and self.current_file):
            self.current_file = os.path.join(self.media_dir, ".{0}.avi".format(utils.get_timestamp()))

        if self.current_file:
            dst_dir = os.path.dirname(self.current_file)

            if not os.path.exists(dst_dir):
                os.makedirs(dst_dir)

            self.log_manager.log("Noise detected! Recording...")

    def stop_recording(self):

        self.last_file = self.current_file

        self.record = []
        self.current_file = ""

    def is_recording(self):
        return len(self.record) > 0

    def get_chunk(self):
        return self.chunk

    def run(self):

        deque_observer = deque(maxlen=utils.OBSERVER_LENGTH * self.CHUNKS_PER_SEC)
        self.deque_history = deque(maxlen=self.HISTORY_LENGTH * self.CHUNKS_PER_SEC)

        self.log_manager.log("Listening...")

        try:
            while True:
                self.chunk = self.stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                self.deque_history.append(self.chunk)

                rms = self.get_rms(self.chunk)
                deque_observer.append(rms)

                self._value = rms

                self.detect_noise = sum([x > self.threshold for x in deque_observer]) > 0
                if self.do_record:
                    self.do_recording()

                pass
        except KeyboardInterrupt:
            self.log_manager.log("Interrupted!")

    def do_recording(self):

        if (self.use_other_to_record and self.force_recording) or (not self.use_other_to_record and self.detect_noise):
            if not self.is_recording():

                self.start_recording()

            self.record.append(self.chunk)

        elif self.is_recording():
            # self.save(list(self.deque_history) + self.record)
            self.save(self.record)

            self.log_manager.log("Listening...")

            self.stop_recording()

    def save(self, data):

        self.log_manager.log("Saving audio...")
        self.saved = False
        if self.current_file:
            data = b''.join(data)

            with open(self.current_file, "wb+") as f:
                f.write(self.generate_wav(data))

            if self.do_convert:
                self.convert_to_mp3(self.current_file)

            self.saved = True

    def convert_to_mp3(self, file_path=""):

        self.log_manager.log("Converting audio...")

        try:
            mp3_file = "{0}.mp3".format(os.path.splitext(file_path)[0])

            lst_cmd = []
            lst_cmd.append("ffmpeg")
            lst_cmd.append("-i {}".format(file_path))
            lst_cmd.append("-f mp3")
            lst_cmd.append("{}".format(mp3_file))

            p = subprocess.Popen(" ".join(lst_cmd), shell=True)
            (output, err) = p.communicate()

            if os.path.exists(file_path):
                p.wait()
                os.remove(file_path)

            self.current_file = mp3_file

        except subprocess.CalledProcessError:
            self.log_manager.log("Error converting audio")

    def bytes_to_array(self, bytes, type):
        """
        Convert raw audio data to TypedArray

        @param bytes bytes
        @return numpy-Array
        """
        return np.frombuffer(bytes, dtype=type)

    def generate_wav(self, raw):
        """
        Create WAVE-file from raw audio chunks

        @param bytes raw
        @return bytes
        """
        # Check if input format is supported
        if self.FORMAT not in (pyaudio.paFloat32, pyaudio.paInt16):
            print("Unsupported format")
            return

        # Convert raw audio bytes to typed array
        samples = self.bytes_to_array(raw, np.float32)

        # Get sample size
        sample_size = pyaudio.get_sample_size(self.FORMAT)

        # Get data-length
        byte_count = (len(samples)) * sample_size

        # Get bits/sample
        bits_per_sample = sample_size * 8

        # Calculate frame-size
        frame_size = int(self.CHANNELS * ((bits_per_sample + 7) / 8))

        # Container for WAVE-content
        wav = bytearray()

        # Start RIFF-Header
        wav.extend(struct.pack('<cccc', b'R', b'I', b'F', b'F'))
        # Add chunk size (data-size minus 8)
        wav.extend(struct.pack('<I', byte_count + 0x2c - 8))
        # Add RIFF-type ("WAVE")
        wav.extend(struct.pack('<cccc', b'W', b'A', b'V', b'E'))

        # Start "Format"-part
        wav.extend(struct.pack('<cccc', b'f', b'm', b't', b' '))
        # Add header length (16 bytes)
        wav.extend(struct.pack('<I', 0x10))
        # Add format-tag (e.g. 1 = PCM, 3 = FLOAT)
        wav.extend(struct.pack('<H', 3))
        # Add channel count
        wav.extend(struct.pack('<H', self.CHANNELS))
        # Add sample rate
        wav.extend(struct.pack('<I', self.RATE))
        # Add bytes/second
        wav.extend(struct.pack('<I', self.RATE * frame_size))
        # Add frame size
        wav.extend(struct.pack('<H', frame_size))
        # Add bits/sample
        wav.extend(struct.pack('<H', bits_per_sample))

        # Start data-part
        wav.extend(struct.pack('<cccc', b'd', b'a', b't', b'a'))
        # Add data-length
        wav.extend(struct.pack('<I', byte_count))

        # Add data
        for sample in samples:
            wav.extend(struct.pack("<f", sample))

        return bytes(wav)


def main():

    nd = NoiseDetector()
    nd.start()

# main()