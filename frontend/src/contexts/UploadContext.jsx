import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import api from '../services/api';
import { toast } from 'sonner';

/**
 * Global upload state that lives ABOVE the router so:
 *  - Navigating between dashboard pages does NOT cancel the upload
 *  - Progress is visible from any page (via <GlobalUploadIndicator />)
 *  - Uploads are resumable byte-for-byte via `upload_id`
 *  - Duplicate video rows are impossible (backend is idempotent on upload_id)
 *
 * The current file is held in memory (a React ref) — SPA navigation preserves
 * it, but a hard refresh clears it (browsers cannot persist File objects).
 * On hard refresh, we still know an upload was interrupted and prompt the user
 * to re-select the same file; the server tells us how many bytes it already
 * has and we resume from that offset.
 */

const CHUNK_SIZE = 8 * 1024 * 1024; // 8MB — fewer HTTP round-trips = faster uploads
const STORAGE_KEY = 'liveadda:pending_upload_v1';

const UploadContext = createContext(null);

export const useUpload = () => {
  const ctx = useContext(UploadContext);
  if (!ctx) throw new Error('useUpload must be used within UploadProvider');
  return ctx;
};

const readPending = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
};
const writePending = (meta) => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(meta)); } catch { /* quota */ }
};
const clearPending = () => {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
};

export const UploadProvider = ({ children, onCompleted }) => {
  // Public state
  const [status, setStatus] = useState('idle');   // idle | uploading | completed | error | paused
  const [progress, setProgress] = useState(0);    // 0..100
  const [filename, setFilename] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  // Detected pending upload from a previous session that needs the user to reselect the file
  const [pendingResume, setPendingResume] = useState(null);

  // Refs — survive re-renders and DO NOT trigger cleanup on unmount of children
  const cancelRef = useRef(false);
  const runningRef = useRef(false);
  const uploadIdRef = useRef(null);
  const completionListenersRef = useRef(new Set());

  // Detect pending upload on mount
  useEffect(() => {
    const meta = readPending();
    if (meta && meta.upload_id) {
      setPendingResume(meta);
    }
  }, []);

  // Warn user before closing tab while upload is running
  useEffect(() => {
    const handler = (e) => {
      if (runningRef.current) {
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);

  const onComplete = useCallback((cb) => {
    completionListenersRef.current.add(cb);
    return () => completionListenersRef.current.delete(cb);
  }, []);

  const emitCompleted = useCallback((data) => {
    completionListenersRef.current.forEach(cb => {
      try { cb(data); } catch { /* isolated */ }
    });
    if (onCompleted) {
      try { onCompleted(data); } catch { /* isolated */ }
    }
  }, [onCompleted]);

  /**
   * Core upload loop. Sends chunks sequentially with `offset` so retries are
   * byte-safe. On any transient failure it retries up to 3× per chunk before
   * flipping status to 'error' (the caller can re-invoke to resume).
   */
  const runUpload = useCallback(async ({ file, title, uploadId, startOffset = 0 }) => {
    runningRef.current = true;
    cancelRef.current = false;
    setStatus('uploading');
    setErrorMsg('');
    setFilename(file.name);
    uploadIdRef.current = uploadId;

    const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE));
    let startIndex = Math.floor(startOffset / CHUNK_SIZE);
    // Snap start offset to a chunk boundary
    let currentOffset = startIndex * CHUNK_SIZE;
    setProgress(Math.min(99, Math.round((currentOffset / file.size) * 100)));

    writePending({
      upload_id: uploadId,
      filename: file.name,
      size: file.size,
      title,
      chunk_size: CHUNK_SIZE,
      total_chunks: totalChunks,
    });

    try {
      let lastData = null;
      for (let index = startIndex; index < totalChunks; index++) {
        if (cancelRef.current) throw new Error('Upload cancelled');
        const start = index * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const blob = file.slice(start, end);

        const formData = new FormData();
        formData.append('upload_id', uploadId);
        formData.append('chunk_index', index);
        formData.append('total_chunks', totalChunks);
        formData.append('offset', start);
        formData.append('filename', file.name);
        formData.append('title', title);
        formData.append('file', blob, file.name);

        // Retry each chunk up to 3× with exponential backoff.
        let attempt = 0;
        let succeeded = false;
        let lastErr;
        while (attempt < 3 && !succeeded) {
          try {
            const { data } = await api.post('/videos/upload/chunk', formData, {
              headers: { 'Content-Type': 'multipart/form-data' },
              timeout: 0,
              onUploadProgress: (evt) => {
                const chunkLoaded = evt.total ? (evt.loaded / evt.total) * blob.size : 0;
                const overall = Math.min(99, Math.round(((start + chunkLoaded) / file.size) * 100));
                setProgress(overall);
              }
            });
            lastData = data;
            succeeded = true;
          } catch (err) {
            lastErr = err;
            attempt += 1;
            if (attempt < 3) {
              // Backoff: 1s, 2s
              await new Promise(r => setTimeout(r, 1000 * attempt));
            }
          }
        }
        if (!succeeded) throw lastErr || new Error('Chunk upload failed');
      }

      setProgress(100);
      setStatus('completed');
      clearPending();
      runningRef.current = false;
      emitCompleted(lastData);
      toast.success(lastData?.message || '✅ Ready for the stream!');
      return { data: lastData, error: null };
    } catch (err) {
      runningRef.current = false;
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed';
      setErrorMsg(typeof msg === 'string' ? msg : 'Upload failed');
      setStatus('error');
      toast.error(typeof msg === 'string' ? msg : 'Upload failed');
      return { data: null, error: msg };
    }
  }, [emitCompleted]);

  /**
   * Public: start a fresh upload for a File the user just picked.
   */
  const startUpload = useCallback(async (file, title) => {
    if (runningRef.current) {
      toast.error('An upload is already in progress. Please wait for it to finish.');
      return { data: null, error: 'busy' };
    }
    const uploadId = `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
    return runUpload({ file, title, uploadId, startOffset: 0 });
  }, [runUpload]);

  /**
   * Public: resume an interrupted upload after the user re-selects the same file.
   */
  const resumeWithFile = useCallback(async (file) => {
    const meta = readPending();
    if (!meta) {
      toast.error('No pending upload to resume.');
      return;
    }
    if (file.size !== meta.size) {
      toast.error('The selected file does not match the interrupted upload (different size).');
      return;
    }
    // Ask the server how many bytes it already has
    try {
      const { data } = await api.get(`/videos/upload/status/${meta.upload_id}`);
      if (data?.completed) {
        // Already finalized — clear and treat as done.
        setStatus('completed');
        setProgress(100);
        clearPending();
        setPendingResume(null);
        emitCompleted(data);
        toast.success('This upload was already completed on the server. Video restored.');
        return;
      }
      setPendingResume(null);
      return runUpload({
        file,
        title: meta.title,
        uploadId: meta.upload_id,
        startOffset: data?.received_bytes || 0,
      });
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to resume';
      toast.error(typeof msg === 'string' ? msg : 'Failed to resume upload');
    }
  }, [runUpload, emitCompleted]);

  const dismissResume = useCallback(() => {
    clearPending();
    setPendingResume(null);
  }, []);

  const dismissStatus = useCallback(() => {
    if (status === 'uploading') return; // don't hide while running
    setStatus('idle');
    setProgress(0);
    setFilename('');
    setErrorMsg('');
  }, [status]);

  const value = {
    status,
    progress,
    filename,
    errorMsg,
    isUploading: status === 'uploading',
    pendingResume,
    startUpload,
    resumeWithFile,
    dismissResume,
    dismissStatus,
    onComplete,
  };

  return <UploadContext.Provider value={value}>{children}</UploadContext.Provider>;
};

export default UploadContext;
