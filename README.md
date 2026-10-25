# ESPHome Swing Fans Component

[![GitHub issues](https://img.shields.io/github/issues/robertos/esphome-swing-fans)](https://github.com/robertos/esphome-swing-fans/issues)
[![GitHub license](https://img.shields.io/github/license/robertos/esphome-swing-fans)](https://github.com/robertos/esphome-swing-fans/blob/main/LICENSE)

This is an ESPHome custom component to control multiple [Swing Fans DC ceiling fans](https://swingfans.com/collections/dc-ceiling-fan) that use [remotes that look like this](https://www.youtube.com/watch?v=WMw-yNIsO1c). The protocol uses a 12-bit or 24-bit command code, with specific pulse timings for sync, 0, and 1 bits.

> **NOTE:** This is shared with no guarantees that this will work or that it won't damage your fans. Use it at your own risk. This project has no relationship with the Swing Fans manufacturer.

This component requires you to configure separate [`remote_transmitter`](https://esphome.io/components/remote_transmitter.html) and [`remote_receiver`](https://esphome.io/components/remote_receiver.html) components, allowing flexibility in your choice of RF hardware (e.g., simple GPIO pins, CC1101 modules via their own transmitter/receiver platforms, etc.).

**Features:**

* Control multiple fans from a single ESP device.
* Supports the specific 5-bit ID + 7/19-bit command protocol and a 24-bit no-DIP variant.
* Provides an optional light entity with six brightness levels for the no-DIP variant.
* Integrates with standard ESPHome `remote_transmitter` and `remote_receiver`.
* Provides standard `fan` entities for Home Assistant (supporting On/Off and 6 speeds).
* Provides optional `button` entities to send the 'flip' (direction change) command.
* Allows hooks (`on_transmit_begin`/`on_transmit_end`) for transmitters requiring special handling (like CC1101 mode switching).
* Updates fan state in Home Assistant if commands are received via RF (e.g., from the original remote).

## Dependencies

* ESPHome.
* [`remote_transmitter`](https://esphome.io/components/remote_transmitter.html) component configured in your YAML.
* [`remote_receiver`](https://esphome.io/components/remote_receiver.html) component configured in your YAML (specifically listening for `rc_switch` data).
* `fan` and `button` components defined in your YAML so `swing_fans` can add more fans and buttons. 

## Hardware

- ESP32 board
- Some RF transmitter - I used a CC1101 module

For an example of building the hardware, see the [instructions in the ESPSomfy-RTS wiki](https://github.com/rstrouse/ESPSomfy-RTS/wiki/Simple-ESPSomfy-RTS-device).

## Installation

You can install this component using the `external_components` feature of ESPHome. Add the following to your device's YAML configuration:

```yaml
external_components:
  - source: github://robertos/esphome-swing-fans@main # Or specify a release tag
    components: [ swing_fans ] # Specify the component name
```

## Configuration

```yaml
# 1. Configure your chosen transmitter and receiver FIRST
remote_transmitter:
  id: gpio_tx # Example ID
  pin: GPIO32 # Example pin
  carrier_duty_percent: 100%
  non_blocking: true

# The receiver is only required if you want to listen for other remotes
remote_receiver:
  id: gpio_rx # Example ID
  pin: GPIO33 # Example pin
  tolerance: 60%
  filter: 4us
  idle: 4ms
  dump: rc_switch # Recommended for debugging
  on_rc_switch:
    then:
      - swing_fans.received_code:
          hub_id: fan_controller
          code: !lambda return x.code;
          protocol: !lambda return x.protocol;

# 2. Configure the main swing_fans controller
swing_fans:
  id: fan_controller # An ID for this controller instance
  remote_transmitter_id: gpio_tx # Link to your transmitter ID

  # Optional hooks for complex transmitters
  # on_transmit_begin:
  #   - ...
  # on_transmit_end:
  #   - ...

  # List ALL fans controlled by this component
  fans:
    - name: "Office Fan" # Must be unique and match fan/button entities below
      fan_id: "01000"    # The 5-bit binary ID for this fan
      is_24_bit: false   # Optional, set to true if this fan uses the longer command format
    - name: "Living Room Fan"
      fan_id: "00100"
      is_24_bit: false
    - name: "Second Room Fan"
      fan_id: "11101"
      is_24_bit: true
    # ... add all other fans here

# 3. Create empty fan and button lists to be filled by swing_fans
fan: []
button: []
```

### Configuration Variables

**`swing_fans` (Hub):**

* **id** (Optional, ID): Manually specify the ID used for linking.
* **remote_transmitter_id** (Required, ID): The ID of the `remote_transmitter` component to use for sending commands.
* **fans** (Required, list): A list defining each fan.
    * **name** (Required, string): The unique name for this fan. This name is used to link the `fan.swing_fans` and `button.swing_fans_direction` entities back to this configuration.
    * **fan_id** (Required for the original protocol, string): The 5-character binary string representing the fan's unique ID (e.g., `"01000"`).
    * **is_24_bit** (Optional, boolean): Set to `true` if this specific fan uses the longer 19-bit command format (total 24 bits including ID). Defaults to `false` (7-bit command format, total 12 bits).
    * **is_24_bit_nodip** (Optional, boolean): Use the no-DIP variant described below. Defaults to `false`.
    * **packet_prefix** (Required for the no-DIP variant, string): The first 16 bits of a received 24-bit packet, including leading zeros.
    * **light** (Optional): A light entity for the no-DIP variant. Supports standard ESPHome brightness light options; defaults to gamma `1.0` and no transition.
    * **direction_button_icon** (Optional, Icon): The icon to be used for the direction button entity, defaults to `"mdi:swap-horizontal`.
    * **direction_button_name** (Optional, string): The name of the entity for the direction button, defaults to `<Fan Name> Direction`.
    * **restore_mode** (Optional): Control how the fan attempts to restore state on boot. See the [ESPHome docs for Fan](https://esphome.io/components/fan/index.html), defaults to `RESTORE_DEFAULT_OFF` so the previous state is restored after a reboot when available.
* **on_transmit_begin** (Optional, Action): An action to perform immediately before transmitting a command. Useful for `cc1101.begin_tx`.
* **on_transmit_end** (Optional, Action): An action to perform immediately after transmitting a command. Useful for `cc1101.end_tx`.

### 24-bit remotes without DIP switches

For a matching no-DIP remote, use `is_24_bit_nodip` and `packet_prefix` instead of `fan_id` and `is_24_bit`. Add `light` to expose the fan's light in Home Assistant:

```yaml
swing_fans:
  id: fan_controller
  remote_transmitter_id: transmitter
  fans:
    - name: "Ceiling Fan"
      is_24_bit_nodip: true
      packet_prefix: "1010010101011010" # Replace with your captured prefix
      light:
        name: "Ceiling Fan Light"

fan: []
button: []
```

To find your prefix, enable `dump: rc_switch` on the receiver and press several remote buttons. Look for repeated `protocol=6` packets with 24 binary digits. Copy the first 16 digits, preserving leading zeros, and check that they remain the same across buttons. These bits contain the addressing information; the boundary between the device ID and any fixed header bits is not yet established. The example prefix above is illustrative.

Keep the receiver's `on_rc_switch` action from the configuration above to update fan and light state when using the remote. Once configured, set `dump: []` to stop logging every received packet. Set `logger: {level: DEBUG}` to see outgoing packets.

The brightness slider selects one of six levels; zero turns the light off. The direction button toggles direction and does not report an absolute summer/winter mode.

## Example with CC1101

If you are using a CC1101 module via an external component that provides `remote_transmitter` and `remote_receiver` interfaces (the example below uses the [Official CC1101 component](https://esphome.io/components/cc1101)):

```yaml
external_components:
  - source: github://robertos/esphome-swing-fans@main
    components: [ swing_fans ]

spi:
  clk_pin: GPIO18
  miso_pin: GPIO19
  mosi_pin: GPIO23

cc1101:
  id: transceiver
  cs_pin: GPIO5
  frequency: 433.92MHz

remote_transmitter:
  id: transmitter
  pin: GPIO32 # GDO0 on the CC1101
  carrier_duty_percent: 100%
  non_blocking: true
  on_transmit:
    then:
    - cc1101.begin_tx: transceiver # Use the ID of the cc1101 component
  on_complete:
    then:
    - cc1101.begin_rx: transceiver   # Use the ID of the cc1101 component

remote_receiver:
  id: receiver
  pin: GPIO33 # GDO2 on the CC1101
  tolerance: 60%
  filter: 4us
  idle: 4ms
  dump: rc_switch
  on_rc_switch:
    then:
      - swing_fans.received_code:
          hub_id: fan_controller
          code: !lambda return x.code;
          protocol: !lambda return x.protocol;
         
swing_fans:
  id: fan_controller
  remote_transmitter_id: transmitter # Use the transmitter ID above
  fans:
    # ... fan list ...

fan: []
button: []
```

## Protocol Details

This component implements a specific protocol observed for certain ceiling fans:

* **Transmission:** Uses raw pulse width modulation.
    * Sync Pulse: `(-8900, 336)` microseconds
    * '0' Bit Pulse: `(-658, 336)` microseconds
    * '1' Bit Pulse: `(-321, 689)` microseconds
* **Data Structure:**
    * `[5-bit Fan ID][7-bit Command]` (12 bits total)
    * `[5-bit Fan ID][19-bit Command]` (24 bits total)
    * No-DIP variant: `[16-bit packet prefix][8-bit command]` in received RC-Switch bit order.
    * Both the ID and Command parts seem to be bitwise inverted in the raw transmission compared to logical representation. The component handles this inversion.
* **Reception:** Uses `remote_receiver` listening for `rc_switch` data, specifically checking for `protocol: 6`, which is close enough to the Swing Fans RF protocol for decoding (not for transmitting). It decodes the received `code` back into Fan ID and Command.

## Changelog

### May 23, 2026

* Set default `restore_mode` for fans to `RESTORE_DEFAULT_OFF`.
* Publish restored fan state during `setup()` so Home Assistant reflects persisted state after reboot.

## Contributing

Contributions are welcome! Please open an issue or pull request.