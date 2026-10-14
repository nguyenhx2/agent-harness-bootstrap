// The only script on this page, and none of the flows depend on it.
//
// It also drives the section navigation. The list is in the markup and works
// as plain links without it; the script adds the narrow-screen drawer and marks
// the section being read.
//
// Every net - the delivery net, the tailor, the control route - is driven by a
// radio group and `:has()`, so stepping a flow, blocking a request and
// resolving a roster all work with JavaScript switched off, keyboard included.
// What is left for a script is the one convenience markup cannot express: a
// copy control on each install listing, injected only once the clipboard API
// is known to exist, so a button that could not work is never drawn.

const JA = document.documentElement.lang.startsWith('ja');
// The class name is the hook the stylesheet owns; the words are the copy. They
// happened to be the same string in English, which hid a bug on the Japanese
// page for exactly as long as nobody measured the button.
const CLASS = 'copy';
const IDLE = JA ? 'コピー' : 'copy';
const DONE = JA ? 'コピー済' : 'copied';
const HOLD = 1600;

function label(button, text, state) {
  button.textContent = text;
  if (state) button.dataset.state = state;
  else delete button.dataset.state;
}

function wire(listing) {
  const code = listing.querySelector('code');
  if (!code) return;

  const button = document.createElement('button');
  button.type = 'button';
  button.className = CLASS;
  button.setAttribute('aria-live', 'polite');
  label(button, IDLE);

  let timer = 0;
  button.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(code.innerText.trim());
    } catch {
      // A denied permission is the user's answer, not an error to shout about.
      return;
    }
    label(button, DONE, 'done');
    clearTimeout(timer);
    timer = setTimeout(() => label(button, IDLE), HOLD);
  });

  listing.append(button);
}

if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
  document.querySelectorAll('.listing').forEach(wire);
}

// ---------------------------------------------------------------- navigation

document.documentElement.classList.add('js');

const toc = document.getElementById('toc');
const menu = document.querySelector('.menu');
const scrim = document.querySelector('.scrim');
const narrow = window.matchMedia('(max-width: 63.99rem)');

function setOpen(open, { restore = true } = {}) {
  if (!toc || !menu) return;
  menu.setAttribute('aria-expanded', String(open));
  toc.toggleAttribute('data-open', open);
  if (scrim) scrim.hidden = !open;
  document.documentElement.classList.toggle('toc-open', open);
  if (open) toc.querySelector('a')?.focus();
  else if (restore) menu.focus();
}

// The drawer hangs from the bottom of the masthead, whose height changes when
// the product name wraps on a narrow phone.
const mast = document.querySelector('.masthead');
if (mast && 'ResizeObserver' in window) {
  new ResizeObserver(() => {
    document.documentElement.style.setProperty('--mast-h', `${mast.offsetHeight}px`);
  }).observe(mast);
}

if (toc && menu) {
  menu.hidden = false;
  menu.addEventListener('click', () => setOpen(menu.getAttribute('aria-expanded') !== 'true'));
  scrim?.addEventListener('click', () => setOpen(false));
  // A followed link closes the drawer and lets the page take focus at the target.
  toc.addEventListener('click', (e) => {
    if (e.target.closest('a') && narrow.matches) setOpen(false, { restore: false });
  });
  document.addEventListener('keydown', (e) => {
    if (menu.getAttribute('aria-expanded') !== 'true') return;
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      return;
    }
    // Keep Tab inside the drawer and its button while it is open.
    if (e.key === 'Tab') {
      const stops = [menu, ...toc.querySelectorAll('a')];
      const first = stops[0];
      const last = stops[stops.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  // Widening past the breakpoint with the drawer open would leave the page locked.
  narrow.addEventListener('change', () => {
    if (!narrow.matches && menu.getAttribute('aria-expanded') === 'true') setOpen(false, { restore: false });
  });
}

// Mark the section being read: the last one whose heading has passed the upper
// third of the viewport.
const links = toc ? [...toc.querySelectorAll('.toc__list a[href^="#"]')] : [];
const targets = links.map((a) => document.getElementById(a.hash.slice(1))).filter(Boolean);

function mark(id) {
  for (const a of links) {
    if (a.hash === `#${id}`) a.setAttribute('aria-current', 'true');
    else a.removeAttribute('aria-current');
  }
}

if (targets.length && 'IntersectionObserver' in window) {
  const seen = new Set();
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (e.isIntersecting) seen.add(e.target.id);
      else seen.delete(e.target.id);
    }
    const current = targets.find((t) => seen.has(t.id));
    if (current) mark(current.id);
    else if (window.scrollY < targets[0].offsetTop) mark('');
  }, { rootMargin: '-30% 0px -60% 0px' });
  targets.forEach((t) => io.observe(t));
}
