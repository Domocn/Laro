/**
 * Ingredient sections ("For the sauce", "For the topping").
 *
 * An ingredient carries an optional `group` (its section). Imported cookbooks used to label
 * sub-recipe lines with a prefix instead, e.g. "Basil Pesto: almonds or cashews"; that is
 * split into a group and the ingredient itself so the list reads "For the basil pesto" →
 * "almonds or cashews". Same rule as the backend (backend/utils/ingredient_groups.py).
 */
const GROUP_RE = /^([A-Za-z][^:\d]{1,40}?):\s+(\S.*)$/;

export function splitIngredientGroup(name) {
  const m = GROUP_RE.exec(String(name || ''));
  if (!m) return { group: null, name };
  return { group: m[1].trim(), name: m[2] };
}

const cleanGroup = (g) => String(g ?? '').replace(/\s+/g, ' ').replace(/:\s*$/, '').trim().slice(0, 80);

/**
 * { group, name } for an ingredient (object or plain string): its `group` when set, else a
 * legacy "Sauce: tahini" name prefix. `group` is null for ungrouped lines.
 */
export function ingredientParts(ing) {
  if (ing == null) return { group: null, name: '' };
  if (typeof ing === 'string') return splitIngredientGroup(ing);
  const name = String(ing.name ?? '');
  const group = cleanGroup(ing.group);
  if (!group) return splitIngredientGroup(name);
  const split = splitIngredientGroup(name);
  // "Sauce: tahini" saved inside section "Sauce": drop the repeated prefix.
  if (split.group && split.group.toLowerCase() === group.toLowerCase()) return { group, name: split.name };
  return { group, name };
}

/** The ingredient with `group` set and a clean name (only objects; strings come back as-is). */
export function withIngredientGroup(ing) {
  if (!ing || typeof ing !== 'object') return ing;
  const { group, name } = ingredientParts(ing);
  const out = { ...ing, name };
  if (group) out.group = group;
  else delete out.group;
  return out;
}

/**
 * Display rows: ungrouped lines first, then each section in the order it first appears. Each
 * row keeps the line's original `index` (line macros and edits are index-aligned) and marks
 * `groupStart` on the first line of a section.
 */
export function groupedRows(list) {
  const rows = (list || []).map((ing, index) => ({ ing, index, ...ingredientParts(ing) }));
  const order = [];
  const sections = new Map();
  for (const row of rows) {
    const key = row.group ? row.group.toLowerCase() : '';
    if (!sections.has(key)) {
      sections.set(key, []);
      if (key) order.push(key);
    }
    sections.get(key).push(row);
  }
  const out = [...(sections.get('') || [])].map((r) => ({ ...r, groupStart: false }));
  for (const key of order) {
    sections.get(key).forEach((r, i) => out.push({ ...r, groupStart: i === 0 }));
  }
  return out;
}

/**
 * "Basil Pesto" → "For the basil pesto"; keeps headings that already read well. Pass the
 * i18n `t` to translate (key `ingredientGroupHeading`: "For the {group}" in English, where
 * {group} is lower-cased; other languages can use {Group}, the name as written).
 */
export function groupHeading(group, t) {
  const g = String(group || '').trim();
  if (/^for\b/i.test(g)) return g;
  const lower = g.toLowerCase();
  if (typeof t === 'function') {
    const text = t('ingredientGroupHeading', { group: lower, Group: g });
    if (text && text !== 'ingredientGroupHeading') return text;
  }
  return `For the ${lower}`;
}

// ---- Recipe editor: rows carry a `sectionId`; sections are [{ id, name }] in display order ----

let sectionSeq = 0;
const newSectionId = () => `section-${Date.now().toString(36)}-${(sectionSeq += 1)}`;

/** Saved ingredients -> editor state. Sections in first-seen order; rows keep their order. */
export function toEditorSections(list, makeId = newSectionId) {
  const sections = [];
  const byKey = new Map();
  const rows = (list || []).map((ing) => {
    const obj = typeof ing === 'string' ? { name: ing, amount: '', unit: '' } : { ...ing };
    const { group, name } = ingredientParts(obj);
    delete obj.group;
    let sectionId = null;
    if (group) {
      const key = group.toLowerCase();
      if (!byKey.has(key)) {
        const section = { id: makeId(), name: group };
        byKey.set(key, section);
        sections.push(section);
      }
      sectionId = byKey.get(key).id;
    }
    return { ...obj, name, sectionId };
  });
  return { rows, sections };
}

/** A new, unnamed section at the end with one empty ingredient row in it. */
export function addEditorSection(state, emptyRow, makeId = newSectionId) {
  const section = { id: makeId(), name: '' };
  return {
    rows: [...state.rows, { ...emptyRow, sectionId: section.id }],
    sections: [...state.sections, section],
  };
}

export function renameEditorSection(state, id, name) {
  return { ...state, sections: state.sections.map((s) => (s.id === id ? { ...s, name } : s)) };
}

/** Remove a section; its ingredients stay, moved to the end of the ungrouped list. */
export function removeEditorSection(state, id) {
  const moved = state.rows.filter((r) => r.sectionId === id).map((r) => ({ ...r, sectionId: null }));
  return {
    rows: [...state.rows.filter((r) => r.sectionId !== id), ...moved],
    sections: state.sections.filter((s) => s.id !== id),
  };
}

/** Move a section up (-1) or down (+1); no-op at the ends. */
export function moveEditorSection(state, id, delta) {
  const i = state.sections.findIndex((s) => s.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= state.sections.length) return state;
  const sections = [...state.sections];
  [sections[i], sections[j]] = [sections[j], sections[i]];
  return { ...state, sections };
}

/**
 * Editor state -> ingredients to save: ungrouped first, then each section in order with its
 * name as `group`. Lines in an unnamed section are saved ungrouped (nothing is lost).
 */
export function fromEditorSections(state) {
  const names = new Map(state.sections.map((s) => [s.id, cleanGroup(s.name)]));
  // eslint-disable-next-line no-unused-vars
  const plain = ({ sectionId, group, ...ing }) => ing;
  const out = state.rows.filter((r) => !names.get(r.sectionId)).map(plain);
  for (const s of state.sections) {
    const group = names.get(s.id);
    if (group) state.rows.filter((r) => r.sectionId === s.id).forEach((r) => out.push({ ...plain(r), group }));
  }
  return out;
}

// ---- One-ingredient-per-line text (import review, version editor) ----

const HEADING_LINE_RE = /^([A-Za-z][^:\d]{1,60}?):$/;

/**
 * Lines for a textarea: ungrouped lines first, then each section as a "Sauce:" line followed
 * by its ingredients. `lineOf(ing)` renders one ingredient.
 */
export function sectionedLines(list, lineOf) {
  const out = [];
  for (const row of groupedRows(list)) {
    if (row.groupStart) out.push(`${row.group}:`);
    const line = typeof row.ing === 'string'
      ? String(row.name || '').trim()
      : String(lineOf({ ...row.ing, name: row.name }) || '').trim();
    if (line) out.push(line);
  }
  return out;
}

/**
 * Textarea lines -> ingredients. A line that is only "Sauce:" starts a section for the lines
 * after it; "Sauce: 2 tbsp tahini" (the older single-line form) is that line in section "Sauce".
 * `parse(line)` turns one line into {amount, unit, name}.
 */
export function parseSectionedLines(lines, parse) {
  let current = null;
  const out = [];
  for (const raw of lines || []) {
    const line = String(raw || '').trim();
    if (!line) continue;
    const heading = HEADING_LINE_RE.exec(line);
    if (heading) {
      current = cleanGroup(heading[1]) || null;
      continue;
    }
    const split = splitIngredientGroup(line);
    const group = split.group || current;
    const ing = { ...parse(split.group ? split.name : line) };
    if (group) ing.group = cleanGroup(group);
    out.push(ing);
  }
  return out;
}

/**
 * Plain-text ingredient list with section headings, e.g. for copy / share:
 * "• 200 g pasta\n\nFor the pesto:\n• 75 g almonds".
 */
export function ingredientsAsText(list, t, bullet = '• ') {
  const lines = [];
  for (const row of groupedRows(list)) {
    if (row.groupStart) {
      if (lines.length) lines.push('');
      lines.push(`${groupHeading(row.group, t)}:`);
    }
    const ing = row.ing;
    const text = typeof ing === 'string'
      ? row.name
      : [ing.amount, ing.unit, row.name].map((x) => String(x ?? '').trim()).filter(Boolean).join(' ');
    if (text) lines.push(`${bullet}${text}`);
  }
  return lines.join('\n');
}
