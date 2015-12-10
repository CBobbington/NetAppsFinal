#!/usr/bin/env python

from zeroconf import Zeroconf, ServiceInfo
import ButtonListener
import netifaces, socket
import logging, logging.config, sys, os, argparse
import json, shelve
import fnmatch
import RPi.GPIO as GPIO
import pika

class CentralServer:
	def __init__(self):
		self._server_name = "CentralAlertServer"
		self._vhost = "/sense"
		self._exchange = "sensor_net"
		self._routing_key = "central_server"
		
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
			
	def ping(self):
		_log.info("Pinging network...")
		tempConn = pika.BlockingConnection(pika.ConnectionParameters(host='localhost', virtual_host=self._vhost))
		tempChan = tempConn.channel()
		tempChan.queue_declare(queue=str(dest), passive=True)
		tempChan.basic_publish(exchange=self._exchange, routing_key="sensor_node")
		tempConn.close()
		
	def start(self):
		streamHandler = logging.StreamHandler()
		streamHandler.setLevel(logging.DEBUG)
		streamHandler.setFormatter(self._log_fmt)
		self._log.addHandler(streamHandler)
		
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BOARD)
		try:
			self._button_listener = ButtonListener()
			self._button_listener.start()
		except RuntimeError:
			self._log.warn("Could not configure GPIO pins!")
			exit(1)
			
		conn = pika.BlockingConnection(pika.ConnectionParameters(host="localhost", virtual_host=self._vhost))	
		chan = conn.channel()

		queueResult = chan.queue_declare(exclusive=True)
		if queueResult is None:
			self._log.error("Could not create queue")
			exit(1)
		else:
			self._log.info("Created queue \'%s\'" % (queueResult.method.queue,))
		
		self._log.info("Using exchange \'%s\'" % (self._exchange,))
		chan.exchange_declare(exchange=self._exchange, type="direct", auto_delete=True)
		chan.queue_bind(exchange=self._exchange, queue=queueResult.method.queue, routing_key=self._routing_key)
		chan.basic_consume(handle_response, queueResult.method.queue, no_ack=True, exclusive=True)

		# Configure zeroconf to broadcast this service
		zeroconf = Zeroconf()

		server_ip, ifaceName = self._getServiceIP()
		if server_ip is None:
			self._log.error("Could not determine server IP")
			exit(1)
		else:
			self._log.info("Broadcasting with IP %s (%s)" % (server_ip, ifaceName))
		
		zeroconf_info = ServiceInfo("_http._tcp.local.",
			self._get_service_name(),
			socket.inet_aton(server_ip),
			5672, 0, 0,
			{"exchange_name": self._exchange, "routing_key": self._routing_key, "virtual_host": self._vhost},
			None)
		
		try:
			zeroconf.register_service(zeroconf_info)
		except Zeroconf.NonUniqueNameException:
			self._log.warn("Service with name \'%s\' already broadcasting on this network!" % (self._get_service_name(),))

		try:
			while True:
				while not self._button_listener.button_pressed():
					pass
				print "Button Press!"
		except KeyboardInterrupt:
			chan.stop_consuming()
			pass
		finally:
			self._log.info("Shutting down server...")
			self._log.info("Closing connection with RabbitMQ")
			if conn is not None:
				conn.close()
			
			self._log.info("Unregistering server")
			zeroconf.unregister_service(zeroconf_info)
			zeroconf.close()
		
			self._log.info("Shutdown complete!")
