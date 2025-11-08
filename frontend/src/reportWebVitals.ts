import type { ReportCallback } from 'web-vitals';

const reportWebVitals = (onPerfEntry?: ReportCallback) => {
  if (onPerfEntry && onPerfEntry instanceof Function) {
    import('web-vitals').then((module) => {
      const runMetric = (
        metric?: (callback: ReportCallback) => void
      ): void => {
        if (typeof metric === 'function') {
          metric(onPerfEntry);
        }
      };

      type ModernWebVitalsModule = {
        onCLS?: (callback: ReportCallback) => void;
        onFCP?: (callback: ReportCallback) => void;
        onINP?: (callback: ReportCallback) => void;
        onLCP?: (callback: ReportCallback) => void;
        onTTFB?: (callback: ReportCallback) => void;
      };

      const modern = module as ModernWebVitalsModule;
      const legacy = module as unknown as Record<
        string,
        (callback: ReportCallback) => void
      >;

      runMetric(modern.onCLS ?? legacy.getCLS);
      runMetric(modern.onFCP ?? legacy.getFCP);
      runMetric(modern.onLCP ?? legacy.getLCP);
      runMetric(modern.onTTFB ?? legacy.getTTFB);
      runMetric(modern.onINP ?? legacy.getINP ?? legacy.getFID);
    });
  }
};

export default reportWebVitals;
