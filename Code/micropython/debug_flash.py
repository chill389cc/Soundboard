import time
from machine import Pin, SPI, mem32
from rp2 import DMA


# ============================================================
# RP2350 SPI registers
# ============================================================

SPI0_BASE = 0x40080000

SPI0_DR = SPI0_BASE + 0x008
SPI0_SR = SPI0_BASE + 0x00C
SPI0_DMACR = SPI0_BASE + 0x024

# SPI status bits
SPI_TFE = 1 << 0    # TX FIFO empty
SPI_RNE = 1 << 2    # RX FIFO not empty
SPI_BSY = 1 << 4    # SPI busy

# RP2350 DMA request for SPI0 TX
DREQ_SPI0_TX = 24


# ============================================================
# Pico hardware initialization
# ============================================================

def init_hardware():
    print("Initializing Pico GPIO, SPI and DMA")

    # Reset SPI pins to GPIO mode first
    Pin(18, Pin.OUT, value=0)
    Pin(19, Pin.OUT, value=0)

    lat = Pin(16, Pin.OUT, value=0)
    blank = Pin(17, Pin.OUT, value=1)

    # Preserve working initialization
    Pin(26, Pin.IN)

    time.sleep_ms(50)

    # Configure hardware SPI
    spi = SPI(
        0,
        baudrate=35_000_000,
        polarity=0,
        phase=0,
        bits=8,
        sck=Pin(18),
        mosi=Pin(19),
        miso=Pin(4),
    )

    print("SPI:", spi)

    # Enable SPI0 TX DMA requests
    mem32[SPI0_DMACR] |= 1 << 1

    # Allocate DMA channel
    dma = DMA()

    # Configure 8-bit transfers
    ctrl = dma.pack_ctrl(
        size=0,
        inc_read=True,
        inc_write=False,
        treq_sel=DREQ_SPI0_TX,
    )

    print("DMA channel:", dma.channel)

    return spi, dma, ctrl, lat, blank


SPI_BUS, DMA_BUS, DMA_CTRL, LAT, BLANK = init_hardware()

# Persistent DMA source buffer
TX_BUFFER = bytearray(2)


# ============================================================
# TLC5928 communication via DMA
# ============================================================

def write_register(value: int) -> None:
    """
    Transfer 16 bits using DMA -> SPI0.

    Wait until SPI finishes before latching.
    """

    TX_BUFFER[0] = (value >> 8) & 0xFF
    TX_BUFFER[1] = value & 0xFF

    LAT.value(0)

    # Start DMA transfer
    DMA_BUS.config(
        read=TX_BUFFER,
        write=SPI0_DR,
        count=2,
        ctrl=DMA_CTRL,
        trigger=True,
    )

    # Wait for DMA to finish feeding the SPI FIFO
    while DMA_BUS.active():
        pass

    # Wait until SPI has actually transmitted everything
    while (
        not (mem32[SPI0_SR] & SPI_TFE)
        or (mem32[SPI0_SR] & SPI_BSY)
    ):
        pass

    # Drain received data (SPI is full duplex)
    while mem32[SPI0_SR] & SPI_RNE:
        _ = mem32[SPI0_DR]

    # Latch transmitted data
    LAT.value(1)
    time.sleep_us(1)
    LAT.value(0)


def initialize_driver():
    BLANK.value(1)

    write_register(0x0000)

    BLANK.value(0)


# ============================================================
# Matrix control
# ============================================================

def set_pixel(col: int, row: int, color: int):
    """
    col: 0-3
    row: 0-3
    color: 0=R, 1=G, 2=B
    """

    value = 1 << col
    value |= 1 << (4 + row * 3 + color)

    write_register(value)


def set_column(col: int, r: int, g: int, b: int):
    """Illuminate all four LEDs in one column."""

    value = 1 << col

    for row in range(4):
        base = 4 + row * 3

        if r:
            value |= 1 << base
        if g:
            value |= 1 << (base + 1)
        if b:
            value |= 1 << (base + 2)

    write_register(value)


# ============================================================
# Test
# ============================================================

initialize_driver()

COLORS = [
    ("Red",     (1, 0, 0)),
    ("Green",   (0, 1, 0)),
    ("Blue",    (0, 0, 1)),
    ("Yellow",  (1, 1, 0)),
    ("Cyan",    (0, 1, 1)),
    ("Magenta", (1, 0, 1)),
    ("White",   (1, 1, 1)),
]

try:
    while True:

        print("=== Testing individual pixels ===")

        for col in range(4):
            for row in range(4):
                for color in range(3):

                    print(
                        "Col:", col,
                        "Row:", row,
                        "Color:", color
                    )

                    set_pixel(col, row, color)
                    time.sleep_ms(30)

        print("=== Testing columns ===")

        for col in range(4):
            for name, rgb in COLORS:

                print("Col:", col, "Color:", name)

                set_column(col, *rgb)
                time.sleep_ms(200)

except KeyboardInterrupt:
    print("Stopping")

finally:
    BLANK.value(1)

    # Stop the DMA channel before releasing it
    DMA_BUS.active(0)
    DMA_BUS.close()

    # Disable SPI DMA requests
    mem32[SPI0_DMACR] &= ~(1 << 1)

    SPI_BUS.deinit()

    print("Stopped")