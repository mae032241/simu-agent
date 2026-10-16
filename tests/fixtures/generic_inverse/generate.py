"""Generate the fully public, deterministic diagonal inverse problem (stdlib only)."""
import json
import math
from pathlib import Path
import random
import sys


def generate(path):
    rng = random.Random(20261016)
    dimension = 8
    splits = {}
    for name, count, attenuation, noise in (
        ('source_train', 128, 0.12, 0.025),
        ('source_validation', 64, 0.12, 0.025),
        ('public_target_stress', 64, 0.48, 0.10),
    ):
        operator = [math.exp(-attenuation * j) for j in range(dimension)]
        examples = []
        for _ in range(count):
            latent = [rng.gauss(0, 1 / (j + 1)) for j in range(dimension)]
            observed = [a * x + rng.gauss(0, noise) for a, x in zip(operator, latent)]
            examples.append(dict(x=latent, y=observed))
        splits[name] = dict(operator=operator, noise_std=noise, examples=examples,
                            labels='public', evaluation='mean squared latent reconstruction error')
    value = dict(version=1, seed=20261016, dimension=dimension, splits=splits,
                 disclosure='All labels are public. No hidden reward or held-out target test exists.')
    Path(path).write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    generate(sys.argv[1])
