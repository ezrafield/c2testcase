typedef struct {
    int mode;
    int limit;
} DeviceState;

extern int sensor_ready(void);

int hard_environment_dependencies(DeviceState *state, int *samples, int index, int force) {
    if (sensor_ready() && state != 0 && samples[index] > state->limit && (state->mode == 2 || force)) {
        return 1;
    }

    return 0;
}
