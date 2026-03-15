#!/usr/bin/env python3
import argparse
import json
import os
import time


STATE_FILE = "/tmp/frontpanel_state.json"
GPIO_SYSFS = "/sys/class/gpio"
SHIFT_CLOCK_GPIO = 539
DATA_OUT_GPIO = 540
RESET_BUTTON_GPIO = 620
PULSE_DELAY_S = 0

LED_ACTIVE_STATE = False  # active low LEDs
BUTTON_PRESSED_STATE = False  # active low button

# matches the order of the bits to shift out
LED_NAMES = ["mode", "status", "attention", "failover"]


class FrontPanel:
    """Driver for the T40 front panel."""

    @staticmethod
    def __write(path: str, value: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(value)

    @staticmethod
    def __export_gpio(pin: int) -> None:
        gpio_dir = os.path.join(GPIO_SYSFS, f"gpio{pin}")
        if not os.path.isdir(gpio_dir):
            FrontPanel.__write(os.path.join(GPIO_SYSFS, "export"), str(pin))

    @staticmethod
    def __set_direction(pin: int, direction: str = "out") -> None:
        FrontPanel.__write(
            os.path.join(GPIO_SYSFS, f"gpio{pin}", "direction"), direction
        )

    @staticmethod
    def __set_value(pin: int, value: int) -> None:
        FrontPanel.__write(os.path.join(GPIO_SYSFS, f"gpio{pin}", "value"), str(value))

    @staticmethod
    def __get_value(pin: int) -> int:
        with open(
            os.path.join(GPIO_SYSFS, f"gpio{pin}", "value"), "r", encoding="utf-8"
        ) as f:
            return int(f.read().strip())

    @staticmethod
    def write_leds(n: int) -> None:
        """Shift out the 4 least significant bits of the given integer to the LEDs."""

        FrontPanel.__export_gpio(SHIFT_CLOCK_GPIO)
        FrontPanel.__export_gpio(DATA_OUT_GPIO)
        FrontPanel.__set_direction(SHIFT_CLOCK_GPIO, "out")
        FrontPanel.__set_direction(DATA_OUT_GPIO, "out")

        for i in range(4):
            bit = (n >> i) & 1
            if not LED_ACTIVE_STATE:
                bit = 1 - bit

            FrontPanel.__set_value(DATA_OUT_GPIO, bit)
            FrontPanel.__set_value(SHIFT_CLOCK_GPIO, 0)
            if PULSE_DELAY_S:
                time.sleep(PULSE_DELAY_S)
            FrontPanel.__set_value(SHIFT_CLOCK_GPIO, 1)
            if PULSE_DELAY_S:
                time.sleep(PULSE_DELAY_S)

    @staticmethod
    def read_reset() -> bool:
        """Read the state of the reset button."""
        FrontPanel.__export_gpio(RESET_BUTTON_GPIO)
        FrontPanel.__set_direction(RESET_BUTTON_GPIO, "in")

        value = FrontPanel.__get_value(RESET_BUTTON_GPIO)
        return value == (1 if BUTTON_PRESSED_STATE else 0)


def write_led_state(n: int) -> None:
    """Write the given shift register state as the last state to the persistent state file."""
    # only 4 LSBs
    n &= 0xF
    state = {"state": n}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def read_led_state() -> int:
    """Read the last state from the persistent state file, or return 0 if the file doesn't exist."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
            return state.get("state", 0)
    except FileNotFoundError:
        return 0


def main() -> None:
    # parse command line
    parser = argparse.ArgumentParser(
        description="control the T40 front panel", prefix_chars="+-"
    )

    parser.add_argument(
        "-r",
        "--reset",
        dest="read_reset",
        action="store_const",
        const=True,
        default=False,
        help="Read the state of the reset button. Exit with code 1 if pressed, 0 if not",
    )

    parser.add_argument(
        "+all",
        dest="all",
        action="store_const",
        const=True,
        default=None,
        help="Turn on all LEDs",
    )
    parser.add_argument(
        "-all", dest="all", action="store_const", const=False, help="Turn off all LEDs"
    )
    for name in LED_NAMES:
        parser.add_argument(
            f"+{name}",
            f"+{name[0]}",
            dest=name,
            action="store_const",
            const=True,
            default=None,
            help=f"Turn on the {name} LED",
        )
        parser.add_argument(
            f"-{name}",
            f"-{name[0]}",
            dest=name,
            action="store_const",
            const=False,
            help=f"Turn off the {name} LED",
        )

    args = parser.parse_args()

    # default all to no change
    requested_led_state = [None] * len(LED_NAMES)

    # set all on / off if requested via +all / -all
    if args.all is not None:
        requested_led_state = [args.all] * len(LED_NAMES)

    # parse explicit LEDs
    for i, name in enumerate(LED_NAMES):
        if getattr(args, name) is not None:
            requested_led_state[i] = getattr(args, name)

    has_requested_leds = any(req is not None for req in requested_led_state)

    # nothing to do? show help
    if not has_requested_leds and not args.read_reset:
        parser.print_help()
        return 0

    # update LEDs if any changes requested
    if has_requested_leds:
        current_state = read_led_state()
        for i, req in enumerate(requested_led_state):
            if req is True:
                current_state |= 1 << i
            elif req is False:
                current_state &= ~(1 << i)

        FrontPanel.write_leds(current_state)
        write_led_state(current_state)

    # read reset button state if requested
    if args.read_reset:
        reset_down = FrontPanel.read_reset()
        print(1 if reset_down else 0)
        return 1 if reset_down else 0

    # otherwise, exit gracefully
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
