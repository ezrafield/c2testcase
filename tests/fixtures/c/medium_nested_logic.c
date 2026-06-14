int medium_nested_logic(int ready, int mode, int count, int limit, int override) {
    if (ready && ((mode == 1 && count > limit) || override)) {
        return 10;
    }

    return 0;
}
