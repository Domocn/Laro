import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { CookMode } from '../components/CookMode';
import { NutritionCalculator } from '../components/NutritionCalculator';
import { RecipeVersions } from '../components/RecipeVersions';
import { RecipeReviews } from '../components/RecipeReviews';
import { CostCalculator } from '../components/CostCalculator';
import { useAuth } from '../context/AuthContext';
import { recipeApi, mealPlanApi, shoppingListApi, sharingApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Calendar } from '../components/ui/calendar';
import { Input } from '../components/ui/input';
import { getImageUrl, formatTime, MEAL_TYPES } from '../lib/utils';
import { 
  Clock, 
  Users, 
  Edit, 
  Trash2, 
  CalendarPlus, 
  ShoppingCart,
  ArrowLeft,
  ChefHat,
  Loader2,
  Share2,
  Copy,
  Check,
  Download,
  FileText,
  Link as LinkIcon,
  Image,
  Heart,
  Printer,
  Minus,
  Plus as PlusIcon,
  Play
} from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';

export const RecipeDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [showMealDialog, setShowMealDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [mealType, setMealType] = useState('Dinner');
  const [addingToMealPlan, setAddingToMealPlan] = useState(false);
  const [addingToShopping, setAddingToShopping] = useState(false);
  const [shareUrl, setShareUrl] = useState('');
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingCard, setGeneratingCard] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const [scaledServings, setScaledServings] = useState(null);
  const [scaledIngredients, setScaledIngredients] = useState(null);
  const [showCookMode, setShowCookMode] = useState(false);
  const recipeCardRef = useRef(null);

  // Generate formatted text for sharing
  const generateRecipeText = () => {
    if (!recipe) return '';
    
    let text = `🍳 ${recipe.title}\n`;
    text += `${'─'.repeat(30)}\n\n`;
    
    if (recipe.description) {
      text += `${recipe.description}\n\n`;
    }
    
    const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);
    text += `⏱️ ${formatTime(totalTime)} | 👥 ${recipe.servings} servings\n\n`;
    
    text += `📝 INGREDIENTS\n`;
    recipe.ingredients.forEach(ing => {
      text += `• ${ing.amount} ${ing.unit} ${ing.name}\n`;
    });
    
    text += `\n👨‍🍳 INSTRUCTIONS\n`;
    recipe.instructions.forEach((step, idx) => {
      text += `${idx + 1}. ${step}\n`;
    });
    
    text += `\n─────────────────────────────\n`;
    text += `Shared from Laro`;
    
    return text;
  };

  const handleCopyAsText = async () => {
    const text = generateRecipeText();
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Recipe copied as text!');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  const handleDownloadCard = async () => {
    setGeneratingCard(true);
    
    try {
      // Create a canvas to generate the recipe card
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // Card dimensions (Instagram story size for easy sharing)
      const width = 1080;
      const height = 1920;
      canvas.width = width;
      canvas.height = height;
      
      // Background
      ctx.fillStyle = '#FDFBF7';
      ctx.fillRect(0, 0, width, height);
      
      // Header background
      ctx.fillStyle = '#4A6741';
      ctx.fillRect(0, 0, width, 400);
      
      // Recipe image placeholder area
      ctx.fillStyle = '#E8F0E6';
      ctx.fillRect(40, 440, width - 80, 400);
      
      // Load and draw image if available
      if (recipe.image_url) {
        const img = new window.Image();
        img.crossOrigin = 'anonymous';
        img.src = getImageUrl(recipe.image_url);
        
        await new Promise((resolve) => {
          img.onload = () => {
            // Draw image with cover fit
            const aspectRatio = img.width / img.height;
            const targetAspect = (width - 80) / 400;
            let drawWidth, drawHeight, offsetX, offsetY;
            
            if (aspectRatio > targetAspect) {
              drawHeight = 400;
              drawWidth = drawHeight * aspectRatio;
              offsetX = 40 - (drawWidth - (width - 80)) / 2;
              offsetY = 440;
            } else {
              drawWidth = width - 80;
              drawHeight = drawWidth / aspectRatio;
              offsetX = 40;
              offsetY = 440 - (drawHeight - 400) / 2;
            }
            
            ctx.save();
            ctx.beginPath();
            ctx.rect(40, 440, width - 80, 400);
            ctx.clip();
            ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
            ctx.restore();
            resolve();
          };
          img.onerror = resolve;
        });
      }
      
      // Title
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 64px Manrope, sans-serif';
      ctx.textAlign = 'center';
      
      // Word wrap title
      const words = recipe.title.split(' ');
      let line = '';
      let y = 180;
      for (const word of words) {
        const testLine = line + word + ' ';
        if (ctx.measureText(testLine).width > width - 100) {
          ctx.fillText(line, width / 2, y);
          line = word + ' ';
          y += 70;
        } else {
          line = testLine;
        }
      }
      ctx.fillText(line, width / 2, y);
      
      // Meta info
      ctx.font = '36px Inter, sans-serif';
      ctx.fillStyle = '#E8F0E6';
      const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);
      ctx.fillText(`${formatTime(totalTime)} • ${recipe.servings} servings`, width / 2, 340);
      
      // Ingredients section
      ctx.textAlign = 'left';
      ctx.fillStyle = '#4A6741';
      ctx.font = 'bold 42px Manrope, sans-serif';
      ctx.fillText('Ingredients', 60, 920);
      
      ctx.fillStyle = '#2D3B29';
      ctx.font = '32px Inter, sans-serif';
      let ingredientY = 980;
      recipe.ingredients.slice(0, 10).forEach(ing => {
        ctx.fillText(`• ${ing.amount} ${ing.unit} ${ing.name}`, 60, ingredientY);
        ingredientY += 50;
      });
      if (recipe.ingredients.length > 10) {
        ctx.fillStyle = '#6B7C66';
        ctx.fillText(`+ ${recipe.ingredients.length - 10} more ingredients...`, 60, ingredientY);
      }
      
      // Instructions section
      ctx.fillStyle = '#4A6741';
      ctx.font = 'bold 42px Manrope, sans-serif';
      ctx.fillText('Instructions', 60, ingredientY + 80);
      
      ctx.fillStyle = '#2D3B29';
      ctx.font = '30px Inter, sans-serif';
      let instructionY = ingredientY + 140;
      recipe.instructions.slice(0, 6).forEach((step, idx) => {
        const shortStep = step.length > 60 ? step.substring(0, 60) + '...' : step;
        ctx.fillText(`${idx + 1}. ${shortStep}`, 60, instructionY);
        instructionY += 50;
      });
      if (recipe.instructions.length > 6) {
        ctx.fillStyle = '#6B7C66';
        ctx.fillText(`+ ${recipe.instructions.length - 6} more steps...`, 60, instructionY);
      }
      
      // Footer
      ctx.fillStyle = '#4A6741';
      ctx.fillRect(0, height - 100, width, 100);
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 32px Manrope, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('🍳 Made with Laro', width / 2, height - 40);
      
      // Download
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `${recipe.title.replace(/[^a-z0-9]/gi, '_')}_recipe.png`;
      link.href = dataUrl;
      link.click();
      
      toast.success('Recipe card downloaded!');
    } catch (error) {
      console.error('Failed to generate card:', error);
      toast.error('Failed to generate recipe card');
    } finally {
      setGeneratingCard(false);
    }
  };

  useEffect(() => {
    loadRecipe();
  }, [id]);

  const loadRecipe = async () => {
    try {
      const res = await recipeApi.getOne(id);
      setRecipe(res.data);
      setIsFavorite(res.data.is_favorite || false);
      setScaledServings(res.data.servings || 4);
    } catch (error) {
      toast.error('Recipe not found');
      navigate('/recipes');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFavorite = async () => {
    setTogglingFavorite(true);
    try {
      const res = await recipeApi.toggleFavorite(id);
      setIsFavorite(res.data.is_favorite);
      toast.success(res.data.is_favorite ? 'Added to favorites!' : 'Removed from favorites');
    } catch (error) {
      toast.error('Failed to update favorite');
    } finally {
      setTogglingFavorite(false);
    }
  };

  const handleScaleServings = async (newServings) => {
    if (newServings < 1) return;
    setScaledServings(newServings);
    
    try {
      const res = await recipeApi.getScaled(id, newServings);
      setScaledIngredients(res.data.ingredients);
    } catch (error) {
      console.error('Failed to scale:', error);
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this recipe?')) return;
    
    setDeleting(true);
    try {
      await recipeApi.delete(id);
      toast.success('Recipe deleted');
      navigate('/recipes');
    } catch (error) {
      toast.error('Failed to delete recipe');
    } finally {
      setDeleting(false);
    }
  };

  const handleAddToMealPlan = async () => {
    setAddingToMealPlan(true);
    try {
      await mealPlanApi.create({
        date: format(selectedDate, 'yyyy-MM-dd'),
        meal_type: mealType,
        recipe_id: recipe.id,
      });
      toast.success('Added to meal plan');
      setShowMealDialog(false);
    } catch (error) {
      toast.error('Failed to add to meal plan');
    } finally {
      setAddingToMealPlan(false);
    }
  };

  const handleAddToShopping = async () => {
    setAddingToShopping(true);
    try {
      await shoppingListApi.fromRecipes([recipe.id]);
      toast.success('Shopping list created');
      navigate('/shopping');
    } catch (error) {
      toast.error('Failed to create shopping list');
    } finally {
      setAddingToShopping(false);
    }
  };

  const handleShare = async () => {
    setSharing(true);
    try {
      const res = await sharingApi.create({ recipe_id: recipe.id });
      const fullUrl = res.data.share_url;
      setShareUrl(fullUrl);
      setShowShareDialog(true);
    } catch (error) {
      toast.error('Failed to create share link');
    } finally {
      setSharing(false);
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      toast.success('Link copied!');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy');
    }
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-mise" />
        </div>
      </Layout>
    );
  }

  if (!recipe) return null;

  const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);
  const isOwner = user?.id === recipe.author_id;

  return (
    <Layout>
      <div className="max-w-4xl mx-auto" data-testid="recipe-detail">
        {/* Back Button */}
        <Link 
          to="/recipes" 
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Recipes
        </Link>

        <motion.article
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden shadow-card"
        >
          {/* Hero Image */}
          <div className="relative aspect-video">
            <img
              src={getImageUrl(recipe.image_url)}
              alt={recipe.title}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
            
            {/* Category Badge */}
            <Badge className="absolute top-4 left-4 bg-white/90 text-foreground">
              {recipe.category}
            </Badge>
          </div>

          <div className="p-6 md:p-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
              <div>
                <h1 className="font-heading text-3xl font-bold text-foreground" data-testid="recipe-title">
                  {recipe.title}
                </h1>
                {recipe.description && (
                  <p className="text-muted-foreground mt-2">{recipe.description}</p>
                )}
              </div>

              {isOwner && (
                <div className="flex gap-2">
                  <Link to={`/recipes/${recipe.id}/edit`}>
                    <Button variant="outline" size="sm" className="rounded-full" data-testid="edit-recipe-btn">
                      <Edit className="w-4 h-4 mr-2" />
                      Edit
                    </Button>
                  </Link>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="rounded-full text-destructive hover:bg-destructive hover:text-white"
                    onClick={handleDelete}
                    disabled={deleting}
                    data-testid="delete-recipe-btn"
                  >
                    {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </Button>
                </div>
              )}
              
              {/* Favorite & Print buttons */}
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className={`rounded-full ${isFavorite ? 'text-red-500 border-red-200 bg-red-50' : ''}`}
                  onClick={handleToggleFavorite}
                  disabled={togglingFavorite}
                  data-testid="favorite-btn"
                >
                  {togglingFavorite ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Heart className={`w-4 h-4 ${isFavorite ? 'fill-current' : ''}`} />
                  )}
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="rounded-full print:hidden"
                  onClick={handlePrint}
                  data-testid="print-btn"
                >
                  <Printer className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Meta Info */}
            <div className="flex flex-wrap gap-6 mb-8 pb-8 border-b border-border/60">
              {totalTime > 0 && (
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-mise" />
                  <div>
                    <p className="text-xs text-muted-foreground">Total Time</p>
                    <p className="font-medium">{formatTime(totalTime)}</p>
                  </div>
                </div>
              )}
              {recipe.prep_time > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">Prep</p>
                  <p className="font-medium">{formatTime(recipe.prep_time)}</p>
                </div>
              )}
              {recipe.cook_time > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">Cook</p>
                  <p className="font-medium">{formatTime(recipe.cook_time)}</p>
                </div>
              )}
              
              {/* Servings with scaling controls */}
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-mise" />
                <div>
                  <p className="text-xs text-muted-foreground">Servings</p>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => handleScaleServings(scaledServings - 1)}
                      className="w-6 h-6 rounded-full bg-mise-light hover:bg-mise text-mise hover:text-white flex items-center justify-center transition-colors print:hidden"
                      disabled={scaledServings <= 1}
                    >
                      <Minus className="w-3 h-3" />
                    </button>
                    <span className="font-medium w-8 text-center">{scaledServings}</span>
                    <button 
                      onClick={() => handleScaleServings(scaledServings + 1)}
                      className="w-6 h-6 rounded-full bg-mise-light hover:bg-mise text-mise hover:text-white flex items-center justify-center transition-colors print:hidden"
                    >
                      <PlusIcon className="w-3 h-3" />
                    </button>
                    {scaledServings !== recipe.servings && (
                      <span className="text-xs text-muted-foreground ml-1">
                        (was {recipe.servings})
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-3 mb-8">
              <Button
                onClick={() => setShowCookMode(true)}
                className="rounded-full bg-mise hover:bg-mise-dark"
              >
                <Play className="w-4 h-4 mr-2" />
                Start Cooking
              </Button>
              <Dialog open={showMealDialog} onOpenChange={setShowMealDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="rounded-full" data-testid="add-to-meal-plan">
                    <CalendarPlus className="w-4 h-4 mr-2" />
                    Add to Meal Plan
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add to Meal Plan</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-4">
                    <div>
                      <label className="text-sm font-medium mb-2 block">Select Date</label>
                      <Calendar
                        mode="single"
                        selected={selectedDate}
                        onSelect={(date) => date && setSelectedDate(date)}
                        className="rounded-xl border"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-2 block">Meal Type</label>
                      <Select value={mealType} onValueChange={setMealType}>
                        <SelectTrigger className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {MEAL_TYPES.map((type) => (
                            <SelectItem key={type} value={type}>{type}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button 
                      onClick={handleAddToMealPlan} 
                      className="w-full rounded-full bg-mise hover:bg-mise-dark"
                      disabled={addingToMealPlan}
                    >
                      {addingToMealPlan ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add to Plan'}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>

              <Button 
                variant="outline" 
                className="rounded-full"
                onClick={handleAddToShopping}
                disabled={addingToShopping}
                data-testid="add-to-shopping"
              >
                {addingToShopping ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <ShoppingCart className="w-4 h-4 mr-2" />
                )}
                Add to Shopping List
              </Button>

              <Button 
                variant="outline" 
                className="rounded-full"
                onClick={() => setShowShareDialog(true)}
                data-testid="share-recipe"
              >
                <Share2 className="w-4 h-4 mr-2" />
                Share
              </Button>
            </div>

            {/* Share Dialog */}
            <Dialog open={showShareDialog} onOpenChange={setShowShareDialog}>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Share2 className="w-5 h-5 text-mise" />
                    Share Recipe
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-4">
                  <p className="text-sm text-muted-foreground">
                    Choose how you want to share this recipe:
                  </p>
                  
                  {/* Recipe Card - Best for messaging */}
                  <div className="p-4 rounded-xl border border-border/60 hover:border-mise transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-coral-light flex items-center justify-center flex-shrink-0">
                        <Image className="w-5 h-5 text-coral" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium text-sm">Recipe Card</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Download a beautiful image to share on WhatsApp, Instagram, etc.
                        </p>
                        <Button 
                          size="sm"
                          onClick={handleDownloadCard}
                          disabled={generatingCard}
                          className="mt-3 rounded-full bg-coral hover:bg-coral-dark"
                        >
                          {generatingCard ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : (
                            <Download className="w-4 h-4 mr-2" />
                          )}
                          Download Card
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Copy as Text */}
                  <div className="p-4 rounded-xl border border-border/60 hover:border-mise transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-mise-light flex items-center justify-center flex-shrink-0">
                        <FileText className="w-5 h-5 text-mise" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium text-sm">Copy as Text</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Copy formatted recipe text to paste anywhere
                        </p>
                        <Button 
                          size="sm"
                          variant="outline"
                          onClick={handleCopyAsText}
                          className="mt-3 rounded-full"
                        >
                          {copied ? (
                            <Check className="w-4 h-4 mr-2" />
                          ) : (
                            <Copy className="w-4 h-4 mr-2" />
                          )}
                          {copied ? 'Copied!' : 'Copy Text'}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Share Link - Only if externally accessible */}
                  <div className="p-4 rounded-xl border border-border/60 hover:border-mise transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
                        <LinkIcon className="w-5 h-5 text-blue-600" />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium text-sm">Share Link</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Create a link others can open (requires external server access)
                        </p>
                        {shareUrl ? (
                          <div className="flex gap-2 mt-3">
                            <Input 
                              value={shareUrl} 
                              readOnly 
                              className="rounded-xl text-xs h-9"
                            />
                            <Button 
                              size="sm"
                              variant="outline"
                              onClick={handleCopyLink}
                              className="rounded-xl h-9"
                            >
                              <Copy className="w-4 h-4" />
                            </Button>
                          </div>
                        ) : (
                          <Button 
                            size="sm"
                            variant="outline"
                            onClick={handleShare}
                            disabled={sharing}
                            className="mt-3 rounded-full"
                          >
                            {sharing ? (
                              <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            ) : (
                              <LinkIcon className="w-4 h-4 mr-2" />
                            )}
                            Generate Link
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground text-center pt-2">
                    💡 Recipe Card works best for locally-hosted servers
                  </p>
                </div>
              </DialogContent>
            </Dialog>

            {/* Tags */}
            {recipe.tags && recipe.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-8">
                {recipe.tags.map((tag, idx) => (
                  <span
                    key={`${tag}-${idx}`}
                    className="px-3 py-1 rounded-full bg-mise-light text-mise text-sm"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {/* Ingredients */}
            <section className="mb-8">
              <h2 className="font-heading text-xl font-semibold mb-4 flex items-center gap-2">
                <ChefHat className="w-5 h-5 text-mise" />
                Ingredients
                {scaledServings !== recipe.servings && (
                  <span className="text-sm font-normal text-muted-foreground">
                    (scaled for {scaledServings} servings)
                  </span>
                )}
              </h2>
              <ul className="space-y-2" data-testid="ingredients-list">
                {(scaledIngredients || recipe.ingredients).map((ing, idx) => (
                  <li key={`${ing.name}-${idx}`} className="flex items-start gap-3 p-3 rounded-xl bg-cream-subtle">
                    <span className="w-2 h-2 rounded-full bg-mise mt-2 flex-shrink-0" />
                    <span>
                      <span className="font-medium">{ing.amount}</span>
                      {ing.unit && <span className="text-muted-foreground"> {ing.unit}</span>}
                      <span> {ing.name}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>

            {/* Instructions */}
            <section className="mb-8">
              <h2 className="font-heading text-xl font-semibold mb-4">Instructions</h2>
              <ol className="space-y-4" data-testid="instructions-list">
                {recipe.instructions.map((step, idx) => (
                  <li key={`step-${idx}`} className="flex gap-4">
                    <span className="flex-shrink-0 w-8 h-8 rounded-full bg-mise text-white flex items-center justify-center font-semibold text-sm">
                      {idx + 1}
                    </span>
                    <p className="pt-1">{step}</p>
                  </li>
                ))}
              </ol>
            </section>

            {/* Nutrition Calculator */}
            <section className="mb-6">
              <NutritionCalculator 
                recipeId={recipe.id}
                ingredients={recipe.ingredients?.map(i => `${i.amount || ''} ${i.unit || ''} ${i.name}`)}
                servings={scaledServings || recipe.servings}
              />
            </section>

            {/* Cost Calculator */}
            <section className="mb-6">
              <CostCalculator 
                recipeId={recipe.id}
                servings={scaledServings || recipe.servings}
              />
            </section>

            {/* Reviews & Ratings */}
            <section className="mb-6">
              <RecipeReviews 
                recipeId={recipe.id}
                currentUserId={user?.id}
              />
            </section>

            {/* Recipe Version History */}
            {isOwner && (
              <section className="mb-6">
                <RecipeVersions 
                  recipeId={recipe.id}
                  currentVersion={recipe.current_version}
                  onRestore={() => loadRecipe()}
                />
              </section>
            )}
          </div>
        </motion.article>
      </div>

      {/* Cook Mode */}
      {showCookMode && (
        <CookMode recipe={recipe} onClose={() => setShowCookMode(false)} />
      )}
    </Layout>
  );
};
