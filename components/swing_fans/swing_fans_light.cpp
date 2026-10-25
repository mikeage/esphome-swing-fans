#include "swing_fans_light.h"
#include "swing_fans.h"

#include <cmath>
#include <cstdlib>

namespace esphome {
namespace swing_fans {

static constexpr uint8_t LIGHT_OFF = 0xF9;
static constexpr uint8_t LIGHT_LEVELS[6] = {0x5E, 0x49, 0x89, 0x5D, 0x85, 0x5B};

SwingFansLight::SwingFansLight(SwingFansHub *hub, const std::string &fan_name,
                             const std::string &packet_prefix)
    : hub_(hub), fan_name_(fan_name), packet_prefix_(std::strtoul(packet_prefix.c_str(), nullptr, 2)) {}

light::LightTraits SwingFansLight::get_traits() {
    auto traits = light::LightTraits();
    traits.set_supported_color_modes({light::ColorMode::BRIGHTNESS});
    return traits;
}

void SwingFansLight::update_state(light::LightState *state) {
    // LightState defers write_state until loop(), after the remote callback returns.
    // Record the origin here so remote updates and boot restoration never transmit.
    this->suppress_write_ = !this->initialized_ || this->receiving_;
    this->initialized_ = true;
}

void SwingFansLight::write_state(light::LightState *state) {
    if (this->suppress_write_) return;
    bool on;
    state->current_values_as_binary(&on);
    int level = 0;
    if (on) {
        float brightness;
        state->current_values_as_brightness(&brightness);
        level = static_cast<int>(std::floor(brightness * 6.0f + 0.5f));
        if (level < 1) level = 1;
        if (level > 6) level = 6;
    }
    // A transition may update repeatedly within one discrete level. Send it once.
    if (level != this->last_sent_level_) {
        this->hub_->send_nodip_command(this->fan_name_, level == 0 ? LIGHT_OFF : LIGHT_LEVELS[level - 1]);
        this->last_sent_level_ = level;
    }
    if (on && !state->is_transformer_active() &&
        std::fabs(state->remote_values.get_brightness() - level / 6.0f) > 0.0001f) {
        // Report the quantized level through LightState, without a second RF write.
        this->receiving_ = true;
        state->make_call().set_state(true).set_brightness(level / 6.0f)
            .set_transition_length_if_supported(0).perform();
        this->receiving_ = false;
    }
}

bool SwingFansLight::process_code(uint64_t code) {
    if (this->state_ == nullptr || (code >> 8) != this->packet_prefix_) return false;
    const uint8_t command = static_cast<uint8_t>(code);
    int level = 0;
    for (int i = 0; i < 6; ++i) {
        if (command == LIGHT_LEVELS[i]) level = i + 1;
    }
    if (level == 0 && command != LIGHT_OFF) return false;
    const bool on = level != 0;
    if (this->state_->remote_values.is_on() != on ||
        (on && std::fabs(this->state_->remote_values.get_brightness() - level / 6.0f) > 0.0001f)) {
        this->last_sent_level_ = -1;
        this->receiving_ = true;
        auto call = this->state_->make_call();
        call.set_state(on);
        if (on) call.set_brightness(level / 6.0f);
        call.set_transition_length_if_supported(0);
        call.perform();
        this->receiving_ = false;
    }
    return true;
}

} // namespace swing_fans
} // namespace esphome
