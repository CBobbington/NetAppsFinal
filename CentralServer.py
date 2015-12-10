#!/usr/bin/env python

from zeroconf import Zeroconf, ServiceInfo
import ButtonListener
import netifaces, socket
import logging, logging.config
import json, shelve
import RPi.GPIO as GPIO
import pika
import time, math

class CentralServer:
	def __init__(self):
		self._server_name = "CentralServer"
		self._vhost = "/sense"
		self._exchange = "sense_net"
		self._response_key = "central_response"
		self._connection_key = "central_connect"
		
		self._gpio_en = None
		self._log_fmt = logging.Formatter(fmt="%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%b %d %H:%M:%S")
		self._log = logging.getLogger()
		self._log.setLevel(logging.INFO)
	
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
		self._state = None
		
		streamHandler = logging.StreamHandler()
		streamHandler.setLevel(logging.DEBUG)
		streamHandler.setFormatter(self._log_fmt)
		self._log.addHandler(streamHandler)
		
		try:
			self._button_listener = ButtonListener.Listener(listen_pin)
		except RuntimeError:
			self._log.error("Could not configure GPIO pins!")
			return False
		
		self._conn = pika.BlockingConnection(pika.ConnectionParameters(host="localhost", virtual_host=self._vhost))	
		
		self._response_chan = self._conn.channel()
		self._responses = []
		self._accept_responses = threading.Event()
		queueResult = self._response_chan.queue_declare(exclusive=True)
		if queueResult is None:
			self._log.error("Could not create response queue")
			return False
		else:
			self._log.info("Created response queue \'%s\'" % (queueResult.method.queue,))
			self._log.info("Using exchange \'%s\'" % (self._exchange,))
			self._response_chan.exchange_declare(exchange=self._exchange, type="topic", auto_delete=True)
			self._response_chan.queue_bind(exchange=self._exchange, queue=queueResult.method.queue, routing_key=self._response_key)
			self._response_chan.basic_consume(self._response_consumer, queueResult.method.queue, no_ack=True, exclusive=True, arguments=(self))
			
		self._connect_chan = self._conn.channel()
		self._new_connections = []
		queueResult = self._connect_chan.queue_declare(exclusive=True)
		if queueResult is None:
			self._log.error("Could not create connect queue")
			return False
		else:
			self._log.info("Created connect queue \'%s\'" % (queueResult.method.queue,))
			self._log.info("Using exchange \'%s\'" % (self._exchange,))
			self._connect_chan.exchange_declare(exchange=self._exchange, type="topic", auto_delete=True)
			self._connect_chan.queue_bind(exchange=self._exchange, queue=queueResult.method.queue, routing_key=self._connect_key)
			self._connect_chan.basic_consume(self._connect_consumer, queueResult.method.queue, no_ack=True, exclusive=True, arguments=(self))
		
		# Configure zeroconf to broadcast this service
		self._zeroconf = Zeroconf()

		server_ip, ifaceName = self._getServiceIP()
		if server_ip is None:
			self._log.error("Could not determine server IP")
			return False
		else:
			self._log.info("Broadcasting with IP %s (%s)" % (server_ip, ifaceName))
		
		self._zeroconf_info = ServiceInfo("_http._tcp.local.",
			self._get_service_name(),
			socket.inet_aton(server_ip),
			5672, 0, 0,
			{"exchange_name": self._exchange, "respone_key": self._response_key, "connect_key": self._connect_key, "virtual_host": self._vhost},
			None)
		
		try:
			self._zeroconf.register_service(self._zeroconf_info)
		except Zeroconf.NonUniqueNameException:
			self._log.warn("Service with name \'%s\' already broadcasting on this network!" % (self._get_service_name(),))
				
		return True
		
	def start(self):
		state = "IDLE_INIT"
		startTime = None
		try:
			while True:
				if state == "IDLE_INIT":
					self._button_listener.start()
					state = "IDLE"
				elif state == "IDLE":
					if len(self._new_connections) > 0:
						# Display / log newly connected nodes, if present
						pass
					elif self._button_listener.button_pressed():
						self._accept_responses.set()
						startTime = time.time()
						self.ping()
						state = "WAIT_FOR_RESPONSE"
				elif state == "WAIT_FOR_RESPONSE":
					timeElapsed = math.floor(time.time() - startTime)
					if len(responses) > 0:
						self._accept_responses.unset()
						state = "DISPLAY_RESULT"
					elif timeElapsed > 15:
						self._accept_responses.unset()
						state = "DISPLAY_TIMEOUT"
					elif self._button_listener.button_pressed():
						self._accept_responses.unset()
						state = "REQ_CANCEL"
					else:
						# Display time left on display
						pass
				elif state == "DISPLAY_RESULT":
					# Display result
					state = "IDLE"
				elif state == "DISPLAY_TIMEOUT":
					# Display timeout message
					state = "IDLE"
				elif state == "REQ_CANCEL":
					# Display cancelled message
					state = "IDLE"
				else:
					state = "IDLE_INIT"
		except KeyboardInterrupt:
			pass
			
	def stop(self):
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
		
	def _response_consumer(ch, method, properties, body, args):
		print "RESPONSE: %s" % body
		
	def _connect_consumer(ch, method, properties, body, args):
		print "CONNECT: %s" % body