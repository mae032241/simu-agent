"""Two reference mechanisms; no framework or domain adapter dependency."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--method', choices=('source_linear', 'operator_ridge'), required=True)
parser.add_argument('--fail', action='store_true', help='Acceptance failure injection, not a third mechanism')
args = parser.parse_args()
if args.fail:
    raise SystemExit('intentional acceptance failure before result production')
raw = Path('dataset.json').read_bytes()
data = json.loads(raw)
train = data['splits']['source_train']['examples']
dimension = data['dimension']
variance = [sum(row['x'][j] ** 2 for row in train) / len(train) for j in range(dimension)]
slopes = [sum(row['x'][j] * row['y'][j] for row in train) /
          sum(row['y'][j] ** 2 for row in train) for j in range(dimension)]
metrics = []
predictions = {}
for name in ('source_validation', 'public_target_stress'):
    split = data['splits'][name]
    if args.method == 'source_linear':
        weights = slopes
    else:
        weights = [a * prior / (a * a * prior + split['noise_std'] ** 2)
                   for a, prior in zip(split['operator'], variance)]
    values = [[weight * y for weight, y in zip(weights, row['y'])] for row in split['examples']]
    mse = sum((prediction - truth) ** 2
              for value, row in zip(values, split['examples'])
              for prediction, truth in zip(value, row['x'])) / (len(values) * dimension)
    metrics.append(dict(name=name + '_mse', value=mse, unit='latent_squared',
                        evaluation_key='generic_inverse.v1/' + name + '/latent_mse', direction='min'))
    predictions[name] = values
artifacts = Path('artifacts')
artifacts.mkdir(exist_ok=True)
(artifacts / 'predictions.json').write_text(json.dumps(predictions, sort_keys=True, allow_nan=False) + '\n')
(artifacts / 'method.json').write_text(json.dumps(dict(method=args.method, dimension=dimension,
    training_split='source_train', dataset_sha256=hashlib.sha256(raw).hexdigest(),
    target_labels_used_for_fit=False, all_evaluation_labels_public=True), sort_keys=True) + '\n')
(artifacts / 'result.json').write_text(json.dumps(dict(version=1, metrics=metrics,
    candidate=dict(label=args.method, metric='public_target_stress_mse', artifact='artifacts/predictions.json'), outputs=[
    dict(path='artifacts/predictions.json', label='Public validation and stress reconstructions'),
    dict(path='artifacts/method.json', label='Mechanism and exact dataset identity'),
]), sort_keys=True, allow_nan=False) + '\n')
