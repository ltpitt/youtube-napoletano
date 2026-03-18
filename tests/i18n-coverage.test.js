'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const LOCALES_DIR = path.join(ROOT, 'youtube_napoletano', 'locales');
const APP_JS = path.join(ROOT, 'static', 'app.js');
const INDEX_HTML = path.join(ROOT, 'templates', 'index.html');

/**
 * Load all locale JSON files and return a map of { locale: parsedObject }.
 */
function loadLocales() {
  const locales = {};
  const files = fs.readdirSync(LOCALES_DIR).filter((f) => f.endsWith('.json'));
  for (const file of files) {
    const name = path.basename(file, '.json');
    locales[name] = JSON.parse(
      fs.readFileSync(path.join(LOCALES_DIR, file), 'utf8')
    );
  }
  return locales;
}

/**
 * Retrieve a nested key value (e.g. "messages.copy_failed") from an object.
 * Returns undefined if any segment is missing.
 */
function getNestedKey(obj, keyPath) {
  return keyPath
    .split('.')
    .reduce((acc, seg) => (acc != null ? acc[seg] : undefined), obj);
}

/**
 * Extract all _str.<section>.<key> references from app.js source.
 * Returns an array of dot-joined key paths (e.g. "messages.copy_failed").
 */
function extractAppJsKeys(source) {
  const keys = new Set();
  // Match _str.<word>.<word> patterns
  const re = /_str\.([a-zA-Z_]+)\.([a-zA-Z_]+)/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    keys.add(`${m[1]}.${m[2]}`);
  }
  return Array.from(keys);
}

/**
 * Extract all data-i18n and data-i18n-placeholder key values from index.html.
 * Returns an array of dot-joined key paths (e.g. "download.placeholder").
 */
function extractHtmlKeys(source) {
  const keys = new Set();
  const re = /data-i18n(?:-placeholder)?="([^"]+)"/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    keys.add(m[1]);
  }
  return Array.from(keys);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('i18n locale coverage', () => {
  const locales = loadLocales();
  const appJsSource = fs.readFileSync(APP_JS, 'utf8');
  const htmlSource = fs.readFileSync(INDEX_HTML, 'utf8');

  const appJsKeys = extractAppJsKeys(appJsSource);
  const htmlKeys = extractHtmlKeys(htmlSource);
  const allKeys = Array.from(new Set([...appJsKeys, ...htmlKeys]));

  test('at least one locale file is present', () => {
    expect(Object.keys(locales).length).toBeGreaterThan(0);
  });

  test('i18n keys are extracted from app.js and index.html', () => {
    expect(allKeys.length).toBeGreaterThan(0);
  });

  for (const locale of Object.keys(locales)) {
    describe(`locale: ${locale}`, () => {
      for (const key of allKeys) {
        test(`has key "${key}"`, () => {
          const value = getNestedKey(locales[locale], key);
          expect(value).toBeDefined();
        });
      }
    });
  }
});
