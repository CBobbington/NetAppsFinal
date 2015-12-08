import threading, shelve, time, copy, abc


class Sensor:
    # Default to using file sensor.dat and a poll rate of 1 poll per second
    # These can be overridden in subclasses that derive Sensor
    __data_file__ = "sensor.dat"
    __poll_rate__ = 1

    # Initializes object
    def __init__(self):
        # Creates thread and controlling signal, configures thread as daemonic
        #   (Thread does not keep program open if it is the only thread left)
        self.__thread_started__ = threading.Event()
        self.__poll_thread__ = threading.Thread(target=self.__listener_thread__)
        self.__poll_thread__.setDaemon(True)

        # Opens persistent data storage, initializes if necessary
        self.__data__ = shelve.open(self.__data_file__, writeback=True)
        if self.__data__ == {}:
            for i in range(10):
                # Note: Shelves don't allow integer keys, casting to str to workaround
                self.__data__[str(i)] = {"num_vals": 0, "vals": []}

    # Starts the polling thread
    def start_polling(self):
        if not self.__thread_started__.is_set():
            self.__thread_started__.set()
            self.__poll_thread__.start()

    # Stops the polling thread
    def stop_polling(self):
        if self.__thread_started__.is_set():
            self.__thread_started__.unset()
            self.__poll_thread__.join()

    # Returns the difference of the most recent value and the most recent value for a given level
    def get_delta(self, level):
        # No values at lowest level
        if len(self.__data__["0"]["vals"]) == 0:
            return None
        # Compare against next most recent value at the lowest level
        elif level == 0 and len(self.__data__["0"]) > 1:
            return self.__data__["0"]["vals"][-1] - self.__data__["0"]["vals"][-2]
        # Compare against most recent value at given level
        elif 0 < level < 10 and len(self.__data__[str(level)]["vals"]) > 0:
            return self.__data__["0"]["vals"][-1] - self.__data__[str(level)]["vals"][-1]
        else:
            return None

    # Returns the data stored for a given level
    def get_data(self, level):
        dat = self.__data__.get(str(level))
        if dat is not None:
            # Returning a copy of the stored data
            return copy.deepcopy(dat["vals"])
        else:
            return None

    # Polls a sensor at a set rate, adding the data to the persistent data store
    def __listener_thread__(self):
        while self.__thread_started__.is_set():
            self.__add_data_value__(0, self.__poll__())
            time.sleep(1 / self.__poll_rate__)

    # Adds a value to a certain level of the data store
    # Each level increases over the previous by a factor of 10
    # Ex. Assuming a base of 1 second per sample...
    #   1 sec -> 10 sec -> 100 sec (1.7 min) -> 1,000 sec (17.8 min) -> 10,000 sec (2.8 hrs) -> 100,000 sec (28.8 hrs)
    def __add_data_value__(self, idx, val):
        # If we get 10 values, we average them and push them to the next highest level
        if self.__data__[str(idx)]["num_vals"] == 10:
            self.__add_data_value__(idx + 1, reduce(lambda x, y: x + y, self.__data__[str(idx)]["vals"]) / len(self.__data__[str(idx)]["vals"]))
            self.__data__[str(idx)]["num_vals"] = 0

        # Only maintain 10 values at a time on each level, discarding the oldest values
        if len(self.__data__[str(idx)]["vals"]) == 10:
            self.__data__[str(idx)]["vals"].pop(0)
        self.__data__[str(idx)]["num_vals"] += 1
        self.__data__[str(idx)]["vals"].append(val)

        self.__data__.sync()

    # Method stub, MUST be implemented by classes extending Sensor
    @abc.abstractmethod
    def __poll__(self):
        raise NotImplementedError()

    # Method stub. Should return whether or not a sensor is available for use
    @abc.abstractmethod
    def sensor_available(self):
        raise NotImplementedError()
