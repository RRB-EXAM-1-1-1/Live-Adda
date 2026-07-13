import React, { useState } from 'react';
import { HelpCircle, Send, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { supportAPI } from '../services/api';
import { toast } from 'sonner';

const Support = () => {
  const [formData, setFormData] = useState({
    subject: '',
    message: ''
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const { data, error } = await supportAPI.createTicket(formData.subject, formData.message);
    setSubmitting(false);

    if (data) {
      toast.success('Support ticket submitted successfully! We\'ll get back to you soon.');
      setFormData({ subject: '', message: '' });
    } else {
      toast.error(error || 'Failed to submit ticket');
    }
  };

  const faqs = [
    {
      question: 'How do I start streaming?',
      answer: 'Upload your videos in the Video Manager, then go to Live Slot to configure and start your stream.'
    },
    {
      question: 'Can I change my plan?',
      answer: 'Yes! Go to the Billings page to view and change your subscription plan at any time.'
    },
    {
      question: 'What video formats are supported?',
      answer: 'We support MP4, MOV, AVI, and most common video formats up to 4K resolution.'
    },
    {
      question: 'How many videos can I upload?',
      answer: 'The number of videos depends on your storage limit. Daily: 5GB, Weekly: 10GB, Monthly: 25GB.'
    }
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Support Center</h1>
        <p className="text-gray-400">Get help and find answers to common questions</p>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-blue-500 transition-all cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center mb-4">
            <HelpCircle className="w-6 h-6 text-blue-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Documentation</h3>
          <p className="text-gray-400 text-sm">Browse our comprehensive guides and tutorials</p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-emerald-500 transition-all cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center mb-4">
            <Mail className="w-6 h-6 text-emerald-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Email Support</h3>
          <p className="text-gray-400 text-sm">Reach out to our team at support@liveadda.com</p>
        </div>

        <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700 hover:border-purple-500 transition-all cursor-pointer">
          <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center mb-4">
            <Send className="w-6 h-6 text-purple-400" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">Live Chat</h3>
          <p className="text-gray-400 text-sm">Chat with our support team in real-time</p>
        </div>
      </div>

      {/* Contact Form */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6">Submit a Support Ticket</h2>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <Label htmlFor="subject" className="text-gray-300 font-medium">Subject</Label>
            <Input
              id="subject"
              type="text"
              placeholder="Brief description of your issue"
              value={formData.subject}
              onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
              className="mt-1 bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-500 focus:border-blue-500"
              required
            />
          </div>
          <div>
            <Label htmlFor="message" className="text-gray-300 font-medium">Message</Label>
            <Textarea
              id="message"
              placeholder="Describe your issue in detail..."
              value={formData.message}
              onChange={(e) => setFormData({ ...formData, message: e.target.value })}
              className="mt-1 bg-gray-700/50 border-gray-600 text-white placeholder:text-gray-500 focus:border-blue-500 min-h-[150px]"
              required
            />
          </div>
          <Button 
            type="submit"
            disabled={submitting}
            data-testid="submit-ticket-button"
            className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white"
          >
            <Send className="w-4 h-4 mr-2" />
            {submitting ? 'Submitting...' : 'Submit Ticket'}
          </Button>
        </form>
      </div>

      {/* FAQs */}
      <div className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 border border-gray-700">
        <h2 className="text-xl font-bold text-white mb-6">Frequently Asked Questions</h2>
        <div className="space-y-4">
          {faqs.map((faq, index) => (
            <div key={index} className="bg-gray-700/30 rounded-xl p-5">
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
