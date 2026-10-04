# Retail pipeline + Power BI dashboard

Python script that processes retail transactions, calculates monthly KPIs and flags suspicious rows. A Power BI dashboard reads the results. GitHub Actions runs the script every Monday.

Data: Online Retail II (UCI Machine Learning Repository), about 1M transactions, Dec 2009 - Dec 2011.

## About this project

I made this to understand how data automation actually works. I already knew Excel, some SQL and Python, but Power BI was new to me, so I wanted a project where I could try all of it together. I chose retail transactions because the data is messy in a way that reminds me of accounting work: returns, duplicates, weird prices. This is my first project like this

## Dashboard

![Financial KPIs](powerbi/screenshots/financial_kpis.png)

![Data Quality](powerbi/screenshots/data_quality.png)

## Project structure

```
.github/workflows/pipeline.yml   weekly schedule
data/                            input file and generated CSVs
powerbi/                         Power BI dashboard
screenshots/                     dashboard images
exploration.ipynb                exploration before the script
pipeline.py                      the pipeline
requirements.txt                 dependencies
```

## What the pipeline does

- loads and checks the data
- calculates monthly revenue, orders and customers
- flags duplicates, bad prices, bad quantities and outliers (z-score > 5)
- saves the results to `data/`

## How to run

```
pip install -r requirements.txt
python pipeline.py
```

Then open the `.pbix` file and click Refresh.

## Notes

- December 2011 is partial (data stops on the 9th).
- Power BI needs a manual Refresh after `git pull`.
