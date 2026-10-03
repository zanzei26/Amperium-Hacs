# Endringslogg

Nyeste versjon øverst. Versjonsnummeret står i `custom_components/amperium/manifest.json`, og hver utgivelse på GitHub bruker teksten herfra som utgivelsesnotat. Versjonene 0.1.0–0.1.2 har ingen utgivelse på GitHub, bare commits.

Om testing: beregningene (`derived.py`, `hourpower.py`) og token-håndteringen (`api.py`) har automatiske tester som kjøres uten Home Assistant (`cd tests && python -m pytest`). Sensorer, oppsettsflyt, varsler og statistikkimport er skrevet mot Home Assistants API, men er ikke kjørt i en ekte Home Assistant av den som har skrevet koden. Meld fra under Issues hvis noe ikke virker.

## 0.11.0
- **Live effekt fra Amperium for deg med Dobbe-modul (eksperimentell, avslått som standard).** Ved oppsett kommer et nytt steg der du velger om du har en Dobbe-modul (HAN-sensoren som sender målingene til Amperium). Du kan endre valget senere under «Konfigurer» («Jeg har en Dobbe-modul»). Eksisterende installasjoner får «nei». Svarer du ja, kobler integrasjonen til samme sanntidsstrøm som live-visningen i appen (RabbitMQ/AMQP) og gir den nye sensoren «Effekt nå (Amperium live)». Svarer du nei, skjer ingenting av dette, og biblioteket installeres ikke. «Effekt nå» bruker nå denne rekkefølgen: din egen effektsensor, så Amperium live (hvis siste måling er under to minutter gammel), så Amperiums timeverdi.
- **Hvorfor:** Feltet `currentActivePowerImport` i `/api/sites` er ikke live (0,0 kW hos en ekte konto mens huset brukte ca. 1,35 kW). En test fra Home Assistant 3. oktober viste også at selve HTTP-kallet `POST /api/sites/{id}/stream/amqp` ga en tom liste med målinger. Live-verdiene kommer som meldinger på køen i svaret.
- **Hvordan det er bygget:** Fra Amperium-appens kode (2.3.0): rutingnøkkel `<MID>.O.<id>` (101 = aktiv effekt import), meldingskropp i JSON med tidspunkt og verdi i watt, og køen leses direkte uten å opprettes. Dette er ikke bekreftet mot ekte meldinger fra måleren.
- **Biblioteket aio-pika installeres første gang funksjonen slås på.** Mislykkes installasjonen, er bare live-funksjonen av (med en melding i loggen). Resten av integrasjonen påvirkes ikke.
- **Slik ser du om måleren leverer:** Attributtene på «Effekt nå (Amperium live)» viser `status` (`connecting`, `connected`, `error` eller `unavailable`), `messages` (antall mottatt), `age_seconds`, `observed_at` og `last_error`. Står den på `connected` mens `messages` blir 0, leverer måleren ikke live-målinger til Amperium akkurat nå (svakt mobilsignal på HAN-modulen er en mulig årsak, ikke bekreftet).
- Brudd på forbindelsen gir ny tilkobling med ventetid fra 5 sekunder til 5 minutter. Kommer det ingen meldinger på 10 minutter, abonnerer den på nytt. Innloggingsdetaljene fra abonnementet vises aldri i logg eller feilmeldinger.
- Token- og innloggingskoden er uendret. Abonnementskallet bruker gjeldende token. Får det 401, prøver live-funksjonen igjen senere, og fornyelsen skjer i den vanlige hentingen.
- 43 nye tester (112 totalt): rutingnøkkel og meldingsformat, kildevalg for «Effekt nå», løkken med feil og ny tilkobling (uten at innloggingsdetaljer lekker), abonnementskallet og tilkoblingen mot et falskt aio-pika. Ikke testet: mot en ekte RabbitMQ hos Amperium, installasjonen av biblioteket i Home Assistant, og sensorene i en ekte Home Assistant.

## 0.10.0
- **Nettleie før støtte og total brutto henger nå alltid sammen med tallene «etter».** «Nettleie før straumstøtte» er nå «Nettleie etter straumstøtte» (fra `/api/sites`) pluss støtten, og «Total brutto» er «Total kostnad etter straumstøtte» pluss fastledd pluss støtten. Da gjelder alltid: før − støtte = etter, og total brutto − støtte − fastledd = total etter støtte. Før bygde «før» på kostnadssvaret, som hentes sjeldnere, og hos en ekte konto ble avviket 0,75 kr (326,12 mot 326,87). Støtten kan henge inntil én time etter. Nedbrytingen i attributtene (kapasitetsledd, energiledd, avgifter) kommer fortsatt fra kostnadssvaret og kan derfor avvike noen øre fra sensorens sum. Forrige måned er uendret (der finnes ikke `/api/sites`-tall).
- **«Effekt nå» følger din egen effektsensor.** Velger du en effektsensor under «Konfigurer» (for eksempel en lokal HAN-leser eller Tibber Pulse), viser «Effekt nå» verdien fra den, omregnet til kW. Amperium oppgir effekt bare én gang i timen og ga hos en ekte konto 0,0 kW mens siste time hadde 2,064 kWh. Er sensoren utilgjengelig eller uten enhet (W, kW eller MW), brukes Amperiums verdi som reserve. Attributtene viser hvilken kilde som er brukt (`source`: `local_sensor` eller `amperium`), den lokale entiteten (`local_entity`) og Amperiums egen verdi (`amperium_kw`). Har du ikke valgt noen sensor, er «Effekt nå» som før (med `source: amperium`). «Effekt nå (live)» og prognosen for timeeffekt er uendret. «Effekt nå» oppdateres like ofte som din sensor.
- **Månedstallene starter nå kl. 00:00 lokal tid den 1., ikke kl. 00:00 UTC.** Hovedhentingen fra `/api/sites` (forbruk, energikostnad, nettleie, støtte, fastledd og kapasitetsgrunnlag «denne måneden») brukte 1. kl. 00:00 UTC, det vil si 01:00 vintertid og 02:00 sommertid. Timene før det falt utenfor måneden, mens timedata og kostnadssvaret (dag/natt, forrige måned) brukte lokal måned. Da kunne tallene ikke stemme med hverandre: i oktober viste en ekte konto dag + natt = 163,47 kWh mot forbruk denne måneden = 161,22 kWh.
- **README:** nytt avsnitt om at kapasitetsgrunnlaget er riktig fra første dag, og om terskelen og timeprognosen som hjelp mot nye topper.
- **Token- og innloggingskoden er uendret fra 0.9.1** (`refresh`, `_auth_get`, lagring av tokens og utløp). Første fornyelse hos en ekte konto er ikke skjedd ennå (forventet rundt 8. oktober 2026), så den delen er fortsatt bare testet med automatiske tester.
- Ikke verifisert mot Amperium eller i Home Assistant etter endringene: månedsstarten mot API-et, og at «Effekt nå» følger den lokale sensoren i en ekte Home Assistant. Etter oppdatering skal dag + natt og «Forbruk denne måneden» ligge tett sammen, og tallene bør stemme med «denne måneden» i appen.
- 20 nye tester (69 totalt): månedsstart i sommer- og vintertid, kilde for «Effekt nå», og at før/etter-tallene går opp.

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
