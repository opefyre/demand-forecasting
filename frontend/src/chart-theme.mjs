// Shared chart geometry; paint and typography come from the CSS design tokens.
export const chartTheme=Object.freeze({
  margin:Object.freeze({top:12,right:16,bottom:12,left:0}),
  forecastMargin:Object.freeze({left:0,right:24,top:12,bottom:0}),
  ticks:Object.freeze({className:'chart-tick'}),
  dot:Object.freeze({r:3}),
});

// Use the full saved group index, never the currently visible subset. Toggling
// a method must not change another method's paint or line pattern.
export function comparisonLine(index) {
  const slot=(index%5)+1;
  return {stroke:`var(--chart-method-${slot})`,
    strokeDasharray:`var(--chart-method-dash-${(Math.floor(index/5)+index)%5+1})`,
    strokeWidth:'var(--chart-line-width)'};
}
