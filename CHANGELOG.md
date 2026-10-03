# Endringslogg

## 0.9.0
- **Ingen utlogging ved oppdatering eller tjenestefeil:** Tokens lagres med en gang de er fornyet. En feil hos Amperium under fornyelsen (HTTP 5xx, 429, nettverk) gir bare en midlertidig feil og blir ikke tolket som ugyldig token. Hvert lagret token starter ikke lenger hele integrasjonen på nytt.
- **Logg inn på nytt:** Har integrasjonen mistet innloggingen, kan du nå sende en ny engangskode fra «Konfigurer på nytt» (før fantes ingen slik flyt).
- Ikon i `brand/` (vises i Home Assistant 2026.3 og nyere).
- 13 nye tester for token-fornyelsen.

## 0.8.0
- Kapasitetsgrunnlaget beregnes nå også fra timedata etter Finnås Kraftlags regel (snittet av de tre høyeste timene i tre ulike døgn): «Kapasitetsgrunnlag (beregnet, tre høyeste døgn)» med de tre toppene som attributt, og «Terskel for ny kapasitetstopp».
- Prognosesensoren for timeeffekt viser terskelen og om timen er på vei over den (krever valgt effektsensor).
- Regelen og trinnbeløpene (inkl. mva) er bekreftet mot tariffarket fra 1.1.2026.

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
