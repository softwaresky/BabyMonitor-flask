import random
import threading
import time
import datetime

try:
    import Adafruit_DHT
except:
    pass

class DhtDetector(threading.Thread):

    def __init__(self):
        threading.Thread.__init__(self)

        self.name = self.__class__.__name__

        self.dict_data = {}
        self.dict_data["temp"] = 0.0
        self.dict_data["hum"] = 0.0


    def get_data(self):
        """

        'timeNow': ,
        'temp': temp,
        'temp_color': temp_color,
        'hum': hum,
        'hum_color': hum_color

        :return: dict
        """
        return self.dict_data

    # get data from DHT sensor
    def getDHTdata(self):
        hum = 0
        temp = 0
        try:
            sensor = Adafruit_DHT.AM2302
            pin = 4
            hum, temp = Adafruit_DHT.read_retry(sensor, pin)
            if hum is not None and temp is not None:
                hum = round(hum)
                temp = round(temp, 1)
        except:
            hum = random.randrange(40, 60)
            temp =random.randrange(-10, 40)

        return temp, hum

    def run(self):

        while True:
            temp, hum  = self.getDHTdata()

            temp_color = "black"
            hum_color = "black"

            if hum > 60:
                hum_color = "#4682B4"
            elif hum < 30:
                hum_color = "#ADD8E6"
            else:
                hum_color = "#00FF00"

            if temp < 20:
                temp_color = "#F0F8FF"
            elif temp > 28:
                temp_color = "#FF4600"
            else:
                temp_color = "#00FF00"

            self.dict_data = {
                'timeNow': str(datetime.datetime.now()).split(".")[0],
                'temp': temp,
                'temp_color': temp_color,
                'hum': hum,
                'hum_color': hum_color
            }

            time.sleep(2)
