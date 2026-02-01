import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { reviewsApi } from '../lib/api';
import {
  Star,
  ThumbsUp,
  ThumbsDown,
  Meh,
  MessageSquare,
  Edit,
  Trash2,
  Loader2,
  ChevronDown,
  ChevronUp,
  Check,
  User
} from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';

// Star Rating Component
const StarRating = ({ rating, onChange, readonly = false, size = 'md' }) => {
  const [hover, setHover] = useState(0);
  const sizeClass = size === 'sm' ? 'w-4 h-4' : size === 'lg' ? 'w-8 h-8' : 'w-6 h-6';
  
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={readonly}
          onClick={() => onChange?.(star)}
          onMouseEnter={() => !readonly && setHover(star)}
          onMouseLeave={() => setHover(0)}
          className={`${readonly ? '' : 'cursor-pointer hover:scale-110'} transition-transform`}
        >
          <Star
            className={`${sizeClass} ${
              star <= (hover || rating)
                ? 'fill-amber-400 text-amber-400'
                : 'text-gray-300'
            }`}
          />
        </button>
      ))}
    </div>
  );
};

// Review Form
const ReviewForm = ({ recipeId, existingReview, onSubmit, onCancel }) => {
  const [rating, setRating] = useState(existingReview?.rating || 0);
  const [comment, setComment] = useState(existingReview?.comment || '');
  const [wouldMakeAgain, setWouldMakeAgain] = useState(existingReview?.would_make_again ?? null);
  const [selectedTags, setSelectedTags] = useState(existingReview?.tags || []);
  const [submitting, setSubmitting] = useState(false);
  const [availableTags, setAvailableTags] = useState({ positive: [], tips: [], occasions: [] });

  useEffect(() => {
    loadTags();
  }, []);

  const loadTags = async () => {
    try {
      const res = await reviewsApi.getTags();
      setAvailableTags(res.data.tags);
    } catch (err) {
      console.log('Could not load tags');
    }
  };

  const toggleTag = (tag) => {
    setSelectedTags(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const handleSubmit = async () => {
    if (rating === 0) {
      toast.error('Please select a rating');
      return;
    }

    setSubmitting(true);
    try {
      const data = {
        recipe_id: recipeId,
        rating,
        comment: comment.trim() || null,
        would_make_again: wouldMakeAgain,
        tags: selectedTags
      };

      if (existingReview) {
        await reviewsApi.update(existingReview.id, data);
        toast.success('Review updated!');
      } else {
        await reviewsApi.create(data);
        toast.success('Review submitted!');
      }
      onSubmit?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not submit review');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4 p-4 bg-muted/50 rounded-xl" data-testid="review-form">
      {/* Rating */}
      <div>
        <label className="text-sm font-medium mb-2 block">Your Rating</label>
        <StarRating rating={rating} onChange={setRating} size="lg" />
      </div>

      {/* Would Make Again */}
      <div>
        <label className="text-sm font-medium mb-2 block">Would you make this again?</label>
        <div className="flex gap-2">
          {[
            { value: true, icon: ThumbsUp, label: 'Yes!' },
            { value: false, icon: ThumbsDown, label: 'No' },
            { value: null, icon: Meh, label: 'Maybe' },
          ].map(({ value, icon: Icon, label }) => (
            <button
              key={label}
              onClick={() => setWouldMakeAgain(value)}
              className={`flex items-center gap-2 px-4 py-2 rounded-full border-2 transition-all ${
                wouldMakeAgain === value
                  ? 'border-mise bg-mise/10 text-mise'
                  : 'border-border/60 hover:border-mise/50'
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tags */}
      <div>
        <label className="text-sm font-medium mb-2 block">Tags (optional)</label>
        <div className="flex flex-wrap gap-1">
          {Object.values(availableTags).flat().slice(0, 12).map(tag => (
            <button
              key={tag}
              onClick={() => toggleTag(tag)}
              className={`px-2 py-1 rounded-full text-xs transition-all ${
                selectedTags.includes(tag)
                  ? 'bg-mise text-white'
                  : 'bg-muted hover:bg-mise/20'
              }`}
            >
              {selectedTags.includes(tag) && <Check className="w-3 h-3 inline mr-1" />}
              {tag.replace(/-/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Comment */}
      <div>
        <label className="text-sm font-medium mb-2 block">Your Review (optional)</label>
        <Textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Share your experience with this recipe..."
          rows={3}
          className="rounded-xl"
        />
      </div>

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button
          onClick={handleSubmit}
          disabled={submitting || rating === 0}
          className="flex-1 rounded-full bg-mise hover:bg-mise-dark"
        >
          {submitting ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <Check className="w-4 h-4 mr-2" />
          )}
          {existingReview ? 'Update Review' : 'Submit Review'}
        </Button>
        {onCancel && (
          <Button variant="outline" onClick={onCancel} className="rounded-full">
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
};

// Single Review Display
const ReviewCard = ({ review, currentUserId, onEdit, onDelete, onHelpful }) => {
  const isOwner = review.user_id === currentUserId;
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-4 bg-white dark:bg-card rounded-xl border border-border/60"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-mise-light flex items-center justify-center">
            <User className="w-4 h-4 text-mise" />
          </div>
          <div>
            <p className="font-medium text-sm">{review.user_name}</p>
            <p className="text-xs text-muted-foreground">
              {format(new Date(review.created_at), 'MMM d, yyyy')}
            </p>
          </div>
        </div>
        <StarRating rating={review.rating} readonly size="sm" />
      </div>

      {/* Would Make Again */}
      {review.would_make_again !== null && (
        <div className="flex items-center gap-1 text-xs mb-2">
          {review.would_make_again ? (
            <>
              <ThumbsUp className="w-3 h-3 text-teal" />
              <span className="text-teal">Would make again</span>
            </>
          ) : (
            <>
              <ThumbsDown className="w-3 h-3 text-coral" />
              <span className="text-coral">Wouldn't make again</span>
            </>
          )}
        </div>
      )}

      {/* Comment */}
      {review.comment && (
        <p className="text-sm text-muted-foreground mb-3">{review.comment}</p>
      )}

      {/* Tags */}
      {review.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {review.tags.map(tag => (
            <span key={tag} className="px-2 py-0.5 bg-muted rounded-full text-xs">
              {tag.replace(/-/g, ' ')}
            </span>
          ))}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2 border-t border-border/60">
        <button
          onClick={() => onHelpful?.(review.id)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-mise transition-colors"
        >
          <ThumbsUp className="w-3 h-3" />
          Helpful ({review.helpful_count || 0})
        </button>
        
        {isOwner && (
          <div className="flex gap-2">
            <button
              onClick={() => onEdit?.(review)}
              className="text-xs text-muted-foreground hover:text-mise"
            >
              <Edit className="w-3 h-3" />
            </button>
            <button
              onClick={() => onDelete?.(review.id)}
              className="text-xs text-muted-foreground hover:text-destructive"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    </motion.div>
  );
};

// Main Reviews Component
export const RecipeReviews = ({ recipeId, currentUserId }) => {
  const [reviews, setReviews] = useState([]);
  const [ratingSummary, setRatingSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editingReview, setEditingReview] = useState(null);
  const [userReview, setUserReview] = useState(null);

  useEffect(() => {
    loadReviews();
  }, [recipeId]);

  const loadReviews = async () => {
    setLoading(true);
    try {
      const res = await reviewsApi.getForRecipe(recipeId);
      setReviews(res.data.reviews || []);
      setRatingSummary(res.data.rating_summary);
      setUserReview(res.data.user_review);
    } catch (err) {
      console.error('Failed to load reviews:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleHelpful = async (reviewId) => {
    try {
      await reviewsApi.markHelpful(reviewId);
      loadReviews();
    } catch (err) {
      toast.error('Could not mark as helpful');
    }
  };

  const handleDelete = async (reviewId) => {
    if (!confirm('Delete this review?')) return;
    
    try {
      await reviewsApi.delete(reviewId);
      toast.success('Review deleted');
      loadReviews();
    } catch (err) {
      toast.error('Could not delete review');
    }
  };

  const handleEdit = (review) => {
    setEditingReview(review);
    setShowForm(true);
  };

  const handleFormSubmit = () => {
    setShowForm(false);
    setEditingReview(null);
    loadReviews();
  };

  return (
    <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden" data-testid="recipe-reviews">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <MessageSquare className="w-5 h-5 text-mise" />
          <span className="font-medium">Reviews & Ratings</span>
          {ratingSummary && (
            <div className="flex items-center gap-2">
              <StarRating rating={Math.round(ratingSummary.average)} readonly size="sm" />
              <span className="text-sm text-muted-foreground">
                {ratingSummary.average} ({ratingSummary.count})
              </span>
            </div>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-border/60"
          >
            <div className="p-4 space-y-4">
              {loading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-mise" />
                </div>
              ) : (
                <>
                  {/* Rating Summary */}
                  {ratingSummary && (
                    <div className="flex items-center gap-4 p-4 bg-muted/50 rounded-xl">
                      <div className="text-center">
                        <p className="text-4xl font-bold text-mise">{ratingSummary.average}</p>
                        <StarRating rating={Math.round(ratingSummary.average)} readonly size="sm" />
                        <p className="text-xs text-muted-foreground mt-1">
                          {ratingSummary.count} review{ratingSummary.count !== 1 ? 's' : ''}
                        </p>
                      </div>
                      {ratingSummary.would_make_again_percent > 0 && (
                        <div className="flex-1 border-l border-border/60 pl-4">
                          <p className="text-2xl font-bold text-teal">
                            {ratingSummary.would_make_again_percent}%
                          </p>
                          <p className="text-xs text-muted-foreground">would make again</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Add/Edit Review Button */}
                  {!showForm && (
                    <Button
                      onClick={() => {
                        setEditingReview(userReview);
                        setShowForm(true);
                      }}
                      className="w-full rounded-full"
                      variant={userReview ? 'outline' : 'default'}
                    >
                      <Star className="w-4 h-4 mr-2" />
                      {userReview ? 'Edit Your Review' : 'Write a Review'}
                    </Button>
                  )}

                  {/* Review Form */}
                  {showForm && (
                    <ReviewForm
                      recipeId={recipeId}
                      existingReview={editingReview}
                      onSubmit={handleFormSubmit}
                      onCancel={() => {
                        setShowForm(false);
                        setEditingReview(null);
                      }}
                    />
                  )}

                  {/* Reviews List */}
                  <div className="space-y-3">
                    {reviews.length === 0 ? (
                      <p className="text-center text-muted-foreground py-4">
                        No reviews yet. Be the first to share your experience!
                      </p>
                    ) : (
                      reviews.map(review => (
                        <ReviewCard
                          key={review.id}
                          review={review}
                          currentUserId={currentUserId}
                          onEdit={handleEdit}
                          onDelete={handleDelete}
                          onHelpful={handleHelpful}
                        />
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
