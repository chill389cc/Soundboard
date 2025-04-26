import time
from machine import Pin

button = Pin(0, Pin.IN, Pin.PULL_UP)

def check_button(pin):
  print("Button down!")

button.irq(trigger=Pin.IRQ_FALLING, handler=check_button)

# Keep the script alive so we can listen for button presses
while True:
  time.sleep(1)


