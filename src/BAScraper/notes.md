Let the function accept both dict and model

If you want to allow flexibility:

```python
from typing import Union

def run_simulation(params: Union[SimulationParams, dict]) -> None:
    if not isinstance(params, SimulationParams):
        params = SimulationParams.model_validate(params)
    print(f"Running at {params.dt}, {params.iterations} iterations")

# usage
raw_data = {
    'dt': '2021-01-01T00:00:00+00:00',
    'iterations': 10
}

validated_params = SimulationParams.model_validate(raw_data)
run_simulation(validated_params)
```