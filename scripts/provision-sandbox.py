"""Operator provisioning only. Never invoked by models, API routes or workers."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from shutil import which

parser=argparse.ArgumentParser()
parser.add_argument('--base-image',required=True,help='Reviewed Docker Official Node image at exact digest: node@sha256:...')
args=parser.parse_args()
if not re.fullmatch(r'(?:docker.io/library/)?node@sha256:[a-f0-9]{64}',args.base_image):parser.error('An exact official Node image digest is required; tags are rejected.')
if not which('docker'):raise SystemExit('DOCKER_UNAVAILABLE: Docker CLI is not installed in this environment.')
root=Path(__file__).resolve().parents[1];recipe=root/'sandbox/next-web-v1'
subprocess.run(['docker','build','--pull','--build-arg','BASE_IMAGE='+args.base_image,'--tag','f01-sandbox:next-web-v1',str(recipe)],check=True)
result=json.loads(subprocess.check_output(['docker','image','inspect','f01-sandbox:next-web-v1']))[0]
image=result['Id']
if not re.fullmatch(r'sha256:[a-f0-9]{64}',image) or result['Config']['User']!='10000:10000' or result['Config'].get('Volumes') or result['Config'].get('OnBuild'):raise SystemExit('SANDBOX_IMAGE_INVALID')
files=[p for p in recipe.rglob('*') if p.is_file() and 'node_modules' not in p.parts]
receipt={'image_id':image,'base_image':args.base_image,'recipe_sha256':hashlib.sha256(b''.join(p.relative_to(recipe).as_posix().encode()+b'\0'+p.read_bytes() for p in sorted(files))).hexdigest(),'containment_verified':False}
output=root/'.runtime/sandbox-image.json';output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
print('Run Docker acceptance before enabling real execution. Image creation alone does not certify containment.')
