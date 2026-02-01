import React from 'react';
import { motion } from 'framer-motion';
import { Button } from './ui/button';
import { 
  UtensilsCrossed, 
  CalendarDays, 
  ShoppingCart, 
  Search,
  Plus,
  Sparkles
} from 'lucide-react';

const icons = {
  recipes: UtensilsCrossed,
  mealPlan: CalendarDays,
  shopping: ShoppingCart,
  search: Search,
  default: Sparkles
};

export const EmptyState = ({ 
  type = 'default',
  title,
  description,
  actionLabel,
  onAction,
  icon: CustomIcon
}) => {
  const Icon = CustomIcon || icons[type] || icons.default;
  
  const defaults = {
    recipes: {
      title: 'No recipes yet',
      description: 'Start building your collection by adding your first recipe.',
      actionLabel: 'Add Recipe'
    },
    mealPlan: {
      title: 'No meals planned',
      description: 'Plan your meals for the week to stay organized.',
      actionLabel: 'Plan Meals'
    },
    shopping: {
      title: 'Shopping list is empty',
      description: 'Add items manually or generate from your meal plan.',
      actionLabel: 'Add Items'
    },
    search: {
      title: 'No results found',
      description: 'Try adjusting your search or filters.',
      actionLabel: null
    },
    default: {
      title: 'Nothing here yet',
      description: 'Get started by adding some content.',
      actionLabel: 'Get Started'
    }
  };

  const config = defaults[type] || defaults.default;
  const displayTitle = title || config.title;
  const displayDescription = description || config.description;
  const displayActionLabel = actionLabel !== undefined ? actionLabel : config.actionLabel;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col items-center justify-center py-16 px-4 text-center"
    >
      <div className="w-20 h-20 rounded-2xl bg-cream-subtle flex items-center justify-center mb-6">
        <Icon className="w-10 h-10 text-muted-foreground" />
      </div>
      
      <h3 className="font-heading text-xl font-semibold mb-2">
        {displayTitle}
      </h3>
      
      <p className="text-muted-foreground max-w-sm mb-6">
        {displayDescription}
      </p>
      
      {displayActionLabel && onAction && (
        <Button 
          onClick={onAction}
          className="rounded-full bg-mise hover:bg-mise-dark"
        >
          <Plus className="w-4 h-4 mr-2" />
          {displayActionLabel}
        </Button>
      )}
    </motion.div>
  );
};
