# Ship position

Every 30 minutes, a GitHub Action checks where the CSL Laurentien is
(MMSI 316001637) using the free aisstream.io AIS feed and saves it to
`position.json`. The Roku family calendar app reads that file.

## Setup (one time)

1. Get a free API key at https://aisstream.io (sign in, then Account › API keys).
2. Create a **public** GitHub repository and upload everything in this folder,
   including the hidden `.github` folder.
3. In the repo: **Settings › Secrets and variables › Actions › New repository secret**.
   Name it `AISSTREAM_API_KEY` and paste the key.
4. In **Settings › Actions › General › Workflow permissions**, choose
   **Read and write permissions** so the Action can save `position.json`.
5. Go to the **Actions** tab, open **Ship position**, and click **Run workflow**
   to test it. After a few minutes `position.json` should have a position in it.

The Roku app reads:
`https://raw.githubusercontent.com/hahnsolo/ship-position/main/position.json`

## Notes

- Public repo, because GitHub Actions minutes are free and unlimited there.
  Ship positions are public AIS data anyway. Your API key stays private in Secrets.
- If the ship is out of range of shore receivers, the last known position is
  kept with `"fresh": false`, and the app shows how long ago it was seen.
- To track a different ship, change `SHIP_MMSI` in `.github/workflows/ship-position.yml`.
