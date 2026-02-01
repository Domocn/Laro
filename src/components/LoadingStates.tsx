import React from 'react';
import { Loader2, ChefHat } from 'lucide-react';
import { motion } from 'framer-motion';

export const LoadingSpinner = ({ size = 'md', className = '' }) => {
  const sizes = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12'
  };

  return (
    <Loader2 className={`animate-spin text-mise ${sizes[size]} ${className}`} />
  );
};

export const PageLoader = ({ message = 'Loading...' }) => {
  return (
    <div className="min-h-[50vh] flex flex-col items-center justify-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="flex flex-col items-center gap-4"
      >
        <div className="relative">
          <div className="w-16 h-16 rounded-2xl bg-mise-light flex items-center justify-center">
            <ChefHat className="w-8 h-8 text-mise" />
          </div>
          <div className="absolute -bottom-1 -right-1">
            <LoadingSpinner size="sm" />
          </div>
        </div>
        <p className="text-muted-foreground text-sm">{message}</p>
      </motion.div>
    </div>
  );
};

export const CardSkeleton = () => {
  return (
    <div className="bg-white rounded-2xl border border-border/60 overflow-hidden animate-pulse">
      <div className="aspect-[4/3] bg-cream-subtle" />
      <div className="p-4 space-y-3">
        <div className="h-5 bg-cream-subtle rounded w-3/4" />
        <div className="h-4 bg-cream-subtle rounded w-1/2" />
        <div className="flex gap-2">
          <div className="h-6 bg-cream-subtle rounded-full w-16" />
          <div className="h-6 bg-cream-subtle rounded-full w-20" />
        </div>
      </div>
    </div>
  );
};

export const RecipeGridSkeleton = ({ count = 6 }) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <CardSkeleton key={i} />
      ))}
    </div>
  );
};

export const ListSkeleton = ({ count = 5 }) => {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 bg-white rounded-xl border border-border/60 animate-pulse">
          <div className="w-12 h-12 rounded-xl bg-cream-subtle" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-cream-subtle rounded w-1/3" />
            <div className="h-3 bg-cream-subtle rounded w-1/2" />
          </div>
        </div>
      ))}
    </div>
  );
};

export const FormSkeleton = () => {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="space-y-2">
        <div className="h-4 bg-cream-subtle rounded w-20" />
        <div className="h-10 bg-cream-subtle rounded-xl" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-cream-subtle rounded w-24" />
        <div className="h-24 bg-cream-subtle rounded-xl" />
      </div>
      <div className="h-10 bg-cream-subtle rounded-full w-32" />
    </div>
  );
};
