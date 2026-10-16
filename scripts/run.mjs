import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const mode = process.argv[2];
let backend;
let vite;
let stopping = false;

async function shutdown(code = 0) {
  if (stopping) return;
  stopping = true;
  if (vite) await vite.close();
  if (backend && backend.exitCode === null) {
    backend.kill('SIGTERM');
    const timer = setTimeout(() => backend.kill('SIGKILL'), 3000);
    timer.unref();
    await new Promise(resolve => backend.once('exit', resolve));
    clearTimeout(timer);
  }
  process.exitCode = code;
}

function port(value, fallback) {
  const result = Number(value || fallback);
  if (!Number.isInteger(result) || result < 1 || result > 65535) throw new Error('Ports must be integers from 1 to 65535.');
  return result;
}

function startBackend(host, apiPort) {
  backend = spawn(python, ['-m', 'mc_builder.server', '--host', host, '--port', String(apiPort)], { cwd: root, stdio: 'inherit' });
  backend.on('error', error => { console.error(error.message); void shutdown(1); });
  backend.on('exit', code => { if (!stopping) void shutdown(code || 1); });
}

async function health(apiPort) {
  try {
    const response = await fetch(`http://127.0.0.1:${apiPort}/api/health`, { signal: AbortSignal.timeout(500) });
    const data = await response.json();
    return response.ok && data.application === 'blockwright' && data.status === 'ok';
  } catch { return false; }
}

process.once('SIGINT', () => void shutdown());
process.once('SIGTERM', () => void shutdown());

try {
  if (!existsSync(python)) throw new Error('Python environment missing. Run python3 -m venv .venv, then .venv/bin/python -m pip install -r requirements-dev.txt.');
  const dependencyCheck = spawnSync(python, ['-c', 'import nbtlib, numpy'], { cwd: root, stdio: 'ignore' });
  if (dependencyCheck.status !== 0) throw new Error('Python dependencies missing. Run .venv/bin/python -m pip install -r requirements.txt.');
  if (mode === 'test') {
    const result = spawnSync(python, ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], { cwd: root, stdio: 'inherit' });
    process.exitCode = result.status ?? 1;
  } else if (mode === 'start') {
    if (!existsSync(path.join(root, 'dist/index.html'))) throw new Error('Frontend missing. Run npm run build first.');
    startBackend('0.0.0.0', port(process.env.PORT, 3000));
  } else if (mode === 'dev') {
    const apiPort = port(process.env.BLOCKWRIGHT_API_PORT, 8000);
    if (!await health(apiPort)) {
      startBackend('127.0.0.1', apiPort);
      const deadline = Date.now() + 10000;
      while (!await health(apiPort)) {
        if (backend.exitCode !== null || stopping) throw new Error(`The Python API could not start on port ${apiPort}.`);
        if (Date.now() > deadline) throw new Error('The Python API did not become ready within 10 seconds.');
        await new Promise(resolve => setTimeout(resolve, 150));
      }
    }
    const { createServer } = await import('vite');
    vite = await createServer({ root, server: { host: '0.0.0.0', port: port(process.env.PORT, 3000), strictPort: true } });
    await vite.listen();
    console.log('Blockwright frontend and API are ready.');
    vite.printUrls();
  } else throw new Error('Use npm run dev, npm start, or npm test.');
} catch (error) {
  console.error(error.message);
  await shutdown(1);
}
