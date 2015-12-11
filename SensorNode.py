import time
import pika
import ButtonListener
import DisplayRunner
from zeroconf import Zeroconf
import threading
import socket
import RPi.GPIO as GPIO

#Initialize a bunch of variables
TABLE_NUM = 1
state = "IDLE"
req_recv = True
prob_occupied = .1
button_pressed = False
wait30 = time.time()
wait600 = time.time()

zeroconf = Zeroconf()
info = None

while info is None:
	info = zeroconf.get_service_info('_http._tcp.local.', 'CentralServer._http._tcp.local.')

print( "Address: %s:%d" % (socket.inet_ntoa(info.address), info.port))
print( "Server: %s" % (info.server))
if info.properties:
	print( "Properties: ")
	for key, value in info.properties.items():
		print("            %s: %s"  % (key, value))

print("\n")

msg_recvd = threading.Event()
def callback(ch, method, properties, body):
	print "MSG: %s" % body
	msg_recvd.set()

credentials = pika.PlainCredentials('client','bottle_pass')
connection = pika.BlockingConnection(pika.ConnectionParameters(socket.inet_ntoa(info.address),info.port, '/bottle', credentials))
channel = connection.channel()
channel.exchange_declare(exchange = "pebble", passive = True)
result = channel.queue_declare(auto_delete = True)
channel.queue_bind(exchange="pebble", queue=result.method.queue, routing_key="node")

display = DisplayRunner.DisplayRunner()
display.set_mode(0)
display.start()

GPIO.setmode(GPIO.BOARD)
GPIO.setup(37, GPIO.IN)
	
def get_prob_occupied():
	return 1
	
try:
	while True:
	#State 0 is idle
		if state == "IDLE":
			msg = channel.basic_get(queue=result.method.queue, no_ack=True)
			if msg[0] is None and msg[1] is None and msg[2] is None:
				if get_prob_occupied() < .5:
					state = "QUERY"
					
					display.set_message("ARE YOU STILL THERE?")
					display.set_mode(2)
					display.start()
					
					wait30 = time.time() + 30
				msg_recvd.clear()
	#State 1 is waiting for user input
		elif state == "QUERY":
			now = time.time()
			if GPIO.input(37):
				state = "IGNORE"
				wait600 = time.time() + 600
			elif time.time() > wait30:
				display.set_mode(3)
				state = "RESERVE"
				wait600 = time.time() + 600
				
				channel.basic_publish(exchange = info.properties['exchange_name'], routing_key = info.properties['routing_key'], body = str(TABLE_NUM))
				
				display.set_mode(0)
				time.sleep(0.5)
				display.set_message("--- RESERVED TABLE (%d) ---" % (TABLE_NUM))
				display.set_mode(2)
	#State 2 is when the table is reserved
		elif state == "RESERVE":
			if listener.button_pressed()and time.time() > wait600:
				display.set_mode(0)
				state = "IDLE"
	#State 3 is when the pi ignores requests
		elif state == "IGNORE":	
			now = time.time()
			if listener.button_pressed():
				display.set_mode(0)
				state = "IDLE"
			else:
				if now > wait600:
					display.set_mode(0)
					state = "IDLE"
		print state
		time.sleep(0.5)
except KeyboardInterrupt:
	pass	
finally:
	pass #clean up

	##
