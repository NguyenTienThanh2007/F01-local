"""Runs real Docker tests with explicit disposable DB; emits an honest bounded report."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
parser=argparse.ArgumentParser()
parser.add_argument('--image-id',required=True)
parser.add_argument('--database-url',required=True)
parser.add_argument('--production', action='store_true')
parser.add_argument('--socket',default='/var/run/docker.sock')
args=parser.parse_args()
if not re.fullmatch(r'sha256:[a-f0-9]{64}',args.image_id):parser.error('Exact local image ID required.')
from urllib.parse import urlsplit
if not urlsplit(args.database_url).path.startswith('/f01_test_') or not args.database_url.startswith('postgresql+psycopg://'):parser.error('Disposable PostgreSQL f01_test_* database required.')
root=Path(__file__).resolve().parents[1]
report={'image_id':args.image_id,'docker_containment':'not_run','docker_journey':'not_run','model_transport':'controlled OpenAI adapter responses','live_provider':'not_run','browser_journey':'not_run','phase2c_started':False}
if args.production: report['production_packaging']='not_run'
output=root/('.runtime/production-acceptance-report.json' if args.production else '.runtime/phase2b-acceptance-report.json');output.parent.mkdir(exist_ok=True)
if not Path(args.socket).is_socket():
    report['requested_image_id']=report.pop('image_id');report['image_id']=None;report['blocker']='DOCKER_SOCKET_UNAVAILABLE';output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(2)
env={**os.environ,'TEST_DATABASE_URL':args.database_url,'F01_DOCKER_ACCEPTANCE':'1','F01_SANDBOX_IMAGE_ID':args.image_id,'F01_DOCKER_SOCKET':args.socket}
start=time.monotonic()
junit=root/'.runtime/docker-acceptance.xml'
junit.unlink(missing_ok=True)  # A failed launch must not reuse earlier passing evidence.
result=subprocess.run(['uv','run','--locked','pytest','-q','tests/docker/test_acceptance.py', *(['tests/docker/test_production.py'] if args.production else []),'--junitxml='+str(junit)],cwd=root/'apps/api',env=env)
import xml.etree.ElementTree as ET
try:
    cases=ET.parse(junit).getroot().iter('testcase')
    for case in cases:
        name=case.attrib.get('name','')
        outcome='skipped' if case.find('skipped') is not None else 'failed' if case.find('failure') is not None or case.find('error') is not None else 'passed'
        if name=='test_docker_containment_and_resource_enforcement':report['docker_containment']=outcome
        elif name=='test_docker_signed_in_build_repair_preview_change_and_failed_update':report['docker_journey']=outcome
        elif name=='test_docker_production_packaging_exact_source_and_root_path':report['production_packaging']=outcome
except (OSError,ET.ParseError):report['blocker']='ACCEPTANCE_REPORT_UNAVAILABLE'
if result.returncode and report['docker_containment']=='passed' and report['docker_journey']=='passed' and (not args.production or report['production_packaging']=='passed'):
    report['docker_journey']='failed';report['blocker']='ACCEPTANCE_PROCESS_FAILED'
accepted=(not args.production or report['production_packaging']=='passed') and result.returncode==0 and report['docker_containment']=='passed' and report['docker_journey']=='passed'
report['duration_seconds']=round(time.monotonic()-start,2);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(0 if accepted else result.returncode or 2)
