import sensor, random


class ExampleSensor(sensor.Sensor):
    # Override only where to write
    __data_file__ = "example_sensor.dat"

    def __init__(self):
        sensor.Sensor.__init__(self)
        self.__valid__ = True

    # Implement poll function, in this case return integers from -10 to 10
    def __poll__(self):
        return random.randint(-10, 10)

    def sensor_available(self):
        return self.__valid__
