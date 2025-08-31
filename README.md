# Anime Scraper API

This is a Flask API that scrapes video links from witanime.red using Playwright.

## Deployment

Click the button below to deploy this API to Railway with one click.

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/volt-PRd/my_test)

---

### How to Use

After deployment, send a POST request to the `/scrape` endpoint of your new Railway URL.

**Request Body:**
```json
{
    "url": "https://witanime.red/episode/some-episode-name/"
}
