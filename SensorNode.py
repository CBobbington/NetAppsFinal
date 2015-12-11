import time
import pika
import ButtonListener
import DisplayRunner
from zeroconf import Zeroconf
import threading

#Initialize a bunch of variables
TABLE_NUM = 1
state = 0
req_recv = True
prob_occupied = .1
button_pressed = False
wait30 = time.time()
wait600 = time.time()

zeroconf = Zeroconf()
info = zeroconf.get_service_info('_http._tcp.local.', 'CentralServer._http._tcp.local.')
print( "Address: %s:%d" % (socket.inet_ntoa(info.address), info.port))
print( "Server: %s" % (info.server))
if info.properties:
	print( "Properties: ")
	for key, value in info.properties.items():
		print("            %s: %s"  % (key, value))

print("\n")

credentials = pika.PlainCredentials('client','bottle_pass')
connection = pika.BlockingConnection(pika.ConnectionParameters(socket.inet_ntoa(info.address),info.port, '/bottle', credentials))
channel = connection.channel()
channel.exchange_declare(exchange = info.properties['exchange_name'], passive = True)
result = channel.queue_declare(auto_delete = True)
queue_name = result.method.queue

listener = ButtonListener.listener(21)
listener.start()

display = DisplayRunner.DisplayRunner()

msg_recvd = threading.Event()

def callback(ch, method, properties, body):
	msg_recvd.set()
	


try:
	while True:
	#State 0 is idle
		if state == "IDLE":
			if msg_recvd.is_set():
				if get_prob_occupied() < .5:
					state = "QUERY"
					display.set_message("ARE YOU STILL THERE?")
					display.set_mode(2)
					display.start()
					wait30 = time.time() + 30
				msg_recvd.unset()
	#State 1 is waiting for user input
		elif state == "QUERY":
			now = time.time()
			if listener.button_pressed():
				state = "IGNORE"
				wait600 = time.time() + 600
				display.stop()
				display.set_mode(2)
				display.start()
			elif now > wait30:
				state = "RESERVE"
				wait600 = time.time() + 600
				display.stop()
				display.set_message("--- RESERVED TABLE (%d) ---" % (TABLE_NUM))
				display.start()
	#State 2 is when the table is reserved
		elif state == "RESERVE":
			if listener.button_pressed()and time.time() > wait600:
				state = "IDLE"
				display.stop()
	#State 3 is when the pi ignores requests
		elif state == "IGNORE":	
			now = time.time()
			if listener.button_pressed():
				state = "IDLE"
			else:
				if now > wait600:
					state = "IDLE"
					display.stop()
		print state
except KeyboardInterrupt:
	pass	
finally:
	pass #clean up

	##
