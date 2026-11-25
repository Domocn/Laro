import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import en from '../locales/en';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const api = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  getOne: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  recipeApi: {
    getAll: () => Promise.resolve({ data: [] }),
    getOne: api.getOne,
    create: api.create,
    update: api.update,
    uploadImage: vi.fn(),
  },
  preferencesApi: { get: () => Promise.resolve({ data: {} }) },
}));
vi.mock('../context/LanguageContext', () => ({
  useLanguage: () => ({
    t: (k, p = {}) => Object.entries(p).reduce((s, [a, v]) => s.replaceAll(`{${a}}`, String(v)), en[k] || k),
  }),
}));
vi.mock('../components/Layout', () => ({ Layout: ({ children }) => <div>{children}</div> }));
vi.mock('../components/VetoReplacementBanner', () => ({ VetoReplacementBanner: () => null }));
vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));

const { RecipeForm } = await import('./RecipeForm');

async function render(path = '/recipes/new') {
  const el = document.createElement('div');
  document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => {
    root.render(
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/recipes/new" element={<RecipeForm />} />
          <Route path="/recipes/:id/edit" element={<RecipeForm />} />
          <Route path="/recipes/:id" element={<div>detail</div>} />
        </Routes>
      </MemoryRouter>,
    );
  });
  return el;
}

// React tracks input values; set through the native setter so onChange fires.
function type(input, value) {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(input), 'value').set;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

const q = (el, id) => el.querySelector(`[data-testid="${id}"]`);
const qa = (el, id) => [...el.querySelectorAll(`[data-testid="${id}"]`)];
const nameInputs = (scope) => [...scope.querySelectorAll(`input[placeholder="${en.ingredientNamePlaceholder}"]`)];

describe('RecipeForm ingredient sections', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    api.create.mockReset().mockResolvedValue({ data: { id: 'new1' } });
    api.update.mockReset().mockResolvedValue({ data: {} });
    api.getOne.mockReset();
  });

  it('adds, names and saves a section; ungrouped ingredients come first', async () => {
    const el = await render();
    await act(async () => type(q(el, 'recipe-title-input'), 'Pesto pasta'));
    await act(async () => type(nameInputs(q(el, 'ingredients-inputs'))[0], 'pasta'));

    await act(async () => q(el, 'add-ingredient-section').click());
    const section = q(el, 'ingredient-section');
    expect(section).not.toBeNull();
    expect(section.getAttribute('role')).toBe('group');
    expect(nameInputs(section)).toHaveLength(1); // starts with one empty row

    await act(async () => type(q(section, 'ingredient-section-name'), 'Basil Pesto'));
    expect(section.textContent).toContain('Shows as “For the basil pesto”');
    await act(async () => type(nameInputs(section)[0], 'almonds'));
    await act(async () => q(section, 'ingredient-section-add-ingredient').click());
    await act(async () => type(nameInputs(q(el, 'ingredient-section'))[1], 'basil'));

    await act(async () => type(el.querySelector('[data-testid="instructions-inputs"] textarea'), 'Blend and toss.'));
    await act(async () => q(el, 'save-recipe-btn').click());

    expect(api.create).toHaveBeenCalledTimes(1);
    const sent = api.create.mock.calls[0][0].ingredients;
    expect(sent.map((i) => [i.name, i.group])).toEqual([
      ['pasta', undefined],
      ['almonds', 'Basil Pesto'],
      ['basil', 'Basil Pesto'],
    ]);
    expect(sent.some((i) => 'sectionId' in i)).toBe(false);
  });

  it('loads sections from an existing recipe and removing one keeps its ingredients', async () => {
    api.getOne.mockResolvedValue({
      data: {
        id: 'r1', title: 'Buns', category: 'Other', servings: 4, instructions: ['Bake.'],
        ingredients: [
          { name: 'flour', amount: '500', unit: 'g', group: 'Dough' },
          { name: 'Filling: cinnamon', amount: '2', unit: 'tsp' }, // legacy prefix
          { name: 'salt', amount: '1', unit: 'tsp' },
        ],
      },
    });
    const el = await render('/recipes/r1/edit');
    await act(async () => {});
    const sections = qa(el, 'ingredient-section');
    expect(sections.map((s) => q(s, 'ingredient-section-name').value)).toEqual(['Dough', 'Filling']);
    expect(nameInputs(sections[1]).map((i) => i.value)).toEqual(['cinnamon']);

    await act(async () => q(sections[0], 'ingredient-section-remove').click());
    expect(qa(el, 'ingredient-section')).toHaveLength(1);

    await act(async () => q(el, 'save-recipe-btn').click());
    const sent = api.update.mock.calls[0][1].ingredients;
    expect(sent.map((i) => [i.name, i.group])).toEqual([
      ['salt', undefined],
      ['flour', undefined],
      ['cinnamon', 'Filling'],
    ]);
  });
});
