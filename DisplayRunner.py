import threading

import time
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw
from Adafruit_LED_Backpack import Matrix8x8

class DisplayRunner:
	def __init__(self):
		self._mode = 0
		
		self._thread_started = threading.Event()
		self._thread = threading.Thread(target=self._runner)
		self._thread.setDaemon(True)
		
		###
		self._display = Matrix8x8.Matrix8x8()
		self._display.begin()
		self._font =  ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 9)
		self._image = Image.new("1", (8,8), "black")
		self._draw = ImageDraw.Draw(self._image)
		self._message = "TEAM 18"
			
	def start(self):
		if not self._thread_started.is_set():
			self._thread_started.set()
			self._thread.start()
	def stop(self):
		if self._thread_started.is_set():
			self._thread_started.clear() ##
			self._thread.join()
			
	def set_mode(self, mode):
		self._mode = mode
	##
	def set_message(self, buffer):
		self._message = buffer
	
	def _runner(self):
		begin= 0
		end = 7
		prevBegin = 0
		prevEnd = 7
		reverse = False

		while self._thread_started.is_set():
			# Do stuff here based on the mode
			#Mode 0 is screen off
			if self._mode == 0:
				self._draw.rectangle((0,0,7,7), outline = 0, fill = 0)
				self._display.set_image(self._image)
				self._display.write_display()
			#Mode 1 is idle screen
			elif self._mode == 1:
				while self._thread_started.is_set() and self._mode ==1:
					self._display.clear()
					self._draw.rectangle((prevBegin, prevBegin, prevEnd, prevEnd), outline = 0)
					self._draw.rectangle((begin, begin, end, end), outline = 255)
					self._display.set_image(self._image)
					self._display.write_display()
				
					prevBegin = begin
					prevEnd = end
					if reverse == True:
						begin = begin - 1
						end = end +1
					else:
						begin = begin + 1
						end = end - 1

					if begin == 3 or begin == -1:
						reverse = not reverse
					time.sleep(.15)

			#Mode 2 is marquee
			elif self._mode == 2:
				max = len(self._message)*8
				x = 8
				i = 0
				while i < max and self._thread_started.is_set() and self._mode == 2:
					x = x - 1
					if x < -(max + 20):
						x = 8
					self._draw.rectangle((0,0,7,7), outline = 0, fill = 0)
					self._draw.text((x, -1), self._message, 1, font = self._font)
					self._display.set_image(self._image)
					self._display.write_display()
					time.sleep(.04)
					i = i + 1
			#Mode 3 is ignore requests, display stop sign
			elif self._mode == 3:
				self._draw.rectangle((0,0,7,7), outline = 0, fill = 0)
				self._draw.line((0,2,0,5), fill = 255)
				self._draw.line((7,2,7,5), fill = 255)
				self._draw.line((2,0,5,0), fill = 255)
				self._draw.line((2,7,5,7), fill = 255)
				self._draw.line((1,1,1,1), fill = 255)
				self._draw.line((1,6,1,6), fill = 255)
				self._draw.line((6,1,6,1), fill = 255)
				self._draw.line((6,6,6,6), fill = 255)
				self._display.set_image(self._image)
				self._display.write_display()
				while self._thread_started.is_set() and self._mode == 3:
					pass
			self._display.clear()
			self._display.write_display()

##testing
if __name__ == "__main__":
	test = DisplayRunner()
	test.start()
	test.set_message("ARE YOU STILL THERE?")
	y = 0
	try:
		while 1:
			print y
			test.set_mode(y)
			time.sleep(5)
			y = y +1
			if y == 4:
				y = 0
	except KeyboardInterrupt:
		pass
	finally:
		test.stop()
