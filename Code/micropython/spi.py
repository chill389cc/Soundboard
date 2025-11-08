import time
import random
from machine import SPI, Pin
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
  _frame_scale = 3
  _PIN_LATCH:Pin
  _PIN_BLANK:Pin
  _PIN_DATA:Pin
  _PIN_CLOCK:Pin
  _SPI:SPI

  def __init__(self, latch_pin:Pin, blank_pin:Pin, data_pin:Pin, clock_pin:Pin):
    #  print("Initializing LedMatrix with SPI...")
     self._PIN_LATCH = latch_pin
     self._PIN_BLANK = blank_pin
     self._PIN_DATA = data_pin
     self._PIN_CLOCK = clock_pin
     self._SPI = SPI(0, baudrate=80000, polarity=0, phase=0,bits=8, miso=Pin("GPIO4"), mosi=data_pin, sck=clock_pin)
    #  print(f"SPI initialized with baudrate 40kHz")
     latch_pin.value(0)
    #  print("LedMatrix initialization complete")

  def _write_shift_register(self, line:list[int], line_marker:list[int],cutoff:int):
    data = [0,0]
    i = 0
    for val in line:
        index = i // 8
        val = 1 if val >= cutoff else 0
        data[index] = data[index] | (val << (7 - (i % 8)))
        # print(f"line_marker val:{val} at index:{index} shifted to:{7 - (i % 8)}")
        i += 1
    for val in line_marker:
        index = i // 8
        data[index] = data[index] | (val << (7 - (i % 8)))
        # print(f"line_marker val:{val} at index:{index} shifted to:{7 - (i % 8)}")
        i += 1
    # print(f"built data: {[hex(b) for b in data]} length: {i}")
    # Debug: Print SPI data being written
    # if cutoff == 1:  # Only print for first cutoff to reduce spam
        # print(f"SPI write: {[hex(b) for b in data]} (line_marker: {line_marker})")
    # print(f"SPI write: {[hex(b) for b in data]} (line_marker: {line_marker})")
    self._SPI.write(bytes(data))
    self._PIN_LATCH.value(1)
    self._PIN_LATCH.value(0)

  def set_pixel(self,x,y,r,g,b):
    # print(f"Setting pixel ({x},{y}) to RGB({r},{g},{b})")
    self._lines[x][3*y + 0] = r
    self._lines[x][3*y + 1] = g
    self._lines[x][3*y + 2] = b

  def set_pixel_lin(self,i,r,b,g):
    x,y = lin_to_pos(i)
    self.set_pixel(x,y,r,b,g)

  async def display_loop(self):
    # print("Starting LED display loop...")
    loop_count = 0
    while True:
      for cutoff in range(self._frame_scale):
        for i in range(4):
            self._write_shift_register(self._lines[i],self._line_markers[i],cutoff+1)
            # print(f"writing line:{line} with cutoff:{cutoff}")
            # Let another thread take a moment

      await asyncio.sleep(0)
      loop_count += 1
      if loop_count % 1000 == 0:  # Print every 1000 loops to show it's running
          print(f"Display loop running... (iteration {loop_count})")
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
      print(f"Initializing AsyncKeys with pins: {pin_numbers}")
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
      print(f"AsyncKeys initialization complete - {len(self._buttons)} buttons configured")

Pin("GPIO26",Pin.IN)
Pin("GPIO16",Pin.IN)
leds = LedMatrix(Pin("GPIO16",Pin.OUT) , Pin("GPIO17",Pin.OUT),Pin("GPIO19",Pin.OUT),Pin("GPIO18",Pin.OUT))

def key_handler(index:int,pin:Pin):
  button_on = not pin.value()
  r = int(random.random()*leds._frame_scale) if button_on else 0
  g = int(random.random()*leds._frame_scale) if button_on else 0
  b = int(random.random()*leds._frame_scale) if button_on else 0
  leds.set_pixel_lin(index,r,g,b)
  # print(f"set led:{index} to {{{r},{g},{b}}}")


keys = AsyncKeys([12,8,4,0,13,9,5,1,14,10,6,2,15,11,7,3], key_handler)

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

asyncio.run(main())