import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import {chromium} from 'playwright';
import {loadScenario, runScenarioAcceptance} from './generated-app-acceptance.mjs';
import {analytics, social, storefront} from './fixtures/multi-app-harness.mjs';

// Hand-written harness fixtures exercise the checker itself. They are NOT generated
// applications and never stand in for real-model, Docker or preview acceptance.
async function serve(html) {
  const server = http.createServer((request, response) => {
    if (request.url === '/') {
      response.writeHead(200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'});
      response.end(html);
    } else {
      response.writeHead(404);
      response.end();
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return {url: `http://127.0.0.1:${server.address().port}/`, close: () => new Promise(resolve => server.close(resolve))};
}

async function accept(id, html) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), `f01-${id}-`));
  const server = await serve(html);
  const browser = await chromium.launch({headless: true});
  try {
    return await runScenarioAcceptance(browser, await loadScenario(id), {url: server.url, directory, checkTimeout: 3000});
  } finally {
    await browser.close();
    await server.close();
    await fs.rm(directory, {recursive: true, force: true});
  }
}

const failed = report => report.checks.filter(check => !check.passed).map(check => `${check.name}: ${check.error}`);

for (const [id, html] of [['analytics-dashboard', analytics], ['storefront', storefront], ['social-profile', social]]) {
  test(`conforming ${id} harness fixture passes every functional, visual and runtime check`, async () => {
    const report = await accept(id, html);
    assert.deepEqual(failed(report), []);
    assert.equal(report.passed, true);
    assert.ok(report.summary.functional.total >= 5);
    assert.equal(report.summary.runtime.total, 2);
  });
}

test('unlabelled demonstration data fails the truthful sample-data check', async () => {
  const report = await accept('analytics-dashboard', analytics.replace('Sample data — fixed harness numbers.', 'Live store performance.'));
  assert.equal(report.passed, false);
  assert.deepEqual(report.checks.filter(check => !check.passed).map(check => check.name), ['Visible "Sample data" label keeps demonstration data truthful']);
});

test('a filter that never changes the KPIs fails instead of passing on presence alone', async () => {
  const report = await accept('analytics-dashboard', analytics.replace('region.onchange=render;', ''));
  assert.equal(report.passed, false);
  assert.ok(failed(report).some(row => row.startsWith('"Region" filter updates KPIs')));
});

test('an inert Add to cart button fails cart, subtotal and persistence checks', async () => {
  const report = await accept('storefront', storefront.replace('cart.push(+t.dataset.add);save();render();', ''));
  assert.equal(report.passed, false);
  const names = report.checks.filter(check => !check.passed).map(check => check.name);
  assert.ok(names.includes('"Add to cart" increments the "Cart" count'));
  assert.ok(names.includes('Cart survives a page reload'));
});

test('an in-memory cart that is lost on reload fails persistence', async () => {
  const report = await accept('storefront', storefront.replace("localStorage.setItem('fernwood-cart',JSON.stringify(cart))", '0'));
  assert.deepEqual(report.checks.filter(check => !check.passed).map(check => check.name), ['Cart survives a page reload']);
});

test('a remote image is reported as an external request even when features work', async () => {
  const report = await accept('social-profile', social.replace('<header>', '<header><img src="https://images.f01-acceptance.invalid/avatar.jpg" alt="Mai Tran">'));
  assert.equal(report.passed, false);
  assert.equal(report.summary.functional.passed, report.summary.functional.total);
  const network = report.checks.find(check => check.name === 'No failed or external network requests');
  assert.equal(network.passed, false);
  assert.ok(report.runtime.externalRequests.some(url => url.startsWith('https://images.f01-acceptance.invalid/')));
});

test('a like toggle without aria-pressed state fails the social interaction check', async () => {
  const report = await accept('social-profile', social.replace(`aria-pressed="'+p.liked+'" `, ''));
  assert.equal(report.passed, false);
  assert.ok(failed(report).some(row => row.startsWith('"Like" toggle changes aria-pressed')));
});

test('products nested as article inside list item are counted once', async () => {
  const nested = storefront.replace(`'<li><h2>'+p.name+'</h2><p>'+p.category+'</p><p>'+money(p.price)+'</p><button type="button" data-add="'+p.id+'">Add to cart</button> <button type="button" data-view="'+p.id+'">View details</button></li>'`,
    `'<li><article><h2>'+p.name+'</h2><p>'+p.category+'</p><p>'+money(p.price)+'</p><button type="button" data-add="'+p.id+'">Add to cart</button> <button type="button" data-view="'+p.id+'">View details</button></article></li>'`);
  assert.notEqual(nested, storefront);
  const report = await accept('storefront', nested);
  assert.deepEqual(failed(report), []);
  assert.deepEqual(report.checks.find(check => check.name.startsWith('"Products"')).evidence, {products: 6});
});
