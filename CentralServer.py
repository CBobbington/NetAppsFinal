#!/usr/bin/env python

from zeroconf import Zeroconf, ServiceInfo
import DisplayRunner
import netifaces, socket
import logging, logging.config
import json, shelve
import RPi.GPIO as GPIO
import pika
import time, math
import threading

class CentralServer:
	_server_name = "CentralServer"
	_vhost = "/bottle"
	_exchange = "pebble"
	_routing_key = "central"
		
	def _get_service_name(self):
		return CentralServer._server_name + "._http._tcp.local."
		
	def _get_service_ip(self):
		wlanIfaceAddrs = netifaces.ifaddresses('wlan0')
		ethIfaceAddrs = netifaces.ifaddresses('eth0')

		if netifaces.AF_INET in ethIfaceAddrs and "addr" in ethIfaceAddrs[netifaces.AF_INET][0]:
			return ethIfaceAddrs[netifaces.AF_INET][0]["addr"], "eth0"
		elif netifaces.AF_INET in wlanIfaceAddrs and "addr" in wlanIfaceAddrs[netifaces.AF_INET][0]:
			return wlanIfaceAddrs[netifaces.AF_INET][0]["addr"], "wlan0"
		else:
			return None, None
		
	def __init__(self, listen_pin):
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BOARD)
		GPIO.setup(listen_pin, GPIO.IN)
		self._pin = listen_pin
		
		self._log_fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%b %d %H:%M:%S")
		self._log = logging.getLogger()
		self._log.setLevel(logging.INFO)
		
		streamHandler = logging.StreamHandler()
		streamHandler.setLevel(logging.DEBUG)
		streamHandler.setFormatter(self._log_fmt)
		self._log.addHandler(streamHandler)
		
		self._display = DisplayRunner.DisplayRunner()
		self._display.set_mode(0)
		self._display.start()
			
		self._new_connections = []
		self._accept_responses = threading.Event()
		self._responses = []
		
		self._conn = pika.BlockingConnection(pika.ConnectionParameters(host="localhost", virtual_host=self._vhost))	
		self._chan = self._conn.channel()
		
		queueResult = self._chan.queue_declare(exclusive=True)
		if queueResult is None:
			self._log.error("Could not create connect queue")
			raise RuntimeError("Error configuring RabbitMQ")
		else:
			self._log.info("Created queue \'%s\'" % (queueResult.method.queue,))
			self._log.info("Using exchange \'%s/%s\'" % (self._vhost, self._exchange,))
			self._chan.exchange_declare(exchange=self._exchange, type="topic", auto_delete=True)
			self._chan.queue_bind(exchange=self._exchange, queue=queueResult.method.queue, routing_key=self._routing_key)
			self._chan.basic_consume(
				lambda ch, method, prop, body: self._consume(ch, method, prop, body),
				queueResult.method.queue, 
				no_ack=True, 
				exclusive=True, 
			)
		self._queue_name = queueResult.method.queue
		
		server_ip, ifaceName = self._get_service_ip()
		if server_ip is None:
			self._log.error("Could not determine server IP")
			raise RuntimeError("Error finding server IP")
		else:
			self._log.info("Broadcasting service %s with IP %s (%s)" % (self._get_service_name(), server_ip, ifaceName))
		
		# Configure zeroconf to broadcast this service
		self._zeroconf = Zeroconf()
		self._zeroconf_info = ServiceInfo("_http._tcp.local.",
			self._get_service_name(),
			socket.inet_aton(server_ip),
			5672, 0, 0,
			{"exchange_name": self._exchange, "routing_key": self._routing_key, "virtual_host": self._vhost},
			None)
		
		try:
			self._zeroconf.register_service(self._zeroconf_info)
		except Zeroconf.NonUniqueNameException:
			self._log.warn("Service with name \'%s\' already broadcasting on this network!" % (self._get_service_name(),))
		
	def start(self):
		state = "IDLE_INIT"
		startTime = None
		msg = None
		try:
			while True:
				if state == "IDLE_INIT":
					self._display.set_message("NEED A TABLE?")
					self._display.set_mode(2)
					state = "IDLE"
				elif state == "IDLE":
					# If new nodes join the network, display them on the screen
					if len(self._new_connections) > 0:
						# Display / log newly connected nodes, if present
						pass
					# Otherwise if the user presses the button, ping the network and wait
					elif GPIO.input(self._pin):
						self._accept_responses.set()
						self.ping()
						
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("SEARCHING...")
						self._display.set_mode(2)
						
						startTime = time.time()
						state = "WAIT_FOR_RESPONSE"
				elif state == "WAIT_FOR_RESPONSE":
					timeElapsed = math.floor(time.time() - startTime)
					msg = channel.basic_get(queue=self._queue_name, no_ack=True)
					# If nodes respond, pick a node from the list of responses and display it
					if msg[0] is not None:
						self._log.info("RESPONSES RECEIVED %s" % str(msg[3]))
						
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("TABLE %s IS FREE" % str(msg[3]))
						self._display.set_mode(2)
						
						state = "DISPLAY_RESULT"
					# Or if 30 seconds pass then all tables are probably full
					elif timeElapsed > 30:
						self._log.info("REQUEST TIMED OUT")
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("SORRY, COULDN'T FIND ANYTING!")
						self._display.set_mode(2)
						
						startTime = time.time()
						self._accept_responses.clear()
						state = "DISPLAY_TIMEOUT"
					# ... Or if the user presses the button, cancel the request
					elif GPIO.input(self._pin):
						self._log.info("REQUEST CANCELLED")
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("REQUEST CANCELLED")
						self._display.set_mode(2)
						
						startTime = time.time()
						self._accept_responses.clear()
						state = "REQ_CANCEL"
				elif state == "DISPLAY_RESULT":
					if time.time() > (startTime + 15):
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("NEED A TABLE?")
						self._display.set_mode(2)
						
						state = "IDLE"
				elif state == "DISPLAY_TIMEOUT":
					if time.time() > (startTime + 15):
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("NEED A TABLE?")
						self._display.set_mode(2)
						
						state = "IDLE"
				elif state == "REQ_CANCEL":
					# Display cancelled message
					if time.time() > (startTime + 15):
						self._display.set_mode(0)
						time.sleep(0.5)
						self._display.set_message("NEED A TABLE?")
						self._display.set_mode(2)
						
						state = "IDLE"
				else:
					state = "IDLE_INIT"
				time.sleep(0.5)
		except KeyboardInterrupt:
			pass
		finally:
			self._display.set_mode(0)
			self._chan.stop_consuming()
			self._log.info("Shutting down server...")
			self._log.info("Closing connection with RabbitMQ")
			if self._conn is not None:
				self._conn.close()
			
			self._log.info("Unregistering server")
			self._zeroconf.unregister_service(self._zeroconf_info)
			self._zeroconf.close()
		
			self._log.info("Shutdown complete!")
		
	def ping(self):
		self._responses = []
		self._log.info("Pinging network...")
		tempConn = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', virtual_host=self._vhost))
		tempChan = tempConn.channel()
		tempChan.basic_publish(exchange=self._exchange, routing_key="node", body="")
		tempConn.close()
		
	def _consume(self, ch, method, properties, body):
		print "MSG: %s" % body

if __name__ == "__main__":
	server = CentralServer(37)
	server.start()
		
