import exampleSensor, exampleSensor2

if __name__ == "__main__":
    # Starts 2 sensors
    test_sensor = exampleSensor.ExampleSensor()
    test_sensor2 = exampleSensor2.ExampleSensor()
    test_sensor.start_polling()
    test_sensor2.start_polling()

    # Available commands are 'display <num> <level>' and 'delta <num> <level>'
    try:
        while True:
            cmd = raw_input("> ").split()
            if cmd[0].lower() == "display" and len(cmd) > 2:
                if cmd[1] == "1":
                    print test_sensor.get_data(int(cmd[2]))
                elif cmd[1] == "2":
                    print test_sensor2.get_data(int(cmd[2]))
            elif cmd[0] == "delta" and len(cmd) > 1:
                if cmd[1] == "1":
                    print test_sensor.get_delta(int(cmd[2]))
                elif cmd[1] == "2":
                    print test_sensor2.get_delta(int(cmd[2]))

    except KeyboardInterrupt:
        test_sensor.stop_polling()
        test_sensor2.stop_polling()
        quit(0)
