import RPi.GPIO as GPIO
import threading

class DisplayRunner:
	def __init__(self):
		self._mode = 0
		
		self._thread_started = threading.Event()
		self._thread = threading.Thread(target=self._runner)
		self._thread.setDaemon(True)
	def start(self):
		if not self._thread_started.is_set() and self._mode:
			self._thread_started.set()
			self._thread.start()
			
	def stop(self):
		if self._thread_staretd.is_set():
			self._thread_started.clear()
			self._thread.join()
			
	def set_mode(self, mode):
		self._mode = mode
	
	def _runner(self):
		while self._thread_started.is_set():
			# Do stuff here based on the mode