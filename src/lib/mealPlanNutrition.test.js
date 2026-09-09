import {
  buildRepeatWeekPayloads,
  dayModeCues,
  nutritionStatus,
  recipeProteinGrams,
  resolveProteinTarget,
  rollupDayNutrition,
  suggestProteinSwaps,
  weekdayCodeFromDate,
} from './mealPlanNutrition';

describe('weekdayCodeFromDate', () => {
  it('maps Monday to mon', () => {
    expect(weekdayCodeFromDate(new Date('2026-09-07T12:00:00'))).toBe('mon');
  });
  it('maps Sunday to sun', () => {
    expect(weekdayCodeFromDate(new Date('2026-09-06T12:00:00'))).toBe('sun');
  });
});

describe('rollupDayNutrition', () => {
  const recipes = [
    { id: 'a', title: 'Chicken', nutrition: { protein: 45, calories: 400 } },
    { id: 'b', title: 'Salad', nutrition: { protein: 12, calories: 220 } },
    { id: 'c', title: 'No macros' },
  ];

  it('sums protein and calories across recipe meals', () => {
    const meals = [
      { id: '1', recipe_id: 'a', entry_type: 'recipe', meal_type: 'Lunch' },
      { id: '2', recipe_id: 'b', entry_type: 'recipe', meal_type: 'Dinner' },
      { id: '3', entry_type: 'note', recipe_title: 'Skip lunch' },
    ];
    const totals = rollupDayNutrition(meals, recipes);
    expect(totals.protein).toBe(57);
    expect(totals.calories).toBe(620);
    expect(totals.recipeMeals).toBe(2);
    expect(totals.hasAnyNutrition).toBe(true);
  });

  it('ignores notes and leftovers without recipe_id', () => {
    const totals = rollupDayNutrition(
      [{ id: '1', entry_type: 'leftover', recipe_title: 'Pizza' }],
      recipes
    );
    expect(totals.protein).toBe(0);
    expect(totals.hasAnyNutrition).toBe(false);
  });
});

describe('nutritionStatus', () => {
  it('is amber when under protein target', () => {
    const status = nutritionStatus(
      { protein: 80, calories: 1800, hasAnyNutrition: true },
      { proteinTarget: 140, calorieTarget: 2200 }
    );
    expect(status.protein).toBe('under');
    expect(status.overall).toBe('amber');
  });

  it('is green when protein target met', () => {
    const status = nutritionStatus(
      { protein: 145, calories: 2000, hasAnyNutrition: true },
      { proteinTarget: 140, calorieTarget: 2200 }
    );
    expect(status.protein).toBe('met');
    expect(status.overall).toBe('green');
  });
});

describe('suggestProteinSwaps', () => {
  it('suggests higher-protein recipes for under-target days', () => {
    const meals = [
      {
        id: 'm1',
        recipe_id: 'low',
        recipe_title: 'Pasta',
        entry_type: 'recipe',
        meal_type: 'Dinner',
      },
    ];
    const recipes = [
      { id: 'low', title: 'Pasta', nutrition: { protein: 20, calories: 600 } },
      { id: 'high', title: 'Steak', nutrition: { protein: 55, calories: 500 } },
      { id: 'mid', title: 'Tofu', nutrition: { protein: 35, calories: 400 } },
    ];
    const result = suggestProteinSwaps({
      meals,
      recipes,
      proteinTarget: 140,
      limit: 3,
    });
    expect(result.underTarget).toBe(true);
    expect(result.suggestions.length).toBeGreaterThan(0);
    expect(result.suggestions[0].recipeId).toBe('high');
    expect(result.suggestions[0].gain).toBe(35);
  });
});

describe('buildRepeatWeekPayloads', () => {
  it('shifts dates by 7 days and preserves recipe entries', () => {
    const payloads = buildRepeatWeekPayloads(
      [
        {
          date: '2026-09-07',
          meal_type: 'Dinner',
          entry_type: 'recipe',
          recipe_id: 'r1',
          recipe_title: 'Soup',
          notes: 'batch',
        },
        {
          date: '2026-09-08',
          meal_type: 'Lunch',
          entry_type: 'note',
          recipe_title: 'Out',
        },
      ],
      { dayOffset: 7 }
    );
    expect(payloads).toEqual([
      {
        date: '2026-09-14',
        meal_type: 'Dinner',
        entry_type: 'recipe',
        notes: 'batch',
        adult_boost: '',
        recipe_id: 'r1',
      },
      {
        date: '2026-09-15',
        meal_type: 'Lunch',
        entry_type: 'note',
        notes: '',
        adult_boost: '',
        recipe_title: 'Out',
      },
    ]);
  });
});

describe('dayModeCues', () => {
  it('flags WFH and gym days from preferences', () => {
    const mon = new Date('2026-09-07T12:00:00');
    const cues = dayModeCues(
      mon,
      {
        worksFromHome: true,
        wfhDays: ['mon', 'wed'],
        hasGymRoutine: true,
        gymDays: ['mon'],
        hasChildren: true,
        kidFriendlyMeals: true,
      },
      { level: 'busy' }
    );
    expect(cues.wfh).toBe(true);
    expect(cues.gym).toBe(true);
    expect(cues.kidNight).toBe(true);
    expect(cues.familyOneMeal).toBe(true);
    expect(cues.busyLevel).toBe('busy');
    expect(weekdayCodeFromDate(mon)).toBe('mon');
  });

  it('respects familyOneMeal off', () => {
    const mon = new Date('2026-09-07T12:00:00');
    const cues = dayModeCues(mon, {
      hasChildren: true,
      kidFriendlyMeals: true,
      familyOneMeal: false,
    });
    expect(cues.familyOneMeal).toBe(false);
    expect(cues.kidNight).toBe(true);
  });
});

describe('resolveProteinTarget', () => {
  it('uses explicit target then high-protein default', () => {
    expect(resolveProteinTarget({ dailyProteinTarget: 160 })).toBe(160);
    expect(
      resolveProteinTarget({ dietaryRestrictions: ['high-protein'] })
    ).toBe(140);
    expect(resolveProteinTarget({})).toBeNull();
  });

  it('reads recipe protein helpers', () => {
    expect(recipeProteinGrams({ nutrition: { protein: 30 } })).toBe(30);
    expect(recipeProteinGrams({ nutrition_protein: 22 })).toBe(22);
  });
});
