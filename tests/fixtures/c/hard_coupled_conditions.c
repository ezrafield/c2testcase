int hard_coupled_conditions(int x, int y) {
    if ((x > 3 && y > 2) || (x > 3 && y < 10)) {
        return 1;
    }

    return 0;
}
