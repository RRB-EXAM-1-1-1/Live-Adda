import React from 'react';
import { useNavigate } from 'react-router-dom';
import { CreditCard, Clock, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { mockPlans, mockUserData } from '../mock';

const Billings = () => {
  const navigate = useNavigate();

  const transactions = [
    { id: 1, date: '2024-01-20', plan: 'Monthly Plan', amount: 79.99, status: 'Paid' },
    { id: 2, date: '2023-12-20', plan: 'Monthly Plan', amount: 79.99, status: 'Paid' },
    { id: 3, date: '2023-11-20', plan: 'Monthly Plan', amount: 79.99, status: 'Paid' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Billings & Plans</h1>
        <p className="text-gray-400">Manage your subscription and billing information</p>
      </div>

      {/* Current Plan */}
      <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-2xl p-6 text-white">
        <div className="flex items-start justify-between mb-6">
          <div>
            <p className="text-blue-100 mb-1">Current Plan</p>
            <h2 className="text-3xl font-bold mb-2">Monthly Plan</h2>
            <p className="text-blue-100">$79.99 / month</p>
          </div>
          <div className="bg-white/20 backdrop-blur-sm px-4 py-2 rounded-full">
            <span className="font-semibold">Active</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
            <p className="text-blue-100 text-sm mb-1">Next Billing Date</p>
            <p className="font-semibold">February 20, 2024</p>
          </div>
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
            <p className="text-blue-100 text-sm mb-1">Payment Method</p>
            <p className="font-semibold">•••• 4242</p>
          </div>
        </div>

        <div className="flex space-x-3">
          <Button 
            onClick={() => navigate('/#pricing')}
            className="bg-white text-blue-600 hover:bg-blue-50"
          >
            Change Plan
          </Button>
          <Button 
            variant="outline"
            className="border-white/30 text-white hover:bg-white/10"
          >
            Update Payment Method
          </Button>
        </div>
      </div>

      {/* Available Plans */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6 flex items-center">
          <CreditCard className="w-5 h-5 mr-2 text-blue-500" />
          Available Plans
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {mockPlans.map((plan) => (
            <div key={plan.id} className="bg-gray-700/30 rounded-xl p-6 border border-gray-600 hover:border-blue-500 transition-all">
              {plan.badge && (
                <span className="inline-block px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-full mb-3">
                  {plan.badge}
                </span>
              )}
              <h3 className="text-xl font-bold text-white mb-2">{plan.name}</h3>
              <div className="mb-4">
                <span className="text-3xl font-bold text-white">${plan.price}</span>
                <span className="text-gray-400"> / {plan.duration}</span>
              </div>
              <ul className="space-y-2 mb-6">
                {plan.features.slice(0, 3).map((feature, idx) => (
                  <li key={idx} className="text-sm text-gray-300 flex items-center">
                    <CheckCircle className="w-4 h-4 text-emerald-500 mr-2" />
                    {feature}
                  </li>
                ))}
              </ul>
              <Button 
                className="w-full bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
                disabled={plan.id === 'monthly'}
              >
                {plan.id === 'monthly' ? 'Current Plan' : 'Upgrade'}
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Transaction History */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6 flex items-center">
          <Clock className="w-5 h-5 mr-2 text-blue-500" />
          Transaction History
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 font-medium pb-3">Date</th>
                <th className="text-left text-gray-400 font-medium pb-3">Description</th>
                <th className="text-right text-gray-400 font-medium pb-3">Amount</th>
                <th className="text-right text-gray-400 font-medium pb-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((transaction) => (
                <tr key={transaction.id} className="border-b border-gray-700/50">
                  <td className="py-4 text-gray-300">{transaction.date}</td>
                  <td className="py-4 text-white">{transaction.plan}</td>
                  <td className="py-4 text-right text-white font-medium">${transaction.amount}</td>
                  <td className="py-4 text-right">
                    <span className="inline-block px-3 py-1 bg-emerald-500/20 text-emerald-400 text-xs font-semibold rounded-full">
                      {transaction.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Billings;
