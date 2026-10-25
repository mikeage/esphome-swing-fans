#pragma once

#include "esphome/components/light/light_output.h"

#include <cstdint>
#include <string>

namespace esphome {
namespace swing_fans {

class SwingFansHub;

class SwingFansLight : public light::LightOutput {
public:
    SwingFansLight(SwingFansHub *hub, const std::string &fan_name, const std::string &packet_prefix);
    light::LightTraits get_traits() override;
    void setup_state(light::LightState *state) override { this->state_ = state; }
    void update_state(light::LightState *state) override;
    void write_state(light::LightState *state) override;
    bool process_code(uint64_t code);

protected:
    SwingFansHub *hub_;
    light::LightState *state_{nullptr};
    std::string fan_name_;
    uint16_t packet_prefix_;
    int last_sent_level_{-1};
    bool initialized_{false};
    bool receiving_{false};
    bool suppress_write_{true};
};

} // namespace swing_fans
} // namespace esphome
