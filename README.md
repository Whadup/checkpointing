# checkpointing

A small library to store checkpoints of intermediate results and resume long-running computations.

### Installation

```bash
pip install git+https://github.com/Whadup/checkpointing
```

## Usage

```python
from checkpointing import checkpointed_function

@checkpointed_function
def long_running_computation():
    # long running computation
    return result

long_running_computation()
```

This will store the result in `.cache/` and load it if the function is called again.


## Internals

This library uses the `inspect` module to get the source code of the function. It then hashes the source code to create a unique identifier for the function. This identifier is used to store the result of the function in `.cache/` as a binary  file using the library `dill`. We can avoid evaluating the function when the source hash and all arguments match. When results of a checkpointed function are passed to another checkpointed function, the arguments match if they correspond to the same cached file.

Results of functions are shallowly inspected, so returning tuples, dicts or lists is treated accordingly. 