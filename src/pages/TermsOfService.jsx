import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, FileText, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';

export const TermsOfService = () => {
  const lastUpdated = 'September 23, 2026';
  const supportEmail = 'app@laro.food';

  return (
    <div className="min-h-screen bg-background">
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

      <main className="container mx-auto px-4 py-12 max-w-4xl">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-2xl bg-laro-light flex items-center justify-center">
            <FileText className="w-6 h-6 text-laro" />
          </div>
          <div>
            <h1 className="text-3xl font-display font-bold text-foreground">Terms of Service</h1>
            <p className="text-muted-foreground">Last updated: {lastUpdated}</p>
          </div>
        </div>

        <div className="prose prose-neutral dark:prose-invert max-w-none space-y-8">
          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Agreement</h2>
            <p className="text-muted-foreground mb-0">
              These Terms of Service (&quot;Terms&quot;) govern your access to and use of the Laro website at{' '}
              <a href="https://laro.food" className="text-laro hover:underline">laro.food</a>, the Laro Android app, and related services (together, the &quot;Service&quot;) operated by Laro (&quot;we,&quot; &quot;our,&quot; or &quot;us&quot;). By creating an account or using the Service, you agree to these Terms and our{' '}
              <Link to="/privacy-policy" className="text-laro hover:underline">Privacy Policy</Link>.
              If you do not agree, do not use the Service.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">The Service</h2>
            <p className="text-muted-foreground mb-0">
              Laro helps you store recipes, plan meals, manage shopping lists, and share a household cookbook. Features may vary by platform, plan, and server configuration. We may add, change, or remove features over time. Self-hosted deployments are operated by their administrator; these Terms apply to hosted laro.food unless your operator provides separate terms.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Accounts</h2>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>You must provide accurate account information and keep your credentials secure.</li>
              <li>You are responsible for activity under your account unless you notify us promptly of unauthorized access.</li>
              <li>You must be old enough to form a binding contract where you live (typically 18, or the age of majority in your region).</li>
              <li>We may suspend or terminate accounts that violate these Terms or pose a security or abuse risk.</li>
            </ul>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Acceptable use</h2>
            <p className="text-muted-foreground">You agree not to:</p>
            <ul className="text-muted-foreground space-y-2 mb-0">
              <li>Use the Service for unlawful, harmful, or fraudulent purposes</li>
              <li>Attempt to bypass security, quotas, or access controls</li>
              <li>Scrape, overload, or interfere with the Service or other users</li>
              <li>Upload malware or content that infringes others&apos; rights</li>
              <li>Harass other users or misuse household, friend, or support features</li>
            </ul>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Your content</h2>
            <p className="text-muted-foreground mb-0">
              You retain ownership of recipes, photos, and other content you add to Laro. You grant us a limited license to host, process, back up, and display that content solely to provide the Service (including sharing you initiate with households, friends, or public links). You represent that you have the rights needed for content you upload. We may remove content that violates these Terms or applicable law.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Laro Pro — subscriptions and billing</h2>
            <p className="text-muted-foreground">
              <strong>Laro Pro</strong> is an optional paid plan with additional features (for example higher AI quotas and advanced imports). Free-tier limits and Pro benefits are described in the app and may change with reasonable notice where required.
            </p>

            <h3 className="text-lg font-medium text-foreground">Web checkout (Lemon Squeezy)</h3>
            <p className="text-muted-foreground">
              New Laro Pro subscriptions purchased on the web at{' '}
              <a href="https://laro.food/settings" className="text-laro hover:underline">laro.food → Settings</a>{' '}
              are sold and billed by{' '}
              <a href="https://www.lemonsqueezy.com" className="text-laro hover:underline" rel="noopener noreferrer" target="_blank">Lemon Squeezy</a>{' '}
              as <strong>merchant of record</strong>. Payment, tax, invoicing, and many consumer billing rules are handled under Lemon Squeezy&apos;s{' '}
              <a href="https://www.lemonsqueezy.com/buyer-terms" className="text-laro hover:underline" rel="noopener noreferrer" target="_blank">buyer terms</a>{' '}
              and related policies. We link your Laro account (for example your user id and email) to checkout so Pro access can be applied after payment.
            </p>
            <ul className="text-muted-foreground space-y-2">
              <li><strong>Trials and renewals:</strong> If a free trial or introductory offer is shown at checkout, its length and price after the trial are stated on the checkout page. Subscriptions renew automatically until you cancel in the Lemon Squeezy customer portal (linked from Settings when available) or as described in your confirmation email.</li>
              <li><strong>Cancellation:</strong> Cancel before the next billing date to avoid future charges. Access typically continues until the end of the current paid period unless stated otherwise at checkout.</li>
              <li><strong>Refunds:</strong> Refund eligibility is determined by Lemon Squeezy and applicable law. Contact{' '}
                <a href={`mailto:${supportEmail}`} className="text-laro hover:underline">{supportEmail}</a>{' '}
                if you need help finding your billing portal or linking a purchase to your Laro account.</li>
              <li><strong>Price changes:</strong> We may change plan prices for new purchases. Changes for existing subscriptions follow Lemon Squeezy and any notice required by law.</li>
            </ul>

            <h3 className="text-lg font-medium text-foreground">Android and app stores</h3>
            <p className="text-muted-foreground">
              If you subscribed through Google Play or another app store, that store&apos;s terms and refund rules apply. Manage those subscriptions in the store account you used to purchase. Some Android builds may direct you to the web for new Pro purchases instead of in-app billing.
            </p>

            <h3 className="text-lg font-medium text-foreground">Legacy billing</h3>
            <p className="text-muted-foreground mb-0">
              Some older subscriptions were processed via RevenueCat, Paddle, Stripe, or similar partners. Those remain subject to the billing channel you used until they expire or you cancel there. Laro continues to honor active Pro access recorded on your account while those subscriptions remain valid.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Referrals, rewards, and admin access</h2>
            <p className="text-muted-foreground mb-0">
              Referral trials, reward redemptions, and complimentary Pro access we grant manually are discretionary program benefits, not guaranteed payment methods. We may adjust or end promotions to prevent abuse. Owner or admin-granted access does not create a recurring billing relationship with Lemon Squeezy unless you separately subscribe.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">AI features</h2>
            <p className="text-muted-foreground mb-0">
              AI-generated meal plans, imports, chat replies, and similar outputs may be inaccurate or incomplete. They are not dietary, medical, or safety advice. You are responsible for verifying allergens, cooking temperatures, and suitability for your household before relying on suggestions.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Disclaimers</h2>
            <p className="text-muted-foreground mb-0">
              THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; WITHOUT WARRANTIES OF ANY KIND, WHETHER EXPRESS OR IMPLIED, INCLUDING IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE. SOME JURISDICTIONS DO NOT ALLOW CERTAIN WARRANTY EXCLUSIONS; IN THOSE CASES, OUR LIABILITY IS LIMITED TO THE MAXIMUM EXTENT PERMITTED BY LAW.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Limitation of liability</h2>
            <p className="text-muted-foreground mb-0">
              TO THE MAXIMUM EXTENT PERMITTED BY LAW, LARO AND ITS OPERATORS WILL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, DATA, OR GOODWILL, ARISING FROM YOUR USE OF THE SERVICE. OUR TOTAL LIABILITY FOR ANY CLAIM RELATING TO THE SERVICE IS LIMITED TO THE GREATER OF (A) THE AMOUNT YOU PAID US FOR LARO PRO IN THE TWELVE MONTHS BEFORE THE CLAIM OR (B) GBP £10, EXCEPT WHERE LIABILITY CANNOT BE LIMITED BY LAW (FOR EXAMPLE DEATH OR PERSONAL INJURY CAUSED BY NEGLIGENCE, OR FRAUD).
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Termination</h2>
            <p className="text-muted-foreground mb-0">
              You may delete your account from Settings. We may suspend or terminate access if you breach these Terms or if we discontinue the Service. Sections that by their nature should survive (including billing obligations already incurred, disclaimers, and limitations of liability) survive termination.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Changes</h2>
            <p className="text-muted-foreground mb-0">
              We may update these Terms from time to time. We will revise the &quot;Last updated&quot; date at the top of this page. Continued use after changes means you accept the updated Terms. Material changes may also be highlighted in the app or by email when appropriate.
            </p>
          </section>

          <section className="bg-card rounded-2xl p-6 border border-border">
            <h2 className="text-xl font-semibold text-foreground mt-0">Contact</h2>
            <p className="text-muted-foreground mb-0">
              Questions about these Terms or billing:
            </p>
            <div className="flex items-center gap-3 text-muted-foreground mt-3">
              <Mail className="w-5 h-5 text-laro" />
              <a href={`mailto:${supportEmail}`} className="text-laro hover:underline">{supportEmail}</a>
            </div>
          </section>
        </div>
      </main>

      <footer className="border-t border-border bg-card/50 mt-12">
        <div className="container mx-auto px-4 py-8 text-center text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} Laro. All rights reserved.</p>
          <div className="flex justify-center gap-6 mt-4">
            <Link to="/" className="hover:text-foreground transition-colors">Home</Link>
            <Link to="/terms-of-service" className="hover:text-foreground transition-colors">Terms of Service</Link>
            <Link to="/privacy-policy" className="hover:text-foreground transition-colors">Privacy Policy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default TermsOfService;
