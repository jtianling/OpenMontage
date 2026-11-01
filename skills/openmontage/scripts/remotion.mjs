import { spawnSync } from 'node:child_process';
import {
  accessSync, constants, cpSync, existsSync, lstatSync, readFileSync, realpathSync,
} from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const skillRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const workspace = realpathSync(process.cwd());
const [action, name, ...args] = process.argv.slice(2);

function localProject() {
  if (!name || path.isAbsolute(name)) throw new Error('Use a workspace-relative project.');
  const candidate = path.resolve(workspace, name);
  const relative = path.relative(workspace, candidate);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('Project must be inside the workspace.');
  }
  const parent = action === 'init' ? realpathSync(path.dirname(candidate)) : realpathSync(candidate);
  const actual = action === 'init' ? path.join(parent, path.basename(candidate)) : parent;
  if (!actual.startsWith(`${workspace}${path.sep}`) ||
      actual === skillRoot || actual.startsWith(`${skillRoot}${path.sep}`)) {
    throw new Error('Project cannot escape the workspace or write into the skill.');
  }
  return actual;
}

function execute(binary, parameters, cwd) {
  const result = spawnSync(binary, parameters, {
    cwd, stdio: 'inherit', env: { ...process.env, DO_NOT_TRACK: '1' },
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${binary} failed: exit=${result.status}, signal=${result.signal}.`);
  }
}

function installed(project) {
  const require = createRequire(path.join(project, 'package.json'));
  const modules = ['remotion', '@remotion/cli', '@remotion/media-utils'];
  const versions = modules.map((name) => {
    const pkg = JSON.parse(readFileSync(require.resolve(`${name}/package.json`), 'utf8'));
    return pkg.version;
  });
  if (new Set(versions).size !== 1) throw new Error('Remotion package versions must match.');
  const binary = path.join(project, 'node_modules', '.bin', 'remotion');
  accessSync(binary, constants.X_OK);
  const config = path.join(project, 'remotion.config.ts');
  if (!existsSync(config)) throw new Error('Missing platform browser/render configuration.');
  return binary;
}

function projectFile(project, value, mustExist) {
  if (!value || path.isAbsolute(value) || value.includes('://')) {
    throw new Error('Use a project-relative file path.');
  }
  const candidate = path.resolve(project, value);
  if (path.relative(project, candidate).split(path.sep)
    .some((part) => part.startsWith('.env'))) {
    throw new Error('Environment files are not render inputs.');
  }
  const parent = realpathSync(path.dirname(candidate));
  const actual = mustExist ? realpathSync(candidate) : path.join(parent, path.basename(candidate));
  if (!actual.startsWith(`${project}${path.sep}`)) {
    throw new Error('File must remain inside the project.');
  }
  if (!mustExist && lstatSync(actual, { throwIfNoEntry: false })) {
    throw new Error('Output already exists.');
  }
  return actual;
}

function renderArguments(project) {
  if (action === 'compositions') {
    if (args.length) throw new Error('compositions does not accept extra flags.');
    return [];
  }
  const [composition, output, ...flags] = args;
  if (!composition || !/^[A-Za-z0-9_-]+$/.test(composition)) {
    throw new Error('Specify a registered composition id.');
  }
  const destination = projectFile(project, output, false);
  const safeFlags = flags.map((flag) => {
    if (flag.startsWith('--props=')) {
      return `--props=${projectFile(project, flag.slice(8), true)}`;
    }
    if (/^--(?:frame|crf|quality)=[0-9]+$/.test(flag) ||
        /^--frames=[0-9]+-[0-9]+$/.test(flag) ||
        /^--scale=(?:[0-9]+(?:\.[0-9]+)?)$/.test(flag)) return flag;
    throw new Error(`Unsupported platform render option: ${flag}`);
  });
  return [composition, destination, ...safeFlags];
}

try {
  if (!['init', 'render', 'still', 'compositions'].includes(action)) {
    throw new Error('Usage: remotion.mjs init|render|still|compositions <project> [args].');
  }
  const project = localProject();
  if (action === 'init') {
    if (args.length || lstatSync(project, { throwIfNoEntry: false })) {
      throw new Error('Use a new project without extra flags.');
    }
    execute('monkeys-video-init', [name], workspace);
    installed(project);
    cpSync(path.join(skillRoot, 'remotion-composer', 'src'), path.join(project, 'src'), {
      recursive: true, errorOnExist: false,
    });
    console.log(JSON.stringify({ project: name, status: 'initialized' }));
  } else {
    const parameters = renderArguments(project);
    execute(installed(project), [action, 'src/index.tsx', ...parameters], project);
  }
} catch (error) {
  console.error(JSON.stringify({ ok: false, error: error.message }));
  process.exitCode = 1;
}
