# dashcam.py
# A Raspberry Pi powered, GPS enabled, 3D printed bicycle dashcam
# By Matthew Timmons-Brown, The Raspberry Pi Guy

# Import necessary modules
import pygame
import picamera
import os
import sys
import io
import atexit
# Change path and import Adafruit's yuv2rgb library
sys.path.insert(0, "/home/pi/bike_dashcam/libraries")
import yuv2rgb

# Change screen to PiTFT, init framebuffer/touchscreen environment variables
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_FBDEV'      , '/dev/fb1')
os.putenv('SDL_MOUSEDRV'   , 'TSLIB')
os.putenv('SDL_MOUSEDEV'   , '/dev/input/touchscreen')

# Set size of display and create buffers for display data
size = width, height = 320, 240
rgb = bytearray(320 * 240 * 3)
yuv = bytearray(320 * 240 * 3 / 2)

# Startup and setup Pygame, load graphics
pygame.init()
pygame.mouse.set_visible(False)
screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
go = pygame.image.load("/home/pi/bike_dashcam/media/go.bmp")

# Startup and setup the Raspberry Pi official camera
camera = picamera.PiCamera()
atexit.register(camera.close)
camera.resolution = size
camera.crop = (0.0,0.0,1.0,1.0)

class Button:

	def __init__(self, rect, **kwargs):
		self.rect = rect
		self.icon = None
		self.callback = None
		self.value = None
		for key, value in kwargs.iteritems():
			if key == "icon": self.icon = value
			elif key == "callback": self.callback = value
			elif key == "value": self.value = value

	def selected(self, pos):
		x1 = self.rect[0]
		y1 = self.rect[1]
		x2 = x1 + self.rect[2] - 1
		y2 = y1 + self.rect[3] - 1
		if ((pos[0] >= x1) and (pos[0] <= x2) and (pos[1] >= y1) and (pos[1] <= y2)):
			if self.callback:		
				if self.value is None:
					self.callback()
				else:
					self.callback(self.value)
			return True
		return False

	def draw(self, screen):
		if self.icon:
			screen.blit(self.icon.bitmap,(self.rect[0]+(self.rect[2]-self.icon.bitmap.get_width())/2, self.rect[1]+(self.rect[3]-self.icon.bitmap.get_height())/2))

buttons = [Button((0,0,50,50), icon='go', callback='start_video')]

def start_video():
	screen.fill((0,0,0))

def main():
	for event in pygame.event.get():
		if(event.type is pygame.MOUSEBUTTONDOWN):
			pos = pygame.mouse.get_pos()
			for b in buttons:
				if b.selected: break

        stream = io.BytesIO()
        camera.capture(stream, use_video_port=True, format='raw')
	stream.seek(0)
	stream.readinto(yuv)
	stream.close()
	yuv2rgb.convert(yuv, rgb, size[0], size[1])
	img = pygame.image.frombuffer(rgb[0:(size[0]*size[1]*3)], size, 'RGB')
	screen.blit(img, ((width - img.get_width() ) / 2, (height - img.get_height()) / 2))
	
	screen.blit(go, (0,0))

	pygame.display.update()

while True:
	main()
