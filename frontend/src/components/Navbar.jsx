import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { Radio } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export const Navbar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, user } = useAuth();
  const isLoggedIn = isAuthenticated;

  // Smooth-scroll to a landing-page section. If we're already on "/" just
  // scroll; otherwise route to "/#section" and let LandingPage's hash-effect
  // handle the scroll after mount.
  const scrollToSection = (sectionId) => (e) => {
    e.preventDefault();
    if (location.pathname === '/') {
      const el = document.getElementById(sectionId);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      navigate(`/#${sectionId}`);
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-lg border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <Link to="/" className="flex items-center space-x-2 group">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center transform group-hover:scale-105 transition-transform">
              <Radio className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold text-gray-900">Live Adda</span>
          </Link>

          <div className="flex items-center space-x-3 sm:space-x-6">
            <a
              href="/#features"
              onClick={scrollToSection('features')}
              data-testid="navbar-features-link"
              className="hidden md:inline text-gray-600 hover:text-gray-900 transition-colors font-medium cursor-pointer"
            >
              Features
            </a>
            <a
              href="/#pricing"
              onClick={scrollToSection('pricing')}
              data-testid="navbar-pricing-link"
              className="hidden md:inline text-gray-600 hover:text-gray-900 transition-colors font-medium cursor-pointer"
            >
              Pricing
            </a>
            
            {isLoggedIn ? (
              <div className="flex items-center space-x-3">
                <span className="hidden sm:inline text-sm text-gray-600">Hello, {user?.name?.split(' ')[0]}</span>
                <Button 
                  onClick={() => navigate('/dashboard')}
                  data-testid="navbar-dashboard-btn"
                  className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-md hover:shadow-lg transition-all"
                >
                  Dashboard
                </Button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 sm:space-x-3">
                <Button 
                  variant="ghost" 
                  onClick={() => navigate('/login')}
                  data-testid="navbar-login-btn"
                  className="text-gray-600 hover:text-gray-900 px-3 sm:px-4"
                >
                  Login
                </Button>
                <Button 
                  onClick={() => navigate('/register')}
                  data-testid="navbar-get-started-btn"
                  className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-md hover:shadow-lg transition-all px-3 sm:px-4"
                >
                  Get Started
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};
