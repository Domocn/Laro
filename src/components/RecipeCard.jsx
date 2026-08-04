import React, { memo } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Users, Heart } from 'lucide-react';
import { getImageUrl, formatTime } from '../lib/utils';
import { Badge } from './ui/badge';

export const RecipeCard = memo(({ recipe }) => {
  const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);

  return (
    <Link
      to={`/recipes/${recipe.id}`}
      className="group block"
      data-testid={`recipe-card-${recipe.id}`}
    >
      <article className="bg-white rounded-2xl border border-border/60 overflow-hidden shadow-soft hover:shadow-hover transition-all duration-300 hover:-translate-y-1">
        {/* Image */}
        <div className="relative aspect-[4/3] overflow-hidden">
          <img
            src={getImageUrl(recipe.image_url)}
            alt={recipe.title}
            loading="lazy"
            decoding="async"
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent" />
          
          {/* Category Badge */}
          <Badge 
            variant="secondary" 
            className="absolute top-3 left-3 bg-white/90 text-foreground backdrop-blur-sm"
          >
            {recipe.category}
          </Badge>
        </div>

        {/* Content */}
        <div className="p-4 sm:p-5">
          <h3 className="font-heading font-semibold text-lg text-foreground line-clamp-1 group-hover:text-laro transition-colors">
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
    </Link>
  );
});

RecipeCard.displayName = 'RecipeCard';
