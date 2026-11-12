### Small instances (55 x 5 seeds): % of runs that reach the optimum

| β | 1 it. | 5 it. | 10 it. | 20 it. | 50 it. |
|---|---|---|---|---|---|
| 0 | 91% | 91% | 91% | 91% | 91% |
| 0.25 | 82% | 96% | 97% | 99% | 100% |
| 0.5 | 85% | 95% | 96% | 98% | 99% |
| 0.75 | 81% | 95% | 96% | 97% | 98% |
| 1 | 82% | 93% | 96% | 97% | 97% |

### Medium instances (8 x 5 seeds): % of runs that reach the best known plan

| β | 1 it. | 5 it. | 10 it. | 20 it. | 50 it. | 100 it. |
|---|---|---|---|---|---|---|
| 0 | 50% | 50% | 50% | 50% | 50% | 50% |
| 0.25 | 38% | 40% | 40% | 52% | 58% | 62% |
| 0.5 | 35% | 38% | 38% | 40% | 65% | 72% |
| 0.75 | 38% | 40% | 45% | 50% | 55% | 65% |
| 1 | 32% | 42% | 48% | 50% | 62% | 72% |

### Medium instances after 100 iterations: first goal where the run is worse than best known (runs), and goal-4 gap of the runs equal on goals 1-3

| β | equal to best | goal 1 | goal 2 | goal 3 | goal 4 | avg goal-4 gap | max goal-4 gap |
|---|---|---|---|---|---|---|---|
| 0 | 20 | 0 | 0 | 10 | 10 | 0.31% | 1.80% |
| 0.25 | 25 | 0 | 0 | 0 | 15 | 0.11% | 0.57% |
| 0.5 | 29 | 0 | 0 | 0 | 11 | 0.14% | 2.40% |
| 0.75 | 26 | 0 | 0 | 0 | 14 | 0.15% | 2.40% |
| 1 | 29 | 0 | 0 | 0 | 11 | 0.09% | 0.57% |

### Medium instances: average runtime of 100 iterations and iteration where the best plan was found

| β | runtime | best found at iteration |
|---|---|---|
| 0 | 4.5 s | 1 |
| 0.25 | 7.6 s | 25 |
| 0.5 | 7.8 s | 26 |
| 0.75 | 8.0 s | 22 |
| 1 | 8.1 s | 25 |

### Medium instances: average runtime (all β) and best known goals (f1, f2, f3, f4)

| instance | runtime of 100 it. | best known goals |
|---|---|---|
| edmonton_s0 | 4.2 s | (0, 14, 5, 0.9833) |
| edmonton_s1 | 3.8 s | (0, 0, 6, 0.9825) |
| edmonton_s2 | 4.1 s | (0, 0, 3, 0.9834) |
| fez1_s0 | 6.5 s | (0, 324, 2, 0.6380) |
| fez1_s1 | 6.9 s | (0, 268, 3, 0.6320) |
| fez1_s2 | 6.7 s | (0, 19, 2, 0.6201) |
| fez2_s0 | 12.6 s | (0, 42, 5, 0.6601) |
| fez2_s1 | 12.8 s | (0, 76, 4, 0.6615) |
