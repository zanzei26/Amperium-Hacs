# Endringslogg

Nyeste versjon øverst. Versjonsnummeret står i `custom_components/amperium/manifest.json`, og hver utgivelse på GitHub bruker teksten herfra som utgivelsesnotat. Versjonene 0.1.0–0.1.2 har ingen utgivelse på GitHub, bare commits.

Om testing: beregningene (`derived.py`, `hourpower.py`) og token-håndteringen (`api.py`) har automatiske tester som kjøres uten Home Assistant (`cd tests && python -m pytest`). Sensorer, oppsettsflyt, varsler og statistikkimport er skrevet mot Home Assistants API, men er ikke kjørt i en ekte Home Assistant av den som har skrevet koden. Meld fra under Issues hvis noe ikke virker.

## 0.9.1
- **Bare én fornyelse av tokenet om gangen.** Treffer flere forespørsler utløpt token samtidig, fornyer den første, og de andre bruker det nye tokenet i stedet for å sende en fornyelse hver. Det hindrer at to fornyelser overskriver hverandre.
- **Innloggingens utløp lagres og vises.** Amperium oppgir når tokenene utløper (`accessTokenExpiresAt`, `refreshTokenExpiresAt`). Tidspunktene lagres sammen med tokenene og vises i den nye diagnostikksensoren «Innlogging gyldig til» (tidspunktet for fornyelsestokenet).
- **Varsel i god tid.** Er det under 30 dager til innloggingen utløper, får du et varsel under Innstillinger → Reparasjoner, og «Konfigurer på nytt» åpnes slik at du kan logge inn med ny engangskode. Varselet forsvinner etter ny innlogging.
- **Fornyelsen logges** (uten tokenverdier): utløp for fornyelsestokenet før og etter, og for tilgangstokenet. Det viser om fristen på ca. ett år løper videre fra hver fornyelse eller ligger fast.
- Installasjoner fra før 0.9.1 har ikke lagret noe utløpstidspunkt. Sensoren er tom, og varselet kan ikke komme, før tokenet er fornyet første gang (tilgangstokenet varer ca. fem dager) eller du har logget inn på nytt.
- 11 nye tester (49 totalt): to samtidige 401-svar gir én fornyelse, utløp lagres og beholdes, `days_until`.

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

## 0.4.0
- Valgfri live effekt fra en sensor du allerede har (for eksempel Tibber Pulse), valgt under «Konfigurer». Gir «Effekt nå (live)» (omregnet til kW) og «Timeeffekt denne timen (prognose)», som regner ut timesnittet så langt og anslår hvor timen ender.

## 0.3.3
- Nettleie forrige måned. Tydeligere navn på kostnadssensorene («… brutto …», «(energi + nettleie)»).
- Du velger Norgespris eller straumstøtte ved oppsett. Det gir «Kompensasjon denne måneden (din ordning)» og «Netto kostnad denne måneden (ca.)».
- Eksempelkort for kostnad: `examples/lovelace-kostnad.yaml`.

## 0.3.2
- Rettet hva «energikostnad» betyr: brutto energi (spot + påslag inkl. mva) før støtte, uten nettleie. Ny sensor for mva på energi, og «Netto kostnad med Norgespris/straumstøtte (ca.)» og «Norgespris sparer denne måneden (ca.)». (Nettleie og støtte ble rettet igjen i 0.5.0.)

## 0.3.1
- HAN-signalet vises som tekst (Ingen signal, Dårlig, Middels, Bra, Veldig bra) i «HAN-signalkvalitet».
- Timeforbruk som attributt på «Forbruk siste time», til grafer. Eksempel med apexcharts-card: `examples/lovelace-forbruk-og-pris.yaml`.

## 0.3.0
- Timeforbruk og -kostnad fra Amperium: forbruk i går, siste time og forrige måned, dag/natt-fordeling (timene kan endres under «Konfigurer»), eksport, energikostnad i går.
- Straumstøtte, Norgespris-kompensasjon og «Norgespris minus straumstøtte forrige måned».
- Timeforbruk importeres som statistikk til Energidashbordet (rundt en gang i timen). Integrasjonen avhenger nå av `recorder`.
- HAN-signalet som tall («HAN-signal»).
- Fra 0.7.0 er flere av støttesensorene herfra fjernet eller erstattet.

## 0.2.0
- Timepriser for i dag og i morgen (som attributter på spotpris-sensoren), og sensorer for laveste, høyeste og gjennomsnittlig timepris i dag.

## 0.1.2
- Sender samme `User-Agent` (`AmperiumApp/2.3.0`) og `Accept-Language` som den offisielle appen.

## 0.1.1
- Egen feilmelding når døgngrensen for engangskoder er nådd («Vent 24 timer og prøv igjen»).
- «HAN-måler online» er en diagnostikk-entitet. Sensorene har fornuftig visningspresisjon (antall desimaler).
- Nytt eksempeldashbord: `examples/lovelace-amperium.yaml`.

## 0.1.0
- Første versjon. Innlogging med telefonnummer og engangskode på SMS, tokens lagres og fornyes automatisk.
- Sensorer: forbruk denne måneden og i dag, effekt nå, kostnad, energikostnad og nettleie denne måneden, spotpris nå, og HAN-måler online.
