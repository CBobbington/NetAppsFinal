import RPi.GPIO as GPIO
import threading

class ButtonListener:
	def __init__(self, pin):
		self._pin = pin
		
		self._thread_started = threading.Event()
		self._thread = threading.Thread(target=self._listener)
		self._thread.setDaemon(True)
		
		self._is_triggered = threading.Event()
		self._is_triggered.clear()
		
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BOARD)
		try:
			GPIO.setup(pin, GPIO.IN)
		except RuntimeError:
			raise RuntimeError("Could not configure GPIO pins")
		
	def start(self):
		if not self._thread_started.is_set() and pin is not None:
			self._thread_started.set()
			self._thread.start()
			
	def stop(self):
		if self._thread_staretd.is_set():
			self._thread_started.clear()
			self._thread.join()
			
	def button_pressed(self):
		return self._is_triggered.is_set()
	
	def _listener(self):
		while self._thread_started.is_set():
			if GPIO.input(self._pin):
				self._is_triggered.set()
			else:
				self._is_triggered.unset()
		self._is_triggered.unset()
		