// Estimate when words are spoken inside a line, and when list items are mentioned.

const norm = (s) => (s || '').toLowerCase().replace(/[^a-z0-9äöåüéæø ]+/g, ' ').replace(/\s+/g, ' ').trim();

// Time (seconds) at which character index `ci` of line `l` is spoken, assuming even pace.
export const charTime = (l, ci) => l.start_sec + (l.duration_sec * ci) / Math.max(1, l.text.length);

// For each item, the second at which the hosts first mention it within the scene's lines.
// Items with a `say` field are matched on that, otherwise on the label, then the detail's first words.
// Unmatched items are spread evenly between their neighbours.
export const mentionTimes = (items, lines, from, to) => {
  const found = items.map((it) => {
    const keys = [it.say, it.label, (it.detail || '').split(' ').slice(0, 3).join(' ')].map(norm).filter((k) => k.length >= 2);
    for (const l of lines) {
      const text = norm(l.text);
      for (const k of keys) {
        const idx = text.indexOf(k);
        if (idx >= 0) return charTime(l, Math.round((idx / Math.max(1, text.length)) * l.text.length));
      }
    }
    return null;
  });
  // Keep times increasing; fill gaps evenly.
  const n = items.length;
  const times = new Array(n).fill(null);
  let last = from;
  found.forEach((t, i) => { if (t !== null && t >= last) { times[i] = t; last = t; } });
  for (let i = 0; i < n; i++) {
    if (times[i] !== null) continue;
    let j = i;
    while (j < n && times[j] === null) j++;
    const a = i === 0 ? from : times[i - 1];
    const b = j < n ? times[j] : to - (to - from) * 0.1;
    const steps = j - i + 1;
    for (let k = i; k < j; k++) times[k] = a + ((b - a) * (k - i + 1)) / steps;
  }
  return times.map((t) => Math.max(from, Math.min(to, t)));
};

// Split a line into caption chunks of at most `maxWords`, breaking at punctuation where possible.
export const captionChunks = (line, maxWords = 11) => {
  const words = line.text.split(/\s+/).filter(Boolean);
  const chunks = [];
  let cur = [];
  words.forEach((w, i) => {
    cur.push(w);
    const punct = /[.,;:?!]$/.test(w);
    if (cur.length >= maxWords || (punct && cur.length >= 5) || i === words.length - 1) {
      chunks.push(cur);
      cur = [];
    }
  });
  let ci = 0;
  return chunks.map((ws) => {
    const text = ws.join(' ');
    const start = charTime(line, ci);
    const wordsT = [];
    let c = ci;
    ws.forEach((w) => { wordsT.push({w, t: charTime(line, c)}); c += w.length + 1; });
    ci += text.length + 1;
    return {start, end: charTime(line, Math.min(line.text.length, ci)), words: wordsT};
  });
};
