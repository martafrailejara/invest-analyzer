# Design — invest-analyzer

Sistema de diseño bloqueado de la app ("Cobalt Night"). Cada rediseño de página lee
este archivo antes de emitir código; se amplía o enmienda aquí, nunca con overrides
locales por página.

## Genre

atmospheric-technical (terminal financiera oscura; deriva del modern-minimal Cobalt)

## Macrostructure family

- Landing: Index-First (índice de instrumentos numerado; hero tipográfico corto)
- Páginas de app: Workbench (panel de configuración + lienzo de resultados) o
  columna única de resultados cuando no hay formulario. Varían solo archetypes.
- Sin páginas de contenido/marketing.

## Theme (oscuro por defecto; claro vía prefers-color-scheme: light)

- `--color-paper`   oklch(14% 0.015 256)
- `--color-paper-2` oklch(18% 0.018 256)
- `--color-ink`     oklch(95% 0.008 250)
- `--color-ink-2`   oklch(86% 0.012 253)
- `--color-rule`    oklch(26% 0.015 256)
- `--color-accent`  oklch(68% 0.17 256)  (cobalto luminoso; tinta oscura encima)
- `--color-focus`   oklch(68% 0.17 256)
- `--color-up`      oklch(72% 0.14 160)  (P&L positivo; el negativo usa --color-error)

Las paletas de series de los gráficos NO cambian: están validadas para CVD en ambos
modos con el validador de dataviz (cobalto/azul claro/violeta/verde/ámbar).

## Typography

- Display: Tomorrow, 500/600, normal (condensada técnica; titulares y cifras héroe)
- Body:    IBM Plex Sans, 400/500
- Mono:    JetBrains Mono, 400/500 — registro "lectura de máquina": nav, etiquetas,
  cifras tabulares, kbd. Uppercase con tracking 0.06em en labels.
- Display tracking: -0.01em
- Type scale anchor: --text-hero = clamp(2rem, 3.5vw + 0.5rem, 3.4rem)

## Spacing

Escala 4pt con nombres (--space-3xs … --space-3xl) en tokens.css. Solo tokens.

## Motion

- Easings: --ease-out cubic-bezier(0.16,1,0.3,1), --ease-in, --ease-in-out
- Reveal: ninguno (la app es instrumento, no cine). Count-up one-shot en cifras héroe.
- Reduced-motion: todo colapsa a instantáneo (regla global).

## Microinteractions stance

- Éxito silencioso; flash solo para confirmaciones de persistencia.
- Spinner en botón ocupado (aria-busy). Focus ring instantáneo, nunca animado.
- Máx. 3 primitivas de movimiento por página.

## CTA voice

- Primario: relleno acento, radio 6px, verbo concreto ("Ejecutar backtest").
- Secundario (btn--min): fondo paper-2, borde rule-2, mismo alto.
- Nunca píldoras, nunca gradientes.

## Per-page allowances

- Sin enrichment en ninguna página: los datos son el ornamento.
- Gráficos siempre vía tokens --chart-* (leídos en runtime por Chart.js).

## What pages MUST share

- Wordmark con el cuadrado de acento; barra superior con menús desplegables por
  grupo (N11-lite) + ⌘K a la derecha; en móvil, un único menú desplegable.
- El acento y su disciplina (≤5% del viewport).
- Tomorrow + IBM Plex Sans + JetBrains Mono (2+1, mono = un solo rol).
- Voz de CTA y radios (6px control / 10px tarjeta).
- Footer colofón denso mono con el descargo legal.
- Semántica P&L: positivo --color-up, negativo --color-error.

## What pages MAY differ on

- Archetype interno (stat strip vs tiles, tabla comparativa vs tabla anual).
- Presencia o no del panel Workbench (páginas sin formulario van a columna única).

## Exports

### tokens.css
La fuente canónica es `app/static/tokens.css` (este repo); replica los valores de
arriba más escalas completas, series de gráficos y bloque claro.

### Tailwind v4 `@theme`
```css
@theme {
  --color-paper: oklch(14% 0.015 256); --color-ink: oklch(95% 0.008 250);
  --color-accent: oklch(68% 0.17 256);
  --font-display: "Tomorrow", sans-serif; --font-body: "IBM Plex Sans", sans-serif;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### DTCG tokens.json
```json
{"color": {"paper": {"$value": "oklch(14% 0.015 256)", "$type": "color"},
  "ink": {"$value": "oklch(95% 0.008 250)", "$type": "color"},
  "accent": {"$value": "oklch(68% 0.17 256)", "$type": "color"}},
 "font": {"display": {"$value": "Tomorrow", "$type": "fontFamily"},
  "body": {"$value": "IBM Plex Sans", "$type": "fontFamily"}}}
```

### shadcn/ui
```css
:root { --background: 14% 0.015 256; --foreground: 95% 0.008 250;
  --primary: 68% 0.17 256; --primary-foreground: 14% 0.015 256;
  --border: 26% 0.015 256; --ring: 68% 0.17 256; --radius: 6px; }
```
