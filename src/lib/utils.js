import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatTime(minutes) {
  if (!minutes) return '0 min';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

export function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function getImageUrl(url) {
  if (!url) return 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80';
  if (url.startsWith('http')) return url;
  // Use dynamic server URL from localStorage (same logic as api.js)
  const serverUrl = localStorage.getItem('laro_server_url') || process.env.REACT_APP_BACKEND_URL || '';
  return `${serverUrl}${url}`;
}

export const MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snack'];

export const CATEGORIES = [
  'All', 'Breakfast', 'Lunch', 'Dinner', 
  'Dessert', 'Appetizer', 'Snack', 'Beverage', 'Other'
];
