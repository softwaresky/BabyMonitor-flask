import json
import datetime

OBSERVER_LENGTH = 5

def is_equal(var1=0.0, var2=0.0, threshold=0.0001):

    return abs(var1 - var2) < threshold

def get_timestamp():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

def read_json(file_path=""):
    with open(file_path, "r") as f:
        return json.load(f)

class LogManager:

    def __init__(self, name=""):
        self.name = name

    def log(self, msg=""):
        print ("{0} | {1} | {2}".format(get_timestamp(), self.name, msg))
