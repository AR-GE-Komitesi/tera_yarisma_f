/* İsraf bileşeni grafikleri: kazan artığı + tabak artığı = toplam israf oranı.
   Veri, sayfadaki <script type="application/json"> bloklarından okunur.
   Her grafiğin yanında aynı verinin tablo görünümü vardır. */
(function () {
  "use strict";

  if (typeof Chart === "undefined") return;

  var drawn = [];

  function token(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function pct(value) {
    if (value === null || value === undefined) return "—";
    return "%" + value.toLocaleString("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  var thresholdLine = {
    id: "esikCizgisi",
    afterDatasetsDraw: function (chart, args, opts) {
      if (opts.value === null || opts.value === undefined) return;
      var area = chart.chartArea;
      var horizontal = chart.options.indexAxis === "y";
      var scale = horizontal ? chart.scales.x : chart.scales.y;
      var px = scale.getPixelForValue(opts.value);
      var ctx = chart.ctx;
      ctx.save();
      ctx.strokeStyle = opts.color;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      if (horizontal) {
        ctx.moveTo(px, area.top);
        ctx.lineTo(px, area.bottom);
      } else {
        ctx.moveTo(area.left, px);
        ctx.lineTo(area.right, px);
      }
      ctx.stroke();
      ctx.restore();
    }
  };

  function draw(holder) {
    var source = document.getElementById(holder.dataset.kaynak);
    if (!source) return;
    var data = JSON.parse(source.textContent);
    if (!data.labels.length) return;

    var horizontal = holder.dataset.yon === "yatay";
    var surface = token("--surface");
    var colors = { pot: token("--series-pot"), plate: token("--series-plate") };
    var muted = token("--muted");
    var grid = token("--grid");
    var axis = token("--axis");
    var font = { family: token("--font") || "system-ui, sans-serif", size: 12 };
    var last = data.series.length - 1;

    if (horizontal) {
      holder.style.height = Math.max(140, data.labels.length * 40 + 56) + "px";
    }

    var values = data.totals.filter(function (v) { return v !== null; });
    var ceiling = Math.max.apply(null, values.concat([data.threshold || 0, 1]));

    var valueAxis = {
      stacked: true,
      beginAtZero: true,
      suggestedMax: Math.ceil(ceiling * 1.1),
      grid: { color: grid, drawTicks: false },
      border: { color: axis },
      ticks: {
        color: muted,
        font: font,
        padding: 6,
        callback: function (v) { return "%" + v; }
      }
    };
    var categoryAxis = {
      stacked: true,
      grid: { display: false },
      border: { color: axis },
      ticks: { color: muted, font: font, maxRotation: 0, autoSkip: true, autoSkipPadding: 12 }
    };

    var chart = new Chart(holder.querySelector("canvas"), {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: data.series.map(function (s, index) {
          return {
            label: s.label,
            data: s.values,
            backgroundColor: colors[s.key],
            borderColor: surface,
            borderWidth: 2,
            borderSkipped: "start",
            maxBarThickness: horizontal ? 22 : 30,
            borderRadius: function () {
              if (index !== last) return 0;
              return horizontal ? { topRight: 4, bottomRight: 4 } : { topLeft: 4, topRight: 4 };
            }
          };
        })
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false, axis: horizontal ? "y" : "x" },
        scales: horizontal ? { x: valueAxis, y: categoryAxis } : { x: categoryAxis, y: valueAxis },
        plugins: {
          legend: { display: false },
          esikCizgisi: { value: data.threshold, color: token("--critical") },
          tooltip: {
            backgroundColor: token("--surface-raised"),
            titleColor: token("--ink"),
            bodyColor: token("--ink-2"),
            footerColor: token("--ink"),
            borderColor: axis,
            borderWidth: 1,
            padding: 10,
            boxPadding: 4,
            titleFont: font,
            bodyFont: font,
            footerFont: { family: font.family, size: 12, weight: "600" },
            callbacks: {
              label: function (item) { return item.dataset.label + ": " + pct(item.raw); },
              footer: function (items) {
                var total = data.totals[items[0].dataIndex];
                var line = "Toplam israf: " + pct(total);
                if (data.threshold !== null && total !== null && total >= data.threshold) {
                  line += "  ▲ " + data.thresholdLabel + " aşıldı";
                }
                return line;
              }
            }
          }
        }
      },
      plugins: [thresholdLine]
    });
    drawn.push(chart);
  }

  function drawAll() {
    drawn.forEach(function (c) { c.destroy(); });
    drawn = [];
    document.querySelectorAll(".grafik[data-kaynak]").forEach(draw);
  }

  document.addEventListener("DOMContentLoaded", drawAll);
  if (window.matchMedia) {
    var scheme = window.matchMedia("(prefers-color-scheme: dark)");
    if (scheme.addEventListener) scheme.addEventListener("change", drawAll);
  }
})();
