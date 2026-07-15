import React, { useState } from 'react';
import { Button } from './ui/button';
import { Check } from 'lucide-react';
import { mockPlans } from '../mock';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const Pricing = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [hoveredPlan, setHoveredPlan] = useState(null);

  const handlePurchase = (planId) => {
    if (isAuthenticated) {
      navigate('/dashboard/billings');
    } else {
      navigate('/register');
    }
  };

  return (
    <section id="pricing" className="py-24 bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Simple, Transparent
            <span className="block mt-2 bg-gradient-to-r from-blue-600 to-blue-700 bg-clip-text text-transparent">
              Pricing Plans
            </span>
          </h2>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Choose the plan that fits your streaming needs. No hidden fees, cancel anytime.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
          {mockPlans.map((plan, index) => {
            const isPopular = plan.badge === 'Popular';
            const isBestValue = plan.badge === 'Best Value';
            const isHovered = hoveredPlan === plan.id;

            return (
              <div
                key={plan.id}
                className={`relative bg-white rounded-2xl shadow-lg hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 ${
                  isPopular || isBestValue ? 'md:scale-105 border-2 border-blue-500' : ''
                }`}
                onMouseEnter={() => setHoveredPlan(plan.id)}
                onMouseLeave={() => setHoveredPlan(null)}
                style={{ animationDelay: `${index * 100}ms` }}
              >
                {/* Badge */}
                {plan.badge && (
                  <div className={`absolute -top-4 left-1/2 transform -translate-x-1/2 px-4 py-1 rounded-full text-sm font-bold text-white ${
                    isBestValue ? 'bg-gradient-to-r from-emerald-500 to-emerald-600' : 'bg-gradient-to-r from-blue-500 to-blue-600'
                  }`}>
                    {plan.badge}
                  </div>
                )}

                <div className="p-8">
                  {/* Plan Name */}
                  <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                  <p className="text-gray-500 mb-6">{plan.duration}</p>

                  {/* Price */}
                  <div className="mb-8">
                    <span className="text-5xl font-bold text-gray-900">{plan.price}</span>
                  </div>

                  {/* Features */}
                  <ul className="space-y-4 mb-8">
                    {plan.features.map((feature, idx) => (
                      <li key={idx} className="flex items-start">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center mr-3 mt-0.5">
                          <Check className="w-4 h-4 text-emerald-600" />
                        </div>
                        <span className="text-gray-700">{feature}</span>
                      </li>
                    ))}
                  </ul>

                  {/* CTA Button */}
                  <Button
                    onClick={() => handlePurchase(plan.id)}
                    data-testid={`landing-buy-${plan.id}`}
                    className={`w-full py-6 text-lg font-semibold rounded-xl transition-all ${
                      isPopular || isBestValue
                        ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white shadow-md hover:shadow-xl'
                        : 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-md hover:shadow-xl'
                    } ${isHovered ? 'transform scale-105' : ''}`}
                  >
                    Buy Now
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};
