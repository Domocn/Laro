import React, { memo } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Users, Heart } from 'lucide-react';
import { getImageUrl, formatTime } from '../lib/utils';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';

export const RecipeCard = memo(({
  recipe,
  selectMode = false,
  selected = false,
  selectable = true,
  onToggleSelect,
}) => {
  const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);

  const card = (
    <article
      className={`bg-white rounded-[12px] overflow-hidden shadow-card transition-all duration-200 ${
        selectMode
          ? selected
            ? 'ring-2 ring-laro/40'
            : ''
          : 'hover:shadow-hover'
      } ${selectMode && !selectable ? 'opacity-50' : ''}`}
    >
      {/* Image */}
      <div className="relative aspect-[4/3] overflow-hidden">
        <img
          src={getImageUrl(recipe.image_url, recipe)}
          alt={recipe.title}
          loading="lazy"
          decoding="async"
          className={`w-full h-full object-cover transition-transform duration-500 ${
            selectMode ? '' : 'group-hover:scale-105'
          }`}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />

        {selectMode && selectable && (
          <div
            className="absolute top-3 left-3 z-10"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onToggleSelect?.(recipe.id);
            }}
          >
            <Checkbox
              checked={selected}
              onCheckedChange={() => onToggleSelect?.(recipe.id)}
              aria-label={`Select ${recipe.title}`}
              className="bg-white/95 border-border shadow-sm dark:bg-white dark:text-[#1E3932] dark:shadow-md"
              data-testid={`recipe-select-${recipe.id}`}
            />
          </div>
        )}

        {/* Category Badge */}
        <Badge
          variant="secondary"
          className={`absolute top-3 ${selectMode && selectable ? 'left-12' : 'left-3'} bg-white/90 text-foreground backdrop-blur-sm font-semibold dark:bg-black/80 dark:text-cream dark:border dark:border-white/70 dark:shadow-md`}
        >
          {recipe.category}
        </Badge>
        {(recipe.tags || []).some((t) => String(t).toLowerCase() === 'needs-review') && (
          <Badge className="absolute top-3 right-3 bg-amber-500 text-white border-0">
            Review
          </Badge>
        )}
      </div>

      {/* Content */}
      <div className="p-4 sm:p-5">
        <h3 className={`font-heading font-semibold text-lg tracking-tighter text-laro-brand line-clamp-1 ${selectMode ? '' : 'group-hover:text-laro'} transition-colors`}>
          {recipe.title}
        </h3>

        {recipe.description && (
          <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
            {recipe.description}
          </p>
        )}

        {/* Meta */}
        <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
          {totalTime > 0 && (
            <span className="flex items-center gap-1.5">
              <Clock className="w-4 h-4" />
              {formatTime(totalTime)}
            </span>
          )}
          {recipe.servings > 0 && (
            <span className="flex items-center gap-1.5">
              <Users className="w-4 h-4" />
              {recipe.servings} servings
            </span>
          )}
        </div>

        {/* Tags */}
        {recipe.tags && recipe.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {recipe.tags.slice(0, 3).map((tag, idx) => (
              <span
                key={`${tag}-${idx}`}
                className="px-2 py-0.5 text-xs rounded-full bg-laro-light text-laro"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );

  if (selectMode) {
    return (
      <div
        role="button"
        tabIndex={selectable ? 0 : -1}
        className="block cursor-pointer"
        data-testid={`recipe-card-${recipe.id}`}
        onClick={() => {
          if (selectable) onToggleSelect?.(recipe.id);
        }}
        onKeyDown={(e) => {
          if (!selectable) return;
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleSelect?.(recipe.id);
          }
        }}
      >
        {card}
      </div>
    );
  }

  return (
    <Link
      to={`/recipes/${recipe.id}`}
      className="group block"
      data-testid={`recipe-card-${recipe.id}`}
    >
      {card}
    </Link>
  );
});

RecipeCard.displayName = 'RecipeCard';
