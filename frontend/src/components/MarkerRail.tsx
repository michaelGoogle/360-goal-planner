import { useCallback, useEffect, useRef, useState, type MutableRefObject, type RefObject } from 'react';
import { AnchorTooltipPortal } from './AnchorTooltipPortal';
import { PLOT_MARGIN } from './Plot';
import {
  EVENT_MARKER_COLOR,
  NEED_MARKER_COLOR,
  WARNING_MARKER_COLOR,
  type ChartMarker,
} from '../lib/chartMarkers';

const DRAG_THRESHOLD_PX = 6;
const STACK_OVERLAP_STEP_PX = 10;

interface Props {
  markers: ChartMarker[];
  xRange: [number, number] | undefined;
  disabled?: boolean;
  onDragMove?: (marker: ChartMarker, x: number) => void;
  onDragEnd: (marker: ChartMarker, x: number) => void;
  onMarkerClick?: (marker: ChartMarker) => void;
}

function MarkerHoverTooltip({
  anchorRef,
  marker,
  isWarning,
  canDrag,
}: {
  anchorRef: RefObject<HTMLButtonElement | null>;
  marker: ChartMarker;
  isWarning: boolean;
  canDrag: boolean;
}) {
  const [title, ...detail] = marker.hoverLines;
  return (
    <AnchorTooltipPortal
      anchorRef={anchorRef}
      open
      className={`x-markertip${isWarning ? ' warn' : ''}`}
    >
      <b>{title}</b>
      {detail.map(line => (
        <p key={line}>{line}</p>
      ))}
      {!isWarning && (
        <p className="m">Click to edit · {canDrag ? 'drag to move' : 'fixed on timeline'}</p>
      )}
    </AnchorTooltipPortal>
  );
}

function MarkerRailItem({
  markerKey,
  marker,
  x,
  slot,
  pctFor,
  color,
  isWarning,
  canDrag,
  isDrag,
  isHover,
  dragRef,
  setDraggingId,
  setHoverId,
}: {
  markerKey: string;
  marker: ChartMarker;
  x: number;
  slot: number;
  pctFor: (x: number) => number;
  color: string;
  isWarning: boolean;
  canDrag: boolean;
  isDrag: boolean;
  isHover: boolean;
  dragRef: MutableRefObject<{
    key: string;
    marker: ChartMarker;
    x: number;
    startClientX: number;
    moved: boolean;
  } | null>;
  setDraggingId: (id: string | null) => void;
  setHoverId: (id: string | null) => void;
}) {
  const anchorRef = useRef<HTMLButtonElement>(null);

  return (
    <div
      className="absolute top-1 flex flex-col items-center"
      style={{
        left: `${pctFor(x)}%`,
        transform: `translate(calc(-50% + ${slot * STACK_OVERLAP_STEP_PX}px), 0)`,
        zIndex: 10 + slot + (isWarning ? 5 : 0),
      }}
    >
      <button
        ref={anchorRef}
        type="button"
        onMouseDown={e => {
          e.preventDefault();
          e.stopPropagation();
          setHoverId(null);
          if (isWarning) return;
          dragRef.current = {
            key: markerKey,
            marker,
            x,
            startClientX: e.clientX,
            moved: false,
          };
          setDraggingId(markerKey);
        }}
        onMouseEnter={() => setHoverId(markerKey)}
        onMouseLeave={() => {
          if (!isDrag) setHoverId(null);
        }}
        className={`min-w-8 h-8 w-8 px-0 rounded-full flex items-center justify-center leading-none
          border bg-white shadow-sm transition-shadow overflow-visible
          ${isWarning ? 'cursor-default text-[#C62828]' : 'cursor-pointer'}
          ${canDrag ? 'hover:shadow-md active:cursor-grabbing' : 'hover:shadow-md'}
          ${isDrag ? 'ring-2 shadow-md' : ''}
          ${!isWarning && marker.icon.length > 2 ? 'text-xs font-bold tracking-tight text-[#333]' : 'text-2xl'}`}
        style={{
          borderColor: color,
          ...(isDrag ? { boxShadow: `0 0 0 2px ${color}` } : {}),
        }}
        aria-label={isWarning ? marker.label : `${marker.label} — click to edit`}
      >
        <span
          aria-hidden
          className={
            marker.id === 'N_RET' || marker.id === 'retirement'
              ? 'inline-block scale-[1.45] origin-center'
              : undefined
          }
        >
          {marker.icon}
        </span>
      </button>

      {isHover && !isDrag && (
        <MarkerHoverTooltip
          anchorRef={anchorRef}
          marker={marker}
          isWarning={isWarning}
          canDrag={canDrag}
        />
      )}
    </div>
  );
}

export function MarkerRail({
  markers,
  xRange,
  disabled,
  onDragMove,
  onDragEnd,
  onMarkerClick,
}: Props) {
  const railRef = useRef<HTMLDivElement>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [localX, setLocalX] = useState<Record<string, number>>({});
  const dragRef = useRef<{
    key: string;
    marker: ChartMarker;
    x: number;
    startClientX: number;
    moved: boolean;
  } | null>(null);

  useEffect(() => {
    setLocalX({});
  }, [markers]);

  const xMin = xRange?.[0];
  const xMax = xRange?.[1];
  const span = xMin != null && xMax != null ? Math.max(1e-6, xMax - xMin) : 1;

  const pctFor = useCallback(
    (x: number) => {
      if (xMin == null) return 0;
      return Math.max(0, Math.min(100, ((x - xMin) / span) * 100));
    },
    [xMin, span],
  );

  const xFromClient = useCallback(
    (clientX: number) => {
      const el = railRef.current;
      if (!el || xMin == null || xMax == null) return xMin ?? 0;
      const rect = el.getBoundingClientRect();
      const innerLeft = rect.left + PLOT_MARGIN.l;
      const innerWidth = Math.max(1, rect.width - PLOT_MARGIN.l - PLOT_MARGIN.r);
      const t = Math.max(0, Math.min(1, (clientX - innerLeft) / innerWidth));
      return Math.round(xMin + t * (xMax - xMin));
    },
    [xMin, xMax],
  );

  useEffect(() => {
    function onMove(e: MouseEvent) {
      const d = dragRef.current;
      if (!d) return;
      if (Math.abs(e.clientX - d.startClientX) >= DRAG_THRESHOLD_PX) {
        d.moved = true;
      }
      if (!d.moved) return;
      if (!(d.marker.draggable && !disabled)) return;
      const x = xFromClient(e.clientX);
      d.x = x;
      setLocalX(prev => ({ ...prev, [d.key]: x }));
      onDragMove?.(d.marker, x);
    }
    function onUp() {
      const d = dragRef.current;
      if (!d) return;
      dragRef.current = null;
      setDraggingId(null);
      setHoverId(null);
      if (d.moved && d.marker.draggable && !disabled) {
        onDragEnd(d.marker, d.x);
      } else {
        onMarkerClick?.(d.marker);
      }
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [xFromClient, onDragMove, onDragEnd, onMarkerClick, disabled]);

  if (markers.length === 0 || xMin == null || xMax == null) return null;

  const slotAt = new Map<number, number>();

  return (
    <div
      ref={railRef}
      className="relative h-11 bg-white border-b border-[#e8e8e8] select-none"
      style={{ paddingLeft: PLOT_MARGIN.l, paddingRight: PLOT_MARGIN.r }}
    >
      <div className="relative h-full w-full">
        {markers.map(m => {
          const key = `${m.kind}:${m.id}`;
          const x = localX[key] ?? m.x;
          if (x < xMin - 0.5 || x > xMax + 0.5) return null;
          const slot = slotAt.get(Math.round(x)) ?? 0;
          slotAt.set(Math.round(x), slot + 1);
          const color =
            m.kind === 'need'
              ? NEED_MARKER_COLOR
              : m.kind === 'warning'
                ? WARNING_MARKER_COLOR
                : EVENT_MARKER_COLOR;
          const isWarning = m.kind === 'warning';
          const canDrag = m.draggable && !disabled && !isWarning;
          const isDrag = draggingId === key;
          const isHover = hoverId === key;

          return (
            <MarkerRailItem
              key={key}
              markerKey={key}
              marker={m}
              x={x}
              slot={slot}
              pctFor={pctFor}
              color={color}
              isWarning={isWarning}
              canDrag={canDrag}
              isDrag={isDrag}
              isHover={isHover}
              dragRef={dragRef}
              setDraggingId={setDraggingId}
              setHoverId={setHoverId}
            />
          );
        })}
      </div>
    </div>
  );
}
