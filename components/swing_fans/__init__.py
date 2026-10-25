"""
ESPHome component to control multiple ceiling fans using a specific
433MHz RF protocol (5-bit ID + 7/19-bit command).

Requires separate remote_transmitter and remote_receiver components.
"""
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import remote_transmitter, fan, button, light
from esphome.components.fan import RESTORE_MODES
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    CONF_ICON,
    CONF_DISABLED_BY_DEFAULT,
    CONF_RESTORE_MODE,
    CONF_CODE,
    CONF_PROTOCOL,
    CONF_TRIGGER_ID,
    CONF_LIGHT,
    CONF_OUTPUT_ID,
    CONF_GAMMA_CORRECT,
    CONF_DEFAULT_TRANSITION_LENGTH,
)
from esphome import automation
from esphome.core import coroutine_with_priority

CODEOWNERS = ["@robertos"]
DEPENDENCIES = ["remote_transmitter", "remote_receiver", "fan", "button"]
AUTO_LOAD = ["light"]

# Indicates that this directory contains multiple related C++ classes/files
MULTI_CONF = True

swing_fans_ns = cg.esphome_ns.namespace("swing_fans")

SwingFansHub = swing_fans_ns.class_("SwingFansHub", cg.Component)
SwingFansFan = swing_fans_ns.class_("SwingFansFan", fan.Fan, cg.Component)
SwingFansButton = swing_fans_ns.class_("SwingFansButton", button.Button, cg.Component)
SwingFansLight = swing_fans_ns.class_("SwingFansLight", light.LightOutput)
ReceivedCodeAction = swing_fans_ns.class_("ReceivedCodeAction", automation.Action)

# Custom configuration keys
CONF_FANS = "fans"
CONF_FAN_ID = "fan_id"
CONF_IS_24_BIT = "is_24_bit"
CONF_DIRECTION_BUTTON_ICON = "direction_button_icon"
CONF_DIRECTION_BUTTON_NAME = "direction_button_name"
CONF_REMOTE_TRANSMITTER_ID = "remote_transmitter_id"
CONF_ON_TRANSMIT_BEGIN = "on_transmit_begin"
CONF_ON_TRANSMIT_END = "on_transmit_end"
CONF_HUB_ID = "hub_id" # Key for linking action to hub
CONF_IS_24_BIT_NODIP = "is_24_bit_nodip"
CONF_PACKET_PREFIX = "packet_prefix"

LIGHT_SCHEMA = light.light_schema(
    SwingFansLight, light.LightType.BRIGHTNESS_ONLY,
    default_restore_mode="RESTORE_DEFAULT_OFF",
).extend({
    cv.Optional(CONF_GAMMA_CORRECT, default=1.0): cv.positive_float,
    cv.Optional(CONF_DEFAULT_TRANSITION_LENGTH, default="0s"): cv.positive_time_period_milliseconds,
})


def validate_packet_prefix(value):
    value = cv.string_strict(value)
    if len(value) != 16 or any(bit not in "01" for bit in value):
        raise cv.Invalid("packet_prefix must be a quoted 16-bit binary string")
    return value


def validate_fan(config):
    if config[CONF_IS_24_BIT_NODIP]:
        if config[CONF_IS_24_BIT] or CONF_FAN_ID in config:
            raise cv.Invalid("Use packet_prefix instead of fan_id/is_24_bit for the no-DIP mode")
        if CONF_PACKET_PREFIX not in config:
            raise cv.Invalid("packet_prefix is required for the no-DIP mode")
    else:
        if CONF_FAN_ID not in config:
            raise cv.Invalid("fan_id is required for the original protocol")
        if CONF_PACKET_PREFIX in config or CONF_LIGHT in config:
            raise cv.Invalid("packet_prefix and light require is_24_bit_nodip: true")
    return config

# Schema for an individual fan entry under the hub
FAN_SCHEMA = cv.All(cv.Schema(
    {
        cv.Required(CONF_NAME): cv.string, # Used for Fan entity name
        cv.Optional(CONF_FAN_ID): cv.string,
        cv.Optional(CONF_IS_24_BIT, default=False): cv.boolean,
        cv.Optional(CONF_IS_24_BIT_NODIP, default=False): cv.boolean,
        cv.Optional(CONF_PACKET_PREFIX): validate_packet_prefix,
        cv.Optional(CONF_LIGHT): LIGHT_SCHEMA,
        cv.Optional(CONF_DIRECTION_BUTTON_ICON, default="mdi:swap-horizontal"): cv.icon,
        cv.Optional(CONF_DIRECTION_BUTTON_NAME): cv.string, # Defaults to "<Fan Name> Direction"
        cv.Optional(CONF_RESTORE_MODE, default="RESTORE_DEFAULT_OFF"): cv.enum(RESTORE_MODES, upper=True, space="_"),
    }
), validate_fan)

# Main hub configuration schema
CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(SwingFansHub),
        cv.Required(CONF_REMOTE_TRANSMITTER_ID): cv.use_id(remote_transmitter.RemoteTransmitterComponent),
        cv.Required(CONF_FANS): cv.ensure_list(FAN_SCHEMA),
        cv.Optional(CONF_ON_TRANSMIT_BEGIN): automation.validate_automation(single=True),
        cv.Optional(CONF_ON_TRANSMIT_END): automation.validate_automation(single=True),
    }
).extend(cv.COMPONENT_SCHEMA)

# Custom action schema for received codes
RECEIVED_CODE_ACTION_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(ReceivedCodeAction),
        cv.Required(CONF_HUB_ID): cv.use_id(SwingFansHub),
        # Fields to receive data from the on_rc_switch lambda
        cv.Required(CONF_CODE): cv.templatable(cv.positive_int),
        cv.Required(CONF_PROTOCOL): cv.templatable(cv.positive_int),
    }
)

@automation.register_action("swing_fans.received_code", ReceivedCodeAction, RECEIVED_CODE_ACTION_SCHEMA, synchronous=True)
async def received_code_action_to_code(config, action_id, template_arg, args):
    paren = await cg.get_variable(config[CONF_HUB_ID])
    var = cg.new_Pvariable(action_id, template_arg, paren)
    cg.add(var.set_code(await cg.templatable(config[CONF_CODE], args, cg.uint64)))
    cg.add(var.set_protocol(await cg.templatable(config[CONF_PROTOCOL], args, cg.uint8)))
    return var

@coroutine_with_priority(40.0) # Run slightly later
async def to_code(config):
    hub = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(hub, config)

    transmitter = await cg.get_variable(config[CONF_REMOTE_TRANSMITTER_ID])
    cg.add(hub.set_transmitter(transmitter))

    if CONF_ON_TRANSMIT_BEGIN in config:
        await automation.build_automation(
            hub.get_transmit_begin_trigger(), [], config[CONF_ON_TRANSMIT_BEGIN]
        )
    if CONF_ON_TRANSMIT_END in config:
        await automation.build_automation(
            hub.get_transmit_end_trigger(), [], config[CONF_ON_TRANSMIT_END]
        )

    # Generate Fan and Button entities based on the fan list
    for i, fan_conf in enumerate(config[CONF_FANS]):
        fan_name = fan_conf[CONF_NAME]

        # Store fan config details in the hub C++ object
        if fan_conf[CONF_IS_24_BIT_NODIP]:
            cg.add(hub.add_nodip_fan_config(fan_name, fan_conf[CONF_PACKET_PREFIX]))
        else:
            cg.add(hub.add_fan_config(fan_name, fan_conf[CONF_FAN_ID], fan_conf[CONF_IS_24_BIT]))

        # Create Fan Entity
        fan_id_obj = cv.declare_id(SwingFansFan)(f"{config[CONF_ID]}_fan_{i}")
        fan_var = cg.new_Pvariable(fan_id_obj, fan_name)
        await fan.register_fan(fan_var, {
            CONF_ID: fan_id_obj, 
            CONF_NAME: fan_name, 
            CONF_DISABLED_BY_DEFAULT: False, 
            CONF_RESTORE_MODE: fan_conf[CONF_RESTORE_MODE]
        })
        cg.add(fan_var.set_hub(hub))
        cg.add(hub.add_managed_fan(fan_name, fan_var)) # Link C++ objects

        # Create Button Entity (for direction)
        button_id_obj = cv.declare_id(SwingFansButton)(f"{config[CONF_ID]}_button_{i}")
        button_var = cg.new_Pvariable(button_id_obj, fan_name)
        button_name = fan_conf.get(CONF_DIRECTION_BUTTON_NAME, f"{fan_name} Direction")
        await button.register_button(button_var, {
             CONF_ID: button_id_obj,
             CONF_NAME: button_name,
             CONF_ICON: fan_conf[CONF_DIRECTION_BUTTON_ICON],
             CONF_DISABLED_BY_DEFAULT: False,
        })
        cg.add(button_var.set_hub(hub))

        # Create the optional six-level light for no-DIP remotes.
        if CONF_LIGHT in fan_conf:
            light_conf = fan_conf[CONF_LIGHT]
            light_var = cg.new_Pvariable(
                light_conf[CONF_OUTPUT_ID], hub, fan_name, fan_conf[CONF_PACKET_PREFIX]
            )
            await light.register_light(light_var, light_conf)
            cg.add(hub.add_managed_light(light_var))
