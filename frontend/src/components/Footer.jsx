import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Radio, Twitter, Youtube, Linkedin, Mail, Phone } from 'lucide-react';

export const Footer = () => {
  const currentYear = new Date().getFullYear();
  const navigate = useNavigate();
  const location = useLocation();

  // Smooth scroll to a landing-page section from the footer, no matter which
  // route we're on. Same pattern the navbar uses.
  const goToSection = (sectionId) => (e) => {
    e.preventDefault();
    if (location.pathname === '/') {
      const el = document.getElementById(sectionId);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      navigate(`/#${sectionId}`);
    }
  };

  return (
    <footer className="bg-gradient-to-br from-gray-900 to-gray-800 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          {/* Brand */}
          <div className="col-span-1">
            <div className="flex items-center space-x-2 mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center">
                <Radio className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-bold">Live Adda</span>
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              Stream your content 24/7 on YouTube without any PC or laptop. Join thousands of creators already streaming.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="font-bold text-lg mb-4">Quick Links</h3>
            <ul className="space-y-2">
              <li>
                <Link to="/" data-testid="footer-home-link" className="text-gray-400 hover:text-white transition-colors">Home</Link>
              </li>
              <li>
                <a href="/#features" onClick={goToSection('features')} data-testid="footer-features-link" className="text-gray-400 hover:text-white transition-colors cursor-pointer">Features</a>
              </li>
              <li>
                <a href="/#pricing" onClick={goToSection('pricing')} data-testid="footer-pricing-link" className="text-gray-400 hover:text-white transition-colors cursor-pointer">Pricing</a>
              </li>
              <li>
                <Link to="/login" data-testid="footer-login-link" className="text-gray-400 hover:text-white transition-colors">Login</Link>
              </li>
              <li>
                <Link to="/terms" data-testid="footer-terms-link" className="text-gray-400 hover:text-white transition-colors">Terms of Service</Link>
              </li>
              <li>
                <Link to="/privacy" data-testid="footer-privacy-link" className="text-gray-400 hover:text-white transition-colors">Privacy Policy</Link>
              </li>
            </ul>
          </div>

          {/* Support / Contact — real details */}
          <div>
            <h3 className="font-bold text-lg mb-4">Support & Contact</h3>
            <ul className="space-y-3">
              <li>
                <Link to="/contact" data-testid="footer-help-link" className="text-gray-400 hover:text-white transition-colors">Help Center</Link>
              </li>
              <li>
                <Link to="/contact" data-testid="footer-contact-link" className="text-gray-400 hover:text-white transition-colors">Contact Us</Link>
              </li>
              <li>
                <a href="mailto:support@liveadda.org" data-testid="footer-email-link" className="text-gray-400 hover:text-white transition-colors flex items-center gap-2 text-sm">
                  <Mail className="w-4 h-4 flex-shrink-0" />
                  <span>support@liveadda.org</span>
                </a>
              </li>
              <li>
                <a href="tel:+918796533673" data-testid="footer-phone-link" className="text-gray-400 hover:text-white transition-colors flex items-center gap-2 text-sm">
                  <Phone className="w-4 h-4 flex-shrink-0" />
                  <span>+91 87965 33673</span>
                </a>
              </li>
              <li>
                <a href="https://wa.me/918796533673" target="_blank" rel="noopener noreferrer" data-testid="footer-whatsapp-link" className="text-gray-400 hover:text-white transition-colors text-sm">
                  Chat on WhatsApp →
                </a>
              </li>
            </ul>
          </div>

          {/* Social */}
          <div>
            <h3 className="font-bold text-lg mb-4">Follow Us</h3>
            <div className="flex space-x-4">
              <a href="https://liveadda.org" data-testid="footer-social-twitter" aria-label="Twitter" className="w-10 h-10 rounded-lg bg-gray-800 hover:bg-blue-600 flex items-center justify-center transition-colors">
                <Twitter className="w-5 h-5" />
              </a>
              <a href="https://liveadda.org" data-testid="footer-social-youtube" aria-label="YouTube" className="w-10 h-10 rounded-lg bg-gray-800 hover:bg-red-600 flex items-center justify-center transition-colors">
                <Youtube className="w-5 h-5" />
              </a>
              <a href="https://liveadda.org" data-testid="footer-social-linkedin" aria-label="LinkedIn" className="w-10 h-10 rounded-lg bg-gray-800 hover:bg-blue-700 flex items-center justify-center transition-colors">
                <Linkedin className="w-5 h-5" />
              </a>
            </div>
            <p className="text-gray-500 text-xs mt-4">
              Follow us for product updates, tips and creator stories.
            </p>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="border-t border-gray-700 pt-8 flex flex-col sm:flex-row justify-between items-center gap-2">
          <p className="text-gray-400 text-sm">
            © {currentYear} Live Adda. All rights reserved.
          </p>
          <p className="text-gray-500 text-xs">
            <Link to="/terms" className="hover:text-gray-300">Terms</Link>
            <span className="mx-2">·</span>
            <Link to="/privacy" className="hover:text-gray-300">Privacy</Link>
            <span className="mx-2">·</span>
            <Link to="/contact" className="hover:text-gray-300">Contact</Link>
          </p>
        </div>
      </div>
    </footer>
  );
};
