\# Seasonal Law v0.1 — SageOS



\## 1. Seasons (Northern Hemisphere, Meteorological)



SageOS recognizes four primary seasonal states:



\- \*\*Reflect\*\* — December, January, February  

\- \*\*Build\*\* — March, April, May  

\- \*\*Fuel\*\* — June, July, August  

\- \*\*Tend\*\* — September, October, November  



For v0.1, the inner season equals the outer season.



\## 2. Natural Inputs



Each day, the Natural Rhythm Engine computes:



\- `light\_cycle` — approximate hours of daylight

\- `avg\_temp` — synthetic seasonal temperature curve

\- `seasonal\_pressure` — 0–1, higher when colder and darker



\## 3. Seasonal Energy



Base seasonal energy by season:



\- Reflect → 0.40  

\- Build   → 0.60  

\- Fuel    → 0.80  

\- Tend    → 0.60  



Daily \*\*seasonal\_energy\*\* is:



> seasonal\_energy = base(season) − 0.20 × seasonal\_pressure



Clamped to \\\[0.0, 1.0\\].



This means:



\- Deep winter (high pressure) pulls Reflect energy downward.

\- Summer (low pressure) leaves Fuel energy close to its base.

\- Shoulder seasons (Build, Tend) sit in the middle.



\## 4. Use in SageOS



For v0.1:



\- Human and household energies remain at fixed base values.

\- seasonal\_energy is dynamic and recorded in `seasonal\_rhythm.csv`.

\- Morning Field Brief displays the live seasonal\_energy each day.



Later versions will:



\- Modulate human\_energy and household\_energy with seasonal\_pressure.

\- Introduce inner-season subphases (early/mid/late Fuel, etc.).

\- Feed seasonal\_energy into drift, alignment, and readiness.



