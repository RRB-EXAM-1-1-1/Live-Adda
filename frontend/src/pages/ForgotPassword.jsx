import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Radio, Mail, Phone, Lock, Eye, EyeOff, ArrowLeft, CheckCircle2 } from 'lucide-react';
import api from '../services/api';
import { toast } from 'sonner';

/**
 * 3-step password reset:
 *   1. Pick channel (email / mobile) + enter email → send OTP
 *   2. Enter 6-digit OTP + new password → submit
 *   3. Success screen → link back to /login
 *
 * The backend always returns a generic "if that email exists" response, so we
 * NEVER surface "email not found" to the caller. We advance to step 2 unconditionally.
 */
const ForgotPassword = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [channel, setChannel] = useState('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const sendOtp = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim()) { setError('Please enter your email'); return; }
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email: email.trim(), channel });
      toast.success(channel === 'email'
        ? 'Check your inbox for the 6-digit code'
        : 'A code has been sent to your registered mobile');
      setStep(2);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not send code. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const submitReset = async (e) => {
    e.preventDefault();
    setError('');
    if (!/^\d{6}$/.test(otp)) { setError('Enter the 6-digit code'); return; }
    if (newPassword.length < 6) { setError('Password must be at least 6 characters'); return; }
    setLoading(true);
    try {
      await api.post('/auth/reset-password', {
        email: email.trim(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setStep(3);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Reset failed. Check the code and try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center space-x-2 mb-6">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center">
              <Radio className="w-7 h-7 text-white" />
            </div>
            <span className="text-2xl font-bold text-gray-900">Live Adda</span>
          </Link>
          <h2 className="text-3xl font-bold text-gray-900 mb-2">Reset your password</h2>
          <p className="text-gray-600">
            {step === 1 && 'Send a one-time code to your email or mobile.'}
            {step === 2 && `We sent a 6-digit code to your ${channel === 'email' ? 'email' : 'mobile'}.`}
            {step === 3 && 'Password updated successfully.'}
          </p>
        </div>

        <div className="bg-white/80 backdrop-blur-lg rounded-2xl shadow-xl p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm" data-testid="forgot-error">
              {error}
            </div>
          )}

          {step === 1 && (
            <form onSubmit={sendOtp} className="space-y-5" data-testid="forgot-step-1">
              <div>
                <Label className="text-gray-700 font-medium mb-2 block">Where should we send the code?</Label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setChannel('email')}
                    data-testid="forgot-channel-email"
                    className={`p-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                      channel === 'email'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    <Mail className="w-5 h-5 mx-auto mb-1" />
                    Email
                  </button>
                  <button
                    type="button"
                    onClick={() => setChannel('sms')}
                    data-testid="forgot-channel-sms"
                    className={`p-3 rounded-lg border-2 text-sm font-semibold transition-all ${
                      channel === 'sms'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 text-gray-600 hover:border-gray-300'
                    }`}
                  >
                    <Phone className="w-5 h-5 mx-auto mb-1" />
                    Mobile
                  </button>
                </div>
                {channel === 'sms' && (
                  <p className="text-xs text-amber-600 mt-2">
                    SMS delivery goes through our support desk right now — you may need to contact support if the code doesn't arrive.
                  </p>
                )}
              </div>

              <div>
                <Label htmlFor="email" className="text-gray-700 font-medium">Registered Email</Label>
                <div className="relative mt-1">
                  <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); setError(''); }}
                    data-testid="forgot-email-input"
                    className="pl-10 py-6 bg-gray-50 border-gray-200 focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                data-testid="forgot-send-otp-btn"
                className="w-full py-6 text-base font-semibold bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
              >
                {loading ? 'Sending…' : 'Send code'}
              </Button>
            </form>
          )}

          {step === 2 && (
            <form onSubmit={submitReset} className="space-y-5" data-testid="forgot-step-2">
              <div>
                <Label htmlFor="otp" className="text-gray-700 font-medium">6-digit code</Label>
                <Input
                  id="otp"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={otp}
                  onChange={(e) => { setOtp(e.target.value.replace(/\D/g, '')); setError(''); }}
                  data-testid="forgot-otp-input"
                  className="mt-1 py-6 text-center text-2xl tracking-widest font-mono bg-gray-50 border-gray-200 focus:border-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">Sent to {email}. Code expires in 15 minutes.</p>
              </div>

              <div>
                <Label htmlFor="newpw" className="text-gray-700 font-medium">New password</Label>
                <div className="relative mt-1">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <Input
                    id="newpw"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="At least 6 characters"
                    value={newPassword}
                    onChange={(e) => { setNewPassword(e.target.value); setError(''); }}
                    data-testid="forgot-newpw-input"
                    className="pl-10 pr-10 py-6 bg-gray-50 border-gray-200 focus:border-blue-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              <Button
                type="submit"
                disabled={loading}
                data-testid="forgot-reset-btn"
                className="w-full py-6 text-base font-semibold bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
              >
                {loading ? 'Resetting…' : 'Reset password'}
              </Button>

              <button
                type="button"
                onClick={() => { setStep(1); setError(''); }}
                className="w-full text-sm text-gray-500 hover:text-gray-700 flex items-center justify-center gap-1"
                data-testid="forgot-back-btn"
              >
                <ArrowLeft className="w-4 h-4" /> Change email or channel
              </button>
            </form>
          )}

          {step === 3 && (
            <div className="text-center space-y-4" data-testid="forgot-step-3">
              <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto" />
              <p className="text-gray-700">Your password has been updated.</p>
              <Button
                onClick={() => navigate('/login')}
                data-testid="forgot-goto-login-btn"
                className="w-full py-6 text-base font-semibold bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
              >
                Continue to sign in
              </Button>
            </div>
          )}

          {step !== 3 && (
            <p className="mt-6 text-center text-sm text-gray-600">
              Remembered it?{' '}
              <Link to="/login" className="font-medium text-blue-600 hover:text-blue-700">Sign in</Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
