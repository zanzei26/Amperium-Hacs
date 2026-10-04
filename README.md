# Finnås Kraftlag (Amperium) for Home Assistant

[![Åpne i Home Assistant og legg til i HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zanzei26&repository=Amperium-Hacs-Finnaas-kraftlag&category=integration)

Henter strømforbruk, kostnad og pris **direkte fra Finnås Kraftlag** via Amperium-plattformen – de samme tallene som vises i appen **Kraftlaget** fra Finnås Kraftlag, rett inn i Home Assistant.

> _Unofficial Home Assistant integration for the Amperium cloud platform (the **Kraftlaget** app from Finnås Kraftlag, Bømlo). Passwordless OTP login, HAN meter data as native sensors._

## Hvem fungerer dette for?

Bekreftet: kunder hos **Finnås Kraftlag** (Bømlo) som bruker appen **Kraftlaget** (`no.finnas_kraftlag.amperium`). Integrasjonen bruker samme API og samme innlogging som den appen.

Ikke bekreftet: om andre kraftlag bruker samme plattform, og om integrasjonen virker for dem. Prøver du den hos et annet kraftlag, meld fra under [Issues](https://github.com/zanzei26/Amperium-Hacs-Finnaas-kraftlag/issues) hva som skjedde, så oppdaterer vi listen.

## Hva du får

Sensorer per anlegg:

| Sensor | Beskrivelse |
|---|---|
| `sensor.*_forbruk_denne_maneden` | Forbruk hittil i måneden (kWh) |
| `sensor.*_forbruk_i_dag` | Forbruk i dag (kWh) |
| `sensor.*_effekt_na` | Effekt nå (kW). Følger din egen effektsensor hvis du har valgt en, ellers Amperiums verdi (oppdateres en gang i timen) |
| «Energikostnad brutto denne måneden» | Energi hittil i måneden, brutto inkl. mva, før støtte (kr), fra månedstallene |
| «Nettleie etter straumstøtte denne måneden» | Nettleie inkl. kapasitetsledd, **etter** straumstøtte og **uten** fastledd (kr) |
| «Total kostnad etter straumstøtte denne måneden» | Energi + nettleie som over, **uten** fastledd (kr). Dette er Amperiums eget månedstall |
| «… forrige måned» (energi, nettleie, total) | De samme tre tallene for forrige måned (kr) |
| «Nettleie før straumstøtte denne måneden» | Nettleie inkl. kapasitetsledd, før støtte, uten fastledd (kr): «Nettleie etter straumstøtte» + støtten, så før − støtte = etter. Postene ligger som attributter (fra kostnadssvaret, kan avvike noen øre) |
| «Fastledd denne måneden» | Fast månedlig avgift (kr). Den er ikke med i månedstallene over |
| «Total brutto denne måneden» | Energi + nettleie + fastledd, før støtte (kr): «Total kostnad etter straumstøtte» + fastledd + støtten |
| «Kapasitetsgrunnlag denne måneden» (kW) | Effekten kapasitetsleddet beregnes av, med trinnet og trinntabellen som attributter |
| «Kapasitetsleddet denne måneden» (kr) og «Til neste kapasitetstrinn» (kW) | Beløpet for trinnet du er i, og hvor mange kW det er til neste trinn. Samme for forrige måned |
| `sensor.*_spotpris_na` | Spotpris nå (kr/kWh), uten mva og påslag. Offisiell pris når den er fastsatt, ellers prisen for gjeldende time fra timelisten (foreløpig). Attributtet `official` viser hvilken |
| «Strømpris nå inkl. påslag og mva» | Prisen du betaler per kWh nå: (spot + påslag) × (1 + mva%), med mva-satsen fra Amperium. Tas fra inneværende time i prislisten. Avledet, ikke bekreftet mot appen |
| `sensor.*_laveste_spotpris_i_dag` | Laveste timepris i dag (kr/kWh), med timen og prisen inkl. påslag og mva (`consumer`) som attributter |
| `sensor.*_hoyeste_spotpris_i_dag` | Høyeste timepris i dag (kr/kWh), med timen og `consumer` som attributter |
| `sensor.*_spotpris_snitt_i_dag` | Gjennomsnittlig timepris i dag (kr/kWh), med snittet inkl. påslag og mva (`consumer`) som attributt |
| `sensor.*_forbruk_i_gar` | Forbruk i går (kWh), summert fra timedata i lokal tid |
| `sensor.*_forbruk_siste_time` | Forbruk siste hele time (kWh) |
| `sensor.*_forbruk_forrige_maned` | Forbruk forrige måned (kWh) |
| `sensor.*_forbruk_dag_denne_maneden` / `..._natt_...` | Forbruk dag og natt hittil i måneden (kWh), se «Dag og natt» |
| `sensor.*_energikostnad_brutto_i_gar` | Brutto energikostnad i går (kr): (spot + påslag) × kWh inkl. mva, før støtte |
| `sensor.*_energikostnad_brutto_denne_maneden` | Brutto energikostnad hittil i måneden (kr), summert fra timedata |
| `sensor.*_mva_pa_energi_denne_maneden` | Mva-delen av energikostnaden hittil i måneden (kr) |
| «Straumstøtte trukket fra nettleien denne måneden» | Straumstøtten slik den er trukket fra nettleien (kr) |
| «Norgespris-kompensasjon denne måneden» | Norgespris-kompensasjon summert fra timedata (kr) |
| «Kompensasjon denne måneden (din ordning)» | Beløpet for ordningen du har valgt (kr) |
| «Netto kostnad denne måneden (din ordning)» | Total kostnad inkl. fastledd, for ordningen du har valgt (kr). Se «Kostnad: brutto, støtte og netto» |
| «Netto kostnad med Norgespris» / «… med straumstøtte» | Netto for hver ordning, avslått som standard |
| «Norgespris sparer denne måneden» | Hvor mye mer Norgespris gir enn straumstøtte hittil i måneden (kr) |
| `sensor.*_eksport_*` | Eksport (solceller), avslått som standard. Slå på hvis du produserer strøm |
| `sensor.*_han_signal` | HAN-signalstyrke (diagnostikk) |
| `sensor.*_han_signalkvalitet` | HAN-signal som tekst: Ingen signal, Dårlig, Middels, Bra, Veldig bra, Ingen data eller Ikke på nett (diagnostikk) |
| `binary_sensor.*_han_maler_online` | Om HAN-måleren er online (diagnostikk) |
| «Innlogging gyldig til» | Når innloggingen (fornyelsestokenet) utløper (diagnostikk). Tom til tokenet er fornyet første gang eller du har logget inn på nytt, se «Innlogging og oppdateringer» |

Sensorene nullstilles daglig/månedlig, så de passer best som egne dashbordkort (se [`examples/lovelace-amperium.yaml`](examples/lovelace-amperium.yaml)).

### Energidashbordet

Integrasjonen importerer **timeforbruk** (og energikostnad, og eksport hvis du har solceller) som langtidsstatistikk i Home Assistant, rundt en gang i timen. Gå til **Innstillinger → Dashbord → Energi** og velg følgende statistikk:

| I Energidashbordet | Velg |
|---|---|
| Nettforbruk | `Amperium forbruk` |
| Kostnad: «Bruk en entitet som sporer totalkostnaden» | `Amperium energikostnad` |
| Retur til nett (hvis du har solceller) | `Amperium eksport` |

Noen ting å vite:
- Statistikken fylles ut for forrige og inneværende måned første gang. Eldre historikk importeres ikke.
- Tallene kommer med forsinkelse fra Amperium (HAN-måleren oppdateres time for time), så siste time kan mangle en stund.
- `Amperium energikostnad (brutto)` er brutto energikostnad (spot + påslag inkl. mva) **før** straumstøtte/Norgespris, og **uten nettleie**. Nettleie finnes bare i månedstallene fra `/api/sites`.

### Forbruk og pris per time (graf)

«Forbruk siste time» har attributtet `consumption_today` (en rad per hele time i dag), og «Spotpris nå» har `prices_today`. Eksempelet [`examples/lovelace-forbruk-og-pris.yaml`](examples/lovelace-forbruk-og-pris.yaml) viser forbruk som søyler og pris som linje med HACS-kortet apexcharts-card. Eksempelet er ikke testet.

### Live effekt fra en sensor du allerede har (valgfritt)

Amperium oppdaterer effekt bare én gang i timen. Under **Konfigurer** kan du velge en eksisterende effektsensor i Home Assistant, for eksempel en lokal HAN-leser eller **Tibber Pulse/Watty**.

**«Effekt nå»** følger da sensoren din (omregnet til kW, fra og med 0.10.0). Er sensoren utilgjengelig eller uten enhet (W, kW eller MW), brukes Amperiums verdi som reserve. Attributtet `source` viser hva som er brukt (`local_sensor` eller `amperium`), `local_entity` hvilken entitet, og `amperium_kw` hva Amperium selv oppgir. Har du ikke valgt noen sensor, viser «Effekt nå» Amperiums verdi, som bare oppdateres en gang i timen.

I tillegg får du to ekstra sensorer:

- **Effekt nå (live)**: speiler sensoren din, omregnet til kW (W, kW og MW støttes). Samme verdi som «Effekt nå» når sensoren virker.
- **Timeeffekt denne timen (prognose)**: kapasitetsleddet bygger på snittet av hver hele time, ikke på øyeblikkseffekt. Sensoren regner ut timesnittet så langt (tidsvektet) og anslår hvor timen ender hvis effekten holder seg. Attributtene viser snittet så langt og hvor stor del av timen som hadde målinger (`coverage`).

Velg en sensor som måler **hele huset**. En lader som Easee viser bare laderens effekt og passer ikke til kapasitetsleddet. Prognosen starter på nytt hvis Home Assistant startes midt i en time. Da regnes den ut fra målingene som finnes, og `coverage` viser det.

### Live effekt fra Amperium (Dobbe-modul, eksperimentell)

Amperium-appen viser live effekt fra en egen sanntidsstrøm (RabbitMQ/AMQP). Feltet «Effekt nå» fra vanlig henting oppdateres bare én gang i timen og kan stå på 0. Har du en **Dobbe-modul** (HAN-sensoren som sender målingene dine til Amperium), velger du det ved oppsett eller senere under **Konfigurer** («Jeg har en Dobbe-modul»). Svaret er **nei** som standard, også for eksisterende installasjoner. Svarer du ja, kobler integrasjonen seg til den samme strømmen som appen bruker, og du får sensoren **Effekt nå (Amperium live)**. Første gang installeres biblioteket `aio-pika`. Mislykkes det, er bare denne funksjonen av. Svarer du nei, skjer ingenting av dette.

«Effekt nå» bruker denne rekkefølgen: **din egen effektsensor** (se over), så **Amperium live** (siste måling må være under to minutter gammel), så Amperiums timeverdi. Attributtet `source` viser hva som er brukt (`local_sensor`, `amperium_live` eller `amperium`).

**Bekreftet i tester 3. oktober 2026, ikke over lang tid.** Meldingsformatet er lest fra appens kode. Tester i en ekte Home Assistant (én konto med Dobbe-modul) viste status `connected`, omtrent én måling hvert annet sekund, og verdier identiske med en lokal Tibber Pulse (1201 W mot 1,201 kW). Enheten fra Amperium er watt. I en overvåking på 15 minutter kom det meldinger uten opphold gjennom flere fornyelser av abonnementet (hvert 4. minutt). Det vanlige HTTP-kallet alene gir en tom liste, så live kommer bare via strømmen. Se attributtene på «Effekt nå (Amperium live)»: `status` (`connecting`, `connected`, `error`, `unavailable`), `messages` (antall mottatt), `age_seconds`, `last_error` (bare mens det er et problem) og `last_error_at`. Står den på `connected` mens `messages` forblir 0, leverer måleren ikke live-målinger til Amperium akkurat nå. Et svakt mobilsignal på HAN-modulen (se «HAN-signalkvalitet») kan være årsaken, men det er ikke bekreftet. Meld fra under Issues hva du ser, særlig hvis du ikke har Dobbe-modul, eller hvis forbindelsen faller ut over tid.

### Kostnad: brutto, støtte og netto

Amperiums månedstall er lettere å misforstå enn de ser ut til. Dette er hva tallene faktisk inneholder, utledet fra en ekte konto (oktober). **Det er ikke bekreftet av Amperium.**

- **Nettleie i månedstallene er allerede etter straumstøtte.** Nettleien består av energiledd dag og natt, elavgift, Enova-avgift og **kapasitetsleddet**, minus straumstøtten. Regnestykket går opp på øre: 46,31 + 20,15 + 14,09 + 1,98 + 400 (kapasitetstrinn 5–10 kW) − 154,12 (støtte) = 328,41, mot oppgitt 328,40. Derfor kan nettleien bli negativ i en måned med mye støtte.
- **Fastleddet er ikke med** i nettleien eller i total fra månedstallene. Det kommer i tillegg (egen sensor). Det ser ut til å være satt per periode og ikke per dag (observert 25 kr for tre dager i oktober og 50 kr for hele september), så det kan hoppe.
- **Energi** (brutto, spot + påslag inkl. mva) er før støtte.
- Beløpene ser ut til å være **inkludert mva**.

Derfor regnes sensorene slik:

- **Total brutto** = Amperiums månedstotal (etter støtte) + fastledd + støtten. Det er det samme som energi + nettleie før støtte + fastledd. Tallene er bygget på samme kilde, så før − støtte = etter, og total brutto − støtte − fastledd = total kostnad etter støtte. Støtten hentes sjeldnere enn månedstallene og kan henge inntil én time etter.
- **Netto med straumstøtte** = Amperiums månedstotal (som allerede er etter støtte) + fastledd.
- **Netto med Norgespris** = Amperiums månedstotal + fastledd + straumstøtten lagt tilbake − Norgespris-kompensasjonen. Straumstøtte gjelder ikke på Norgespris.
- **Norgespris sparer** = Norgespris-kompensasjon − straumstøtten som er trukket fra nettleien (`gridRent`, det som faktisk er trukket på fakturaen). Det finnes bare ett støttetall: «Straumstøtte trukket fra nettleien denne måneden».

Du velger ordningen (Norgespris eller straumstøtte) når du setter opp integrasjonen, og kan endre den under **Konfigurer**. «Netto kostnad denne måneden» bruker valgt ordning. Har du ikke valgt (eldre installasjon), er den utilgjengelig til du velger.

Støtten leses uten hensyn til fortegn (den er alltid et fradrag). Tallene for **forrige måned** hentes fra samme kostnadssvar: nettleie etter støtte er `gridRent.totalAmount`, total er svarets `totalAmount`, og energi er differansen (avledet). Tallene er **omtrentlige**: kompensasjon og energi summeres fra hele timer, mens månedstallene kan ligge noen timer foran eller bak. Bruk dem som peiling, ikke som faktura. Eksempelkortet [`examples/lovelace-kostnad.yaml`](examples/lovelace-kostnad.yaml) viser oppsettet.

### Kapasitetsledd

Slik beregnes det hos Finnås Kraftlag (tariffark gjeldende fra 1.1.2026, privatkunder): **trinnet bestemmes av snittet av de tre høyeste timeforbrukene i tre ulike døgn** i måneden du faktureres for. Hvis snittet blir 6,5 kW, havner du i trinn 5–10 kW og betaler 400 kr for måneden. Beløpene er **inkludert mva**.

| Trinn | kr/mnd |
|---|---|
| 0–2 kW | 210 |
| 2–5 kW | 300 |
| 5–10 kW | 400 |
| 10–15 kW | 525 |
| 15–20 kW | 700 |
| 20–25 kW | 875 |
| 25–50 kW | 2000 |
| 50–75 kW | 3000 |
| 75–100 kW | 4000 |
| over 100 kW | 5000 |

Tabellen er den samme som Amperium selv leverer, og integrasjonen leser trinnene derfra. Du får:

- **Kapasitetsgrunnlag denne måneden** (kW), **kapasitetsleddet** (kr) og **kW til neste trinn**, alle fra Amperium. Samme tall for forrige måned. Hele trinntabellen ligger som attributt.
- **Kapasitetsgrunnlag (beregnet, tre høyeste døgn):** Integrasjonen finner høyeste time hvert døgn (lokal tid) i denne måneden, tar de tre høyeste døgntoppene og regner snittet. Attributtet `peaks` viser de tre timene (dato, time og kW), og `difference_kw` viser avviket fra Amperiums eget tall. Amperiums tall er fasit. Den beregnede verdien brukes til å se hvilke timer som er toppene.
- **Terskel for ny kapasitetstopp:** Den tredje høyeste døgntoppen. Et nytt døgn må ha en time over dette for å heve grunnlaget.

Timedata fra Amperium kommer med litt forsinkelse, så den pågående timen er ikke med. Har du valgt en effektsensor (se over), viser «Timeeffekt denne timen (prognose)» attributtene `capacity_threshold_kw` og `above_threshold`. Da ser du om timen er på vei over terskelen.

**Kapasitetsgrunnlag: riktig fra første dag.** Integrasjonen henter kraftlagets egne timedata for hele måneden. Kapasitetsgrunnlaget (snittet av høyeste time i hvert av de tre høyeste døgnene) blir derfor riktig selv om du installerer integrasjonen midt i måneden. Lokale kalkulatorer som måler effekt selv, for eksempel fra en HAN-leser, kjenner bare timene etter at de ble satt opp, og kan vise for lavt grunnlag den første måneden. Eksempel fra en installasjon 2. oktober 2026 kl. 21:36: en lokal kalkulator viste 3,29 kW (trinn 2–5 kW), mens riktig grunnlag var 6,38 kW (trinn 5–10 kW). Tallet 3,29 er oppgitt av brukeren og er ikke kontrollert av meg.

Vil du unngå nye topper, bruk «Terskel for ny kapasitetstopp» og attributtet `above_threshold` på «Timeeffekt denne timen (prognose)».

### Når måneden starter

Alle månedstall («denne måneden») regnes fra kl. 00:00 **lokal tid** den 1. i måneden (norsk tid, med sommertid), og stemmer da med timedata og dag/natt-fordelingen. Fra og med 0.10.0. Før det startet hovedhentingen kl. 00:00 UTC, det vil si 01:00 eller 02:00 lokal tid.

### Dag og natt

Dag/natt-forbruket for denne måneden hentes direkte fra Amperium (`gridRent.importedEnergyDay/Night`), slik nettleien faktisk deles. Hvis Amperium ikke leverer dem, summeres det fra timedata i **lokal tid** med dag kl. 06–22 og natt resten. Timene kan endres under **Innstillinger → Enheter og tjenester → Amperium → Konfigurer** og gjelder bare i det tilfellet.

### Timepriser

Sensoren **Spotpris nå** har attributtene `official` (om prisen er offisiell eller foreløpig), `prices_today` og `prices_tomorrow`: lister med én rad per time (`start`, `end`, `spot`, `surcharge`, `vat_percent`, `official`). Prisene for i morgen kommer rundt midten av dagen. `spot` er offisiell spotpris når den er fastsatt, ellers foreløpig pris. Hver time har også `consumer`: prisen du betaler per kWh, (spot + påslag) inkl. mva. Listene kan brukes i for eksempel ApexCharts eller automasjoner.

## Installasjon (HACS)

1. HACS → ⋮ → **Egendefinerte arkiv** (Custom repositories).
2. Lim inn URL-en til dette repoet, kategori **Integration**.
3. Søk opp **Amperium** i HACS og installer.
4. Start Home Assistant på nytt.

Eller manuelt: kopier `custom_components/amperium/` til `config/custom_components/` og start på nytt.

## Oppsett

1. **Innstillinger → Enheter og tjenester → Legg til integrasjon → Amperium**.
2. Skriv inn **telefonnummeret** du bruker hos kraftlaget (samme som i Kraftlaget-appen).
3. Du får en **engangskode på SMS** – skriv den inn.
4. Har du flere anlegg, velger du hvilket du vil følge.
5. Velg ordning: **Norgespris** eller **straumstøtte**.
6. Velg om du har en **Dobbe-modul** (HAN-sensoren som sender målingene til Amperium). Svar nei hvis du er usikker. Du kan endre valget senere under **Konfigurer**. Ferdig.

Integrasjonen logger inn passordløst med engangskode én gang, lagrer et refresh-token og fornyer tilgangen automatisk i bakgrunnen. Du trenger normalt aldri logge inn på nytt.

## Innlogging og oppdateringer

Du logger inn med engangskode én gang. Integrasjonen lagrer tokens i oppsettet, og de ligger igjen når du oppdaterer integrasjonen i HACS og starter Home Assistant på nytt, så en oppdatering logger deg ikke ut.

Tokenene (målt fra svar fra Amperium, ikke dokumentert av dem): tilgangstokenet varer ca. **5 dager**, fornyelsestokenet ca. **1 år**. Fornyelsen godtar bare et tilgangstoken som har utløpt, så integrasjonen fornyer først når Amperium svarer 401.

- **Token fornyes automatisk** når det utløper. Treffer flere forespørsler 401 samtidig, sendes bare én fornyelse, og de andre bruker det nye tokenet. Nye tokens lagres med en gang.
- **Feil hos Amperium logger deg ikke ut.** Bare når Amperium selv avviser tokenet (HTTP 400/401/403) ber integrasjonen deg logge inn på nytt. Tjenestefeil (HTTP 5xx, 429, nettverk) gir bare en midlertidig feil.
- **Du ser når innloggingen utløper.** Diagnostikksensoren «Innlogging gyldig til» viser tidspunktet Amperium har oppgitt for fornyelsestokenet. Installasjoner fra før 0.9.1 mangler tidspunktet til tokenet er fornyet første gang (opptil ca. fem dager) eller du har logget inn på nytt.
- **Varsel i god tid.** Er det under 30 dager igjen, kommer et varsel under Reparasjoner, og «Konfigurer på nytt» åpnes. Du får en ny engangskode på SMS til samme nummer. Husk døgngrensen for engangskoder.
- **Må du logge inn på nytt av andre grunner** (for eksempel etter lang tid uten kontakt), viser Home Assistant «Konfigurer på nytt» på integrasjonen.
- **Loggen** (nivå info) viser hver fornyelse med utløpstidene, uten tokenverdier: «Amperium token refreshed; refresh token expires … (was …)». Der ser du om fristen på ca. ett år løper videre ved hver fornyelse eller ligger fast. Det er ikke avklart ennå.
- Kjører du et eget skript mot Amperium ved siden av, la det logge inn for seg selv med egen engangskode i stedet for å dele tokenfilen. Det er ikke bekreftet om Amperium gjør et gammelt fornyelsestoken ugyldig når et nytt utstedes.

## Hvordan det virker

Amperium bruker passordløs OTP-innlogging i tillegg til en statisk app-nøkkel (`api-key`). Integrasjonen:

1. Ber om engangskode: `POST /api/accounts/login/request-otp`
2. Logger inn: `POST /api/accounts/login/otp` → access- og refresh-token
3. Fornyer ved behov: `POST /api/accounts/login/refresh-token` (kun når access-token er utløpt)
4. Henter data: `GET /api/sites?charges_from=…&charges_to=…`
5. Henter timepriser: `GET /api/sites/{id}/prices?from=…&to=…` (i dag og i morgen)
6. Henter timeforbruk: `GET /api/sites/{id}/consumption/energy?from=…&to=…&resolution=H`
7. Henter kostnad: `GET /api/sites/{id}/consumption/charges?from=…&to=…&resolution=H`

`resolution` må være én bokstav (`H`, `D` eller `M`). Ord og tall avvises av API-et. Timedata hentes høyst en gang i timen.

Polling hvert 15. minutt (HAN-måleren oppdateres time for time).

## Ansvarsfraskrivelse

Ikonet i `custom_components/amperium/brand/` er ikonet til appen Kraftlaget fra Finnås Kraftlag. Det vises i Home Assistant 2026.3 og nyere, og brukes bare for å vise hvilken tjeneste integrasjonen kobler til. Det betyr ikke at Finnås Kraftlag står bak integrasjonen.


Dette er et uoffisielt, community-laget prosjekt uten tilknytning til Amperium eller noe kraftlag. Det bruker samme offentlige API som Amperium-appen, med din egen innlogging mot din egen konto. Bruk på eget ansvar.

## Versjoner

Alle endringer per versjon, fra 0.1.0 til nå, står i [CHANGELOG.md](CHANGELOG.md). Det samme står i utgivelsesnotatet for hver versjon under [Releases](https://github.com/zanzei26/Amperium-Hacs-Finnaas-kraftlag/releases).

## Lisens

MIT – se [LICENSE](LICENSE).

## Utvikling

De rene beregningene (`derived.py`, `hourpower.py`, deler av `api.py`) har tester som ikke trenger Home Assistant:

```
cd tests && python -m pytest
```
