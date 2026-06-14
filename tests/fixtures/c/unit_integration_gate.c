typedef struct {
    int unit_assertions_passed;
    int branch_coverage_pct;
    int mcdc_coverage_pct;
    int static_analysis_clean;
    int integration_smoke_passed;
    int interface_contract_passed;
    int dependency_stubbed;
    int known_unreachable_justified;
} TestEvidence;

int unit_integration_gate(const TestEvidence *e, int allow_lower_mcdc_for_mock) {
    if (
        e != 0 &&
        e->unit_assertions_passed &&
        e->branch_coverage_pct >= 90 &&
        (e->mcdc_coverage_pct >= 100 || (allow_lower_mcdc_for_mock && e->mcdc_coverage_pct >= 85)) &&
        e->static_analysis_clean &&
        e->integration_smoke_passed &&
        e->interface_contract_passed &&
        (e->dependency_stubbed || e->known_unreachable_justified)
    ) {
        return 1;
    }

    return 0;
}
