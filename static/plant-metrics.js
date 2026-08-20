/* The curves of the metrics page, drawn with ApexCharts.
   Redrawn after every HTMX swap, since changing plant replaces the panel. */
(function () {
  // Recessive chrome: the ink of the labels never carries the identity of a
  // curve, the mark beside the title does.
  var INK = '#A1A1AA';
  var GRID = '#F4F4F5';

  var drawn = {};
  var width = {};

  // ApexCharts fixes its width when it draws. Told again whenever its holder
  // changed width, otherwise a curve keeps the width it was born with and
  // spills over its card. Watched two ways: the holder itself, and the window,
  // since either can be the one that moved.
  function sync() {
    Object.keys(drawn).forEach(function (field) {
      var holder = document.querySelector('.metric-chart[data-metric="' + field + '"]');
      if (!holder) {
        return;
      }
      var known = Math.round(holder.getBoundingClientRect().width);
      if (!known || width[field] === known) {
        return;
      }
      width[field] = known;
      drawn[field].updateOptions({ chart: { width: known } }, false, false);
    });
  }

  var pending = null;

  function syncSoon() {
    clearTimeout(pending);
    pending = setTimeout(sync, 120);
  }

  var watcher = window.ResizeObserver ? new ResizeObserver(syncSoon) : null;
  window.addEventListener('resize', syncSoon);

  function options(holder, points) {
    var unit = holder.dataset.unit;
    return {
      chart: {
        type: 'line',
        height: 260,
        fontFamily: "'Poppins', sans-serif",
        toolbar: { show: false },
        animations: { enabled: false },
      },
      series: [{ name: holder.dataset.title, data: points }],
      colors: [holder.dataset.colour],
      // Straight segments: a smoothed curve would invent measures between two points.
      stroke: { curve: 'straight', width: 2 },
      markers: { size: 4, hover: { size: 6 } },
      dataLabels: { enabled: false },
      legend: { show: false },
      grid: { borderColor: GRID, strokeDashArray: 0, padding: { left: 12, right: 12 } },
      xaxis: {
        type: 'datetime',
        labels: { datetimeUTC: false, style: { colors: INK, fontSize: '11px' } },
        axisBorder: { show: false },
        axisTicks: { show: false },
        crosshairs: { show: true },
        tooltip: { enabled: false },
      },
      yaxis: {
        labels: { style: { colors: INK, fontSize: '11px' } },
      },
      tooltip: {
        // The whole column answers, not just the dot itself.
        intersect: false,
        shared: false,
        x: { format: 'dd MMM HH:mm' },
        y: { formatter: function (value) { return value + ' ' + unit; } },
      },
    };
  }

  function render() {
    document.querySelectorAll('.metric-chart[data-metric]').forEach(function (holder) {
      var field = holder.dataset.metric;
      if (drawn[field]) {
        drawn[field].destroy();
        delete drawn[field];
        delete width[field];
      }
      var source = document.getElementById(field);
      if (!source) {
        return;
      }
      var points = JSON.parse(source.textContent);
      if (!points.length) {
        return;
      }
      drawn[field] = new ApexCharts(holder, options(holder, points));
      drawn[field].render();
      width[field] = Math.round(holder.getBoundingClientRect().width);
      if (watcher) {
        watcher.observe(holder);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', render);
  document.addEventListener('htmx:afterSwap', render);

  // Exposed for the console, and for anything wanting to redraw by hand.
  window.renderPlantMetrics = render;
})();
