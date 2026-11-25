import { useEffect } from 'react';

/** HashRouter links to legal pages must land on the static path URL for Play / crawlers. */
export const LegalRedirect = ({ href }) => {
  useEffect(() => {
    window.location.replace(href);
  }, [href]);
  return (
    <div className="min-h-screen flex items-center justify-center text-muted-foreground p-8">
      Opening legal page…
    </div>
  );
};

export default LegalRedirect;
