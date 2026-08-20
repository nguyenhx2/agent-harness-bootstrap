// The only script on this page, and none of the flows depend on it.
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
