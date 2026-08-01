import React, { useRef } from 'react';
import { Upload, X, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { Progress } from './ui/progress';
import { Button } from './ui/button';
import { useUpload } from '../contexts/UploadContext';

/**
 * Floating upload widget rendered by DashboardLayout so the user sees upload
 * progress from ANY page in the dashboard. Also surfaces a "resume upload"
 * prompt if a previous session was interrupted.
 */
const GlobalUploadIndicator = () => {
  const {
    status,
    progress,
    filename,
    errorMsg,
    pendingResume,
    resumeWithFile,
    dismissResume,
    dismissStatus,
  } = useUpload();

  const fileInputRef = useRef(null);

  // Nothing pending, nothing running, nothing recent → render nothing.
  if (status === 'idle' && !pendingResume) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 w-[92vw] max-w-sm rounded-2xl bg-gray-900/95 backdrop-blur-xl border border-gray-700 shadow-2xl overflow-hidden"
      data-testid="global-upload-indicator"
    >
      {/* Active / recent upload state */}
      {status !== 'idle' && (
        <div className="p-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center min-w-0">
              {status === 'uploading' && (
                <Upload className="w-5 h-5 mr-2 text-blue-400 animate-pulse flex-shrink-0" />
              )}
              {status === 'completed' && (
                <CheckCircle2 className="w-5 h-5 mr-2 text-emerald-400 flex-shrink-0" />
              )}
              {status === 'error' && (
                <AlertCircle className="w-5 h-5 mr-2 text-red-400 flex-shrink-0" />
              )}
              <div className="min-w-0">
                <p className="text-sm font-semibold text-white truncate" data-testid="global-upload-filename">
                  {filename || 'Upload'}
                </p>
                <p className="text-xs text-gray-400">
                  {status === 'uploading' && 'Uploading in background — you can keep navigating'}
                  {status === 'completed' && '✅ Ready for the stream!'}
                  {status === 'error' && (errorMsg || 'Upload failed')}
                </p>
              </div>
            </div>
            {status !== 'uploading' && (
              <button
                onClick={dismissStatus}
                className="text-gray-500 hover:text-white ml-2 flex-shrink-0"
                data-testid="global-upload-dismiss"
                aria-label="Dismiss"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {status === 'uploading' && (
            <>
              <Progress value={progress} className="h-2" />
              <div className="mt-2 flex justify-between text-xs text-gray-400">
                <span>{progress}%</span>
                <span>Do not close this tab</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Pending-resume banner (only shown when no upload is currently running) */}
      {pendingResume && status !== 'uploading' && (
        <div className="p-4 border-t border-gray-800 bg-amber-500/10">
          <div className="flex items-start">
            <RefreshCw className="w-5 h-5 mr-2 text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-white">
                Resume interrupted upload?
              </p>
              <p className="text-xs text-gray-400 mt-1 truncate">
                {pendingResume.filename}
              </p>
              <p className="text-[11px] text-gray-500 mt-1">
                Re-select the same file — we'll skip the parts we already have.
              </p>
              <div className="flex gap-2 mt-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    e.target.value = '';
                    if (f) resumeWithFile(f);
                  }}
                  data-testid="resume-upload-file-input"
                />
                <Button
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  className="bg-amber-500 hover:bg-amber-600 text-black h-8"
                  data-testid="resume-upload-btn"
                >
                  Select file
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={dismissResume}
                  className="text-gray-400 hover:text-white h-8"
                  data-testid="resume-upload-dismiss"
                >
                  Discard
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GlobalUploadIndicator;
