# Endringslogg

## 0.7.0 (brudd for eksisterende installasjoner)

**Fjernet** (det skal bare finnes ett støttetall, nemlig støtten som er trukket fra nettleien i `gridRent`):
- «Straumstøtte denne måneden» (`subsidy_month`, summert fra timedata)
- «Norgespris minus straumstøtte forrige måned» (`norgespris_minus_subsidy`)
- «Norgespris minus straumstøtte denne måneden» (innført i 0.6.0)
- Kallet til endepunktet `norgespris-vs-subsidy` er borte.

Eksisterende installasjoner beholder disse som **utilgjengelige** entiteter i entitetsregisteret. Slett dem under Innstillinger → Enheter og tjenester → Entiteter. «Norgespris sparer denne måneden» dekker sammenligningen.

**Endret:**
- «Strømpris nå inkl. påslag og mva» (`spot_price_incl_vat`) tas fra inneværende time i prislisten (med foreløpig pris som reserve), ellers fra hovedhentingen. Manglende påslag regnes som 0.
- Laveste, høyeste og snitt spotpris har attributtet `consumer` (inkl. påslag og mva).
- Tester for de rene beregningene lagt til.

## 0.6.0
- Strømpris inkl. påslag og mva som sensor, og feltet `consumer` i timelistene.
- Norgespris minus straumstøtte for inneværende måned (fjernet igjen i 0.7.0).

## 0.5.1
- Støtten leses uten hensyn til fortegn. Dag/natt-kWh hentes fra `gridRent`. Forrige måned hentes fra kostnadssvaret.

## 0.5.0
- Rettet kostnadsmodellen (nettleie er etter straumstøtte, fastledd kommer i tillegg). Kapasitetsledd lagt inn.

Eldre versjoner: se utgivelsene på GitHub.
