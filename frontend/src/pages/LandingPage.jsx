import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { Hero } from '../components/Hero';
import { Features } from '../components/Features';
import { Pricing } from '../components/Pricing';
import { Footer } from '../components/Footer';

const LandingPage = () => {
  const { hash } = useLocation();

  // When we land with a `#features` or `#pricing` hash (e.g. from a footer/navbar
  // link on another page), scroll to the section once the DOM has rendered.
  useEffect(() => {
    if (!hash) return;
    const id = hash.replace('#', '');
    // Defer a tick so all sections have mounted before we query for them.
    const t = setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => clearTimeout(t);
  }, [hash]);

  return (
    <div className="min-h-screen">
      <Navbar />
      <Hero />
      <Features />
      <Pricing />
      <Footer />
    </div>
  );
};

export default LandingPage;
