typedef enum {
    STATE_INIT = 0,
    STATE_ACTIVE = 1,
    STATE_ERROR = 2
} State;

int medium_enum_state(State state, int retries, int has_fault, int manual_reset) {
    if ((state == STATE_ACTIVE && retries <= 3) || (has_fault && !manual_reset)) {
        return 1;
    }

    return 0;
}
