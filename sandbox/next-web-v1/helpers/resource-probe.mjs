import fs from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { spawn } from 'node:child_process';

const mode = process.argv[2];

if (mode === 'memory') {
  const chunks = [];
  for (let n = 0; n < 128; n++) {
    const b = Buffer.alloc(16 * 1024 * 1024, 1);
    chunks.push(b);
  }
  console.log('{}');
}

if (mode === 'disk') {
  let full = false;
  const handle = await fs.open('/work/disk-probe', 'w');
  try {
    for (let n = 0; n < 32; n++) {
      await handle.write(Buffer.alloc(1024 * 1024, 1));
    }
  } catch (e) {
    full = e.code === 'ENOSPC';
  } finally {
    await handle.close();
    await fs.unlink('/work/disk-probe');
  }
  console.log(JSON.stringify({ full }));
}

if (mode === 'cpu') {
  const children = [];
  for (let n = 0; n < 4; n++) {
    children.push(
      spawn('/usr/local/bin/node', ['/opt/f01/busy.mjs'], { stdio: 'ignore' })
    );
  }

  await new Promise((resolve) => setTimeout(resolve, 4000));

  for (const child of children) {
    child.kill('SIGKILL');
  }

  console.log(
    JSON.stringify({
      stat: await fs.readFile('/sys/fs/cgroup/cpu.stat', 'utf8'),
    })
  );
}

if (mode === 'pids') {
  const children = [];
  let rejected = false;

  for (let n = 0; n < 150; n++) {
    const child = spawn('/bin/sleep', ['15'], { stdio: 'ignore' });

    const started = await new Promise((resolve) => {
      child.once('spawn', () => resolve(true));
      child.once('error', () => resolve(false));
    });

    if (!started) {
      rejected = true;
      break;
    }

    children.push(child);
  }

  const events = readFileSync('/sys/fs/cgroup/pids.events', 'utf8');

  for (const child of children) {
    child.kill('SIGKILL');
  }

  console.log(JSON.stringify({ events, rejected }));
}
