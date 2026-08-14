# SETUP — nalozi i ključevi

Ovo uputstvo prolazi kroz sve što moraš sam da napraviš pre nego što alat
proradi. Pisano je za nekoga ko prvi put otvara Google Cloud Console.

Ništa od ovoga ne lepiš u chat. Ključevi idu isključivo u fajl `.env` koji
nikad ne odlazi na GitHub.

Redosled: **1) Pexels → 2) Google Cloud → 3) GitHub**. Pexels je najlakši i
gotov je za dva minuta, pa da odmah imaš osećaj kako izgleda kad je gotovo.

---

## Rečnik pojmova koji se ponavljaju

- **API** — vrata kroz koja jedan program pita drugi program za podatke. Naša
  skripta kroz Google-ov API pita "daj mi picerije u Novom Sadu".
- **API ključ (key)** — dugačak niz slova i brojeva koji dokazuje da si to ti.
  Ponaša se kao lozinka: ko ga ima, troši u tvoje ime.
- **`.env` fajl** — običan tekstualni fajl u kome stoje ključevi. Program ga
  čita, a `.gitignore` sprečava da ode na internet.
- **Kvota (quota)** — gornja granica koliko puta dnevno smeš da pozoveš API.
  Kad se dostigne, Google odbija dalje pozive umesto da ti naplati.
- **Billing account** — nalog za naplatu, tj. tvoja kartica zakačena za Google.
- **Repo (repository)** — folder projekta na GitHub-u, sa istorijom izmena.

---

## 1. Pexels — slike za sajtove

### Čemu služi

Pexels je sajt sa besplatnim fotografijama. Njegova licenca dozvoljava
komercijalnu upotrebu bez obaveznog potpisivanja autora, što znači da te slike
smeju da idu direktno na sajt koji praviš klijentu.

**Šta bi bilo bez njega:** demo sajtovi bi ostali bez slika ili bi ti ručno
tražio i skidao slike za svaki lokal. Google-ove fotografije lokala se NE smeju
staviti na sajt — one su vlasništvo mušterija i vlasnika, koristimo ih samo kao
stilsku referencu da znamo kako lokal izgleda.

### Da li je besplatan

Da, potpuno. Ne traži karticu. Ograničenja su 200 poziva na sat i 20.000 poziva
mesečno, što je ogromno za našu upotrebu — jedan lokal potroši 5 do 8 poziva.
Nema šanse da budeš naplaćen jer ne postoji plaćena verzija koju bi mogao
slučajno da uključiš.

### Korak po korak

1. Otvori **https://www.pexels.com/join/**
2. Registruj se (mejlom ili preko Google dugmeta — svejedno je).
3. Otvori **https://www.pexels.com/api/**
4. Klikni dugme **"Get Started"**.
5. Pojaviće se kratak formular. Popuni ovako:
   - **What are you building?** (ili slično pitanje o tipu projekta) — izaberi
     opciju u smislu *Personal project* / *Website*.
   - **Description / What will you use the API for?** — upiši nešto poput:
     `Personal tool that finds stock photos for small business website mockups.`
     Ne moraš da se trudiš, ovo niko ne odbija.
   - **URL** — ako traži adresu sajta, upiši adresu svog GitHub profila ili
     bilo koji svoj sajt.
6. Klikni **"Generate API Key"** / **"Request API Key"**.
7. Ključ se odmah pojavi na ekranu — dugačak niz slova i brojeva. Ostaje uvek
   dostupan na **https://www.pexels.com/api/key/**, ne moraš da ga pamtiš.

### Gde da ga zalepiš

U fajl `.env` u folderu projekta, u red:

```
PEXELS_API_KEY=ovde_ide_tvoj_kljuc
```

Bez navodnika, bez razmaka oko znaka `=`.

---

## 2. Google Cloud — Places API (New)

Ovo je najduži deo i jedini gde postoji rizik od troška. Pročitaj do kraja pre
nego što kreneš da klikćeš.

### Čemu služi

Google Places API je izvor podataka o firmama: ime, adresa, ocena, broj
recenzija, telefon i — najvažnije za nas — **da li firma ima sajt**. Cela Faza 1
se oslanja na to.

**Šta bi bilo bez njega:** alat i dalje radi, ali preko rezervnog izvora
OpenStreetMap (besplatan, bez ključa). Problem je što OpenStreetMap nema ocene
ni broj recenzija, a to su nam dva od pet kriterijuma za rangiranje. Bez njih ne
možeš da razlikuješ picerija sa 300 recenzija i ocenom 4.7 (idealan klijent) od
picerije sa 4 recenzije (verovatno mrtva). Zato je Google jako poželjan.

### Da li je besplatan

**Delimično, i tu treba biti pažljiv.**

Google zahteva da zakačiš karticu (billing account) pre nego što uopšte dozvoli
korišćenje Maps Platform API-ja. Nema načina da se to zaobiđe. Ali:

- Postoji besplatna mesečna količina poziva koja se resetuje svakog prvog u
  mesecu.
- Google naplaćuje po **najskupljem polju koje zatražiš** u jednom pozivu. Naša
  skripta traži telefon, ocenu i broj recenzija, a to su "skupa" polja, pa naš
  poziv pada u najskuplju kategoriju Text Search-a. Ta kategorija ima najmanju
  besplatnu količinu — **oko 1.000 poziva mesečno**.
- Zato je limit u našoj skripti postavljen na **900 poziva mesečno**, namerno
  ispod besplatne granice. Kad se dostigne 900, skripta se sama zaustavi.

Koliko je to u praksi: jedan poziv vraća do 20 firmi. Pretraga sa `--limit 100`
potroši 5 poziva. 900 poziva mesečno je otprilike 180 takvih pretraga — daleko
više nego što ćeš stvarno raditi.

> Iznose i besplatne granice Google povremeno menja. Aktuelne brojeve uvek
> proveri na **https://mapsplatform.google.com/pricing/** pre nego što se
> osloniš na njih.

### Kako da budeš siguran da nećeš biti naplaćen

Tri odvojene brane, i svaku od njih ćeš postaviti:

1. **Kvota u Google Cloud Console** (koraci 7 i 8 ispod) — Google fizički odbija
   pozive preko granice. Ovo je jedina zaštita koja stvarno zaustavlja trošak.
2. **Brojač u skripti** — skripta broji sopstvene pozive u `data/usage.json` i
   staje na 900 u tekućem mesecu.
3. **Budžetski alarm** (korak 9) — mejl kad potrošnja pređe iznos.
   ⚠️ Alarm **samo šalje mejl, ne zaustavlja ništa.** Nikad se ne oslanjaj samo
   na njega.

### Korak po korak

**Korak 1 — Otvori konzolu**

Idi na **https://console.cloud.google.com/** i uloguj se svojim Google nalogom
(običan Gmail je sasvim dovoljno). Ako je prvi put, prihvati uslove korišćenja
(*Terms of Service*) čekiranjem kvadratića i klikom na **"AGREE AND CONTINUE"**.

**Korak 2 — Napravi projekat**

"Projekat" je samo fioka u kojoj stoje tvoj ključ i tvoje kvote.

1. U gornjoj traci, levo pored search polja, stoji padajući meni sa imenom
   projekta (piše **"Select a project"** ako još nemaš nijedan). Klikni ga.
2. U prozoru koji se otvori, gore desno klikni **"NEW PROJECT"**.
3. **Project name:** upiši `prospect-kit`.
4. **Location / Organization:** ostavi kako jeste (`No organization`).
5. Klikni **"CREATE"**. Sačekaj 10-20 sekundi.
6. Vrati se na isti padajući meni i izaberi `prospect-kit` da bude aktivan
   projekat. **Proveri da u gornjoj traci piše `prospect-kit`** — sve dalje
   mora da se dešava unutar tog projekta.

**Korak 3 — Zakači karticu (billing)**

1. Klikni meni sa tri crte gore levo (☰, zove se *Navigation menu*).
2. Izaberi **"Billing"**.
3. Ako nemaš nijedan nalog za naplatu, piše nešto kao *This project has no
   billing account*. Klikni **"LINK A BILLING ACCOUNT"**, pa **"CREATE BILLING
   ACCOUNT"**.
4. **Country:** Serbia. Prihvati uslove, klikni **"CONTINUE"**.
5. **Account type:** *Individual*.
6. Unesi ime, adresu i podatke kartice. Google napravi probnu rezervaciju od
   oko 1 evra/dolara samo da proveri karticu i ona se poništi za par dana.
   Nije naplata.
7. Klikni **"START MY FREE TRIAL"** ili **"SUBMIT AND ENABLE BILLING"**.

Ako ti Google ponudi *free trial* sa kreditom — slobodno uzmi, ne škodi.
Bitno je da Google **ne prebacuje automatski na plaćeni nalog** kad kredit
istekne; tada te pita eksplicitno.

**Korak 4 — Uključi Places API (New)**

⚠️ Postoje dva slična imena. Treba nam ono sa **"(New)"**.

1. ☰ **Navigation menu** → **"APIs & Services"** → **"Library"**.
2. U search polje ukucaj `Places API`.
3. Iz rezultata izaberi karticu na kojoj piše tačno **"Places API (New)"**.
   Nemoj kliknuti na staru **"Places API"** bez zagrade.
4. Klikni plavo dugme **"ENABLE"**.
5. Sačekaj da se stranica prebaci na ekran sa statistikom tog API-ja.

**Korak 5 — Napravi API ključ**

1. ☰ **Navigation menu** → **"APIs & Services"** → **"Credentials"**.
2. Gore klikni **"+ CREATE CREDENTIALS"** → iz menija izaberi **"API key"**.
3. Iskoči prozor sa ključem. Klikni ikonicu za kopiranje i **odmah ga zalepi u
   `.env`** (vidi dole "Gde da ga zalepiš") — posle je vidljiv i u listi, ali
   nema razloga da rizikuješ.
4. U istom prozoru klikni **"Edit API key"** (ako si zatvorio prozor: u listi
   *API Keys* klikni ikonicu olovke pored ključa).

**Korak 6 — Ograniči ključ (važno za sigurnost)**

Na stranici za izmenu ključa:

1. **Name:** upiši `prospect-kit-key` da znaš čemu služi.
2. **Application restrictions:** ostavi **"None"**. (Opcija *IP addresses*
   izgleda sigurnije, ali kućna IP adresa se menja i skripta bi ti pucala
   svaki drugi dan.)
3. **API restrictions:** izaberi **"Restrict key"**, pa u padajućem spisku
   čekiraj **samo "Places API (New)"**.
   Ovo znači: i da ključ nekome procuri, ne može njime da koristi nijedan drugi
   Google servis.
4. Klikni **"SAVE"**.

**Korak 7 — POSTAVI KVOTU. Ovo je najvažniji korak u celom uputstvu.**

Sve ostalo je udobnost. Ovo je jedino što stoji između tebe i računa ako nešto
u kodu krene u petlju i pozove API 50.000 puta. Nemoj ga preskočiti i nemoj ga
ostaviti "za kasnije".

1. ☰ **Navigation menu** → skroluj do **"Google Maps Platform"** → klikni
   **"Quotas"**.
   (Ako ne nalaziš stavku u meniju, otvori direktno:
   **https://console.cloud.google.com/google/maps-apis/quotas**)
2. Gore stoji padajući meni **"API"** — izaberi **"Places API (New)"**.
3. Otvori karticu **"Quotas"** i u listi nađi red koji u imenu ima **"per day"**
   — na primer *Text Search (New) requests per day* ili *Requests per day*.
   Ako ima više takvih, zanima te onaj koji pominje **Text Search**.
4. Čekiraj kvadratić u tom redu i klikni ikonicu **olovke** (Edit).
5. Upiši **`50`** i klikni **"SAVE"** / **"SUBMIT"**.
   50 poziva dnevno je i dalje 10 pretraga sa `--limit 100` na dan, a
   matematički ne može da probije mesečnih 900 u kratkom roku.

**Korak 8 — Ako se kvota ne da menjati na tom mestu**

Kod nekih naloga Maps Platform ekran ne dozvoljava izmenu. Onda idi drugim putem:

1. ☰ **"APIs & Services"** → **"Enabled APIs & services"** → klikni
   **"Places API (New)"**.
2. Kartica **"Quotas & System Limits"**.
3. U polje za filtriranje ukucaj `per day`.
4. Nađi red sa dnevnim limitom, čekiraj ga, klikni olovku, upiši `50`, **SAVE**.

Ako ni tu ne postoji dnevni limit koji se može menjati (Google to povremeno
menja), javi mi i pojačaćemo zaštitu u samoj skripti — ali onda **obavezno**
uradi i korak 9.

**Korak 9 — Budžetski alarm**

1. ☰ **"Billing"** → u levom meniju **"Budgets & alerts"**.
2. Klikni **"CREATE BUDGET"**.
3. **Name:** `prospect-kit-alarm`.
4. **Projects:** izaberi samo `prospect-kit`.
5. **Budget type:** *Specified amount*. **Target amount:** upiši `1`.
6. **Set alert threshold rules:** ostavi 50%, 90%, 100%.
7. Čekiraj da se šalje mejl na tvoj nalog. **"FINISH"**.

Sad ti Google javi mejlom čim potrošnja pređe pola evra. Ponavljam: ovo
**ne zaustavlja** trošak, samo te obaveštava.

### Gde da ga zalepiš

U `.env`, u red:

```
GOOGLE_MAPS_API_KEY=ovde_ide_tvoj_kljuc
```

### Kako da napraviš `.env` fajl

U folderu `lead-finder-site-builder` već postoji `.env.example` — to je prazan
šablon. Otvori PowerShell u tom folderu i pokreni:

```powershell
Copy-Item .env.example .env
notepad .env
```

Zalepi ključeve iza znakova `=`, sačuvaj (Ctrl+S) i zatvori Notepad.

Gotov `.env` izgleda ovako:

```
GOOGLE_MAPS_API_KEY=AIzaSyC3xK9...
PEXELS_API_KEY=563492ad6f91...
```

`.env` je već u `.gitignore`, tako da nikad neće otići na GitHub.

---

## 3. GitHub

### Čemu služi

Dve stvari odjednom: rezervna kopija koda (ako se laptop pokvari, projekat je
i dalje tu) i javna vitrina — otvoren repo koji možeš da staviš u biografiju
i pošalješ klijentima kao dokaz da znaš da radiš.

**Šta bi bilo bez njega:** kod postoji samo na tvom Desktopu i istorija izmena
je lokalna. Ako nešto pokvarimo, i dalje bismo mogli da se vratimo unazad, ali
kvar diska bi značio gubitak svega.

### Da li je besplatan

Da. Javni repozitorijumi su neograničeni i besplatni zauvek. `gh` alat je
besplatan i open-source. Nema mesta gde se unosi kartica.

### Korak po korak

**Korak 1 — Nalog**

Ako nemaš nalog: **https://github.com/signup**, unesi mejl, lozinku i korisničko
ime, potvrdi mejl. Korisničko ime biraj pažljivo — biće u adresi svakog tvog
projekta i klijenti ga vide.

**Korak 2 — Instaliraj `gh` (GitHub CLI)**

`gh` je Github-ov program za terminal. Trebaće nam da se ulogujemo i da
podesimo repo bez ručnog kopiranja tokena.

Otvori **PowerShell** i pokreni:

```powershell
winget install --id GitHub.cli
```

Kad se završi, **zatvori PowerShell i otvori novi prozor** (bez toga sistem još
ne zna za novu komandu). Proveri:

```powershell
gh --version
```

Ako ispiše broj verzije, gotovo je. Ako piše da komanda nije pronađena, restartuj
računar i probaj opet.

**Korak 3 — Uloguj se**

```powershell
gh auth login
```

Program postavlja pitanja u terminalu, biraš strelicama gore/dole i potvrđuješ
Enterom:

1. *What account do you want to log into?* → **GitHub.com**
2. *What is your preferred protocol for Git operations?* → **HTTPS**
3. *Authenticate Git with your GitHub credentials?* → **Yes**
4. *How would you like to authenticate?* → **Login with a web browser**
5. Ispisaće ti kod u formatu `XXXX-XXXX`. **Zapamti ga**, pritisni Enter —
   otvara se browser. Zalepi kod, klikni **"Continue"**, pa **"Authorize
   github"**.
6. Vrati se u terminal, treba da piše `✓ Logged in as tvojekorisnickoime`.

Ja tvoj token nikad ne vidim ni ne kucam — `gh` ga čuva sam u Windows
Credential Manager-u.

**Korak 4 — Napravi PRAZAN repo kroz sajt**

⚠️ Ovaj korak ima jednu zamku, pročitaj objašnjenje.

1. Otvori **https://github.com/new**
2. **Repository name:** `lead-finder-site-builder`
3. **Description:** zalepi ovo:
   ```
   Automatically find local businesses without a website, then generate a ready-to-deploy site and outreach message for each one.
   ```
4. Izaberi **Public**.
5. **NE ČEKIRAJ NIJEDNU OD OVE TRI STVARI:**
   - ☐ *Add a README file*
   - ☐ *Add .gitignore*
   - ☐ *Choose a license*
6. Klikni **"Create repository"**.
7. Kopiraj adresu koja se pojavi (izgleda kao
   `https://github.com/tvojeime/lead-finder-site-builder.git`) i pošalji mi je
   u chat.

**Zašto se ništa ne čekira:** svaka od te tri opcije napravi prvi commit na
GitHub-u. Na tvom kompjuteru već postoji prvi commit sa istim fajlovima. To bi
bile dve nezavisne istorije istog projekta i Git bi odbio da ih spoji — dobio
bi grešku `refused to merge unrelated histories` i morali bismo da je rešavamo
ručno. README, licencu i `.gitignore` pravimo lokalno i oni odu na GitHub sa
prvim `push`-om.

### Gde da zalepiš

Ništa. Adresu repoa mi samo pošalji u chat, a `gh` sam čuva pristup.

---

## Kontrolna lista

Pre nego što nastavimo, treba da imaš:

- [ ] `.env` fajl u folderu `lead-finder-site-builder`
- [ ] `PEXELS_API_KEY` popunjen
- [ ] `GOOGLE_MAPS_API_KEY` popunjen
- [ ] Places API **(New)** uključen u projektu `prospect-kit`
- [ ] Ključ ograničen samo na Places API (New)
- [ ] **Dnevna kvota postavljena na 50**
- [ ] Budžetski alarm na 1 evro
- [ ] `gh --version` ispisuje verziju
- [ ] `gh auth login` prošao
- [ ] Prazan javni repo napravljen, bez README/licence/.gitignore

Google ključ nije obavezan da bismo krenuli — bez njega skripta radi preko
OpenStreetMap-a. Ali za pravu upotrebu ga hoćeš.

---

## Ako nešto zapne

| Problem | Šta znači | Rešenje |
|---|---|---|
| `REQUEST_DENIED` ili `403` | ključ nije aktivan ili API nije uključen | proveri Korak 4 i Korak 6 |
| `This API project is not authorized to use this API` | uključio si staru "Places API" umesto "(New)" | vrati se na Korak 4 |
| `You must enable Billing` | kartica nije zakačena | Korak 3 |
| `gh: command not found` | terminal još ne zna za `gh` | zatvori i otvori nov PowerShell |
| `RESOURCE_EXHAUSTED` / `429` | probio si dnevnu kvotu | to je zaštita, radi kako treba — sačekaj sutra |
