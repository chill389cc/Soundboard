import time
import array
import rp2

from machine import Pin


# ============================================================
# Configuration
# ============================================================

WIDTH = 4
HEIGHT = 4

PWM_BITS = 8

# PIO clock frequency
PIO_FREQ = 8_000_000

# Duration of the smallest PWM bit plane
PWM_BASE_US = 10

# Animation speed
ANIMATION_SPEED = 25

# GPIO assignments
PIN_LAT = 16
PIN_BLANK = 17
PIN_CLK = 18
PIN_DATA = 19


# ============================================================
# PIO program
# ============================================================

# Three side-set pins:
#
# GPIO16 = LAT
# GPIO17 = BLANK
# GPIO18 = SCLK
#
# Side-set values:
#
# 0b000 = LAT=0, BLANK=0, CLK=0
# 0b010 = LAT=0, BLANK=1, CLK=0
# 0b011 = LAT=1, BLANK=1, CLK=0
# 0b110 = LAT=0, BLANK=1, CLK=1
#
# GPIO19 = SIN, controlled by OUT instruction.


@rp2.asm_pio(
    out_init=rp2.PIO.OUT_LOW,
    sideset_init=(
        rp2.PIO.OUT_LOW,   # LAT
        rp2.PIO.OUT_HIGH,  # BLANK
        rp2.PIO.OUT_LOW,   # CLK
    ),
    out_shiftdir=rp2.PIO.SHIFT_LEFT,
    autopull=False,
)
def led_driver():

    wrap_target()

    # ----------------------------------------
    # Receive 16-bit output pattern
    # ----------------------------------------

    pull(block).side(0b010)

    # 16 bits to transmit
    set(y, 15).side(0b010)

    label("shift")

    # Set SIN while CLK is LOW
    out(pins, 1).side(0b010)

    # Clock HIGH: TLC5928 samples SIN
    nop().side(0b110)

    # Clock LOW
    jmp(y_dec, "shift").side(0b010)

    # ----------------------------------------
    # Latch the 16 transmitted bits
    # ----------------------------------------

    # LAT HIGH, outputs still blanked
    nop().side(0b011)

    # LAT LOW, wait for dwell value
    pull(block).side(0b010)

    # ----------------------------------------
    # PWM dwell
    # ----------------------------------------

    # Load duration and enable outputs
    mov(x, osr).side(0b000)

    label("dwell")

    # Hold outputs enabled for X cycles
    jmp(x_dec, "dwell").side(0b000)

    # Disable outputs before next transfer
    nop().side(0b010)

    wrap()


# ============================================================
# LED Matrix Class
# ============================================================

class LedMatrix:

    def __init__(self):

        print("Initializing PIO LED matrix")

        # Explicitly reset pins to GPIO mode.
        # This preserves the startup behavior
        # that fixed our earlier SPI test.

        Pin(PIN_LAT, Pin.OUT, value=0)
        Pin(PIN_BLANK, Pin.OUT, value=1)
        Pin(PIN_CLK, Pin.OUT, value=0)
        Pin(PIN_DATA, Pin.OUT, value=0)

        Pin(26, Pin.IN)

        time.sleep_ms(50)

        # ------------------------------------
        # Framebuffer
        # ------------------------------------

        # frame[x][y] = (r, g, b)

        self.frame = [
            [(0, 0, 0) for _ in range(HEIGHT)]
            for _ in range(WIDTH)
        ]

        # ------------------------------------
        # PIO state machine
        # ------------------------------------

        self.sm = rp2.StateMachine(
            0,
            led_driver,
            freq=PIO_FREQ,
            sideset_base=Pin(PIN_LAT),
            out_base=Pin(PIN_DATA),
        )

        # ------------------------------------
        # DMA
        # ------------------------------------

        self.dma = rp2.DMA()

        # 4 columns * 8 PWM planes * 2 words
        self.words_per_frame = WIDTH * PWM_BITS * 2

        self.dma_buffer = array.array(
            "I",
            [0] * self.words_per_frame
        )

        # RP2350 PIO0 TX0 DREQ = 0
        self.dma_ctrl = self.dma.pack_ctrl(
            size=2,            # 32-bit words
            inc_read=True,
            inc_write=False,
            treq_sel=0,        # PIO0 TX0
            bswap=False,
        )

        # Clock cycles per microsecond
        self.cycles_per_us = PIO_FREQ // 1_000_000

        self.running = False

        print("PIO initialized")
        print("DMA channel:", self.dma.channel)

    # ========================================================
    # Framebuffer operations
    # ========================================================

    def set_pixel(
        self,
        x: int,
        y: int,
        r: int,
        g: int,
        b: int,
    ) -> None:

        self.frame[x][y] = (
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
        )

    def fill(
        self,
        r: int,
        g: int,
        b: int,
    ) -> None:

        for x in range(WIDTH):
            for y in range(HEIGHT):
                self.set_pixel(x, y, r, g, b)

    def clear(self) -> None:
        self.fill(0, 0, 0)

    # ========================================================
    # TLC5928 output encoding
    # ========================================================

    def build_column(
        self,
        col: int,
        bit: int,
    ) -> int:

        # OUT0-3: Column transistor controls
        value = 1 << col

        # OUT4-15: Four RGB rows
        for row in range(HEIGHT):

            r, g, b = self.frame[col][row]

            base = 4 + row * 3
            mask = 1 << bit

            if r & mask:
                value |= 1 << base

            if g & mask:
                value |= 1 << (base + 1)

            if b & mask:
                value |= 1 << (base + 2)

        return value

    # ========================================================
    # PWM frame encoding
    # ========================================================

    def build_dma_frame(self) -> None:
        """
        Convert the 4x4 RGB framebuffer into
        32 PIO display operations.

        Each operation has:
          Word 0: TLC5928 output pattern
          Word 1: PWM dwell cycles
        """

        index = 0

        for bit in range(PWM_BITS):

            # Binary-weighted PWM duration
            duration_us = PWM_BASE_US * (1 << bit)

            cycles = duration_us * self.cycles_per_us

            for col in range(WIDTH):

                pattern = self.build_column(col, bit)

                # The PIO shifts MSB first.
                # Place 16-bit data in upper half
                # of 32-bit OSR.

                self.dma_buffer[index] = pattern << 16
                index += 1

                # Dwell duration
                self.dma_buffer[index] = cycles
                index += 1

    # ========================================================
    # DMA transfer
    # ========================================================

    def transfer_frame(self) -> None:
        """
        Send one complete PWM frame to PIO
        through DMA.
        """

        self.dma.config(
            read=self.dma_buffer,
            write=self.sm,
            count=self.words_per_frame,
            ctrl=self.dma_ctrl,
            trigger=True,
        )

        # Wait for DMA to finish reading the buffer.
        #
        # PIO continues independently and may still
        # be processing the final words.

        while self.dma.active():
            pass

    # ========================================================
    # Driver control
    # ========================================================

    def start(self) -> None:

        self.build_dma_frame()

        self.sm.active(1)
        self.running = True

    def stop(self) -> None:

        self.running = False

        self.dma.active(0)
        self.sm.active(0)

        self.dma.close()

        # Reclaim BLANK from PIO and disable outputs
        Pin(PIN_BLANK, Pin.OUT, value=1)

        print("LED driver stopped")


# ============================================================
# Color generation
# ============================================================

def hsv_to_rgb(
    hue: int,
    saturation: int,
    value: int,
) -> tuple[int, int, int]:
    """
    Integer HSV to RGB conversion.

    hue:        0-767
    saturation: 0-255
    value:      0-255
    """

    hue %= 768

    # Divide hue wheel into 3 sectors
    sector = hue // 256
    position = hue % 256

    if sector == 0:
        r = 255 - position
        g = position
        b = 0

    elif sector == 1:
        r = 0
        g = 255 - position
        b = position

    else:
        r = position
        g = 0
        b = 255 - position

    # Apply saturation
    r = 255 - ((255 - r) * saturation // 255)
    g = 255 - ((255 - g) * saturation // 255)
    b = 255 - ((255 - b) * saturation // 255)

    # Apply brightness
    r = r * value // 255
    g = g * value // 255
    b = b * value // 255

    return r, g, b


# ============================================================
# Animated gradient
# ============================================================

def update_gradient(
    matrix: LedMatrix,
    offset: int,
) -> None:
    """
    Generate a color gradient across the matrix.

    Hue changes across X and Y.

    Brightness increases from 0 to 255
    across the 16 LEDs.
    """

    for x in range(WIDTH):
        for y in range(HEIGHT):

            # Hue gradient
            hue = (
                offset
                + x * 64
                + y * 32
            ) % 768

            # Brightness gradient 0-255
            brightness = (x + y * WIDTH) * 17

            r, g, b = hsv_to_rgb(
                hue,
                255,
                brightness,
            )

            matrix.set_pixel(
                x, y,
                r, g, b,
            )


# ============================================================
# Main
# ============================================================

def main() -> None:

    matrix = LedMatrix()

    matrix.start()

    print("Starting RGB gradient animation")

    try:

        while True:

            # Animate hue over time
            offset = (
                time.ticks_ms() * ANIMATION_SPEED // 100
            ) % 768

            update_gradient(matrix, offset)

            # Convert frame to PWM bit planes
            matrix.build_dma_frame()

            # Transfer frame using DMA
            matrix.transfer_frame()

    except KeyboardInterrupt:

        print("Stopping animation")

    finally:

        matrix.stop()


main()