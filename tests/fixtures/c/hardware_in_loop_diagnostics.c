extern int adc_read_channel(int channel);
extern int can_bus_alive(void);
extern int pwm_feedback_ok(int channel);

int hardware_in_loop_diagnostics(int channel, int expected_mv, int tolerance_mv, int emergency_stop) {
    int measured = adc_read_channel(channel);

    if (
        can_bus_alive() &&
        pwm_feedback_ok(channel) &&
        !emergency_stop &&
        measured >= expected_mv - tolerance_mv &&
        measured <= expected_mv + tolerance_mv &&
        (channel >= 0 && channel < 8)
    ) {
        return 1;
    }

    if (emergency_stop || !can_bus_alive() || !pwm_feedback_ok(channel)) {
        return -1;
    }

    return 0;
}
