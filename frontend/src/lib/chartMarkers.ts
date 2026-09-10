import { NEED_ICONS, NEED_META, sessionAge, type GpSession, type NeedType } from './types';
import { hydrateStressEvents, STRESS_BY_ID } from './stressEvents';

export type ChartMarkerKind = 'need' | 'event' | 'warning';

export interface ChartMarker {
  kind: ChartMarkerKind;
  id: string;
  label: string;
  icon: string;
  x: number;
  xEnd?: number;
  draggable: boolean;
  hoverLines: string[];
}

/** Same icons as Scenario Visualizer — sourced from NEED_ICONS. */
export const EVENT_ICONS: Record<string, string> = {
  crash: '📉',
  Crash: '📉',
  MarketCrash: '📉',
  death: 'RIP',
  Death: 'RIP',
  ci: '🏥',
  CI: '🏥',
  tpd: '♿',
  PTD: '♿',
  Disability: '♿',
  pa: '🩹',
  PersonalAccident: '🩹',
  inc: '💼',
  Unemployment: '💼',
  infl: '📈',
  Inflation: '📈',
  hosp: '🏨',
  care: '❤️',
  wed: '💍',
  baby: '👶',
  exp: '🛒',
  ccy: '$',
};

export const NEED_MARKER_COLOR = '#FB8C00';
export const EVENT_MARKER_COLOR = '#7E57C2';
export const WARNING_MARKER_COLOR = '#C62828';

const ACCUM = new Set<NeedType>(['N_RET', 'N_EDU', 'N_SAV', 'N_PRP']);

function money(n: number): string {
  return Math.round(n).toLocaleString('en-US');
}

/** Build timeline markers from the GP session (same rules as SV). */
export function extractSessionMarkers(session: GpSession): ChartMarker[] {
  const startAge = sessionAge(session) || 40;
  const startYear = new Date().getFullYear();
  const markers: ChartMarker[] = [];

  for (const n of session.needs) {
    if (!n.enabled) continue;
    let x: number;
    let draggable = false;
    if (n.type === 'N_RET') {
      x = n.retAge || session.ageOfRetirement || 65;
      draggable = true;
    } else if (ACCUM.has(n.type)) {
      const year = n.fundsNeededYear || n.targetYear || startYear + 10;
      x = startAge + Math.max(0, year - startYear);
      draggable = true;
    } else {
      x = startAge;
      draggable = false;
    }

    const hoverLines = [NEED_META[n.type].label, `Type: ${n.type}`];
    if (n.needAmount) hoverLines.push(`Target: ${money(n.needAmount)}`);
    if (n.type === 'N_RET') hoverLines.push(`Retirement age: ${x}`);
    if (draggable) hoverLines.push('Drag to move · release to recalculate');

    markers.push({
      kind: 'need',
      id: n.type,
      label: NEED_META[n.type].label,
      icon: NEED_ICONS[n.type] ?? '⭐',
      x,
      draggable,
      hoverLines,
    });
  }

  if (!markers.some(m => m.id === 'N_RET')) {
    const ret = session.ageOfRetirement || 65;
    markers.push({
      kind: 'need',
      id: 'retirement',
      label: 'Retirement',
      icon: '🏖️',
      x: ret,
      draggable: true,
      hoverLines: ['Retirement', `Retirement age: ${ret}`, 'Drag to move · release to recalculate'],
    });
  }

  for (const ev of hydrateStressEvents(session.events)) {
    if (!ev.on) continue;
    const spec = STRESS_BY_ID[ev.id];
    const x = startAge + Math.max(0, ev.year || 0);
    const xEnd = spec && spec.kind !== 'one' ? startAge + Math.max(ev.from, ev.to) : undefined;
    markers.push({
      kind: 'event',
      id: ev.id,
      label: ev.label,
      icon: EVENT_ICONS[ev.id] ?? '⚡',
      x,
      xEnd,
      draggable: true,
      hoverLines: [ev.label, `Event: ${ev.label}`, 'Drag to move · release to recalculate'],
    });
  }

  markers.sort((a, b) => a.x - b.x || (a.kind === b.kind ? 0 : a.kind === 'need' ? -1 : 1));
  return markers;
}

export function markersToPlotlyShapes(markers: ChartMarker[]): Record<string, unknown>[] {
  const shapes: Record<string, unknown>[] = [];
  for (const m of markers) {
    if (m.kind === 'warning') continue;
    const color = m.kind === 'need' ? NEED_MARKER_COLOR : EVENT_MARKER_COLOR;
    shapes.push({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: m.x,
      x1: m.x,
      y0: 0,
      y1: 1,
      line: { color, width: 1.2, dash: 'dot' },
      layer: 'below',
    });
    if (m.xEnd != null && m.xEnd > m.x) {
      shapes.push({
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: m.x,
        x1: m.xEnd,
        y0: 0,
        y1: 1,
        fillcolor: color,
        opacity: 0.06,
        line: { width: 0 },
        layer: 'below',
      });
    }
  }
  return shapes;
}

/** Apply a dragged marker to the session, then re-run the projection. */
export function applyMarkerMoveToSession(session: GpSession, marker: ChartMarker, newX: number): GpSession {
  const startAge = sessionAge(session) || 40;
  const startYear = new Date().getFullYear();
  const age = Math.max(startAge, Math.round(newX));
  const calendarYear = startYear + (age - startAge);

  if (marker.kind === 'need') {
    if (marker.id === 'N_RET' || marker.id === 'retirement') {
      return {
        ...session,
        ageOfRetirement: age,
        needs: session.needs.map(n =>
          n.type === 'N_RET' ? { ...n, retAge: age, targetYear: calendarYear, fundsNeededYear: calendarYear } : n,
        ),
      };
    }
    if (marker.id === 'N_SAV' || marker.id === 'N_PRP' || marker.id === 'N_EDU') {
      return {
        ...session,
        needs: session.needs.map(n =>
          n.type === marker.id ? { ...n, targetYear: calendarYear, fundsNeededYear: calendarYear } : n,
        ),
      };
    }
    return session;
  }

  if (marker.kind === 'event') {
    const yearOffset = Math.max(0, age - startAge);
    return {
      ...session,
      events: hydrateStressEvents(session.events).map(e =>
        e.id === marker.id ? { ...e, year: yearOffset, from: yearOffset, to: Math.max(e.to, yearOffset) } : e,
      ),
    };
  }
  return session;
}
