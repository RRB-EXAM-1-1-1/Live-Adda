import React, { useState } from 'react';
import { HelpCircle, Send, Mail, MessageCircle, Phone, ExternalLink } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { supportAPI } from '../services/api';
import { toast } from 'sonner';

const WHATSAPP_NUMBER = '918796533673';
const WHATSAPP_LINK = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent("Hi Live Adda team, I need help with ")}`;
const SUPPORT_EMAIL = 'support@liveadda.org';

const Support = () => {
  const [formData, setFormData] = useState({ subject: '', message: '' });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const { data, error } = await supportAPI.createTicket(formData.subject, formData.message);
    setSubmitting(false);
    if (data) {
      toast.success("Support ticket submitted! We'll get back to you soon.");
      setFormData({ subject: '', message: '' });
    } else {
      toast.error(error || 'Failed to submit ticket');
    }
  };

  const faqs = [
    { question: 'How do I start streaming?', answer: 'Upload videos in Video Manager, then go to Live Slot to configure and start your 24/7 YouTube stream.' },
    { question: 'Can I change my plan?', answer: 'Yes — Billings shows all plans; buying the same active plan stacks duration onto your remaining validity.' },
    { question: 'What video formats are supported?', answer: 'MP4, MOV, MKV, AVI up to 4K. MP4 gives the smoothest 24/7 loop.' },
    { question: 'How much can I upload?', answer: 'Every plan includes a strict 2GB storage limit. Delete unused videos in Video Manager to free space.' },
    { question: 'My upload seems slow — is it stuck?', answer: 'Uploads are chunked and resume automatically. If you navigate to another page it keeps running in the background.' },
  ];

  return (
    <div className="space-y-8" data-testid="support-page">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Support Center</h1>
        <p className="text-gray-400">Get help via WhatsApp, email, or open a ticket below</p>
      </div>

      {/* Direct-contact cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <a
          href={WHATSAPP_LINK}
          target="_blank" rel="noreferrer"
          data-testid="support-whatsapp-link"
          className="group bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-emerald-500 hover:bg-emerald-500/5 transition-all"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <MessageCircle className="w-6 h-6 text-emerald-400" />
            </div>
            <ExternalLink className="w-4 h-4 text-gray-500 group-hover:text-emerald-400 transition-colors" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">WhatsApp Support</h3>
          <p className="text-gray-400 text-sm mb-2">Fastest way to reach us — usually replies within minutes</p>
          <div className="flex items-center gap-2 text-emerald-400 font-medium text-sm">
            <Phone className="w-4 h-4" />
            +91 87965 33673
          </div>
        </a>

        <a
          href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('Live Adda Support Request')}`}
          data-testid="support-email-link"
          className="group bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-blue-500 hover:bg-blue-500/5 transition-all"
        >
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center group-hover:scale-110 transition-transform">
              <Mail className="w-6 h-6 text-blue-400" />
            </div>
            <ExternalLink className="w-4 h-4 text-gray-500 group-hover:text-blue-400 transition-colors" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-1">Email Support</h3>
          <p className="text-gray-400 text-sm mb-2">For detailed queries and attachments — we respond within 24 hrs</p>
          <div className="flex items-center gap-2 text-blue-400 font-medium text-sm">
            <Mail className="w-4 h-4" />
            {SUPPORT_EMAIL}
          </div>
        </a>
      </div>

      {/* Ticket form */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
            <HelpCircle className="w-5 h-5 text-purple-400" />
          </div>
          <h2 className="text-xl font-bold text-white">Or, submit a support ticket</h2>
        </div>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <Label htmlFor="subject" className="text-gray-300 font-medium">Subject</Label>
            <Input
              id="subject" type="text" placeholder="Brief description of your issue"
              value={formData.subject}
              onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
              className="mt-1 bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-500 focus:border-blue-500"
              required
            />
          </div>
          <div>
            <Label htmlFor="message" className="text-gray-300 font-medium">Message</Label>
            <Textarea
              id="message" placeholder="Describe your issue in detail…"
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
              className="mt-1 bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-500 focus:border-blue-500 min-h-[150px]"
              required
            />
          </div>
          <Button
            type="submit" disabled={submitting}
            data-testid="submit-ticket-button"
            className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
          >
            <Send className="w-4 h-4 mr-2" />
            {submitting ? 'Submitting…' : 'Submit Ticket'}
          </Button>
        </form>
      </div>

      {/* FAQ */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6">Frequently Asked Questions</h2>
        <div className="space-y-4">
          {faqs.map((faq, i) => (
            <div key={i} className="bg-gray-700/30 rounded-xl p-5">
              <h3 className="text-white font-semibold mb-2">{faq.question}</h3>
              <p className="text-gray-400 text-sm">{faq.answer}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Support;
