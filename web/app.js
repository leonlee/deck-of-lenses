(() => {
  const input = document.querySelector('#search');
  if (!input) return;
  const cards = [...document.querySelectorAll('[data-lens]')];
  const filters = [...document.querySelectorAll('[data-filter]')];
  let active = 'all';
  const normalize = value => value.normalize('NFKC').toLowerCase().trim();
  function update() {
    const words = normalize(input.value).split(/\s+/).filter(Boolean);
    let count = 0;
    for (const card of cards) {
      const match = words.every(word => normalize(card.dataset.search).includes(word));
      card.hidden = !match || (active !== 'all' && !card.dataset.suits.split(' ').includes(active));
      if (!card.hidden) count++;
    }
    document.querySelector('#count').textContent = count;
    document.querySelector('#empty').hidden = count !== 0;
  }
  input.addEventListener('input', update);
  for (const button of filters) button.addEventListener('click', () => {
    active = button.dataset.filter;
    for (const filter of filters) filter.setAttribute('aria-pressed', String(filter === button));
    update();
  });
  document.querySelector('#clear').addEventListener('click', () => {
    input.value = '';
    active = 'all';
    for (const filter of filters) filter.setAttribute('aria-pressed', String(filter.dataset.filter === 'all'));
    update();
    input.focus();
  });
  // Browsers can restore form values before or after this script runs.
  window.addEventListener('pageshow', update);
  update();
  document.querySelector('#catalog-tools').hidden = false;
})();
