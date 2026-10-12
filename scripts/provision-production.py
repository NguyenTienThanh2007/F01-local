"""Operator-only: derive the reviewed production recipe from an exact installed image."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--base-image-id', required=True)
args = parser.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}', args.base_image_id):
    parser.error('Exact accepted local image ID required.')
root = Path(__file__).resolve().parents[1]
base_tag = 'f01-production-base:'+args.base_image_id.removeprefix('sha256:')
subprocess.run(['docker', 'tag', args.base_image_id, base_tag], check=True)
installed = subprocess.check_output(['docker', 'image', 'inspect', base_tag, '--format', '{{.Id}}'], text=True).strip()
if installed != args.base_image_id:
    raise SystemExit('PRODUCTION_BASE_MISMATCH')
recipe = root/'sandbox/next-static-v1'
subprocess.run(['docker', 'build', '--build-arg', 'BASE_IMAGE='+base_tag, '--tag', 'f01-sandbox:next-static-v1', str(recipe)], check=True)
image = subprocess.check_output(['docker', 'image', 'inspect', 'f01-sandbox:next-static-v1', '--format', '{{.Id}}'], text=True).strip()
receipt = {'base_image_id': args.base_image_id, 'image_id': image, 'recipe_sha256': hashlib.sha256(b''.join(p.name.encode()+b'\0'+p.read_bytes() for p in sorted(recipe.iterdir()) if p.is_file())).hexdigest(), 'accepted': False}
(root/'.runtime').mkdir(exist_ok=True)
(root/'.runtime/production-image.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt, indent=2))
