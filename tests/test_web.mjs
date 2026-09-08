import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const script = readFileSync(new URL('../web/app.js', import.meta.url), 'utf8');
function setup(restoredQuery = '') {
  const element = (data = {}) => ({
    dataset: data, events: {}, hidden: false, attributes: {}, value: '',
    addEventListener(name, callback) { this.events[name] = callback; },
    setAttribute(name, value) { this.attributes[name] = value; },
    focus() { this.focused = true; },
  });
  const cards = [
    element({ search: '36 Chance 运气', suits: 'Game' }),
    element({ search: '41 Skill vs Chance 技能与运气', suits: 'Game' }),
    element({ search: '1 Emotion 情感', suits: 'Experience' }),
  ];
  const filters = ['all', 'Game', 'Experience'].map(filter => element({ filter }));
  const nodes = Object.fromEntries(['search', 'count', 'empty', 'clear', 'catalog-tools'].map(id => ['#' + id, element()]));
  nodes['#search'].value = restoredQuery;
  nodes['#catalog-tools'].hidden = true;
  const window = element();
  const document = {
    querySelector: selector => nodes[selector],
    querySelectorAll: selector => selector === '[data-lens]' ? cards : filters,
  };
  runInNewContext(script, { document, window });
  return { cards, filters, nodes, window };
}

test('English and Chinese search find the same matching lenses', () => {
  const { nodes, cards } = setup();
  for (const query of ['CHANCE', '运气']) {
    nodes['#search'].value = query;
    nodes['#search'].events.input();
    assert.deepEqual(cards.map(card => card.hidden), [false, false, true]);
    assert.equal(nodes['#count'].textContent, 2);
  }
});
test('Category filtering combines with search, and clear restores all lenses', () => {
  const { nodes, cards, filters } = setup();
  nodes['#search'].value = 'chance';
  nodes['#search'].events.input();
  filters[2].events.click();
  assert.equal(nodes['#empty'].hidden, false);
  assert.equal(filters[2].attributes['aria-pressed'], 'true');
  nodes['#clear'].events.click();
  assert.ok(cards.every(card => !card.hidden));
  assert.equal(nodes['#count'].textContent, 3);
  assert.equal(nodes['#empty'].hidden, true);
  assert.equal(filters[0].attributes['aria-pressed'], 'true');
  assert.equal(nodes['#search'].focused, true);
});
test('Reader pages need no catalog controls', () => {
  assert.doesNotThrow(() => runInNewContext(script, { document: { querySelector: () => null } }));
});
test('Restored search values agree with results on initialization and pageshow', () => {
  const { nodes, cards, window } = setup('运气');
  assert.equal(nodes['#count'].textContent, 2);
  assert.deepEqual(cards.map(card => card.hidden), [false, false, true]);
  assert.equal(nodes['#catalog-tools'].hidden, false);
  nodes['#search'].value = 'Emotion';
  window.events.pageshow();
  assert.deepEqual(cards.map(card => card.hidden), [true, true, false]);
  assert.equal(nodes['#count'].textContent, 1);
});
