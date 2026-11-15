$content = @'
name: FXBOT Daily Run
on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:
jobs:
  daily:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python predictor_v3.py
      - run: python check.py
      - run: python paper_trade_v2.py
      - run: python today_signal.py
      - run: |
          git config --global user.email 'bot@fxbot.com'
          git config --global user.name 'FXBOT Daily Bot'
          git add -f results/ today_signal.txt
          git commit -m 'Auto-update 15min'
          git push
'@

New-Item -ItemType Directory -Force -Path .github/workflows | Out-Null
$content | Out-File -Encoding utf8 .github/workflows/daily.yml -Force
Write-Host "Created daily.yml with */15" -ForegroundColor Green
Get-Content .github/workflows/daily.yml
