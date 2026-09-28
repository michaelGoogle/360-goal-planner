import { useMediaQuery } from './useMediaQuery';

/**
 * Auto-detect mobile / touch-narrow layouts via viewport (not User-Agent).
 * Phones and small tablets get the lite chrome.
 */
export function useIsMobile(): boolean {
  const narrow = useMediaQuery('(max-width: 767px)');
  const tabletTouch = useMediaQuery('(max-width: 1023px) and (pointer: coarse)');
  const phoneLandscape = useMediaQuery('(orientation: landscape) and (max-height: 500px)');
  return narrow || tabletTouch || phoneLandscape;
}
