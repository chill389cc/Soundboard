# from typing import Callable, Optional
import time
import random
from machine import Pin
import asyncio


def lin_to_pos(lin) -> tuple[int,int]:
   y = int(lin % 4)
   x = int((lin - y) / 4)
   return (x,y)

def pos_to_lin(x,y) -> int:
   lin = x*4 + y
   return lin

class LedMatrix:
  # These are the write line for the led matrix, the first 12 values are RGB values
  # The last 4 bits signal what column is active. Technically any number of columns can be active
  # but for simplicity we activate one at a time. :shrug:    
  _lines = [[0,0,0,0,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,0,0,0,0],
            [0,0,0,0,0,0,0,0,0,0,0,0]]
  _line_markers = [[1,0,0,0],
                   [0,1,0,0],
                   [0,0,1,0],
                   [0,0,0,1]]
  # frame scale sets the color scale. ex. a scale of 10 would allow each color to range from 0-10
  _frame_scale = 10

  _PIN_LATCH:Pin
  _PIN_BLANK:Pin
  _PIN_DATA:Pin
  _PIN_CLOCK:Pin

  def __init__(self, latch_pin:Pin, blank_pin:Pin, data_pin:Pin, clock_pin:Pin):
     self._PIN_LATCH = latch_pin
     self._PIN_BLANK = blank_pin
     self._PIN_DATA = data_pin
     self._PIN_CLOCK = clock_pin
     latch_pin.value(0)

  def _write_shift_register(self, line:list[int], line_marker:list[int],cutoff:int):
    for val in line:
      self._PIN_CLOCK.value(0)
      self._PIN_DATA.value(bool(val >= cutoff))
      self._PIN_CLOCK.value(1)
    for val in line_marker:
      self._PIN_CLOCK.value(0)
      self._PIN_DATA.value(val)
      self._PIN_CLOCK.value(1)
    
    self._PIN_LATCH.value(1)
    self._PIN_LATCH.value(0)

  def set_pixel(self,x,y,r,g,b):
    self._lines[x][3*y + 0] = r
    self._lines[x][3*y + 1] = g
    self._lines[x][3*y + 2] = b

  def set_pixel_lin(self,i,r,b,g):
    x,y = lin_to_pos(i)
    self.set_pixel(x,y,r,b,g)

  async def display_loop(self):
    while True:
      for cutoff in range(self._frame_scale):
        for i in range(4):
            self._write_shift_register(self._lines[i],self._line_markers[i],cutoff+1)
            # print(f"writing line:{line} with cutoff:{cutoff}")
            # Let another thread take a moment

      await asyncio.sleep(0)
      # print("display")

class AsyncKeys:
  _buttons:list[Pin]
  _button_state:list[bool]

  @staticmethod
  def _make_handler(i:int, custom_handler):
    def handler(t:Pin):
      if custom_handler:
        custom_handler(i,t)
    return handler

  def __init__(self, pin_numbers: list[int],optional_handler=None) -> None:
      self._buttons = []
      self._button_map = {}
      self._button_state = []
      for i in pin_numbers:
        pinName = f"GPIO{i}"
        pin = Pin(pinName,Pin.IN,Pin.PULL_UP)
        print(f"initializing \"{pinName}\"")
        index = len(self._buttons)
        pin.irq(self._make_handler(index,optional_handler))
        self._buttons.append(pin)

# LED_LAT = Pin("GPIO16",Pin.OUT)
# LED_BLANK = Pin("GPIO17",Pin.OUT)
# LED_BLANK.value(0)
# LED_SIN = Pin("GPIO18",Pin.OUT)
# LED_SCLK = Pin("GPIO19",Pin.OUT)

leds = LedMatrix(Pin("GPIO16",Pin.OUT) , Pin("GPIO17",Pin.OUT),Pin("GPIO18",Pin.OUT),Pin("GPIO19",Pin.OUT))

def key_handler(index:int,pin:Pin):
  button_on = not pin.value()
  r = int(random.random()*leds._frame_scale) if button_on else 0
  g = int(random.random()*leds._frame_scale) if button_on else 0
  b = int(random.random()*leds._frame_scale) if button_on else 0
  leds.set_pixel_lin(index,r,g,b)
  # print(f"set led:{index} to {{{r},{g},{b}}}")


keys = AsyncKeys([12,8,4,0,13,9,5,1,14,10,6,2,15,11,7,3], key_handler)

# SW = [
#   Pin("GPIO12",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO8",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO4",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO0",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO13",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO9",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO5",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO1",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO14",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO10",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO6",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO2",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO15",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO11",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO7",Pin.IN,Pin.PULL_UP),
#   Pin("GPIO3",Pin.IN,Pin.PULL_UP)
# ] 



# for i in range(16):
#   SW[i].irq(make_handler(i))

# def _set_leds(array_vals,scale = 1):
#   for val in array_vals:
#     LED_SCLK.value(0)
#     LED_SIN.value(val >= scale)
#     LED_SCLK.value(1)
#   LED_LAT.value(1)
#   LED_LAT.value(0)

async def main():
    asyncio.create_task(leds.display_loop())
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
        # for lin in range(16):
        #   set_pixel_lin((lin+0)%16,0,0,0)
        #   set_pixel_lin((lin+1)%16,1,0,0)
        #   set_pixel_lin((lin+2)%16,0,1,0)
        #   set_pixel_lin((lin+3)%16,1,1,0)
        #   set_pixel_lin((lin+4)%16,0,0,1)
        #   set_pixel_lin((lin+5)%16,1,0,1)
        #   set_pixel_lin((lin+6)%16,0,1,1)
        #   set_pixel_lin((lin+7)%16,1,1,1)
        #   await asyncio.sleep_ms(50)


    #   if not _buttons[0]:
    #     for lin in range(15):
    #       set_pixel_lin(lin,0,0,0)
    #       set_pixel_lin((lin+1)%16,1,0,0)
    #       set_pixel_lin((lin+2)%16,0,1,0)
    #       set_pixel_lin((lin+3)%16,1,1,0)
    #       set_pixel_lin((lin+4)%16,0,0,1)
    #       set_pixel_lin((lin+5)%16,1,0,1)
    #       set_pixel_lin((lin+6)%16,0,1,1)
    #       set_pixel_lin((lin+7)%16,1,1,1)
    #       await asyncio.sleep_ms(50)
    #   else:
          await asyncio.sleep_ms(50)


# def test_red_leds():
#   _set_leds([1,0,0,1,0,0,1,0,0,1,0,0,1,0,0,0])
#   time.sleep_ms(500)
#   _set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,1,0,0])
#   time.sleep_ms(500)
#   _set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,0,1,0])
#   time.sleep_ms(500)
#   _set_leds([1,0,0,1,0,0,1,0,0,1,0,0,0,0,0,1])
#   time.sleep_ms(500)

# def test_green_leds():
#   _set_leds([0,1,0,0,1,0,0,1,0,0,1,0,1,0,0,0])
#   time.sleep_ms(500)
#   _set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,1,0,0])
#   time.sleep_ms(500)
#   _set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,0,1,0])
#   time.sleep_ms(500)
#   _set_leds([0,1,0,0,1,0,0,1,0,0,1,0,0,0,0,1])
#   time.sleep_ms(500)

# def test_blue_leds():
#   _set_leds([0,0,1,0,0,1,0,0,1,0,0,1,1,0,0,0])
#   time.sleep_ms(500)
#   _set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,1,0,0])
#   time.sleep_ms(500)
#   _set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,0,1,0])
#   time.sleep_ms(500)
#   _set_leds([0,0,1,0,0,1,0,0,1,0,0,1,0,0,0,1])
#   time.sleep_ms(500)

asyncio.run(main())

# while True:
#   test_red_leds()
#   test_green_leds()
#   test_blue_leds()
