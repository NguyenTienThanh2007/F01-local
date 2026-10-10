from pathlib import Path
import os,subprocess,sys,time,urllib.request
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'scripts'))
from test_database import test_database,free_port
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
with test_database(root) as database:
 config=Config(str(root/'apps/api/alembic.ini'));engine=create_engine(database)
 with engine.begin() as connection:
  config.attributes['connection']=connection;command.upgrade(config,'head')
 engine.dispose();port=free_port();token='synthetic-m4-browser-token-12345678901234567890'
 env={**os.environ,'APP_ENV':'test','AUTH_MODE':'development','EXECUTION_MODE':'simulated','SIMULATION_RUNNER_ENABLED':'false','DATABASE_URL':database,'DEV_API_TOKEN':token,'DEV_AUTH_SUBJECT':'m4-browser-owner','OPENAI_API_KEY':''}
 with (root/'.runtime/editorial-workspace-api.log').open('w') as log:
  api=subprocess.Popen([sys.executable,'-m','uvicorn','f01.main:app','--host','127.0.0.1','--port',str(port)],cwd=root/'apps/api',env=env,stdout=log,stderr=log)
  try:
   for _ in range(100):
    if api.poll() is not None:raise RuntimeError('Owned test API failed at startup; inspect editorial-workspace-api.log')
    try:
     urllib.request.urlopen(f'http://127.0.0.1:{port}/v1/health/live',timeout=1).close();break
    except OSError:time.sleep(.1)
   else:raise RuntimeError('Owned test API did not become ready')
   test_env={**env,'M4_API_URL':f'http://127.0.0.1:{port}','M4_TEST_DATABASE_URL':database,'M4_TEST_TOKEN':token,'M4_AXE_SCRIPT':str(root/'apps/web/node_modules/axe-core/axe.min.js')}
   result=subprocess.run(['pnpm','--filter','@f01/web','test:workspace:e2e'],cwd=root,env=test_env)
  finally:
   api.terminate()
   try:api.wait(timeout=5)
   except subprocess.TimeoutExpired:api.kill();api.wait(timeout=5)
raise SystemExit(result.returncode)
