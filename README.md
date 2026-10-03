# Amperium for Home Assistant

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
| `binary_sensor.*_han_maler_online` | Om HAN-måleren er online |

Sensorene nullstilles daglig/månedlig, så de passer best som egne dashbordkort (se [`examples/lovelace-amperium.yaml`](examples/lovelace-amperium.yaml)). Energidashbordet i Home Assistant vil helst ha en kumulativ livstidsmåler, så forbruket til Energidashbordet bør fortsatt hentes fra HAN-måleren/Tibber, ikke fra disse månedssensorene.

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

Polling hvert 15. minutt (HAN-måleren oppdateres time for time).

## Ansvarsfraskrivelse

Dette er et uoffisielt, community-laget prosjekt uten tilknytning til Amperium eller noe kraftlag. Det bruker samme offentlige API som Amperium-appen, med din egen innlogging mot din egen konto. Bruk på eget ansvar.

## Lisens

MIT – se [LICENSE](LICENSE).
