# Person 3: Data and Instance Generation

## 1. Objective
Generate reproducible ambulance relocation instances
for Model R and the GRASP heuristic.

## 2. Data Sources
- Fez-Meknes: Published ambulance deployment dataset.
- Madrid: Municipal geographic and SAMUR-PC data.
- Edmonton: Published emergency response dataset.

## 3. Synthetic Assumptions
- Ambulance locations are generated using random seeds.
- Home bases and remaining shift times are synthetic.
- Sleeping crew locations are generated randomly.
- Fez-Meknes base capacities are assumed.
- Madrid base capacities are estimated.
- Edmonton base-to-base times are approximated.

## 4. Experimental Design
- 200 scenarios across three regions.
- Multiple fleet sizes and response-time limits.
- Five random seeds per configuration.
- All scenarios use the heading_home shift mode.

## 5. Validation
- Correct matrix dimensions.
- Non-negative travel times.
- Normalized demand weights.
- Reproducibility with fixed random seeds.
- Model R capacity feasibility.

## 6. Outputs
- scenarios_multiregion.csv
- scenario_statistics.csv


## 7. Integration with Other Team Members

The official scenario generator is implemented in
`official_instances.py`.

The experimental catalog contains 200 reproducible
scenarios across Fez-Meknes, Madrid, and Edmonton.

### Loading an instance

From the repository root:

```python
from person3.catalog import load_instance

inst = load_instance("fez_case1_I4_T20_S0_seed0")
```

The returned object is compatible with:
- Person 1's Gurobi Model R solver.
- Person 2's GRASP heuristic.
- Person 4's experimental evaluation framework.

### Running validation

```bash
python person3/audit_catalog.py
python person3/handoff_check.py
```

### Generated outputs

- `scenarios_multiregion.csv`: scenario catalog
- `scenario_statistics.csv`: validation and descriptive statistics

### Reproducibility

Every scenario is identified by a unique ID and its
generation parameters, including the random seed.

The geographic matrices are reused from the existing
repository datasets.

### Limitations

The ambulance states are synthetic rather than observed
historical dispatch states.

Capacity assumptions vary by region.

The scenarios represent individual relocation decisions,
not a complete time-evolving emergency dispatch simulation.
