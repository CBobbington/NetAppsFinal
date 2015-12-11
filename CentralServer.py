#!/usr/bin/env python

from zeroconf import Zeroconf, ServiceInfo
import ButtonListener, DisplayRunner
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

		if netifaces.AF_INET in wlanIfaceAddrs and "addr" in wlanIfaceAddrs[netifaces.AF_INET][0]:
			return wlanIfaceAddrs[netifaces.AF_INET][0]["addr"], "wlan0"
		elif netifaces.AF_INET in ethIfaceAddrs and "addr" in ethIfaceAddrs[netifaces.AF_INET][0]:
			return ethIfaceAddrs[netifaces.AF_INET][0]["addr"], "eth0"
		else:
			return None, None
		
	def __init__(self, listen_pin):
		self._gpio_en = None
		self._log_fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%b %d %H:%M:%S")
		self._log = logging.getLogger()
		self._log.setLevel(logging.INFO)
		
		streamHandler = logging.StreamHandler()
		streamHandler.setLevel(logging.DEBUG)
		streamHandler.setFormatter(self._log_fmt)
		self._log.addHandler(streamHandler)
		
		try:
			self._button_listener = ButtonListener.Listener(listen_pin)
		except RuntimeError:
			self._log.error("Could not configure GPIO pins!")
			raise RuntimeError("Error configuring GPIO")
			
		self._display = DisplayRunner.DisplayRunner()
		self._display.set_mode(0)
		self._display.start()
		self._display.stop()
			
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
			self._log.info("Using exchange \'%s\\%s\'" % (self._vhost, self._exchange,))
			self._chan.exchange_declare(exchange=self._exchange, type="topic", auto_delete=True)
			self._chan.queue_bind(exchange=self._exchange, queue=queueResult.method.queue, routing_key=self._routing_key)
			self._chan.basic_consume(
				lambda ch, method, prop, body: self._consume(ch, method, prop, body),
				queueResult.method.queue, 
				no_ack=True, 
				exclusive=True, 
			)
		
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
		try:
			while True:
				if state == "IDLE_INIT":
					self._button_listener.start()
					state = "IDLE"
				elif state == "IDLE":
					# If new nodes join the network, display them on the screen
					if len(self._new_connections) > 0:
						# Display / log newly connected nodes, if present
						pass
					# Otherwise if the user presses the button, ping the network and wait
					elif self._button_listener.button_pressed():
						self._accept_responses.set()
						self._display.set_message("SEARCHING...")
						self._display.start()
						startTime = time.time()
						self.ping()
						state = "WAIT_FOR_RESPONSE"
				elif state == "WAIT_FOR_RESPONSE":
					timeElapsed = math.floor(time.time() - startTime)
					# If nodes respond, pick a node from the list of responses and display it
					if len(self._responses) > 0:
						self._accept_responses.unset()
						state = "DISPLAY_RESULT"
					# Or if 30 seconds pass then all tables are probably full
					elif timeElapsed > 30:
						self._display.stop()
						self._display.set_message("SORRY, COULDN'T FIND ANYTING!")
						self._display.start()
						startTime = time.time()
						
						self._accept_responses.unset()
						state = "DISPLAY_TIMEOUT"
					# ... Or if the user presses the button, cancel the request
					elif self._button_listener.button_pressed():
						self._display.stop()
						self._display.set_message("REQUEST CANCELLED")
						self._display.start()
						startTime = time.time()
						
						self._accept_responses.unset()
						state = "REQ_CANCEL"
				elif state == "DISPLAY_RESULT":
					# Display node to go to
					state = "IDLE"
				elif state == "DISPLAY_TIMEOUT":
					if time.time() > (startTime + 15):
						self._display.stop()
						state = "IDLE"
					time.sleep(1)
				elif state == "REQ_CANCEL":
					# Display cancelled message
					if time.time() > (starTime + 15):
						self._display.stop()
						state = "IDLE"
					state = "IDLE"
					time.sleep(1)
				else:
					state = "IDLE_INIT"
		except KeyboardInterrupt:
			pass
		finally:
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
		_log.info("Pinging network...")
		tempConn = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', virtual_host=self._vhost))
		tempChan = tempConn.channel()
		tempChan.queue_declare(queue=str(dest), passive=True)
		tempChan.basic_publish(exchange=self._exchange, routing_key="node")
		tempConn.close()
		
	def _consume(self, ch, method, properties, body):
		print "MSG: %s" % body

if __name__ == "__main__":
	server = CentralServer(21)
	server.start()
		
