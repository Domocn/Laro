import React, { useState, useCallback } from 'react';
import { cn } from '../lib/utils';

/**
 * OptimizedImage - An image component with loading state and error handling
 *
 * Features:
 * - Lazy loading by default
 * - Shimmer placeholder while loading
 * - Graceful error fallback
 * - Smooth fade-in transition
 */
export const OptimizedImage = ({
  src,
  alt,
  className,
  containerClassName,
  fallbackSrc = 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=800&q=80',
  eager = false,
  ...props
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleLoad = useCallback(() => {
    setIsLoading(false);
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setHasError(true);
  }, []);

  const imageSrc = hasError ? fallbackSrc : src;

  return (
    <div className={cn('relative overflow-hidden', containerClassName)}>
      {/* Shimmer placeholder */}
      {isLoading && (
        <div className="absolute inset-0 bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 animate-shimmer bg-[length:200%_100%]" />
      )}

      {/* Actual image */}
      <img
        src={imageSrc}
        alt={alt}
        loading={eager ? 'eager' : 'lazy'}
        decoding="async"
        onLoad={handleLoad}
        onError={handleError}
        className={cn(
          'transition-opacity duration-300',
          isLoading ? 'opacity-0' : 'opacity-100',
          className
        )}
        {...props}
      />
    </div>
  );
};

export default OptimizedImage;
