import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

export type Trace = Record<string, unknown>;
export type Layout = Record<string, unknown>;

/** Plot area insets — MarkerRail and RangeSlider padding must match. */
export const PLOT_MARGIN = { l: 64, r: 28, t: 16, b: 36 };

interface PlotProps {
  data: Trace[];
  layout?: Layout;
  className?: string;
}

const LIGHT: Layout = {
  paper_bgcolor: '#ffffff',
  plot_bgcolor: '#ffffff',
  font: { color: '#7B8694', family: 'Segoe UI, system-ui, sans-serif', size: 13 },
  margin: PLOT_MARGIN,
  showlegend: false,
  xaxis: {
    gridcolor: '#e8e8e8',
    zerolinecolor: '#bbbbbb',
    linecolor: '#cccccc',
    showgrid: false,
    rangeslider: { visible: false },
    fixedrange: true,
    automargin: false,
  },
  yaxis: {
    gridcolor: '#EEF1F6',
    zerolinecolor: '#999999',
    zerolinewidth: 1,
    linecolor: '#cccccc',
    showgrid: true,
    tickformat: '~s',
    separatethousands: true,
    fixedrange: true,
    automargin: false,
    rangemode: 'tozero',
    title: { text: 'Amount', standoff: 8 },
  },
  hoverlabel: { bgcolor: '#ffffff', bordercolor: '#cccccc', font: { size: 12, color: '#333' } },
};

function isTouchUi(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    window.matchMedia('(hover: none) and (pointer: coarse)').matches ||
    (navigator.maxTouchPoints ?? 0) > 0
  );
}

function plotConfig(touch: boolean) {
  return {
    responsive: true,
    displayModeBar: false,
    scrollZoom: false,
    doubleClick: touch ? (false as const) : ('reset' as const),
  };
}

/** Plotly chart — same engine as Scenario Visualizer. */
export function Plot({ data, layout, className }: PlotProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const touch = isTouchUi();
    const merged = {
      ...LIGHT,
      ...layout,
      ...(touch ? { dragmode: false as const } : {}),
      xaxis: {
        ...(LIGHT.xaxis as object),
        ...(layout?.xaxis as object),
        rangeslider: { visible: false },
        ...(touch ? { fixedrange: true } : {}),
      },
      yaxis: {
        ...(LIGHT.yaxis as object),
        ...(layout?.yaxis as object),
        ...(touch ? { fixedrange: true } : {}),
      },
      margin: { ...(LIGHT.margin as object), ...(layout?.margin as object) },
      annotations: [
        ...((LIGHT.annotations as unknown[]) || []),
        ...((layout?.annotations as unknown[]) || []),
      ],
      showlegend: layout?.showlegend ?? LIGHT.showlegend ?? false,
      legend: {
        ...(LIGHT.legend as object),
        ...(layout?.legend as object),
      },
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Plotly.react(el, data as any, merged as any, plotConfig(touch) as any);
  }, [data, layout]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (el.offsetWidth > 0) Plotly.Plots.resize(el);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);

  return <div ref={ref} className={`${className ?? 'x-svplot'} touch-pan-y`} />;
}
