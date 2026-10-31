import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CreditCard, Clock, CheckCircle, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { razorpayAPI, billingAPI, slotsAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

const PLANS = [
  {
    id: 'daily',
    name: 'Daily',
    price: 35,
    duration: '24 Hours',
    badge: null,
    features: ['+1 Live Streaming Slot', '24/7 Continuous Stream', '2GB Video Storage', 'Standard Support']
  },
  {
    id: 'weekly',
    name: 'Weekly',
    price: 199,
    duration: '7 Days',
    badge: 'Popular',
    features: ['+1 Live Streaming Slot', '24/7 Continuous Stream', '2GB Video Storage', 'Priority Support']
  },
  {
    id: 'monthly',
    name: 'Monthly',
    price: 599,
    duration: '30 Days',
    badge: 'Best Value',
    features: ['+1 Live Streaming Slot', '24/7 Continuous Stream', '2GB Video Storage', 'Priority Support', 'Advanced Analytics']
  }
];

const PLAN_LABEL = { daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', lifetime: 'Lifetime' };

const Billings = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [currentPlan, setCurrentPlan] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [processingPlan, setProcessingPlan] = useState(null);
  const [pollingPayment, setPollingPayment] = useState(false);

  const hasActivePlan = user?.plan && user?.plan_expires_at;

  // Renew flow: /dashboard/billings?renew=<slot_id>  (from My Slots → Renew)
  const renewSlotId = searchParams.get('renew');
  const [renewSlot, setRenewSlot] = useState(null);

  useEffect(() => {
    loadBillingData();
    syncPendingPayments(false);
    if (renewSlotId) {
      slotsAPI.list().then(({ data }) => {
        const s = data?.slots?.find((x) => x.slot_id === renewSlotId);
        if (s) setRenewSlot(s); else toast.error('That slot was not found. You can buy a new slot below.');
      });
    }
  }, []);

  const clearRenew = () => { setRenewSlot(null); setSearchParams({}); };

  const loadBillingData = async () => {
    const planResult = await billingAPI.getCurrentPlan();
    if (planResult.data) setCurrentPlan(planResult.data);

    const txnResult = await billingAPI.getTransactions();
    if (txnResult.data) setTransactions(txnResult.data);
  };

  const [syncing, setSyncing] = useState(false);
  const syncPendingPayments = async (manual) => {
    setSyncing(true);
    const { data } = await razorpayAPI.syncPayments();
    setSyncing(false);
    if (data?.activated > 0) {
      toast.success('🎉 Payment confirmed! Your plan is now active.');
      await refreshUser();
      await loadBillingData();
    } else if (manual) {
      toast.info(data?.checked ? 'Payment not confirmed by Razorpay yet. If money was deducted, it usually confirms within a few minutes.' : 'No pending payments.');
    }
  };

  const handlePurchase = async (planId, slotToRenew = null) => {
    if (!window.Razorpay) {
      toast.error('Payment gateway is still loading. Please try again in a moment.');
      return;
    }
    setProcessingPlan(slotToRenew ? `renew-${slotToRenew}` : planId);
    const { data, error } = await razorpayAPI.createOrder(planId, slotToRenew);

    if (!data) {
      setProcessingPlan(null);
      toast.error(error || 'Failed to create order');
      return;
    }

    const options = {
      key: data.key_id,
      amount: data.amount,
      currency: data.currency,
      name: 'Live Adda',
      description: slotToRenew ? `Renew slot — ${data.plan_name}` : `New slot — ${data.plan_name}`,
      order_id: data.order_id,
      prefill: data.prefill,
      theme: { color: '#059669' },
      handler: async (response) => {
        setPollingPayment(true);
        const verify = await razorpayAPI.verifyPayment({
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature
        });
        setPollingPayment(false);
        setProcessingPlan(null);
        if (verify.data) {
          toast.success(slotToRenew ? '🎉 Slot renewed successfully!' : '🎉 Payment successful! Your new slot is ready.');
          await refreshUser();
          await loadBillingData();
          if (slotToRenew) { clearRenew(); navigate('/dashboard/live-slot'); }
        } else {
          toast.error(verify.error || 'Payment verification failed');
        }
      },
      modal: {
        ondismiss: () => {
          setProcessingPlan(null);
          toast.info('Payment window closed. Checking payment status…');
          // UPI-app / tab-switch flows often complete the payment but never
          // return to the handler — ask the server to confirm with Razorpay.
          setTimeout(() => { syncPendingPayments(false); loadBillingData(); }, 4000);
        }
      }
    };

    const rzp = new window.Razorpay(options);
    rzp.on('payment.failed', (resp) => {
      setProcessingPlan(null);
      toast.error(resp.error?.description || 'Payment failed');
    });
    rzp.open();
  };

  const getRemainingDays = () => {
    if (!user?.plan_expires_at) return 0;
    const expiry = new Date(user.plan_expires_at);
    const now = new Date();
    const days = Math.ceil((expiry - now) / (1000 * 60 * 60 * 24));
    return days > 0 ? days : 0;
  };

  return (
    <div className="space-y-8" data-testid="billings-page">
      {/* Payment Processing Overlay */}
      {pollingPayment && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center" data-testid="payment-processing-overlay">
          <div className="bg-gray-800 rounded-2xl p-8 text-center max-w-sm">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin mx-auto mb-4" />
            <h3 className="text-white text-xl font-bold mb-2">Processing Payment</h3>
            <p className="text-gray-400">Please wait while we confirm your payment...</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Billings & Plans</h1>
        <p className="text-gray-400">Manage your subscription and billing information</p>
      </div>

      {/* Active Plans & Slots (slot-stacking) */}
      {user?.active_plans && user.active_plans.length > 0 && (
        <div
          className="bg-gray-800/60 backdrop-blur-lg rounded-2xl p-6 border border-emerald-500/20"
          data-testid="active-plans-panel"
        >
          <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
            <h2 className="text-xl font-bold text-white flex items-center">
              <CheckCircle className="w-5 h-5 mr-2 text-emerald-400" />
              Your Active Plans
            </h2>
            <div
              data-testid="total-slots-badge"
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/30"
            >
              <span className="text-emerald-300 font-semibold text-sm">
                {user.stream_slots} concurrent stream slot{user.stream_slots !== 1 ? 's' : ''} unlocked
              </span>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {user.active_plans.map((p, i) => {
              const exp = new Date(p.expires_at);
              const days = Math.max(0, Math.ceil((exp - new Date()) / (1000 * 60 * 60 * 24)));
              return (
                <div
                  key={`${p.plan_id}-${i}`}
                  data-testid={`active-plan-${p.plan_id}`}
                  className="bg-gray-900/50 rounded-xl p-4 border border-gray-700"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-white font-semibold">{PLAN_LABEL[p.plan_id] || p.plan_id}</span>
                    <span className="text-emerald-400 text-xs font-semibold">+1 slot</span>
                  </div>
                  <p className="text-gray-400 text-xs">Expires in {days} day{days !== 1 ? 's' : ''} · {exp.toLocaleDateString()}</p>
                </div>
              );
            })}
          </div>
          <p className="text-gray-500 text-xs mt-4">
            💡 Each purchase below adds one more slot. To extend an existing slot, use <b>Renew</b> on the My Slots page.
          </p>
        </div>
      )}

      {/* Current Plan */}
      {hasActivePlan ? (
        <div className="bg-gradient-to-br from-blue-600 to-blue-700 rounded-2xl p-6 text-white" data-testid="current-plan-card">
          <div className="flex items-start justify-between mb-6">
            <div>
              <p className="text-blue-100 mb-1">Current Plan</p>
              <h2 className="text-3xl font-bold mb-2">{currentPlan?.plan_name || user?.plan} Plan</h2>
              <p className="text-blue-100">₹{currentPlan?.price} </p>
            </div>
            <div className="bg-white/20 backdrop-blur-sm px-4 py-2 rounded-full">
              <span className="font-semibold">Active</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
              <p className="text-blue-100 text-sm mb-1">Plan Expires In</p>
              <p className="font-semibold">{getRemainingDays()} days</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4">
              <p className="text-blue-100 text-sm mb-1">Expiry Date</p>
              <p className="font-semibold">
                {user?.plan_expires_at ? new Date(user.plan_expires_at).toLocaleDateString() : 'N/A'}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-6" data-testid="no-active-plan-card">
          <h3 className="text-white text-xl font-bold mb-2">No Active Plan</h3>
          <p className="text-gray-400">Choose a plan below to start uploading videos and streaming 24/7.</p>
        </div>
      )}

      {/* Renew a specific slot */}
      {renewSlot && (
        <div className="rounded-2xl p-6 border border-amber-500/40 bg-amber-500/10" data-testid="renew-slot-banner">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-amber-300 text-xs font-semibold uppercase tracking-wider mb-1">Renewing slot</p>
              <h2 className="text-2xl font-bold text-white">{renewSlot.name}</h2>
              <p className="text-gray-300 text-sm mt-1">
                {renewSlot.plan_name} plan · {renewSlot.status === 'expired'
                  ? 'expired — renewing restarts it from today'
                  : `expires ${new Date(renewSlot.expires_at).toLocaleString()} — renewing adds time on top`}
              </p>
              <p className="text-gray-400 text-xs mt-2">Your slot name stays the same. Pick how long to extend it:</p>
            </div>
            <Button variant="ghost" className="text-gray-400 hover:text-white" onClick={clearRenew} data-testid="renew-cancel-btn">Cancel</Button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4">
            {PLANS.map((p) => (
              <Button key={p.id} disabled={!!processingPlan} onClick={() => handlePurchase(p.id, renewSlot.slot_id)}
                data-testid={`renew-with-${p.id}`}
                className={`h-auto py-3 flex-col ${p.id === renewSlot.plan_id ? 'bg-amber-500 hover:bg-amber-600 text-black' : 'bg-gray-700 hover:bg-gray-600 text-white'}`}>
                <span className="font-bold">+{p.duration}</span>
                <span className="text-xs opacity-80">₹{p.price}{p.id === renewSlot.plan_id ? ' · same plan' : ''}</span>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Available Plans */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700" id="plans">
        <h2 className="text-xl font-bold text-white mb-1 flex items-center">
          <CreditCard className="w-5 h-5 mr-2 text-blue-500" />
          Add a New Slot
        </h2>
        <p className="text-gray-400 text-sm mb-6">Every purchase adds one more live slot. Buy as many as you need — 1, 5 or 50.</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {PLANS.map((plan) => {
            const isCurrent = hasActivePlan && user?.plan === plan.id;
            const isProcessing = processingPlan === plan.id;
            
            return (
              <div 
                key={plan.id} 
                className={`bg-gray-700/30 rounded-xl p-6 border transition-all ${
                  plan.badge ? 'border-blue-500' : 'border-gray-600 hover:border-blue-500'
                }`}
                data-testid={`plan-card-${plan.id}`}
              >
                {plan.badge && (
                  <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full mb-3 ${
                    plan.badge === 'Best Value' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'
                  }`}>
                    {plan.badge}
                  </span>
                )}
                <h3 className="text-xl font-bold text-white mb-2">{plan.name}</h3>
                <div className="mb-4">
                  <span className="text-3xl font-bold text-white">₹{plan.price}</span>
                  <span className="text-gray-400"> / {plan.duration}</span>
                </div>
                <ul className="space-y-2 mb-6">
                  {plan.features.map((feature, idx) => (
                    <li key={idx} className="text-sm text-gray-300 flex items-center">
                      <CheckCircle className="w-4 h-4 text-emerald-500 mr-2 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                <Button 
                  className="w-full bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
                  disabled={isProcessing}
                  onClick={() => handlePurchase(plan.id)}
                  data-testid={`buy-plan-${plan.id}`}
                >
                  {isProcessing ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Processing...</>
                  ) : isCurrent ? (
                    'Add Another Slot'
                  ) : (
                    'Buy Now'
                  )}
                </Button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Transaction History */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6 flex items-center justify-between">
          <span className="flex items-center"><Clock className="w-5 h-5 mr-2 text-blue-500" />Transaction History</span>
          {transactions.some((t) => t.payment_status !== 'paid') && (
            <Button size="sm" variant="outline" disabled={syncing} onClick={() => syncPendingPayments(true)}
              className="border-amber-500/50 text-amber-300 hover:bg-amber-500/10" data-testid="check-payment-status-btn">
              {syncing ? 'Checking…' : 'Check pending payment'}
            </Button>
          )}
        </h2>

        {transactions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left text-gray-400 font-medium pb-3">Date</th>
                  <th className="text-left text-gray-400 font-medium pb-3">Plan</th>
                  <th className="text-right text-gray-400 font-medium pb-3">Amount</th>
                  <th className="text-right text-gray-400 font-medium pb-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((txn) => (
                  <tr key={txn.transaction_id} className="border-b border-gray-700/50">
                    <td className="py-4 text-gray-300">{new Date(txn.created_at).toLocaleDateString()}</td>
                    <td className="py-4 text-white capitalize">{txn.plan_id} Plan</td>
                    <td className="py-4 text-right text-white font-medium">{txn.currency === 'INR' ? '₹' : '$'}{txn.amount}</td>
                    <td className="py-4 text-right">
                      <span className={`inline-block px-3 py-1 text-xs font-semibold rounded-full ${
                        txn.payment_status === 'paid' 
                          ? 'bg-emerald-500/20 text-emerald-400' 
                          : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {txn.payment_status === 'paid' ? 'Paid' : 'Pending'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-400 text-center py-4">No transactions yet</p>
        )}
      </div>
    </div>
  );
};

export default Billings;
