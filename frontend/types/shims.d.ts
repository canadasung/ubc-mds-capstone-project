// Minimal module shims for packages without bundled/complete TypeScript types.

// @tabler/icons-react ships ESM types that the bundler resolver occasionally
// resolves to the untyped CJS entry. Declare the icons we use as React SVG
// components so the rest of the app stays type-checked.
declare module "@tabler/icons-react" {
  import type { FC, SVGProps } from "react";
  export interface TablerIconsProps extends SVGProps<SVGSVGElement> {
    size?: number | string;
    stroke?: number | string;
    color?: string;
  }
  export type Icon = FC<TablerIconsProps>;
  export const IconSearch: Icon;
  export const IconCheck: Icon;
  export const IconChevronDown: Icon;
  export const IconChevronRight: Icon;
  export const IconInfoCircle: Icon;
  export const IconAlertTriangle: Icon;
  export const IconCircleCheck: Icon;
  export const IconX: Icon;
  const _default: Record<string, Icon>;
  export default _default;
}

declare module "plotly.js-dist-min" {
  const Plotly: any;
  export default Plotly;
}

declare module "react-plotly.js/factory" {
  import type { ComponentType } from "react";
  import type { PlotParams } from "react-plotly.js";
  export default function createPlotlyComponent(
    plotly: unknown,
  ): ComponentType<PlotParams>;
}
