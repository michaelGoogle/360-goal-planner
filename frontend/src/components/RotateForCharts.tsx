/** Portrait prompt to use landscape for the SV wealth chart. */
export function RotateForCharts() {
  return (
    <div className="x-rotate" role="status">
      <p className="x-rotate-t">Rotate for the wealth chart</p>
      <p className="x-rotate-s">
        Landscape opens the year-by-year projection. Portrait keeps your plan and the numbers.
      </p>
    </div>
  );
}
