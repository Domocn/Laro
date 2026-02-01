import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const CATEGORIES = [
  'All',
  'Breakfast',
  'Lunch',
  'Dinner',
  'Dessert',
  'Appetizer',
  'Side Dish',
  'Beverage',
  'Snack',
  'Other'
];

export const MEAL_TYPES = [
  'Breakfast',
  'Lunch',
  'Dinner',
  'Snack'
];

export const getImageUrl = (url: string | null | undefined) => {
  if (!url) return '/mise-logo.png';
  if (url.startsWith('http')) return url;
  
  // Handle relative URLs if any
  const serverUrl = localStorage.getItem('mise_server_url') || '';
  if (serverUrl) {
    return `${serverUrl.replace(/\/$/, '')}${url.startsWith('/') ? '' : '/'}${url}`;
  }
  
  return url;
};

export const formatTime = (minutes: number) => {
  if (!minutes) return '0 min';
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};
