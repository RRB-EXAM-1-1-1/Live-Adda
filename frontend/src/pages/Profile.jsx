import React, { useState } from 'react';
import { User, Mail, Lock, Save, Shield, Crown } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { useAuth } from '../contexts/AuthContext';
import api from '../services/api';
import { toast } from 'sonner';

const Profile = () => {
  const { user, refreshUser } = useAuth();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    name: user?.name || '',
    email: user?.email || '',
    mobile_number: user?.mobile_number || '',
    current_password: '',
    new_password: '',
    confirm_password: '',
  });

  const isAdmin = user?.role === 'admin' || user?.plan === 'lifetime';

  const submit = async (e) => {
    e.preventDefault();
    if (form.new_password && form.new_password !== form.confirm_password) {
      toast.error('New passwords do not match');
      return;
    }
    setSaving(true);
    try {
      const payload = {};
      if (form.name && form.name !== user.name) payload.name = form.name;
      if (form.email && form.email !== user.email) payload.email = form.email;
      if ((form.mobile_number || '') !== (user.mobile_number || '')) payload.mobile_number = form.mobile_number;
      if (form.new_password) {
        payload.current_password = form.current_password;
        payload.new_password = form.new_password;
      }
      if (Object.keys(payload).length === 0) {
        toast.info('Nothing to update');
        return;
      }
      const { data } = await api.put('/auth/profile', payload);
      toast.success(data?.message || 'Profile updated');
      await refreshUser();
      setForm({ ...form, current_password: '', new_password: '', confirm_password: '' });
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Update failed';
      toast.error(typeof msg === 'string' ? msg : 'Update failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-8" data-testid="profile-page">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Profile</h1>
        <p className="text-gray-400">Manage your account details and password</p>
      </div>

      {/* Account summary */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center">
              <User className="w-7 h-7 text-white" />
            </div>
            <div>
              <p className="text-white text-lg font-semibold" data-testid="profile-name">{user?.name}</p>
              <p className="text-gray-400 text-sm" data-testid="profile-email-display">{user?.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isAdmin && (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-amber-500/15 text-amber-300 text-xs font-semibold border border-amber-500/30">
                <Crown className="w-3.5 h-3.5" /> Lifetime · 3 slots
              </span>
            )}
            {user?.plan && !isAdmin && (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-500/15 text-emerald-300 text-xs font-semibold border border-emerald-500/30">
                <Shield className="w-3.5 h-3.5" /> {user.plan.charAt(0).toUpperCase() + user.plan.slice(1)}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Edit form */}
      <form onSubmit={submit} className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 space-y-6">
        <h2 className="text-xl font-bold text-white">Update details</h2>

        <div>
          <Label htmlFor="name" className="text-gray-300 flex items-center gap-1.5"><User className="w-4 h-4"/>Name</Label>
          <Input
            id="name" type="text" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="mt-1 bg-gray-700/50 border-gray-600 text-white"
            data-testid="profile-name-input"
          />
        </div>

        <div>
          <Label htmlFor="email" className="text-gray-300 flex items-center gap-1.5"><Mail className="w-4 h-4"/>Email</Label>
          <Input
            id="email" type="email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="mt-1 bg-gray-700/50 border-gray-600 text-white"
            data-testid="profile-email-input"
          />
        </div>

        <div>
          <Label htmlFor="mobile_number" className="text-gray-300">Mobile Number (WhatsApp / SMS)</Label>
          <Input
            id="mobile_number" type="tel" value={form.mobile_number}
            onChange={(e) => setForm({ ...form, mobile_number: e.target.value })}
            className="mt-1 bg-gray-700/50 border-gray-600 text-white"
            placeholder="+91 98765 43210"
            data-testid="profile-mobile-input"
          />
          <p className="text-gray-500 text-xs mt-1">Used by support so we can reach you if a stream fails.</p>
        </div>

        <div className="pt-4 border-t border-gray-700">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2"><Lock className="w-4 h-4"/>Change password</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="current_password" className="text-gray-300">Current</Label>
              <Input
                id="current_password" type="password" value={form.current_password}
                onChange={(e) => setForm({ ...form, current_password: e.target.value })}
                className="mt-1 bg-gray-700/50 border-gray-600 text-white"
                data-testid="profile-current-password"
              />
            </div>
            <div>
              <Label htmlFor="new_password" className="text-gray-300">New</Label>
              <Input
                id="new_password" type="password" value={form.new_password}
                onChange={(e) => setForm({ ...form, new_password: e.target.value })}
                className="mt-1 bg-gray-700/50 border-gray-600 text-white"
                data-testid="profile-new-password"
              />
            </div>
            <div>
              <Label htmlFor="confirm_password" className="text-gray-300">Confirm</Label>
              <Input
                id="confirm_password" type="password" value={form.confirm_password}
                onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
                className="mt-1 bg-gray-700/50 border-gray-600 text-white"
                data-testid="profile-confirm-password"
              />
            </div>
          </div>
        </div>

        <Button
          type="submit" disabled={saving}
          className="bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white"
          data-testid="profile-save-button"
        >
          <Save className="w-4 h-4 mr-2" />
          {saving ? 'Saving…' : 'Save changes'}
        </Button>
      </form>
    </div>
  );
};

export default Profile;
