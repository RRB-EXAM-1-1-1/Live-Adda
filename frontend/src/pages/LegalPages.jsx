import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Footer } from '../components/Footer';
import { Radio, ArrowLeft } from 'lucide-react';

/**
 * Reusable layout for static legal / info pages. Each concrete page below
 * just declares its title, effective date, and sections — no boilerplate.
 */
const LegalLayout = ({ title, effectiveDate, children, testid }) => {
  useEffect(() => { window.scrollTo(0, 0); }, []);
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      <Navbar />
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-28 pb-16" data-testid={testid}>
        <Link to="/" className="inline-flex items-center gap-2 text-sm text-blue-700 hover:text-blue-900 mb-6">
          <ArrowLeft className="w-4 h-4" /> Back to home
        </Link>
        <div className="bg-white/90 backdrop-blur rounded-2xl shadow-xl p-8 sm:p-12">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center">
              <Radio className="w-6 h-6 text-white" />
            </div>
            <span className="text-lg font-semibold text-gray-700">Live Adda</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mt-4">{title}</h1>
          <p className="text-sm text-gray-500 mt-2">Effective: {effectiveDate}</p>
          <div className="prose prose-slate max-w-none mt-8 text-gray-700 leading-relaxed [&_h2]:text-xl [&_h2]:font-bold [&_h2]:text-gray-900 [&_h2]:mt-8 [&_h2]:mb-3 [&_p]:mb-4 [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-4 [&_li]:mb-1">
            {children}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export const Terms = () => (
  <LegalLayout title="Terms of Service" effectiveDate="1 July 2026" testid="terms-page">
    <p>
      Welcome to Live Adda ("we", "our", "the Service"). By creating an account, uploading a video,
      or streaming through liveadda.org you agree to these Terms of Service. Please read them carefully.
    </p>

    <h2>1. Your Account</h2>
    <p>
      You are responsible for maintaining the confidentiality of your login credentials and for all
      activity that occurs under your account. You agree to notify us immediately at
      <a href="mailto:support@liveadda.org" className="text-blue-700 underline"> support@liveadda.org </a>
      of any unauthorised use of your account. You must be at least 18 years old, or the age of legal
      majority in your jurisdiction, to use the Service.
    </p>

    <h2>2. Acceptable Content</h2>
    <p>You agree not to upload, stream, or otherwise transmit any content that:</p>
    <ul>
      <li>Infringes third-party copyright, trademark, or other intellectual-property rights;</li>
      <li>Contains material that is unlawful, obscene, defamatory, harassing, hateful, or violent;</li>
      <li>Promotes pornography, gambling, or the sale of illegal goods/services;</li>
      <li>Contains malware, viruses, or code designed to disrupt any system;</li>
      <li>Violates YouTube's Community Guidelines or Terms of Service, since the Service pushes
        your content to YouTube on your behalf.</li>
    </ul>
    <p>
      We reserve the right to remove any content and to suspend or terminate any account that violates
      this policy, without notice and without refund.
    </p>

    <h2>3. Subscription & Payments</h2>
    <p>
      Live Adda offers time-bound plans (Daily, Weekly, Monthly, etc.). Payments are processed by
      Razorpay. All plan prices are shown inclusive of applicable taxes unless stated otherwise.
      Subscription fees are non-refundable once your live stream has started, except where required
      by law. Chargeback attempts on completed streaming services may result in permanent account
      termination.
    </p>

    <h2>4. Service Availability & Storage Limits</h2>
    <p>
      We aim for 99% uptime but do not guarantee uninterrupted service. Each user account is limited
      to the storage quota associated with their active plan. Uploaded videos are automatically
      purged from our servers when a user's plan expires, when they stop their live stream, or when
      they manually delete the video. It is your responsibility to keep an original copy of anything
      you upload.
    </p>

    <h2>5. Intellectual Property</h2>
    <p>
      You retain all ownership of any content you upload. By uploading, you grant Live Adda a limited,
      non-exclusive, revocable licence to store, transcode, and transmit that content to YouTube
      solely for the purpose of providing the Service.
    </p>

    <h2>6. Limitation of Liability</h2>
    <p>
      The Service is provided "as is". To the maximum extent permitted by law, Live Adda is not liable
      for any indirect, incidental, or consequential damages arising from your use of the Service,
      including but not limited to lost viewers, lost revenue, or lost data.
    </p>

    <h2>7. Termination</h2>
    <p>
      You may cancel your account at any time from your profile. We may suspend or terminate an
      account that we reasonably believe violates these Terms, is used for fraud, or poses a risk to
      other users or to YouTube.
    </p>

    <h2>8. Changes to These Terms</h2>
    <p>
      We may update these Terms occasionally. Material changes will be announced via an in-app
      notification or by email to your registered address. Continued use of the Service after such
      changes constitutes acceptance.
    </p>

    <h2>9. Governing Law</h2>
    <p>
      These Terms are governed by the laws of India. Any dispute will be resolved in the competent
      courts of Bengaluru, Karnataka.
    </p>

    <h2>10. Contact</h2>
    <p>
      Questions about these Terms? Reach us at
      <a href="mailto:support@liveadda.org" className="text-blue-700 underline"> support@liveadda.org </a>
      or +91 87965 33673.
    </p>
  </LegalLayout>
);

export const Privacy = () => (
  <LegalLayout title="Privacy Policy" effectiveDate="1 July 2026" testid="privacy-page">
    <p>
      Live Adda ("we", "our") respects your privacy. This policy explains what data we collect,
      how we use it, and the choices you have.
    </p>

    <h2>1. Information We Collect</h2>
    <ul>
      <li><strong>Account data:</strong> your name, email, mobile number, and hashed password.</li>
      <li><strong>Payment data:</strong> transaction IDs and plan history. Card / UPI details are handled
        entirely by Razorpay — we never see or store them.</li>
      <li><strong>Uploaded content:</strong> videos you upload, plus metadata (title, resolution, codec,
        duration). Videos are stored only for as long as they are needed to serve your live stream
        and are automatically deleted when your plan expires or your stream stops.</li>
      <li><strong>Streaming logs:</strong> stream keys, YouTube channel IDs (when you connect via OAuth),
        ffmpeg process metrics, and timestamps. Retained for a maximum of 30 days for debugging.</li>
      <li><strong>Analytics:</strong> anonymised usage data through Google Analytics and PostHog
        (page views, feature clicks). IP addresses are anonymised.</li>
    </ul>

    <h2>2. How We Use Your Information</h2>
    <ul>
      <li>To provide and operate the streaming service and enforce plan limits;</li>
      <li>To send you transactional emails (password resets, plan-expiry reminders, receipts);</li>
      <li>To improve the Service and detect abuse or fraud;</li>
      <li>To comply with legal obligations.</li>
    </ul>

    <h2>3. Sharing Your Data</h2>
    <p>We do not sell your personal information. We share data only with:</p>
    <ul>
      <li><strong>Razorpay</strong> — to process payments (subject to their privacy policy);</li>
      <li><strong>YouTube (Google)</strong> — the destination platform for your live streams. You control
        the connection via YouTube OAuth and can revoke it at any time from your Google account.</li>
      <li><strong>Resend</strong> — our transactional email delivery provider;</li>
      <li><strong>Law-enforcement authorities</strong> — only when compelled by a lawful order.</li>
    </ul>

    <h2>4. Data Retention</h2>
    <p>
      Account and payment records are retained for as long as your account is active plus 7 years
      to satisfy tax and legal obligations. Uploaded videos are purged automatically when your plan
      expires or your stream ends (typically within 30 seconds). You may request full account
      deletion at
      <a href="mailto:support@liveadda.org" className="text-blue-700 underline"> support@liveadda.org </a>.
    </p>

    <h2>5. Security</h2>
    <p>
      Passwords are stored using bcrypt hashing. Traffic is encrypted end-to-end via HTTPS.
      Access to production systems is limited to authorised personnel and audited. Despite our
      efforts, no online service can guarantee absolute security — please choose a strong password
      and enable two-factor authentication on your linked YouTube account.
    </p>

    <h2>6. Your Rights</h2>
    <ul>
      <li>Access, correct, or export your personal data;</li>
      <li>Withdraw consent for optional processing at any time;</li>
      <li>Request account deletion;</li>
      <li>Object to direct marketing (we don't send any, but the right stands).</li>
    </ul>

    <h2>7. Cookies</h2>
    <p>
      We use strictly necessary cookies (session, CSRF) and anonymised analytics cookies
      (Google Analytics, PostHog). No third-party advertising cookies are set.
    </p>

    <h2>8. Children</h2>
    <p>
      The Service is not intended for children under 18. We do not knowingly collect data from minors.
    </p>

    <h2>9. Changes</h2>
    <p>
      We may update this Privacy Policy. Material changes will be communicated via email or an
      in-app notification prior to taking effect.
    </p>

    <h2>10. Contact the Privacy Team</h2>
    <p>
      Email <a href="mailto:support@liveadda.org" className="text-blue-700 underline">support@liveadda.org</a>
      &nbsp;or call +91 87965 33673.
    </p>
  </LegalLayout>
);

export const Contact = () => (
  <LegalLayout title="Contact & Help Center" effectiveDate="Always available" testid="contact-page">
    <p>
      Need a hand? We answer every message. Choose the channel that suits you.
    </p>

    <h2>Email</h2>
    <p>
      <a href="mailto:support@liveadda.org" className="text-blue-700 underline">support@liveadda.org</a><br />
      Typical response time: within 4 hours during Indian business hours.
    </p>

    <h2>Phone / WhatsApp</h2>
    <p>
      <a href="tel:+918796533673" className="text-blue-700 underline">+91 87965 33673</a><br />
      <a href="https://wa.me/918796533673" target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">
        Message us on WhatsApp →
      </a>
    </p>

    <h2>Common Questions</h2>
    <ul>
      <li><strong>My stream buffers on YouTube.</strong> Re-upload the video and wait for the "Ready"
        badge before going live. Our system pre-conforms every video for YouTube; the badge means
        it's done.</li>
      <li><strong>I forgot my password.</strong> Use the
        <Link to="/forgot-password" className="text-blue-700 underline"> Forgot password </Link>
        flow — you'll get a 6-digit code by email in ~1 minute.</li>
      <li><strong>My plan expired and my video is gone.</strong> Uploaded videos are auto-deleted once
        a plan expires. Re-subscribe and upload again to continue.</li>
      <li><strong>How many streams can I run?</strong> Your slot count equals the number of active
        plans on your account. Stacking a Monthly on top of a Daily gives you two concurrent slots.</li>
    </ul>

    <h2>Report Abuse</h2>
    <p>
      Believe someone on Live Adda is violating copyright or streaming inappropriate content?
      Email <a href="mailto:support@liveadda.org" className="text-blue-700 underline">support@liveadda.org</a>
      &nbsp;with the channel URL and a screenshot. We investigate every report within 24 hours.
    </p>
  </LegalLayout>
);
