import { useCallback, useEffect, useMemo, useState } from 'react';
import { MarkerRail } from './MarkerRail';
import { Plot, type Layout, type Trace } from './Plot';
import { RangeSlider } from './RangeSlider';
import {
  buildXAxis,
  defaultRangeEndIndex,
  floorWealth,
  visibleStackedYRange,
  visibleYRange,
} from '../lib/chartAxis';
import {
  extractSessionMarkers,
  markersToPlotlyShapes,
  type ChartMarker,
} from '../lib/chartMarkers';
import {
  pickAvailable,
  pickEarmarked,
  pickFunding,
  seriesLength,
  SV_COLORS,
  type ChartView,
  type SvData,
} from '../lib/sv';
import type { GpSession } from '../lib/types';
import { sessionAge } from '../lib/types';

export function SvChart({
  data,
  view,
  session,
  busy,
  error,
  onMarkerMove,
  onMarkerClick,
}: {
  data: SvData | null;
  view: ChartView;
  session: GpSession;
  busy: boolean;
  error: string | null;
  onMarkerMove: (marker: ChartMarker, newX: number) => void;
  onMarkerClick: (marker: ChartMarker) => void;
}) {
  const startAge = sessionAge(session) || 40;
  const n = data ? seriesLength(data) : 0;
  const x = useMemo(() => buildXAxis(n, startAge), [n, startAge]);
  const [range, setRange] = useState<[number, number]>([0, 0]);
  const [dragOverrides, setDragOverrides] = useState<Record<string, number>>({});

  useEffect(() => {
    if (x.length === 0) return;
    setRange([0, defaultRangeEndIndex(x.length, startAge, session.endAge || 85)]);
  }, [x.length, startAge, session.endAge]);

  const xRange =
    x.length > 0
      ? ([x[range[0]] ?? x[0], x[range[1]] ?? x[x.length - 1]] as [number, number])
      : undefined;

  const baseMarkers = useMemo(() => extractSessionMarkers(session), [session]);
  const markers = useMemo(
    () =>
      baseMarkers.map(m => {
        const key = `${m.kind}:${m.id}`;
        const ox = dragOverrides[key];
        if (ox == null) return m;
        return { ...m, x: ox };
      }),
    [baseMarkers, dragOverrides],
  );

  const handleDragMove = useCallback((marker: ChartMarker, newX: number) => {
    setDragOverrides(prev => ({ ...prev, [`${marker.kind}:${marker.id}`]: newX }));
  }, []);

  const handleDragEnd = useCallback(
    (marker: ChartMarker, newX: number) => {
      setDragOverrides(prev => ({ ...prev, [`${marker.kind}:${marker.id}`]: newX }));
      onMarkerMove(marker, newX);
    },
    [onMarkerMove],
  );

  useEffect(() => {
    setDragOverrides({});
  }, [session.needs, session.events, session.ageOfRetirement]);

  const earmarked = data ? pickEarmarked(data, 'pre') : null;
  const funding = data ? pickFunding(data) : null;

  const traces = useMemo((): Trace[] => {
    if (!data || !x.length) return [];
    if (view === 'cash') {
      return [
        { x, y: data.prePositiveCashFlow, type: 'bar', name: 'Cash Inflow', marker: { color: SV_COLORS.inflow } },
        { x, y: data.preNegativeCashFlow, type: 'bar', name: 'Cash Outflow', marker: { color: SV_COLORS.outflow } },
      ];
    }
    if (view === 'exp') {
      if (!funding) return [];
      return [
        { x, y: funding.active, type: 'bar', name: 'Active income', marker: { color: SV_COLORS.active } },
        { x, y: funding.passive, type: 'bar', name: 'Passive income', marker: { color: SV_COLORS.passive } },
        { x, y: funding.savings, type: 'bar', name: 'From savings', marker: { color: SV_COLORS.savings } },
        { x, y: funding.shortfall, type: 'bar', name: 'Shortfall', marker: { color: SV_COLORS.shortfall } },
      ];
    }
    const available = floorWealth(pickAvailable(data, 'pre'));
    const traces: Trace[] = [
      {
        x,
        y: available,
        type: 'scatter',
        mode: 'lines',
        name: 'Available assets',
        line: { color: SV_COLORS.wealth, width: 2 },
        fill: 'tozeroy',
        fillcolor: SV_COLORS.wealthFill,
      },
    ];
    if (earmarked) {
      traces.push({
        x,
        y: floorWealth(earmarked),
        type: 'scatter',
        mode: 'lines',
        name: 'Earmarked for goals',
        line: { color: SV_COLORS.earmarked, width: 2 },
        fill: 'tozeroy',
        fillcolor: SV_COLORS.earmarkedFill,
      });
    }
    return traces;
  }, [data, view, x, earmarked, funding]);

  const [rangeLo, rangeHi] = range;
  const shapes = useMemo(() => markersToPlotlyShapes(markers), [markers]);

  const layout = useMemo((): Layout => {
    const ys = traces
      .map(t => t.y as number[] | undefined)
      .filter((y): y is number[] => Array.isArray(y));
    const raw =
      view === 'exp'
        ? visibleStackedYRange(ys, rangeLo, rangeHi, { includeZero: true })
        : visibleYRange(ys, rangeLo, rangeHi, { includeZero: true });
    const yRange =
      view === 'wealth' || view === 'sav'
        ? raw
          ? ([Math.max(0, raw[0]), Math.max(0, raw[1])] as [number, number])
          : undefined
        : raw;
    return {
      barmode: view === 'cash' ? 'relative' : view === 'exp' ? 'stack' : undefined,
      bargap: view === 'exp' ? 0.08 : 0.05,
      margin: { l: 64, r: 28, t: 16, b: 36 },
      showlegend: true,
      legend: {
        orientation: 'v',
        x: 0.99,
        y: 0.97,
        xanchor: 'right',
        yanchor: 'top',
        bgcolor: 'rgba(255,255,255,0.88)',
        borderwidth: 0,
        font: { size: 12, color: '#4C5766', family: 'Segoe UI, system-ui, sans-serif' },
        itemsizing: 'constant',
        tracegroupgap: 6,
      },
      xaxis: { range: xRange, rangeslider: { visible: false }, automargin: false },
      yaxis: {
        title: { text: 'Amount' },
        tickformat: '~s',
        separatethousands: true,
        automargin: false,
        rangemode: view === 'wealth' || view === 'sav' ? 'tozero' : undefined,
        ...(yRange ? { range: yRange, autorange: false } : {}),
      },
      shapes,
    };
  }, [traces, view, rangeLo, rangeHi, xRange, shapes]);

  if (!data) {
    return (
      <div className="x-sm" style={{ padding: 40 }}>
        {busy ? 'Scenario Visualizer is calculating…' : error ? error : 'No projection yet.'}
      </div>
    );
  }
  if (!traces.length) {
    return (
      <div className="x-sm" style={{ padding: 40 }}>
        {view === 'exp' ? 'Expense funding is not in this projection.' : 'No projection yet.'}
      </div>
    );
  }

  return (
    <>
      <MarkerRail
        markers={markers}
        xRange={xRange}
        disabled={busy}
        onDragMove={handleDragMove}
        onDragEnd={handleDragEnd}
        onMarkerClick={onMarkerClick}
      />
      <Plot data={traces} layout={layout} className="x-svplot" />
      {x.length > 1 ? (
        <RangeSlider
          min={0}
          max={x.length - 1}
          value={range}
          labels={x}
          axisLabel="Age"
          onChange={setRange}
        />
      ) : null}
    </>
  );
}
