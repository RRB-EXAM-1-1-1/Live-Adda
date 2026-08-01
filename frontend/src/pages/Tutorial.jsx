import React from 'react';
import { BookOpen, CreditCard, Upload, Radio, CheckCircle2, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';

const Step = ({ n, title, children }) => (
  <div className="flex gap-4">
    <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-700 text-white font-bold flex items-center justify-center shadow-lg">
      {n}
    </div>
    <div className="flex-1">
      <h4 className="text-white font-semibold mb-1">{title}</h4>
      <p className="text-gray-400 text-sm leading-relaxed">{children}</p>
    </div>
  </div>
);

const Chapter = ({ icon: Icon, title, subtitle, children, accent = 'from-emerald-500 to-emerald-600' }) => (
  <section className="bg-gray-800/50 backdrop-blur-lg rounded-2xl p-6 md:p-8 border border-gray-700">
    <div className="flex items-start gap-4 mb-6">
      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${accent} flex items-center justify-center flex-shrink-0`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <div>
        <h2 className="text-2xl font-bold text-white">{title}</h2>
        <p className="text-gray-400 text-sm mt-1">{subtitle}</p>
      </div>
    </div>
    <div className="space-y-5 pl-1">{children}</div>
  </section>
);

const Tutorial = () => {
  const navigate = useNavigate();

  return (
    <div className="space-y-8 max-w-4xl" data-testid="tutorial-page">
      <div className="flex items-start gap-4">
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-7 h-7 text-white" />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Tutorial</h1>
          <p className="text-gray-400">Step-by-step guide to buy a plan, upload a video, and go live 24/7 on YouTube.</p>
        </div>
      </div>

      <Chapter icon={CreditCard} title="1. Buy a plan" subtitle="Pick a plan that fits your streaming needs" accent="from-emerald-500 to-emerald-600">
        <Step n={1} title="Open Billings">
          Click <b>Billings</b> in the sidebar to see the current plans: Daily ₹35, Weekly ₹199, Monthly ₹599.
        </Step>
        <Step n={2} title="Choose a plan and pay via Razorpay">
          Click the plan you want. A secure Razorpay payment window opens. Complete payment using UPI / cards / netbanking.
        </Step>
        <Step n={3} title="Wait for confirmation">
          Your plan activates instantly on payment success. You'll see a "Current Plan" badge and validity date on the dashboard.
        </Step>
        <div className="pt-2">
          <Button onClick={() => navigate('/dashboard/billings')} data-testid="tutorial-go-billings" className="bg-emerald-500 hover:bg-emerald-600 text-white">
            Go to Billings <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </Chapter>

      <Chapter icon={Upload} title="2. Upload a video" subtitle="Prepare the video that will loop 24/7 on YouTube" accent="from-blue-500 to-blue-700">
        <Step n={1} title="Open Video Manager">
          Click <b>Video Manager</b> in the sidebar and press the green <b>Upload Video</b> button.
        </Step>
        <Step n={2} title="Pick your MP4">
          Select an MP4 file up to 2GB. Upload runs in the background — you can switch pages, it will not stop.
        </Step>
        <Step n={3} title="Wait for 'Ready for the stream!'">
          A thumbnail preview appears in the grid when the upload is done. If a file re-uploads, the duplicate is automatically prevented.
        </Step>
        <div className="pt-2">
          <Button onClick={() => navigate('/dashboard/videos')} data-testid="tutorial-go-videos" className="bg-blue-600 hover:bg-blue-700 text-white">
            Go to Video Manager <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </Chapter>

      <Chapter icon={Radio} title="3. Start a live stream" subtitle="Send your video to YouTube 24/7 with one click" accent="from-red-500 to-pink-600">
        <Step n={1} title="Open Live Slot">
          Click <b>Live Slot</b> in the sidebar. Pick the uploaded video you want to broadcast.
        </Step>
        <Step n={2} title="Enter your YouTube stream key">
          On YouTube Studio → <b>Go Live</b> → <b>Stream</b>, copy your Stream Key and paste it into Live Adda.
        </Step>
        <Step n={3} title="Click Start Streaming">
          FFmpeg pushes your video 24/7 to YouTube Live in a loop. You can stop the stream anytime from the same page.
        </Step>
        <div className="pt-2">
          <Button onClick={() => navigate('/dashboard/live-slot')} data-testid="tutorial-go-livesolt" className="bg-red-600 hover:bg-red-700 text-white">
            Go to Live Slot <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </Chapter>

      <section className="bg-gradient-to-br from-emerald-500/10 to-blue-500/10 border border-emerald-500/30 rounded-2xl p-6 flex items-start gap-4">
        <CheckCircle2 className="w-8 h-8 text-emerald-400 flex-shrink-0 mt-1" />
        <div>
          <h3 className="text-white font-semibold mb-1">That's it — you're live 24/7!</h3>
          <p className="text-gray-400 text-sm">
            Need help? Open the <b>Support</b> option in the sidebar footer to reach us on WhatsApp or email.
          </p>
        </div>
      </section>
    </div>
  );
};

export default Tutorial;
