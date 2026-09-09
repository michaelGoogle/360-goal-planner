import { useEffect, useRef } from 'react';
import { Ico } from '../../lib/icons';

export function ReportWalkthrough({
  who,
  mediaUrl,
  status,
}: {
  who: string;
  mediaUrl: string;
  status: 'pending' | 'completed' | 'failed';
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const ready = status === 'completed' && Boolean(mediaUrl);

  useEffect(() => {
    const pause = () => {
      videoRef.current?.pause();
    };
    window.addEventListener('beforeprint', pause);
    return () => window.removeEventListener('beforeprint', pause);
  }, []);

  const whose = who === 'you' ? 'your' : `${who}’s`;

  return (
    <div className="x-rpt-stage">
      {ready ? (
        <video
          ref={videoRef}
          className="x-rpt-video"
          controls
          playsInline
          preload="metadata"
          src={mediaUrl}
        >
          <track kind="captions" />
        </video>
      ) : status === 'failed' ? (
        <div className="x-rpt-wait" role="status">
          <b>Video unavailable</b>
          <span>We could not make the clip. Share the report again to retry.</span>
        </div>
      ) : (
        <div className="x-rpt-wait" role="status">
          <span className="x-rpt-play">{Ico.play}</span>
          <b>Preparing {whose} plan video</b>
          <span>This usually takes a few minutes. A link will also go by WhatsApp.</span>
        </div>
      )}
      <p className="x-rpt-cap">
        {ready
          ? `A walkthrough of ${whose} plan. This clip is not in the PDF.`
          : `The plan video appears here once it is ready. It is not in the printed PDF.`}
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
