/* Observatorio de Sostenibilidad Territorial de Marbella
   Capa B: lee exclusivamente los ficheros ligeros generados por el pipeline.
   Ninguna llamada a API pesada desde el navegador. */

(function () {
  'use strict';

  var MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
  var graficos = [];

  function css(nombre) {
    return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  }

  function etiquetaPeriodo(p) {
    var t = p.split('-');
    return MESES[parseInt(t[1], 10) - 1] + ' ' + t[0];
  }

  /* ---------- Tema claro / oscuro ---------- */
  function temaInicial() {
    var guardado = null;
    try { guardado = null; } catch (e) { /* sin estado persistente por diseno */ }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function aplicarTema(tema) {
    document.documentElement.setAttribute('data-theme', tema);
    graficos.forEach(function (g) { if (g && g.destroy) g.destroy(); });
    graficos = [];
    if (window._datosNdvi) dibujarGraficos(window._datosNdvi);
  }

  /* ---------- Opciones comunes de Chart.js ---------- */
  function opcionesBase() {
    var apagada = css('--tinta-apagada');
    var rejilla = css('--rejilla');
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--superficie'),
          titleColor: css('--tinta'),
          bodyColor: css('--tinta-2'),
          borderColor: css('--borde'),
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
          titleFont: { family: 'Montserrat', weight: '600', size: 13 },
          bodyFont: { family: 'Montserrat', size: 12.5 },
          displayColors: false
        }
      },
      scales: {
        x: {
          grid: { display: false },
          border: { color: css('--eje') },
          ticks: { color: apagada, font: { family: 'Montserrat', size: 11 }, maxRotation: 0, autoSkipPadding: 22 }
        },
        y: {
          grid: { color: rejilla, drawTicks: false },
          border: { display: false },
          ticks: { color: apagada, font: { family: 'Montserrat', size: 11 }, padding: 8 }
        }
      }
    };
  }

  /* ---------- Graficos ---------- */
  function dibujarGraficos(d) {
    var serie = d.serie;
    var azul = css('--serie-1');
    var azulSuave = css('--serie-1-suave');

    // 1. Serie mensual completa. Los huecos van como null: Chart.js corta la linea.
    graficos.push(new Chart(document.getElementById('g-serie'), {
      type: 'line',
      data: {
        labels: serie.map(function (r) { return etiquetaPeriodo(r.periodo); }),
        datasets: [{
          label: 'NDVI medio',
          data: serie.map(function (r) { return r.valor; }),
          borderColor: azul,
          backgroundColor: azulSuave,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: azul,
          pointHoverBorderColor: css('--superficie'),
          pointHoverBorderWidth: 2,
          tension: 0.25,
          fill: true,
          spanGaps: false
        }]
      },
      options: Object.assign(opcionesBase(), {
        plugins: Object.assign(opcionesBase().plugins, {
          tooltip: Object.assign(opcionesBase().plugins.tooltip, {
            callbacks: {
              label: function (ctx) {
                var r = serie[ctx.dataIndex];
                if (r.valor === null) return 'Sin observación válida';
                var lineas = ['NDVI medio: ' + r.valor.toFixed(3)];
                if (r.cobertura_pct !== null && r.cobertura_pct !== undefined) {
                  lineas.push('Cobertura: ' + r.cobertura_pct.toFixed(1) + '%');
                }
                if (r.aviso) lineas.push('Aviso: cobertura baja');
                return lineas;
              }
            }
          })
        })
      })
    }));

    // 2. Ciclo estacional: media por mes con banda de recorrido minimo-maximo
    var porMes = MESES.map(function () { return []; });
    serie.forEach(function (r) {
      if (r.valor !== null) porMes[parseInt(r.periodo.split('-')[1], 10) - 1].push(r.valor);
    });
    var media = porMes.map(function (v) { return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null; });
    var minimo = porMes.map(function (v) { return v.length ? Math.min.apply(null, v) : null; });
    var maximo = porMes.map(function (v) { return v.length ? Math.max.apply(null, v) : null; });

    graficos.push(new Chart(document.getElementById('g-estacional'), {
      type: 'line',
      data: {
        labels: MESES,
        datasets: [
          { label: 'Máximo', data: maximo, borderColor: 'transparent', backgroundColor: azulSuave, pointRadius: 0, fill: '+1', tension: 0.35 },
          { label: 'Mínimo', data: minimo, borderColor: 'transparent', backgroundColor: azulSuave, pointRadius: 0, fill: false, tension: 0.35 },
          {
            label: 'Media', data: media, borderColor: azul, borderWidth: 2,
            pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: azul,
            pointHoverBorderColor: css('--superficie'), pointHoverBorderWidth: 2,
            fill: false, tension: 0.35
          }
        ]
      },
      options: Object.assign(opcionesBase(), {
        plugins: Object.assign(opcionesBase().plugins, {
          tooltip: Object.assign(opcionesBase().plugins.tooltip, {
            callbacks: {
              label: function (ctx) {
                if (ctx.raw === null) return null;
                return ctx.dataset.label + ': ' + ctx.raw.toFixed(3);
              }
            }
          })
        })
      })
    }));

    // 3. Media anual
    var porAnio = {};
    serie.forEach(function (r) {
      if (r.valor === null) return;
      var a = r.periodo.split('-')[0];
      (porAnio[a] = porAnio[a] || []).push(r.valor);
    });
    var anios = Object.keys(porAnio).sort();
    var mediasAnuales = anios.map(function (a) {
      return porAnio[a].reduce(function (x, y) { return x + y; }, 0) / porAnio[a].length;
    });

    // Linea con puntos, no barras: la variacion interanual es pequena frente al valor
    // absoluto, y unas barras con el eje en cero no la mostrarian. Las barras codifican
    // magnitud por longitud y exigen eje a cero; una linea admite un eje ajustado.
    graficos.push(new Chart(document.getElementById('g-anual'), {
      type: 'line',
      data: {
        labels: anios,
        datasets: [{
          label: 'NDVI medio anual',
          data: mediasAnuales,
          borderColor: azul,
          backgroundColor: azul,
          borderWidth: 2,
          pointRadius: 4,
          pointHoverRadius: 6,
          pointBackgroundColor: azul,
          pointBorderColor: css('--superficie'),
          pointBorderWidth: 2,
          tension: 0.2,
          fill: false
        }]
      },
      options: Object.assign(opcionesBase(), {
        plugins: Object.assign(opcionesBase().plugins, {
          tooltip: Object.assign(opcionesBase().plugins.tooltip, {
            callbacks: {
              label: function (ctx) {
                var n = porAnio[ctx.label].length;
                return ['NDVI medio: ' + ctx.raw.toFixed(3), n + ' meses' + (n < 12 ? ' (año parcial)' : '')];
              }
            }
          })
        }),
        scales: Object.assign(opcionesBase().scales, {
          y: Object.assign(opcionesBase().scales.y, { beginAtZero: false })
        })
      })
    }));
  }

  /* ---------- KPI ---------- */
  function pintarKpis(d) {
    var conDato = d.serie.filter(function (r) { return r.valor !== null; });
    var ultimo = conDato[conDato.length - 1];
    var valores = conDato.map(function (r) { return r.valor; });

    var porMes = {};
    conDato.forEach(function (r) {
      var m = r.periodo.split('-')[1];
      (porMes[m] = porMes[m] || []).push(r.valor);
    });
    var mediasMes = Object.keys(porMes).map(function (m) {
      return porMes[m].reduce(function (a, b) { return a + b; }, 0) / porMes[m].length;
    });
    var amplitud = Math.max.apply(null, mediasMes) - Math.min.apply(null, mediasMes);

    var minimo = conDato.reduce(function (a, b) { return a.valor < b.valor ? a : b; });

    var kpis = [
      { etiqueta: 'Último valor', valor: ultimo.valor.toFixed(3), nota: etiquetaPeriodo(ultimo.periodo) },
      { etiqueta: 'Media de la serie', valor: (valores.reduce(function (a, b) { return a + b; }, 0) / valores.length).toFixed(3), nota: d.n_periodos + ' meses observados' },
      { etiqueta: 'Amplitud estacional', valor: amplitud.toFixed(3), nota: 'Diferencia entre el mes más y menos verde' },
      { etiqueta: 'Mínimo de la serie', valor: minimo.valor.toFixed(3), nota: etiquetaPeriodo(minimo.periodo) }
    ];

    document.getElementById('kpis').innerHTML = kpis.map(function (k) {
      return '<div class="kpi"><p class="kpi-etiqueta">' + k.etiqueta + '</p>' +
        '<p class="kpi-valor">' + k.valor + '</p>' +
        '<p class="kpi-nota">' + k.nota + '</p></div>';
    }).join('');
  }

  /* ---------- Estado de frescura ---------- */
  function pintarEstado(d, manifiesto) {
    document.getElementById('estado-ultimo').textContent = etiquetaPeriodo(d.ultimo_periodo);

    var comprobacion = manifiesto && manifiesto.ndvi_municipal && manifiesto.ndvi_municipal.ultima_ejecucion;
    document.getElementById('estado-comprobacion').textContent = comprobacion
      ? new Date(comprobacion).toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' })
      : 'No disponible';

    // Sentinel-2 publica cada pocos dias; mas de dos meses de retraso indica anomalia
    var t = d.ultimo_periodo.split('-');
    var ultimo = new Date(parseInt(t[0], 10), parseInt(t[1], 10) - 1, 1);
    var hoy = new Date();
    var meses = (hoy.getFullYear() - ultimo.getFullYear()) * 12 + (hoy.getMonth() - ultimo.getMonth());

    var el = document.getElementById('estado-frescura');
    if (meses <= 1) { el.className = 'pastilla al-dia'; el.textContent = 'Al día'; }
    else if (meses <= 3) { el.className = 'pastilla demorado'; el.textContent = 'Demorado ' + meses + ' meses'; }
    else { el.className = 'pastilla detenido'; el.textContent = 'Desactualizado ' + meses + ' meses'; }
  }

  /* ---------- Tabla ---------- */
  function pintarTabla(d) {
    document.getElementById('tabla-cuerpo').innerHTML = d.serie.map(function (r) {
      if (r.valor === null) {
        return '<tr><td>' + etiquetaPeriodo(r.periodo) + '</td>' +
          '<td colspan="5">Sin dato</td><td>' + (r.motivo || '') + '</td></tr>';
      }
      return '<tr><td>' + etiquetaPeriodo(r.periodo) + '</td>' +
        '<td>' + r.valor.toFixed(4) + '</td>' +
        '<td>' + r.mediana.toFixed(4) + '</td>' +
        '<td>' + r.p25.toFixed(4) + '</td>' +
        '<td>' + r.p75.toFixed(4) + '</td>' +
        '<td' + (r.aviso ? ' class="marcado"' : '') + '>' + r.cobertura_pct.toFixed(1) + '%</td>' +
        '<td>' + (r.aviso || '') + '</td></tr>';
    }).join('');
  }

  /* ---------- Ficha de metadatos ---------- */
  function pintarFicha(ficha) {
    var filas = [
      ['Fuente', ficha.fuente],
      ['Fórmula', '<code>' + ficha.formula + '</code>'],
      ['Resolución espacial', ficha.resolucion_espacial],
      ['Resolución temporal', ficha.resolucion_temporal],
      ['Método de cálculo', ficha.metodo],
      ['Enmascaramiento', ficha.enmascaramiento],
      ['Sistema de referencia', 'Petición en EPSG:' + ficha.epsg_peticion + ' · Cálculo de superficies en EPSG:' + ficha.epsg_calculo],
      ['Periodo de la serie', ficha.serie_desde + ' a ' + ficha.serie_hasta + ' (' + ficha.n_periodos + ' meses, ' + ficha.n_huecos + ' huecos)'],
      ['Recorrido observado', ficha.valor_minimo_serie + ' a ' + ficha.valor_maximo_serie],
      ['Licencia', ficha.licencia]
    ];
    document.getElementById('ficha').innerHTML = filas.map(function (f) {
      return '<dt>' + f[0] + '</dt><dd>' + f[1] + '</dd>';
    }).join('');

    document.getElementById('lista-limitaciones').innerHTML =
      (ficha.limitaciones || []).map(function (l) { return '<li>' + l + '</li>'; }).join('');
  }

  /* ---------- Mapa ---------- */
  function pintarMapa(geojson, fichaLimite) {
    var mapa = L.map('mapa', { scrollWheelZoom: false });

    // El mapa base sigue al tema para no romper el contraste en modo oscuro
    var oscuro = document.documentElement.getAttribute('data-theme') === 'dark';
    L.tileLayer('https://{s}.basemaps.cartocdn.com/' + (oscuro ? 'dark_all' : 'light_all') + '/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      maxZoom: 19
    }).addTo(mapa);

    // Capa ambiental servida por WMS bajo demanda, no preprocesada.
    // El nombre de capa procede del GetCapabilities del servicio, no de una convencion.
    L.tileLayer.wms('https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_RENPA', {
      layers: 'red_natura_2000', format: 'image/png', transparent: true, opacity: 0.5,
      attribution: 'REDIAM, Junta de Andalucía'
    }).addTo(mapa);

    var capa = L.geoJSON(geojson, {
      style: { color: css('--serie-1'), weight: 2.5, fillColor: css('--serie-1'), fillOpacity: 0.07 }
    }).addTo(mapa);
    mapa.fitBounds(capa.getBounds(), { padding: [18, 18] });

    var datos = [
      ['Superficie', fichaLimite.superficie_ha.toLocaleString('es-ES') + ' ha'],
      ['Código INE', fichaLimite.codigo_ine],
      ['Fuente del límite', 'CNIG'],
      ['Sistema de referencia', 'EPSG:' + fichaLimite.epsg_calculo]
    ];
    document.getElementById('datos-ambito').innerHTML = datos.map(function (d) {
      return '<div class="dato"><p class="dato-etiqueta">' + d[0] + '</p><p class="dato-valor">' + d[1] + '</p></div>';
    }).join('');
  }

  /* ---------- Arranque ---------- */
  function json(ruta) {
    return fetch(ruta).then(function (r) {
      if (!r.ok) throw new Error('No se pudo cargar ' + ruta);
      return r.json();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.documentElement.setAttribute('data-theme', temaInicial());

    document.getElementById('btn-tema').addEventListener('click', function () {
      var actual = document.documentElement.getAttribute('data-theme');
      aplicarTema(actual === 'dark' ? 'light' : 'dark');
    });

    var btnTabla = document.getElementById('btn-tabla');
    btnTabla.addEventListener('click', function () {
      var tabla = document.getElementById('tabla-datos');
      var visible = !tabla.hidden;
      tabla.hidden = visible;
      btnTabla.setAttribute('aria-expanded', String(!visible));
      btnTabla.textContent = visible ? 'Ver los datos en tabla' : 'Ocultar la tabla';
    });

    // Carga progresiva: cada bloque se pinta en cuanto tiene su dato,
    // sin que el fallo de uno bloquee a los demas.
    json('data/ndvi_municipal.json').then(function (d) {
      window._datosNdvi = d;
      pintarKpis(d);
      dibujarGraficos(d);
      pintarTabla(d);
      json('data/metadata/manifest.json')
        .then(function (m) { pintarEstado(d, m); })
        .catch(function () { pintarEstado(d, null); });
    }).catch(function (e) {
      console.error(e);
      document.getElementById('kpis').innerHTML =
        '<p class="kpi-nota">No se pudieron cargar los datos del indicador.</p>';
    });

    json('data/metadata/ndvi_municipal.json').then(pintarFicha).catch(function (e) { console.error(e); });

    Promise.all([
      json('data/limite_municipal.geojson'),
      json('data/metadata/limite_municipal.json')
    ]).then(function (r) { pintarMapa(r[0], r[1]); }).catch(function (e) { console.error(e); });
  });
})();
