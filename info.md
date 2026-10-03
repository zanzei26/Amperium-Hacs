# Amperium

Strømforbruk, kostnad og pris **direkte fra kraftlaget ditt** via Amperium-plattformen (Finnås Kraftlag m.fl.) – de samme tallene som på fakturaen og i Amperium-appen.

## Sensorer
- Forbruk denne måneden / i dag (kWh)
- Effekt nå (kW)
- Total kostnad, energikostnad og nettleie hittil i måneden (kr)
- Offisiell spotpris nå (kr/kWh)
- HAN-måler online (binær)

## Oppsett
1. Installer via HACS og start Home Assistant på nytt.
2. **Innstillinger → Enheter og tjenester → Legg til integrasjon → Amperium**.
3. Skriv inn telefonnummeret du bruker hos kraftlaget → du får en engangskode på SMS → skriv den inn.
4. Har du flere anlegg, velger du hvilket du vil følge.

Passordløs innlogging med engangskode én gang; token fornyes automatisk i bakgrunnen.

Se [README](https://github.com/zanzei26/Amperium-Hacs) for detaljer.
