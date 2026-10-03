# Amperium for Home Assistant

[![Åpne i Home Assistant og legg til i HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=zanzei26&repository=Amperium-Hacs&category=integration)

Henter strømforbruk, kostnad og pris **direkte fra kraftlaget ditt** via Amperium-plattformen (Finnås Kraftlag m.fl.) – de samme tallene som står på fakturaen og i Amperium-appen, rett inn i Home Assistant.

> _Unofficial Home Assistant integration for the Amperium cloud platform used by several Norwegian power companies. Passwordless OTP login, HAN meter data as native sensors._

## Hva du får

Sensorer per anlegg:

| Sensor | Beskrivelse |
|---|---|
| `sensor.*_forbruk_denne_maneden` | Forbruk hittil i måneden (kWh) |
| `sensor.*_forbruk_i_dag` | Forbruk i dag (kWh) |
| `sensor.*_effekt_na` | Effekt nå (kW) |
| `sensor.*_kostnad_denne_maneden` | Total kostnad hittil i måneden (kr) |
| `sensor.*_energikostnad_denne_maneden` | Energidelen av kostnaden (kr) |
| `sensor.*_nettleie_denne_maneden` | Nettleie hittil i måneden (kr) |
| `sensor.*_spotpris_na` | Offisiell spotpris nå (kr/kWh) |
| `sensor.*_laveste_spotpris_i_dag` | Laveste timepris i dag (kr/kWh), med timen som attributt |
| `sensor.*_hoyeste_spotpris_i_dag` | Høyeste timepris i dag (kr/kWh), med timen som attributt |
| `sensor.*_spotpris_snitt_i_dag` | Gjennomsnittlig timepris i dag (kr/kWh) |
| `binary_sensor.*_han_maler_online` | Om HAN-måleren er online |

Sensorene nullstilles daglig/månedlig, så de passer best som egne dashbordkort (se [`examples/lovelace-amperium.yaml`](examples/lovelace-amperium.yaml)). Energidashbordet i Home Assistant vil helst ha en kumulativ livstidsmåler, så forbruket til Energidashbordet bør fortsatt hentes fra HAN-måleren/Tibber, ikke fra disse månedssensorene.

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
2. Skriv inn **telefonnummeret** du bruker hos kraftlaget (samme som i Amperium-appen).
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

Polling hvert 15. minutt (HAN-måleren oppdateres time for time).

## Ansvarsfraskrivelse

Dette er et uoffisielt, community-laget prosjekt uten tilknytning til Amperium eller noe kraftlag. Det bruker samme offentlige API som Amperium-appen, med din egen innlogging mot din egen konto. Bruk på eget ansvar.

## Lisens

MIT – se [LICENSE](LICENSE).
