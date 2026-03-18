'use strict';

/**
 * i18n Coverage Test
 *
 * Verifies that every i18n key referenced by the frontend (static/app.js and
 * templates/index.html) exists in every locale JSON file under
 * youtube_napoletano/locales.
 *
 * The test fails with a clear message listing each missing key per locale so
 * that translation gaps are immediately visible.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

/**
 * Extract all `_str.<section>.<key>` paths referenced in app.js.
 * Matches patterns like `_str.messages.copy_failed` or `_str.download.success`.
 * @returns {string[]} Array of unique dotted key paths, e.g. ["messages.copy_failed"]
 */
function extractKeysFromAppJs() {
  const source = fs.readFileSync(path.join(ROOT, 'static', 'app.js'), 'utf8');
  const keys = new Set();
  // Match _str.<word>.<word> — the two-level dotted path used throughout app.js
  const re = /_str\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    keys.add(`${m[1]}.${m[2]}`);
  }
  return [...keys];
}

/**
 * Extract all keys from data-i18n and data-i18n-placeholder attributes in index.html.
 * @returns {string[]} Array of unique dotted key paths, e.g. ["download.placeholder"]
 */
function extractKeysFromTemplate() {
  const html = fs.readFileSync(path.join(ROOT, 'templates', 'index.html'), 'utf8');
  const keys = new Set();
  const re = /data-i18n(?:-placeholder)?="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    keys.add(m[1]);
  }
  return [...keys];
}

/**
 * Resolve a dotted key path (e.g. "messages.copy_failed") against a locale object.
 * @param {object} obj  The parsed locale JSON
 * @param {string} keyPath  Dotted path like "messages.copy_failed"
 * @returns {boolean} true if the key exists and its value is not null/undefined
 */
function hasKey(obj, keyPath) {
  const parts = keyPath.split('.');
  let current = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object' || !(part in current)) {
      return false;
    }
    current = current[part];
  }
  return current != null;
}

// ──────────────────────────────────────────────────────────────────────────────
// Collect all keys referenced by the frontend
// ──────────────────────────────────────────────────────────────────────────────

const appJsKeys = extractKeysFromAppJs();
const templateKeys = extractKeysFromTemplate();
const allKeys = [...new Set([...appJsKeys, ...templateKeys])].sort();

// ──────────────────────────────────────────────────────────────────────────────
// Load all locale files
// ──────────────────────────────────────────────────────────────────────────────

const localesDir = path.join(ROOT, 'youtube_napoletano', 'locales');
const localeFiles = fs
  .readdirSync(localesDir)
  .filter((f) => f.endsWith('.json'))
  .sort();

// ──────────────────────────────────────────────────────────────────────────────
// Tests
// ──────────────────────────────────────────────────────────────────────────────

describe('i18n key extraction sanity checks', () => {
  test('finds at least one key in app.js', () => {
    expect(appJsKeys.length).toBeGreaterThan(0);
  });

  test('finds at least one key in index.html', () => {
    expect(templateKeys.length).toBeGreaterThan(0);
  });

  test('combined key list is non-empty', () => {
    expect(allKeys.length).toBeGreaterThan(0);
  });
});

describe('locale files exist', () => {
  test('at least one locale JSON file is present', () => {
    expect(localeFiles.length).toBeGreaterThan(0);
  });

  test.each(['en.json', 'nap.json', 'it.json', 'es.json', 'fr.json', 'de.json'])(
    '%s exists in locales directory',
    (filename) => {
      expect(localeFiles).toContain(filename);
    },
  );
});

describe('translation completeness — every frontend key must exist in every locale', () => {
  for (const filename of localeFiles) {
    const filePath = path.join(localesDir, filename);
    const locale = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    const locale_name = filename.replace('.json', '');

    test.each(allKeys)(`[${locale_name}] key "%s" is present`, (keyPath) => {
      const present = hasKey(locale, keyPath);
      if (!present) {
        throw new Error(
          `Missing translation key "${keyPath}" in locale file "${filename}". ` +
            `Add the translation under the "${keyPath.split('.')[0]}" section.`,
        );
      }
      expect(present).toBe(true);
    });
  }
});
