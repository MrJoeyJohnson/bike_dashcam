# dashcam.py
# A Raspberry Pi powered, GPS enabled, 3D printed bicycle dashcam
# By Matthew Timmons-Brown, The Raspberry Pi Guy

# Import necessary modules
import pygame
import picamera
import fnmatch
import os
import sys
import io
import atexit
import time
import threading
import subprocess
import gps
import RPi.GPIO as GPIO
 
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

# Startup and setup Pygame and screen
pygame.init()
pygame.mouse.set_visible(False)
screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)

# Route to folder for videos
# route = "/home/pi/bike_dashcam/videos"
# Set route and mount USB stick
route = "/media/usb"
subprocess.call(["sudo", "mount", "-t", "vfat", "/dev/sda1", "/media/usb"])

# Setup GPIO pin for low battery detection
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN)

# Setup GPS
subprocess.call(["sudo", "killall", "gpsd"])
subprocess.call(["sudo", "gpsd", "/dev/ttyS0", "-F", "/var/run/gpsd.sock"])
session = gps.gps("localhost", "2947")
session.stream(gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)

class Icon:
	"""A simple icon bitmap class that connects a name to a pygame image"""
	
	def __init__(self, name):
		self.name = name
		try:
			self.bitmap = pygame.image.load("/home/pi/bike_dashcam/media/" + name + ".png")
		except:
			pass

class Button:
	"""A button class to control all aspects of touchscreen buttons"""
	
	def __init__(self, rect, **kwargs):
		self.rect = rect
		self.icon_name = None
		self.icon = None
		self.callback = None
		self.value = None
		# All of the properties a button can have:
		# Name, linked icon file, its own callback function etc
		for key, value in kwargs.iteritems():
			if key == "icon": self.icon = value
			elif key == "icon_name": self.icon_name = value
			elif key == "callback": self.callback = value
			elif key == "value": self.value = value

	# Function to check whether or not a button has been pressed
	# If pressed, trigger that button's callback function, if it has one
	def selected(self, pos):
		# If position of touch was within button rectangle, trigger callback
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

	# Function to draw a button onto the screen
	def draw(self, screen):
		if self.icon:
			screen.blit(self.icon.bitmap,(self.rect[0]+(self.rect[2]-self.icon.bitmap.get_width())/2, self.rect[1]+(self.rect[3]-self.icon.bitmap.get_height())/2))
		else:
			pass

# Create and populate an icon list. This approach allows the addition of unlimited number of icons
icons = []
for file in os.listdir("/home/pi/bike_dashcam/media/"):
	if fnmatch.fnmatch(file, '*.png'):
		icons.append(Icon(file.split('.')[0]))

class VideoThread(threading.Thread):
	"""A threading class to control video recording whilst maintaining touch capabilities"""	

	def __init__(self, path):
		threading.Thread.__init__(self)
		self.path = path
		self.vid_count = 0

	def run(self):
		global busy
		while tinterrupt == False:
			self.recording()
		# Change global busy value, as no longer busy
		busy = False

	def recording(self):
		gps = get_gps()

		# Looping recording - will overwrite old video files
		if self.vid_count >= 135: # More than 30 minutes of recording time, theoretically 4GB 
			self.vid_count = 0
		video_path = (self.path + "%s.h264" % self.vid_count)
		self.vid_count += 1		

		# For filming puposes - this records and stores EVERY clip -  will fill up your whole storage medium!
#		while os.path.exists(video_path):
#			self.vid_count += 1
#			video_path = (self.path + "%s.h264" % self.vid_count)
#			print video_path

		# Record in 15 second videos

		subprocess.call(["raspivid", "-o", video_path, "-t", "15000", "-ae", "60,0xff,0x808000", "-a", str(gps)])

# Video callback function
# When go button is pressed, this executes. Starts a thread that records 30 second videos
def start_video_callback():
	global busy
	busy = True
	global camera_is_definitely_on
	camera_is_definitely_on = False
	camera.close()
	screen.fill((0,0,0))
	pygame.display.update()
	new_video_thread = VideoThread(route + "/dash")
	new_video_thread.start()

# Shutdown callback function
# When shutdown button is pressed, this executes. Shuts down the Pi safely
def shutdown_callback():
	subprocess.call(["sudo", "shutdown", "now"])
		
# List of buttons
buttons = [Button((0,0,50,50), icon_name='go', callback=start_video_callback), Button((270,0,50,50), icon_name='shutdown', callback=shutdown_callback)]

# Assign icons to buttons
for b in buttons:
	for i in icons:
		if b.icon_name == i.name:
			b.icon = i
			b.icon_name = None

# Init go/shutdown buttons
go = buttons[0]
shutdown = buttons[1]

# Live streaming function
# When the device is not busy recording, this streams the camera output to the PiTFT
def stream_to_screen():
	stream = io.BytesIO()
        camera.capture(stream, use_video_port=True, format='raw')
	stream.seek(0)
	stream.readinto(yuv)
	stream.close()
	yuv2rgb.convert(yuv, rgb, size[0], size[1])
	img = pygame.image.frombuffer(rgb[0:(size[0]*size[1]*3)], size, 'RGB')
	screen.blit(img, ((width - img.get_width() ) / 2, (height - img.get_height()) / 2))

	# Overlay and draw the buttons, then update the display
	go.draw(screen)
	shutdown.draw(screen)	
	pygame.display.update()

# GPS function
# Retrieves current GPS coordinates
# Have found the GPS boards to be quite temperamental and take a few goes to get going
def get_gps():
	report = session.next()
	if report['class'] == 'TPV':
		if hasattr(report, 'lat') and hasattr(report, 'lon'):
			output = (report.lat, report.lon)
		else:
			output = "No GPS"
	else:
		output = "No GPS"
	return output
	
# Set up global and local variables
global busy
busy = False
global tinterrupt
tinterrupt = False

old_busy = True

global camera_is_definitely_on
camera_is_definitely_on = False

### Main body of code ###

while True:
 
	while True:
		# For every touch press, execute button callback or interrupt recording
		for event in pygame.event.get():
			if(event.type is pygame.MOUSEBUTTONDOWN):
				if busy == True:
					tinterrupt = True
				else:
					pos = pygame.mouse.get_pos()
					print pos
					for b in buttons:
						if b.selected(pos):
							break
		break

	# If a recording has just stopped, re-enable the camera in Python
	# PiCamera cannot be used at the same time as recording
	# Throws up some nasty errors - GPU related?
	if (busy == False) and (old_busy == True):
		camera = picamera.PiCamera()
		atexit.register(camera.close)
		camera.resolution = size
		camera.crop = (0.0,0.0,1.0,1.0)
		camera_is_definitely_on = True

	old_busy = busy

	# Low battery detection on pin 21
	# Pin drops to 0 if low battery detected
	low_battery = GPIO.input(21)
	if low_battery == 0:
		screen.fill((255,0,0))
		pygame.display.update()
		shutdown_callback()

	# Stream to display
	while not busy and camera_is_definitely_on:
		stream_to_screen()
		break
