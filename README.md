# Ranking Liga Weekly · La Guarida del Dragón

Ranking mensual de la Liga Weekly de Star Wars Unlimited de [La Guarida del Dragón](https://www.laguaridadeldragon.cl/), con los resultados de [melee.gg](https://melee.gg/Hub/Organization/16078).

## Puntaje

- 3 puntos por cada victoria (los byes cuentan como victoria).
- 1 punto por asistir a cada weekly.
- Empates en puntos se ordenan por cantidad de victorias.
- Solo cuentan los torneos cuyo nombre dice "Liga Weekly".
- Cada weekly se asigna al mes en que se jugó, en hora de Chile.

## Cómo se actualiza

El flujo `.github/workflows/actualizar.yml` corre los miércoles a las 22:00 (hora de Chile) y repite la descarga algunas veces durante la noche y el jueves, porque GitHub a veces atrasa las tareas programadas:

1. `scraper/scrape.py` descarga los torneos desde melee.gg y escribe `site/data.json`.
2. El cambio se guarda en el repositorio.
3. La carpeta `site/` se publica en GitHub Pages.

Para actualizar a mano: pestaña **Actions** → **Actualizar ranking** → **Run workflow**.
