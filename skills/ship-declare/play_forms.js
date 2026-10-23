// Helpers for Play Console App content forms. Run once with javascript_tool on each form page
// (a navigation clears them), then call them in later javascript_tool calls. They read and answer
// the form as text, so no screenshots are needed.
//   inputs()            radios and checkboxes with their label and state
//   pick(/label/)       click the radio or checkbox whose label matches (no-op when already checked)
//   btn('Next')         click the button with that exact text; save() clicks the last visible Save
//   text(n)             the page text after the left menu (document.querySelector('main') is often null)
//   answerIarc(yes)     answer every open IARC question: Yes when the question matches the regex
//                       `yes`, otherwise No. Sections open one by one, so it waits between answers.
//                       Returns one line per answer: check them, then Save, Next, read the ratings, Save.
//   tick(cb)            check an Angular <mat-checkbox role=checkbox> (table rows, "Select all rows",
//                       tags): they ignore .click(), but take mouse events sent to their inner div
//   setTags(['Card'])   in the open Manage tags panel, check exactly these tags; then btn('Apply').
//                       Returns the tags now checked, or the names Play does not offer.
window.tick = async (cb, on = true) => {
  if ((cb.getAttribute('aria-checked') === 'true') !== on) {
    const inner = cb.querySelector('div') || cb;
    for (const ty of ['mousedown', 'mouseup', 'click'])
      inner.dispatchEvent(new MouseEvent(ty, { bubbles: true, cancelable: true, view: window }));
    await new Promise((r) => setTimeout(r, 400));
  }
  return cb.getAttribute('aria-checked');
};
window.setTags = async (names) => {
  const panel = [...document.querySelectorAll('[role=dialog],aside,[class*=panel]')]
    .filter((e) => e.innerText.includes('Add up to 5 tags'))
    .sort((a, b) => a.innerText.length - b.innerText.length)[0];
  if (!panel) return 'open Manage tags first';
  const rows = [...panel.querySelectorAll('[role=row]')].filter((r) => r.querySelector('[role=checkbox]'));
  const name = (r) => r.innerText.split('\n')[0].trim();
  const missing = names.filter((n) => !rows.some((r) => name(r) === n));
  if (missing.length) return `not offered: ${missing.join(', ')}`;
  for (const r of rows) await tick(r.querySelector('[role=checkbox]'), names.includes(name(r)));
  return rows.filter((r) => r.querySelector('[role=checkbox]').getAttribute('aria-checked') === 'true').map(name).join(', ');
};
window.lbl = (i) => {
  let e = i;
  for (let k = 0; k < 6 && e; k++) {
    e = e.parentElement;
    const t = e?.innerText?.trim();
    if (t) return t.replace(/\s+/g, ' ').slice(0, 90);
  }
  return '';
};
const boxes = () => [...document.querySelectorAll('input[type=radio],input[type=checkbox]')];
window.inputs = () =>
  boxes().map((r, i) => `${i} ${r.type[0]} ${r.checked ? '[x]' : '[ ]'} ${lbl(r)}`).join('\n');
window.pick = (re) => {
  const r = boxes().find((r) => re.test(lbl(r)));
  if (r && !r.checked) r.click();
  return r ? lbl(r) : `NOTFOUND ${re}`;
};
window.btn = (t) => {
  const b = [...document.querySelectorAll('button')].filter((b) => b.offsetParent && b.innerText.trim() === t).at(-1);
  b?.click();
  return b ? `${t}${b.disabled ? ' (disabled)' : ''}` : `no ${t}`;
};
window.save = () => btn('Save');
window.buttons = () =>
  [...document.querySelectorAll('button')]
    .filter((b) => b.offsetParent)
    .map((b) => b.innerText.trim() + (b.disabled ? '(d)' : ''))
    .filter((t) => t && t.length < 40)
    .join(' | ');
window.text = (n = 2000) => {
  const t = document.body.innerText.replace(/\n{2,}/g, '\n');
  const i = t.indexOf('\nsell\n');
  return t.slice(i > 0 ? i + 6 : 0).slice(0, n);
};
// IARC questions: radio groups whose options are labelled (hidden groups have empty labels).
const iarcGroups = () => {
  const g = {};
  for (const r of document.querySelectorAll('input[type=radio]')) (g[r.name] ||= []).push(r);
  return Object.values(g)
    .map((arr) => {
      const opts = arr.map(lbl);
      let c = arr[0];
      const len = opts.join('').length + 20;
      while (c && !(c.innerText && c.innerText.length > len)) c = c.parentElement;
      const q = (c?.innerText || '').replace(/\s+/g, ' ').replace(/ (Learn more|Please note).*$/, '');
      return { arr, opts, q };
    })
    .filter((g) => g.opts.every((o) => o));
};
window.answerIarc = async (yes = /$^/) => {
  const log = [];
  for (let k = 0; k < 40; k++) {
    const g = iarcGroups().find((g) => !g.arr.some((a) => a.checked));
    if (!g) break;
    const want = yes.test(g.q) ? 'Yes' : 'No';
    const i = g.opts.indexOf(want);
    if (i < 0) {
      log.push(`STOP (${g.opts.join('/')}) ${g.q.slice(0, 160)}`);
      break;
    }
    g.arr[i].click();
    log.push(`${want}: ${g.q.slice(0, 140)}`);
    await new Promise((r) => setTimeout(r, 900));
  }
  return log.join('\n');
};
'play_forms ready';
