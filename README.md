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
| `sensor.*_effekt_na` | Effekt nå (kW) |
| «Energikostnad brutto denne måneden» | Energi hittil i måneden, brutto inkl. mva, før støtte (kr), fra månedstallene |
| «Nettleie etter straumstøtte denne måneden» | Nettleie inkl. kapasitetsledd, **etter** straumstøtte og **uten** fastledd (kr) |
| «Total kostnad etter straumstøtte denne måneden» | Energi + nettleie som over, **uten** fastledd (kr). Dette er Amperiums eget månedstall |
| «… forrige måned» (energi, nettleie, total) | De samme tre tallene for forrige måned (kr) |
| «Nettleie før straumstøtte denne måneden» | Nettleie inkl. kapasitetsledd, før støtte, uten fastledd (kr). Postene ligger som attributter |
| «Fastledd denne måneden» | Fast månedlig avgift (kr). Den er ikke med i månedstallene over |
| «Total brutto denne måneden» | Energi + nettleie + fastledd, før støtte (kr) |
| «Kapasitetsgrunnlag denne måneden» (kW) | Effekten kapasitetsleddet beregnes av, med trinnet og trinntabellen som attributter |
| «Kapasitetsleddet denne måneden» (kr) og «Til neste kapasitetstrinn» (kW) | Beløpet for trinnet du er i, og hvor mange kW det er til neste trinn. Samme for forrige måned |
| `sensor.*_spotpris_na` | Offisiell spotpris nå (kr/kWh) |
| `sensor.*_laveste_spotpris_i_dag` | Laveste timepris i dag (kr/kWh), med timen som attributt |
| `sensor.*_hoyeste_spotpris_i_dag` | Høyeste timepris i dag (kr/kWh), med timen som attributt |
| `sensor.*_spotpris_snitt_i_dag` | Gjennomsnittlig timepris i dag (kr/kWh) |
| `sensor.*_forbruk_i_gar` | Forbruk i går (kWh), summert fra timedata i lokal tid |
| `sensor.*_forbruk_siste_time` | Forbruk siste hele time (kWh) |
| `sensor.*_forbruk_forrige_maned` | Forbruk forrige måned (kWh) |
| `sensor.*_forbruk_dag_denne_maneden` / `..._natt_...` | Forbruk dag og natt hittil i måneden (kWh), se «Dag og natt» |
| `sensor.*_energikostnad_brutto_i_gar` | Brutto energikostnad i går (kr): (spot + påslag) × kWh inkl. mva, før støtte |
| `sensor.*_energikostnad_brutto_denne_maneden` | Brutto energikostnad hittil i måneden (kr), summert fra timedata |
| `sensor.*_mva_pa_energi_denne_maneden` | Mva-delen av energikostnaden hittil i måneden (kr) |
| «Straumstøtte denne måneden» | Straumstøtte summert fra timedata (kr) |
| «Straumstøtte trukket fra nettleien denne måneden» | Straumstøtten slik den er trukket fra nettleien (kr) |
| «Norgespris-kompensasjon denne måneden» | Norgespris-kompensasjon summert fra timedata (kr) |
| «Kompensasjon denne måneden (din ordning)» | Beløpet for ordningen du har valgt (kr) |
| «Netto kostnad denne måneden (din ordning)» | Total kostnad inkl. fastledd, for ordningen du har valgt (kr). Se «Kostnad: brutto, støtte og netto» |
| «Netto kostnad med Norgespris» / «… med straumstøtte» | Netto for hver ordning, avslått som standard |
| «Norgespris sparer denne måneden» | Hvor mye mer Norgespris gir enn straumstøtte hittil i måneden (kr) |
| `sensor.*_norgespris_minus_straumstotte_forrige_maned` | Hvor mye mer Norgespris ga enn straumstøtte forrige hele måned (kr) |
| `sensor.*_eksport_*` | Eksport (solceller), avslått som standard. Slå på hvis du produserer strøm |
| `sensor.*_han_signal` | HAN-signalstyrke (diagnostikk) |
| `sensor.*_han_signalkvalitet` | HAN-signal som tekst: Ingen signal, Dårlig, Middels, Bra, Veldig bra, Ingen data eller Ikke på nett (diagnostikk) |
| `binary_sensor.*_han_maler_online` | Om HAN-måleren er online (diagnostikk) |

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

Amperium oppdaterer effekt bare én gang i timen. Under **Konfigurer** kan du velge en eksisterende effektsensor i Home Assistant, for eksempel **Tibber Pulse/Watty**. Da får du to ekstra sensorer:

- **Effekt nå (live)**: speiler sensoren din, omregnet til kW (W, kW og MW støttes).
- **Timeeffekt denne timen (prognose)**: kapasitetsleddet bygger på snittet av hver hele time, ikke på øyeblikkseffekt. Sensoren regner ut timesnittet så langt (tidsvektet) og anslår hvor timen ender hvis effekten holder seg. Attributtene viser snittet så langt og hvor stor del av timen som hadde målinger (`coverage`).

Velg en sensor som måler **hele huset**. En lader som Easee viser bare laderens effekt og passer ikke til kapasitetsleddet. Prognosen starter på nytt hvis Home Assistant startes midt i en time. Da regnes den ut fra målingene som finnes, og `coverage` viser det.

### Kostnad: brutto, støtte og netto

Amperiums månedstall er lettere å misforstå enn de ser ut til. Dette er hva tallene faktisk inneholder, utledet fra en ekte konto (oktober). **Det er ikke bekreftet av Amperium.**

- **Nettleie i månedstallene er allerede etter straumstøtte.** Nettleien består av energiledd dag og natt, elavgift, Enova-avgift og **kapasitetsleddet**, minus straumstøtten. Regnestykket går opp på øre: 46,31 + 20,15 + 14,09 + 1,98 + 400 (kapasitetstrinn 5–10 kW) − 154,12 (støtte) = 328,41, mot oppgitt 328,40. Derfor kan nettleien bli negativ i en måned med mye støtte.
- **Fastleddet er ikke med** i nettleien eller i total fra månedstallene. Det kommer i tillegg (egen sensor).
- **Energi** (brutto, spot + påslag inkl. mva) er før støtte.
- Beløpene ser ut til å være **inkludert mva**.

Derfor regnes sensorene slik:

- **Total brutto** = energi + nettleie før støtte + fastledd.
- **Netto med straumstøtte** = Amperiums månedstotal (som allerede er etter støtte) + fastledd.
- **Netto med Norgespris** = Amperiums månedstotal + fastledd + straumstøtten lagt tilbake − Norgespris-kompensasjonen. Straumstøtte gjelder ikke på Norgespris.
- **Norgespris sparer** = Norgespris-kompensasjon − straumstøtte.

Du velger ordningen (Norgespris eller straumstøtte) når du setter opp integrasjonen, og kan endre den under **Konfigurer**. «Netto kostnad denne måneden» bruker valgt ordning. Har du ikke valgt (eldre installasjon), er den utilgjengelig til du velger.

Tallene er **omtrentlige**: kompensasjon og energi summeres fra hele timer, mens månedstallene kan ligge noen timer foran eller bak. Bruk dem som peiling, ikke som faktura. Eksempelkortet [`examples/lovelace-kostnad.yaml`](examples/lovelace-kostnad.yaml) viser oppsettet.

### Kapasitetsledd

Kapasitetsleddet bestemmes av **kapasitetsgrunnlaget**, en effekt i kW som Amperium regner ut fra månedens topper. Grunnlaget avgjør hvilket trinn du havner i. Eksempel fra Finnås: 5–10 kW koster 400 kr/måned, og 10–15 kW koster 525 kr/måned. Integrasjonen viser grunnlaget, trinnets beløp, hvor mange kW det er til neste trinn og hva neste trinn koster ekstra. Hele trinntabellen ligger som attributt.

Hvor mange topper som inngår i grunnlaget, er ikke bekreftet. Det ser ut til å bygge på timetopper og ikke dagssnitt. Trinnbeløpene ser ut til å være inkludert mva. Integrasjonen regner ikke ut grunnlaget selv, men bruker Amperiums eget tall.

Har du valgt en effektsensor (se over), viser «Timeeffekt denne timen (prognose)» hvor timen er på vei, så du kan sammenligne med «Til neste kapasitetstrinn».

### Dag og natt

Dag/natt-forbruket summeres fra timedata i **lokal tid**. Standard er dag kl. 06–22 og natt resten. Du kan endre timene under **Innstillinger → Enheter og tjenester → Amperium → Konfigurer**. Helg og helligdager behandles ikke spesielt. Sjekk hos nettselskapet at nettleien din faktisk deler døgnet slik.

### Timepriser

Sensoren **Spotpris nå** har attributtene `prices_today` og `prices_tomorrow`: lister med én rad per time (`start`, `end`, `spot`, `surcharge`, `vat_percent`, `official`). Prisene for i morgen kommer rundt midten av dagen. `spot` er offisiell spotpris når den er fastsatt, ellers foreløpig pris. Listene kan brukes i for eksempel ApexCharts eller automasjoner.

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
4. Har du flere anlegg, velger du hvilket du vil følge. Ferdig.

Integrasjonen logger inn passordløst med engangskode én gang, lagrer et refresh-token og fornyer tilgangen automatisk i bakgrunnen. Du trenger normalt aldri logge inn på nytt.

## Hvordan det virker

Amperium bruker passordløs OTP-innlogging i tillegg til en statisk app-nøkkel (`api-key`). Integrasjonen:

1. Ber om engangskode: `POST /api/accounts/login/request-otp`
2. Logger inn: `POST /api/accounts/login/otp` → access- og refresh-token
3. Fornyer ved behov: `POST /api/accounts/login/refresh-token` (kun når access-token er utløpt)
4. Henter data: `GET /api/sites?charges_from=…&charges_to=…`
5. Henter timepriser: `GET /api/sites/{id}/prices?from=…&to=…` (i dag og i morgen)
6. Henter timeforbruk: `GET /api/sites/{id}/consumption/energy?from=…&to=…&resolution=H`
7. Henter kostnad: `GET /api/sites/{id}/consumption/charges?from=…&to=…&resolution=H`
8. Henter støttesammenligning: `GET /api/sites/{id}/consumption/norgespris-vs-subsidy?from=…&to=…`

`resolution` må være én bokstav (`H`, `D` eller `M`). Ord og tall avvises av API-et. Timedata hentes høyst en gang i timen.

Polling hvert 15. minutt (HAN-måleren oppdateres time for time).

## Ansvarsfraskrivelse

Dette er et uoffisielt, community-laget prosjekt uten tilknytning til Amperium eller noe kraftlag. Det bruker samme offentlige API som Amperium-appen, med din egen innlogging mot din egen konto. Bruk på eget ansvar.

## Lisens

MIT – se [LICENSE](LICENSE).
