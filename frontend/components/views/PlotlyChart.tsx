"use client";

/**
 * Client-only Plotly wrapper. Built via the factory + the prebuilt minified
 * bundle so we don't pull plotly's full source through the bundler. Imported
 * with next/dynamic({ ssr: false }) from TimelineView, since plotly.js touches
 * `window` at import time and cannot run during SSR.
 */

import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import type { PlotParams } from "react-plotly.js";

const Plot = createPlotlyComponent(Plotly);

export default function PlotlyChart(props: PlotParams) {
  return <Plot {...props} />;
}
