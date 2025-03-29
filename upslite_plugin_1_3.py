# Based on UPS Lite v1.1 from https://github.com/xenDE
# Made specifically to address the problems caused by the hardware changes in 1.3.  Oh yeah I also removed the auto-shutdown feature because it's kind of broken.
#
# To setup, see page six of this manual to see how to enable i2c:
# https://github.com/linshuqin329/UPS-Lite/blob/master/UPS-Lite_V1.3_CW2015/Instructions%20for%20UPS-Lite%20V1.3.pdf
#
# Follow page seven, install the dependencies (python-smbus) and copy this script over for later use:
# https://github.com/linshuqin329/UPS-Lite/blob/master/UPS-Lite_V1.3_CW2015/UPS_Lite_V1.3_CW2015.py
#
# Now, install this plugin by copying this to the 'available-plugins' folder in your pwnagotchi, install and enable the plugin with the commands:
# sudo pwnagotchi plugins install upslite_plugin_1_3
# sudo pwnagotchi plugins enable upslite_plugin_1_3
#
# Now restart raspberry pi. Once back up ensure upslite_plugin_1_3 plugin is turned on in the WebUI. If there is still '0%' on your battery meter
# run the script we saved earlier and ensure that the pwnagotchi is plugged in both at the battery and the raspberry pi. The script should start trying to
# read the battery, and should be successful once there's a USB cable running power to the battery supply.


import logging
import struct
import RPi.GPIO as GPIO
import sys
import time  # Added for potential delay after QuickStart

sys.path.append('/usr/local/share/pwnagotchi')
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# only import when the module is loaded and enabled
# Moved here so it doesn't fail plugin loading if smbus is missing
try:
    import smbus
except ImportError:
    logging.error("UPSLite plugin requires smbus. Run 'sudo apt install python3-smbus'")
    smbus = None # Ensure smbus is defined even if import fails

CW2015_ADDRESS   = 0X62
CW2015_REG_VCELL = 0X02
CW2015_REG_SOC   = 0X04
CW2015_REG_MODE  = 0X0A
CW2015_QUICKSTART_VAL = 0x30 # Value to write to MODE reg for QuickStart
GPIO_PIN_CHARGING = 4        # GPIO4 for charging status

# Set up logging
log = logging.getLogger('pwnagotchi_plugins')


class UPS:
    def __init__(self):
        if smbus is None:
             raise ImportError("smbus library not found for UPS class")
        # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
        self._bus = smbus.SMBus(1)
        self._quick_start() # Initialize the chip

        # Setup GPIO - do it once here
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(GPIO_PIN_CHARGING, GPIO.IN)
            log.debug("UPSLite: GPIO %d setup OK.", GPIO_PIN_CHARGING)
        except Exception as e:
            log.error("UPSLite: Error setting up GPIO %d: %s", GPIO_PIN_CHARGING, e)
            # Decide how to handle - maybe disable charging status? For now, just log.

    def _quick_start(self):
        """Wakes up the CW2015 and triggers calculations."""
        try:
            # Use write_byte_data for single byte register, or write_word_data if required by specific smbus implementation/chip behavior
            # The manufacturer script used write_word_data, let's stick to that for consistency maybe?
            # bus.write_word_data(CW2015_ADDRESS, CW2015_REG_MODE, CW2015_QUICKSTART_VAL)
            # Let's try write_byte_data first as MODE is a single register 0x0A
            self._bus.write_byte_data(CW2015_ADDRESS, CW2015_REG_MODE, CW2015_QUICKSTART_VAL)
            log.info("UPSLite: CW2015 QuickStart command sent (wrote 0x%02X to 0x%02X)", CW2015_QUICKSTART_VAL, CW2015_REG_MODE)
            time.sleep(0.1) # Give chip a moment
        except IOError as e:
            log.error("UPSLite: Error sending QuickStart command: %s", e)
        except Exception as e:
            log.error("UPSLite: Unexpected error during QuickStart: %s", e)


    def voltage(self):
        """Reads voltage. Returns voltage in V or 0.0 on error."""
        try:
            read = self._bus.read_word_data(CW2015_ADDRESS, CW2015_REG_VCELL)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            # Correct scale factor: 0.305 mV per LSB = 0.000305 V per LSB
            voltage = swapped * 0.305 / 1000
            return voltage
        except IOError as e:
            log.debug("UPSLite: I2C Error reading voltage: %s", e) # Use debug for potentially frequent errors
            return 0.0
        except Exception as e:
            log.error("UPSLite: Unexpected error reading voltage: %s", e)
            return 0.0

    def capacity(self):
        """Reads capacity percentage. Returns % (0-100) or 0.0 on error."""
        try:
            # Removed unused 'address = 0x36'
            read = self._bus.read_word_data(CW2015_ADDRESS, CW2015_REG_SOC)
            swapped = struct.unpack("<H", struct.pack(">H", read))[0]
            capacity = swapped / 256.0 # Use 256.0 for explicit float division
            # Clamp value between 0 and 100 in case of weird readings
            return max(0.0, min(100.0, capacity))
        except IOError as e:
            log.debug("UPSLite: I2C Error reading capacity: %s", e) # Use debug for potentially frequent errors
            return 0.0
        except Exception as e:
            log.error("UPSLite: Unexpected error reading capacity: %s", e)
            return 0.0

    def charging(self):
        """Checks charging status via GPIO. Returns '+' (charging), '-' (discharging), or '?' (error)."""
        try:
            # GPIO setup is now done in __init__
            return '+' if GPIO.input(GPIO_PIN_CHARGING) == GPIO.HIGH else '-'
        except Exception as e:
            # Log error if GPIO read fails after setup
            log.error("UPSLite: Error reading GPIO %d: %s", GPIO_PIN_CHARGING, e)
            return '?' # Return '?' or some other indicator of error


class UPSLite(plugins.Plugin):
  __GitHub__ = ""
    __author__ = 'pwnagotchi contributor, based on evilsocket@gmail.com'
    __author__ = "(edited by: Juan Milano juan_milano@hotmail.com"
    __version__ = '1.0.2' # Incremented version
    __version__ = "1.0.0"
    __license__ = 'GPL3'
    __license__ = "GPL3"
    __description__ = 'A plugin that displays battery capacity and charging status for the UPS Lite v1.3 using CW20150 .'
    __description__ = "A plugin that will add a voltage indicator for the UPS Lite v1.3"
    __name__ = "UPSLite"
    __help__ = "A plugin that will add a voltage indicator for the UPS Lite v1.3 designed by xiaoj"
    __dependencies__ = {
        "pip": ["scapy"],
    }
    __defaults__ = {
        "enabled": False,
    }





    def __init__(self):
        self.ups = None
        log.debug("UPSLite plugin __init__") # Use Pwnagotchi logger

    def on_loaded(self):
        log.info("UPSLite plugin loaded")
        try:
            self.ups = UPS()
            log.info("UPSLite: UPS object initialized successfully.")
        except Exception as e:
            log.error("UPSLite: Failed to initialize UPS object: %s", e)
            self.ups = None # Ensure ups is None if init fails

    def on_ui_setup(self, ui):
        try:
            log.debug("UPSLite: Setting up UI element 'ups'")
            ui.add_element('ups', LabeledValue(color=BLACK, label='UPS', value='--', position=(ui.width() // 2 + 15, 0),
                                               label_font=fonts.Bold, text_font=fonts.Medium))
        except Exception as e:
            log.error("UPSLite: Error setting up UI: %s", e)

    def on_unload(self, ui):
        try:
            log.info("UPSLite plugin unloaded")
            with ui._lock:
                ui.remove_element('ups')
            # Cleanup GPIO here if it was setup in on_loaded,
            # but since it's in UPS.__init__, rely on script exit or UPS object deletion for cleanup?
            # Proper GPIO cleanup in plugins can be tricky. For simplicity, often omitted.
            # If desired: GPIO.cleanup()
        except Exception as e:
            log.error("UPSLite: Error during unload: %s", e)


    def on_ui_update(self, ui):
        if self.ups: # Check if UPS object was initialized successfully
            try:
                capacity = self.ups.capacity()
                charging = self.ups.charging()
                # Format to integer percentage
                ui.set('ups', "%2i%%%s" % (int(round(capacity)), charging))
            except Exception as e:
                log.error("UPSLite: Error during UI update: %s", e)
                # Optionally set UI to an error state
                # ui.set('ups', "ERR")
        else:
            # If UPS object failed to init, display error or default
             ui.set('ups', "--")
