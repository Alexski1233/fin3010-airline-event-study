# FIN3010 Airline Event Study

This is a cleaned-up version of a FIN-3010 course project on abnormal stock returns during the first COVID-19 market shock.

The project looks at Norwegian Air Shuttle and a small sample of European airlines around 11 March 2020, when the WHO declared COVID-19 a global pandemic. The analysis uses CAPM-style expected returns, abnormal returns, CAR/CAAR, and simple significance tests.

The submitted paper received a B. I have kept the repo simple and close to the original work rather than trying to make it look like a production research package.

## Project Structure

```text
.
├── src/
│   ├── norwegian_ols_EW.py   # CAPM estimate for Norwegian Air
│   ├── nas_ar.py             # Norwegian Air event-window abnormal returns
│   └── euro_car.py           # European airline CAAR analysis
├── notebooks/                # cleaned exploratory notebooks
├── data/                     # data used for the analysis
└── report/                   # submitted exam paper
```

## How to Run

Install the Python packages:

```bash
pip install -r requirements.txt
```

Run the scripts from the project root:

```bash
/opt/anaconda3/bin/python src/norwegian_ols_EW.py
/opt/anaconda3/bin/python src/nas_ar.py
/opt/anaconda3/bin/python src/euro_car.py
```

You can also use `python` if it points to an environment with the packages in `requirements.txt`.

## Example Results

Using the local data currently in this project:

- Norwegian Air CAPM beta: `1.7795`
- Norwegian Air CAR in the `[-10, +10]` window: `-28.50%`
- European airline CAAR in the `[-10, +10]` window: `-14.97%`, with `p = 0.010`

## Notes

- The data and report are included because this repository is meant to preserve the submitted course project.
- Some scripts are cleaner than the notebooks. The notebooks are included as supporting working material, while the scripts in `src/` are the main version to run.

## Main Question

To what extent did airline stock prices incorporate new public information related to the COVID-19 pandemic announcement?
