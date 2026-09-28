import { useMediaQuery } from './useMediaQuery';

export type Orientation = 'portrait' | 'landscape';

export function useOrientation(): Orientation {
  const landscape = useMediaQuery('(orientation: landscape)');
  return landscape ? 'landscape' : 'portrait';
}
