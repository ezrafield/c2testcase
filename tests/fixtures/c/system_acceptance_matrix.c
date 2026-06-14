typedef enum {
    PHASE_ARCHITECTURE = 0,
    PHASE_BASIC_DESIGN = 1,
    PHASE_DETAIL_DESIGN = 2,
    PHASE_CODING = 3,
    PHASE_UNIT_TEST = 4,
    PHASE_INTEGRATION_TEST = 5,
    PHASE_SYSTEM_TEST = 6,
    PHASE_HARDWARE_TEST = 7
} ProjectPhase;

int system_acceptance_matrix(
    ProjectPhase phase,
    int risk_class,
    int requirement_pass,
    int timing_pass,
    int memory_pass,
    int fault_injection_pass,
    int hardware_loop_pass,
    int waiver_count
) {
    if (
        (phase == PHASE_SYSTEM_TEST || phase == PHASE_HARDWARE_TEST) &&
        risk_class <= 2 &&
        requirement_pass &&
        timing_pass &&
        memory_pass &&
        (fault_injection_pass || risk_class == 0) &&
        (hardware_loop_pass || phase == PHASE_SYSTEM_TEST) &&
        waiver_count == 0
    ) {
        return 1;
    }

    return 0;
}
