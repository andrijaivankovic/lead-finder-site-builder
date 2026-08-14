# SETUP — accounts and API keys

This guide walks through everything you need before the tool works. It is
written for someone opening the Google Cloud Console for the first time.

Keys go into a `.env` file and nowhere else. That file never reaches GitHub.

Order: **1) Pexels → 2) Google Cloud → 3) GitHub**. Pexels takes two minutes.

---

## Terms used throughout

- **API** — the door one program knocks on to ask another program for data.
  This tool asks Google for "pizzerias in Novi Sad" through an API.
- **API key** — a long string that proves the request is yours. Treat it like a
  password: whoever holds it spends on your account.
- **`.env` file** — a plain text file holding your keys. The program reads it,
  and `.gitignore` keeps it off GitHub.
- **Quota** — a ceiling on how many calls per day you are allowed. Once hit,
  Google rejects further calls instead of billing you.
- **Billing account** — your card, linked to Google.

---

## 1. Pexels — photos for the generated sites

### What it does

Pexels hosts free photographs under a licence that allows commercial use
without mandatory attribution, so those images can go straight onto a client
demo site.

**Without it:** demo sites have no images, or you hunt for them by hand for
every business. Google Place Photos cannot be used on the site — they belong to
the owners and customers who took them, and are only a style reference.

### Cost

Free, no card anywhere. Limits are 200 calls per hour and 20,000 per month;
one business consumes five to eight. No paid tier exists, so accidental
charges are not possible.

### Steps

1. Open **https://www.pexels.com/join/** and register.
2. Open **https://www.pexels.com/api/** and click **"Get Started"**.
3. Fill the short form:
   - **Project Category** → *Personal Use / Just for Fun*
   - **Explain briefly how and where you want to integrate our photos** →
     `Personal tool that finds stock photos for small business website mockups.`
   - **URL** → optional, leave it empty if you have no site yet
4. Tick the terms checkbox and click **"Generate API Key"**.
5. The key appears immediately and stays available at
   **https://www.pexels.com/api/key/**.

### Where it goes

In `.env`, on the line `PEXELS_API_KEY=`

---

## 2. Google Cloud — Places API (New)

The longest part, and the only one that carries any cost risk. Read it through
before clicking.

### What it does

Places API is the source of business data: name, address, rating, review count,
phone, and most importantly **whether the business has a website**. The whole
ranking depends on it.

**Without it:** the tool falls back to OpenStreetMap, which is free and needs
no key, but has no ratings and no review counts. Two of the five scoring rules
stop working, so you cannot tell a bakery with 300 reviews and a 4.7 rating
(an ideal client) from one with 4 reviews (probably dead).

### Cost

**Partly free, and this needs care.**

Google requires a linked card before it allows any Maps Platform call. There is
no way around that. However:

- A free monthly allowance resets on the first of each month.
- Google bills by **the most expensive field you request**. This tool asks for
  phone, rating and review count, which are Enterprise-tier fields, so each
  Text Search call lands in the tier with the smallest free allowance —
  **1,000 calls per month**.
- The limit inside the tool is therefore **900 calls**, deliberately below it.

In practice: one call returns up to 20 businesses, and Google caps a single
query at three pages, so one fully paginated search costs 3 calls and returns
up to 60 businesses. 900 calls is roughly 300 such searches per month.

> Google changes these numbers from time to time. Check the current figures at
> **https://mapsplatform.google.com/pricing/**

### Three independent brakes

1. **A quota in the Cloud Console** (steps 7 and 8) — Google physically refuses
   calls past the ceiling. This is the only brake that actually stops spending.
2. **The counter in this tool** — tracked in `data/usage.json`, stops at 900.
3. **A budget alert** (step 9) — ⚠️ **emails you, stops nothing.** Never rely
   on it alone.

### Steps

**1. Open the console** — **https://console.cloud.google.com/**, sign in, and
accept the Terms of Service with **"AGREE AND CONTINUE"**.

If you are blocked with *Google Cloud access blocked*, Google now requires
2-step verification on the account. Click **"Enable MFA"**, turn on 2-Step
Verification, wait two minutes, and refresh.

**2. Create a project** (a drawer holding your key and quotas)
- Top bar, project dropdown left of the search box → **"NEW PROJECT"**
- **Project name:** `lead-finder-site-builder`, organization left as `No organization`
- **"CREATE"**, wait 10–20 seconds
- Reopen the dropdown and **select `lead-finder-site-builder`**. Confirm its name shows in
  the top bar before continuing.

**3. Link a card**
- ☰ **Navigation menu** → **"Billing"** → **"LINK A BILLING ACCOUNT"** →
  **"CREATE BILLING ACCOUNT"**
- Country, then **Account type: Individual**
- Name, address, card. Google places a verification hold of about one unit of
  currency and releases it within days. It is not a charge.
- **"START MY FREE TRIAL"** / **"SUBMIT AND ENABLE BILLING"**

If you see *Cannot create another individual profile for the same country*, you
already have a personal Google payments profile from Play, YouTube or similar.
Do not fill in the Organization form. Cancel, refresh, and pick the existing
profile from the dropdown above *Contact information*. If the dropdown does not
appear, sign out of every other Google account in the browser and retry.

**4. Enable the API** — ⚠️ two similar names exist
- ☰ → **"APIs & Services"** → **"Library"** → search `Places API`
- Open the card reading exactly **"Places API (New)"**, not the older
  **"Places API"**
- Click **"ENABLE"**

**5. Create the key**
- ☰ → **"APIs & Services"** → **"Credentials"**
- **"+ CREATE CREDENTIALS"** → **"API key"**
- Copy it into `.env` right away, then click **"Edit API key"**

**6. Restrict the key**
- **Name:** `lead-finder-key`
- **Application restrictions:** leave **"None"**. *IP addresses* looks safer but
  a home IP changes and the script would break every other day.
- **API restrictions:** **"Restrict key"** → tick **only "Places API (New)"**,
  so a leaked key cannot reach any other Google service
- **"SAVE"**

**7. Set the quota — the most important step here**

Everything else is convenience. This is the only thing standing between you and
a bill if code loops and fires 50,000 calls.

- ☰ → **"Google Maps Platform"** → **"Quotas"**
  (direct link: **https://console.cloud.google.com/google/maps-apis/quotas**)
- **API** dropdown → **"Places API (New)"**
- **"Quotas"** tab → find a row containing **"per day"**, preferring one that
  mentions **Text Search**
- Tick it, click the **pencil**, enter **`50`**, **"SAVE"**

50 per day still allows 16 fully paginated searches daily and cannot overrun
900 in a month.

**8. If that screen will not let you edit**
- ☰ → **"APIs & Services"** → **"Enabled APIs & services"** →
  **"Places API (New)"** → **"Quotas & System Limits"**
- Filter for `per day`, tick the row, pencil, `50`, **SAVE**

**9. Budget alert**
- ☰ → **"Billing"** → **"Budgets & alerts"** → **"CREATE BUDGET"**
- Name `lead-finder-alarm`, project `lead-finder-site-builder`
- **Budget type:** *Specified amount*, **Target amount:** `1`
- Thresholds 50/90/100%, email to your account, **"FINISH"**

### Where it goes

In `.env`, on the line `GOOGLE_MAPS_API_KEY=`

### Creating the `.env` file

From the project folder:

```powershell
Copy-Item .env.example .env
notepad .env
```

Paste the keys after the `=` signs, no quotes and no spaces:

```
GOOGLE_MAPS_API_KEY=AIzaSyC3xK9...
PEXELS_API_KEY=563492ad6f91...
```

`.env` is already in `.gitignore`.

---

## 3. GitHub

### What it does

A backup of the code, and a public shopfront — an open repository you can put
in a CV or send to a client as proof of work.

**Without it:** the project exists only on your desktop, and a disk failure
takes everything with it.

### Cost

Free. Public repositories are unlimited, `gh` is free and open source, and no
card is involved.

### Steps

**1. Account** — **https://github.com/signup**. Choose the username carefully;
it appears in the address of every project you publish.

**2. Install `gh` (GitHub CLI)**

```powershell
winget install --id GitHub.cli
```

Then **close PowerShell and open a new window** — until you do, the system
still holds the old list of commands. Verify:

```powershell
gh --version
```

**3. Sign in**

```powershell
gh auth login
```

Answer with arrow keys and Enter:

1. *What account do you want to log into?* → **GitHub.com**
2. *What is your preferred protocol for Git operations?* → **HTTPS**
3. *Authenticate Git with your GitHub credentials?* → **Yes**
4. *How would you like to authenticate?* → **Login with a web browser**
5. Note the `XXXX-XXXX` code, press Enter, paste it in the browser, then
   **"Authorize github"**

`gh` stores the token in Windows Credential Manager. If you picked SSH by
mistake, switch afterwards with `gh config set git_protocol https` followed by
`gh auth setup-git`.

**4. Create an empty repository** — ⚠️ this is where it goes wrong

- **https://github.com/new**
- **Repository name:** `lead-finder-site-builder`
- **Description:**
  `Automatically find local businesses without a website, then generate a ready-to-deploy site and outreach message for each one.`
- **Public**
- **Tick none of these:** ☐ *Add a README file* ☐ *Add .gitignore*
  ☐ *Choose a license*
- **"Create repository"**

**Why nothing is ticked:** each of those options creates a first commit on
GitHub. Your machine already has its own first commit. Git would see two
unrelated histories of the same project and refuse to merge them
(`refused to merge unrelated histories`). The README, licence and `.gitignore`
are created locally and travel up with the first push.

---

## Checklist

- [ ] `.env` exists with `PEXELS_API_KEY` filled in
- [ ] `GOOGLE_MAPS_API_KEY` filled in
- [ ] Places API **(New)** enabled on project `lead-finder-site-builder`
- [ ] Key restricted to Places API (New) only
- [ ] **Daily quota set to 50**
- [ ] Budget alert at 1 unit of currency
- [ ] `gh --version` works and `gh auth login` succeeded
- [ ] Empty public repository created

The Google key is not required to start — without it the tool runs on
OpenStreetMap.

---

## Troubleshooting

| Message | Meaning | Fix |
|---|---|---|
| `REQUEST_DENIED` or `403` | key inactive, or API not enabled | steps 4 and 6 |
| `This API project is not authorized to use this API` | the old "Places API" was enabled instead of "(New)" | step 4 |
| `You must enable Billing` | no card linked | step 3 |
| `gh: command not found` | terminal still holds the old PATH | open a new PowerShell |
| `RESOURCE_EXHAUSTED` / `429` | daily quota hit | the brake is working — wait for tomorrow |
| `504 Gateway Timeout` from Overpass | free OpenStreetMap servers are overloaded | try again in a few minutes |
