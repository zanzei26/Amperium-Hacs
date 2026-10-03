# Finnås Kraftlag (Amperium)

Strømforbruk, kostnad og pris **direkte fra Finnås Kraftlag** via Amperium-plattformen – de samme tallene som vises i appen **Kraftlaget** fra Finnås Kraftlag.

**Bekreftet for:** Finnås Kraftlag (Bømlo). Andre kraftlag er ikke bekreftet – prøver du et annet, meld fra under Issues på GitHub.

## Sensorer
- Forbruk denne måneden / i dag (kWh)
- Effekt nå (kW)
- Total kostnad, energikostnad og nettleie hittil i måneden (kr)
- Offisiell spotpris nå (kr/kWh)
- Laveste, høyeste og gjennomsnittlig timepris i dag (kr/kWh)
- Timepriser for i dag og i morgen som attributter på spotpris-sensoren
- Forbruk i går, siste time og forrige måned, dag/natt-fordeling, energikostnad i går
- Straumstøtte og Norgespris-sammenligning
- Nettleie med kapasitetsledd, fastledd og total brutto/netto for din ordning (Norgespris eller straumstøtte)
- Valgfri live effekt fra en sensor du har fra før (f.eks. Tibber Pulse)
- Timeforbruk importert som statistikk til Energidashbordet (velg «Amperium forbruk»)
- HAN-måler online (binær)
- Når innloggingen utløper (diagnostikk), med varsel i god tid

## Oppsett
1. Installer via HACS og start Home Assistant på nytt.
2. **Innstillinger → Enheter og tjenester → Legg til integrasjon → Amperium**.
3. Skriv inn telefonnummeret du bruker hos kraftlaget → du får en engangskode på SMS → skriv den inn.
4. Har du flere anlegg, velger du hvilket du vil følge.

Passordløs innlogging med engangskode én gang; token fornyes automatisk i bakgrunnen. En oppdatering i HACS logger deg ikke ut. Du får varsel når det er under 30 dager til innloggingen utløper.

Alle endringer per versjon: [CHANGELOG](https://github.com/zanzei26/Amperium-Hacs-Finnaas-kraftlag/blob/main/CHANGELOG.md).

Se [README](https://github.com/zanzei26/Amperium-Hacs-Finnaas-kraftlag) for detaljer.
