import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';

export const PrivacyPolicy = () => {
  const lastUpdated = 'February 1, 2026';
  const contactEmail = 'privacy@laro.food';

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/laro-icon.png" alt="Laro" className="w-10 h-10 rounded-lg" />
            <span className="font-display font-bold text-xl text-foreground">Laro</span>
          </Link>
          <Button variant="ghost" asChild>
            <Link to="/" className="flex items-center gap-2">
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </Link>
          </Button>
        </div>
      </header>

      {/* Content */}
      <main className="container mx-auto px-4 py-12 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-2xl bg-laro-light flex items-center justify-center">
            <Shield className="w-6 h-6 text-laro" />
          </div>
          <div>
            <h1 className="text-3xl font-display font-bold text-foreground">Privacy Policy</h1>
            <p className="text-muted-foreground">Last updated: {lastUpdated}</p>
          </div>
        </div>

        <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8">
          {/* Introduction */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Introduction</h2>
            <p className="text-muted-foreground">
              Laro ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use the Laro application (the "App") and related services.
            </p>
            <p className="text-muted-foreground mb-0">
              We believe in privacy by design. Laro is built to minimize data collection while providing you with a powerful recipe management experience. Your recipes are your own.
            </p>
          </section>

          {/* Information We Collect */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Information We Collect</h2>

            <h3 className="text-lg font-medium text-foreground">Information You Provide</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Account Information:</strong> Email address and display name when you create an account</li>
              <li><strong>Recipe Data:</strong> Recipes, cookbooks, ingredients, and cooking instructions you add</li>
              <li><strong>Pantry Information:</strong> Ingredients and expiration dates you track</li>
              <li><strong>Meal Plans:</strong> Your weekly meal planning data</li>
              <li><strong>Shopping Lists:</strong> Items you add to shopping lists</li>
              <li><strong>Preferences:</strong> Dietary restrictions, allergens, cooking skill level, and household size</li>
              <li><strong>Household Data:</strong> Information about household members you invite to share recipes</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Information Collected Automatically</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Device Tokens:</strong> Push notification tokens to deliver meal reminders and alerts</li>
              <li><strong>Crash Reports:</strong> Anonymous crash data to improve app stability (via Firebase Crashlytics)</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Information We Do NOT Collect</h3>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>We do not use analytics or tracking services</li>
              <li>We do not collect browsing history or behavioral data</li>
              <li>We do not collect location data (geofencing is processed locally on your device)</li>
              <li>We do not sell or share your data with advertisers</li>
            </ul>
          </section>

          {/* How We Use Your Information */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">How We Use Your Information</h2>
            <p className="text-muted-foreground">We use your information solely to:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>Provide and maintain the Laro service</li>
              <li>Sync your recipes and data across devices</li>
              <li>Enable household sharing features</li>
              <li>Send push notifications for meal reminders and pantry expiration alerts (if enabled)</li>
              <li>Process subscription payments through our payment provider</li>
              <li>Improve app stability through crash reporting</li>
              <li>Respond to your support requests</li>
            </ul>
          </section>

          {/* Data Storage and Security */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Data Storage and Security</h2>

            <h3 className="text-lg font-medium text-foreground">Local Storage</h3>
            <p className="text-muted-foreground">
              The Laro mobile app stores your data locally on your device using AES-256 encryption (SQLCipher). This means your recipes and personal data are encrypted and protected even if your device is compromised.
            </p>

            <h3 className="text-lg font-medium text-foreground">Cloud Synchronization</h3>
            <p className="text-muted-foreground">
              When you use cloud sync features, your data is transmitted using HTTPS encryption and stored securely on servers hosted by Railway (railway.app), a cloud platform provider based in the United States.
            </p>

            <h3 className="text-lg font-medium text-foreground">Security Measures</h3>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>AES-256 encryption for local database storage</li>
              <li>HTTPS/TLS encryption for all data in transit</li>
              <li>Secure authentication with optional two-factor authentication (2FA)</li>
            </ul>
          </section>

          {/* Third-Party Services */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Third-Party Services</h2>
            <p className="text-muted-foreground">We use the following third-party services:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li><strong>Railway:</strong> Backend hosting infrastructure</li>
              <li><strong>Cloudflare:</strong> CDN, DDoS protection, DNS</li>
              <li><strong>Firebase:</strong> Push notifications and crash reporting</li>
              <li><strong>RevenueCat:</strong> Subscription management</li>
              <li><strong>Google/GitHub OAuth:</strong> Social login (optional)</li>
            </ul>
          </section>

          {/* Your Rights */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Your Rights</h2>
            <p className="text-muted-foreground">You have the right to:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>Access your personal data</li>
              <li>Correct inaccurate data</li>
              <li>Delete your account and data</li>
              <li>Export your data (JSON format available in Settings)</li>
              <li>Withdraw consent at any time</li>
            </ul>
          </section>

          {/* Contact Us */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Contact Us</h2>
            <p className="text-muted-foreground">
              If you have any questions about this Privacy Policy, please contact us:
            </p>
            <div className="flex items-center gap-3 text-muted-foreground mb-0">
              <Mail className="w-5 h-5 text-laro" />
              <a href={`mailto:${contactEmail}`} className="text-laro hover:underline">{contactEmail}</a>
            </div>
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card/50 mt-12">
        <div className="container mx-auto px-4 py-8 text-center text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} Laro. All rights reserved.</p>
          <div className="flex justify-center gap-6 mt-4">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <Link to="/privacy-policy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default PrivacyPolicy;
