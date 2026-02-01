import React from 'react';
import { Link } from 'react-router-dom';
import { Clock, Users, Utensils } from 'lucide-react';
import { cn } from '../lib/utils';
import { Badge } from './ui/badge';

// Helper to get image URL (mirrors the logic in lib/utils if available)
const getImageUrl = (url: string) => {
  if (!url) return 'https://images.unsplash.com/photo-1495195129352-aec325b55b65?auto=format&fit=crop&q=80&w=800';
  if (url.startsWith('http')) return url;
  return `https://mise-recipe.live.blink.new/storage/${url}`; // Assuming fallback
};

const formatTime = (minutes: number) => {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};

export const RecipeCard: React.FC<{ recipe: any }> = ({ recipe }) => {
  const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);

  return (
    <Link
      to={`/recipes/${recipe.id}`}
      className="group block active:scale-[0.98] transition-transform duration-200"
      data-testid={`recipe-card-${recipe.id}`}
    >
      <article className="bg-surface-container-low rounded-[2rem] overflow-hidden border border-border/10 transition-all duration-300 hover:bg-surface-container hover:shadow-lg">
        {/* Image */}
        <div className="relative aspect-[16/10] overflow-hidden m-2 rounded-[1.5rem]">
          <img
            src={getImageUrl(recipe.image_url)}
            alt={recipe.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-60" />
          
          {/* Category Badge - Material 3 Tonal style */}
          {recipe.category && (
            <div className="absolute top-3 left-3 bg-white/20 backdrop-blur-md text-white text-[11px] font-bold px-3 py-1 rounded-full uppercase tracking-wider">
              {recipe.category}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-5 pt-2">
          <h3 className="font-heading font-semibold text-lg text-foreground line-clamp-1 group-hover:text-primary transition-colors">
            {recipe.title}
          </h3>
          
          {recipe.description && (
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2 leading-relaxed">
              {recipe.description}
            </p>
          )}

          {/* Meta & Stats */}
          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center gap-3 text-xs font-medium text-muted-foreground">
              {totalTime > 0 && (
                <span className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded-lg">
                  <Clock className="w-3.5 h-3.5" />
                  {formatTime(totalTime)}
                </span>
              )}
              {recipe.servings > 0 && (
                <span className="flex items-center gap-1.5 bg-muted/50 px-2 py-1 rounded-lg">
                  <Users className="w-3.5 h-3.5" />
                  {recipe.servings}
                </span>
              )}
            </div>
            
            <div className="flex gap-1.5">
               {recipe.tags?.slice(0, 1).map((tag: string, idx: number) => (
                  <span key={idx} className="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">
                    #{tag}
                  </span>
               ))}
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
};
