"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  createChart,
  IChartApi,
  ISeriesApi,
  LineStyle,
  Time,
} from "lightweight-charts";
import type { LiquidityLevel, MarketSnapshot } from "@/lib/types";

type Props = {
  snapshots: MarketSnapshot[];
  levels: LiquidityLevel[];
};

export default function LiquidityChart({ snapshots, levels }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0b0f14" },
        textColor: "#94a3b8",
        fontFamily:
          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      rightPriceScale: { borderColor: "#1f2937" },
      timeScale: { borderColor: "#1f2937", timeVisible: true, secondsVisible: false },
      crosshair: { mode: 1 },
    });
    chartRef.current = chart;

    const series: ISeriesApi<"Candlestick"> = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    const candleData = snapshots
      .slice()
      .sort(
        (a, b) =>
          new Date(a.timestamp_utc).getTime() -
          new Date(b.timestamp_utc).getTime(),
      )
      .map((c) => ({
        time: (new Date(c.timestamp_utc).getTime() / 1000) as Time,
        open: Number(c.open),
        high: Number(c.high),
        low: Number(c.low),
        close: Number(c.close),
      }));
    series.setData(candleData);

    for (const level of levels) {
      if (level.status === "invalidated") continue;
      const color =
        level.liquidity_side === "BSL"
          ? "#3b82f6"
          : level.liquidity_side === "SSL"
            ? "#fbbf24"
            : "#94a3b8";
      series.createPriceLine({
        price: Number(level.price),
        color,
        lineStyle: level.status === "taken" ? LineStyle.Dashed : LineStyle.Solid,
        lineWidth: 1,
        axisLabelVisible: true,
        title: `${level.level_type} ${level.status}`,
      });
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [snapshots, levels]);

  return (
    <div
      ref={containerRef}
      className="h-[480px] w-full rounded border border-shadow-border bg-shadow-bg"
    />
  );
}
