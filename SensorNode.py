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

# Trigger check whenever this node recieves a message (server request)
def callback(ch, method, properties, body):
	msg_recvd.set()

# This function returns the probablity of table being occupied
#  based on sensor data and the SVM
def get_prob_occupied():
	return 0

try:
	while True:
	#State 0 is idle
		if state == "IDLE":
			# Leave IDLE on message recv
			if msg_recvd.is_set():
				# Only query the user if the probability of occupation is low
				if get_prob_occupied() < .25:
					state = "QUERY"
					
					# Display message to the table
					display.set_message("ARE YOU STILL THERE?")
					display.set_mode(2)
					display.start()
					wait30 = time.time() + 30
				# Otherwise ignore the request
				else:
					pass
				msg_recvd.unset()
	#State 1 is waiting for user input
		elif state == "QUERY":
			now = time.time()
			# If button is pressed, silence requests for 10 minutes
			if listener.button_pressed():
				state = "IGNORE"
				wait600 = time.time() + 600
				
				# Stop the display, display the stop sign
				display.stop()
				display.set_mode(2)
				display.start()
			# Otherwise if a user doesn't press the button within 30 seconds...
			elif now > wait30:
				state = "RESERVE"
				wait600 = time.time() + 600

				# Display a message saying this table is now reserved
				display.stop()
				display.set_message("--- RESERVED TABLE (%d) ---" % (TABLE_NUM))
				display.start()

				# Respond back to the central server with a message, including this node's number
	#State 2 is when the table is reserved
		elif state == "RESERVE":
			# When the user gets to the table and presses the button (or they don't get here within ten minutes) revert back to idle
			if listener.button_pressed()and time.time() > wait600:
				state = "IDLE"
				display.stop()
	#State 3 is when the pi ignores requests
		elif state == "IGNORE":	
			now = time.time()
			# Revert back to IDLE when the user presses the button OR 10 minutes have passed
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
