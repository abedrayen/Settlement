export function formatCurrency(value: number, decimals = 0): string {
  return `£${value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function formatPercent(value: number, decimals = 0): string {
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(decimals)}%`;
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
