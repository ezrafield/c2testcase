typedef struct {
    int architecture_baseline;
    int basic_design_reviewed;
    int detail_design_reviewed;
    int code_reviewed;
    int unit_test_passed;
    int integration_test_passed;
    int system_test_passed;
    int hardware_test_passed;
    int safety_signoff;
    int open_major_defects;
    int requirements_trace_complete;
    int interface_control_ready;
} LifecycleEvidence;

int architecture_lifecycle_gate(const LifecycleEvidence *evidence, int release_override) {
    if (
        evidence != 0 &&
        evidence->architecture_baseline &&
        evidence->basic_design_reviewed &&
        evidence->detail_design_reviewed &&
        evidence->code_reviewed &&
        evidence->unit_test_passed &&
        evidence->integration_test_passed &&
        evidence->system_test_passed &&
        evidence->hardware_test_passed &&
        evidence->safety_signoff &&
        evidence->requirements_trace_complete &&
        evidence->interface_control_ready &&
        (evidence->open_major_defects == 0 || release_override)
    ) {
        return 1;
    }

    return 0;
}
