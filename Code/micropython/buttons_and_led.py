import time
from machine import Pin
import asyncio

_frames = [[0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,0],
          [0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0],
          [0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0],
          [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1]]

_buttons = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

LED_LAT = Pin("GPIO16",Pin.OUT)
LED_BLANK = Pin("GPIO17",Pin.OUT)
LED_BLANK.value(0)
LED_SIN = Pin("GPIO18",Pin.OUT)
LED_SCLK = Pin("GPIO19",Pin.OUT)


SW = [
  Pin("GPIO12",Pin.IN,Pin.PULL_UP),
  Pin("GPIO8",Pin.IN,Pin.PULL_UP),
  Pin("GPIO4",Pin.IN,Pin.PULL_UP),
  Pin("GPIO0",Pin.IN,Pin.PULL_UP),
  Pin("GPIO13",Pin.IN,Pin.PULL_UP),
  Pin("GPIO9",Pin.IN,Pin.PULL_UP),
  Pin("GPIO5",Pin.IN,Pin.PULL_UP),
  Pin("GPIO1",Pin.IN,Pin.PULL_UP),
  Pin("GPIO14",Pin.IN,Pin.PULL_UP),
  Pin("GPIO10",Pin.IN,Pin.PULL_UP),
  Pin("GPIO6",Pin.IN,Pin.PULL_UP),
  Pin("GPIO2",Pin.IN,Pin.PULL_UP),
  Pin("GPIO15",Pin.IN,Pin.PULL_UP),
  Pin("GPIO11",Pin.IN,Pin.PULL_UP),
  Pin("GPIO7",Pin.IN,Pin.PULL_UP),
  Pin("GPIO3",Pin.IN,Pin.PULL_UP)
] 

def make_handler(i):
    def handler(t):
        _buttons[i] = t.value()
        print(f"button {i} to {_buttons[i]}")
        on = 0 if _buttons[i] else 1 
        set_pixel_lin(i,on,on,on)
    return handler

for i in range(16):
  SW[i].irq(make_handler(i))


def set_pixel(x,y,r,g,b):
  _frames[x][3*y + 0] = r
  _frames[x][3*y + 1] = g
  _frames[x][3*y + 2] = b

def set_pixel_lin(i,r,b,g):
  y = int(i % 4)
  x = int((i - y) / 4)
  set_pixel(x,y,r,b,g)

def _set_leds(array_bits):
  for bit in array_bits:
    LED_SCLK.value(0)
    LED_SIN.value(bit)
    # time.sleep_ms(5)
    LED_SCLK.value(1)
    # time.sleep_ms(5)
  # time.sleep_ms(5)
  LED_LAT.value(1)
  # time.sleep_ms(5)
  LED_LAT.value(0)

async def display_loop():
  while True:
    for frame in _frames:
      _set_leds(frame)
    # Let another thread take a moment
    await asyncio.sleep(0)

async def main():
    asyncio.create_task(display_loop())
    while True:
      # for col in [0,1,2,3]:
      #   print(f"testing {col}")
      #   set_pixel(col,0,1,0,0)
      #   set_pixel(col,1,0,1,0)
      #   set_pixel(col,2,1,1,0)
      #   set_pixel(col,3,0,0,1)
      #   set_pixel(col-1 if col > 0 else 3,0,0,0,0)
      #   set_pixel(col-1 if col > 0 else 3,1,0,0,0)
      #   set_pixel(col-1 if col > 0 else 3,2,0,0,0)
      #   set_pixel(col-1 if col > 0 else 3,3,0,0,0)
      #   await asyncio.sleep_ms(500)
      if not _buttons[0]:
        for lin in range(15):
          set_pixel_lin(lin,0,0,0)
          set_pixel_lin((lin+1)%16,1,0,0)
          set_pixel_lin((lin+2)%16,0,1,0)
          set_pixel_lin((lin+3)%16,1,1,0)
          set_pixel_lin((lin+4)%16,0,0,1)
          set_pixel_lin((lin+5)%16,1,0,1)
          set_pixel_lin((lin+6)%16,0,1,1)
          set_pixel_lin((lin+7)%16,1,1,1)
          await asyncio.sleep_ms(50)
      else:
        await asyncio.sleep_ms(50)


# def test_red_leds():
#   set_leds([1,0,0,1,0,0,1,0,0,1,0,0,1,0,0,0])
#   # time.sleep_ms(100)
#   set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,1,0,0])
#   # time.sleep_ms(100)
#   set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,0,1,0])
#   # time.sleep_ms(100)
#   set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,0,0,1])
#   # time.sleep_ms(100)

# def test_green_leds():
#   set_leds([0,1,0,0,1,0,0,1,0,0,1,0,1,0,0,0])
#   # time.sleep_ms(100)
#   set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,1,0,0])
#   # time.sleep_ms(100)
#   set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,0,1,0])
#   # time.sleep_ms(100)
#   set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,1])
#   # time.sleep_ms(100)

# def test_blue_leds():
#   set_leds([0,0,1,0,0,1,0,0,1,0,0,1,1,0,0,0])
#   # time.sleep_ms(100)
#   set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,1,0,0])
#   # time.sleep_ms(100)
#   set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,0,1,0])
#   # time.sleep_ms(100)
#   set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,0,0,1])
#   # time.sleep_ms(100)

asyncio.run(main())

# while True:
#   led.toggle()
#   display_leds()
  # set_leds([1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1])
