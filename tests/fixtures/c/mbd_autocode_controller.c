typedef struct {
    int speed_rpm;
    int throttle_pct;
    int brake_pct;
    int battery_mv;
    int limp_mode;
    int sensor_fault;
} MbdInputs;

typedef struct {
    int torque_request;
    int diagnostic_code;
} MbdOutputs;

int mbd_autocode_controller(const MbdInputs *u, MbdOutputs *y, int calibration_ready) {
    if (
        calibration_ready &&
        u != 0 &&
        y != 0 &&
        ((u->speed_rpm > 1200 && u->throttle_pct > 35 && u->brake_pct < 5) ||
         (u->battery_mv < 9500 && !u->limp_mode)) &&
        !u->sensor_fault
    ) {
        y->torque_request = 1;
        return 1;
    }

    if (u != 0 && (u->sensor_fault || u->limp_mode || u->battery_mv < 9000)) {
        return -1;
    }

    return 0;
}
