import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Shield, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';

export const PrivacyPolicy = () => {
  const lastUpdated = 'August 23, 2026';
  const contactEmail = 'privacy@laro.food';
  const supportEmail = 'app@laro.food';

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
              Laro (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;) is committed to protecting your privacy. This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use the Laro website at{' '}
              <a href="https://laro.food" className="text-laro hover:underline">laro.food</a>, the Laro Android app, and related services (together, the &quot;Service&quot;).
            </p>
            <p className="text-muted-foreground mb-0">
              We build Laro to help you cook, plan meals, and share food with the people you trust. We collect what we need to run those features and avoid selling your personal data. Your recipes remain yours.
            </p>
          </section>

          {/* Information We Collect */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Information We Collect</h2>

            <h3 className="text-lg font-medium text-foreground">Account and identity</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Account information:</strong> Email address, display name, password (stored hashed), and optional profile details you provide</li>
              <li><strong>Authentication:</strong> Email verification status; optional Google or GitHub OAuth account identifiers when you choose social sign-in; optional two-factor authentication (TOTP) secrets when you enable 2FA</li>
              <li><strong>Referrals:</strong> Friend / referral codes you enter or share (used for trials and reward points)</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Content you create in Laro</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Recipes and cookbooks:</strong> Titles, ingredients, steps, photos, tags, notes, and imported content (URLs, PDFs, meal packs)</li>
              <li><strong>Meal plans and shopping lists:</strong> Planned meals, list items, and related notes</li>
              <li><strong>Pantry / fridge:</strong> Ingredients you track and optional expiration dates</li>
              <li><strong>Preferences:</strong> Dietary restrictions, allergens, cooking skill, household size, language, and similar settings</li>
              <li><strong>Household and friends:</strong> Household membership, invites, friend requests, and recipe sharing with people you choose</li>
              <li><strong>Support:</strong> Messages and attachments you send through in-app support tickets</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">AI and optional media inputs</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>AI requests:</strong> Prompts and context you submit for features such as AI chat, meal-plan generation, recipe or PDF import, and receipt scanning (subject to plan quotas)</li>
              <li><strong>Images you upload:</strong> Recipe photos, cookbook scans, or receipt images when you use those features</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Health-related data (optional)</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>On-device Health Connect (Android):</strong> If you enable it, we may write nutrition (calories / macros) to Health Connect when you mark a meal cooked. This stays on your device and apps you authorize; we do not receive Health Connect data from other apps</li>
              <li><strong>Google Health API (optional link):</strong> If you connect Google Health / Fitbit nutrition write via our OAuth flow, we store encrypted tokens and may send anonymous nutrition logs when you mark a meal cooked (if you leave sync enabled). You can disconnect and undo logs in Settings</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Information collected automatically</h3>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Device and session data:</strong> IP address, browser or app version, device type, and login / session metadata needed for security and multi-device sync</li>
              <li><strong>Push tokens:</strong> Firebase Cloud Messaging tokens to deliver meal reminders and alerts you enable</li>
              <li><strong>Crash reports:</strong> Diagnostic crash data via Firebase Crashlytics (Android) to improve stability</li>
              <li><strong>Android analytics:</strong> Basic Firebase Analytics events on the Android app (for example app opens and feature usage aggregates). We do not use advertising ID–based ad tracking networks</li>
              <li><strong>Live sync:</strong> WebSocket connection metadata so your household / account data can refresh across devices in near real time</li>
              <li><strong>Cookies and local storage (web):</strong> Essential storage to keep you signed in, remember preferences, and store cookie-consent choice. See &quot;Cookies and local storage&quot; below</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Information we do not sell</h3>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>We do not sell your personal data</li>
              <li>We do not share your recipes or account content with advertisers</li>
              <li>We do not collect precise GPS location for advertising</li>
            </ul>
          </section>

          {/* How We Use Your Information */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">How We Use Your Information</h2>
            <p className="text-muted-foreground">We use your information to:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>Provide, maintain, and secure the Service (accounts, sync, households, friends, cookbooks, meal plans, shopping lists, pantry)</li>
              <li>Power optional AI features you request (chat, meal planning, imports, receipt OCR), including sending prompts / files to our configured AI providers</li>
              <li>Send transactional email (verification, password reset, security notices) when email is enabled</li>
              <li>Send push notifications you enable (meal reminders, pantry alerts, and similar)</li>
              <li>Process and manage subscriptions and referrals (including trial eligibility and reward points)</li>
              <li>Write optional nutrition logs when you enable Health Connect or Google Health sync</li>
              <li>Estimate shopping costs using public Open Prices catalog data where that feature is enabled (we do not upload your identity to that catalog sync)</li>
              <li>Improve reliability (crash reporting) and understand aggregate product usage on Android (Firebase Analytics)</li>
              <li>Respond to support requests and enforce our terms and safety rules</li>
            </ul>
          </section>

          {/* AI Features */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">AI Features</h2>
            <p className="text-muted-foreground">
              Some Laro features use artificial intelligence. Depending on server configuration, processing may use cloud AI providers (for example OpenAI-compatible APIs such as Groq) and/or a self-hosted model (Ollama) when available. Production hosted Laro typically uses cloud AI with usage quotas tied to your plan.
            </p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>Content you submit for AI (text, recipe context, PDFs, images) is processed to fulfill your request</li>
              <li>We use AI providers as processors to generate results; we do not use your private recipes to train a public Laro model</li>
              <li>Cloud AI providers process data under their own privacy terms; avoid submitting sensitive personal information you do not want processed by those services</li>
              <li>Self-hosted deployments may point AI at a local Ollama instance you control</li>
              <li><strong>Calendar meal pace (optional):</strong> if you paste a private calendar ICS URL, we fetch it over HTTPS on our servers to read busy times for meal planning. Event titles from ICS may be visible to the server while parsing but are discarded and are not sent to AI — only busy/free evening windows are used. Your ICS URL is sensitive; treat it like a password and revoke it if shared accidentally.</li>
            </ul>
          </section>

          {/* Sharing */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Sharing and visibility</h2>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li><strong>Households:</strong> Members you invite can see shared household data according to household permissions</li>
              <li><strong>Friends:</strong> Friend connections and recipe shares you initiate are visible to the people involved</li>
              <li><strong>Public / shared links:</strong> If you create a shareable recipe link, anyone with the link may view that shared content</li>
              <li>We do not make your private library public by default</li>
            </ul>
          </section>

          {/* Payments */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Subscriptions and payments</h2>
            <p className="text-muted-foreground">
              Paid plans are managed through RevenueCat. Purchases on Android are processed by Google Play; other store or web billing partners may apply where offered. We receive subscription status, entitlements, and related identifiers so we can unlock Pro features. We do not store your full payment card numbers on Laro servers—payment processors and app stores handle payment details.
            </p>
            <p className="text-muted-foreground mb-0">
              Referral trials and reward redemptions are recorded on your account so we can apply benefits accurately.
            </p>
          </section>

          {/* Data Storage and Security */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Data Storage and Security</h2>

            <h3 className="text-lg font-medium text-foreground">Hosting</h3>
            <p className="text-muted-foreground">
              The hosted Service at laro.food runs on a virtual private server in the United Kingdom (currently OVH, London region), with Cloudflare providing DNS, CDN, and protection in front of the site. Self-hosted instances store data wherever the operator deploys them.
            </p>

            <h3 className="text-lg font-medium text-foreground">Local storage (Android)</h3>
            <p className="text-muted-foreground">
              The Android app keeps an encrypted local database (SQLCipher / AES-256) for offline use and sync. On-device Health Connect writes stay under your device permissions.
            </p>

            <h3 className="text-lg font-medium text-foreground">Transmission and access controls</h3>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>HTTPS / TLS for data in transit</li>
              <li>Encrypted OAuth tokens for optional Google Health linking</li>
              <li>Optional two-factor authentication (2FA)</li>
              <li>Authenticated WebSocket channels for live multi-device updates</li>
            </ul>
          </section>

          {/* Cookies */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Cookies and local storage</h2>
            <p className="text-muted-foreground mb-0">
              On the web app we use local storage (and similar browser storage) primarily to keep you signed in, remember UI preferences (such as language or theme accents), and record whether you accepted or declined our cookie notice. These are functional / preference storage rather than third-party advertising cookies. Declining the banner does not remove storage required for basic sign-in if you continue to use the Service.
            </p>
          </section>

          {/* Third-Party Services */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Third-Party Services</h2>
            <p className="text-muted-foreground">Depending on the feature you use, we may share limited data with:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li><strong>OVH:</strong> Server hosting (UK)</li>
              <li><strong>Cloudflare:</strong> DNS, CDN, DDoS / bot protection</li>
              <li><strong>Firebase (Google):</strong> Push notifications (FCM), Crashlytics, and Android Analytics</li>
              <li><strong>Google / GitHub:</strong> Optional OAuth sign-in</li>
              <li><strong>Google Health API:</strong> Optional nutrition write when you link the integration</li>
              <li><strong>RevenueCat + Google Play (and other stores as applicable):</strong> Subscription management and billing</li>
              <li><strong>Email delivery (e.g. Resend or SMTP):</strong> Transactional messages such as verification and password reset</li>
              <li><strong>AI providers (e.g. Groq / OpenAI-compatible APIs, or Ollama when configured):</strong> Processing AI feature requests</li>
              <li><strong>Open Food Facts — Open Prices:</strong> Public price catalog sync used for cost estimates (where enabled)</li>
            </ul>
          </section>

          {/* Retention */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Data Retention</h2>
            <p className="text-muted-foreground mb-0">
              We keep account and content data while your account is active. If you delete your account from Settings (or complete a confirmed deletion flow), we remove or anonymize associated personal data from our primary systems within a reasonable period, except where we must retain limited records for security, fraud prevention, legal compliance, or unresolved support / billing issues. Backups may persist for a short additional window before rotating. Local app data remains on your device until you clear app data or uninstall.
            </p>
          </section>

          {/* Your Rights */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Your Rights</h2>
            <p className="text-muted-foreground">Depending on where you live, you may have the right to:</p>
            <ul className="text-muted-foreground space-y-2">
              <li>Access your personal data</li>
              <li>Correct inaccurate data</li>
              <li>Delete your account and data (Settings)</li>
              <li>Export your data (JSON / ZIP export available in Settings)</li>
              <li>Withdraw optional consents (notifications, health sync, cookie preference) at any time</li>
              <li>Object to or restrict certain processing, where applicable law provides</li>
            </ul>
            <p className="text-muted-foreground mb-0">
              To exercise these rights, use in-app controls where available or email us at the address below. We may need to verify your identity before fulfilling a request.
            </p>
          </section>

          {/* Children */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Children&apos;s Privacy</h2>
            <p className="text-muted-foreground mb-0">
              Laro is not directed to children under 13 (or the equivalent minimum age in your country). We do not knowingly collect personal information from children. If you believe a child has provided us personal data, contact us and we will take appropriate steps to delete it.
            </p>
          </section>

          {/* International */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">International Processing</h2>
            <p className="text-muted-foreground mb-0">
              Primary hosted application data is stored in the United Kingdom. Some processors (for example Google Firebase, OAuth providers, RevenueCat, email, or cloud AI) may process data in other countries. Where required, we rely on appropriate safeguards offered by those providers and applicable law.
            </p>
          </section>

          {/* Changes */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Changes to This Policy</h2>
            <p className="text-muted-foreground mb-0">
              We may update this Privacy Policy from time to time. We will revise the &quot;Last updated&quot; date at the top of this page. Continued use of the Service after changes means you acknowledge the updated policy. Material changes may also be highlighted in the app or by email when appropriate.
            </p>
          </section>

          {/* Contact Us */}
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Contact Us</h2>
            <p className="text-muted-foreground">
              If you have questions about this Privacy Policy or your data, contact us:
            </p>
            <div className="flex items-center gap-3 text-muted-foreground">
              <Mail className="w-5 h-5 text-laro" />
              <a href={`mailto:${contactEmail}`} className="text-laro hover:underline">{contactEmail}</a>
            </div>
            <p className="text-muted-foreground mb-0 mt-3">
              General app support:{' '}
              <a href={`mailto:${supportEmail}`} className="text-laro hover:underline">{supportEmail}</a>
            </p>
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
