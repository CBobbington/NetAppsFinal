import sensor, random


class ExampleSensor(sensor.Sensor):
    # Override defaults, write to example_sensor2.dat at 10 samples/sec
    __data_file__ = "example_sensor2.dat"
    __poll_rate__ = 10

    def __init__(self):
        sensor.Sensor.__init__(self)
        self.__valid__ = True

    # Implement poll function, in this case values from 0 to 1
    def __poll__(self):
        return random.random()

    def sensor_available(self):
        return self.__valid__
