/* tests/i18n-coverage.test.js */
const fs = require('fs');
const path = require('path');

function extractKeysFromAppJs(source) {
  // Find occurrences like: _str.messages.details_hint or _str.progress.percent
  const re = /_str\s*\.\s*([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*)/g;
  const keys = new Set();
  let m;
  while ((m = re.exec(source)) !== null) keys.add(m[1]);
  return Array.from(keys);
}

function extractKeysFromTemplate(source) {
  // Find data-i18n and data-i18n-placeholder attribute values (single or double quoted)
  const re = /data-i18n(?:-placeholder)?\s*=\s*(?:"([^"]+)"|'([^']+)')/g;
  const keys = new Set();
  let m;
  while ((m = re.exec(source)) !== null) {
    const val = m[1] || m[2];
    if (val) keys.add(val);
  }
  return Array.from(keys);
}

function hasNestedKey(obj, dotted) {
  const parts = dotted.split('.');
  let cur = obj;
  for (const p of parts) {
    if (cur && Object.prototype.hasOwnProperty.call(cur, p)) {
      cur = cur[p];
    } else {
      return false;
    }
  }
  return true;
}

test('frontend i18n keys exist in all locale files', () => {
  const repoRoot = path.resolve(__dirname, '..');
  const appJsPath = path.join(repoRoot, 'static', 'app.js');
  const templatePath = path.join(repoRoot, 'templates', 'index.html');
  const localesDir = path.join(repoRoot, 'youtube_napoletano', 'locales');

  const appJs = fs.readFileSync(appJsPath, 'utf8');
  const template = fs.readFileSync(templatePath, 'utf8');

  const keysFromApp = extractKeysFromAppJs(appJs);
  const keysFromTpl = extractKeysFromTemplate(template);
  const allKeys = Array.from(new Set([...keysFromApp, ...keysFromTpl]));

  const localeFiles = fs.readdirSync(localesDir).filter(f => f.endsWith('.json'));
  const missing = {};

  localeFiles.forEach(file => {
    const localePath = path.join(localesDir, file);
    let localeJson;
    try {
      localeJson = JSON.parse(fs.readFileSync(localePath, 'utf8'));
    } catch (err) {
      missing[file] = [`<failed to parse ${file}: ${String(err)}>`];
      return;
    }
    const miss = [];
    allKeys.forEach(k => {
      if (!hasNestedKey(localeJson, k)) miss.push(k);
    });
    if (miss.length) missing[file] = miss;
  });

  if (Object.keys(missing).length) {
    const msgLines = ['Missing i18n keys detected:'];
    for (const [file, keys] of Object.entries(missing)) {
      msgLines.push(`- ${file}:`);
      keys.forEach(k => msgLines.push(`  - ${k}`));
    }
    throw new Error(msgLines.join('\n'));
  }
});
