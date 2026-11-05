import asyncio
from machine import Pin, SPI


class LedMatrix:
    WIDTH = 4
    HEIGHT = 4

    # TLC5928 output mapping:
    # OUT0-3   = Column transistor controls
    # OUT4-15  = RGB sinks (3 channels per row)

    def __init__(
        self,
        latch_pin: int = 16,
        blank_pin: int = 17,
        clock_pin: int = 18,
        data_pin: int = 19,
        baudrate: int = 10_000_000,
    ):
        # Initialize GPIO pins before enabling SPI
        Pin(clock_pin, Pin.OUT, value=0)
        Pin(data_pin, Pin.OUT, value=0)

        self._lat = Pin(latch_pin, Pin.OUT, value=0)
        self._blank = Pin(blank_pin, Pin.OUT, value=1)

        # Preserve configuration from working test
        Pin(26, Pin.IN)

        self._spi = SPI(
            0,
            baudrate=baudrate,
            polarity=0,
            phase=0,
            bits=8,
            sck=Pin(clock_pin),
            mosi=Pin(data_pin),
            miso=Pin(4),
        )

        # Framebuffer: frame[x][y] = (r, g, b)
        self._frame = [
            [(0, 0, 0) for _ in range(self.HEIGHT)]
            for _ in range(self.WIDTH)
        ]

        # Preallocated SPI buffer
        self._buffer = bytearray(2)

        # Initialize driver
        self._write_register(0)
        self._blank.value(0)

    def _write_register(self, value: int) -> None:
        """Write a 16-bit value to the TLC5928."""

        self._buffer[0] = (value >> 8) & 0xFF
        self._buffer[1] = value & 0xFF

        self._lat.value(0)
        self._spi.write(self._buffer)
        self._lat.value(1)
        self._lat.value(0)

    def set_pixel(
        self,
        x: int,
        y: int,
        r: int,
        g: int,
        b: int,
    ) -> None:
        """Set a pixel's RGB brightness (0-255)."""

        if not (0 <= x < self.WIDTH):
            raise ValueError("Invalid x coordinate")

        if not (0 <= y < self.HEIGHT):
            raise ValueError("Invalid y coordinate")

        self._frame[x][y] = (
            max(0, min(255, r)),
            max(0, min(255, g)),
            max(0, min(255, b)),
        )

    def get_pixel(self, x: int, y: int) -> tuple[int, int, int]:
        """Return the RGB value of a pixel."""
        return self._frame[x][y]

    def set_frame(self, frame: list) -> None:
        """
        Replace the entire framebuffer.

        Format:
        frame[x][y] = (r, g, b)
        """

        if len(frame) != self.WIDTH:
            raise ValueError("Frame must contain 4 columns")

        for x in range(self.WIDTH):
            if len(frame[x]) != self.HEIGHT:
                raise ValueError("Each column must contain 4 pixels")

            for y in range(self.HEIGHT):
                self.set_pixel(x, y, *frame[x][y])

    def fill(self, r: int, g: int, b: int) -> None:
        """Fill the entire matrix with one color."""

        for x in range(self.WIDTH):
            for y in range(self.HEIGHT):
                self.set_pixel(x, y, r, g, b)

    def clear(self) -> None:
        """Clear the framebuffer."""
        self.fill(0, 0, 0)

    def _build_column(
        self,
        x: int,
        bit: int,
    ) -> int:
        """
        Build a 16-bit output register for one column
        and one PWM bit plane.
        """

        # Enable column transistor
        value = 1 << x

        for y in range(self.HEIGHT):
            r, g, b = self._frame[x][y]

            base = 4 + y * 3

            if r & (1 << bit):
                value |= 1 << base

            if g & (1 << bit):
                value |= 1 << (base + 1)

            if b & (1 << bit):
                value |= 1 << (base + 2)

        return value

    async def refresh(self) -> None:
        """
        Display one complete RGB PWM frame.

        Uses 8-bit bit-plane PWM.
        """

        for bit in range(8):
            for x in range(self.WIDTH):
                value = self._build_column(x, bit)

                # Disable outputs during column switching
                self._blank.value(1)

                self._write_register(value)

                # Enable outputs
                self._blank.value(0)

                # Weighted PWM duration
                await asyncio.sleep_us(1 << bit)

    async def display_loop(self) -> None:
        """Continuously refresh the LED matrix."""

        while True:
            await self.refresh()

    def stop(self) -> None:
        """Disable outputs and release SPI."""

        self._blank.value(1)
        self._spi.deinit()