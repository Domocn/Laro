import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChefHat,
  Clock,
  Users,
  Printer,
  Share2,
  Loader2,
  AlertCircle,
  Utensils,
  Timer,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  MessageCircle,
  ExternalLink
} from 'lucide-react';
import { Button } from '../components/ui/button';
import api from '../lib/api';
import { toast } from 'sonner';

// WhatsApp icon component
const WhatsAppIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
  </svg>
);

export const SharedRecipe = () => {
  const { shareCode } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [showFullRecipe, setShowFullRecipe] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadSharedRecipe();
  }, [shareCode]);

  const loadSharedRecipe = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get(`/share/recipe/${shareCode}`);
      setData(res.data);
    } catch (err) {
      if (err.response?.status === 404) {
        setError('This share link is invalid or has been revoked.');
      } else if (err.response?.status === 410) {
        setError('This share link has expired.');
      } else {
        setError('Failed to load recipe. Please try again later.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePrint = () => {
    setShowFullRecipe(true);
    setTimeout(() => window.print(), 100);
  };

  const handleCopyLink = async () => {
    const url = window.location.href;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success('Link copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      toast.error('Failed to copy link');
    }
  };

  const handleShare = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({
          title: data.recipe.title,
          text: `Check out this recipe: ${data.recipe.title}`,
          url: url,
        });
      } catch (err) {
        // User cancelled or error
      }
    } else {
      handleCopyLink();
    }
  };

  const handleWhatsAppShare = () => {
    const recipe = data.recipe;
    const url = window.location.href;
    const includeLinks = data.include_links_in_share !== false;

    // Format all ingredients
    const allIngredients = recipe.ingredients
      ?.map((ing, i) => `${i + 1}. ${typeof ing === 'string' ? ing : ing.text || ing.name}`)
      .join('\n');

    // Format all instructions
    const allInstructions = recipe.instructions
      ?.map((step, i) => `${i + 1}. ${typeof step === 'string' ? step : step.text || step.instruction}`)
      .join('\n\n');

    // Build time info line
    const timeInfo = [
      recipe.prep_time ? `⏱️ Prep: ${recipe.prep_time}` : '',
      recipe.cook_time ? `🍳 Cook: ${recipe.cook_time}` : '',
      recipe.servings ? `👥 Serves ${recipe.servings}` : ''
    ].filter(Boolean).join(' | ');

    // Create full recipe message
    let message = `🍳 *${recipe.title}*

${recipe.description ? `${recipe.description}\n\n` : ''}${timeInfo ? `${timeInfo}\n\n` : ''}📝 *Ingredients:*
${allIngredients || 'No ingredients listed'}

👨‍🍳 *Instructions:*
${allInstructions || 'No instructions listed'}`;

    // Add link if enabled
    if (includeLinks) {
      message += `\n\n👉 View online: ${url}`;
    }

    message += `\n\n_Shared via Laro_`;

    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-cream dark:bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-10 h-10 animate-spin text-mise mx-auto mb-4" />
          <p className="text-muted-foreground">Loading recipe...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-cream dark:bg-background flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
          </div>
          <h1 className="font-heading text-2xl font-bold mb-2">Recipe Not Found</h1>
          <p className="text-muted-foreground mb-6">{error}</p>
          <Link to="/">
            <Button className="rounded-full bg-mise hover:bg-mise-dark">
              <ChefHat className="w-4 h-4 mr-2" />
              Go to Laro
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  const recipe = data.recipe;
  const author = data.author;

  return (
    <div className="min-h-screen bg-gradient-to-b from-cream to-cream-subtle dark:from-background dark:to-muted/20">
      {/* Minimal Header - Only visible on scroll or full view */}
      <header className="bg-white/80 dark:bg-card/80 backdrop-blur-md border-b border-border/40 sticky top-0 z-40 print:hidden">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link to="/" className="flex items-center hover:opacity-80 transition-opacity">
            <img src="/mise-banner.svg" alt="Laro" className="h-9" />
          </Link>

          <div className="flex items-center gap-2">
            {data.allow_print && (
              <Button variant="ghost" size="sm" onClick={handlePrint} className="rounded-full">
                <Printer className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-lg mx-auto px-4 py-6 sm:py-10">
        {/* Recipe Card - Default View */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-card rounded-3xl border border-border/40 overflow-hidden shadow-xl"
        >
          {/* Hero Image */}
          <div className="relative aspect-[4/3] overflow-hidden bg-gradient-to-br from-mise/20 to-mise/5">
            {recipe.image_url ? (
              <img
                src={recipe.image_url}
                alt={recipe.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <ChefHat className="w-20 h-20 text-mise/30" />
              </div>
            )}

            {/* Gradient overlay */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />

            {/* Title on image */}
            <div className="absolute bottom-0 left-0 right-0 p-5 text-white">
              <h1 className="font-heading text-2xl sm:text-3xl font-bold leading-tight drop-shadow-lg">
                {recipe.title}
              </h1>
              {author && (
                <p className="text-white/80 text-sm mt-1 drop-shadow">
                  by {author.name}
                </p>
              )}
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-3 border-b border-border/40">
            <div className="flex flex-col items-center justify-center py-4 border-r border-border/40">
              <Clock className="w-5 h-5 text-mise mb-1" />
              <span className="text-xs text-muted-foreground">Prep</span>
              <span className="font-semibold text-sm">{recipe.prep_time || '-'}</span>
            </div>
            <div className="flex flex-col items-center justify-center py-4 border-r border-border/40">
              <Timer className="w-5 h-5 text-mise mb-1" />
              <span className="text-xs text-muted-foreground">Cook</span>
              <span className="font-semibold text-sm">{recipe.cook_time || '-'}</span>
            </div>
            <div className="flex flex-col items-center justify-center py-4">
              <Users className="w-5 h-5 text-mise mb-1" />
              <span className="text-xs text-muted-foreground">Serves</span>
              <span className="font-semibold text-sm">{recipe.servings || '-'}</span>
            </div>
          </div>

          {/* Description */}
          {recipe.description && (
            <div className="px-5 py-4 border-b border-border/40">
              <p className="text-muted-foreground text-sm leading-relaxed">
                {recipe.description}
              </p>
            </div>
          )}

          {/* Tags */}
          {recipe.tags && recipe.tags.length > 0 && (
            <div className="px-5 py-3 border-b border-border/40">
              <div className="flex flex-wrap gap-2">
                {recipe.tags.map((tag, index) => (
                  <span
                    key={`${tag}-${index}`}
                    className="px-3 py-1 bg-mise/10 text-mise text-xs font-medium rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Share Actions */}
          <div className="p-5 space-y-3 print:hidden">
            {/* WhatsApp Share - Primary Action */}
            <Button
              onClick={handleWhatsAppShare}
              className="w-full rounded-xl bg-[#25D366] hover:bg-[#20BD5A] text-white h-12 text-base font-semibold"
            >
              <WhatsAppIcon className="w-5 h-5 mr-2" />
              Share on WhatsApp
            </Button>

            {/* Secondary Actions */}
            <div className="grid grid-cols-2 gap-3">
              <Button
                variant="outline"
                onClick={handleCopyLink}
                className="rounded-xl h-11"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4 mr-2 text-green-500" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Link
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                onClick={handleShare}
                className="rounded-xl h-11"
              >
                <Share2 className="w-4 h-4 mr-2" />
                Share
              </Button>
            </div>

            {/* View Full Recipe Toggle */}
            <Button
              variant="ghost"
              onClick={() => setShowFullRecipe(!showFullRecipe)}
              className="w-full rounded-xl text-mise hover:text-mise-dark hover:bg-mise/5"
            >
              {showFullRecipe ? (
                <>
                  <ChevronUp className="w-4 h-4 mr-2" />
                  Hide Full Recipe
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4 mr-2" />
                  View Full Recipe
                </>
              )}
            </Button>
          </div>

          {/* Full Recipe - Expandable */}
          <AnimatePresence>
            {showFullRecipe && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3 }}
                className="overflow-hidden border-t border-border/40"
              >
                <div className="p-5 space-y-6">
                  {/* Ingredients */}
                  <section>
                    <h2 className="font-heading text-lg font-semibold mb-3 flex items-center gap-2">
                      <span className="w-7 h-7 bg-mise/10 rounded-lg flex items-center justify-center text-mise text-sm">📝</span>
                      Ingredients
                    </h2>
                    <ul className="space-y-2">
                      {recipe.ingredients?.map((ingredient, index) => (
                        <li key={`ingredient-${index}`} className="flex items-start gap-3 text-sm">
                          <span className="w-5 h-5 bg-cream-subtle dark:bg-muted rounded flex-shrink-0 flex items-center justify-center text-xs font-medium">
                            {index + 1}
                          </span>
                          <span>{typeof ingredient === 'string' ? ingredient : ingredient.text || ingredient.name}</span>
                        </li>
                      ))}
                    </ul>
                  </section>

                  {/* Instructions */}
                  <section>
                    <h2 className="font-heading text-lg font-semibold mb-3 flex items-center gap-2">
                      <span className="w-7 h-7 bg-mise/10 rounded-lg flex items-center justify-center text-mise text-sm">👨‍🍳</span>
                      Instructions
                    </h2>
                    <ol className="space-y-4">
                      {recipe.instructions?.map((step, index) => (
                        <li key={`instruction-${index}`} className="flex gap-3">
                          <span className="w-6 h-6 bg-mise text-white rounded-full flex-shrink-0 flex items-center justify-center text-sm font-medium">
                            {index + 1}
                          </span>
                          <p className="text-sm leading-relaxed pt-0.5">
                            {typeof step === 'string' ? step : step.text || step.instruction}
                          </p>
                        </li>
                      ))}
                    </ol>
                  </section>

                  {/* Nutrition (if available) */}
                  {recipe.nutrition && Object.keys(recipe.nutrition).length > 0 && (
                    <section>
                      <h2 className="font-heading text-lg font-semibold mb-3">Nutrition</h2>
                      <div className="grid grid-cols-4 gap-2">
                        {recipe.nutrition.calories && (
                          <div className="text-center p-2 bg-cream-subtle dark:bg-muted rounded-xl">
                            <p className="text-lg font-bold text-mise">{recipe.nutrition.calories}</p>
                            <p className="text-xs text-muted-foreground">cal</p>
                          </div>
                        )}
                        {recipe.nutrition.protein && (
                          <div className="text-center p-2 bg-cream-subtle dark:bg-muted rounded-xl">
                            <p className="text-lg font-bold text-mise">{recipe.nutrition.protein}g</p>
                            <p className="text-xs text-muted-foreground">protein</p>
                          </div>
                        )}
                        {recipe.nutrition.carbs && (
                          <div className="text-center p-2 bg-cream-subtle dark:bg-muted rounded-xl">
                            <p className="text-lg font-bold text-mise">{recipe.nutrition.carbs}g</p>
                            <p className="text-xs text-muted-foreground">carbs</p>
                          </div>
                        )}
                        {recipe.nutrition.fat && (
                          <div className="text-center p-2 bg-cream-subtle dark:bg-muted rounded-xl">
                            <p className="text-lg font-bold text-mise">{recipe.nutrition.fat}g</p>
                            <p className="text-xs text-muted-foreground">fat</p>
                          </div>
                        )}
                      </div>
                    </section>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* CTA Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mt-6 bg-gradient-to-br from-mise to-mise-dark rounded-2xl p-6 text-white text-center print:hidden"
        >
          <ChefHat className="w-10 h-10 mx-auto mb-3 opacity-90" />
          <h3 className="font-heading text-xl font-bold mb-2">
            Love this recipe?
          </h3>
          <p className="text-white/80 text-sm mb-4">
            Join Laro to save, organize, and share your favorite recipes. It's free!
          </p>
          <Link to="/register">
            <Button className="rounded-full bg-white text-mise hover:bg-cream font-semibold px-6">
              <ExternalLink className="w-4 h-4 mr-2" />
              Join Laro for Free
            </Button>
          </Link>
        </motion.div>

        {/* Footer */}
        <div className="mt-6 text-center text-xs text-muted-foreground print:hidden">
          <p>Shared via <Link to="/" className="text-mise hover:underline">Laro</Link> - Your Personal Recipe Manager</p>
        </div>
      </main>

      {/* Print Styles */}
      <style>{`
        @media print {
          body { background: white !important; }
          header, .print\\:hidden { display: none !important; }
          main { padding: 0 !important; max-width: 100% !important; }
          .rounded-3xl { border-radius: 0 !important; }
          .shadow-xl { box-shadow: none !important; }
        }
      `}</style>
    </div>
  );
};

export default SharedRecipe;
