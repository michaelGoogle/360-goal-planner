import { useEffect, useRef } from 'react';
import { Ico } from '../../lib/icons';

export function ReportWalkthrough({
  who,
  dummyUrl,
  mediaUrl,
  status,
}: {
  who: string;
  dummyUrl: string;
  mediaUrl: string;
  status: 'idle' | 'pending' | 'completed' | 'failed';
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const customReady = status === 'completed' && Boolean(mediaUrl);
  const src = customReady ? mediaUrl : dummyUrl;
  const whose = who === 'you' ? 'your' : `${who}’s`;

  useEffect(() => {
    const pause = () => {
      videoRef.current?.pause();
    };
    window.addEventListener('beforeprint', pause);
    return () => window.removeEventListener('beforeprint', pause);
  }, []);

  useEffect(() => {
    const el = videoRef.current;
    if (!el || !src) return;
    el.load();
  }, [src]);

  return (
    <div className="x-rpt-stage">
      <div className="x-rpt-frame">
        <div className="x-rpt-frame-in">
          {src ? (
            <video
              ref={videoRef}
              className="x-rpt-video"
              controls
              playsInline
              preload="metadata"
              src={src}
            >
              <track kind="captions" />
            </video>
          ) : (
            <div className="x-rpt-wait" role="status">
              <span className="x-rpt-play">{Ico.play}</span>
              <b>Plan report video</b>
              <span>A walkthrough of this report will play here.</span>
            </div>
          )}
        </div>
      </div>
      {status === 'pending' && !customReady ? (
        <p className="x-rpt-note">
          We are making your customised video. A WhatsApp link will follow in a few minutes.
        </p>
      ) : null}
      <p className="x-rpt-cap">
        {customReady
          ? `A walkthrough of ${whose} plan. This clip is not in the PDF.`
          : 'A walkthrough of this report. Click Share report to get a customised video and this report on WhatsApp. It is not in the printed PDF.'}
      </p>
    </div>
  );
}

export function ReportWalkthroughStill({ who }: { who: string }) {
  return (
    <div className="x-rpt-still">
      <b>Plan video</b>
      <span>
        Watch the plan video in the online report
        {who === 'you' ? '' : ` for ${who}`}. It does not play in this PDF.
      </span>
    </div>
  );
}
