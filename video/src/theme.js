export const W = 1920;
export const H = 1080;
export const FPS = 30;

// Editorial "paper" palette, matched to the show's LinkedIn motion graphics.
export const C = {
  paper: '#EEE3DE',   // background
  paper2: '#E6D9D3',  // panels, empty bar tracks
  band: '#DDD1CB',    // highlight bands (e.g. "peak season")
  grid: '#D6C9C3',    // gridlines, rules
  ink: '#17434B',     // headlines, primary data (dark teal)
  text: '#2B2523',    // body text
  sub: '#4B4441',     // secondary text
  muted: '#8C837F',   // axis labels, footnotes
  orange: '#E8562A',  // accent: the number that hurts, alerts
  blue: '#2B8CB8',    // second series
  sage: '#A7BCB6',    // neutral data (demand bars)
  sand: '#EECF91',    // areas, excess
  salmon: '#D98A72',  // soft warning fills
  // Older names the templates use, mapped onto the paper palette:
  white: '#17434B',
  amber: '#E8562A',
  teal: '#2B8CB8',
  red: '#E8562A',
  line: '#D6C9C3',
  ink2: '#E6D9D3',
  ink3: '#DDD1CB',
};

export const FONT = "'Lato', 'Inter', system-ui, sans-serif";       // body, labels
export const HEAD = "'Arimo', 'Arial', 'Helvetica', sans-serif";   // headlines and big numbers

export const SEGMENT_LABELS = {
  cold_open: 'Top story',
  welcome: 'This week',
  lead_stories: 'Lead stories',
  ai_tech: 'AI & tech',
  nordics_dach: 'Nordics & DACH',
  market_moves: 'Market moves',
  use_cases: 'Use cases',
  macro: 'Macro & trade',
  numbers: 'The numbers',
  events_ahead: 'Events ahead',
  quick_hits: 'Quick hits',
  top_story: 'Top story',
  briefing: 'The briefing',
  week_threads: "The week's threads",
  voices: 'Expert voices',
  week_ahead: 'The week ahead',
  sign_off: 'Sign-off',
  book_open: 'Book of the week',
  book_intro: "Today's book",
  book_context: 'The book',
  big_ideas: 'The big ideas',
  for_planners: 'Why it matters now',
  reading_guide: 'How to read it',
  shelf: 'Also on the shelf',
  book_sign_off: 'Sign-off',
};

export const segmentLabel = (id) =>
  SEGMENT_LABELS[id] || (id || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase());

export const fmt = (v, decimals = 0) =>
  Number(v).toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals});
