// The only script on the page. The contents disclosure is a <details>, so it
// already works without this file; these three behaviours are the manners a
// menu is expected to have.
const contents = document.getElementById('contents');

if (contents) {
  const close = () => contents.removeAttribute('open');

  contents.addEventListener('click', (event) => {
    if (event.target.closest('a')) close();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !contents.open) return;
    close();
    contents.querySelector('summary')?.focus();
  });

  document.addEventListener('pointerdown', (event) => {
    if (contents.open && !contents.contains(event.target)) close();
  });
}
