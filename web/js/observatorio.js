/* Observatorio de Sostenibilidad Territorial de Marbella
   Capa B: lee exclusivamente los ficheros ligeros generados por el pipeline.
   Ninguna llamada a API pesada desde el navegador. */

(function () {
  'use strict';

  var MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

  // Definicion de los indicadores publicados. Anadir uno nuevo es anadir una entrada aqui.
  var INDICADORES = [
    {
      clave: 'ndvi_municipal',
      bloque: 'Bloque 1 · Vegetación y espacios verdes',
      titulo: 'NDVI medio municipal',
      descripcion: 'Índice de vegetación de diferencia normalizada promediado sobre el término municipal, en compuesto mensual a partir de Sentinel-2.',
      unidad: '',
      decimales: 3,
      banda: null,
      columnas: [['Mediana', 'mediana'], ['P25', 'p25'], ['P75', 'p75']],
      notaAmplitud: 'Diferencia entre el mes más y menos verde'
    },
    {
      clave: 'lst_municipal',
      bloque: 'Bloque 2 · Clima urbano',
      titulo: 'Temperatura superficial terrestre',
      descripcion: 'Temperatura de la superficie del terreno promediada sobre el término municipal, a partir de los pasos de Landsat 8 y 9 hacia las 11:00 hora local. No es temperatura del aire.',
      unidad: ' °C',
      decimales: 1,
      banda: ['p10', 'p90'],
      notaBanda: 'La banda recoge el recorrido entre los percentiles 10 y 90 de la superficie.',
      columnas: [['Mediana', 'mediana'], ['P10', 'p10'], ['P90', 'p90'], ['Escenas', 'n_escenas']],
      notaAmplitud: 'Diferencia entre el mes más y menos cálido'
    },
    {
      clave: 'ndbi_municipal',
      bloque: 'Bloque 3 · Suelo y urbanización',
      titulo: 'NDBI, índice de superficie construida',
      descripcion: 'Índice normalizado de superficie construida. Crece con el sellado del suelo y el material urbano, y decrece con la vegetación. Debe leerse comparando el mismo mes entre años: en verano el agostamiento del suelo lo eleva sin que haya urbanización nueva.',
      unidad: '',
      decimales: 3,
      banda: null,
      columnas: [['Mediana', 'mediana'], ['P25', 'p25'], ['P75', 'p75']],
      notaAmplitud: 'Diferencia entre el mes de índice más alto y más bajo'
    },
    {
      clave: 'clorofila_litoral',
      bloque: 'Bloque 4 · Litoral y aguas',
      titulo: 'Clorofila-a en aguas litorales',
      descripcion: 'Concentración de clorofila-a en la franja marina de 2 km frente a la costa, a partir del producto oficial de Sentinel-3. Los productos oceánicos pierden fiabilidad cerca de la costa: la serie sirve para leer estacionalidad y tendencia, no como medida absoluta.',
      unidad: ' mg/m³',
      decimales: 3,
      banda: null,
      columnas: [],
      notaAmplitud: 'Diferencia entre el mes de mayor y menor concentración'
    },
    {
      clave: 'no2_troposferico',
      bloque: 'Bloque 5 · Energía y atmósfera',
      titulo: 'Dióxido de nitrógeno troposférico',
      descripcion: 'Columna troposférica de NO₂ sobre el municipio. El píxel de Sentinel-5P mide unos 5,5 × 3,5 km, de modo que sobre las 11.714 ha del término caben apenas una veintena de valores: la serie describe tendencia y estacionalidad de ámbito comarcal, no la calidad del aire de un punto concreto.',
      unidad: ' µmol/m²',
      decimales: 1,
      banda: null,
      columnas: [['Mediana', 'mediana'], ['Píxeles', 'pixeles_validos']],
      notaAmplitud: 'Diferencia entre el mes de mayor y menor columna'
    },
    {
      clave: 'radiacion_solar',
      bloque: 'Bloque 5 · Energía y atmósfera',
      titulo: 'Irradiación solar global horizontal',
      descripcion: 'Energía solar recibida por metro cuadrado de superficie horizontal, promediada sobre nueve puntos de muestreo del término municipal. Procede de un reanálisis de recorrido cerrado, no de una serie de satélite que crezca cada mes.',
      unidad: ' kWh/m²',
      decimales: 1,
      banda: ['minimo_espacial', 'maximo_espacial'],
      notaBanda: 'La banda recoge el recorrido entre los puntos de muestreo, es decir, la diferencia entre la costa y la sierra.',
      columnas: [['Mínimo espacial', 'minimo_espacial'], ['Máximo espacial', 'maximo_espacial'], ['Puntos', 'n_puntos']],
      notaAmplitud: 'Diferencia entre el mes más y menos soleado',
      agregadoAnual: 'suma'   // la cifra que se maneja son los kWh/m2 acumulados en el año
    }
  ];

  var graficos = [];
  var cargados = {};

  function css(n) {
    return getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  }

  function etiquetaPeriodo(p) {
    var t = p.split('-');
    return MESES[parseInt(t[1], 10) - 1] + ' ' + t[0];
  }

  function fmt(v, ind) {
    return v === null || v === undefined ? '—' : v.toFixed(ind.decimales) + ind.unidad;
  }

  /* ---------- Opciones comunes de Chart.js ---------- */
  function opcionesBase() {
    var apagada = css('--tinta-apagada');
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: css('--superficie'), titleColor: css('--tinta'),
          bodyColor: css('--tinta-2'), borderColor: css('--borde'), borderWidth: 1,
          padding: 12, cornerRadius: 8, displayColors: false,
          titleFont: { family: 'Montserrat', weight: '600', size: 13 },
          bodyFont: { family: 'Montserrat', size: 12.5 }
        }
      },
      scales: {
        x: {
          grid: { display: false }, border: { color: css('--eje') },
          ticks: { color: apagada, font: { family: 'Montserrat', size: 11 }, maxRotation: 0, autoSkipPadding: 22 }
        },
        y: {
          grid: { color: css('--rejilla'), drawTicks: false }, border: { display: false },
          ticks: { color: apagada, font: { family: 'Montserrat', size: 11 }, padding: 8 }
        }
      }
    };
  }

  /* ---------- Construccion del bloque de un indicador ---------- */
  function plantillaBloque(ind) {
    return '' +
      '<section class="bloque" aria-labelledby="t-' + ind.clave + '">' +
        '<div class="bloque-cabecera"><div>' +
          '<p class="bloque-supra">' + ind.bloque + '</p>' +
          '<h2 id="t-' + ind.clave + '">' + ind.titulo + '</h2>' +
          '<p class="bloque-desc">' + ind.descripcion + '</p>' +
        '</div></div>' +
        '<div class="rejilla-kpi" id="kpi-' + ind.clave + '"></div>' +
        '<figure class="figura"><figcaption>' +
          '<h3>Serie mensual completa</h3>' +
          '<p>Valor medio municipal por mes. Los meses sin observación válida se representan como discontinuidad; no se interpolan.' +
          (ind.notaBanda ? ' ' + ind.notaBanda : '') +
          '</p></figcaption>' +
          '<div class="lienzo"><canvas id="g-serie-' + ind.clave + '" role="img" aria-label="Serie mensual de ' + ind.titulo + '"></canvas></div>' +
        '</figure>' +
        '<div class="rejilla-dos">' +
          '<figure class="figura"><figcaption><h3>Ciclo estacional medio</h3>' +
            '<p>Promedio de cada mes en el conjunto de la serie. La banda representa el recorrido entre el mínimo y el máximo observados.</p></figcaption>' +
            '<div class="lienzo lienzo-bajo"><canvas id="g-est-' + ind.clave + '" role="img" aria-label="Ciclo estacional de ' + ind.titulo + '"></canvas></div></figure>' +
          '<figure class="figura"><figcaption><h3>' + (ind.agregadoAnual === 'suma' ? 'Acumulado anual' : 'Media anual') + '</h3>' +
            '<p>' + (ind.agregadoAnual === 'suma'
              ? 'Suma de los meses disponibles en cada año. Un año incompleto acumula menos.'
              : 'Promedio de los meses disponibles en cada año. El año en curso es parcial.') + '</p></figcaption>' +
            '<div class="lienzo lienzo-bajo"><canvas id="g-anual-' + ind.clave + '" role="img" aria-label="Media anual de ' + ind.titulo + '"></canvas></div></figure>' +
        '</div>' +
        '<div class="bloque-acciones">' +
          '<button type="button" class="btn" data-tabla="' + ind.clave + '" aria-expanded="false" aria-controls="tabla-' + ind.clave + '">Ver los datos en tabla</button> ' +
          '<button type="button" class="btn" data-ficha="' + ind.clave + '" aria-expanded="false" aria-controls="ficha-' + ind.clave + '">Ver la ficha del indicador</button>' +
        '</div>' +
        '<div id="tabla-' + ind.clave + '" class="envoltura-tabla" hidden>' +
          '<table><caption class="sr-only">Serie mensual de ' + ind.titulo + '</caption>' +
          '<thead id="cab-' + ind.clave + '"></thead><tbody id="cuerpo-' + ind.clave + '"></tbody></table>' +
        '</div>' +
        '<div id="ficha-' + ind.clave + '" hidden>' +
          '<dl class="ficha" id="dl-' + ind.clave + '"></dl>' +
          '<div class="aviso"><h3>Limitaciones declaradas</h3><ul id="lim-' + ind.clave + '"></ul></div>' +
        '</div>' +
      '</section>';
  }

  /* ---------- Graficos de un indicador ---------- */
  function dibujar(ind, d) {
    var serie = d.serie;
    var azul = css('--serie-1');
    var suave = css('--serie-1-suave');
    var sup = css('--superficie');

    function tt(base, extra) {
      var o = opcionesBase();
      o.plugins.tooltip.callbacks = { label: extra };
      return Object.assign(o, base || {});
    }

    // 1. Serie mensual. Los huecos van como null y Chart.js corta la linea.
    var conjuntos = [];
    if (ind.banda) {
      var inf = ind.banda[0], sup2 = ind.banda[1];
      conjuntos.push(
        { label: 'sup', data: serie.map(function (r) { return r[sup2]; }), borderColor: 'transparent', backgroundColor: suave, pointRadius: 0, fill: '+1', tension: 0.25, spanGaps: false },
        { label: 'inf', data: serie.map(function (r) { return r[inf]; }), borderColor: 'transparent', backgroundColor: suave, pointRadius: 0, fill: false, tension: 0.25, spanGaps: false }
      );
    }
    conjuntos.push({
      label: ind.titulo, data: serie.map(function (r) { return r.valor; }),
      borderColor: azul, backgroundColor: ind.banda ? 'transparent' : suave, borderWidth: 2,
      pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: azul,
      pointHoverBorderColor: sup, pointHoverBorderWidth: 2,
      tension: 0.25, fill: !ind.banda, spanGaps: false
    });

    graficos.push(new Chart(document.getElementById('g-serie-' + ind.clave), {
      type: 'line',
      data: { labels: serie.map(function (r) { return etiquetaPeriodo(r.periodo); }), datasets: conjuntos },
      options: tt(null, function (ctx) {
        var r = serie[ctx.dataIndex];
        if (r.valor === null) return ctx.datasetIndex === conjuntos.length - 1 ? 'Sin observación válida' : null;
        if (ctx.dataset.label === 'sup') return 'Máximo: ' + fmt(r[ind.banda[1]], ind);
        if (ctx.dataset.label === 'inf') return 'Mínimo: ' + fmt(r[ind.banda[0]], ind);
        var l = [ind.titulo + ': ' + fmt(r.valor, ind)];
        if (r.n_escenas) l.push(r.n_escenas + ' escena(s)');
        if (r.cobertura_pct !== undefined && r.cobertura_pct !== null) l.push('Cobertura: ' + r.cobertura_pct.toFixed(1) + '%');
        if (r.aviso) l.push('Aviso: cobertura baja');
        return l;
      })
    }));

    // 2. Ciclo estacional con banda de recorrido minimo-maximo
    var porMes = MESES.map(function () { return []; });
    serie.forEach(function (r) {
      if (r.valor !== null) porMes[parseInt(r.periodo.split('-')[1], 10) - 1].push(r.valor);
    });
    var media = porMes.map(function (v) { return v.length ? v.reduce(function (a, b) { return a + b; }, 0) / v.length : null; });
    var mini = porMes.map(function (v) { return v.length ? Math.min.apply(null, v) : null; });
    var maxi = porMes.map(function (v) { return v.length ? Math.max.apply(null, v) : null; });

    graficos.push(new Chart(document.getElementById('g-est-' + ind.clave), {
      type: 'line',
      data: {
        labels: MESES,
        datasets: [
          { label: 'Máximo', data: maxi, borderColor: 'transparent', backgroundColor: suave, pointRadius: 0, fill: '+1', tension: 0.35 },
          { label: 'Mínimo', data: mini, borderColor: 'transparent', backgroundColor: suave, pointRadius: 0, fill: false, tension: 0.35 },
          { label: 'Media', data: media, borderColor: azul, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: azul, pointHoverBorderColor: sup, pointHoverBorderWidth: 2, fill: false, tension: 0.35 }
        ]
      },
      options: tt(null, function (ctx) {
        return ctx.raw === null ? null : ctx.dataset.label + ': ' + fmt(ctx.raw, ind);
      })
    }));

    // 3. Media anual. Linea con puntos, no barras: la variacion interanual es pequena
    // frente al valor absoluto y unas barras con el eje en cero no la mostrarian.
    var porAnio = {};
    serie.forEach(function (r) {
      if (r.valor === null) return;
      var a = r.periodo.split('-')[0];
      (porAnio[a] = porAnio[a] || []).push(r.valor);
    });
    var suma = ind.agregadoAnual === 'suma';
    var anios = Object.keys(porAnio).sort();
    var mediasAnuales = anios.map(function (a) {
      var t = porAnio[a].reduce(function (x, y) { return x + y; }, 0);
      return suma ? t : t / porAnio[a].length;
    });

    var opc = tt(null, function (ctx) {
      var n = porAnio[ctx.label].length;
      var etq = suma ? 'Acumulado anual' : ind.titulo;
      return [etq + ': ' + fmt(ctx.raw, ind), n + ' meses' + (n < 12 ? ' (año parcial)' : '')];
    });
    opc.scales.y.beginAtZero = false;

    graficos.push(new Chart(document.getElementById('g-anual-' + ind.clave), {
      type: 'line',
      data: {
        labels: anios,
        datasets: [{
          label: 'Media anual', data: mediasAnuales,
          borderColor: azul, backgroundColor: azul, borderWidth: 2,
          pointRadius: 4, pointHoverRadius: 6, pointBorderColor: sup, pointBorderWidth: 2,
          tension: 0.2, fill: false
        }]
      },
      options: opc
    }));
  }

  /* ---------- KPI ---------- */
  function pintarKpis(ind, d) {
    // Una serie cerrada se declara como tal para que no se lea como desactualizada
    if (d.tipo_serie === 'reanalisis_cerrado') {
      var cab = document.querySelector('#t-' + ind.clave).closest('.bloque-cabecera');
      if (cab && !cab.querySelector('.pastilla')) {
        var p = document.createElement('p');
        p.innerHTML = '<span class="pastilla cerrada">Serie cerrada · termina en ' +
                      etiquetaPeriodo(d.serie_termina_en) + '</span>';
        p.style.margin = '12px 0 0';
        cab.querySelector('div').appendChild(p);
      }
    }
    var con = d.serie.filter(function (r) { return r.valor !== null; });
    if (!con.length) return;
    var ultimo = con[con.length - 1];
    var vals = con.map(function (r) { return r.valor; });

    var porMes = {};
    con.forEach(function (r) { (porMes[r.periodo.split('-')[1]] = porMes[r.periodo.split('-')[1]] || []).push(r.valor); });
    var mediasMes = Object.keys(porMes).map(function (m) {
      return porMes[m].reduce(function (a, b) { return a + b; }, 0) / porMes[m].length;
    });
    var amplitud = Math.max.apply(null, mediasMes) - Math.min.apply(null, mediasMes);
    var maximo = con.reduce(function (a, b) { return a.valor > b.valor ? a : b; });

    var kpis = [
      { e: 'Último valor', v: fmt(ultimo.valor, ind), n: etiquetaPeriodo(ultimo.periodo) },
      { e: 'Media de la serie', v: fmt(vals.reduce(function (a, b) { return a + b; }, 0) / vals.length, ind), n: con.length + ' meses observados' },
      { e: 'Amplitud estacional', v: fmt(amplitud, ind), n: ind.notaAmplitud },
      { e: 'Máximo de la serie', v: fmt(maximo.valor, ind), n: etiquetaPeriodo(maximo.periodo) }
    ];
    document.getElementById('kpi-' + ind.clave).innerHTML = kpis.map(function (k) {
      return '<div class="kpi"><p class="kpi-etiqueta">' + k.e + '</p><p class="kpi-valor">' + k.v +
             '</p><p class="kpi-nota">' + k.n + '</p></div>';
    }).join('');
  }

  /* ---------- Tabla ---------- */
  function pintarTabla(ind, d) {
    var cols = ['Periodo', 'Media'].concat(ind.columnas.map(function (c) { return c[0]; }))
                                     .concat(['Cobertura', 'Observaciones']);
    document.getElementById('cab-' + ind.clave).innerHTML =
      '<tr>' + cols.map(function (c) { return '<th scope="col">' + c + '</th>'; }).join('') + '</tr>';

    document.getElementById('cuerpo-' + ind.clave).innerHTML = d.serie.map(function (r) {
      if (r.valor === null) {
        return '<tr><td>' + etiquetaPeriodo(r.periodo) + '</td><td colspan="' + (cols.length - 2) +
               '">Sin dato</td><td>' + (r.motivo || '') + '</td></tr>';
      }
      var c = [etiquetaPeriodo(r.periodo), fmt(r.valor, ind)];
      ind.columnas.forEach(function (col) {
        var v = r[col[1]];
        // Los recuentos son enteros, no magnitudes con unidad
        c.push(typeof v === 'number' && col[1].indexOf('n_') === 0 ? String(v) : fmt(v, ind));
      });
      c.push((r.cobertura_pct !== undefined && r.cobertura_pct !== null ? r.cobertura_pct.toFixed(1) + '%' : '—'));
      c.push(r.aviso || (r.escenas_descartadas ? r.escenas_descartadas + ' escena(s) descartada(s)' : ''));
      return '<tr>' + c.map(function (x, i) {
        return '<td' + (i === c.length - 2 && r.aviso ? ' class="marcado"' : '') + '>' + x + '</td>';
      }).join('') + '</tr>';
    }).join('');
  }

  /* ---------- Ficha ---------- */
  function pintarFicha(ind, f) {
    var filas = [
      ['Fuente', f.fuente],
      ['Fórmula', '<code>' + f.formula + '</code>'],
      ['Resolución espacial', f.resolucion_espacial],
      ['Resolución temporal', f.resolucion_temporal],
      ['Método de cálculo', f.metodo],
      ['Enmascaramiento', f.enmascaramiento],
      ['Periodo de la serie', f.serie_desde + ' a ' + f.serie_hasta + ' (' + f.n_periodos + ' meses, ' + f.n_huecos + ' huecos)'],
      ['Recorrido observado', f.valor_minimo_serie + ' a ' + f.valor_maximo_serie],
      ['Licencia', f.licencia]
    ];
    if (f.hora_de_paso) filas.splice(4, 0, ['Hora de paso', f.hora_de_paso]);
    if (f.epsg_peticion) filas.splice(6, 0, ['Sistema de referencia', 'Petición en EPSG:' + f.epsg_peticion + ' · Cálculo de superficies en EPSG:' + f.epsg_calculo]);

    document.getElementById('dl-' + ind.clave).innerHTML =
      filas.map(function (x) { return '<dt>' + x[0] + '</dt><dd>' + x[1] + '</dd>'; }).join('');
    document.getElementById('lim-' + ind.clave).innerHTML =
      (f.limitaciones || []).map(function (l) { return '<li>' + l + '</li>'; }).join('');
  }


  /* ---------- Bloque transversal: cruce ambiental y turistico ---------- */
  // Tres slots de la paleta categorica, en orden fijo y validados para separacion CVD.
  // El color sigue a la serie, nunca a su posicion, y no se cicla.
  var COLORES_CRUCE = { pernoctaciones: '--serie-1', ndvi: '--serie-3', lst: '--serie-2' };

  function pintarCruce(d, ficha) {
    var perf = d.perfil_estacional_normalizado;
    var crudo = d.perfil_estacional_crudo;
    var sup = css('--superficie');

    var defs = [
      { k: 'pernoctaciones', etq: 'Pernoctaciones', dec: 0, uni: '' },
      { k: 'ndvi', etq: 'NDVI', dec: 3, uni: '' },
      { k: 'lst', etq: 'Temperatura superficial', dec: 1, uni: ' \u00b0C' }
    ];

    graficos.push(new Chart(document.getElementById('g-cruce'), {
      type: 'line',
      data: {
        labels: MESES,
        datasets: defs.map(function (x) {
          var c = css(COLORES_CRUCE[x.k]);
          return {
            label: x.etq, data: perf[x.k], borderColor: c, backgroundColor: c,
            borderWidth: 2, pointRadius: 0, pointHoverRadius: 5,
            pointHoverBackgroundColor: c, pointHoverBorderColor: sup, pointHoverBorderWidth: 2,
            tension: 0.35, fill: false
          };
        })
      },
      options: (function () {
        var o = opcionesBase();
        // Se muestra el valor real, no el normalizado: la escala 0-1 solo sirve para superponer
        o.plugins.tooltip.callbacks = { label: function (ctx) {
          var x = defs[ctx.datasetIndex];
          var v = crudo[x.k][ctx.dataIndex];
          if (v === null || v === undefined) return null;
          var txt = x.dec === 0 ? Math.round(v).toLocaleString('es-ES') : v.toFixed(x.dec);
          return x.etq + ': ' + txt + x.uni;
        } };
        o.scales.y.min = 0;
        o.scales.y.max = 1;
        return o;
      })()
    }));

    // La identidad nunca queda solo en el color: la leyenda esta siempre presente
    document.getElementById('leyenda-cruce').innerHTML = defs.map(function (x) {
      return '<span class="leyenda-item"><span class="leyenda-marca" style="background:' +
             css(COLORES_CRUCE[x.k]) + '"></span>' + x.etq + '</span>';
    }).join('');

    var conInt = d.serie.filter(function (r) { return r.pernoctaciones_por_plaza_dia != null; });
    var azul = css('--serie-1');
    graficos.push(new Chart(document.getElementById('g-intensidad'), {
      type: 'line',
      data: {
        labels: conInt.map(function (r) { return etiquetaPeriodo(r.periodo); }),
        datasets: [{
          label: 'Pernoctaciones por plaza y dia',
          data: conInt.map(function (r) { return r.pernoctaciones_por_plaza_dia; }),
          borderColor: azul, backgroundColor: css('--serie-1-suave'), borderWidth: 2,
          pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: azul,
          pointHoverBorderColor: sup, pointHoverBorderWidth: 2, tension: 0.25, fill: true
        }]
      },
      options: (function () {
        var o = opcionesBase();
        o.plugins.tooltip.callbacks = { label: function (ctx) {
          var r = conInt[ctx.dataIndex];
          var l = [ctx.raw.toFixed(2) + ' pernoct./plaza y d\u00eda'];
          if (r.provisional) l.push('Dato provisional del INE');
          return l;
        } };
        return o;
      })()
    }));

    var c = {};
    (d.cruces || []).forEach(function (x) { c[x.variable] = x; });
    var co = d.coincidencias || {};
    var kpis = [
      { e: 'Correlaci\u00f3n con el NDVI', v: c.ndvi ? c.ndvi.correlacion_pearson.toFixed(3) : '\u2014',
        n: 'Negativa: m\u00e1s ocupaci\u00f3n, menos verde' },
      { e: 'Correlaci\u00f3n con la LST', v: c.lst ? c.lst.correlacion_pearson.toFixed(3) : '\u2014',
        n: 'Positiva: m\u00e1s ocupaci\u00f3n, m\u00e1s calor superficial' },
      { e: 'Mes de m\u00e1xima ocupaci\u00f3n', v: co.mes_maxima_ocupacion || '\u2014', n: 'Media de la serie' },
      { e: 'Mes de m\u00ednimo NDVI', v: co.mes_minimo_ndvi || '\u2014', n: 'Media de la serie' }
    ];
    document.getElementById('kpi-cruce').innerHTML = kpis.map(function (k) {
      return '<div class="kpi"><p class="kpi-etiqueta">' + k.e + '</p><p class="kpi-valor">' +
             k.v + '</p><p class="kpi-nota">' + k.n + '</p></div>';
    }).join('');

    if (co.mes_maxima_ocupacion && co.mes_maxima_ocupacion === co.mes_minimo_ndvi) {
      var pico = crudo.pernoctaciones[MESES.indexOf(co.mes_maxima_ocupacion)];
      var validos = crudo.pernoctaciones.filter(function (v) { return v !== null && v !== undefined; });
      var valle = Math.min.apply(null, validos);
      document.getElementById('hallazgo-cruce').innerHTML =
        '<strong>' + co.mes_maxima_ocupacion + ' concentra a la vez el m\u00e1ximo de ocupaci\u00f3n, ' +
        'el m\u00ednimo de vegetaci\u00f3n y el m\u00e1ximo de temperatura superficial.</strong> ' +
        'El municipio recibe entonces ' + (pico / valle).toFixed(1) + ' veces m\u00e1s pernoctaciones ' +
        'que en el mes m\u00e1s tranquilo, y lo hace cuando la vegetaci\u00f3n est\u00e1 en su punto m\u00e1s bajo ' +
        'y las superficies alcanzan su temperatura m\u00e1xima.';
    }

    if (ficha) {
      document.getElementById('dl-cruce').innerHTML = [
        ['Fuente', ficha.fuente], ['M\u00e9todo de c\u00e1lculo', ficha.metodo],
        ['Periodo', ficha.serie_desde + ' a ' + ficha.serie_hasta],
        ['Licencia', ficha.licencia]
      ].map(function (x) { return '<dt>' + x[0] + '</dt><dd>' + x[1] + '</dd>'; }).join('');
      document.getElementById('lim-cruce').innerHTML =
        (ficha.limitaciones || []).map(function (l) { return '<li>' + l + '</li>'; }).join('');
    }
  }

  /* ---------- Estado de frescura ---------- */
  function pintarEstado(estado) {
    var claves = Object.keys(cargados);
    if (!claves.length) return;
    var vivas = claves.filter(function (k) { return cargados[k].tipo_serie !== 'reanalisis_cerrado'; });
    var ultimos = (vivas.length ? vivas : claves)
      .map(function (k) { return cargados[k].ultimo_periodo; }).filter(Boolean).sort();
    var ultimo = ultimos[ultimos.length - 1];
    document.getElementById('estado-ultimo').textContent = etiquetaPeriodo(ultimo);

    // La marca de comprobacion no se versiona: llega en estado.json con el despliegue
    var c = estado && estado.ultima_comprobacion;
    document.getElementById('estado-comprobacion').textContent = c
      ? new Date(c).toLocaleDateString('es-ES', { day: '2-digit', month: 'long', year: 'numeric' })
      : 'No disponible';

    var t = ultimo.split('-');
    var hoy = new Date();
    var meses = (hoy.getFullYear() - parseInt(t[0], 10)) * 12 + (hoy.getMonth() - (parseInt(t[1], 10) - 1));
    var el = document.getElementById('estado-frescura');
    if (meses <= 1) { el.className = 'pastilla al-dia'; el.textContent = 'Al día'; }
    else if (meses <= 3) { el.className = 'pastilla demorado'; el.textContent = 'Demorado ' + meses + ' meses'; }
    else { el.className = 'pastilla detenido'; el.textContent = 'Desactualizado ' + meses + ' meses'; }

    document.getElementById('estado-indicadores').textContent = claves.length;
  }

  /* ---------- Mapa ---------- */
  function pintarMapa(geojson, ficha) {
    var mapa = L.map('mapa', { scrollWheelZoom: false });
    var oscuro = document.documentElement.getAttribute('data-theme') === 'dark';
    L.tileLayer('https://{s}.basemaps.cartocdn.com/' + (oscuro ? 'dark_all' : 'light_all') + '/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 19
    }).addTo(mapa);

    // Capa ambiental por WMS bajo demanda. El nombre de capa procede del GetCapabilities.
    L.tileLayer.wms('https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_RENPA', {
      layers: 'red_natura_2000', format: 'image/png', transparent: true, opacity: 0.5,
      attribution: 'REDIAM, Junta de Andalucía'
    }).addTo(mapa);

    var capa = L.geoJSON(geojson, {
      style: { color: css('--serie-1'), weight: 2.5, fillColor: css('--serie-1'), fillOpacity: 0.07 }
    }).addTo(mapa);
    mapa.fitBounds(capa.getBounds(), { padding: [18, 18] });

    document.getElementById('datos-ambito').innerHTML = [
      ['Superficie', ficha.superficie_ha.toLocaleString('es-ES') + ' ha'],
      ['Código INE', ficha.codigo_ine],
      ['Fuente del límite', 'CNIG'],
      ['Sistema de referencia', 'EPSG:' + ficha.epsg_calculo]
    ].map(function (d) {
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

  function alternar(boton, id, textos) {
    var caja = document.getElementById(id);
    var visible = !caja.hidden;
    caja.hidden = visible;
    boton.setAttribute('aria-expanded', String(!visible));
    boton.textContent = visible ? textos[0] : textos[1];
  }

  function aplicarTema(tema) {
    document.documentElement.setAttribute('data-theme', tema);
    graficos.forEach(function (g) { if (g && g.destroy) g.destroy(); });
    graficos = [];
    INDICADORES.forEach(function (ind) { if (cargados[ind.clave]) dibujar(ind, cargados[ind.clave]); });
    if (window._cruce) pintarCruce(window._cruce[0], window._cruce[1]);
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.documentElement.setAttribute(
      'data-theme',
      window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    );

    document.getElementById('btn-tema').addEventListener('click', function () {
      aplicarTema(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });

    var cont = document.getElementById('indicadores');
    cont.innerHTML = INDICADORES.map(plantillaBloque).join('');

    // Un unico delegado: no hay onclick en el HTML
    cont.addEventListener('click', function (ev) {
      var b = ev.target.closest('button');
      if (!b) return;
      if (b.dataset.tabla) alternar(b, 'tabla-' + b.dataset.tabla, ['Ver los datos en tabla', 'Ocultar la tabla']);
      if (b.dataset.ficha) alternar(b, 'ficha-' + b.dataset.ficha, ['Ver la ficha del indicador', 'Ocultar la ficha']);
    });

    // Carga progresiva: cada indicador se pinta en cuanto llega, sin que el fallo
    // de uno impida mostrar los demas.
    var promesas = INDICADORES.map(function (ind) {
      return json('data/' + ind.clave + '.json').then(function (d) {
        cargados[ind.clave] = d;
        pintarKpis(ind, d);
        dibujar(ind, d);
        pintarTabla(ind, d);
        return json('data/metadata/' + ind.clave + '.json').then(function (f) { pintarFicha(ind, f); });
      }).catch(function (e) {
        console.error(e);
        var caja = document.getElementById('kpi-' + ind.clave);
        if (caja) caja.innerHTML = '<p class="kpi-nota">Este indicador aún no tiene datos publicados.</p>';
      });
    });

    document.getElementById('btn-ficha-cruce').addEventListener('click', function () {
      alternar(this, 'ficha-cruce', ['Ver la ficha del indicador', 'Ocultar la ficha']);
    });

    Promise.all([
      json('data/presion_turistica.json'),
      json('data/metadata/presion_turistica.json').catch(function () { return null; })
    ]).then(function (r) {
      window._cruce = r;
      pintarCruce(r[0], r[1]);
    }).catch(function (e) { console.error(e); });

    Promise.all(promesas).then(function () {
      json('data/estado.json').then(pintarEstado).catch(function () { pintarEstado(null); });
    });

    Promise.all([
      json('data/limite_municipal.geojson'),
      json('data/metadata/limite_municipal.json')
    ]).then(function (r) { pintarMapa(r[0], r[1]); }).catch(function (e) { console.error(e); });
  });
})();
