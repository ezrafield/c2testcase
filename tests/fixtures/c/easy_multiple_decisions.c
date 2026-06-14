int easy_multiple_decisions(int x, int y, int enabled) {
    int score = 0;

    if (enabled && x >= 5) {
        score += 1;
    }

    if (y != 0 || x < -2) {
        score += 2;
    }

    while (enabled && score < 4) {
        score += 1;
    }

    return score;
}
